import asyncio
import logging
import os
import re
from datetime import datetime
from unittest.mock import MagicMock

from playwright.async_api import async_playwright
from app.services.tracking_scraper_service import ScraperService

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def mock_connect_browser(p):
    logger.info("MOCK: Launching local browser instead of connecting to browserless")
    return await p.chromium.launch()

async def verify_fix():
    logger.info("Starting verification...")
    
    # Monkey-patch _connect_browser to use local browser
    ScraperService._connect_browser = mock_connect_browser
    
    # Ensure screenshots dir exists
    os.makedirs("screenshots", exist_ok=True)
    
    # Test Item ID 999
    item_id = 999
    url = "https://example.com"
    
    logger.info(f"Scraping item {item_id}...")
    
    # We expect this to fail scraping real content from example.com with specific selectors,
    # but we only care about the screenshot filename generation which happens at the end.
    # Actually, if scraping fails, it might return None, "" early.
    # checking tracking_scraper_service.py:
    # It has a try/except block.
    # If _navigate_and_wait works, it proceeds. example.com should load.
    # _take_screenshot is called at the end.
    
    # However, ScraperService.scrape_item returns (None, "") if exception occurs.
    # We need to make sure it doesn't crash before screenshot.
    # example.com is simple, so it should load.
    # It will try to click popups (won't find any), wait for selector (if provided).
    # If we don't provide selector, it calls _auto_detect_price.
    
    full_path, _ = await ScraperService.scrape_item(url=url, item_id=item_id)
    
    if full_path:
        logger.info(f"Screenshot path returned: {full_path}")
        
        # Verify format: item_{id}_{timestamp}.png
        # Check if it matches regex
        pattern = r"screenshots/item_999_\d+\.png"
        if re.match(pattern, full_path):
             logger.info("SUCCESS: Filename contains timestamp!")
        else:
             logger.error(f"FAILURE: Filename does not match pattern {pattern}")
             exit(1)
             
        # Clean up
        if os.path.exists(full_path):
            os.remove(full_path)
            logger.info("Cleaned up screenshot file")
            
    else:
        logger.error("FAILURE: Scraper returned None for path. Did navigation fail?")
        exit(1)

    await ScraperService.shutdown()

if __name__ == "__main__":
    asyncio.run(verify_fix())
