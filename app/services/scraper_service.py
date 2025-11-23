import asyncio
import logging
import os
import re
from urllib.parse import urlparse, urlunparse

from playwright.async_api import TimeoutError as PlaywrightTimeoutError
from playwright.async_api import async_playwright

logger = logging.getLogger(__name__)

BROWSERLESS_URL = os.getenv("BROWSERLESS_URL", "ws://browserless:3000")

# Nombre de tentatives pour le scraping
MAX_RETRIES = 2
RETRY_DELAY = 3  # secondes


def simplify_url(url: str) -> str:
    """
    Simplifie les URLs en supprimant les paramètres de tracking.
    Particulièrement utile pour Amazon qui a des URLs très longues.

    Exemples:
    - Amazon: https://www.amazon.fr/dp/B0CFYHHPPV?ref=... -> https://www.amazon.fr/dp/B0CFYHHPPV
    - Autres: garde l'URL originale si pas de simplification possible
    """
    try:
        parsed = urlparse(url)
        hostname = parsed.hostname or ""

        # Simplification pour Amazon
        if "amazon" in hostname:
            # Extraire l'ASIN (identifiant produit Amazon)
            # Format: /dp/ASIN ou /gp/product/ASIN
            asin_match = re.search(r"/(?:dp|gp/product)/([A-Z0-9]{10})", url)
            if asin_match:
                asin = asin_match.group(1)
                # Reconstruire une URL simple
                simplified = f"{parsed.scheme}://{parsed.netloc}/dp/{asin}"
                logger.info(f"URL Amazon simplifiée: {url[:80]}... -> {simplified}")
                return simplified

        # Pour les autres sites, supprimer les paramètres de tracking courants
        # mais garder les paramètres essentiels
        tracking_params = [
            "utm_source", "utm_medium", "utm_campaign", "utm_content", "utm_term",
            "ref", "ref_", "tag", "linkCode", "linkId", "camp", "creative",
            "crid", "dib", "dib_tag", "qid", "sprefix", "sr", "keywords",
            "fbclid", "gclid", "msclkid"
        ]

        if parsed.query:
            # Garder seulement les paramètres non-tracking
            from urllib.parse import parse_qs, urlencode
            params = parse_qs(parsed.query)
            filtered_params = {
                k: v[0] for k, v in params.items()
                if k.lower() not in tracking_params
            }
            new_query = urlencode(filtered_params) if filtered_params else ""
            simplified = urlunparse((
                parsed.scheme,
                parsed.netloc,
                parsed.path,
                parsed.params,
                new_query,
                ""  # fragment
            ))
            if simplified != url:
                logger.info(f"URL simplifiée: {url[:60]}... -> {simplified[:60]}...")
            return simplified

        return url

    except Exception as e:
        logger.warning(f"Erreur lors de la simplification de l'URL: {e}")
        return url


class ScraperService:
    @staticmethod
    async def scrape_item(  # noqa: PLR0913, PLR0912, PLR0915
        url: str,
        selector: str | None = None,
        item_id: int | None = None,
        smart_scroll: bool = False,
        scroll_pixels: int = 350,
        text_length: int = 0,
        timeout: int = 90000,
    ) -> tuple[str | None, str]:
        """
        Scrapes the given URL using Browserless and Playwright.
        Returns a tuple: (screenshot_path, page_text)

        Args:
            url: Target URL to scrape
            selector: Optional CSS selector to focus on
            item_id: Optional item ID for screenshot naming
            smart_scroll: Enable scrolling to load lazy content
            scroll_pixels: Number of pixels to scroll (must be positive)
            text_length: Number of characters to extract (0 = disabled)
            timeout: Page load timeout in milliseconds
        """
        # Simplifier l'URL avant le scraping
        original_url = url
        url = simplify_url(url)

        # Input validation
        if scroll_pixels <= 0:
            logger.warning(f"Invalid scroll_pixels value: {scroll_pixels}, using default 350")
            scroll_pixels = 350

        if timeout <= 0:
            logger.warning(f"Invalid timeout value: {timeout}, using default 90000")
            timeout = 90000

        # Retries avec backoff
        last_error = None
        for attempt in range(MAX_RETRIES + 1):
            if attempt > 0:
                logger.info(f"Tentative {attempt + 1}/{MAX_RETRIES + 1} pour {url}")
                await asyncio.sleep(RETRY_DELAY * attempt)

            result = await ScraperService._do_scrape(
                url=url,
                selector=selector,
                item_id=item_id,
                smart_scroll=smart_scroll,
                scroll_pixels=scroll_pixels,
                text_length=text_length,
                timeout=timeout,
            )

            if result[0] is not None:  # Screenshot réussi
                return result

            last_error = "Scraping failed"
            logger.warning(f"Tentative {attempt + 1} échouée pour {url}")

        logger.error(f"Toutes les tentatives ont échoué pour {url}")
        return None, ""

    @staticmethod
    async def _do_scrape(  # noqa: PLR0913, PLR0912, PLR0915
        url: str,
        selector: str | None = None,
        item_id: int | None = None,
        smart_scroll: bool = False,
        scroll_pixels: int = 350,
        text_length: int = 0,
        timeout: int = 90000,
    ) -> tuple[str | None, str]:
        """Exécute le scraping réel (appelé par scrape_item avec retries)."""
        async with async_playwright() as p:
            browser = None
            context = None
            page = None
            try:
                logger.info(f"Connecting to Browserless at {BROWSERLESS_URL}")

                # Utiliser l'endpoint WebSocket de Browserless
                # Format: ws://browserless:3000?token=xxx ou ws://browserless:3000
                browser = await p.chromium.connect_over_cdp(
                    BROWSERLESS_URL,
                    timeout=60000,  # 60s pour la connexion
                )

                context = await browser.new_context(
                    viewport={"width": 1920, "height": 1080},
                    user_agent=(
                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/120.0.0.0 Safari/537.36"
                    ),
                    locale="fr-FR",
                    timezone_id="Europe/Paris",
                    # Options supplémentaires pour éviter la détection
                    extra_http_headers={
                        "Accept-Language": "fr-FR,fr;q=0.9,en-US;q=0.8,en;q=0.7",
                        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
                    }
                )

                # Stealth mode / Ad blocking attempts
                await context.route("**/*", lambda route: route.continue_())

                page = await context.new_page()

                logger.info(f"Navigating to {url} (Timeout: {timeout}ms)")
                try:
                    # First wait for domcontentloaded - this is the minimum we need
                    await page.goto(url, wait_until="domcontentloaded", timeout=timeout)
                    logger.info(f"Page loaded (domcontentloaded): {url}")

                    # Then try to wait for networkidle, but don't fail if it times out
                    # This helps with heavy pages that never fully settle
                    try:
                        await page.wait_for_load_state("networkidle", timeout=5000)
                        logger.info("Network idle reached")
                    except PlaywrightTimeoutError:
                        logger.info("Network idle timed out (non-critical), proceeding...")

                except Exception as e:
                    logger.error(f"Error navigating to {url}: {e}")
                    # Try to take screenshot anyway if page partially loaded
                    pass

                # Wait a bit for dynamic content if needed
                await page.wait_for_timeout(2000)

                # Try to close common popups and cookie banners
                logger.info("Attempting to close popups and cookie banners...")
                popup_selectors = [
                    # === SITES SPÉCIFIQUES FRANÇAIS ===
                    # Amazon France
                    "#sp-cc-accept",
                    "#sp-cc-rejectall-link",
                    "input[data-action-type='DISMISS']",
                    "#a-popover-content-1 button",
                    "[data-action='a-popover-close']",
                    # E.Leclerc, Darty, Fnac
                    "#onetrust-accept-btn-handler",
                    ".onetrust-accept-btn-handler",
                    # Auchan
                    "#popin_tc_privacy_button_2",
                    ".popin_tc_privacy_button",
                    "#didomi-notice-agree-button",
                    # Carrefour
                    "[data-testid='accept-cookies-button']",
                    # Cdiscount
                    "#footer_tc_privacy_button_2",
                    ".privacy_prompt_accept",
                    # Boulanger
                    ".bcom-consent-accept-all",
                    "#cookieBanner-accept",
                    # Gifi, Centrakor, La Foir'Fouille (Magento)
                    ".action-primary.action-accept",
                    "#btn-cookie-allow",
                    # PrestaShop (Stokomani, B&M, etc.)
                    ".btn-primary[data-dismiss='modal']",
                    "#gdpr_consent_agree",

                    # === CMP (Consent Management Platforms) ===
                    ".didomi-continue-without-agreeing",
                    "#tarteaucitronPersonalize2",
                    ".tarteaucitronAllow",
                    "#tarteaucitronAllDenied2",
                    ".cc-btn.cc-allow",
                    ".cky-btn-accept",
                    "#CybotCookiebotDialogBodyLevelButtonLevelOptinAllowAll",
                    "#CybotCookiebotDialogBodyButtonAccept",
                    ".qc-cmp2-summary-buttons button:first-child",
                    "#axeptio_btn_acceptAll",
                    ".axeptio_acceptAll",

                    # === TEXTE FRANÇAIS ===
                    "button:has-text('Tout accepter')",
                    "button:has-text('Accepter tout')",
                    "button:has-text('Accepter et fermer')",
                    "button:has-text('Accepter les cookies')",
                    "button:has-text('Accepter')",
                    "button:has-text('J\\'accepte')",
                    "button:has-text('OK')",
                    "button:has-text('Continuer')",
                    "a:has-text('Tout accepter')",
                    "a:has-text('Accepter')",

                    # === POPUPS GÉNÉRAUX ===
                    "button[aria-label='Close']",
                    "button[aria-label='close']",
                    "button[aria-label='Fermer']",
                    ".close-button",
                    ".modal-close",
                    "svg[data-name='Close']",
                    "[class*='popup'] button",
                    "[class*='modal'] button",
                    "button:has-text('No, thanks')",
                    "button:has-text('No thanks')",
                    "button:has-text('Accept')",
                    "a:has-text('No, thanks')",
                    "div[role='dialog'] button[aria-label='Close']",
                ]

                for popup_selector in popup_selectors:
                    try:
                        if await page.locator(popup_selector).count() > 0:
                            logger.info(f"Found popup close button: {popup_selector}")
                            # Try to click it. If it fails, catch and continue
                            await page.locator(popup_selector).first.click(timeout=2000)
                            await page.wait_for_timeout(1000)  # Wait for animation
                    except Exception as e:
                        logger.debug(f"Could not close popup with selector {popup_selector}: {e}")

                # Also try pressing Escape
                try:
                    await page.keyboard.press("Escape")
                except Exception as e:
                    logger.debug(f"Could not press Escape key: {e}")

                if selector:
                    try:
                        logger.info(f"Waiting for selector: {selector}")
                        await page.wait_for_selector(selector, timeout=5000)
                        # Scroll to element
                        element = page.locator(selector).first
                        await element.scroll_into_view_if_needed()
                        logger.info(f"Scrolled to selector: {selector}")
                    except Exception as e:
                        logger.warning(f"Selector {selector} not found or timed out: {e}")
                else:
                    # Auto-detect price if no selector
                    logger.info("No selector provided. Attempting to find price element...")
                    try:
                        # Look for common price patterns
                        price_locator = page.locator("text=/$[0-9,]+(\\.[0-9]{2})?/")
                        if await price_locator.count() > 0:
                            # Pick the first one that looks visible and reasonable size
                            # This is heuristic
                            await price_locator.first.scroll_into_view_if_needed()
                            logger.info("Scrolled to potential price element")
                    except Exception as e:
                        logger.warning(f"Auto-price detection failed: {e}")

                # Smart Scroll
                if smart_scroll:
                    logger.info(f"Performing smart scroll ({scroll_pixels}px)...")
                    try:
                        await page.evaluate(f"window.scrollBy(0, {scroll_pixels})")
                        await page.wait_for_timeout(1000)
                    except Exception as e:
                        logger.warning(f"Smart scroll failed: {e}")

                # IMPORTANT: Prendre le screenshot AVANT l'extraction de texte
                # pour éviter de perdre le screenshot si le navigateur se ferme
                screenshot_dir = "screenshots"
                os.makedirs(screenshot_dir, exist_ok=True)
                if item_id:
                    filename = f"{screenshot_dir}/item_{item_id}.png"
                else:
                    url_part = url.split("//")[-1].replace("/", "_")[:50]  # Limiter la longueur
                    timestamp = int(asyncio.get_event_loop().time())
                    filename = f"{screenshot_dir}/{url_part}_{timestamp}.png"

                try:
                    await page.screenshot(path=filename, full_page=False)
                    logger.info(f"Screenshot saved to {filename}")
                except Exception as e:
                    logger.error(f"Screenshot failed: {e}")
                    return None, ""

                # Text Extraction (après le screenshot pour ne pas le perdre)
                page_text = ""
                if text_length > 0:
                    try:
                        logger.info(f"Extracting text (limit: {text_length} chars)...")
                        # Get text from body avec un timeout court
                        raw_text = await page.inner_text("body", timeout=10000)
                        # Simple truncation
                        page_text = raw_text[:text_length]
                        logger.info(f"Extracted {len(page_text)} characters")
                    except Exception as e:
                        logger.warning(f"Text extraction failed (screenshot saved): {e}")
                        # On continue car le screenshot a été pris

                return filename, page_text

            except Exception as e:
                logger.error(f"Error scraping {url}: {e}")
                return None, ""

            finally:
                # Fermeture propre des ressources dans l'ordre inverse
                try:
                    if page and not page.is_closed():
                        await page.close()
                except Exception as e:
                    logger.debug(f"Error closing page: {e}")

                try:
                    if context:
                        await context.close()
                except Exception as e:
                    logger.debug(f"Error closing context: {e}")

                try:
                    if browser and browser.is_connected():
                        await browser.close()
                except Exception as e:
                    logger.debug(f"Error closing browser: {e}")
