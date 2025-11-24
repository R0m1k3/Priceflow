import asyncio
import logging
import os
import random
import re
from urllib.parse import urlparse, urlunparse

from playwright.async_api import TimeoutError as PlaywrightTimeoutError
from playwright.async_api import async_playwright

logger = logging.getLogger(__name__)

BROWSERLESS_URL = os.getenv("BROWSERLESS_URL", "ws://browserless:3000")

# Nombre de tentatives pour le scraping
MAX_RETRIES = 2
RETRY_DELAY = 3  # secondes

# Amazon-specific configuration
AMAZON_MAX_RETRIES = 4
AMAZON_BASE_DELAY = 3.0

# Pool of realistic User-Agents for rotation
USER_AGENT_POOL = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:133.0) Gecko/20100101 Firefox/133.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36 Edg/131.0.0.0",
]

# Amazon blocking indicators
AMAZON_BLOCK_INDICATORS = [
    "Toutes nos excuses",
    "Sorry, something went wrong",
    "api-services-support@amazon.com",
    "Enter the characters you see below",
    "Saisissez les caractères",
    "Service Unavailable",
    "robot check",
    "automated access",
]


def _get_random_user_agent() -> str:
    """Get a random User-Agent from the pool"""
    return random.choice(USER_AGENT_POOL)


def _is_amazon_url(url: str) -> bool:
    """Check if URL is an Amazon URL"""
    return "amazon" in url.lower()


def _is_amazon_blocked(html_content: str) -> bool:
    """Check if Amazon has blocked the request"""
    html_lower = html_content.lower()
    for indicator in AMAZON_BLOCK_INDICATORS:
        if indicator.lower() in html_lower:
            return True
    return False


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
        browser=None,  # Instance de navigateur partagée optionnelle
    ) -> tuple[str | None, str, bool]:
        """
        Scrapes the given URL using Browserless and Playwright.
        Returns a tuple: (screenshot_path, page_text, is_available)

        Args:
            url: Target URL to scrape
            selector: Optional CSS selector to focus on
            item_id: Optional item ID for screenshot naming
            smart_scroll: Enable scrolling to load lazy content
            scroll_pixels: Number of pixels to scroll (must be positive)
            text_length: Number of characters to extract (0 = disabled)
            timeout: Page load timeout in milliseconds
            browser: Optional shared Playwright browser instance
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

        # Amazon needs more retries with longer delays
        is_amazon = _is_amazon_url(url)
        max_retries = AMAZON_MAX_RETRIES if is_amazon else MAX_RETRIES
        base_delay = AMAZON_BASE_DELAY if is_amazon else RETRY_DELAY

        # Retries avec backoff
        last_error = None
        for attempt in range(max_retries + 1):
            if attempt > 0:
                # Exponential backoff with jitter for Amazon
                if is_amazon:
                    jitter = random.uniform(0.5, 1.5)
                    delay = min(base_delay * (2 ** attempt) * jitter, 30.0)
                else:
                    delay = base_delay * attempt
                logger.info(f"Tentative {attempt + 1}/{max_retries + 1} pour {url} (délai: {delay:.1f}s)")
                await asyncio.sleep(delay)

            result = await ScraperService._do_scrape(
                url=url,
                selector=selector,
                item_id=item_id,
                smart_scroll=smart_scroll,
                scroll_pixels=scroll_pixels,
                text_length=text_length,
                timeout=timeout,
                browser=browser,
                is_amazon=is_amazon,
            )

            if result[0] is not None:  # Screenshot réussi
                return result

            last_error = "Scraping failed"
            logger.warning(f"Tentative {attempt + 1} échouée pour {url}")

        logger.error(f"Toutes les tentatives ont échoué pour {url}")
        return None, "", False  # Product unavailable if all retries failed

    @staticmethod
    async def _do_scrape(  # noqa: PLR0913, PLR0912, PLR0915
        url: str,
        selector: str | None = None,
        item_id: int | None = None,
        smart_scroll: bool = False,
        scroll_pixels: int = 350,
        text_length: int = 0,
        timeout: int = 90000,
        browser=None,
        is_amazon: bool = False,
    ) -> tuple[str | None, str, bool]:
        """Exécute le scraping réel (appelé par scrape_item avec retries)."""

        # Si un navigateur est fourni, on l'utilise directement sans async_playwright context manager
        # sinon on crée tout de zéro
        playwright_manager = None
        local_browser = None

        try:
            if browser:
                # Utiliser le navigateur partagé
                current_browser = browser
            else:
                # Créer un nouveau navigateur
                playwright_manager = async_playwright()
                p = await playwright_manager.start()
                logger.info(f"Connecting to Browserless at {BROWSERLESS_URL}")
                current_browser = await p.chromium.connect_over_cdp(
                    BROWSERLESS_URL,
                    timeout=60000,
                )
                local_browser = current_browser

            context = None
            page = None
            is_available = True  # Par défaut, le produit est disponible

            # Use random User-Agent for anti-detection (especially for Amazon)
            current_user_agent = _get_random_user_agent()

            # Enhanced headers for stealth
            extra_headers = {
                "Accept-Language": "fr-FR,fr;q=0.9,en-US;q=0.8,en;q=0.7",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
                "Accept-Encoding": "gzip, deflate, br",
                "Cache-Control": "max-age=0",
                "Sec-Ch-Ua": '"Google Chrome";v="131", "Chromium";v="131", "Not_A Brand";v="24"',
                "Sec-Ch-Ua-Mobile": "?0",
                "Sec-Ch-Ua-Platform": '"Windows"',
                "Sec-Fetch-Dest": "document",
                "Sec-Fetch-Mode": "navigate",
                "Sec-Fetch-Site": "none",
                "Sec-Fetch-User": "?1",
                "Upgrade-Insecure-Requests": "1",
            }

            # Add referer for Amazon
            if is_amazon:
                extra_headers["Referer"] = "https://www.google.fr/"

            try:
                context = await current_browser.new_context(
                    viewport={"width": 1920, "height": 1080},
                    user_agent=current_user_agent,
                    locale="fr-FR",
                    timezone_id="Europe/Paris",
                    extra_http_headers=extra_headers,
                )

                # Stealth mode / Ad blocking attempts
                await context.route("**/*", lambda route: route.continue_())

                page = await context.new_page()

                # Add random delay before navigation for Amazon
                if is_amazon:
                    await asyncio.sleep(random.uniform(1.0, 3.0))

                logger.info(f"Navigating to {url} (Timeout: {timeout}ms)")
                response = None
                amazon_blocked = False
                try:
                    # First wait for domcontentloaded - this is the minimum we need
                    response = await page.goto(url, wait_until="domcontentloaded", timeout=timeout)

                    # Check HTTP status code
                    if response:
                        status = response.status
                        logger.info(f"HTTP Status: {status}")

                        # For Amazon, 503 is usually a block, not product unavailability
                        if is_amazon and status == 503:
                            logger.warning(f"Amazon returned 503 - likely blocking")
                            amazon_blocked = True
                        # Detect unavailable products by HTTP status (non-Amazon)
                        elif status in [404, 410, 451]:
                            logger.warning(f"Product unavailable - HTTP {status}")
                            is_available = False
                        elif status == 503 and not is_amazon:
                            logger.warning(f"Product unavailable - HTTP {status}")
                            is_available = False
                        elif status >= 400:
                            logger.warning(f"HTTP error {status}, marking as potentially unavailable")
                            is_available = False

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
                    # If navigation fails completely, mark as unavailable
                    is_available = False
                    # Try to take screenshot anyway if page partially loaded
                    pass

                # Wait a bit for dynamic content if needed - longer for Amazon
                wait_time = random.uniform(2.0, 4.0) if is_amazon else 2.0
                await page.wait_for_timeout(int(wait_time * 1000))

                # Check for Amazon blocking in page content
                if is_amazon:
                    try:
                        page_html = await page.content()
                        if _is_amazon_blocked(page_html):
                            logger.warning(f"Amazon blocking detected in page content for {url}")
                            amazon_blocked = True
                    except Exception as e:
                        logger.debug(f"Could not check Amazon blocking: {e}")

                # If Amazon blocked us, return None to trigger retry
                if amazon_blocked:
                    logger.warning(f"Amazon blocked - will retry with different User-Agent")
                    return None, "", True  # Return None screenshot to trigger retry

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
                    return None, "", is_available

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
                        
                        # Check for "product not found" messages in page text
                        unavailable_patterns = [
                            "produit introuvable",
                            "produit indisponible",
                            "page introuvable",
                            "404",
                            "product not found",
                            "item not found",
                            "page not found",
                            "n'existe plus",
                            "plus disponible",
                            "no longer available",
                            "article introuvable",
                            "cette page n'existe pas",
                            "this page doesn't exist",
                        ]
                        
                        page_text_lower = page_text.lower()
                        for pattern in unavailable_patterns:
                            if pattern in page_text_lower:
                                logger.warning(f"Product unavailable - found pattern: '{pattern}'")
                                is_available = False
                                break
                                
                    except Exception as e:
                        logger.warning(f"Text extraction failed (screenshot saved): {e}")
                        # On continue car le screenshot a été pris

                return filename, page_text, is_available

            except Exception as e:
                logger.error(f"Error scraping {url}: {e}")
                return None, "", False  # Mark as unavailable on error

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

                # On ne ferme le navigateur que s'il est local (non partagé)
                if local_browser:
                    try:
                        if local_browser.is_connected():
                            await local_browser.close()
                    except Exception as e:
                        logger.debug(f"Error closing browser: {e}")
                        
        finally:
            # Si on a créé un manager playwright local, on l'arrête
            if playwright_manager:
                try:
                    await playwright_manager.__aexit__(None, None, None)
                except Exception as e:
                    logger.debug(f"Error stopping playwright manager: {e}")
