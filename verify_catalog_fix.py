import asyncio
import logging
import sys
import os

# Identify workspace root
sys.path.append(os.getcwd())

from app.services.cataloguemate_scraper import scrape_catalog_pages

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def verify_scraper():
    # Gifi catalog URL from the browser session
    url = "https://www.cataloguemate.fr/gifi/catalogue-du-mardi-16122025-61964/"

    print(f"Verifying scraper on: {url}")

    pages = await scrape_catalog_pages(url)

    print(f"Found {len(pages)} pages.")

    if not pages:
        print("FAIL: No pages found.")
        return

    # check first page image
    first_img = pages[0]["image_url"]
    print(f"Page 1 Image: {first_img}")

    if "thumbor" in first_img or "leafletscdns" in first_img:
        print("SUCCESS: Image is a Thumbor/Leaflet URL.")
    elif "icon" in first_img or "logo" in first_img:
        print("FAIL: Image appears to be an icon/logo.")
    else:
        print(f"WARNING: Image URL is: {first_img}")


if __name__ == "__main__":
    asyncio.run(verify_scraper())
