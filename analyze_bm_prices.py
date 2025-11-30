"""
Analyze B&M product page for price extraction
"""
import asyncio
import sys
import re
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
    
    # URL from the screenshot
    url = "https://www.bmstores.fr/products/chaise-haute-pliante-bois-492966"
    print(f"Loading: {url}\n")
    await page.goto(url, wait_until="networkidle")
    
    content = await page.content()
    soup = BeautifulSoup(content, "html.parser")
    
    # Find all elements with € symbol
    price_els = soup.find_all(string=re.compile('€'))
    print(f"Found {len(price_els)} elements with '€'\n")
    
    prices_found = {}
    for el in price_els[:30]:
        text = el.strip()
        if text and len(text) < 100:
            parent = el.find_parent()
            if parent:
                parent_class = parent.get('class', [])
                parent_class_str = ' '.join(parent_class) if isinstance(parent_class, list) else str(parent_class)
                
                # Extract price value
                price_match = re.search(r'(\d+[.,]\d+)\s*€', text)
                if price_match:
                    price_val = price_match.group(1)
                    key = f"{price_val}€ in .{parent_class_str[:50]}"
                    if key not in prices_found:
                        prices_found[key] = text
    
    print("Prices found:")
    for key, text in prices_found.items():
        print(f"  {key}: '{text}'")
    
    # Try common price selectors
    print("\nTrying specific selectors:")
    selectors = [
        ".price",
        "[class*='price']",
        "[data-price]",
        ".product-price",
        "span[class*='price']"
    ]
    
    for selector in selectors:
        try:
            els = soup.select(selector)
            if els:
                for el in els[:2]:
                    text = el.get_text(strip=True)
                    if '€' in text:
                        print(f"  {selector}: {text}")
        except:
            pass
    
    await context.close()
    await browser.close()
    await playwright.stop()

if __name__ == "__main__":
    asyncio.run(main())
