"""
Browserless Service - Enhanced Version
Manages connections to Browserless.io with advanced robustness features:
- Auto-reconnection on browser disconnection
- Advanced popup handling
- Flexible configuration
- Thread-safe operations
- Amazon & Generic price extraction
"""

import asyncio
import logging
import os
import re
import time
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
    # Cookie banners
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

                # Test if browser is still alive
                try:
                    test_context = await cls._browser.new_context()
                    await test_context.close()
                    return True
                except Exception as e:
                    logger.error(f"Browser connection test failed: {e}")
                    logger.info("Attempting to reconnect browser...")
                    cls._browser = None
                    if cls._playwright:
                        try:
                            await cls._playwright.stop()
                        except Exception:
                            pass
                        cls._playwright = None
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

        if use_proxy:
            logger.info("Proxy support requested (not implemented in this version)")

        context = await browser.new_context(**options)
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
    async def _extract_amazon_price(page: Page) -> str:
        """Extract price from Amazon product page."""
        price_selectors = [
            ".a-price .a-offscreen",
            "#corePrice_desktop .a-price .a-offscreen",
            "#corePriceDisplay_desktop_feature_div .a-price .a-offscreen",
            ".a-price[data-a-color='price'] .a-offscreen",
            "#priceblock_ourprice",
            "#priceblock_dealprice",
            "span.a-price-whole",
        ]

        for selector in price_selectors:
            try:
                element = page.locator(selector).first
                price_text = await element.inner_text(timeout=2000)
                if price_text and price_text.strip():
                    logger.info(f"Extracted Amazon price via {selector}: {price_text}")
                    return price_text.strip()
            except Exception:
                continue

        # Try combination: whole + fraction
        try:
            whole = await page.locator("span.a-price-whole").first.inner_text()
            fraction = await page.locator("span.a-price-fraction").first.inner_text()
            if whole and fraction:
                price_text = f"{whole}{fraction}"
                logger.info(f"Extracted Amazon price from whole+fraction: {price_text}")
                return price_text
        except Exception:
            pass

        logger.warning("Could not extract Amazon price")
        return ""

    @staticmethod
    async def _extract_generic_price(page: Page) -> str:
        """Extract price from generic e-commerce pages."""
        price_selectors = [
            "[itemprop='price']",
            "[data-testid='price']",
            "[data-test='price']",
            ".current-price",
            ".sale-price",
            ".final-price",
            ".product-price",
            ".special-price",
            "[data-price]",
            ".price-current",
            ".price-now",
            ".price-sales",
            "[class*='price']:not([class*='old']):not([class*='was']):not([class*='original']):not([class*='before']):not([class*='regular']):not([class*='strike']):not([class*='barre'])",
            "#price",
            "#product-price",
            "span[class*='prix']:not([class*='ancien']):not([class*='barre'])",
            ".prix-actuel",
            ".price:not(.old-price):not(.was-price)",
        ]

        found_prices = []

        for selector in price_selectors:
            try:
                elements = page.locator(selector)
                count = await elements.count()

                for i in range(min(count, 3)):
                    try:
                        element = elements.nth(i)
                        if await element.is_visible(timeout=1000):
                            # Check if strikethrough
                            try:
                                text_decoration = await element.evaluate("el => window.getComputedStyle(el).textDecoration")
                                if "line-through" in text_decoration:
                                    continue
                            except Exception:
                                pass

                            price_text = await element.inner_text()
                            if price_text and ('€' in price_text or (',' in price_text and any(c.isdigit() for c in price_text))):
                                price_text = price_text.strip()

                                # Validate price range
                                numeric_match = re.search(r'(\d+[.,]?\d*)', price_text.replace(' ', '').replace('\xa0', ''))
                                if numeric_match:
                                    try:
                                        price_val = float(numeric_match.group(1).replace(',', '.'))
                                        if 0.01 <= price_val <= 100000:
                                            found_prices.append((selector, price_text))
                                            logger.info(f"Found valid price via {selector}: {price_text}")

                                            # Return high-priority immediately
                                            if selector in ["[itemprop='price']", "[data-testid='price']", ".current-price", ".sale-price", ".final-price", ".product-price"]:
                                                return price_text
                                    except (ValueError, AttributeError):
                                        continue
                    except Exception:
                        continue
            except Exception:
                continue

        if found_prices:
            best_price = found_prices[-1][1]
            if len(found_prices) > 1:
                logger.info(f"Multiple prices found, selecting last: {best_price}")
            return best_price

        # Regex fallback
        try:
            all_text = await page.inner_text('body')
            price_matches = re.findall(r'\d+[,\.]\d{2}\s*€', all_text)
            if price_matches:
                logger.info(f"Found price via regex: {price_matches[0]}")
                return price_matches[0]
        except Exception:
            pass

        logger.warning("Could not extract generic price")
        return ""

    @classmethod
    async def get_page_content(
        cls,
        url: str,
        use_proxy: bool = False,
        wait_selector: str | None = None,
        extract_text: bool = False
    ) -> tuple[str, str]:
        """
        Fetch page content with full stealth lifecycle.
        
        Args:
            url: URL to fetch
            use_proxy: Whether to use proxy
            wait_selector: CSS selector to wait for
            extract_text: If True, returns visible text; if False, returns HTML
            
        Returns:
            tuple[content, screenshot_path]: Content (HTML or text) and screenshot path
        """
        # Ensure browser connected
        if not await cls._ensure_browser_connected():
            logger.error("Failed to establish browser connection")
            return "", ""

        try:
            context = await cls._create_context(cls._browser, use_proxy=use_proxy)
            page = await context.new_page()

            try:
                await cls._navigate_and_wait(page, url, 90000)
                await cls._handle_popups(page)

                # Amazon-specific wait
                if "amazon" in url.lower() and "/dp/" in url:
                    amazon_selectors = [".a-price .a-offscreen", "#corePriceDisplay_desktop_feature_div"]
                    for selector in amazon_selectors:
                        try:
                            await page.wait_for_selector(selector, timeout=5000, state="visible")
                            logger.info(f"Amazon price element found: {selector}")
                            break
                        except Exception:
                            continue

                # Extract content
                if extract_text:
                    content = await page.inner_text('body')
                    logger.info(f"Extracted {len(content)} chars of visible text")

                    # Normalize French prices
                    content = re.sub(r'(\d+)€(\d{2})\b', r'\1.\2 €', content)
                    content = re.sub(r'(\d+),(\d{2})\s*€', r'\1.\2 €', content)
                    content = re.sub(r'(\d+)\s(\d{3})', r'\1\2', content)

                    # Extract price
                    extracted_price = ""
                    if "amazon" in url.lower() and "/dp/" in url:
                        extracted_price = await cls._extract_amazon_price(page)
                    else:
                        extracted_price = await cls._extract_generic_price(page)

                    # Prepend normalized price
                    if extracted_price:
                        normalized_price = re.sub(r'(\d+)€(\d{2})', r'\1.\2 €', extracted_price)
                        normalized_price = re.sub(r'(\d+),(\d{2})', r'\1.\2', normalized_price)
                        normalized_price = normalized_price.replace(' ', '')
                        content = f"PRIX DÉTECTÉ: {normalized_price}\n\n{content}"
                        logger.info(f"Prepended price: {normalized_price}")
                else:
                    content = await page.content()

                # Take screenshot
                screenshot_path = ""
                try:
                    os.makedirs("/app/screenshots", exist_ok=True)
                    timestamp = int(time.time() * 1000)
                    safe_name = "".join(c if c.isalnum() else "_" for c in url.split("//")[-1])[:50]
                    screenshot_path = f"/app/screenshots/{safe_name}_{timestamp}.jpg"

                    is_amazon = "amazon" in url.lower() and "/dp/" in url

                    if is_amazon:
                        # Focused Amazon screenshot
                        for selector in ["#dp-container", "#ppd", "#centerCol"]:
                            try:
                                element = page.locator(selector).first
                                if await element.is_visible():
                                    await element.screenshot(path=screenshot_path, quality=85, type="jpeg")
                                    logger.info(f"Amazon focused screenshot: {selector}")
                                    break
                            except Exception:
                                continue
                        else:
                            await page.screenshot(path=screenshot_path, full_page=False, quality=80, type="jpeg")
                    else:
                        await page.screenshot(path=screenshot_path, full_page=False, quality=80, type="jpeg")

                    logger.info(f"Screenshot saved to {screenshot_path}")
                except Exception as e:
                    logger.warning(f"Screenshot failed: {e}")

                return content, screenshot_path

            finally:
                await context.close()

        except Exception as e:
            logger.error(f"Error scraping {url}: {e}")
            return "", ""


# Global instance
browserless_service = BrowserlessService()
