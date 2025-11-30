"""
Amazon Scraper Service - Using persistent browser connection
Based on ScraperService pattern for better session management and anti-detection
"""

import asyncio
import logging
import os
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

# Cookie/popup selectors for Amazon
AMAZON_POPUP_SELECTORS = [
    "#sp-cc-accept",  # Cookie banner
    "#sp-cc-rejectall-link",
    "button[data-action='a-popover-close']",
    "[data-action='sp-cc-accept']",
    "input[aria-labelledby='sp-cc-accept-label']",
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

    cleaned = price_text.strip().replace('€', '').replace('EUR', '').strip()
    cleaned = cleaned.replace(' ', '').replace('\xa0', '')
    cleaned = cleaned.replace(',', '.')

    match = re.search(r'(\d+\.?\d*)', cleaned)
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

    match = re.search(r'(\d+[,.]\d+)', rating_text)
    if match:
        try:
            return float(match.group(1).replace(',', '.'))
        except ValueError:
            return None
    return None


def parse_reviews_count(reviews_text: str) -> int | None:
    """Parse review count"""
    if not reviews_text:
        return None

    cleaned = re.sub(r'[^\d\s]', '', reviews_text)
    cleaned = cleaned.replace(' ', '').replace('\xa0', '')

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
    async def _create_context(browser: Browser) -> BrowserContext:
        """Create browser context with stealth settings"""
        context = await browser.new_context(
            viewport={"width": 1920, "height": 1080},
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/131.0.0.0 Safari/537.36"
            ),
            locale="fr-FR",
            timezone_id="Europe/Paris",
        )

        # Stealth mode
        await context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
            window.chrome = { runtime: {} };
        """)

        await context.route("**/*", lambda route: route.continue_())
        return context

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
    async def scrape_search(cls, query: str, max_results: int = 20) -> list[AmazonProduct]:
        """
        Scrape Amazon France search results

        Args:
            query: Search query
            max_results: Maximum products to return

        Returns:
            List of AmazonProduct objects
        """
        search_url = AMAZON_FR_SEARCH_URL.format(query=quote_plus(query))
        logger.info(f"🔍 Searching Amazon France: {query}")
        logger.info(f"📍 URL: {search_url}")

        # Ensure browser is connected
        if not await cls._ensure_browser_connected():
            logger.error("Failed to establish browser connection")
            return []

        products = []

        try:
            context = await cls._create_context(cls._browser)
            page = await context.new_page()

            try:
                # Navigate
                logger.info(f"Navigating to {search_url}")
                await page.goto(search_url, wait_until="domcontentloaded", timeout=60000)
                logger.info("Page loaded (domcontentloaded)")

                # Wait for network idle
                try:
                    await page.wait_for_load_state("networkidle", timeout=10000)
                    logger.info("Network idle reached")
                except PlaywrightTimeoutError:
                    logger.info("Network idle timed out (non-critical)")

                # Handle popups
                await cls._handle_popups(page)

                # Wait a bit for content
                await page.wait_for_timeout(2000)

                # Get HTML
                html_content = await page.content()
                logger.info(f"✅ Page content extracted ({len(html_content)} bytes)")

                if len(html_content) < 10000:
                    logger.error(f"❌ Page too small - likely blocked")
                    return []

                # Parse with BeautifulSoup
                soup = BeautifulSoup(html_content, 'html.parser')

                # Find product cards
                product_cards = soup.find_all('div', {'data-component-type': 's-search-result'})

                if not product_cards:
                    # Try alternative
                    product_cards = soup.find_all('div', {'data-asin': True, 'data-index': True})

                if not product_cards:
                    logger.warning("⚠️ No products found")
                    # Check for blocks
                    if '503' in html_content or 'robot' in html_content.lower():
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
        asin = card.get('data-asin', '')
        if not asin:
            logger.debug(f"  ⏭️ Card {idx}: No ASIN")
            return None

        # Sponsored
        sponsored = bool(card.select_one('[data-component-type="sp-sponsored-result"]'))

        # Title
        title = None
        for selector in ['h2 a span', 'h2 span', 'h2.s-line-clamp-2 span']:
            elem = card.select_one(selector)
            if elem:
                title = elem.get_text(strip=True)
                if title:
                    break

        if not title:
            logger.debug(f"  ⏭️ Card {idx}: No title")
            return None

        # URL
        link_elem = card.select_one('h2 a') or card.select_one('a.s-link-style')
        if not link_elem:
            logger.debug(f"  ⏭️ Card {idx}: No link")
            return None

        href = link_elem.get('href', '')
        product_url = f"{AMAZON_FR_BASE_URL}{href}" if href.startswith('/') else href

        # Price
        price = None
        for selector in ['.a-price .a-offscreen', '.a-price-whole', 'span.a-price span.a-offscreen']:
            elem = card.select_one(selector)
            if elem:
                price = parse_amazon_price(elem.get_text(strip=True))
                if price:
                    break

        # Original price
        original_price = None
        elem = card.select_one('.a-price.a-text-price .a-offscreen')
        if elem:
            original_price = parse_amazon_price(elem.get_text(strip=True))

        # Rating
        rating = None
        for selector in ['[aria-label*="étoile"]', '[aria-label*="star"]']:
            elem = card.select_one(selector)
            if elem:
                rating = parse_rating(elem.get('aria-label', ''))
                if rating:
                    break

        # Reviews
        reviews_count = None
        for selector in ['[aria-label*="étoile"] + span', 'span.s-underline-text']:
            elem = card.select_one(selector)
            if elem:
                reviews_count = parse_reviews_count(elem.get_text(strip=True))
                if reviews_count:
                    break

        # Image
        image_url = None
        for selector in ['img.s-image', 'img']:
            elem = card.select_one(selector)
            if elem:
                image_url = elem.get('src') or elem.get('data-src')
                if image_url:
                    break

        # Prime
        prime = bool(card.select_one('[aria-label*="Prime"]') or card.select_one('i.a-icon-prime'))

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
