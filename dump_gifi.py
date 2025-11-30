"""
Script to dump Gifi HTML and analyze structure
"""
import asyncio
import sys
import os
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
    
    print("Loading Gifi search page...")
    await page.goto("https://www.gifi.fr/resultat-recherche?q=chaise", wait_until="domcontentloaded")
    
    # Wait for products
    try:
        await page.wait_for_selector("article.product-miniature", timeout=10000)
    except:
        pass
    
    # Save HTML
    content = await page.content()
    os.makedirs("/app/debug_dumps", exist_ok=True)
    with open("/app/debug_dumps/gifi_full.html", "w", encoding="utf-8") as f:
        f.write(content)
    
    print(f"HTML saved ({len(content)} bytes)")
    
    # Extract first product structure
    products = await page.query_selector_all("article.product-miniature")
    print(f"Found {len(products)} products")
    
    if products:
        first_html = await products[0].evaluate("el => el.outerHTML")
        with open("/app/debug_dumps/gifi_first_product.html", "w", encoding="utf-8") as f:
            f.write(first_html)
        print(f"First product HTML saved")
    
    await context.close()
    await browser.close()
    await playwright.stop()
    print("Done")

if __name__ == "__main__":
    asyncio.run(main())
