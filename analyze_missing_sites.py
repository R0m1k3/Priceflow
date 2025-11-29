"""
Script pour analyser les sélecteurs CSS des sites manquants
"""
import asyncio
from playwright.async_api import async_playwright

async def analyze_site(url: str, site_name: str):
    print(f"\n=== Analyse de {site_name} ===")
    print(f"URL: {url}")
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        page = await browser.new_page()
        
        try:
            await page.goto(url, wait_until="networkidle", timeout=30000)
            await page.wait_for_timeout(3000)
            
            # Try cookie banners
            cookie_selectors = [
                "button:has-text('Accepter')",
                "button:has-text('Tout accepter')",
                "#didomi-notice-agree-button",
                ".didomi-continue-without-agreeing"
            ]
            for selector in cookie_selectors:
                try:
                    await page.click(selector, timeout=2000)
                    print(f"✓ Cookie banner fermé: {selector}")
                    break
                except:
                    pass
            
            await page.wait_for_timeout(2000)
            
            # Save HTML
            html = await page.content()
            filename = f"{site_name.lower().replace(' ', '_')}_search.html"
            with open(filename, "w", encoding="utf-8") as f:
                f.write(html)
            print(f"✓ HTML sauvegardé: {filename}")
            
            # Take screenshot
            screenshot_path = f"{site_name.lower().replace(' ', '_')}_search.png"
            await page.screenshot(path=screenshot_path, full_page=True)
            print(f"✓ Screenshot: {screenshot_path}")
            
            # Test common product link selectors
            test_selectors = [
                "a.product-link",
                "a.product-name",
                "a[href*='/produit']",
                "a[href*='/product']",
                "a[href*='/p/']",
                ".product-title a",
                ".product-item a",
                "article a",
                "a.product",
                "a[itemprop='url']",
            ]
            
            print("\n--- Test de sélecteurs ---")
            for selector in test_selectors:
                try:
                    elements = await page.query_selector_all(selector)
                    if elements:
                        print(f"✓ {selector}: {len(elements)} éléments trouvés")
                        # Get first few hrefs
                        for i, elem in enumerate(elements[:3]):
                            href = await elem.get_attribute("href")
                            text = await elem.inner_text()
                            print(f"  [{i+1}] {text[:50]} -> {href}")
                except Exception as e:
                    pass
            
        except Exception as e:
            print(f"❌ Erreur: {e}")
        finally:
            await browser.close()

async def main():
    sites = [
        ("https://bmstores.fr/module/ambjolisearch/jolisearch?s=chaise", "BM"),
        ("https://www.centrakor.com/recherche?controller=search&s=chaise", "Centrakor"),
        ("https://www.lincroyable.fr/recherche?query=chaise", "L'Incroyable"),
    ]
    
    for url, name in sites:
        await analyze_site(url, name)
        await asyncio.sleep(2)

if __name__ == "__main__":
    asyncio.run(main())
