import asyncio
import logging
from datetime import UTC, datetime

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app import database, models
from app.ai_schema import AIExtractionMetadata, AIExtractionResponse
from app.services.ai_service import AIService
from app.services.item_service import ItemService
from app.services.notification_service import NotificationService
from app.services.browserless_service import browserless_service
from app.services.tracking_scraper_service import ScraperService, ScrapeConfig

logger = logging.getLogger(__name__)
scheduler = AsyncIOScheduler()

PRICE_CHANGE_THRESHOLD_PERCENT = 20.0
LOW_CONFIDENCE_THRESHOLD = 0.7


def _get_thresholds():
    with database.SessionLocal() as session:
        settings = {s.key: s.value for s in session.query(models.Settings).all()}
        return {
            "price": float(settings.get("confidence_threshold_price", "0.5")),
            "stock": float(settings.get("confidence_threshold_stock", "0.5")),
        }


def _update_db_result(
    item_id: int,
    extraction: AIExtractionResponse,
    metadata: AIExtractionMetadata,
    thresholds: dict,
    screenshot_path: str,
):
    with database.SessionLocal() as session:
        item = session.query(models.Item).filter(models.Item.id == item_id).first()
        if not item:
            return None, None

        old_price, old_stock = item.current_price, item.in_stock
        price, in_stock = extraction.price, extraction.in_stock
        p_conf, s_conf = extraction.price_confidence, extraction.in_stock_confidence

        if price is not None:
            if p_conf >= thresholds["price"]:
                if (
                    old_price
                    and (abs(price - old_price) / old_price * 100 > PRICE_CHANGE_THRESHOLD_PERCENT)
                    and p_conf < LOW_CONFIDENCE_THRESHOLD
                ):
                    item.last_error = f"Uncertain: Large price change with low confidence ({p_conf:.2f})"
                else:
                    item.last_error = None
                item.current_price = price
                item.current_price_confidence = p_conf

            session.add(
                models.PriceHistory(
                    item_id=item.id,
                    price=price,
                    screenshot_path=screenshot_path,
                    price_confidence=p_conf,
                    in_stock_confidence=s_conf,
                    ai_model=metadata.model_name,
                    ai_provider=metadata.provider,
                    prompt_version=metadata.prompt_version,
                    repair_used=metadata.repair_used,
                )
            )

        if in_stock is not None and s_conf >= thresholds["stock"]:
            item.in_stock = in_stock
            item.in_stock_confidence = s_conf

        item.last_checked = datetime.now(UTC)
        item.is_refreshing = False
        if item.last_error and not item.last_error.startswith("Uncertain:"):
            item.last_error = None

        session.commit()
        return old_price, old_stock


def _update_db_error(item_id, error_msg):
    with database.SessionLocal() as session:
        if item := session.query(models.Item).filter(models.Item.id == item_id).first():
            item.is_refreshing = False
            item.last_error = error_msg
            item.last_checked = datetime.now(UTC)
            session.commit()


def _update_db_product_unavailable(item_id: int, error_msg: str, screenshot_path: str | None = None):
    """Mark item as unavailable (product no longer exists on retailer site)."""
    with database.SessionLocal() as session:
        if item := session.query(models.Item).filter(models.Item.id == item_id).first():
            item.is_refreshing = False
            item.is_available = False  # Mark product as unavailable
            item.in_stock = False  # Also mark as out of stock
            item.last_error = error_msg
            item.last_checked = datetime.now(UTC)

            # Record in history if we have a screenshot
            if screenshot_path:
                session.add(
                    models.PriceHistory(
                        item_id=item.id,
                        price=item.current_price or 0,  # Keep last known price
                        screenshot_path=screenshot_path,
                        price_confidence=0.0,  # Zero confidence = unavailable
                        in_stock_confidence=1.0,  # High confidence it's unavailable
                        ai_model="unavailable-detector",
                        ai_provider="internal",
                        prompt_version="unavailable-v1",
                        repair_used=False,
                    )
                )

            session.commit()


async def process_item_check(item_id: int):
    loop = asyncio.get_running_loop()
    with database.SessionLocal() as session:
        item_data, config = await loop.run_in_executor(None, ItemService.get_item_data_for_checking, session, item_id)

    if not item_data:
        logger.error(f"process_item_check: Item ID {item_id} not found")
        return

    try:
        logger.info(f"Checking item: {item_data['name']} ({item_data['url']})")
        # Use independent ScraperService for tracking
        from app.services.tracking_scraper_service import ScraperService

        screenshot_path, html_content, final_url, page_title = await ScraperService.scrape_item(
            url=item_data["url"], selector=item_data["selector"], item_id=item_id, return_html=True
        )

        if not screenshot_path:
            raise Exception("Failed to capture screenshot")

        # Detect Amazon login wall/redirection/block
        is_amazon = "amazon" in item_data["url"]
        is_blocked = False

        if is_amazon:
            login_terms = ["signin", "captcha", "s'identifier", "log in", "login"]
            title_lower = page_title.lower()
            if (
                any(term in final_url.lower() for term in login_terms)
                or any(term in title_lower for term in login_terms)
                or "amazon.fr: s'identifier" in title_lower
            ):
                is_blocked = True

        if is_blocked:
            logger.warning(f"Amazon Bot Detection triggered for item {item_id}. Title: {page_title}, URL: {final_url}")
            await loop.run_in_executor(None, _update_db_error, item_id, f"Amazon Bot Detection: {page_title}")
            return

        # Detect Action.com product unavailability
        is_action = "action.com" in item_data["url"]
        is_product_unavailable = False

        if is_action:
            unavailable_terms = [
                "showproductwarning=true",
                "produit indisponible",
                "malheureusement, ce produit est actuellement indisponible",
            ]
            final_url_lower = final_url.lower()
            html_lower = html_content.lower() if html_content else ""

            if any(term in final_url_lower for term in unavailable_terms) or any(
                term in html_lower for term in unavailable_terms
            ):
                is_product_unavailable = True

        if is_product_unavailable:
            logger.warning(f"Product unavailable detected for item {item_id} on Action.com")
            await loop.run_in_executor(
                None, _update_db_product_unavailable, item_id, "Produit indisponible sur Action.com", screenshot_path
            )

            # Send notification if configured
            if item_data["notification_channel"]:
                await NotificationService.send_notification(
                    item_data["notification_channel"],
                    title=f"⚠️ Produit indisponible : {item_data['name']}",
                    body=f"Le produit '{item_data['name']}' n'est plus disponible sur Action.com.\n{item_data['url']}",
                )
            return

        # HYBRID EXTRACTION STRATEGY (Aligned with ImprovedSearchService)
        # 1. Try specialized parser (if available) or JSON-LD
        price = None
        in_stock = True

        # Site-specific parser (Gifi)
        from urllib.parse import urlparse

        domain = urlparse(item_data["url"]).netloc
        if "gifi.fr" in domain:
            from app.services.parsers.gifi_parser import GifiParser

            try:
                parser = GifiParser()
                details = parser.parse_product_details(html_content, item_data["url"])
                if details.get("price") is not None:
                    price = details["price"]
                    in_stock = details.get("in_stock", True)
                    logger.info(f"GifiParser found price: {price}€")
            except Exception as e:
                logger.debug(f"GifiParser failed: {e}")

        # Simple JSON-LD extract (if not found by specific parser)
        if price is None:
            import json

            try:
                from bs4 import BeautifulSoup

                soup = BeautifulSoup(html_content, "html.parser")
                scripts = soup.find_all("script", type="application/ld+json")
                for script in scripts:
                    if script.string:
                        try:
                            data = json.loads(script.string)
                            if isinstance(data, list):
                                data = data[0]
                            if data.get("@type") == "Product" and "offers" in data:
                                offers = data["offers"]
                                if isinstance(offers, list) and offers:
                                    offers = offers[0]
                                if "price" in offers:
                                    price = float(str(offers["price"]).replace(",", "."))
                                    break
                        except:
                            pass
            except Exception as e:
                logger.debug(f"JSON-LD extraction failed: {e}")

        # 2. Try AIPriceExtractor (Text AI - Gemma 3) - Very reliable for search
        # DISABLED FOR VISION PRIORITY (User Request: Option 2)
        # from app.services.ai_price_extractor import AIPriceExtractor
        # if price is None:
        #     price = await AIPriceExtractor.extract_price(html_content, item_data["name"])
        #     if price:
        #         logger.info(f"AIPriceExtractor (Text) found price: {price}€")

        # 3. Fallback/Verification with AIService (Vision AI - Gemini)
        extraction = None
        metadata = None

        if price is not None:
            # Create a synthetic AI response if we already have a high-confidence price
            extraction = AIExtractionResponse(
                price=price, in_stock=in_stock, price_confidence=0.95, in_stock_confidence=0.9, source_type="text"
            )
            metadata = AIExtractionMetadata(
                model_name="hybrid-text-parser",
                provider="internal-hybrid",
                prompt_version="hybrid-v2",
                repair_used=False,
            )
        else:
            # Fallback to Vision AI if text extraction failed
            # Clean text properly before sending to AI
            from app.utils.text import clean_text

            cleaned_html = clean_text(html_content)
            if not (ai_result := await AIService.analyze_image(screenshot_path, page_text=cleaned_html[:10000])):
                raise Exception("AI analysis (Vision) failed")
            extraction, metadata = ai_result

        thresholds = await loop.run_in_executor(None, _get_thresholds)
        old_price, old_stock = await loop.run_in_executor(
            None, _update_db_result, item_id, extraction, metadata, thresholds, screenshot_path
        )

        # Check for notifications
        if item_data["notification_channel"] and extraction.price:
            channel = item_data["notification_channel"]
            logger.info(
                f"📢 Notification check for item {item_id}: old_price={old_price}, new_price={extraction.price}, target_price={item_data['target_price']}"
            )

            notification_sent = False

            # CASE 1: Target price is set -> notify only when target is reached
            if item_data["target_price"]:
                if extraction.price <= item_data["target_price"]:
                    # Only notify if we haven't already notified for this price
                    if not old_price or old_price > item_data["target_price"]:
                        logger.info(
                            f"✅ Target price reached for {item_data['name']}: {extraction.price}€ <= {item_data['target_price']}€"
                        )
                        await NotificationService.send_notification(
                            channel,
                            title=f"🎯 Prix cible atteint : {item_data['name']}",
                            body=f"Le prix de {item_data['name']} est passé à {extraction.price}€ (Cible: {item_data['target_price']}€)\n{item_data['url']}",
                        )
                        notification_sent = True
                else:
                    logger.info(f"ℹ️ Price {extraction.price}€ not yet at target {item_data['target_price']}€")

            # CASE 2: No target price -> notify on ANY price drop
            else:
                if old_price and extraction.price < old_price:
                    drop_percent = (old_price - extraction.price) / old_price * 100
                    logger.info(f"📉 Price drop detected for {item_data['name']}: {drop_percent:.1f}%")
                    await NotificationService.send_notification(
                        channel,
                        title=f"📉 Baisse de prix : {item_data['name']}",
                        body=f"Le prix de {item_data['name']} a baissé de {drop_percent:.1f}% !\nNouveau prix : {extraction.price}€ (Ancien: {old_price}€)\n{item_data['url']}",
                    )
                    notification_sent = True

                # Also notify on significant price increases (>= 5%)
                elif old_price and extraction.price > old_price:
                    increase_percent = (extraction.price - old_price) / old_price * 100
                    if increase_percent >= 5:
                        logger.info(f"📈 Price increase detected for {item_data['name']}: {increase_percent:.1f}%")
                        await NotificationService.send_notification(
                            channel,
                            title=f"📈 Hausse de prix : {item_data['name']}",
                            body=f"Le prix de {item_data['name']} a augmenté de {increase_percent:.1f}%.\nNouveau prix : {extraction.price}€ (Ancien: {old_price}€)\n{item_data['url']}",
                        )
                        notification_sent = True

            if not notification_sent:
                logger.info(f"ℹ️ No notification triggered for item {item_id} (no significant change)")
        else:
            if not item_data["notification_channel"]:
                logger.debug(f"⚠️ Item {item_id} has no notification channel assigned.")
            if not extraction.price:
                logger.debug(f"⚠️ Item {item_id} has no extracted price.")

    except Exception as e:
        logger.error(f"Error in process_item_check: {e}")
        await loop.run_in_executor(None, _update_db_error, item_id, str(e))


async def scheduled_refresh():
    logger.info("Heartbeat: Checking for items due for refresh")
    loop = asyncio.get_running_loop()
    try:
        with database.SessionLocal() as session:
            due_items = await loop.run_in_executor(None, ItemService.get_due_items, session)

        for item_id, _, _ in due_items:
            await process_item_check(item_id)
    except Exception as e:
        logger.error(f"Error in scheduled refresh: {e}", exc_info=True)
