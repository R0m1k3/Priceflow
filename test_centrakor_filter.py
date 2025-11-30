"""
Test detailed logging for Centrakor image extraction
"""
import asyncio
import sys
sys.path.insert(0, '/app')

from playwright.async_api import async_playwright
from bs4 import BeautifulSoup
import re

async def main():
    playwright = await async_playwright().start()
    browser = await playwright.chromium.connect_over_cdp("ws://browserless:3000")
    
    context = await browser.new_context(
        viewport={"width": 1920, "height": 1080},
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    )
    
    page = await context.new_page()
    
    await page.goto("https://www.centrakor.com/search/chaise", wait_until="networkidle")
    content = await page.content()
    
    soup = BeautifulSoup(content, "html.parser")
    products = soup.select("div.product-item")
    
    print(f"Testing first product:\n")
    
    first = products[0]
    
    # Get all images
    img_els = first.select("img.responsive-image__actual")
    print(f"Found {len(img_els)} images with selector")
    
    for i, img_el in enumerate(img_els):
        print(f"\n=== Image {i+1} ===")
        candidate_url = img_el.get("src")
        print(f"URL: {candidate_url}")
        
        # Test filters
        if any(keyword in candidate_url.lower() for keyword in ['picto', 'icon', 'logo', 'badge']):
            print("  ❌ Filtered: Contains picto/icon/logo/badge keyword")
            continue
        
        width_match = re.search(r'width=(\d+)', candidate_url)
        height_match = re.search(r'height=(\d+)', candidate_url)
        print(f"  Width match: {width_match.group(1) if width_match else None}")
        print(f"  Height match: {height_match.group(1) if height_match else None}")
        
        if width_match and height_match:
            width = int(width_match.group(1))
            height = int(height_match.group(1))
            print(f"  Dimensions: {width}x{height}")
            if width < 100 and height < 100:
                print(f"  ❌ Filtered: Too small ({width}x{height})")
                continue
            else:
                print(f"  ✅ PASS: Large enough ({width}x{height})")
        else:
            print("  ✅ PASS: No dimensions in URL")
    
    await context.close()
    await browser.close()
    await playwright.stop()

if __name__ == "__main__":
    asyncio.run(main())
