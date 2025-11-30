"""
Test extracting price from Gifi search page HTML
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
    
    print("Loading Gifi search...")
    await page.goto("https://www.gifi.fr/resultat-recherche?q=chaise", wait_until="networkidle")
    
    content = await page.content()
    
    soup = BeautifulSoup(content, "html.parser")
    products = soup.select("div.product-tile")
    
    print(f"Found {len(products)} products\n")
    
    for i, product in enumerate(products[:3]):
        print(f"\\n=== Product {i+1} ===")
        
        # Get title
        title_el = product.select_one("div.pdp-link a")
        title = title_el.get_text(strip=True) if title_el else "N/A"
        print(f"Title: {title}")
        
        # Try to find price in product HTML
        product_html = product.prettify()
        
        # Look for price patterns
        price_patterns = [
            r'(\d+)[,.](\d+)\s*€',  # 19,99 € or 19.99 €
            r'€\s*(\d+)[,.](\d+)',  # € 19,99
            r'(\d+)€(\d+)',         # 19€99
            r'"price"\s*:\s*"?(\d+\.?\d*)"?',  # JSON price
        ]
        
        for pattern in price_patterns:
            matches = re.findall(pattern, product_html)
            if matches:
                print(f"Pattern '{pattern}': {matches[:3]}")
        
        # Find all text with €
        euro_texts = product.find_all(string=re.compile('€'))
        if euro_texts:
            print(f"Texts with €:")
            for text in euro_texts[:5]:
                print(f"  - {text.strip()[:80]}")
    
    await context.close()
    await browser.close()
    await playwright.stop()
    print("\nDone")

if __name__ == "__main__":
    asyncio.run(main())
