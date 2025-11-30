"""
Analyze Carrefour price extraction
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
    
    print("Loading Carrefour search...")
    await page.goto("https://www.carrefour.fr/s?q=chaise", wait_until="networkidle")
    
    content = await page.content()
    soup = BeautifulSoup(content, "html.parser")
    
    products = soup.select("article.product-list-card-plp-grid-new")
    print(f"Found {len(products)} products\n")
    
    for i, product in enumerate(products[:3]):
        print(f"=== Product {i+1} ===")
        
        # Title
        title_el = product.select_one("h3, h2, a")
        title = title_el.get_text(strip=True) if title_el else "N/A"
        print(f"Title: {title[:60]}")
        
        # Find all text with € symbol
        import re
        product_html = str(product)
        prices = re.findall(r'(\d+[.,]\d+)\s*€', product_html)
        print(f"Prices found in HTML: {prices}")
        
        # Look for price elements
        price_els = product.find_all(string=re.compile('€'))
        if price_els:
            print(f"Elements with €:")
            for el in price_els[:3]:
                print(f"  - {el.strip()[:50]}")
        
        print()
    
    await context.close()
    await browser.close()
    await playwright.stop()

if __name__ == "__main__":
    asyncio.run(main())
