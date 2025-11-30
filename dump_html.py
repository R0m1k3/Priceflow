"""
Quick HTML Dumper - Saves raw HTML from search pages for manual analysis
"""
import asyncio
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from app.services.improved_search_service import ImprovedSearchService
from app.core.search_config import SITE_CONFIGS

async def dump_search_html(site_key: str, query: str = "chaise"):
    """Download and save raw HTML for manual inspection"""
    config = SITE_CONFIGS.get(site_key)
    if not config:
        print(f"❌ Site '{site_key}' not found")
        return
    
    print(f"\n🔍 Dumping HTML for: {config['name']}")
    
    # Ensure browser is initialized
    await ImprovedSearchService.initialize()
    
    # Create context manually to get HTML
    context = await ImprovedSearchService._create_context(ImprovedSearchService._browser)
    page = await context.new_page()
    
    try:
        search_url = config["search_url"].format(query=query)
        print(f"   URL: {search_url}")
        
        await page.goto(search_url, wait_until="networkidle", timeout=30000)
        await ImprovedSearchService._handle_popups(page)
        await page.wait_for_timeout(3000)
        
        html = await page.content()
        
        filename = f"dump_{site_key.replace('.', '_')}.html"
        with open(filename, "w", encoding="utf-8") as f:
            f.write(html)
        
        print(f"   ✅ Saved to: {filename} ({len(html)} bytes)")
        
        # Quick analysis
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html, "html.parser")
        
        # Try current selector
        current_selector = config.get("product_selector")
        matches = soup.select(current_selector)
        print(f"   📊 Current selector '{current_selector}' matches: {len(matches)}")
        
        # Try image selector
        if "product_image_selector" in config:
            img_selector = config["product_image_selector"]
            img_matches = soup.select(img_selector)
            print(f"   🖼️  Current image selector '{img_selector}' matches: {len(img_matches)}")
        
    finally:
        await context.close()

async def main():
    sites = [
        "e-leclerc.com",
        "auchan.fr",
        "carrefour.fr",
        "stokomani.fr",
        "centrakor.com",
        "cdiscount.com",
        "lincroyable.fr"
    ]
    
    for site_key in sites:
        try:
            await dump_search_html(site_key)
        except Exception as e:
            print(f"❌ Error: {e}")
        await asyncio.sleep(1)
    
    await ImprovedSearchService.shutdown()

if __name__ == "__main__":
    asyncio.run(main())
