"""
Amazon Scraper Service - Using persistent browser connection
Based on ScraperService pattern for better session management and anti-detection
"""

import asyncio
import logging
import os
import random
import re
from dataclasses import dataclass
from datetime import datetime
from urllib.parse import quote_plus

from bs4 import BeautifulSoup
from playwright.async_api import Browser, BrowserContext, Page, async_playwright
from playwright.async_api import TimeoutError as PlaywrightTimeoutError
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

BROWSERLESS_URL = os.getenv("BROWSERLESS_URL", "ws://browserless:3000")

# Amazon configuration
AMAZON_FR_BASE_URL = "https://www.amazon.fr"
AMAZON_FR_SEARCH_URL = "https://www.amazon.fr/s?k={query}"

# Retry configuration for login wall avoidance
MAX_RETRY_ATTEMPTS = 3
RETRY_DELAY_SECONDS = 2.0

# Cookie/popup selectors for Amazon (extended list)
AMAZON_POPUP_SELECTORS = [
    "#sp-cc-accept",  # Cookie banner - accept
    "#sp-cc-rejectall-link",  # Cookie banner - reject all
    "#sp-cc-rejectall-make-promise-link",  # Alternative reject
    "button[data-action='a-popover-close']",
    "[data-action='sp-cc-accept']",
    "input[aria-labelledby='sp-cc-accept-label']",
    "button:has-text('Accepter')",
    "button:has-text('Refuser')",
    "button:has-text('Continuer')",
    ".a-button-close",  # Generic Amazon close button
    "[data-action='a-modal-close']",
]


# ============================================================================
# PYDANTIC SCHEMAS
# ============================================================================


class AmazonProduct(BaseModel):
    """Schema for Amazon product extraction"""

    title: str = Field(description="Product title")
    url: str = Field(description="Product URL")
    price: float | None = Field(default=None, description="Price in EUR")
    original_price: float | None = Field(default=None, description="Original price if discounted")
    rating: float | None = Field(default=None, description="Product rating (0-5)")
    reviews_count: int | None = Field(default=None, description="Number of reviews")
    image_url: str | None = Field(default=None, description="Product image URL")
    in_stock: bool = Field(default=True, description="Availability status")
    prime: bool = Field(default=False, description="Prime eligible")
    sponsored: bool = Field(default=False, description="Is sponsored")


# ============================================================================
# PARSING HELPERS
# ============================================================================


def parse_amazon_price(price_text: str) -> float | None:
    """Parse Amazon price formats"""
    if not price_text:
        return None

    cleaned = price_text.strip().replace("€", "").replace("EUR", "").strip()
    cleaned = cleaned.replace(" ", "").replace("\xa0", "")
    cleaned = cleaned.replace(",", ".")

    match = re.search(r"(\d+\.?\d*)", cleaned)
    if match:
        try:
            return float(match.group(1))
        except ValueError:
            return None
    return None


def parse_rating(rating_text: str) -> float | None:
    """Parse rating"""
    if not rating_text:
        return None

    match = re.search(r"(\d+[,.]\d+)", rating_text)
    if match:
        try:
            return float(match.group(1).replace(",", "."))
        except ValueError:
            return None
    return None


def parse_reviews_count(reviews_text: str) -> int | None:
    """Parse review count"""
    if not reviews_text:
        return None

    cleaned = re.sub(r"[^\d\s]", "", reviews_text)
    cleaned = cleaned.replace(" ", "").replace("\xa0", "")

    try:
        return int(cleaned)
    except ValueError:
        return None


# ============================================================================
# AMAZON SCRAPER SERVICE
# ============================================================================


class AmazonScraperService:
    """Persistent browser service for Amazon scraping"""

    _playwright = None
    _browser: Browser | None = None
    _lock = asyncio.Lock()

    @classmethod
    async def initialize(cls):
        """Initialize shared browser (Thread-Safe)"""
        async with cls._lock:
            await cls._initialize()

    @classmethod
    async def _initialize(cls):
        """Internal initialization"""
        if cls._browser is None:
            logger.info("Initializing AmazonScraperService shared browser...")
            cls._playwright = await async_playwright().start()
            cls._browser = await cls._connect_browser(cls._playwright)
            logger.info("AmazonScraperService initialized.")

    @classmethod
    async def shutdown(cls):
        """Shutdown shared browser"""
        async with cls._lock:
            if cls._browser:
                logger.info("Shutting down AmazonScraperService...")
                await cls._browser.close()
                cls._browser = None
            if cls._playwright:
                await cls._playwright.stop()
                cls._playwright = None
            logger.info("AmazonScraperService shutdown complete.")

    @classmethod
    async def _ensure_browser_connected(cls) -> bool:
        """Ensure browser is connected, reconnect if needed"""
        async with cls._lock:
            try:
                if cls._browser is None:
                    logger.warning("Browser not initialized, initializing...")
                    await cls._initialize()
                    return cls._browser is not None

                # Test connection
                try:
                    test_context = await cls._browser.new_context()
                    await test_context.close()
                    return True
                except Exception as e:
                    logger.error(f"Browser connection test failed: {e}")
                    logger.info("Attempting to reconnect...")
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
        """Connect to Browserless"""
        logger.info(f"Connecting to Browserless at {BROWSERLESS_URL}")
        return await p.chromium.connect_over_cdp(BROWSERLESS_URL)

    @staticmethod
    async def _create_context(browser: Browser, proxy: dict | None = None, attempt: int = 1) -> BrowserContext:
        """Create browser context with dynamic stealth settings and optional proxy"""
        from app.core.search_config import get_random_stealth_config

        stealth_config = get_random_stealth_config()
        logger.info(f"🎲 Attempt {attempt}: Creating context with new identity")
        ua = stealth_config["ua"]
        ch = stealth_config["ch"]
        platform = stealth_config["platform"]

        logger.info(f"🎭 Using stealth profile: {ua[:50]}...")
        if proxy:
            logger.info(f"🌐 Using proxy: {proxy.get('server', 'unknown')}")

        context_options = dict(
            viewport={"width": 1920, "height": 1080},
            user_agent=ua,
            locale="fr-FR",
            timezone_id="Europe/Paris",
            extra_http_headers={
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
                "Accept-Language": "fr-FR,fr;q=0.9,en-US;q=0.8,en;q=0.7",
                "Accept-Encoding": "gzip, deflate, br",
                "DNT": "1",
                "Connection": "keep-alive",
                "Upgrade-Insecure-Requests": "1",
                "Sec-Ch-Ua": ch,
                "Sec-Ch-Ua-Mobile": "?0",
                "Sec-Ch-Ua-Platform": platform,
                "Sec-Fetch-Dest": "document",
                "Sec-Fetch-Mode": "navigate",
                "Sec-Fetch-Site": "none",
                "Sec-Fetch-User": "?1",
                "Cache-Control": "max-age=0",
                "Referer": "https://www.google.fr/",
            },
        )

        # Add proxy if provided
        if proxy:
            context_options["proxy"] = proxy

        context = await browser.new_context(**context_options)

        # Comprehensive stealth mode injector
        await context.add_init_script("""
            // Reset webdriver
            Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
            
            // Re-mock chrome object
            window.chrome = {
                runtime: {},
                loadTimes: function() {},
                csi: function() {},
                app: {}
            };
            
            // Consistent plugins
            Object.defineProperty(navigator, 'plugins', {
                get: () => [
                    { name: 'PDF Viewer', filename: 'internal-pdf-viewer' },
                    { name: 'Chrome PDF Viewer', filename: 'internal-pdf-viewer' },
                    { name: 'Chromium PDF Viewer', filename: 'internal-pdf-viewer' }
                ]
            });
            
            // Languages
            Object.defineProperty(navigator, 'languages', {
                get: () => ['fr-FR', 'fr', 'en-US', 'en']
            });
            
            // Device Memory (randomized)
            Object.defineProperty(navigator, 'deviceMemory', { get: () => 8 });
        """)

        await context.route("**/*", lambda route: route.continue_())
        return context

    @staticmethod
    async def _simulate_human_behavior(page: Page):
        """Perform subtle human-like interactions"""
        try:
            # Random mouse movements
            for _ in range(3):
                x = random.randint(100, 800)
                y = random.randint(100, 600)
                await page.mouse.move(x, y, steps=10)
                await asyncio.sleep(random.uniform(0.1, 0.3))

            # Subtle scroll
            await page.evaluate("window.scrollBy(0, window.innerHeight / 4)")
            await asyncio.sleep(random.uniform(0.5, 1.0))
            await page.evaluate("window.scrollBy(0, -window.innerHeight / 5)")
        except Exception as e:
            logger.warning(f"Failed to simulate human behavior: {e}")

    @staticmethod
    async def _handle_popups(page: Page):
        """Close Amazon popups/cookies"""
        logger.info("Handling Amazon popups...")
        for selector in AMAZON_POPUP_SELECTORS:
            try:
                if await page.locator(selector).count() > 0:
                    logger.info(f"Found popup: {selector}")
                    await page.locator(selector).first.click(timeout=2000)
                    await page.wait_for_timeout(1000)
            except Exception:
                pass

        try:
            await page.keyboard.press("Escape")
        except Exception:
            pass

    @classmethod
    async def scrape_search(cls, query: str, max_results: int = 50) -> list[AmazonProduct]:
        """
        Scrape Amazon France search results with retry mechanism

        Args:
            query: Search query
            max_results: Maximum products to return

        Returns:
            List of AmazonProduct objects
        """
        from app.core.search_config import get_amazon_proxies

        search_url = AMAZON_FR_SEARCH_URL.format(query=quote_plus(query))
        logger.info(f"🔍 Searching Amazon France: {query}")
        logger.info(f"📍 URL: {search_url}")

        # Ensure browser is connected
        if not await cls._ensure_browser_connected():
            logger.error("Failed to establish browser connection")
            return []

        # Get available proxies for rotation
        proxies = get_amazon_proxies()

        # Retry loop with identity rotation
        for attempt in range(1, MAX_RETRY_ATTEMPTS + 1):
            logger.info(f"🔄 Attempt {attempt}/{MAX_RETRY_ATTEMPTS}")

            # Select proxy for this attempt (cycle through or None if empty)
            proxy = proxies[(attempt - 1) % len(proxies)] if proxies else None

            products = await cls._try_scrape(query, max_results, proxy, attempt)

            if products:
                logger.info(f"✅ Successfully extracted {len(products)} products on attempt {attempt}")
                return products

            if attempt < MAX_RETRY_ATTEMPTS:
                delay = RETRY_DELAY_SECONDS * attempt  # Exponential backoff
                logger.warning(f"⏳ Attempt {attempt} failed, retrying in {delay}s with new identity...")
                await asyncio.sleep(delay)

        if not products and proxies:
            logger.warning("⚠️ All proxy attempts failed. Attempting fallback to direct connection...")
            products = await cls._try_scrape(query, max_results, None, MAX_RETRY_ATTEMPTS + 1)
            if products:
                logger.info("✅ Successfully extracted products using direct connection fallback")
                return products

        logger.error(f"❌ All attempts failed for query: {query}")
        return []

    @classmethod
    async def _try_scrape(cls, query: str, max_results: int, proxy: dict | None, attempt: int) -> list[AmazonProduct]:
        """Single scrape attempt with given identity"""
        search_url = AMAZON_FR_SEARCH_URL.format(query=quote_plus(query))
        products = []

        try:
            context = await cls._create_context(cls._browser, proxy=proxy, attempt=attempt)
            page = await context.new_page()

            try:
                # CRITICAL: Load Amazon homepage FIRST in same context to establish session
                logger.info("🏠 Loading Amazon homepage to establish session/cookies...")
                await page.goto("https://www.amazon.fr", wait_until="networkidle", timeout=30000)
                logger.info("✅ Homepage loaded")

                # Handle homepage popups
                await cls._handle_popups(page)

                # Simulate human behavior on homepage
                await cls._simulate_human_behavior(page)

                # Small delay
                await asyncio.sleep(random.uniform(1.0, 3.0))

                # NOW interact with the search bar naturally
                try:
                    logger.info(f"⌨️ Typing search query: {query}")
                    search_input_selector = "#twotabsearchtextbox"

                    # Wait for input to be visible and editable
                    await page.wait_for_selector(search_input_selector, state="visible", timeout=10000)
                    search_input = page.locator(search_input_selector)

                    # Click and clear first
                    await search_input.click()
                    await search_input.fill("")

                    # Type slowly like a human
                    await search_input.type(query, delay=100)

                    await asyncio.sleep(random.uniform(0.5, 1.5))

                    # Click search button
                    submit_selector = "#nav-search-submit-button"
                    await page.wait_for_selector(submit_selector, state="visible", timeout=5000)
                    await page.click(submit_selector)

                    logger.info("🖱️ Clicked search button, waiting for results...")

                except Exception as e:
                    logger.warning(f"⚠️ Search bar interaction failed: {e}. Fallback to direct URL.")
                    # Fallback to direct navigation
                    logger.info(f"🔍 Navigating to search: {search_url}")
                    await page.goto(search_url, wait_until="domcontentloaded", timeout=60000)

                logger.info("Page loaded (domcontentloaded)")

                # Wait for content or block
                try:
                    await page.wait_for_selector(
                        'div[data-component-type="s-search-result"], .s-result-list', timeout=10000
                    )
                    logger.info("✅ Search results detected")

                    # CRITICAL: Wait for page to fully stabilize before extraction
                    # Amazon's JS may redirect after initial content loads
                    await asyncio.sleep(random.uniform(2.0, 4.0))

                    # Check if URL has changed (login redirect)
                    current_url = page.url
                    if "ap/signin" in current_url or "ap/register" in current_url:
                        logger.warning(f"⚠️ Redirected to login page: {current_url}")
                        return []

                    # Wait for network to be idle (no pending requests)
                    try:
                        await page.wait_for_load_state("networkidle", timeout=5000)
                    except Exception:
                        pass  # Timeout is acceptable, we just want to give it a chance

                    # Simulate more human behavior to appear natural
                    await cls._simulate_human_behavior(page)

                    # Another small delay before extraction
                    await asyncio.sleep(random.uniform(1.0, 2.0))

                except Exception:
                    logger.warning("🕒 Search results not found immediately, checking for blocks...")

                # Re-check URL before extraction
                current_url = page.url
                if "ap/signin" in current_url or "ap/register" in current_url:
                    logger.warning(f"⚠️ Redirected to login page before extraction: {current_url}")
                    return []

                # Get HTML
                html_content = await page.content()

                # Proactive block detection
                if (
                    "Type the characters you see in this image" in html_content
                    or "Saisissez les caractères que vous voyez" in html_content
                ):
                    logger.error("🚫 CAPTCHA / Bot detection triggered")
                    return []

                if "Identifiez-vous" in html_content and "commander" not in html_content:
                    logger.warning("⚠️ Redirected to login wall")
                    # Save screenshot for debugging
                    try:
                        debug_path = "/tmp/amazon_login_wall.png"
                        await page.screenshot(path=debug_path)
                        logger.info(f"📸 Saved debug screenshot to {debug_path}")
                    except Exception:
                        pass
                    return []

                logger.info(f"✅ Page content extracted ({len(html_content)} bytes)")

                if len(html_content) < 10000:
                    logger.error(f"❌ Page too small - likely blocked")
                    return []

                # Parse with BeautifulSoup
                soup = BeautifulSoup(html_content, "html.parser")

                # Find product cards
                product_cards = soup.find_all("div", {"data-component-type": "s-search-result"})

                if not product_cards:
                    # Try alternative
                    product_cards = soup.find_all("div", {"data-asin": True, "data-index": True})

                if not product_cards:
                    logger.warning("⚠️ No products found")
                    # Check for blocks
                    if "503" in html_content or "robot" in html_content.lower():
                        logger.error("🚫 Amazon blocked request")
                    return []

                logger.info(f"📦 Found {len(product_cards)} product cards")

                # Extract products
                for idx, card in enumerate(product_cards):
                    if len(products) >= max_results:
                        break

                    try:
                        product = cls._extract_product(card, idx)
                        if product:
                            products.append(product)
                            logger.debug(f"  ✓ [{len(products)}] {product.title[:50]}... - {product.price}€")
                    except Exception as e:
                        logger.error(f"Error parsing card {idx}: {e}")
                        continue

                logger.info(f"✅ Successfully extracted {len(products)} products")

            finally:
                await context.close()

        except Exception as e:
            logger.error(f"❌ Error during scraping: {e}", exc_info=True)
            return []

        return products

    @staticmethod
    def _extract_product(card, idx: int) -> AmazonProduct | None:
        """Extract product data from card"""
        # ASIN
        asin = card.get("data-asin", "")
        if not asin:
            logger.debug(f"  ⏭️ Card {idx}: No ASIN")
            return None

        # Sponsored
        sponsored = bool(card.select_one('[data-component-type="sp-sponsored-result"]'))

        # Title
        title = None
        for selector in ["h2 a span", "h2 span", "h2.s-line-clamp-2 span"]:
            elem = card.select_one(selector)
            if elem:
                title = elem.get_text(strip=True)
                if title:
                    break

        if not title:
            logger.debug(f"  ⏭️ Card {idx}: No title")
            return None

        # URL
        link_elem = card.select_one("h2 a") or card.select_one("a.s-link-style")
        if not link_elem:
            logger.debug(f"  ⏭️ Card {idx}: No link element")
            return None

        href = link_elem.get("href", "")

        # CRITICAL: Validate href is not empty or just '#'
        if not href or href == "#" or href.strip() == "":
            logger.warning(f"  ⏭️ Card {idx}: Invalid href '{href}' for {title[:30] if title else 'unknown'}")
            return None

        # Build absolute URL
        if href.startswith("/"):
            product_url = f"{AMAZON_FR_BASE_URL}{href}"
        elif href.startswith("http"):
            product_url = href
        else:
            logger.warning(
                f"  ⏭️ Card {idx}: Unexpected href format '{href[:50]}' for {title[:30] if title else 'unknown'}"
            )
            return None

        logger.debug(f"  ✓ Card {idx}: URL = {product_url[:80]}...")

        # Price
        price = None
        for selector in [".a-price .a-offscreen", ".a-price-whole", "span.a-price span.a-offscreen"]:
            elem = card.select_one(selector)
            if elem:
                price = parse_amazon_price(elem.get_text(strip=True))
                if price:
                    break

        # Original price
        original_price = None
        elem = card.select_one(".a-price.a-text-price .a-offscreen")
        if elem:
            original_price = parse_amazon_price(elem.get_text(strip=True))

        # Rating
        rating = None
        for selector in ['[aria-label*="étoile"]', '[aria-label*="star"]']:
            elem = card.select_one(selector)
            if elem:
                rating = parse_rating(elem.get("aria-label", ""))
                if rating:
                    break

        # Reviews
        reviews_count = None
        for selector in ['[aria-label*="étoile"] + span', "span.s-underline-text"]:
            elem = card.select_one(selector)
            if elem:
                reviews_count = parse_reviews_count(elem.get_text(strip=True))
                if reviews_count:
                    break

        # Image
        image_url = None
        for selector in ["img.s-image", "img"]:
            elem = card.select_one(selector)
            if elem:
                image_url = elem.get("src") or elem.get("data-src")
                if image_url:
                    break

        # Prime
        prime = bool(card.select_one('[aria-label*="Prime"]') or card.select_one("i.a-icon-prime"))

        # Stock
        in_stock = True
        if card.select_one('[aria-label*="Indisponible"]'):
            in_stock = False

        return AmazonProduct(
            title=title,
            url=product_url,
            price=price,
            original_price=original_price,
            rating=rating,
            reviews_count=reviews_count,
            image_url=image_url,
            in_stock=in_stock,
            prime=prime,
            sponsored=sponsored,
        )


# Global instance
amazon_scraper_service = AmazonScraperService()
