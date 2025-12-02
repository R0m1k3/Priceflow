import asyncio
from playwright.async_api import async_playwright

async def main():
    async with async_playwright() as p:
        # Launch with headless=True to mimic server environment
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        )
        page = await context.new_page()
        
        # Try a product URL that might trigger the check
        url = "https://www.amazon.fr/dp/B07S58MPKW" 
        print(f"Navigating to {url}")
        
        try:
            await page.goto(url)
            await page.wait_for_timeout(5000)
            
            content = await page.content()
            
            if "Continuer les achats" in content:
                print("🚨 Popup detected!")
                with open("amazon_popup.html", "w", encoding="utf-8") as f:
                    f.write(content)
                await page.screenshot(path="amazon_popup.png")
                
                # Analyze the button
                print("Searching for button...")
                
                # Try various locators
                locators = [
                    "button", 
                    "input[type='submit']", 
                    "a.a-button-text",
                    "span.a-button-inner"
                ]
                
                for sel in locators:
                    elements = page.locator(sel)
                    count = await elements.count()
                    for i in range(count):
                        el = elements.nth(i)
                        if await el.is_visible():
                            txt = await el.inner_text()
                            val = await el.get_attribute("value") or ""
                            if "Continuer" in txt or "Continuer" in val:
                                print(f"✅ Found candidate: {sel}")
                                print(f"   Text: {txt}")
                                print(f"   Value: {val}")
                                print(f"   OuterHTML: {await el.evaluate('el => el.outerHTML')}")
            else:
                print("No popup detected. Page title:", await page.title())
                
        except Exception as e:
            print(f"Error: {e}")
            
        await browser.close()

if __name__ == "__main__":
    asyncio.run(main())
