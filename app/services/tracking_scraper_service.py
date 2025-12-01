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
    # Amazon-specific popups
    "#sp-cc-accept",  # Cookie banner Amazon
    "#sp-cc-rejectall-link",
    "button[data-action='a-popover-close']",
    "[data-action='sp-cc-accept']",
    "input[aria-labelledby='sp-cc-accept-label']",
    "#nav-flyout-prime button",  # Prime flyout
    
    # French RGPD/Cookie consent platforms
    "#axeptio_btn_acceptAll",  # Axeptio
    "#axeptio_main_button",
    "button#didomi-notice-agree-button",  # Didomi
    ".didomi-popup-notice-button-accept",
    "#onetrust-accept-btn-handler",  # OneTrust
    "button.onetrust-close-btn-handler",
    "#tarteaucitronPersonalize2",  # TarteAuCitron
    "button#tarteaucitronAllAllowed",
    
    # Generic close buttons
    "button[aria-label='Close']",
    "button[aria-label='close']",
    "button[aria-label='Fermer']",
    "button[aria-label='fermer']",
    ".close-button",
    ".modal-close",
    "svg[data-name='Close']",
    "[class*='popup'] button",
    "[class*='modal'] button",
    "[class*='overlay'] button",
    
    # Newsletter/subscription popups
    "button:has-text('No, thanks')",
    "button:has-text('No thanks')",
    "button:has-text('Non merci')",
    "button:has-text('Non, merci')",
    "a:has-text('No, thanks')",
    "a:has-text('Non merci')",
    
    # Dialog/modal close buttons
    "div[role='dialog'] button[aria-label='Close']",
    "div[role='dialog'] button[aria-label='Fermer']",
    "[role='dialog'] .close",
    
    # Cookie banners (generic)
    "#cookieConsent button",
    ".cookie-consent button",
    "button[id*='cookie'][id*='accept']",
    "button[class*='cookie'][class*='accept']",
    ".cc-dismiss",
    ".cc-allow",
]


@dataclass
class ScrapeConfig:
    """Configuration for scraping parameters."""

    smart_scroll: bool = False
    scroll_pixels: int = 350
    text_length: int = 0
    timeout: int = 90000


class TrackingScraperService:
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
            logger.info("Initializing TrackingScraperService shared browser...")
            cls._playwright = await async_playwright().start()
            cls._browser = await cls._connect_browser(cls._playwright)
            logger.info("TrackingScraperService initialized.")

    @classmethod
    async def shutdown(cls):
        """Shutdown the shared browser instance."""
        async with cls._lock:
            if cls._browser:
                logger.info("Shutting down TrackingScraperService shared browser...")
                await cls._browser.close()
                cls._browser = None
            if cls._playwright:
                await cls._playwright.stop()
                cls._playwright = None
            logger.info("TrackingScraperService shutdown complete.")

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
    ) -> tuple[str | None, str]:
        """
        Scrapes the given URL using Browserless and Playwright.
        Returns a tuple: (screenshot_path, page_text)
        """
        if config is None:
            config = ScrapeConfig()

        # Input validation & defaults
        scroll_pixels = max(350, config.scroll_pixels if config.scroll_pixels > 0 else 350)
        timeout = max(30000, config.timeout if config.timeout > 0 else 90000)

        # Ensure browser is connected and healthy
        if not await TrackingScraperService._ensure_browser_connected():
            logger.error("Failed to establish browser connection")
            return None, ""

        try:
            context = await TrackingScraperService._create_context(TrackingScraperService._browser)
            page = await context.new_page()

            try:
                await TrackingScraperService._navigate_and_wait(page, url, timeout)
                await TrackingScraperService._handle_popups(page, url)

                if selector:
                    await TrackingScraperService._wait_for_selector(page, selector)
                else:
                    await TrackingScraperService._auto_detect_price(page)

                if config.smart_scroll:
                    await TrackingScraperService._smart_scroll(page, scroll_pixels)

                page_text = await TrackingScraperService._extract_text(page, config.text_length)
                
                # Second popup handling pass right before screenshot to ensure clean capture
                await TrackingScraperService._handle_popups(page, url)
                await page.wait_for_timeout(1000)  # Final wait for any animations
                
                screenshot_path = await TrackingScraperService._take_screenshot(page, url, item_id)

                return screenshot_path, page_text

            finally:
                await context.close()

        except Exception as e:
            logger.error(f"Error scraping {url}: {e}")
            return None, ""

    @staticmethod
    async def _connect_browser(p) -> Browser:
        logger.info(f"Connecting to Browserless at {BROWSERLESS_URL}")
        return await p.chromium.connect_over_cdp(BROWSERLESS_URL)

    @staticmethod
    async def _create_context(browser: Browser) -> BrowserContext:
        context = await browser.new_context(
            viewport={"width": 1920, "height": 1080},
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
        )
        # Stealth mode / Ad blocking attempts
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
    async def _handle_popups(page: Page, url: str = ""):
        """
        Close popups and cookie banners with retry logic and verification.
        
        Args:
            page: Playwright page object
            url: URL being scraped (for Amazon detection)
        """
        logger.info("Attempting to close popups...")
        is_amazon = "amazon" in url.lower() if url else False
        
        if is_amazon:
            logger.info("🛒 Amazon detected - applying enhanced popup handling")
        
        closed_popups = []
        
        # First pass: Try to close all visible popups
        for popup_selector in POPUP_SELECTORS:
            try:
                popup_count = await page.locator(popup_selector).count()
                if popup_count > 0:
                    logger.info(f"Found popup close button: {popup_selector}")
                    await page.locator(popup_selector).first.click(timeout=3000)
                    closed_popups.append(popup_selector)
                    await page.wait_for_timeout(1500)  # Increased wait for popup animation
            except Exception as e:
                logger.debug(f"Could not click {popup_selector}: {e}")
                pass
        
        # Try Escape key multiple times (some sites need it)
        for _ in range(2):
            try:
                await page.keyboard.press("Escape")
                await page.wait_for_timeout(500)
            except Exception:
                pass
        
        # Second pass: Verify and retry if any popups are still visible
        if closed_popups:
            logger.info(f"Verifying {len(closed_popups)} closed popup(s)...")
            await page.wait_for_timeout(1000)
            
            for popup_selector in closed_popups:
                try:
                    if await page.locator(popup_selector).count() > 0:
                        logger.warning(f"Popup reappeared, retrying: {popup_selector}")
                        await page.locator(popup_selector).first.click(timeout=2000)
                        await page.wait_for_timeout(1000)
                except Exception:
                    pass
        
        # Amazon-specific: Extra wait for JS-heavy popups
        if is_amazon:
            await page.wait_for_timeout(2000)
            logger.info("✅ Amazon popup handling complete")
        
        logger.info(f"Popup handling complete ({len(closed_popups)} closed)")

    @staticmethod
    async def _verify_no_popups(page: Page) -> bool:
        """
        Verify that no modal/overlay elements are currently visible.
        
        Returns:
            True if no popups are visible, False otherwise
        """
        overlay_selectors = [
            "[role='dialog']",
            ".modal[style*='display: block']",
            ".popup[style*='display: block']",
            "[class*='overlay'][style*='display: block']",
            "[class*='modal-open']",
        ]
        
        for selector in overlay_selectors:
            try:
                count = await page.locator(selector).count()
                if count > 0:
                    # Check if actually visible
                    elem = page.locator(selector).first
                    if await elem.is_visible():
                        logger.warning(f"⚠️ Visible popup/overlay detected: {selector}")
                        return False
            except Exception:
                pass
        
        return True

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
            raw_text = await page.inner_text("body")
            page_text = raw_text[:text_length]
            logger.info(f"Extracted {len(page_text)} characters")
            return page_text
        except Exception as e:
            logger.error(f"Text extraction failed: {e}")
            return ""

    @staticmethod
    async def _take_screenshot(page: Page, url: str, item_id: int | None) -> str:
        screenshot_dir = "screenshots"
        os.makedirs(screenshot_dir, exist_ok=True)

        if item_id:
            filename = f"{screenshot_dir}/item_{item_id}.png"
        else:
            url_part = url.split("//")[-1].replace("/", "_")
            timestamp = datetime.now().timestamp()
            filename = f"{screenshot_dir}/{url_part}_{timestamp}.png"

        await page.screenshot(path=filename, full_page=False)
        logger.info(f"Screenshot saved to {filename}")
        return filename
