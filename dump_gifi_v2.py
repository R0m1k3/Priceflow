"""
Dump Gifi with longer wait for JavaScript
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
    await page.goto("https://www.gifi.fr/resultat-recherche?q=chaise", wait_until="networkidle")
    
    # Wait for ANY content
    print("Waiting for content...")
    await page.wait_for_timeout(5000)
    
    # Save HTML
    content = await page.content()
    os.makedirs("/app/debug_dumps", exist_ok=True)
    with open("/app/debug_dumps/gifi_with_wait.html", "w", encoding="utf-8") as f:
        f.write(content)
    
    print(f"HTML saved ({len(content)} bytes)")
    
    # Find any elements with price
    price_els = await page.query_selector_all("*:has-text('€')")
    print(f"Elements with € symbol: {len(price_els)}")
    
    # Find all divs/articles
    all_divs = await page.query_selector_all("div, article, li")
    print(f"Total divs/articles/li: {len(all_divs)}")
    
    # Screenshot
    await page.screenshot(path="/app/debug_dumps/gifi_screenshot.png", full_page=True)
    print("Screenshot saved")
    
    # Get all classes
    all_classes = await page.evaluate("""() => {
        const elements = document.querySelectorAll('*');
        const classes = new Set();
        elements.forEach(el => {
            if (el.className && typeof el.className === 'string') {
                el.className.split(' ').forEach(cls => {
                    if (cls && (cls.includes('product') || cls.includes('item') || cls.includes('card'))) {
                        classes.add(cls);
                    }
                });
            }
        });
        return Array.from(classes);
    }""")
    
    print(f"\\nProduct-related classes found:")
    for cls in all_classes:
        print(f"  - {cls}")
    
    await context.close()
    await browser.close()
    await playwright.stop()
    print("Done")

if __name__ == "__main__":
    asyncio.run(main())
