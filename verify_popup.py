import asyncio
import logging
import sys
from app.services.browserless_service import browserless_service

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def verify_popups():
    # URL that was reported to have issues
    url = "https://www.bmstores.fr/363943-bougie-parfumee-avec-bijou-350g-senteurs-assorties"
    # Fallback to search if that product is gone
    fallback_url = "https://www.bmstores.fr/module/ambjolisearch/jolisearch?s=calendrier"
    
    logger.info(f"--- Testing Popup Handling on {url} ---")
    
    try:
        content, screenshot_path = await browserless_service.get_page_content(
            url,
            extract_text=False
        )
        
        logger.info(f"Screenshot saved to: {screenshot_path}")
        logger.info("Please inspect the screenshot to ensure no 'Stock Inconnu' or 'Calendrier' popups are visible.")
        
    except Exception as e:
        logger.error(f"Verification failed: {e}")
    finally:
        await browserless_service.shutdown()

if __name__ == "__main__":
    asyncio.run(verify_popups())
