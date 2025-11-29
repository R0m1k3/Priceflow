import asyncio
import logging
import os
from playwright.async_api import async_playwright
from app.services.scraper_service import ScraperService

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def verify_fix():
    logger.info("Starting verification...")
    
    # Mock browserless URL if not set
    if not os.getenv("BROWSERLESS_URL"):
        os.environ["BROWSERLESS_URL"] = "ws://browserless:3000"

    playwright = await async_playwright().start()
    try:
        # Connect to browserless (or launch local if not available, but code expects connect)
        # For this test, we might need to mock the browser object if we can't actually connect
        # But let's try to just create a local browser for testing purposes if connect fails
        # Actually, the code expects a browser object.
        
        logger.info("Launching local browser for test...")
        browser = await playwright.chromium.launch()
        
        logger.info("Calling scrape_item with browser argument...")
        try:
            # We pass a dummy URL, we expect it might fail scraping but NOT raise TypeError
            await ScraperService.scrape_item(
                url="https://example.com",
                browser=browser,
                timeout=5000 # Short timeout
            )
            logger.info("SUCCESS: scrape_item accepted the browser argument!")
        except TypeError as e:
            logger.error(f"FAILURE: TypeError raised: {e}")
        except Exception as e:
            logger.info(f"Scraping failed as expected (network/etc), but argument was accepted: {e}")
            
        await browser.close()
        
    finally:
        await playwright.stop()

if __name__ == "__main__":
    asyncio.run(verify_fix())
