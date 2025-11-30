"""
Browserless Service
Manages connections to Browserless.io with advanced stealth capabilities.
Handles:
- Connection lifecycle
- Stealth injection
- Proxy rotation
- Human behavior simulation
"""

import asyncio
import logging
import random
import time
from typing import Optional, Any

from playwright.async_api import async_playwright, Browser, BrowserContext, Page
from app.core.search_config import (
    BROWSERLESS_URL, 
    get_amazon_proxies, 
    get_random_user_agent,
    COOKIE_ACCEPT_SELECTORS
)

logger = logging.getLogger(__name__)

# Stealth JS to inject
STEALTH_JS = """
// Advanced Stealth Mode
Object.defineProperty(navigator, 'webdriver', { get: () => false });
delete Object.getPrototypeOf(navigator).webdriver;
window.chrome = { runtime: {} };
Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3, 4, 5] });
Object.defineProperty(navigator, 'languages', { get: () => ['fr-FR', 'fr', 'en-US', 'en'] });
"""

class BrowserlessService:
    def __init__(self):
        self._playwright = None
        self._browser: Optional[Browser] = None
        self._proxies = get_amazon_proxies()

    async def start(self):
        """Initialize the browser connection"""
        if not self._playwright:
            self._playwright = await async_playwright().start()
        
        if not self._browser or not self._browser.is_connected():
            try:
                logger.info(f"Connecting to Browserless at {BROWSERLESS_URL}")
                # Use the stealth endpoint if possible, otherwise standard
                # Note: /chromium/stealth might need specific token or config, 
                # falling back to standard connect_over_cdp which is safer for generic browserless
                self._browser = await self._playwright.chromium.connect_over_cdp(
                    BROWSERLESS_URL,
                    timeout=60000
                )
            except Exception as e:
                logger.error(f"Failed to connect to Browserless: {e}")
                raise

    async def stop(self):
        """Close resources"""
        if self._browser:
            await self._browser.close()
        if self._playwright:
            await self._playwright.stop()

    async def get_context(self, use_proxy: bool = False) -> BrowserContext:
        """Create a new context with stealth settings"""
        await self.start()
        
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
            }
        }

        if use_proxy and self._proxies:
            proxy = random.choice(self._proxies)
            options["proxy"] = proxy
            logger.info(f"Using proxy: {proxy['server'].split('//')[1]}")

        context = await self._browser.new_context(**options)
        
        # Block aggressive tracking but keep images for visual verification if needed
        # (Optimized for speed vs detection)
        await context.route("**/*", lambda route: route.continue_())
        
        return context

    async def simulate_human_behavior(self, page: Page):
        """Simulate random mouse movements and scrolling"""
        try:
            # Mouse movements
            for _ in range(random.randint(2, 5)):
                await page.mouse.move(
                    random.randint(100, 1800),
                    random.randint(100, 900)
                )
                await asyncio.sleep(random.uniform(0.1, 0.3))
            
            # Scrolling
            await page.evaluate("window.scrollBy(0, 300)")
            await asyncio.sleep(random.uniform(0.5, 1.0))
            await page.evaluate("window.scrollBy(0, -100)")
        except Exception:
            pass

    async def handle_popups(self, page: Page):
        """Attempt to close cookie banners and popups"""
        try:
            # Check for multiple popups (cookies + promo)
            # We iterate through all selectors and click any that are visible
            # We do this in a loop to handle sequential popups
            for _ in range(3): # Try up to 3 times for sequential popups
                clicked_something = False
                for selector in COOKIE_ACCEPT_SELECTORS:
                    try:
                        # Use a short timeout for check
                        element = page.locator(selector).first
                        if await element.is_visible(timeout=100):
                            await element.click()
                            logger.info(f"Closed popup/banner with {selector}")
                            await asyncio.sleep(0.5) # Wait for animation
                            clicked_something = True
                    except Exception:
                        continue
                
                if not clicked_something:
                    break
        except Exception:
            pass

    async def _extract_generic_price(self, page: Page) -> str:
        """
        Extract price from generic e-commerce pages using common selectors and patterns.
        Returns price text (e.g., "1,99 €") or empty string if not found.
        IMPROVED: Better validation to avoid "fantasy" prices
        """
        # Common price selectors used across e-commerce sites (ordered by priority)
        price_selectors = [
            # Highest priority: semantic and explicit current prices
            "[itemprop='price']",
            "[data-testid='price']",
            "[data-test='price']",
            ".current-price",
            ".sale-price",
            ".final-price",
            ".product-price",
            ".special-price",
            "[data-price]",
            # Specific e-commerce platforms
            ".price-current",
            ".price-now",
            ".price-sales",
            # Medium priority: generic price classes (exclude old/was/original/strikethrough)
            "[class*='price']:not([class*='old']):not([class*='was']):not([class*='original']):not([class*='before']):not([class*='regular']):not([class*='strike']):not([class*='barre'])",
            # ID-based
            "#price",
            "#product-price",
            "#our-price",
            "#main-price",
            # French-specific
            "span[class*='prix']:not([class*='ancien']):not([class*='barre']):not([class*='promotion'])",
            "div[class*='prix']:not([class*='ancien']):not([class*='barre'])",
            "span[class*='tarif']",
            ".prix-actuel",
            ".prix-vente",
            # Lower priority: generic .price (might catch old prices)
            ".price:not(.old-price):not(.was-price)",
        ]

        found_prices = []

        for selector in price_selectors:
            try:
                elements = page.locator(selector)
                count = await elements.count()

                # Check up to 3 elements per selector
                for i in range(min(count, 3)):
                    try:
                        element = elements.nth(i)
                        if await element.is_visible(timeout=1000):
                            # Check if element is strikethrough (old price)
                            try:
                                text_decoration = await element.evaluate("el => window.getComputedStyle(el).textDecoration")
                                if "line-through" in text_decoration:
                                    logger.debug(f"Skipping strikethrough price at {selector}")
                                    continue  # Skip crossed-out prices
                            except Exception:
                                pass  # If we can't check, continue anyway

                            price_text = await element.inner_text()
                            # Check if it looks like a price (contains € or digits with comma/dot)
                            if price_text and ('€' in price_text or (',' in price_text and any(c.isdigit() for c in price_text))):
                                # Clean up price text
                                price_text = price_text.strip()

                                # VALIDATION: Check if price is reasonable (not fantasy)
                                import re
                                numeric_match = re.search(r'(\d+[.,]?\d*)', price_text.replace(' ', '').replace('\xa0', ''))
                                if numeric_match:
                                    try:
                                        # Parse as float
                                        price_val = float(numeric_match.group(1).replace(',', '.'))

                                        # Reject unreasonable prices
                                        if price_val <= 0 or price_val < 0.01 or price_val > 100000:
                                            logger.debug(f"Rejected unreasonable price: {price_val}€ from {selector}")
                                            continue

                                        found_prices.append((selector, price_text))
                                        logger.info(f"Found valid price via {selector}: {price_text} ({price_val}€)")

                                        # Return immediately if high-priority
                                        if selector in ["[itemprop='price']", "[data-testid='price']", ".current-price", ".sale-price", ".final-price", ".product-price"]:
                                            return price_text
                                    except (ValueError, AttributeError):
                                        logger.debug(f"Could not parse price: {price_text}")
                                        continue
                    except Exception:
                        continue
            except Exception:
                continue

        # If we found prices with lower-priority selectors
        if found_prices:
            # When multiple prices found, the LAST one in DOM order is usually the current price
            # (websites typically show: old price first, then current price)
            best_price = found_prices[-1][1]  # Take last (most recently added)
            if len(found_prices) > 1:
                prices_list = [p[1] for p in found_prices]
                logger.info(f"Multiple prices found: {prices_list}, selecting last (most likely current): {best_price}")
            return best_price

        # Fallback: Use regex to find price patterns in all text
        try:
            all_text = await page.inner_text('body')
            import re
            # Match French price formats: "1,99 €", "12,99€", "1.234,56 €"
            price_matches = re.findall(r'\d+[,\.]\d{2}\s*€', all_text)
            if price_matches:
                # Return first price found
                logger.info(f"Found price via regex: {price_matches[0]}")
                return price_matches[0]
        except Exception:
            pass

        logger.warning("Could not extract generic price with any method")
        return ""

    async def _extract_amazon_price(self, page: Page) -> str:
        """
        Extract price directly from Amazon product page using CSS selectors.
        Returns price text (e.g., "89,99 €") or empty string if not found.
        """
        # Amazon price selectors in priority order
        # Note: .a-offscreen elements are hidden but contain the full price for screen readers
        price_selectors = [
            ".a-price .a-offscreen",  # Most reliable - hidden text with full price
            "#corePrice_desktop .a-price .a-offscreen",
            "#corePriceDisplay_desktop_feature_div .a-price .a-offscreen",
            ".a-price[data-a-color='price'] .a-offscreen",
            "#priceblock_ourprice",  # Older Amazon layout
            "#priceblock_dealprice",  # Deal prices
            "span.a-price-whole",  # Visible whole number part
        ]

        for selector in price_selectors:
            try:
                # Don't check visibility for .a-offscreen elements (they're hidden by design)
                element = page.locator(selector).first

                # For offscreen elements, just check if they exist and have text
                if "offscreen" in selector or "priceblock" in selector:
                    price_text = await element.inner_text(timeout=2000)
                else:
                    # For visible elements, check visibility first
                    if await element.is_visible(timeout=2000):
                        price_text = await element.inner_text()
                    else:
                        continue

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

        logger.warning("Could not extract Amazon price with any selector")
        return ""

    async def get_page_content(
        self,
        url: str,
        use_proxy: bool = False,
        wait_selector: str = None,
        extract_text: bool = False
    ) -> tuple[str, str]:
        """
        Fetch page content with full stealth lifecycle.

        Args:
            url: URL to fetch
            use_proxy: Whether to use proxy rotation
            wait_selector: CSS selector to wait for before capturing
            extract_text: If True, returns visible text; if False, returns HTML source

        Returns:
            (content, screenshot_path) where content is either HTML or visible text
        """
        context = await self.get_context(use_proxy=use_proxy)
        page = await context.new_page()
        
        try:
            logger.info(f"Navigating to {url}")
            # Random delay before start
            await asyncio.sleep(random.uniform(0.5, 1.5))
            
            response = await page.goto(url, wait_until="domcontentloaded", timeout=60000)
            
            if response.status == 503:
                logger.warning(f"503 Detected on {url}")
                # Retry logic could be handled here or by caller, 
                # for now we return what we have, caller decides
            
            # Handle pre-search interaction
            from app.core.search_config import SITE_CONFIGS
            for config in SITE_CONFIGS.values():
                if config["search_url"].split("/")[2] in url:
                    # Handle complex interaction list
                    if config.get("pre_search_interaction"):
                        try:
                            logger.info(f"Executing pre-search interaction sequence for {config['name']}")
                            for step in config["pre_search_interaction"]:
                                step_type = step.get("type")
                                selector = step.get("selector")
                                
                                if step_type == "input":
                                    logger.info(f"Inputting text into {selector}")
                                    await page.fill(selector, step["value"])
                                    
                                elif step_type == "click":
                                    logger.info(f"Clicking {selector}")
                                    # Use force=True to bypass potential overlays
                                    await page.click(selector, timeout=5000)
                                    
                                elif step_type == "wait":
                                    seconds = step.get("seconds", 1)
                                    logger.info(f"Waiting {seconds}s")
                                    await asyncio.sleep(seconds)
                                    
                            logger.info("Pre-search sequence completed")
                            await asyncio.sleep(2) # Final stabilization wait
                        except Exception as e:
                            logger.warning(f"Pre-search sequence failed: {e}")

                    # Handle simple selector (legacy support)
                    elif config.get("pre_search_selector"):
                        try:
                            selector = config["pre_search_selector"]
                            logger.info(f"Attempting pre-search interaction: {selector}")
                            if await page.locator(selector).is_visible(timeout=5000):
                                await page.click(selector)
                                logger.info("Clicked pre-search selector")
                                await asyncio.sleep(2) # Wait for transition
                        except Exception as e:
                            logger.warning(f"Pre-search interaction failed: {e}")
                    break

            await self.handle_popups(page)
            await self.simulate_human_behavior(page)
            
            if wait_selector:
                try:
                    await page.wait_for_selector(wait_selector, timeout=10000)
                except Exception:
                    logger.warning(f"Wait selector {wait_selector} timed out")

            # For Amazon product pages, wait for price to load
            if "amazon" in url.lower() and "/dp/" in url:
                amazon_price_selectors = [
                    ".a-price .a-offscreen",  # Main price element
                    "#corePriceDisplay_desktop_feature_div",  # Price section
                    "#corePrice_desktop",  # Alternative price container
                    ".a-price-whole",  # Price number
                ]
                for selector in amazon_price_selectors:
                    try:
                        await page.wait_for_selector(selector, timeout=5000, state="visible")
                        logger.info(f"Amazon price element found: {selector}")
                        break
                    except Exception:
                        continue
                else:
                    logger.warning("No Amazon price selector found, proceeding anyway")

            # Wait for network idle to ensure dynamic content loads
            try:
                await page.wait_for_load_state("networkidle", timeout=5000)
            except Exception:
                pass

            # Extract content based on extract_text parameter
            if extract_text:
                # Extract visible text for AI analysis (monitoring use case)
                try:
                    content = await page.inner_text('body')
                    logger.info(f"Extracted {len(content)} chars of visible text from page")

                    # Normalize French prices to English format for AI
                    import re
                    # Pattern 1: digits€XX → digits.XX € (e.g., "3€99" → "3.99 €")
                    content = re.sub(r'(\d+)€(\d{2})\b', r'\1.\2 €', content)
                    # Pattern 2: digits,XX € → digits.XX € (e.g., "3,99 €" → "3.99 €")
                    content = re.sub(r'(\d+),(\d{2})\s*€', r'\1.\2 €', content)
                    # Remove spaces in thousands: 1 234.56 → 1234.56
                    content = re.sub(r'(\d+)\s(\d{3})', r'\1\2', content)
                    logger.debug("Normalized French price formats to English")

                except Exception as e:
                    # Fallback to HTML content if inner_text fails
                    logger.warning(f"Failed to extract inner_text, falling back to HTML: {e}")
                    content = await page.content()

                # Extract price directly from DOM for better accuracy
                extracted_price = None

                # For Amazon, use specific selectors
                if "amazon" in url.lower() and "/dp/" in url:
                    extracted_price = await self._extract_amazon_price(page)
                    if extracted_price:
                        logger.info(f"Extracted Amazon price: {extracted_price}")
                else:
                    # For other sites, try common price selectors
                    extracted_price = await self._extract_generic_price(page)
                    if extracted_price:
                        logger.info(f"Extracted generic price: {extracted_price}")

                # Prepend extracted price to content if found
                if extracted_price:
                    # Convert French format to English for AI
                    import re
                    normalized_price = extracted_price
                    # Pattern 1: digits€digits → digits.digits € (e.g., "3€99" → "3.99 €")
                    normalized_price = re.sub(r'(\d+)€(\d{2})', r'\1.\2 €', normalized_price)
                    # Pattern 2: digits,digits → digits.digits (e.g., "3,99" → "3.99")
                    normalized_price = re.sub(r'(\d+),(\d{2})', r'\1.\2', normalized_price)
                    # Remove spaces in thousands separators if any (1 234,56 → 1234.56)
                    normalized_price = normalized_price.replace(' ', '')

                    content = f"PRIX DÉTECTÉ: {normalized_price}\n\n{content}"
                    logger.info(f"Prepended normalized price to content: {normalized_price} (original: {extracted_price})")
                else:
                    logger.warning("Could not extract price from DOM, relying on text/image only")
            else:
                # Extract raw HTML for parsing (search use case)
                content = await page.content()
                logger.debug(f"Extracted {len(content)} chars of HTML from page")

            
            # Take screenshot if needed for AI analysis
            screenshot_path = ""
            try:
                import os
                from datetime import datetime
                
                # Ensure directory exists
                screenshots_dir = "/app/screenshots"
                if not os.path.exists(screenshots_dir):
                    os.makedirs(screenshots_dir, exist_ok=True)
                
                timestamp = int(time.time() * 1000)
                safe_name = "".join(c if c.isalnum() else "_" for c in url.split("//")[-1])[:50]
                filename = f"{safe_name}_{timestamp}.jpg"
                screenshot_path = f"{screenshots_dir}/{filename}"

                # For Amazon, take focused screenshot of product info area
                # Full-page screenshots of Amazon are too large and price becomes tiny when resized
                is_amazon = "amazon" in url.lower() and "/dp/" in url

                if is_amazon:
                    # Try to screenshot just the main product area containing price
                    try:
                        # Look for main product container
                        product_selectors = [
                            "#dp-container",  # Main product container
                            "#ppd",  # Product page data
                            "#centerCol",  # Center column with price
                        ]
                        screenshot_taken = False
                        for selector in product_selectors:
                            try:
                                element = page.locator(selector).first
                                if await element.is_visible():
                                    await element.screenshot(path=screenshot_path, quality=85, type="jpeg")
                                    logger.info(f"Amazon focused screenshot saved using {selector}")
                                    screenshot_taken = True
                                    break
                            except Exception:
                                continue

                        if not screenshot_taken:
                            # Fallback to viewport screenshot (better than full-page for Amazon)
                            await page.screenshot(path=screenshot_path, full_page=False, quality=80, type="jpeg")
                            logger.info("Amazon viewport screenshot saved (fallback)")
                    except Exception as e:
                        logger.warning(f"Amazon focused screenshot failed: {e}, using viewport")
                        await page.screenshot(path=screenshot_path, full_page=False, quality=80, type="jpeg")
                else:
                    # For non-Amazon sites, use full_page to capture entire page
                    await page.screenshot(path=screenshot_path, full_page=True, quality=80, type="jpeg")
                    logger.info(f"Full-page screenshot saved to {screenshot_path}")
            except Exception as e:
                logger.warning(f"Failed to take screenshot: {e}")

            return content, screenshot_path

        except Exception as e:
            logger.error(f"Error fetching {url}: {e}")
            return "", ""
        finally:
            await context.close()

# Global instance
browserless_service = BrowserlessService()
