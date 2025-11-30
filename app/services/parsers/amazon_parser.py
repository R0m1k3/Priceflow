"""
Amazon France Parser - Robust and specialized parser for Amazon.fr
Based on amazon_scraper_v2.py with proven selectors and logic
"""

from bs4 import BeautifulSoup

from .base_parser import BaseParser, ProductResult


class AmazonParser(BaseParser):
    """
    Specialized parser for Amazon France

    Features:
    - Multiple fallback selectors for each element
    - Sponsored product detection
    - Prime eligibility detection
    - Rating and reviews extraction
    - Original price detection (discounts)
    """

    def __init__(self):
        super().__init__(
            site_name="Amazon",
            base_url="https://www.amazon.fr"
        )

    def parse_search_results(self, html: str, query: str, search_url: str) -> list[ProductResult]:
        """
        Parse Amazon search results page

        Amazon uses data-component-type="s-search-result" for product cards
        """
        soup = BeautifulSoup(html, 'html.parser')
        products = []

        # Primary selector: data-component-type
        product_cards = soup.find_all('div', {'data-component-type': 's-search-result'})

        if not product_cards:
            self.logger.warning("No products with primary selector, trying alternative")
            # Alternative: data-asin
            product_cards = soup.find_all('div', {'data-asin': True, 'data-index': True})

        if not product_cards:
            # Check for blocks
            if 'captcha' in html.lower():
                self.logger.error("🚫 CAPTCHA detected")
            elif 'robot' in html.lower() or 'bot' in html.lower():
                self.logger.error("🤖 Bot detection triggered")
            else:
                self.logger.warning("📦 No results found")
            return []

        self.logger.info(f"Found {len(product_cards)} product cards on Amazon")

        for idx, card in enumerate(product_cards):
            try:
                product = self._parse_product_card(card)
                if product:
                    products.append(product)
            except Exception as e:
                self.logger.error(f"Error parsing card {idx}: {e}")
                continue

        return products

    def _parse_product_card(self, card) -> ProductResult | None:
        """Parse a single Amazon product card"""

        # Extract ASIN
        asin = card.get('data-asin', '')
        if not asin:
            return None

        # Check if sponsored
        sponsored = bool(card.select_one('[data-component-type="sp-sponsored-result"]'))

        # Extract title - multiple selectors
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
            return None

        # Extract URL
        link_elem = card.select_one('h2 a')
        if not link_elem:
            link_elem = card.select_one('a.s-link-style')
        if not link_elem:
            return None

        href = link_elem.get('href', '')
        product_url = self.make_absolute_url(href)

        # Extract price (current price)
        price = None
        price_selectors = [
            '.a-price .a-offscreen',
            '.a-price-whole',
            'span.a-price span.a-offscreen',
        ]
        for selector in price_selectors:
            price_elem = card.select_one(selector)
            if price_elem:
                price_text = price_elem.get_text(strip=True)
                price = self.parse_price_text(price_text)
                if price:
                    break

        # Extract original price (if discounted)
        original_price = None
        original_price_elem = card.select_one('.a-price.a-text-price .a-offscreen')
        if original_price_elem:
            original_price = self.parse_price_text(original_price_elem.get_text(strip=True))

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
                    rating = self.parse_rating_text(aria_label)
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
                reviews_count = self.parse_reviews_count_text(reviews_elem.get_text(strip=True))
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
                image_url = self._get_image_src(img_elem)
                if image_url:
                    break

        # Check Prime eligibility
        prime = bool(
            card.select_one('[aria-label*="Prime"]') or
            card.select_one('i.a-icon-prime')
        )

        # Check availability
        in_stock = True
        unavailable_elem = card.select_one('[aria-label*="Indisponible"]') or \
                          card.select_one('[aria-label*="Unavailable"]')
        if unavailable_elem:
            in_stock = False

        return ProductResult(
            title=title,
            url=product_url,
            source=self.site_name,
            price=price,
            original_price=original_price,
            currency="EUR",
            in_stock=in_stock,
            image_url=image_url,
            rating=rating,
            reviews_count=reviews_count,
            sponsored=sponsored,
            snippet=f"Prime: {'✓' if prime else '✗'} | {'Sponsored' if sponsored else 'Organic'}"
        )
