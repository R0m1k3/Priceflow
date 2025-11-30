"""
Deep analysis - compare products WITH images vs WITHOUT images
"""
import asyncio
import sys
sys.path.insert(0, '/app')

from playwright.async_api import async_playwright
from bs4 import BeautifulSoup

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
    
    print(f"Analyzing {len(products)} products for image patterns\n")
    
    for i, product in enumerate(products[:10]):
        # Get title
        title_el = product.select_one("a.product-item__name")
        title = title_el.get_text(strip=True) if title_el else f"Product {i+1}"
        
        # Get ALL images
        all_imgs = product.select("img.responsive-image__actual")
        
        print(f"\n=== {i+1}. {title[:50]} ===")
        print(f"Found {len(all_imgs)} images")
        
        for j, img in enumerate(all_imgs):
            src = img.get('src', '')
            print(f"  Image {j+1}: {src if src else '(no src)'}")
            if not src:
                # Check other attributes
                for attr in ['data-src', 'data-lazy-src', 'srcset']:
                    val = img.get(attr)
                    if val:
                        print(f"    {attr}: {val[:80]}")
    
    await context.close()
    await browser.close()
    await playwright.stop()

if __name__ == "__main__":
    asyncio.run(main())
