import asyncio
import logging
import re
import sys

# Mock logger
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# Fallback implementation of _fetch_with_fallback for standalone test
async def _fetch_with_fallback(url):
    # We need to install httpx for this to work
    try:
        import httpx

        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
        async with httpx.AsyncClient(verify=False, timeout=30.0) as client:
            response = await client.get(url, headers=headers)
            return response.text
    except ImportError:
        print("Please pip install httpx strict")
        return ""


async def scrape_catalog_pages_standalone(catalog_url: str):
    from bs4 import BeautifulSoup

    print(f"Scraping: {catalog_url}")
    html_content = await _fetch_with_fallback(catalog_url)

    if not html_content:
        print("Failed to fetch content")
        return []

    soup = BeautifulSoup(html_content, "html.parser")

    # --- COPIED LOGIC FROM cataloguemate_scraper.py ---
    main_image_url = None
    max_area = 0

    # Strategy 1: Look for specific container/class identified in browser inspection
    candidates = soup.select(".letaky-grid-preview img")

    # Strategy 2: Fallback to all images if specific container not found
    if not candidates:
        candidates = soup.find_all("img")

    print(f"Found {len(candidates)} candidates")

    for img in candidates:
        # Check multiple attributes for the real image URL
        src = img.get("src") or img.get("data-src") or img.get("data-original")

        if not src:
            continue

        # Skip common UI elements - refined list
        if any(
            x in src.lower()
            for x in [
                "logo",
                "icon",
                "facebook",
                "twitter",
                "instagram",
                "loader",
                "spinner",
                "market",
                "googleplay",
                "appstore",
            ]
        ):
            continue

        # Strong Signal: URL contains 'thumbor' or 'leafletscdns' (host for catalog images)
        is_thumbor = "thumbor" in src.lower() or "leafletscdns" in src.lower()

        # Calculate area if dimensions exist
        width = img.get("width")
        height = img.get("height")
        area = 0
        if width and height:
            try:
                area = int(width) * int(height)
            except:
                pass

        if is_thumbor:
            if area > max_area or (area == 0 and max_area == 0):
                max_area = area
                main_image_url = src
                print(f"Match (Thumbor): {src}")
        elif area > 50000:
            if area > max_area:
                max_area = area
                main_image_url = src
                print(f"Match (Size): {src}")

    return main_image_url


if __name__ == "__main__":
    url = "https://www.cataloguemate.fr/gifi/catalogue-du-mardi-16122025-61964/"
    result = asyncio.run(scrape_catalog_pages_standalone(url))
    print(f"FINAL RESULT: {result}")
