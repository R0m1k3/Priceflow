"""
Analyze a Carrefour product page for price selectors
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
    
    # Visit a Carrefour product page (from the screenshot)
    url = "https://www.carrefour.fr/p/chaise-pliante-44x45-7x79-cm-gris-carrefour-home-3245390032010"
    print(f"Loading: {url}")
    await page.goto(url, wait_until="networkidle")
    
    content = await page.content()
    soup = BeautifulSoup(content, "html.parser")
    
    # Find all elements with € symbol
    price_els = soup.find_all(string=re.compile('€'))
    print(f"\nFound {len(price_els)} elements with '€'")
    
    prices_found = set()
    for el in price_els[:20]:
        text = el.strip()
        if text and len(text) < 50:
            prices_found.add(text)
            parent = el.find_parent()
            print(f"  '{text}' in <{parent.name} class='{parent.get('class')}'>")
    
    # Try common price selectors
    selectors = [
        ".product-price",
        "[class*='price']",
        ".price",
        "span.price",
        "div.price",
        "[data-price]"
    ]
    
    print("\nTrying specific selectors:")
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
