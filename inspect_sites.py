import asyncio
import logging
from app.services.browserless_service import BrowserlessService
from app.core.search_config import SITE_CONFIGS

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def dump_site(site_key, query="chaise"):
    config = SITE_CONFIGS.get(site_key)
    if not config:
        logger.error(f"Site {site_key} not found in config")
        return

    search_url = config["search_url"].format(query=query)
    logger.info(f"Dumping {site_key} from {search_url}")

    try:
        content, _ = await BrowserlessService.get_page_content(
            search_url,
            wait_selector=config.get("wait_selector"),
            use_proxy=config.get("requires_proxy", False)
        )
        
        if content:
            filename = f"/app/{site_key}_dump.html"
            with open(filename, "w", encoding="utf-8") as f:
                f.write(content)
            logger.info(f"Successfully dumped to {filename}")
        else:
            logger.error(f"Failed to get content for {site_key}")
            
    except Exception as e:
        logger.error(f"Error dumping {site_key}: {e}")

async def main():
    await BrowserlessService.initialize()
    try:
        await dump_site("amazon.fr")
        await dump_site("stokomani.fr")
        # await dump_site("lincroyable.fr") # Already have this
    finally:
        await BrowserlessService.shutdown()

if __name__ == "__main__":
    asyncio.run(main())
