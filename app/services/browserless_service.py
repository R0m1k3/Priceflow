"""
Browserless Service - Unified Persistent Browser Service
Consolidates ScraperService pattern with Amazon price extraction improvements

Features:
- Persistent browser connection (singleton pattern)
- Auto-reconnection on disconnection
- Thread-safe operations (asyncio.Lock)
- Improved Amazon price extraction (main price block targeting)
- Generic price extraction with strict validation
- Screenshot and text extraction
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
    "input[aria-labelledby='sp-cc-accept-label']",
    "#nav-flyout-prime button",
    
    # Amazon Interstitials (Soft blocks)
    "button:has-text('Continuer les achats')",
    "span:has-text('Continuer les achats')",
    "a:has-text('Continuer les achats')",
    "input[value='Continuer les achats']",
    "input[value='Continue shopping']",
    "span.a-button-inner > input.a-button-input[type='submit']",
    "form:has-text('Continuer les achats') input[type='submit']",
    "[aria-labelledby='continue-shopping-label']",
]


@dataclass
class ScrapeConfig:
    """Configuration for scraping parameters."""

    smart_scroll: bool = False
    scroll_pixels: int = 350
    text_length: int = 0
    timeout: int = 30000  # 30s default


class BrowserlessService:
    """
    Unified persistent browserless service with auto-reconnection.
    Combines ScraperService pattern with enhanced price extraction.
    """

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
            logger.info("🚀 Initializing BrowserlessService shared browser...")
            cls._playwright = await async_playwright().start()
            cls._browser = await cls._connect_browser(cls._playwright)
            logger.info("✅ BrowserlessService browser ready (persistent)")

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
        """
        Ensure browser is connected, reconnect if needed.
        Returns True if browser is ready, False otherwise.
        """
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
                    logger.debug("✅ Browser connection test passed (reusing)")
                    return True
                except Exception as e:
                    logger.error(f"❌ Browser connection test failed: {e}")
                    logger.info("🔄 Attempting to reconnect...")
                    
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
            "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
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
        
        # Inject stealth scripts
        await context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined
            });
            Object.defineProperty(navigator, 'languages', {
                get: () => ['fr-FR', 'fr', 'en-US', 'en']
            });
            Object.defineProperty(navigator, 'plugins', {
                get: () => [1, 2, 3, 4, 5]
            });
            window.chrome = { runtime: {} };
            
            // Mock permissions
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
        """Navigate to URL and wait for page load."""
        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=timeout)
            logger.info(f"✅ Page loaded (domcontentloaded): {url}")

            try:
                await page.wait_for_load_state("networkidle", timeout=2000)
                logger.info("✅ Network idle reached")
            except PlaywrightTimeoutError:
                logger.debug("⚠️ Network idle timed out (non-critical), proceeding...")

        except Exception as e:
            logger.warning(f"Navigation warning for {url}: {e}")

        await page.wait_for_timeout(1500)

    @staticmethod
    async def _handle_popups(page: Page):
        """Attempt to close popups and cookie banners with retry logic."""
        logger.debug("Attempting to close popups...")
        
        # First pass: Try to close all visible popups
        closed_popups = []
        for popup_selector in POPUP_SELECTORS:
            try:
                if await page.locator(popup_selector).count() > 0:
                    logger.info(f"🚫 Closing popup: {popup_selector}")
                    await page.locator(popup_selector).first.click(timeout=2000)
                    closed_popups.append(popup_selector)
                    await page.wait_for_timeout(1000)
            except Exception:
                pass

        # Try Escape key multiple times
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

    @staticmethod
    async def _extract_amazon_price(page: Page) -> str:
        """
        Extract price from Amazon product page with strict validation.
        Prioritize main price block to avoid false positives.
        """
        # Priority 1: Main price display area (most specific)
        main_price_selectors = [
            "#corePriceDisplay_desktop_feature_div .a-price .a-offscreen",
            "#corePrice_desktop .a-price .a-offscreen",
            "#corePrice_feature_div .a-price .a-offscreen",
            "#priceblock_ourprice",
            "#priceblock_dealprice",
            "#priceblock_saleprice",
        ]
        
        for selector in main_price_selectors:
            try:
                elements = page.locator(selector)
                count = await elements.count()
                
                for i in range(count):
                    element = elements.nth(i)
                    
                    if not await element.is_visible(timeout=1000):
                        continue
                    
                    # Check if strikethrough (old price)
                    try:
                        text_decoration = await element.evaluate("el => window.getComputedStyle(el).textDecoration")
                        if "line-through" in text_decoration:
                            continue
                    except Exception:
                        pass
                    
                    price_text = await element.inner_text(timeout=1000)
                    if price_text and price_text.strip():
                        if re.search(r'\d+[.,]\d{2}', price_text):
                            numeric_match = re.search(r'(\d+)[.,](\d{2})', price_text)
                            if numeric_match:
                                price_val = float(f"{numeric_match.group(1)}.{numeric_match.group(2)}")
                                if 0.01 <= price_val <= 10000:
                                    logger.info(f"💰 Amazon main price via {selector}: {price_text} ({price_val}€)")
                                    return price_text.strip()
            except Exception as e:
                logger.debug(f"Selector {selector} failed: {e}")
                continue
        
        # Priority 2: Buybox area
        try:
            buybox = page.locator("#buybox, #buybox_feature_div, #desktop_buybox")
            if await buybox.count() > 0:
                price_elem = buybox.locator(".a-price .a-offscreen").first
                if await price_elem.is_visible(timeout=1000):
                    price_text = await price_elem.inner_text()
                    if price_text and re.search(r'\d+[.,]\d{2}', price_text):
                        numeric_match = re.search(r'(\d+)[.,](\d{2})', price_text)
                        if numeric_match:
                            price_val = float(f"{numeric_match.group(1)}.{numeric_match.group(2)}")
                            if 0.01 <= price_val <= 10000:
                                logger.info(f"💰 Amazon buybox price: {price_text} ({price_val}€)")
                                return price_text.strip()
        except Exception:
            pass
        
        # Priority 3: Whole + Fraction
        try:
            price_container = page.locator("#corePriceDisplay_desktop_feature_div, #corePrice_desktop, #price")
            whole_elem = price_container.locator("span.a-price-whole").first
            fraction_elem = price_container.locator("span.a-price-fraction").first
            
            whole = await whole_elem.inner_text(timeout=1000)
            fraction = await fraction_elem.inner_text(timeout=1000)
            
            if whole and fraction:
                whole = whole.rstrip('.,')
                price_text = f"{whole},{fraction}"
                
                numeric_match = re.search(r'(\d+)[.,](\d{2})', price_text)
                if numeric_match:
                    price_val = float(f"{numeric_match.group(1)}.{numeric_match.group(2)}")
                    if 0.01 <= price_val <= 10000:
                        logger.info(f"💰 Amazon whole+fraction: {price_text} ({price_val}€)")
                        return price_text
        except Exception:
            pass
        
        logger.warning("⚠️ Could not extract Amazon price with any method")
        return ""

    @staticmethod
    async def _extract_generic_price(page: Page) -> str:
        """Extract price from generic e-commerce pages with strict validation."""
        # High-priority semantic selectors
        high_priority_selectors = [
            "[itemprop='price']",
            "[data-testid='price']",
            "[data-test='price']",
            "[data-price]",
        ]

        # Medium-priority specific selectors
        medium_priority_selectors = [
            ".current-price",
            ".sale-price",
            ".final-price",
            ".product-price",
            ".special-price",
            ".price-current",
            ".price-now",
            ".prix-actuel",
            "#price",
            "#product-price",
        ]

        # Low-priority generic selectors
        low_priority_selectors = [
            "span[class*='prix']:not([class*='ancien']):not([class*='barre'])",
            ".price:not(.old-price):not(.was-price)",
            "[class*='price']:not([class*='old']):not([class*='was']):not([class*='original']):not([class*='before']):not([class*='strike']):not([class*='barre'])",
        ]

        all_selectors = high_priority_selectors + medium_priority_selectors + low_priority_selectors
        found_prices = []

        # Strict French price regex
        strict_price_regex = re.compile(r'(\d{1,4}(?:\s?\d{3})*[.,]\d{2})\s*€?')

        for selector in all_selectors:
            try:
                elements = page.locator(selector)
                count = await elements.count()

                for i in range(min(count, 3)):
                    try:
                        element = elements.nth(i)
                        
                        if not await element.is_visible(timeout=1000):
                            continue

                        # Check if strikethrough
                        try:
                            text_decoration = await element.evaluate("el => window.getComputedStyle(el).textDecoration")
                            if "line-through" in text_decoration:
                                logger.debug(f"⏭️ Skipping strikethrough price at {selector}")
                                continue
                        except Exception:
                            pass

                        price_text = await element.inner_text()
                        if not price_text:
                            continue

                        price_match = strict_price_regex.search(price_text)
                        if price_match:
                            matched_price = price_match.group(0)
                            
                            numeric_text = matched_price.replace('€', '').replace(' ', '').replace(',', '.')
                            try:
                                price_val = float(numeric_text)
                                
                                if 0.01 <= price_val <= 100000:
                                    found_prices.append((selector, matched_price))
                                    logger.info(f"💰 Valid price via {selector}: {matched_price} ({price_val}€)")

                                    if selector in high_priority_selectors:
                                        return matched_price
                                else:
                                    logger.debug(f"⏭️ Price out of range ({price_val}€): {matched_price}")
                            except ValueError:
                                logger.debug(f"⏭️ Could not parse price value: {matched_price}")
                                continue

                    except Exception as e:
                        logger.debug(f"Error processing element {i} of {selector}: {e}")
                        continue
            except Exception as e:
                logger.debug(f"Error with selector {selector}: {e}")
                continue

        if found_prices:
            best_price = found_prices[0][1]  # Take first (highest priority)
            if len(found_prices) > 1:
                prices_list = [p[1] for p in found_prices]
                logger.info(f"💰 Multiple prices found: {prices_list}, selecting first: {best_price}")
            return best_price

        # Fallback: Strict regex in body text
        try:
            all_text = await page.inner_text('body')
            price_matches = strict_price_regex.findall(all_text)
            if price_matches:
                first_match = price_matches[0]
                logger.info(f"💰 Found price via regex fallback: {first_match}")
                return first_match
        except Exception as e:
            logger.debug(f"Regex fallback failed: {e}")

        logger.warning("⚠️ Could not extract generic price with any method")
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
        Fetch page content with persistent browser.
        
        Returns:
            tuple[content, screenshot_path]: Content (HTML or text) and screenshot path
        """
        if not await cls._ensure_browser_connected():
            logger.error("❌ Failed to establish browser connection")
            return "", ""

        try:
            context = await cls._create_context(cls._browser, use_proxy=use_proxy)
            page = await context.new_page()

            try:
                await cls._navigate_and_wait(page, url, 30000)
                await cls._handle_popups(page)

                # Amazon-specific wait
                if "amazon" in url.lower() and "/dp/" in url:
                    amazon_selectors = [".a-price .a-offscreen", "#corePriceDisplay_desktop_feature_div"]
                    for selector in amazon_selectors:
                        try:
                            await page.wait_for_selector(selector, timeout=5000, state="visible")
                            logger.info(f"✅ Amazon price element found: {selector}")
                            break
                        except Exception:
                            continue
                
                # Generic wait selector
                if wait_selector:
                    try:
                        logger.info(f"⏳ Waiting for selector: {wait_selector}")
                        await page.wait_for_selector(wait_selector, timeout=10000, state="attached")
                        logger.info(f"✅ Wait selector found: {wait_selector}")
                    except Exception as e:
                        logger.warning(f"⚠️ Wait selector {wait_selector} timed out or failed: {e}")

                # Extract content
                if extract_text:
                    content = await page.inner_text('body')
                    logger.info(f"📄 Extracted {len(content)} chars of visible text")

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

                    if extracted_price:
                        normalized_price = re.sub(r'(\d+),(\d{2})', r'\1.\2', extracted_price)
                        normalized_price = normalized_price.replace(' ', '')
                        content = f"PRIX DÉTECTÉ: {normalized_price}\n\n{content}"
                        logger.info(f"💰 Prepended price: {normalized_price}")
                    else:
                        logger.warning("⚠️ No price detected for this page")
                else:
                    content = await page.content()
                    logger.debug(f"📄 Extracted {len(content)} chars of HTML")

                # Take screenshot
                screenshot_path = ""
                try:
                    os.makedirs("screenshots", exist_ok=True)
                    timestamp = int(time.time() * 1000)
                    safe_name = "".join(c if c.isalnum() else "_" for c in url.split("//")[-1])[:50]
                    screenshot_path = f"screenshots/{safe_name}_{timestamp}.jpg"

                    is_amazon = "amazon" in url.lower() and "/dp/" in url

                    if is_amazon:
                        # Focused Amazon screenshot
                        for selector in ["#dp-container", "#ppd", "#centerCol"]:
                            try:
                                element = page.locator(selector).first
                                if await element.is_visible():
                                    await element.screenshot(path=screenshot_path, quality=85, type="jpeg")
                                    logger.info(f"📸 Amazon focused screenshot: {selector}")
                                    break
                            except Exception:
                                continue
                        else:
                            await page.screenshot(path=screenshot_path, full_page=False, quality=80, type="jpeg")
                    else:
                        await page.screenshot(path=screenshot_path, full_page=False, quality=80, type="jpeg")
                        logger.info(f"📸 Viewport screenshot saved to {screenshot_path}")

                except Exception as e:
                    logger.warning(f"Screenshot failed: {e}")

                return content, screenshot_path

            finally:
                await context.close()

        except Exception as e:
            logger.error(f"❌ Error scraping {url}: {e}", exc_info=True)
            return "", ""

    @classmethod
    async def scrape_item(
        cls,
        url: str,
        selector: str | None = None,
        item_id: int | None = None,
        config: ScrapeConfig | None = None,
    ) -> tuple[str | None, str]:
        """
        Legacy method for compatibility with ScraperService pattern.
        Returns: (screenshot_path, page_text)
        """
        if config is None:
            config = ScrapeConfig()

        # Call get_page_content with extract_text=True
        page_text, screenshot_path = await cls.get_page_content(
            url,
            extract_text=True
        )

        return screenshot_path, page_text


# Global instance (backward compatibility)
browserless_service = BrowserlessService()
