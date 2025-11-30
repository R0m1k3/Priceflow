"""
Analyze Centrakor HTML structure for image selectors
"""
import asyncio
import sys
import re
sys.path.insert(0, '/app')

from playwright.async_api import async_playwright
from bs4 import BeautifulSoup

async def main():
    print("Connecting to browserless...")
    playwright = await async_playwright().start()
    browser = await playwright.chromium.connect_over_cdp("ws://browserless:3000")
    
    context = await browser.new_context(
        viewport={"width": 1920, "height": 1080},
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    )
    
    page = await context.new_page()
    
    print("Loading Centrakor search...")
    await page.goto("https://www.centrakor.com/search/chaise", wait_until="networkidle")
    
    content = await page.content()
    
    soup = BeautifulSoup(content, "html.parser")
    
    # Try to find product containers
    selectors = [
        "div.product-item",
        "div.product-card",
        "article",
        "div[class*='product']",
        "li[class*='product']"
    ]
    
    for selector in selectors:
        products = soup.select(selector)
        if products:
            print(f"\n✓ Found {len(products)} products with selector: {selector}")
            
            # Analyze first product
            first = products[0]
            print(f"\nFirst product HTML snippet:")
            print(str(first)[:500])
            print("\n...")
            
            # Find all images
            images = first.find_all('img')
            print(f"\nFound {len(images)} images in first product:")
            for i, img in enumerate(images):
                print(f"\n  Image {i+1}:")
                print(f"    Class: {img.get('class')}")
                print(f"    Src: {img.get('src', '')[:80]}")
                print(f"    Data-src: {img.get('data-src', '')[:80]}")
                print(f"    Alt: {img.get('alt', '')[:50]}")
            
            break
    
    await context.close()
    await browser.close()
    await playwright.stop()
    print("\nDone")

if __name__ == "__main__":
    asyncio.run(main())
