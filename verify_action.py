import asyncio
import logging
import sys
import os

# Add project root to path
sys.path.append(os.getcwd())

from app.services.direct_search_service import direct_search_service
from app.core.search_config import SITE_CONFIGS

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def verify_site(site_key):
    logger.info(f"Verifying {site_key}...")
    try:
        results = await direct_search_service.search_site(site_key, "chaise")
        if results:
            logger.info(f"✅ {site_key}: Found {len(results)} results")
            for i, res in enumerate(results[:3]):
                title = res.get('title', 'No Title')
                price = res.get('price', 'No Price')
                url = res.get('url', 'No URL')
                logger.info(f"  {i+1}. {title[:50]}... - {price} - {url[:50]}...")
        else:
            logger.error(f"❌ {site_key}: No results found")
    except Exception as e:
        logger.error(f"❌ {site_key}: Error - {e}")

async def main():
    await verify_site("action.com")

if __name__ == "__main__":
    asyncio.run(main())
