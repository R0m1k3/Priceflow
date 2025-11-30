"""
Analyze a Gifi product page to understand price structure
"""
import asyncio
import sys
sys.path.insert(0, '/app')

from playwright.async_api import async_playwright

async def main():
    print("Connecting to browserless...")
    playwright = await async_playwright().start()
    browser = await playwright.chromium.connect_over_cdp("ws://browserless:3000")
    
    context = await browser.new_context(
        viewport={"width": 1920, "height": 1080},
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    )
    
    page = await context.new_page()
    
    # Visit a Gifi product page
    url = "https://www.gifi.fr/meuble-et-deco/linge-de-maison/coussin-plaid-et-tapis/housse-de-chaise-canape-ou-fauteuil/housse-de-chaise-uni-blanc/000000000000410028.html"
    print(f"Loading: {url}")
    await page.goto(url, wait_until="networkidle")
    
    # Get page title
    title = await page.title()
    print(f"Title: {title}")
    
    # Find all elements with price-like text
    price_els = await page.query_selector_all("*:has-text('€')")
    print(f"\nFound {len(price_els)} elements with '€'")
    
    # Get first 10 price elements
    for i, el in enumerate(price_els[:10]):
        text = await el.inner_text()
        tag = await el.evaluate("el => el.tagName")
        classes = await el.evaluate("el => el.className")
        print(f"{i+1}. <{tag} class='{classes}'> {text[:50]}")
    
    # Try specific selectors
    selectors = [
        ".price",
        ".product-price",
        "[class*='price']",
        "[data-price]",
        "span.price",
        "div.price"
    ]
    
    print("\nTrying specific selectors:")
    for selector in selectors:
        try:
            els = await page.query_selector_all(selector)
            if els:
                for el in els[:2]:
                    text = await el.inner_text()
                    print(f"  {selector}: {text}")
        except:
            pass
    
    await context.close()
    await browser.close()
    await playwright.stop()
    print("\nDone")

if __name__ == "__main__":
    asyncio.run(main())
