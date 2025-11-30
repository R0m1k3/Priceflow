"""
Amazon France Scraper - Using Browserless Service
Uses the existing browserless_service with Playwright for reliable scraping
"""

import logging
import random
import re
from typing import Any
from urllib.parse import quote_plus

from bs4 import BeautifulSoup
from pydantic import BaseModel, Field

from app.services.browserless_service import browserless_service

logger = logging.getLogger(__name__)

# Amazon France configuration
AMAZON_FR_BASE_URL = "https://www.amazon.fr"
AMAZON_FR_SEARCH_URL = "https://www.amazon.fr/s?k={query}"


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
    Scrape Amazon France search results using Browserless service.

    Args:
        query: Search query
        max_results: Maximum number of products to return (default 20)

    Returns:
        List of AmazonProduct objects
    """
    search_url = AMAZON_FR_SEARCH_URL.format(query=quote_plus(query))
    logger.info(f"🔍 Searching Amazon France: {query}")
    logger.info(f"📍 URL: {search_url}")

    products = []

    try:
        # STRATEGY: Load Amazon homepage FIRST to establish session/cookies
        # Then do the search - appears more human-like
        logger.info("🏠 Loading Amazon homepage first to establish session...")
        home_html, _ = await browserless_service.get_page_content(
            url="https://www.amazon.fr",
            use_proxy=False,
            wait_selector=None,
            extract_text=False
        )

        if not home_html or len(home_html) < 10000:
            logger.warning(f"⚠️ Homepage load failed ({len(home_html) if home_html else 0} bytes)")
        else:
            logger.info(f"✅ Homepage loaded ({len(home_html)} bytes) - cookies established")

        # Small delay to appear more human
        import asyncio
        await asyncio.sleep(2)

        # NOW do the search
        logger.info("🚀 Fetching search page with Browserless (NO PROXY)...")
        html_content, _ = await browserless_service.get_page_content(
            url=search_url,
            use_proxy=False,  # Try without proxy first
            wait_selector=None,  # Let it load naturally
            extract_text=False  # We want HTML for parsing
        )

        if not html_content or len(html_content) < 10000:
            logger.error(f"❌ Page too small ({len(html_content)} bytes) - likely blocked or empty")
            return []

        logger.info(f"✅ Page loaded successfully ({len(html_content)} bytes)")

        # Debug: Save HTML to file for inspection
        debug_file = f"/tmp/amazon_debug_{query[:20]}.html"
        try:
            with open(debug_file, 'w', encoding='utf-8') as f:
                f.write(html_content)
            logger.debug(f"📝 HTML saved to {debug_file} for debugging")
        except Exception as e:
            logger.debug(f"Could not save debug HTML: {e}")

        # Parse HTML with BeautifulSoup
        soup = BeautifulSoup(html_content, 'html.parser')

        # Amazon uses data-component-type="s-search-result" for product cards
        product_cards = soup.find_all('div', {'data-component-type': 's-search-result'})

        if not product_cards:
            logger.warning("⚠️ No products found with primary selector")
            # Try alternative selector
            product_cards = soup.find_all('div', {'data-asin': True, 'data-index': True})
            if product_cards:
                logger.info(f"✓ Found {len(product_cards)} cards with alternative selector")

        if not product_cards:
            logger.warning("⚠️ No products found - checking for CAPTCHA or blocks")
            # Check for CAPTCHA
            if 'captcha' in html_content.lower():
                logger.error("🚫 CAPTCHA detected - Amazon blocked the request")
            elif 'robot' in html_content.lower() or 'bot' in html_content.lower():
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

                # Extract title - try multiple selectors
                title = None
                title_selectors = [
                    'h2 a span',
                    'h2 span',
                    'h2.s-line-clamp-2 span',
                    '.s-title-instructions-style span',
                ]
                for selector in title_selectors:
                    title_elem = card.select_one(selector)
                    if title_elem:
                        title = title_elem.get_text(strip=True)
                        if title:
                            break

                if not title:
                    logger.debug(f"  ⏭️ Card {idx} ({asin}): No title found, skipping")
                    continue

                # Extract URL
                link_elem = card.select_one('h2 a')
                if not link_elem:
                    # Try alternative
                    link_elem = card.select_one('a.s-link-style')
                if not link_elem:
                    logger.debug(f"  ⏭️ Card {idx} ({asin}): No link found, skipping")
                    continue

                href = link_elem.get('href', '')
                product_url = f"{AMAZON_FR_BASE_URL}{href}" if href.startswith('/') else href

                # Extract price
                price = None
                original_price = None

                # Current price - try multiple selectors
                price_selectors = [
                    '.a-price .a-offscreen',
                    '.a-price-whole',
                    'span.a-price span.a-offscreen',
                ]
                for selector in price_selectors:
                    price_elem = card.select_one(selector)
                    if price_elem:
                        price_text = price_elem.get_text(strip=True)
                        price = parse_amazon_price(price_text)
                        if price:
                            break

                # Original price (if discounted)
                original_price_elem = card.select_one('.a-price.a-text-price .a-offscreen')
                if original_price_elem:
                    original_price = parse_amazon_price(original_price_elem.get_text(strip=True))

                # Extract rating
                rating = None
                rating_selectors = [
                    '[aria-label*="étoile"]',
                    '[aria-label*="star"]',
                    'i.a-icon-star-small span',
                ]
                for selector in rating_selectors:
                    rating_elem = card.select_one(selector)
                    if rating_elem:
                        aria_label = rating_elem.get('aria-label', '')
                        if aria_label:
                            rating = parse_rating(aria_label)
                            if rating:
                                break

                # Extract reviews count
                reviews_count = None
                reviews_selectors = [
                    '[aria-label*="étoile"] + span',
                    '[aria-label*="star"] + span',
                    'span.s-underline-text',
                ]
                for selector in reviews_selectors:
                    reviews_elem = card.select_one(selector)
                    if reviews_elem:
                        reviews_count = parse_reviews_count(reviews_elem.get_text(strip=True))
                        if reviews_count:
                            break

                # Extract image
                image_url = None
                img_selectors = [
                    'img.s-image',
                    'img[data-image-latency="s-product-image"]',
                    'img',
                ]
                for selector in img_selectors:
                    img_elem = card.select_one(selector)
                    if img_elem:
                        image_url = img_elem.get('src') or img_elem.get('data-src')
                        if image_url:
                            break

                # Check Prime eligibility
                prime = bool(card.select_one('[aria-label*="Prime"]') or card.select_one('i.a-icon-prime'))

                # Check availability
                in_stock = True
                unavailable_elem = card.select_one('[aria-label*="Indisponible"]') or card.select_one('[aria-label*="Unavailable"]')
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
                logger.debug(f"  ✓ [{len(products)}] {title[:50]}... - {price}€")

            except Exception as e:
                logger.error(f"❌ Error parsing product card {idx}: {e}")
                continue

        logger.info(f"✅ Successfully extracted {len(products)} products")

    except Exception as e:
        logger.error(f"❌ Error during Amazon scraping: {e}", exc_info=True)
        return []

    return products


# ============================================================================
# TESTING
# ============================================================================

async def test_amazon_scraper():
    """Test the Amazon scraper with a simple query"""
    logger.info("=" * 60)
    logger.info("Testing Amazon France Scraper (Browserless)")
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
