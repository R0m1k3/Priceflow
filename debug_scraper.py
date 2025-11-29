import asyncio
import logging
import sys
import os

# Add project root to path
sys.path.append(os.getcwd())

from app.services.browserless_service import browserless_service
from app.core.search_config import SITE_CONFIGS

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def debug_site(site_key: str, query: str = "chaise"):
    print(f"--- Debugging {site_key} ---")
    config = SITE_CONFIGS.get(site_key)
    if not config:
        print(f"Site {site_key} not found in config")
        return

    search_url = config["search_url"].format(query=query)
    print(f"URL: {search_url}")
    
    print("Fetching content...")
    try:
        html, screenshot_path = await browserless_service.get_page_content(
            search_url,
            use_proxy=config.get("requires_proxy", False),
            wait_selector=config.get("wait_selector")
        )
        
        print(f"Screenshot saved to: {screenshot_path}")
        print(f"HTML length: {len(html)}")
        
        # Save HTML for inspection
        with open(f"debug_{site_key}.html", "w", encoding="utf-8") as f:
            f.write(html)
        print(f"HTML saved to debug_{site_key}.html")
        
        # Check if wait selector is present in HTML
        if config.get("wait_selector"):
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(html, "html.parser")
            found = soup.select(config["wait_selector"])
            print(f"Wait selector '{config['wait_selector']}' found: {len(found)} elements")
            
    except Exception as e:
        print(f"Error: {e}")

async def main():
    if len(sys.argv) < 2:
        print("Usage: python debug_scraper.py <site_key> [query]")
        return
    
    site_key = sys.argv[1]
    query = sys.argv[2] if len(sys.argv) > 2 else "chaise"
    
    await browserless_service.start()
    try:
        await debug_site(site_key, query)
    finally:
        await browserless_service.stop()

if __name__ == "__main__":
    asyncio.run(main())
