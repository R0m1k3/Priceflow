"""
Browserless Service - Enhanced Version
Manages connections to Browserless.io with advanced robustness features:
- Auto-reconnection on browser disconnection
- Advanced popup handling
- Flexible configuration
- Thread-safe operations
"""

import asyncio
import logging
import os
from dataclasses import dataclass
from datetime import datetime

from playwright.async_api import Browser, BrowserContext, Page, async_playwright
from playwright.async_api import TimeoutError as PlaywrightTimeoutError

from app.core.search_config import (
    BROWSERLESS_URL,
    get_random_user_agent,
)

logger = logging.getLogger(__name__)

# Comprehensive popup selectors
POPUP_SELECTORS = [
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
    "a:has-text('No, thanks')",
    "div[role='dialog'] button[aria-label='Close']",
    # Cookie banners (kept for compatibility)
    "#sp-cc-accept",
    "#onetrust-accept-btn-handler",
    "button:has-text('Tout accepter')",
    "button:has-text('Accepter')",
]


@dataclass
class ScrapeConfig:
    """Configuration for scraping parameters."""

    smart_scroll: bool = False
    scroll_pixels: int = 350
    text_length: int = 0
    timeout: int = 90000


class BrowserlessService:
    """Enhanced browserless service with auto-reconnection and robust error handling."""

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
            logger.info("Initializing BrowserlessService shared browser...")
            cls._playwright = await async_playwright().start()
            cls._browser = await cls._connect_browser(cls._playwright)
            logger.info("BrowserlessService initialized.")

    @classmethod
    async def shutdown(cls):
        """Shutdown the shared browser instance."""
        async with cls._lock:
            if cls._browser:
                logger.info("Shutting down BrowserlessService shared browser...")
                await cls._browser.close()
                cls._browser = None
            if cls._playwright:
                await cls._playwright.stop()
                cls._playwright = None
            logger.info("BrowserlessService shutdown complete.")

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
    async def _connect_browser(p) -> Browser:
        """Connect to Browserless."""
        logger.info(f"Connecting to Browserless at {BROWSERLESS_URL}")
        return await p.chromium.connect_over_cdp(BROWSERLESS_URL, timeout=60000)

    @staticmethod
    async def _create_context(browser: Browser, use_proxy: bool = False) -> BrowserContext:
        """Create a new browser context with stealth settings."""
        user_agent = get_random_user_agent()

        options = {
            "viewport": {"width": 1920, "height": 1080},
            "user_agent": user_agent,
            "locale": "fr-FR",
            "timezone_id": "Europe/Paris",
            "java_script_enabled": True,
            "bypass_csp": True,
            "extra_http_headers": {
                "Accept-Language": "fr-FR,fr;q=0.9,en-US;q=0.8,en;q=0.7",
                "Sec-Ch-Ua-Platform": '"Windows"',
                "Upgrade-Insecure-Requests": "1",
            },
        }

        # Proxy support (can be enhanced with proxy pool in future)
        if use_proxy:
            logger.info("Proxy support requested (not implemented in this version)")

        context = await browser.new_context(**options)

        # Block aggressive tracking but keep images
        await context.route("**/*", lambda route: route.continue_())

        return context

    @staticmethod
    async def _navigate_and_wait(page: Page, url: str, timeout: int):
        """Navigate to URL and wait for page load."""
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
        """Attempt to close popups and cookie banners."""
        logger.info("Attempting to close popups...")
        for popup_selector in POPUP_SELECTORS:
            try:
                if await page.locator(popup_selector).count() > 0:
                    logger.info(f"Found popup close button: {popup_selector}")
                    await page.locator(popup_selector).first.click(timeout=2000)
                    await page.wait_for_timeout(1000)
            except Exception:
                pass

        try:
            await page.keyboard.press("Escape")
        except Exception:
            pass

    @staticmethod
    async def _wait_for_selector(page: Page, selector: str):
        """Wait for selector and scroll into view."""
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
        """Attempt to auto-detect and scroll to price element."""
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
        """Perform smart scrolling."""
        logger.info(f"Performing smart scroll ({scroll_pixels}px)...")
        try:
            await page.evaluate(f"window.scrollBy(0, {scroll_pixels})")
            await page.wait_for_timeout(1000)
        except Exception as e:
            logger.warning(f"Smart scroll failed: {e}")

    @staticmethod
    async def _extract_text(page: Page, text_length: int) -> str:
        """Extract text from page body."""
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
    async def _take_screenshot(page: Page, url: str, item_id: int | None = None) -> str:
        """Take screenshot and save to disk."""
        screenshot_dir = "/app/screenshots"
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

    @classmethod
    async def get_page_content(
        cls,
        url: str,
        use_proxy: bool = False,
        wait_selector: str | None = None,
        config: ScrapeConfig | None = None,
    ) -> tuple[str, str]:
        """
        Fetch page content with full stealth lifecycle.
        
        Args:
            url: URL to scrape
            use_proxy: Whether to use proxy (reserved for future use)
            wait_selector: Optional CSS selector to wait for
            config: Optional scraping configuration
            
        Returns:
            tuple[screenshot_path, page_text]: Screenshot path and extracted text
        """
        if config is None:
            config = ScrapeConfig()

        # Input validation & defaults
        scroll_pixels = max(350, config.scroll_pixels if config.scroll_pixels > 0 else 350)
        timeout = max(30000, config.timeout if config.timeout > 0 else 90000)

        # Ensure browser is connected and healthy
        if not await cls._ensure_browser_connected():
            logger.error("Failed to establish browser connection")
            return "", ""

        try:
            context = await cls._create_context(cls._browser, use_proxy=use_proxy)
            page = await context.new_page()

            try:
                await cls._navigate_and_wait(page, url, timeout)
                await cls._handle_popups(page)

                if wait_selector:
                    await cls._wait_for_selector(page, wait_selector)
                else:
                    await cls._auto_detect_price(page)

                if config.smart_scroll:
                    await cls._smart_scroll(page, scroll_pixels)

                page_text = await cls._extract_text(page, config.text_length)
                
                # Extract item_id from URL if it matches pattern
                item_id = None
                if "item_" in url:
                    # This is a simplified extraction, adjust based on your URL patterns
                    pass
                    
                screenshot_path = await cls._take_screenshot(page, url, item_id)

                return screenshot_path, page_text

            finally:
                await context.close()

        except Exception as e:
            logger.error(f"Error scraping {url}: {e}")
            return "", ""


# Global instance for backward compatibility
browserless_service = BrowserlessService()
