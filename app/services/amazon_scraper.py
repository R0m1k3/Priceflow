"""
Amazon France Scraper Service - Powered by Crawl4AI
Anti-bot detection techniques:
- Realistic User-Agent rotation
- Complete HTTP headers mimicking real browsers
- Proxy rotation (10 residential proxies)
- Random delays between requests
- Browser fingerprint randomization
- Cookie persistence
- NetworkIdle waiting for complete page load
"""

import asyncio
import hashlib
import logging
import random
import re
from datetime import datetime
from typing import Any
from urllib.parse import quote_plus

from bs4 import BeautifulSoup
from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig, CacheMode
from pydantic import BaseModel, Field

from app.core.search_config import AMAZON_PROXY_LIST_RAW, USER_AGENT_POOL

logger = logging.getLogger(__name__)

# Amazon France configuration
AMAZON_FR_BASE_URL = "https://www.amazon.fr"
AMAZON_FR_SEARCH_URL = "https://www.amazon.fr/s?k={query}"

# Additional realistic User-Agents specifically for Amazon
AMAZON_USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:133.0) Gecko/20100101 Firefox/133.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Safari/605.1.15",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36 Edg/131.0.0.0",
]

# Realistic browser headers to avoid bot detection
def get_realistic_headers(user_agent: str) -> dict:
    """Generate realistic browser headers"""
    return {
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
        "Accept-Language": "fr-FR,fr;q=0.9,en-US;q=0.8,en;q=0.7",
        "Accept-Encoding": "gzip, deflate, br",
        "DNT": "1",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none",
        "Sec-Fetch-User": "?1",
        "Cache-Control": "max-age=0",
        "User-Agent": user_agent,
    }


def get_random_proxy() -> str | None:
    """
    Get a random proxy from the pool in Crawl4AI format.

    Returns:
        Proxy string in format: http://username:password@ip:port
    """
    if not AMAZON_PROXY_LIST_RAW:
        return None

    proxy_str = random.choice(AMAZON_PROXY_LIST_RAW)
    parts = proxy_str.split(":")

    if len(parts) == 4:
        ip = parts[0]
        port = parts[1]
        username = parts[2]
        password = parts[3]

        # Format: http://username:password@ip:port
        return f"http://{username}:{password}@{ip}:{port}"

    return None


async def random_delay(min_seconds: float = 1.5, max_seconds: float = 4.0):
    """Add random delay to mimic human behavior"""
    delay = random.uniform(min_seconds, max_seconds)
    logger.debug(f"Human-like delay: {delay:.2f}s")
    await asyncio.sleep(delay)


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
# PRICE PARSING HELPERS
# ============================================================================

def parse_amazon_price(price_text: str) -> float | None:
    """
    Parse Amazon price formats:
    - "12,99 €"
    - "12,99€"
    - "12.99 EUR"
    - "1 234,99 €"
    """
    if not price_text:
        return None

    # Remove currency symbols and extra spaces
    cleaned = price_text.strip().replace('€', '').replace('EUR', '').strip()

    # Remove thousands separators (space or dot in French format)
    cleaned = cleaned.replace(' ', '').replace('\xa0', '')  # \xa0 is non-breaking space

    # Replace comma with dot for decimal separator
    cleaned = cleaned.replace(',', '.')

    # Extract first number (in case of ranges like "12.99 - 15.99")
    match = re.search(r'(\d+\.?\d*)', cleaned)
    if match:
        try:
            return float(match.group(1))
        except ValueError:
            return None

    return None


def parse_rating(rating_text: str) -> float | None:
    """Parse rating like '4,5 sur 5 étoiles' or '4.5 out of 5 stars'"""
    if not rating_text:
        return None

    # Match patterns like "4,5" or "4.5"
    match = re.search(r'(\d+[,.]\d+)', rating_text)
    if match:
        try:
            return float(match.group(1).replace(',', '.'))
        except ValueError:
            return None

    return None


def parse_reviews_count(reviews_text: str) -> int | None:
    """Parse review count like '1 234' or '12,345'"""
    if not reviews_text:
        return None

    # Remove non-digit characters except spaces
    cleaned = re.sub(r'[^\d\s]', '', reviews_text)
    cleaned = cleaned.replace(' ', '').replace('\xa0', '')

    try:
        return int(cleaned)
    except ValueError:
        return None


# ============================================================================
# SCRAPING FUNCTIONS
# ============================================================================

async def scrape_amazon_search(query: str, max_results: int = 20) -> list[AmazonProduct]:
    """
    Scrape Amazon France search results for a given query.

    Anti-detection features:
    1. Random User-Agent from realistic pool
    2. Complete browser headers
    3. Random proxy from pool
    4. Random delays between operations
    5. Browser fingerprint randomization via Crawl4AI
    6. NetworkIdle waiting
    7. Cookie handling

    Args:
        query: Search query
        max_results: Maximum number of products to return (default 20)

    Returns:
        List of AmazonProduct objects
    """
    search_url = AMAZON_FR_SEARCH_URL.format(query=quote_plus(query))
    logger.info(f"🔍 Searching Amazon France: {query}")
    logger.info(f"📍 URL: {search_url}")

    # Select random User-Agent
    user_agent = random.choice(AMAZON_USER_AGENTS)
    logger.debug(f"🎭 User-Agent: {user_agent[:50]}...")

    # Select random proxy
    proxy = get_random_proxy()
    if proxy:
        # Extract just the IP for logging (hide credentials)
        proxy_parts = proxy.split('@')
        proxy_server = proxy_parts[1] if len(proxy_parts) > 1 else proxy
        logger.debug(f"🌐 Using proxy: {proxy_server}")
    else:
        logger.warning("⚠️ No proxy available - may face rate limiting")

    # Configure Crawl4AI browser with anti-detection
    browser_config = BrowserConfig(
        headless=True,
        verbose=False,
        user_agent=user_agent,
        proxy_config=proxy,  # Use proxy_config instead of deprecated proxy
        extra_args=[
            "--disable-blink-features=AutomationControlled",  # Disable automation detection
            "--disable-dev-shm-usage",
            "--no-sandbox",
            "--disable-gpu",
            "--disable-setuid-sandbox",
            "--disable-web-security",
            "--disable-features=IsolateOrigins,site-per-process",
            "--disable-infobars",
            "--window-size=1920,1080",
            "--start-maximized",
            # Randomize viewport
            f"--user-agent={user_agent}",
        ],
    )

    # Configure crawler behavior
    crawler_config = CrawlerRunConfig(
        cache_mode=CacheMode.BYPASS,  # Always fetch fresh data
        wait_for_images=True,
        process_iframes=False,
        remove_overlay_elements=True,  # Remove popups/modals
        wait_until="networkidle",  # Wait for all network requests
        delay_before_return_html=2.0,  # Extra wait for JS rendering
        page_timeout=30000,  # 30 seconds timeout
        # Accept cookies automatically
        js_code="""
        // Accept cookies if banner appears
        const cookieButton = document.querySelector('#sp-cc-accept, button[id*="accept"]');
        if (cookieButton) {
            cookieButton.click();
        }
        """,
    )

    products = []

    try:
        # Add human-like delay before request
        await random_delay(1.0, 2.5)

        async with AsyncWebCrawler(config=browser_config) as crawler:
            logger.info("🚀 Launching browser...")
            result = await crawler.arun(url=search_url, config=crawler_config)

            if not result.success:
                logger.error(f"❌ Crawl failed: {result.error_message}")
                return []

            logger.info(f"✅ Page loaded successfully ({len(result.html)} bytes)")

            # Parse HTML with BeautifulSoup
            soup = BeautifulSoup(result.html, 'html.parser')

            # Debug: Save HTML to file for inspection
            debug_file = f"/tmp/amazon_debug_{query[:20]}.html"
            try:
                with open(debug_file, 'w', encoding='utf-8') as f:
                    f.write(result.html)
                logger.debug(f"📝 HTML saved to {debug_file} for debugging")
            except Exception as e:
                logger.debug(f"Could not save debug HTML: {e}")

            # Amazon uses data-component-type="s-search-result" for product cards
            product_cards = soup.find_all('div', {'data-component-type': 's-search-result'})

            if not product_cards:
                logger.warning("⚠️ No products found - checking for CAPTCHA or blocks")
                # Check for CAPTCHA
                if 'captcha' in result.html.lower():
                    logger.error("🚫 CAPTCHA detected - Amazon blocked the request")
                elif 'robot' in result.html.lower() or 'bot' in result.html.lower():
                    logger.error("🤖 Bot detection triggered")
                else:
                    logger.warning("📦 Empty results - query may have no matches")
                return []

            logger.info(f"📦 Found {len(product_cards)} product cards")

            for idx, card in enumerate(product_cards):
                if len(products) >= max_results:
                    break

                try:
                    # Extract ASIN (Amazon Standard Identification Number)
                    asin = card.get('data-asin', '')
                    if not asin:
                        logger.debug(f"  ⏭️ Card {idx}: No ASIN found, skipping")
                        continue

                    logger.debug(f"  🔍 Card {idx}: Processing ASIN {asin}")

                    # Check if sponsored
                    sponsored = bool(card.select_one('[data-component-type="sp-sponsored-result"]'))

                    # Extract title
                    title_elem = card.select_one('h2 a span, h2 span')
                    if not title_elem:
                        logger.debug(f"  ⏭️ Card {idx} ({asin}): No title found, skipping")
                        continue
                    title = title_elem.get_text(strip=True)

                    # Extract URL
                    link_elem = card.select_one('h2 a')
                    if not link_elem:
                        logger.debug(f"  ⏭️ Card {idx} ({asin}): No link found, skipping")
                        continue
                    href = link_elem.get('href', '')
                    product_url = f"{AMAZON_FR_BASE_URL}{href}" if href.startswith('/') else href

                    # Extract price
                    price = None
                    original_price = None

                    # Current price
                    price_elem = card.select_one('.a-price .a-offscreen')
                    if price_elem:
                        price = parse_amazon_price(price_elem.get_text(strip=True))

                    # Original price (if discounted)
                    original_price_elem = card.select_one('.a-price.a-text-price .a-offscreen')
                    if original_price_elem:
                        original_price = parse_amazon_price(original_price_elem.get_text(strip=True))

                    # Extract rating
                    rating = None
                    rating_elem = card.select_one('[aria-label*="étoile"], [aria-label*="star"]')
                    if rating_elem:
                        rating = parse_rating(rating_elem.get('aria-label', ''))

                    # Extract reviews count
                    reviews_count = None
                    reviews_elem = card.select_one('[aria-label*="étoile"] + span, [aria-label*="star"] + span')
                    if reviews_elem:
                        reviews_count = parse_reviews_count(reviews_elem.get_text(strip=True))

                    # Extract image
                    image_url = None
                    img_elem = card.select_one('img.s-image')
                    if img_elem:
                        image_url = img_elem.get('src') or img_elem.get('data-src')

                    # Check Prime eligibility
                    prime = bool(card.select_one('[aria-label*="Prime"], i.a-icon-prime'))

                    # Check availability
                    in_stock = True
                    unavailable_elem = card.select_one('[aria-label*="Indisponible"], [aria-label*="Unavailable"]')
                    if unavailable_elem:
                        in_stock = False

                    product = AmazonProduct(
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

                    products.append(product)
                    logger.debug(f"  ✓ [{idx+1}] {title[:50]}... - {price}€")

                except Exception as e:
                    logger.error(f"❌ Error parsing product card {idx}: {e}")
                    continue

            logger.info(f"✅ Successfully extracted {len(products)} products")

    except Exception as e:
        logger.error(f"❌ Error during Amazon scraping: {e}", exc_info=True)
        return []

    return products


async def scrape_amazon_search_batched(
    query: str,
    max_results: int = 20,
    batch_size: int = 20
) -> list[AmazonProduct]:
    """
    Scrape Amazon with automatic pagination if needed.

    Note: For now, we just scrape the first page (20 results).
    Pagination can be added later if needed.

    Args:
        query: Search query
        max_results: Maximum total results (default 20)
        batch_size: Results per page (default 20)

    Returns:
        List of AmazonProduct objects
    """
    # For now, single page only
    return await scrape_amazon_search(query, max_results)


# ============================================================================
# TESTING / VERIFICATION
# ============================================================================

async def test_amazon_scraper():
    """Test the Amazon scraper with a simple query"""
    logger.info("=" * 60)
    logger.info("Testing Amazon France Scraper")
    logger.info("=" * 60)

    test_query = "aspirateur"
    products = await scrape_amazon_search(test_query, max_results=5)

    logger.info(f"\n📊 Results for '{test_query}':")
    logger.info(f"Found {len(products)} products\n")

    for idx, product in enumerate(products, 1):
        logger.info(f"{idx}. {product.title}")
        logger.info(f"   💰 Price: {product.price}€" + (f" (was {product.original_price}€)" if product.original_price else ""))
        logger.info(f"   ⭐ Rating: {product.rating}/5 ({product.reviews_count} reviews)" if product.rating else "   ⭐ No rating")
        logger.info(f"   🔗 {product.url}")
        logger.info(f"   {'✅ Prime' if product.prime else '📦 Standard'} | {'📢 Sponsored' if product.sponsored else '🔍 Organic'}")
        logger.info("")

    return products


if __name__ == "__main__":
    # Run test
    asyncio.run(test_amazon_scraper())
