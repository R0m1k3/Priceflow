import asyncio
import logging
import sys
# from bs4 import BeautifulSoup # Removed
from playwright.async_api import async_playwright

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

BASE_URL = "https://www.cataloguemate.fr"

async def debug_catalog_list():
    """Debug the catalog list extraction using Playwright directly"""
    slug = "gifi"
    url = f"{BASE_URL}/offres/paris/{slug}/"
    
    logger.info(f"--- DEBUGGING LIST: {url} ---")
    
    async with async_playwright() as p:
        # Use browserless or local depending on connection
        # For this script we use local headless for simplicity if browserless is not available, 
        # but since we are in the container we might need browserless. 
        # Let's try to simulate what browserless_service does but simplified.
        
        try:
           browser = await p.chromium.launch(headless=True) # Try local first
        except:
           logger.info("Local browser failed, trying browserless...")
           browser = await p.chromium.connect_over_cdp("ws://browserless:3000")

        context = await browser.new_context(
             user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
        )
        page = await context.new_page()
        
        logger.info(f"Navigating to {url}")
        await page.goto(url, wait_until="domcontentloaded")
        
        # Wait a bit
        await page.wait_for_timeout(2000)
        
        content = await page.content()
        # soup = BeautifulSoup(content, 'html.parser')
        
        # 1. Dump all links to see what we have
        # Use JS to extract links
        links_data = await page.evaluate("""
            () => {
                return Array.from(document.querySelectorAll('a[href]')).map(a => ({
                    href: a.getAttribute('href'),
                    text: a.innerText.trim()
                }));
            }
        """)
        
        logger.info(f"Found {len(links_data)} links total")
        
        potential_catalogs = []
        
        for i, link in enumerate(links_data):
            href = link['href']
            text = link['text']
            
            # Normalize
            if href.startswith(BASE_URL):
                href = href.replace(BASE_URL, "")
            
            # Log interesting links
            if slug in href or "catalogue" in href.lower():
                logger.info(f"Link {i}: {href} | Text: '{text}'")
                
                # Apply our filter logic to see if it passes
                if f"/{slug}/" in href:
                    if not any(x in href for x in ["/offres/", "/magasins/", "/rechercher/", "page="]):
                        # Check ID pattern
                        import re
                        if re.search(r'-\d+/?$', href) or "catalogue" in href.lower():
                            potential_catalogs.append(href)
                            logger.info(f"  -> MATCHES FILTER! (Found catalog)")
                        else:
                             logger.info(f"  -> Rejected (no ID/keyword)")
                    else:
                        logger.info(f"  -> Rejected (invalid pattern)")
        
        logger.info(f"Total matching catalogs: {len(potential_catalogs)}")
        
        await browser.close()
        return potential_catalogs[0] if potential_catalogs else None

if __name__ == "__main__":
    asyncio.run(debug_catalog_list())
