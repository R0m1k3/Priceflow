import asyncio
import logging
import os
import re
import sys
from unittest.mock import MagicMock, AsyncMock

# Add current directory to sys.path to allow importing app
sys.path.append(os.getcwd())

# Mock playwright before importing app
mock_playwright = MagicMock()
sys.modules["playwright"] = mock_playwright
sys.modules["playwright.async_api"] = mock_playwright

from app.services.tracking_scraper_service import ScraperService

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def verify_logic():
    logger.info("Starting logic verification...")
    
    # Mock Page object
    mock_page = MagicMock()
    mock_page.screenshot = AsyncMock()
    
    item_id = 123
    url = "http://test.com"
    
    # Call _take_screenshot directly
    logger.info("Calling _take_screenshot...")
    filename = await ScraperService._take_screenshot(mock_page, url, item_id)
    
    logger.info(f"Returned filename: {filename}")
    
    # Verify format
    pattern = r"screenshots/item_123_\d+\.png"
    if re.match(pattern, filename):
        logger.info("SUCCESS: Filename matches expected timestamp pattern!")
        print("VERIFICATION_SUCCESS")
    else:
        logger.error(f"FAILURE: Filename {filename} does not match pattern {pattern}")
        exit(1)

if __name__ == "__main__":
    asyncio.run(verify_logic())
