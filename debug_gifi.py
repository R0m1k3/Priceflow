import asyncio
import logging
from playwright.async_api import async_playwright

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def debug_gifi():
    url = "https://www.gifi.fr/catalogsearch/result/?q=lutin"
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        
        logger.info(f"Navigating to {url}...")
        await page.goto(url, timeout=60000)
        
        # Wait for results
        try:
            await page.wait_for_selector(".products-grid, .product-items, .search-results, .products", timeout=10000)
            logger.info("Results container found.")
        except:
            logger.warning("Results container NOT found (timeout).")
            
        # Get all links matching the current selector
        selector = ".product-item a.product-item-link, .product-item-info a, .product-item a, .products-grid a, a[href$='.html']"
        
        # Let's try to be more specific and see what we get with different parts of the selector
        
        # 1. Current full selector
        elements = await page.query_selector_all(selector)
        logger.info(f"Found {len(elements)} elements with current selector.")
        
        for i, el in enumerate(elements[:10]):
            href = await el.get_attribute("href")
            text = await el.inner_text()
            logger.info(f"Link {i}: {href} | Text: {text.strip()[:50]}")

        # 2. Try to find product specific classes
        logger.info("--- Inspecting specific product classes ---")
        product_items = await page.query_selector_all(".product-item")
        logger.info(f"Found {len(product_items)} .product-item elements")
        
        if product_items:
            first_item = product_items[0]
            html = await first_item.inner_html()
            logger.info(f"First product item HTML snippet: {html[:500]}")

        await browser.close()

if __name__ == "__main__":
    asyncio.run(debug_gifi())
