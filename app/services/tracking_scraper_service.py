import asyncio
import logging
import os
from dataclasses import dataclass
from datetime import datetime

from playwright.async_api import Browser, BrowserContext, Page, async_playwright
from playwright.async_api import TimeoutError as PlaywrightTimeoutError

logger = logging.getLogger(__name__)

BROWSERLESS_URL = os.getenv("BROWSERLESS_URL", "ws://browserless:3000")

POPUP_SELECTORS = [
    "button[aria-label='Close']",
    "button[aria-label='close']",
    ".close-button",
    ".modal-close",
    "svg[data-name='Close']",
    "[class*='popup'] button",
    "[class*='modal'] button",
    "button:has-text('No, thanks')",
    "button:has-text('No thanks')",
    "a:has-text('No, thanks')",
    "div[role='dialog'] button[aria-label='Close']",
    # Amazon Interstitials (Added for robustness)
    "button:has-text('Continuer les achats')",
    "span:has-text('Continuer les achats')",
    "a:has-text('Continuer les achats')",
    "input[value='Continuer les achats']",
    "input[value='Continue shopping']",
    "span.a-button-inner > input.a-button-input[type='submit']",
    "form:has-text('Continuer les achats') input[type='submit']",
    "[aria-labelledby='continue-shopping-label']",
    # Didomi / Gifi
    "#didomi-notice-agree-button",
    "button[id='didomi-notice-agree-button']",
    "span:has-text('Accepter & Fermer')",
    "button:has-text('Accepter & Fermer')",
    # Common banners
    "#sp-cc-accept",
    "#onetrust-accept-btn-handler",
    ".cookie-consent-accept",
    "[data-action='accept-cookies']",
    "button[id*='accept']",
    "button[class*='accept']",
]


@dataclass
class ScrapeConfig:
    """Configuration for scraping parameters."""

    smart_scroll: bool = False
    scroll_pixels: int = 350
    text_length: int = 0
    timeout: int = 90000


class ScraperService:
    _playwright = None
    _browser: Browser | None = None
    _lock = asyncio.Lock()

    @classmethod
    async def initialize(cls):
        """Initialize the shared browser instance (Public, Thread-Safe)."""
        async with cls._lock:
            await cls._initialize()

    @classmethod
    async def _initialize(cls):
        """Internal initialization logic (Assumes lock is held)."""
        if cls._browser is None:
            logger.info("Initializing ScraperService shared browser...")
            cls._playwright = await async_playwright().start()
            cls._browser = await cls._connect_browser(cls._playwright)
            logger.info("ScraperService initialized.")

    @classmethod
    async def shutdown(cls):
        """Shutdown the shared browser instance."""
        async with cls._lock:
            if cls._browser:
                logger.info("Shutting down ScraperService shared browser...")
                await cls._browser.close()
                cls._browser = None
            if cls._playwright:
                await cls._playwright.stop()
                cls._playwright = None
            logger.info("ScraperService shutdown complete.")

    @classmethod
    async def _ensure_browser_connected(cls) -> bool:
        """Ensure browser is connected, reconnect if needed."""
        async with cls._lock:
            try:
                if cls._browser is None:
                    logger.warning("Browser not initialized, initializing...")
                    await cls._initialize()
                    return cls._browser is not None

                # Test if browser is still alive by trying to create a context
                try:
                    test_context = await cls._browser.new_context()
                    await test_context.close()
                    return True
                except Exception as e:
                    logger.error(f"Browser connection test failed: {e}")
                    logger.info("Attempting to reconnect browser...")
                    # Clear the old browser
                    cls._browser = None
                    if cls._playwright:
                        try:
                            await cls._playwright.stop()
                        except Exception:
                            pass
                        cls._playwright = None
                    # Reconnect
                    await cls._initialize()
                    return cls._browser is not None
            except Exception as e:
                logger.error(f"Failed to ensure browser connection: {e}")
                return False

    @staticmethod
    async def scrape_item(
        url: str,
        selector: str | None = None,
        item_id: int | None = None,
        config: ScrapeConfig | None = None,
        return_html: bool = False,
    ) -> tuple[str | None, str, str, str]:
        """
        Scrapes the given URL using Browserless and Playwright.
        Returns a tuple: (screenshot_path, page_text_or_html, final_url, page_title)
        """
        if config is None:
            config = ScrapeConfig()

        # Input validation & defaults
        scroll_pixels = max(350, config.scroll_pixels if config.scroll_pixels > 0 else 350)
        timeout = max(30000, config.timeout if config.timeout > 0 else 90000)

        # Ensure browser is connected and healthy
        if not await ScraperService._ensure_browser_connected():
            logger.error("Failed to establish browser connection")
            return None, "", url, ""

        try:
            context = await ScraperService._create_context(ScraperService._browser, url)
            page = await context.new_page()

            try:
                # Random delay to simulate human lead-in
                import random
                await asyncio.sleep(random.uniform(0.5, 2.0))
                
                await ScraperService._navigate_and_wait(page, url, timeout)
                final_url = page.url
                page_title = await page.title()
                
                # Humanize: scroll a bit and back
                await page.mouse.move(random.randint(100, 500), random.randint(100, 500))
                await page.evaluate("window.scrollBy(0, 100)")
                await asyncio.sleep(0.5)
                await page.evaluate("window.scrollBy(0, -100)")

                await ScraperService._handle_popups(page)

                # FORCER LE MAGASIN NANCY POUR B&M STORES
                if "bmstores.fr" in url:
                    try:
                        logger.info("B&M Stores detected: checking store selection (Nancy)...")
                        # Check if store is already selected or if modal is needed
                        store_btn = page.locator(".mod-shops .btn-shop, .js-show-shops")
                        if await store_btn.count() > 0:
                            logger.info("Opening store selector...")
                            await store_btn.first.click(timeout=2000)
                            await page.wait_for_timeout(1000)
                            
                            # Type Nancy in the search input
                            search_input = page.locator("#search_mag")
                            if await search_input.count() > 0:
                                await search_input.fill("Nancy")
                                await page.keyboard.press("Enter")
                                await page.wait_for_timeout(1500)
                                
                                # Select the first Nancy store (Nancy Essey or Nancy Centre)
                                select_btn = page.locator(".shop-list .btn-select-shop, button:has-text('Choisir ce magasin')")
                                if await select_btn.count() > 0:
                                    logger.info("Selecting Nancy store...")
                                    await select_btn.first.click()
                                    await page.wait_for_timeout(2000)
                                    # Refresh page or wait for update
                                    await page.reload(wait_until="domcontentloaded")
                                    await page.wait_for_timeout(1000)
                    except Exception as e:
                        logger.warning(f"Failed to force B&M store Nancy: {e}")

                if selector:
                    await ScraperService._wait_for_selector(page, selector)
                else:
                    await ScraperService._auto_detect_price(page)

                if config.smart_scroll:
                    await ScraperService._smart_scroll(page, scroll_pixels)

                if return_html:
                    content_data = await page.content()
                else:
                    content_data = await ScraperService._extract_text(page, config.text_length)
                
                screenshot_path = await ScraperService._take_screenshot(page, url, item_id)

                return screenshot_path, content_data, final_url, page_title

            finally:
                await context.close()

        except Exception as e:
            logger.error(f"Error scraping {url}: {e}")
            return None, "", url, ""

    @staticmethod
    async def _connect_browser(p) -> Browser:
        logger.info(f"Connecting to Browserless at {BROWSERLESS_URL}")
        # Note: Added timeout for connection
        return await p.chromium.connect_over_cdp(BROWSERLESS_URL, timeout=30000)

    @staticmethod
    async def _create_context(browser: Browser, url: str) -> BrowserContext:
        """Create context with advanced stealth and headers (specifically for Amazon)"""
        # Determine base domain for referer
        from urllib.parse import urlparse
        parsed = urlparse(url)
        base_domain = f"{parsed.scheme}://{parsed.netloc}/"

        context = await browser.new_context(
            viewport={"width": 1920, "height": 1080},
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/131.0.0.0 Safari/537.36"
            ),
            locale="fr-FR",
            timezone_id="Europe/Paris",
            extra_http_headers={
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
                "Accept-Language": "fr-FR,fr;q=0.9,en-US;q=0.8,en;q=0.7",
                "Cache-Control": "max-age=0",
                "Sec-Ch-Ua": '"Google Chrome";v="131", "Chromium";v="131", "Not_A Brand";v="24"',
                "Sec-Ch-Ua-Mobile": "?0",
                "Sec-Ch-Ua-Platform": '"Windows"',
                "Sec-Fetch-Dest": "document",
                "Sec-Fetch-Mode": "navigate",
                "Sec-Fetch-Site": "none",
                "Sec-Fetch-User": "?1",
                "Upgrade-Insecure-Requests": "1",
                "Referer": base_domain if "amazon" in url else "https://www.google.com/"
            }
        )

        # Advanced Stealth mode
        await context.add_init_script("""
            // Redefine webdriver
            Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
            
            // Masquerade plugins
            Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3, 4, 5] });
            
            // Languages
            Object.defineProperty(navigator, 'languages', { get: () => ['fr-FR', 'fr', 'en-US', 'en'] });

            // Chrome runtime
            window.chrome = { runtime: {} };

            // Overwrite permissions
            const originalQuery = window.navigator.permissions.query;
            window.navigator.permissions.query = (parameters) => (
                parameters.name === 'notifications' ?
                    Promise.resolve({ state: Notification.permission }) :
                    originalQuery(parameters)
            );
        """)

        await context.route("**/*", lambda route: route.continue_())
        return context

    @staticmethod
    async def _navigate_and_wait(page: Page, url: str, timeout: int):
        logger.info(f"Navigating to {url} (Timeout: {timeout}ms)")
        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=timeout)
            logger.info(f"Page loaded (domcontentloaded): {url}")

            try:
                await page.wait_for_load_state("networkidle", timeout=5000)
                logger.info("Network idle reached")
            except PlaywrightTimeoutError:
                logger.info("Network idle timed out (non-critical), proceeding...")

        except Exception as e:
            logger.warning(f"Navigation warning for {url}: {e}")

        # Wait a bit for dynamic content
        await page.wait_for_timeout(2000)

    @staticmethod
    async def _handle_popups(page: Page):
        """Aggressive multi-pass popup and overlay removal"""
        logger.info("Starting aggressive popup removal...")
        
        # 1. Multi-pass clicking (some popups appear after others are closed)
        for i in range(2):
            logger.debug(f"Popup removal pass {i+1}")
            for selector in POPUP_SELECTORS:
                try:
                    locators = page.locator(selector)
                    count = await locators.count()
                    if count > 0:
                        for j in range(count):
                            target = locators.nth(j)
                            if await target.is_visible():
                                logger.info(f"Closing popup: {selector}")
                                await target.click(timeout=1000)
                                await page.wait_for_timeout(500)
                except Exception:
                    pass
            
            # Hammer Escape key
            try:
                await page.keyboard.press("Escape")
                await page.wait_for_timeout(200)
            except: pass

        # 2. Javascript cleanup (Hide pesky overlays and CMPs that won't close)
        logger.info("Injecting CSS/JS cleanup for persistent overlays...")
        await page.evaluate("""
            () => {
                const selectorsToHide = [
                    '#didomi-host', '.didomi-popup-container', '[id*="didomi"]',
                    '#onetrust-banner-sdk', '#onetrust-consent-sdk',
                    '.cookie-banner', '.cookie-consent', '.qc-cmp2-container',
                    '.modal-backdrop', '.modal-overlay', '.fade.show'
                ];
                
                // Hide specific IDs/classes
                selectorsToHide.forEach(s => {
                    const el = document.querySelector(s);
                    if (el) el.style.display = 'none';
                });

                // Clear overlays (fixed/absolute elements with high z-index that cover too much)
                const all = document.getElementsByTagName("*");
                for (let i = 0, max = all.length; i < max; i++) {
                    const el = all[i];
                    const style = window.getComputedStyle(el);
                    if (style.position === 'fixed' || style.position === 'absolute') {
                        const zIndex = parseInt(style.zIndex);
                        if (zIndex > 100) {
                            // Check if it's potentially a popup (covers a lot of area or has modal classes)
                            const rect = el.getBoundingClientRect();
                            if (rect.width > window.innerWidth * 0.5 && rect.height > window.innerHeight * 0.5) {
                                console.log('Hiding potential popup:', el);
                                el.style.setProperty('display', 'none', 'important');
                            }
                        }
                    }
                }
                
                // Unlock scroll if it was locked by a modal
                document.body.style.overflow = 'auto';
                document.documentElement.style.overflow = 'auto';
            }
        """)
        
        # Wait for any transitions
        await page.wait_for_timeout(1000)

    @staticmethod
    async def _wait_for_selector(page: Page, selector: str):
        try:
            logger.info(f"Waiting for selector: {selector}")
            await page.wait_for_selector(selector, timeout=5000)
            element = page.locator(selector).first
            await element.scroll_into_view_if_needed()
            logger.info(f"Scrolled to selector: {selector}")
        except Exception as e:
            logger.warning(f"Selector {selector} not found or timed out: {e}")

    @staticmethod
    async def _auto_detect_price(page: Page):
        logger.info("No selector provided. Attempting to find price element...")
        try:
            price_locator = page.locator("text=/$[0-9,]+(\\.[0-9]{2})?/")
            if await price_locator.count() > 0:
                await price_locator.first.scroll_into_view_if_needed()
                logger.info("Scrolled to potential price element")
        except Exception as e:
            logger.warning(f"Auto-price detection failed: {e}")

    @staticmethod
    async def _smart_scroll(page: Page, scroll_pixels: int):
        logger.info(f"Performing smart scroll ({scroll_pixels}px)...")
        try:
            await page.evaluate(f"window.scrollBy(0, {scroll_pixels})")
            await page.wait_for_timeout(1000)
        except Exception as e:
            logger.warning(f"Smart scroll failed: {e}")

    @staticmethod
    async def _extract_text(page: Page, text_length: int) -> str:
        if text_length <= 0:
            return ""

        try:
            logger.info(f"Extracting text (limit: {text_length} chars)...")
            
            # Smart extraction: remove noise (nav, footer, scripts) before getting text
            clean_text = await page.evaluate("""
                () => {
                    // Clone body to not affect the visual page
                    const clone = document.body.cloneNode(true);
                    
                    // Remove noise selectors
                    const noiseSelectors = [
                        'nav', 'header', 'footer', 'script', 'style', 'noscript', 'iframe',
                        '.cookie-banner', '.popup', '#menu', '.menu', '.sidebar',
                        '[role="navigation"]', '[role="banner"]', '[role="contentinfo"]'
                    ];
                    
                    noiseSelectors.forEach(selector => {
                        const elements = clone.querySelectorAll(selector);
                        elements.forEach(el => el.remove());
                    });
                    
                    return clone.innerText;
                }
            """)
            
            # Fallback if cleaning removed everything (unlikely but safe)
            if not clean_text or len(clean_text) < 100:
                logger.warning("Cleaned text too short, falling back to full body text")
                clean_text = await page.inner_text("body")

            # Collapse whitespace
            import re
            clean_text = re.sub(r'\s+', ' ', clean_text).strip()

            page_text = clean_text[:text_length]
            logger.info(f"Extracted {len(page_text)} chars")
            return page_text
        except Exception as e:
            logger.error(f"Text extraction failed: {e}")
            return ""

    @staticmethod
    async def _take_screenshot(page: Page, url: str, item_id: int | None) -> str:
        screenshot_dir = "screenshots"
        os.makedirs(screenshot_dir, exist_ok=True)

        if item_id:
            # Use timestamp to ensure unique filenames (fixes caching issues)
            timestamp = int(datetime.now().timestamp())
            filename = f"{screenshot_dir}/item_{item_id}_{timestamp}.png"
        else:
            url_part = url.split("//")[-1].replace("/", "_")
            timestamp = datetime.now().timestamp()
            filename = f"{screenshot_dir}/{url_part}_{timestamp}.png"

        await page.screenshot(path=filename, full_page=False)
        logger.info(f"Screenshot saved to {filename}")
        return filename
