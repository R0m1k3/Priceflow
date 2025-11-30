"""
Improved Search Service - Using Persistent Browser Connection
Based on ScraperService pattern for better session management and reliability

UPDATED: Now uses modular, site-specific parsers for robust product extraction
"""

import asyncio
import logging
from typing import AsyncGenerator
from urllib.parse import quote_plus, urljoin

from bs4 import BeautifulSoup
from playwright.async_api import Browser, BrowserContext, Page, async_playwright
from playwright.async_api import TimeoutError as PlaywrightTimeoutError
from sqlalchemy.orm import Session

from app.core.search_config import SITE_CONFIGS, BROWSERLESS_URL
from app.models import SearchSite
from app.schemas import SearchProgress, SearchResultItem
from app.services.parsers import ParserFactory, ProductResult

logger = logging.getLogger(__name__)

# Common popup/cookie selectors
COMMON_POPUP_SELECTORS = [
    "#sp-cc-accept",  # Cookie banner
    "#onetrust-accept-btn-handler",  # OneTrust
    ".cookie-consent-accept",
    "[data-action='accept-cookies']",
    "button[id*='accept']",
    "button[class*='accept']",
]


class SearchResult:
    """Search result data class"""
    def __init__(
        self,
        url: str,
        title: str,
        snippet: str,
        source: str,
        price: float | None = None,
        currency: str = "EUR",
        in_stock: bool | None = None,
        image_url: str | None = None,
    ):
        self.url = url
        self.title = title
        self.snippet = snippet
        self.source = source
        self.price = price
        self.currency = currency
        self.in_stock = in_stock
        self.image_url = image_url

    def to_dict(self):
        return {
            "url": self.url,
            "title": self.title,
            "snippet": self.snippet,
            "source": self.source,
            "price": self.price,
            "currency": self.currency,
            "in_stock": self.in_stock,
            "image_url": self.image_url,
        }


class ImprovedSearchService:
    """Persistent browser service for e-commerce search scraping"""

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
            logger.info("Initializing ImprovedSearchService shared browser...")
            cls._playwright = await async_playwright().start()
            cls._browser = await cls._connect_browser(cls._playwright)
            logger.info("ImprovedSearchService initialized.")

    @classmethod
    async def shutdown(cls):
        """Shutdown shared browser"""
        async with cls._lock:
            if cls._browser:
                logger.info("Shutting down ImprovedSearchService...")
                await cls._browser.close()
                cls._browser = None
            if cls._playwright:
                await cls._playwright.stop()
                cls._playwright = None
            logger.info("ImprovedSearchService shutdown complete.")

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
        """Close common popups/cookies"""
        logger.debug("Handling popups...")
        for selector in COMMON_POPUP_SELECTORS:
            try:
                if await page.locator(selector).count() > 0:
                    logger.debug(f"Found popup: {selector}")
                    await page.locator(selector).first.click(timeout=2000)
                    await page.wait_for_timeout(500)
            except Exception:
                pass



    @staticmethod
    def _parse_results(html: str, site_key: str, base_url: str, query: str) -> list[SearchResult]:
        """
        DEPRECATED: Legacy parsing method - now using specialized parsers
        This method is kept for backward compatibility but should not be used
        """
        config = SITE_CONFIGS[site_key]
        soup = BeautifulSoup(html, "html.parser")
        results = []

        # Prepare query words for filtering
        query_words = [w.lower() for w in query.split() if len(w) > 2]

        # Select product links
        logger.debug(f"Parsing content for {site_key} (length: {len(html)}) with selector: {config['product_selector']}")
        links = soup.select(config["product_selector"])
        logger.debug(f"Found {len(links)} raw items for {site_key}")

        # Deduplicate links
        seen_urls = set()

        for item in links:
            # Keep reference to original container for image search
            container = item
            if site_key == "centrakor.com":
                logger.debug(f"  Processing Centrakor item: {item.name}, classes: {item.get('class')}")
            
            # If selector targets the container (div.product-card), we need to find the link inside
            if item.name != 'a':
                # Try to find the link using product_link_selector if available
                if "product_link_selector" in config:
                    found_link = item.select_one(config["product_link_selector"])
                    if found_link:
                        link = found_link
                    else:
                        # Fallback: find first 'a' tag
                        found_link = item.find('a')
                        if found_link:
                            link = found_link
                        else:
                            logger.debug(f"  ⚠️ No link found in container for {site_key}")
                            continue
                else:
                    # No link selector specified, try to find first 'a'
                    found_link = item.find('a')
                    if found_link:
                        link = found_link
                    else:
                        logger.debug(f"  ⚠️ No link found in container for {site_key}")
                        continue
            else:
                # Item is already a link
                link = item
            
            href = link.get("href")
            if not href:
                logger.debug(f"  ⚠️ No href in link for {site_key}")
                continue

            full_url = urljoin(base_url, href)

            # Basic cleanup
            if full_url in seen_urls:
                continue
            seen_urls.add(full_url)

            # Extract title
            title = link.get_text(strip=True)

            # If no text, check title attribute or nested image alt
            if not title:
                if link.get("title"):
                    title = link.get("title")
                else:
                    img = link.find("img")
                    if img and img.get("alt"):
                        title = img.get("alt")

            if not title or len(title) < 3:
                logger.debug(f"  ⚠️ Skipped item with empty/short title: '{title}'")
                continue

            # Extract Image URL - PRIORITIZE CONFIGURED SELECTOR
            image_url = None

            # PRIORITY 1: Use product_image_selector if configured (site-specific)
            if "product_image_selector" in config:
                # Search in the original container first - get ALL matches
                img_els = container.select(config["product_image_selector"])
                
                # Filter and find first valid image  
                for img_el in img_els:
                    # Try multiple attributes in order of priority
                    candidate_url = (
                        img_el.get("src") or
                        img_el.get("data-src") or
                        img_el.get("data-lazy-src") or
                        img_el.get("data-original")
                    )
                    
                    # Handle srcset (use first URL)
                    if not candidate_url and img_el.get("srcset"):
                        srcset = img_el.get("srcset")
                        candidate_url = srcset.split(",")[0].split()[0]
                    
                    # Skip invalid images (pictos, icons, etc.)
                    if candidate_url:
                        # SPECIAL: No filtering for Centrakor (debugging)
                        if site_key == "centrakor.com":
                            # Skip placeholders
                            if "placeholder" in candidate_url.lower():
                                logger.debug(f"  ⏭️ Skipping placeholder: {candidate_url[:50]}")
                                continue
                            # Filter only tiny pictos
                            if 'picto' in candidate_url.lower() and ('width=60' in candidate_url or 'height=80' in candidate_url):
                                logger.debug(f"  ⏭️ Skipping tiny picto: {candidate_url[:50]}")
                                continue
                            image_url = candidate_url
                            logger.debug(f"  🖼️ Centrakor image: {image_url[:70]}")
                            break
                        
                        # Normal filtering for other sites
                        # Filter out obvious pictos and small icons
                        if any(keyword in candidate_url.lower() for keyword in ['picto', 'icon', 'logo', 'badge']):
                            logger.debug(f"  ⏭️ Skipping picto/icon: {candidate_url[:50]}")
                            continue
                        # Filter out VERY small images (less than 100px)
                        import re
                        width_match = re.search(r'width=(\d+)', candidate_url)
                        height_match = re.search(r'height=(\d+)', candidate_url)
                        if width_match and height_match:
                            width = int(width_match.group(1))
                            height = int(height_match.group(1))
                            if width < 100 and height < 100:
                                logger.debug(f"  ⏭️ Skipping small image ({width}x{height}): {candidate_url[:50]}")
                                continue
                        
                        # This is a valid product image
                        image_url = candidate_url
                        logger.debug(f"  🖼️ Image found via product_image_selector: {image_url[:50]}...")
                        break

            # PRIORITY 2: Fallback - Look for any img directly in the link
            if not image_url:
                img = link.find("img")
                if img:
                    image_url = (
                        img.get("src") or
                        img.get("data-src") or
                        img.get("data-lazy-src") or
                        img.get("data-original")
                    )
                    
                    # Handle srcset
                    if not image_url and img.get("srcset"):
                        srcset = img.get("srcset")
                        image_url = srcset.split(",")[0].split()[0]
                    
                    if image_url:
                        logger.debug(f"  🖼️ Image found via link.find('img'): {image_url[:50]}...")

            # PRIORITY 3: Look for picture > source elements
            if not image_url:
                picture = link.find("picture")
                if picture:
                    source = picture.find("source")
                    if source and source.get("srcset"):
                        srcset = source.get("srcset")
                        image_url = srcset.split(",")[0].split()[0]
                    
                    if not image_url:
                        img_in_picture = picture.find("img")
                        if img_in_picture:
                            image_url = img_in_picture.get("src") or img_in_picture.get("data-src")
                    
                    if image_url:
                        logger.debug(f"  🖼️ Image found via <picture>: {image_url[:50]}...")

            # Clean up and validate image URL
            if image_url:
                # Remove data URIs, 1x1 pixels, placeholders
                if (image_url.startswith("data:") or 
                    "1x1" in image_url or 
                    "placeholder" in image_url.lower() or
                    image_url.strip() == ""):
                    logger.debug(f"  ⏭️ Skipping invalid image: {image_url[:50]}")
                    image_url = None
                elif not image_url.startswith("http"):
                    image_url = urljoin(base_url, image_url)
                    logger.debug(f"  🔗 Made image URL absolute: {image_url[:80]}...")
            
            if not image_url:
                logger.warning(f"  ⚠️ No image found for: {title[:50]}")

            # Extract price from search results for sites where product pages are unavailable
            product_price = None
            if site_key == "gifi.fr":
                # Gifi: Extract price from product tile HTML
                import re
                container_html = str(container)
                price_match = re.search(r'(\d+)[,.](\d+)\s*€', container_html)
                if price_match:
                    euros = int(price_match.group(1))
                    cents = int(price_match.group(2))
                    product_price = float(f"{euros}.{cents}")
                    logger.debug(f"  💰 Extracted price from search: {product_price}€")

            # Create result
            results.append(SearchResult(
                url=full_url,
                title=title,
                snippet=f"Product from {config['name']}",
                source=config["name"],
                price=product_price,  # Set price if extracted from search
                image_url=image_url
            ))

        logger.debug(f"Parsed {len(results)} results from HTML")
        return results

    @classmethod
    async def _scrape_item_details(cls, result: SearchResult, context: BrowserContext) -> SearchResult | None:
        """Scrape price and details for a single item using same context"""
        try:
            # SPECIAL CASE: L'Incroyable - Price is in the title
            if "lincroyable.fr" in result.url:
                import re
                # Extract price from title (e.g., "34€99" or "59€99")
                price_match = re.search(r'(\d+)€(\d+)', result.title)
                if price_match:
                    # Convert to float (e.g., "34€99" -> 34.99)
                    price_euros = int(price_match.group(1))
                    price_cents = int(price_match.group(2))
                    result.price = float(f"{price_euros}.{price_cents}")
                    
                    # Clean title by removing price
                    result.title = re.sub(r'\d+€\d+', '', result.title).strip()
                    logger.debug(f"L'Incroyable - Extracted price {result.price}€ from title")
                    
                    return result
            
            # SPECIAL CASE: Gifi - Price extracted from search, no need to visit page
            if "gifi.fr" in result.url and result.price is not None:
                logger.debug(f"Gifi - Price already extracted from search: {result.price}€")
                return result
            
            page = await context.new_page()
            try:
                logger.debug(f"Scraping details for: {result.title[:50]}...")

                # Navigate to product page
                await page.goto(result.url, wait_until="domcontentloaded", timeout=20000)

                # Wait for network idle
                try:
                    await page.wait_for_load_state("networkidle", timeout=5000)
                except PlaywrightTimeoutError:
                    pass

                # Handle popups
                await cls._handle_popups(page)

                # Wait for content
                await page.wait_for_timeout(1500)

                # Extract price using multiple selectors
                price = await cls._extract_price(page)
                result.price = price

                # Extract stock status
                in_stock = await cls._extract_stock_status(page)
                result.in_stock = in_stock

                # Keep original image URL from search page - don't replace with screenshot
                # (Screenshots would need to be served by FastAPI, and original images are already good)

                logger.debug(f"  ✓ {result.title[:40]}... - {price}€ - Stock: {in_stock}")
                return result

            finally:
                await page.close()

        except Exception as e:
            logger.error(f"Error scraping item details {result.url}: {e}")
            return result  # Return original result without price

    @staticmethod
    async def _extract_price(page: Page) -> float | None:
        """Extract price from product page using multiple selectors"""
        import re
        
        # PRIORITY 1: Selectors for sale/promotional prices (highest priority)
        sale_price_selectors = [
            '.price-current',
            '.prix-actuel',
            '.sale-price',
            '.promo-price',
            '[class*="promo"]',
            '[class*="sale"]',
            '[class*="discount"]',
        ]
        
        # PRIORITY 2: Standard price selectors
        price_selectors = [
            '.price',
            '[data-testid="price"]',
            '[itemprop="price"]',
            '.product-price',
            '.a-price .a-offscreen',
            '.a-price-whole',
            'span[class*="price"]',
        ]
        
        # Try sale prices first
        for selector in sale_price_selectors:
            try:
                elements = await page.query_selector_all(selector)
                for elem in elements:
                    # Skip if element is strikethrough (old price)
                    parent_html = await elem.evaluate('el => el.parentElement.outerHTML')
                    if 'text-decoration: line-through' in parent_html or 'text-decoration-line: line-through' in parent_html:
                        continue
                    
                    price_text = await elem.inner_text()
                    if price_text:
                        cleaned = price_text.strip().replace('€', '').replace('EUR', '').strip()
                        cleaned = cleaned.replace(' ', '').replace('\xa0', '').replace(',', '.')
                        
                        match = re.search(r'(\d+\.?\d*)', cleaned)
                        if match:
                            try:
                                price_val = float(match.group(1))
                                if 0.01 < price_val < 100000:
                                    logger.debug(f"Found sale price: {price_val}€ from {selector}")
                                    return price_val
                            except ValueError:
                                continue
            except Exception:
                continue
        
        # Fallback to standard price selectors
        for selector in price_selectors:
            try:
                elements = await page.query_selector_all(selector)
                for elem in elements:
                    # Skip if element is strikethrough (old price)
                    try:
                        parent_html = await elem.evaluate('el => el.parentElement.outerHTML')
                        if 'text-decoration: line-through' in parent_html or 'text-decoration-line: line-through' in parent_html:
                            continue
                    except:
                        pass
                    
                    price_text = await elem.inner_text()
                    if price_text:
                        cleaned = price_text.strip().replace('€', '').replace('EUR', '').strip()
                        cleaned = cleaned.replace(' ', '').replace('\xa0', '').replace(',', '.')
                        
                        match = re.search(r'(\d+\.?\d*)', cleaned)
                        if match:
                            try:
                                price_val = float(match.group(1))
                                if 0.01 < price_val < 100000:
                                    logger.debug(f"Found price: {price_val}€ from {selector}")
                                    return price_val
                            except ValueError:
                                continue
            except Exception:
                continue

        logger.debug("No price found")
        return None

    @staticmethod
    async def _extract_stock_status(page: Page) -> bool | None:
        """Extract stock status from product page"""
        # Check for out of stock indicators
        out_of_stock_texts = [
            "rupture de stock",
            "indisponible",
            "out of stock",
            "unavailable",
            "épuisé",
            "non disponible"
        ]

        try:
            page_text = await page.inner_text("body")
            page_text_lower = page_text.lower()

            for text in out_of_stock_texts:
                if text in page_text_lower:
                    logger.debug(f"Out of stock detected: '{text}'")
                    return False

            # If we find "add to cart" or similar, assume in stock
            add_to_cart_texts = ["ajouter au panier", "add to cart", "acheter", "buy now"]
            for text in add_to_cart_texts:
                if text in page_text_lower:
                    logger.debug(f"In stock detected: '{text}'")
                    return True

        except Exception as e:
            logger.debug(f"Stock check error: {e}")

        return None  # Unknown




    @classmethod
    async def search_site_generator(cls, site_key: str, query: str) -> AsyncGenerator[SearchResult, None]:
        """Search a single site and yield results as they are scraped"""
        config = SITE_CONFIGS.get(site_key)
        if not config:
            logger.error(f"Unknown site: {site_key}")
            return

        search_url = config["search_url"].format(query=quote_plus(query))
        logger.info(f"Searching {config['name']} at {search_url}")

        if not await cls._ensure_browser_connected():
            logger.error("Failed to connect to browser")
            return

        try:
            context = await cls._create_context(cls._browser)
            
            try:
                page = await context.new_page()
                
                # Navigate
                await page.goto(search_url, wait_until="domcontentloaded", timeout=30000)
                
                # Wait for selector
                wait_selector = config.get("wait_selector") or config.get("product_selector")
                try:
                    if wait_selector:
                        await page.wait_for_selector(wait_selector, timeout=10000)
                except Exception:
                    logger.warning(f"Timeout waiting for selector {wait_selector} on {site_key}")

                # Get content
                content = await page.content()
                await page.close() # Close search page to free resources
                
                # Parse results (Phase 1)
                base_url = search_url.split("/search")[0]
                if "amazon" in site_key:
                    base_url = "https://www.amazon.fr"
                    
                initial_results = cls._parse_results(content, site_key, base_url, query)
                
                if not initial_results:
                    logger.warning(f"No results found for {site_key}")
                    # Dump HTML for debugging
                    import os
                    dump_dir = "/app/debug_dumps"
                    os.makedirs(dump_dir, exist_ok=True)
                    dump_path = f"{dump_dir}/{site_key.replace('.', '_')}_no_results.html"
                    with open(dump_path, 'w', encoding='utf-8') as f:
                        f.write(content)
                    logger.warning(f"HTML dumped to {dump_path} for inspection")
                    return

                # Phase 2: Scrape details (Streaming)
                semaphore = asyncio.Semaphore(3)
                
                async def scrape_wrapper(res):
                    async with semaphore:
                        return await cls._scrape_item_details(res, context)

                tasks = [scrape_wrapper(r) for r in initial_results]
                
                for future in asyncio.as_completed(tasks):
                    enriched_res = await future
                    if enriched_res:
                        yield enriched_res

            finally:
                await context.close()

        except Exception as e:
            logger.error(f"Error searching {site_key}: {e}")

    @classmethod
    async def search_all(cls, query: str) -> list[SearchResult]:
        """Search all configured sites"""
        tasks = []
        for site_key in SITE_CONFIGS.keys():
            tasks.append(cls.search_site(site_key, query))

        results_list = await asyncio.gather(*tasks)
        all_results = []
        for r in results_list:
            all_results.extend(r)
        return all_results


# ==========================================
# COMPATIBILITY LAYER FOR API ROUTERS
# ==========================================

async def search_products(
    query: str,
    db: Session,
    site_ids: list[int] | None = None,
    max_results: int | None = None,
) -> AsyncGenerator[SearchProgress, None]:
    """
    Compatibility wrapper for search_products using improved service.
    Yields SearchProgress events incrementally.
    """
    # 1. Get sites to search
    sites = db.query(SearchSite).order_by(SearchSite.priority).all()
    if site_ids:
        sites = [s for s in sites if s.id in site_ids]

    active_sites = [s for s in sites if s.is_active]

    # Initial event
    yield SearchProgress(
        status="searching",
        total=len(active_sites),
        completed=0,
        message=f"Démarrage de la recherche sur {len(active_sites)} sites...",
        results=[],
    )

    # 2. Map DB sites to Config keys with improved matching
    site_keys = []
    for site in active_sites:
        matched_key = None
        
        # Normalize domain for comparison (remove www., lowercase, etc.)
        site_domain_normalized = site.domain.lower().replace("www.", "").replace("http://", "").replace("https://", "").strip("/")

        # Try multiple matching strategies:
        for key in SITE_CONFIGS.keys():
            key_normalized = key.lower().replace("www.", "")

            # 1. Exact match
            if site_domain_normalized == key_normalized:
                matched_key = key
                logger.info(f"✅ Mapped {site.name} ({site.domain}) → {key} (exact match)")
                break

            # 2. Contains match (one in the other)
            if key_normalized in site_domain_normalized or site_domain_normalized in key_normalized:
                matched_key = key
                logger.info(f"✅ Mapped {site.name} ({site.domain}) → {key} (contains)")
                break

            # 3. Normalize punctuation (. vs - vs nothing) and compare
            # e.leclerc → eleclerc, e-leclerc.com → eleclecrcom
            domain_no_punct = site_domain_normalized.replace("-", "").replace(".", "")
            key_no_punct = key_normalized.replace("-", "").replace(".", "")

            # Exact match without punctuation
            if domain_no_punct == key_no_punct:
                matched_key = key
                logger.info(f"✅ Mapped {site.name} ({site.domain}) → {key} (normalized punctuation)")
                break

            # Contains match without punctuation (handles .com, .fr suffixes)
            if len(domain_no_punct) > 3 and len(key_no_punct) > 3:
                if domain_no_punct in key_no_punct or key_no_punct in domain_no_punct:
                    matched_key = key
                    logger.info(f"✅ Mapped {site.name} ({site.domain}) → {key} (normalized contains)")
                    break
        
        if matched_key:
            site_keys.append(matched_key)
        else:
            logger.warning(f"❌ No config found for {site.name} (domain: {site.domain}, normalized: {site_domain_normalized})")

    # 3. Execute searches and stream results
    generators = [ImprovedSearchService.search_site_generator(key, query) for key in site_keys]

    queue = asyncio.Queue()
    active_producers = len(generators)

    # Limit concurrent sites
    site_semaphore = asyncio.Semaphore(2)

    async def producer(gen):
        async with site_semaphore:
            try:
                async for item in gen:
                    await queue.put(item)
            except Exception as e:
                logger.error(f"Error in search producer: {e}")
            finally:
                await queue.put(None)  # Sentinel

    # Start producers
    for gen in generators:
        asyncio.create_task(producer(gen))

    # Consumer loop
    results_so_far = []
    completed_sites = 0

    while active_producers > 0:
        item = await queue.get()

        if item is None:
            active_producers -= 1
            completed_sites += 1
            yield SearchProgress(
                status="searching",
                total=len(active_sites),
                completed=completed_sites,
                message=f"Recherche en cours... ({completed_sites}/{len(active_sites)} sites terminés)",
                results=results_so_far,
            )
        else:
            # Convert to SearchResultItem
            api_item = SearchResultItem(
                url=item.url,
                title=item.title,
                price=item.price,
                currency=item.currency,
                in_stock=item.in_stock,
                site_name=item.source,
                site_domain=item.source,
                image_url=item.image_url,
            )
            results_so_far.append(api_item)

            # Yield update with new result
            yield SearchProgress(
                status="searching",
                total=len(active_sites),
                completed=completed_sites,
                message=f"Trouvé: {item.title[:30]}...",
                results=results_so_far,
            )

    # Final event
    yield SearchProgress(
        status="completed",
        total=len(active_sites),
        completed=len(active_sites),
        message=f"Terminé. {len(results_so_far)} résultats trouvés.",
        results=results_so_far,
    )


# Global instance
improved_search_service = ImprovedSearchService()
