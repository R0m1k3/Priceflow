"""
Detailed analysis of Centrakor image structure
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
    
    print(f"Analyzing {min(5, len(products))} products:\n")
    
    for i, product in enumerate(products[:5]):
        print(f"=== Product {i+1} ===")
        
        # Title
        title_el = product.select_one("a.product-item__name")
        title = title_el.get_text(strip=True) if title_el else "N/A"
        print(f"Title: {title}")
        
        # All images
        images = product.find_all('img')
        print(f"Found {len(images)} img tags")
        
        for j, img in enumerate(images):
            print(f"\n  Image {j+1}:")
            print(f"    tag: {img.name}")
            print(f"    class: {img.get('class')}")
            for attr in ['src', 'data-src', 'data-lazy-src', 'srcset', 'data-srcset']:
                val = img.get(attr)
                if val:
                    print(f"    {attr}: {val[:80]}")
        
        print()
    
    await context.close()
    await browser.close()
    await playwright.stop()

if __name__ == "__main__":
    asyncio.run(main())
