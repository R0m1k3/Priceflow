import asyncio
import logging
import re
from datetime import UTC, datetime
from urllib.parse import urlparse

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from bs4 import BeautifulSoup

from app import database, models
from app.ai_schema import AIExtractionMetadata, AIExtractionResponse
from app.services.ai_service import AIService
from app.services.item_service import ItemService
from app.services.notification_service import NotificationService
from app.services.tracking_scraper_service import ScraperService
from app.utils.text import clean_text

logger = logging.getLogger(__name__)
scheduler = AsyncIOScheduler()

PRICE_CHANGE_THRESHOLD_PERCENT = 20.0
LOW_CONFIDENCE_THRESHOLD = 0.7
TITLE_SIMILARITY_THRESHOLD = 0.4  # Below this, consider product changed


def _normalize_title(title: str) -> str:
    """Normalize title for comparison: lowercase, remove common suffixes/prefixes, strip."""
    if not title:
        return ""

    title = title.lower().strip()

    # Standardize V2, V3 etc. (v2 -> 2) for better matching on Amazon
    title = re.sub(r"\bv(\d+)\b", r"\1", title)

    # Remove common website suffixes/prefixes
    patterns = [
        r" - b&m$",
        r" \| b&m$",
        r" - action$",
        r" \| action$",
        r" - gifi$",
        r" \| gifi$",
        r" - amazon$",
        r" \| amazon$",
        r"^b&m stores : ",
        r"^gifi : ",
        r"^action : ",
    ]
    for pattern in patterns:
        title = re.sub(pattern, "", title)

    # Separate numbers from letters (handles cases like 'Blanc40' or '100pièces')
    title = re.sub(r"([a-zA-Z])(\d)", r"\1 \2", title)
    title = re.sub(r"(\d)([a-zA-Z])", r"\1 \2", title)

    # Remove non-word characters (punctuation) early to simplify regex
    title = re.sub(r"[^\w\s]", " ", title)
    title = " ".join(title.split())

    # Remove technical metadata at the end (Action specific noise)
    # Match various patterns like "0 09 pce 342" or "100 pièces" etc.
    title = re.sub(r"\s+\d+\s+\d+\s+pce.*$", "", title)
    title = re.sub(r"\s+\d+\s+pièces.*$", "", title)
    title = re.sub(r"\s+\d+\s+€.*$", "", title)
    title = re.sub(r"\s+\d+\s+\d+\s+€.*$", "", title)

    return title.strip()


def _is_generic_or_error_title(title: str) -> bool:
    """Check if the title is a generic error, bot detection, or placeholder."""
    if not title:
        return True
    t = title.lower()
    error_terms = [
        "access denied",
        "just a moment",
        "cloudflare",
        "attention required",
        "erreur 403",
        "403 forbidden",
        "security check",
        "robot or human",
        "bot verification",
        "loading",
        "chargement",
        "veuillez patienter",
        "site non accessible",
        "maintenance",
        "un instant",
    ]
    if any(term in t for term in error_terms):
        return True

    # Titles that are just the domain name are often placeholders or homepages
    domain_titles = ["bmstores.fr", "gifi.fr", "action.com", "amazon.fr"]
    if t.strip() in domain_titles:
        return True

    return False


def _titles_match(stored_name: str, page_title: str) -> bool:
    """
    Check if the page title still matches the stored product name.
    Returns True if they match (product still exists), False if different (product replaced).
    """
    if not stored_name or not page_title:
        return True  # Can't compare, assume match

    norm_stored = _normalize_title(stored_name)
    norm_page = _normalize_title(page_title)

    # If one is empty after normalization, assume match
    if not norm_stored or not norm_page:
        return True

    # Check if stored name is contained in page title or vice versa
    if norm_stored in norm_page or norm_page in norm_stored:
        return True

    # Check word overlap ratio (Jaccard similarity)
    stored_words = set(norm_stored.split())
    page_words = set(norm_page.split())

    if not stored_words or not page_words:
        return True

    intersection = stored_words & page_words
    union = stored_words | page_words
    similarity = len(intersection) / len(union) if union else 0

    is_match = similarity >= TITLE_SIMILARITY_THRESHOLD

    # Fallback for short stored names: if 75% of words match, it's likely the same product
    # This helps with long descriptive titles (Amazon) vs short stored names
    if not is_match and len(stored_words) <= 5:
        match_ratio = len(intersection) / len(stored_words) if stored_words else 0
        if match_ratio >= 0.75:
            is_match = True

    return is_match


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

                # Auto-reset availability if price was successfully extracted
                if item.is_available is False:
                    item.is_available = True
                    item.last_error = None
                    logger.info(f"Item {item.id} marked as available again (price extracted)")

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
        item_data, _ = await loop.run_in_executor(None, ItemService.get_item_data_for_checking, session, item_id)

    if not item_data:
        logger.error(f"process_item_check: Item ID {item_id} not found")
        return

    try:
        logger.info(f"Checking item: {item_data['name']} ({item_data['url']}) [PATCH V2 LOADED]")
        # Use independent ScraperService for tracking
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

        # Detect product replacement by comparing page title with stored name
        # If title has changed significantly, the original product was replaced
        titles_match = _titles_match(item_data["name"], page_title)
        is_generic_title = _is_generic_or_error_title(page_title)

        if not titles_match:
            # If titles don't match, check if it's because of a generic bot detection/blocker
            # We only do this check if titles_match is False to avoid false positives on valid pages
            # If titles don't match, check if it's because of a generic bot detection/blocker
            # We only do this check if titles_match is False to avoid false positives on valid pages
            bot_terms_title = [
                "captcha",
                "robot or human",
                "bot verification",
                "security check",
                "access denied",
                "403 forbidden",
                "just a moment",
            ]
            # HTML terms must be stricter to avoid catching footer text (like "Cloudflare Ray ID")
            bot_terms_html = [
                "captcha",
                "robot or human",
                "bot verification",
                "security check",
                "access denied",
                "attention required",
                "enable javascript",
            ]
            
            html_lower = html_content.lower() if html_content else ""
            
            # Check Title first (Strong signal)
            if any(term in page_title.lower() for term in bot_terms_title):
                 logger.warning(f"Bot detection / blocker confirmed (Title match) for item {item_id} (Title: {page_title})")
                 await loop.run_in_executor(
                    None, _update_db_error, item_id, f"Accès bloqué par le site (Bot Detection) : {page_title}"
                 )
                 return

            # Check HTML ONLY if title is also generic or fails validation, 
            # OR if the match is very specific (like huge CAPTCHA text)
            # BUT avoid "cloudflare" in HTML unless title is strictly "Just a moment..."
            if any(term in html_lower for term in bot_terms_html):
                logger.warning(f"Bot detection / blocker confirmed (HTML match) for item {item_id}")
                await loop.run_in_executor(
                    None, _update_db_error, item_id, f"Accès bloqué par le site (Bot Detection HTML)"
                )
                return

            # If it's a generic or error title, don't mark as unavailable, just mark as error
            if is_generic_title:
                logger.warning(f"Generic/Error title detected for item {item_id}: '{page_title}'")
                await loop.run_in_executor(
                    None, _update_db_error, item_id, f"Site inaccessible ou titre générique : {page_title}"
                )
                return

            # Specific check for Action.com unavailability (after title mismatch)
            is_action = "action.com" in item_data["url"]
            if is_action:
                unavailable_terms = [
                    "showproductwarning=true",
                    "produit indisponible",
                    "malheureusement, ce produit est actuellement indisponible",
                ]
                final_url_lower = final_url.lower()
                html_lower = html_content.lower() if html_content else ""

                if any(term in final_url_lower for term in unavailable_terms) or any(
                    term in html_lower
                    for term in [
                        # Use more specific terms for HTML to avoid false positives in random text or meta
                        "malheureusement, ce produit est actuellement indisponible",
                        ">produit indisponible<",
                        ">ce produit est indisponible<",
                        "product-unavailable-message",
                    ]
                ):
                    logger.warning(f"Product unavailable confirmed for item {item_id} on Action.com")
                    await loop.run_in_executor(
                        None,
                        _update_db_product_unavailable,
                        item_id,
                        "Produit indisponible sur Action.com",
                        screenshot_path,
                    )

                    # Send notification if configured
                    if item_data["notification_channel"]:
                        await NotificationService.send_notification(
                            item_data["notification_channel"],
                            title=f"⚠️ Produit indisponible : {item_data['name']}",
                            body=f"Le produit '{item_data['name']}' n'est plus disponible sur Action.com.\n{item_data['url']}",
                        )
                    return

            # If it's a 404 indication in the title, it's a real unavailability
            if "404" in page_title.lower() or "page non trouvée" in page_title.lower():
                logger.info(f"404 detected in title for item {item_id}")
            else:
                logger.warning(
                    f"Product replacement detected for item {item_id}. "
                    f"Stored: '{item_data['name']}', Page title: '{page_title}'"
                )

                # For Action.com, if we haven't confirmed unavailability above,
                # don't mark as unavailable yet, just mark as potential replacement error
                # unless the title is almost completely different
                if is_action:
                    # Check if at least some significant words match
                    norm_stored = _normalize_title(item_data["name"])
                    norm_page = _normalize_title(page_title)
                    stored_words = set(norm_stored.split())
                    page_words = set(norm_page.split())
                    intersection = stored_words & page_words
                    if len(intersection) >= 2 or (len(stored_words) <= 3 and len(intersection) >= 1):
                        logger.warning(
                            f"Borderline title match for Action.com item {item_id}. Keeping as available but marking error."
                        )
                        await loop.run_in_executor(
                            None,
                            _update_db_error,
                            item_id,
                            f"Titre différent mais produit probablement correct : {page_title}",
                        )
                        return

            await loop.run_in_executor(
                None,
                _update_db_product_unavailable,
                item_id,
                f"Produit retiré ou remplacé (titre: {page_title[:50]}...)"
                if len(page_title) > 50
                else f"Produit retiré ou remplacé (titre: {page_title})",
                screenshot_path,
            )

            # Send notification if configured
            if item_data["notification_channel"]:
                await NotificationService.send_notification(
                    item_data["notification_channel"],
                    title=f"⚠️ Produit remplacé : {item_data['name']}",
                    body=f"Le produit '{item_data['name']}' semble avoir été remplacé.\nNouveau titre: {page_title}\n{item_data['url']}",
                )
            return

        # If titles match and product was previously marked unavailable, reset it
        if titles_match:

            def _reset_availability(item_id: int):
                with database.SessionLocal() as session:
                    if item := session.query(models.Item).filter(models.Item.id == item_id).first():
                        if item.is_available is False:
                            item.is_available = True
                            item.last_error = None
                            session.commit()
                            logger.info(f"Item {item_id} marked as available again (title matches)")

            await loop.run_in_executor(None, _reset_availability, item_id)

        # HYBRID EXTRACTION STRATEGY (Aligned with ImprovedSearchService)
        # 1. Try specialized parser (if available) or JSON-LD
        price = None
        in_stock = True

        # Site-specific parser (Gifi)
        domain = urlparse(item_data["url"]).netloc
        if "gifi.fr" in domain:
            try:
                from app.services.parsers.gifi_parser import GifiParser

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
            try:
                soup = BeautifulSoup(html_content, "html.parser")
                scripts = soup.find_all("script", type="application/ld+json")
                for script in scripts:
                    if script.string:
                        try:
                            import json

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
