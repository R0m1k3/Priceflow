import asyncio
import logging
import sys
from bs4 import BeautifulSoup
from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig, CacheMode

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

BASE_URL = "https://www.cataloguemate.fr"

async def debug_catalog_list():
    """Debug the catalog list extraction"""
    # Test with Gifi
    slug = "gifi"
    url = f"{BASE_URL}/{slug}/"
    
    logger.info(f"--- DEBUGGING LIST: {url} ---")
    
    browser_config = BrowserConfig(headless=True)
    run_config = CrawlerRunConfig(
        cache_mode=CacheMode.BYPASS,
        wait_for_images=True,
    )
    
    async with AsyncWebCrawler(config=browser_config) as crawler:
        result = await crawler.arun(url=url, config=run_config)
        
        if not result.success:
            logger.error(f"Failed to fetch {url}: {result.error_message}")
            return None
            
        logger.info(f"Successfully fetched {url} ({len(result.html)} chars)")
        
        soup = BeautifulSoup(result.html, 'html.parser')
        
        # 1. Dump all links to see what we have
        links = soup.find_all('a', href=True)
        logger.info(f"Found {len(links)} links total")
        
        potential_catalogs = []
        
        for i, link in enumerate(links):
            href = link['href']
            text = link.get_text(strip=True)
            
            # Normalize
            if href.startswith(BASE_URL):
                href = href.replace(BASE_URL, "")
            
            # Log interesting links
            if slug in href or "catalogue" in href.lower():
                logger.info(f"Link {i}: {href} | Text: '{text}'")
                
                # Apply our filter logic to see if it passes
                if href.startswith(f"/{slug}/") and href != f"/{slug}/":
                    if not any(x in href for x in ["offres", "magasins", "rechercher"]):
                        potential_catalogs.append(href)
                        logger.info(f"  -> MATCHES FILTER!")
        
        logger.info(f"Total matching catalogs: {len(potential_catalogs)}")
        return potential_catalogs[0] if potential_catalogs else None

async def debug_catalog_page(catalog_rel_url):
    """Debug the catalog page extraction"""
    if not catalog_rel_url:
        logger.error("No catalog URL to debug")
        return

    full_url = f"{BASE_URL}{catalog_rel_url}"
    logger.info(f"\n--- DEBUGGING PAGE: {full_url} ---")
    
    browser_config = BrowserConfig(headless=True)
    run_config = CrawlerRunConfig(
        cache_mode=CacheMode.BYPASS,
        wait_for_images=True,
        delay_before_return_html=2.0 # Wait a bit more
    )
    
    async with AsyncWebCrawler(config=browser_config) as crawler:
        result = await crawler.arun(url=full_url, config=run_config)
        
        if not result.success:
            logger.error(f"Failed to fetch {full_url}")
            return
            
        soup = BeautifulSoup(result.html, 'html.parser')
        
        # 1. Dump all images
        images = soup.find_all('img')
        logger.info(f"Found {len(images)} images")
        
        for i, img in enumerate(images):
            src = img.get('src', '')
            width = img.get('width', '?')
            height = img.get('height', '?')
            alt = img.get('alt', '')
            
            # Filter noise
            if "logo" in src or "icon" in src:
                continue
                
            logger.info(f"Img {i}: {src} | {width}x{height} | Alt: {alt}")
            
            # Check our heuristic
            is_likely = any(k in src.lower() for k in ['page', 'flyer', 'catalog', 'upload', 'images'])
            if is_likely:
                logger.info("  -> LIKELY CATALOG IMAGE")

if __name__ == "__main__":
    async def main():
        cat_url = await debug_catalog_list()
        if cat_url:
            await debug_catalog_page(cat_url)
            
    asyncio.run(main())
