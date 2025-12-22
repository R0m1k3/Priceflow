import asyncio
import logging
import sys
import os

# Identify workspace root
sys.path.append(os.getcwd())

# Mock Env Vars
os.environ["DATABASE_URL"] = "postgresql://user:password@localhost:5432/pricewatch"
os.environ["BROWSERLESS_URL"] = "ws://localhost:3012"  # Ignored by patch, but good for completeness

from app.services.improved_search_service import ImprovedSearchService
from playwright.async_api import async_playwright

# Setup logging
logging.basicConfig(level=logging.DEBUG)  # DEBUG level to see price extraction logic
logger = logging.getLogger(__name__)


# Monkey patch _connect_browser to use local launch
async def _connect_browser_local(p):
    logger.info("Launching local browser (headless)...")
    return await p.chromium.launch(headless=True)


ImprovedSearchService._connect_browser = _connect_browser_local


async def test_search():
    await ImprovedSearchService.initialize()

    query = "nintendo switch"
    target_site = "stokomani.fr"

    print(f"Searching for: {query} on {target_site}")

    async for result in ImprovedSearchService.search_site_generator(target_site, query):
        print(f"[{result.source}] {result.title}\n  -> Price: {result.price}€\n  -> URL: {result.url}")

    await ImprovedSearchService.shutdown()


if __name__ == "__main__":
    asyncio.run(test_search())
