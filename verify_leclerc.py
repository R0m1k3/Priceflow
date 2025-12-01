import asyncio
import logging
from playwright.async_api import async_playwright

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def verify_leclerc():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        
        # 1. Perform Search
        logger.info("--- Step 1: Searching for 'Chaise' on E.Leclerc ---")
        search_url = "https://www.e.leclerc/recherche?q=Chaise"
        try:
            await page.goto(search_url, wait_until="domcontentloaded", timeout=30000)
            await page.wait_for_timeout(5000) # Wait for JS
        except Exception as e:
            logger.error(f"Navigation failed: {e}")
        
        # 2. Dump HTML
        content = await page.content()
        logger.info(f"HTML Content Length: {len(content)}")
        
        # 3. Analyze Classes
        classes = await page.evaluate("Array.from(document.querySelectorAll('*')).map(e => e.className).filter(c => c).join(' ')")
        logger.info(f"Classes found: {classes[:1000]}")
        
        # 4. Check for Product Selectors
        selectors = [
            "div[class*='product']",
            "article",
            ".product-card",
            ".c-product-card",
            "a[class*='product']"
        ]
        
        for sel in selectors:
            count = await page.locator(sel).count()
            if count > 0:
                logger.info(f"Selector '{sel}' found {count} elements")
                first_html = await page.locator(sel).first.evaluate("el => el.outerHTML")
                logger.info(f"First element HTML ({sel}): {first_html[:500]}...")
        
        await browser.close()

if __name__ == "__main__":
    asyncio.run(verify_leclerc())
