import asyncio
import logging
import sys
from playwright.async_api import async_playwright
from app.services.ai_price_extractor import AIPriceExtractor
from app.services.improved_search_service import ImprovedSearchService
from app.core.search_config import SITE_CONFIGS

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def verify_bm():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        
        # 1. Perform Search to get a product URL
        logger.info("--- Step 1: Searching for 'Chaise pliante pu creme' on B&M ---")
        # Use specific search to find the problematic product
        search_url = "https://bmstores.fr/module/ambjolisearch/jolisearch?s=Chaise+pliante+pu+creme"
        await page.goto(search_url)
        await page.wait_for_load_state("networkidle")
        
        # Take screenshot of search results
        await page.screenshot(path="bm_search_results.png")
        logger.info("Screenshot saved: bm_search_results.png")
        
        # Get first product link
        product_link = await page.get_attribute("a.thumbnail.product-thumbnail", "href")
        if not product_link:
            logger.error("No product found in search")
            return
            
        if not product_link.startswith("http"):
            product_link = "https://www.bmstores.fr" + product_link
            
        logger.info(f"Testing Product URL: {product_link}")
        
        # 2. Go to Product Page
        await page.goto(product_link)
        await page.wait_for_load_state("networkidle")
        await page.screenshot(path="bm_product_page.png")
        logger.info("Screenshot saved: bm_product_page.png")
        
        # 3. Dump HTML snippet (price area)
        content = await page.content()
        logger.info(f"HTML Content Length: {len(content)}")
        
        # Check for 12.95
        if "12,95" in content or "12.95" in content:
            logger.info("✅ Price 12.95 found in raw HTML")
        else:
            logger.warning("❌ Price 12.95 NOT found in raw HTML")
            
        # 4. Test JSON-LD
        logger.info("\n--- Step 2: Testing JSON-LD ---")
        json_ld_scripts = await page.query_selector_all('script[type="application/ld+json"]')
        for i, script in enumerate(json_ld_scripts):
            text = await script.inner_text()
            logger.info(f"JSON-LD #{i}: {text[:500]}...")
            
        # 5. Test CSS Selectors
        logger.info("\n--- Step 3: Testing CSS Selectors ---")
        selectors = [
            '.price-current', '.prix-actuel', '.sale-price', '.promo-price', 
            '.price', '[data-testid="price"]', '[itemprop="price"]', '.product-price',
            '.current-price-value'
        ]
        for sel in selectors:
            elements = await page.query_selector_all(sel)
            for el in elements:
                text = await el.inner_text()
                logger.info(f"Selector '{sel}': {text.strip()}")
                
        # 6. Test AI Extraction
        logger.info("\n--- Step 4: Testing AI Extraction (Gemma 3) ---")
        title = await page.title()
        
        # Ensure API key is available
        import os
        if not os.getenv("OPENROUTER_API_KEY"):
            logger.warning("OPENROUTER_API_KEY not set in env, AI might fail")
            
        ai_price = await AIPriceExtractor.extract_price(content, title)
        logger.info(f"AI Extracted Price: {ai_price}")
        
        await browser.close()

if __name__ == "__main__":
    asyncio.run(verify_bm())
