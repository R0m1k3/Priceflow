"""
Analyze B&M with longer wait and playwright evaluation
"""
import asyncio
import sys
sys.path.insert(0, '/app')

from playwright.async_api import async_playwright

async def main():
    playwright = await async_playwright().start()
    browser = await playwright.chromium.connect_over_cdp("ws://browserless:3000")
    
    context = await browser.new_context(
        viewport={"width": 1920, "height": 1080},
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    )
    
    page = await context.new_page()
    
    url = "https://www.bmstores.fr/products/chaise-haute-pliante-bois-492966"
    print(f"Loading: {url}\n")
    await page.goto(url, wait_until="networkidle")
    
    # Wait extra time for JS
    await page.wait_for_timeout(5000)
    
    # Look for elements containing price
    print("Searching for price elements...\n")
    
    # Try to find any text with €
    price_els = await page.query_selector_all("*:has-text('€')")
    print(f"Found {len(price_els)} elements with €\n")
    
    for i, el in enumerate(price_els[:10]):
        text = await el.inner_text()
        tag = await el.evaluate("el => el.tagName")
        classes = await el.evaluate("el => el.className")
        print(f"{i+1}. <{tag} class='{classes}'> {text[:100]}")
    
    # Screenshot for debugging
    await page.screenshot(path="/app/debug_dumps/bm_screenshot.png", full_page=True)
    print("\nScreenshot saved to /app/debug_dumps/bm_screenshot.png")
    
    await context.close()
    await browser.close()
    await playwright.stop()

if __name__ == "__main__":
    asyncio.run(main())
