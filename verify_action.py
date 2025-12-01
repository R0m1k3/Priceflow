import asyncio
import logging
from playwright.async_api import async_playwright

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def verify_action():
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            proxy={
                "server": "http://142.111.48.253:7030",
                "username": "jasuwwjr",
                "password": "elbsx170nmnl"
            }
        )
        page = await browser.new_page()
        
        # 1. Perform Search
        logger.info("--- Step 1: Searching for 'Chaise' on Action ---")
        search_url = "https://www.action.com/fr-fr/search/?q=Chaise"
        await page.goto(search_url, wait_until="domcontentloaded")
        await page.wait_for_timeout(5000) # Wait for JS to load

        
        # 2. Dump HTML
        content = await page.content()
        logger.info(f"HTML Content Length: {len(content)}")
        
        # Save HTML to file for analysis (optional, but good for debugging)
        with open("action_search.html", "w", encoding="utf-8") as f:
            f.write(content)
            
        # 3. Try to find product containers
        # Common selectors to test
        selectors = [
            ".product-card",
            ".product-item",
            ".card",
            "div[class*='product']",
            "a[class*='product']"
        ]
        
        # Print all classes found
        classes = await page.evaluate("Array.from(document.querySelectorAll('*')).map(e => e.className).filter(c => c).join(' ')")
        logger.info(f"Classes found: {classes[:1000]}")
        
        # Check for specific text "Chaise" to see if results loaded
        if "Chaise" in content:
             logger.info("✅ 'Chaise' found in content")
        else:
             logger.warning("❌ 'Chaise' NOT found in content")

        for sel in selectors:
            count = await page.locator(sel).count()
            if count > 0:
                logger.info(f"Selector '{sel}' found {count} elements")
                # Print first element HTML
                first_html = await page.locator(sel).first.evaluate("el => el.outerHTML")
                logger.info(f"First element HTML ({sel}): {first_html[:500]}...")
        
        await browser.close()

if __name__ == "__main__":
    asyncio.run(verify_action())
