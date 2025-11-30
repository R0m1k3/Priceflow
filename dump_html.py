"""
Quick HTML Dumper - Saves raw HTML from search pages for manual analysis
"""
import asyncio
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from app.services.browserless_service import browserless_service
from app.core.search_config import SITE_CONFIGS

async def dump_search_html(site_key: str, query: str = "chaise"):
    """Download and save raw HTML for manual inspection"""
    config = SITE_CONFIGS.get(site_key)
    if not config:
        print(f"❌ Site '{site_key}' not found")
        return
    
    print(f"\n🔍 Dumping HTML for: {config['name']}")
    
    # Ensure browser is initialized
    await browserless_service.initialize()
    
    try:
        search_url = config["search_url"].format(query=query)
        print(f"   URL: {search_url}")
        
        # Override wait_selector for La Foir'Fouille
        wait_selector = config.get("wait_selector")
        if site_key == "lafoirfouille.fr":
            wait_selector = ".sf-grid-vignet"
            print(f"   ⚠️  Overriding wait_selector to: {wait_selector}")
        
        html_content, screenshot_path = await browserless_service.get_page_content(
            search_url,
            wait_selector=wait_selector,
            use_proxy=config.get("requires_proxy", False)
        )
        
        if not html_content:
            print("   ❌ No HTML content returned")
            return

        filename = f"dump_{site_key.replace('.', '_')}.html"
        with open(filename, "w", encoding="utf-8") as f:
            f.write(html_content)
        
        print(f"   ✅ Saved to: {filename} ({len(html_content)} bytes)")
        
        # Quick analysis
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html_content, "html.parser")
        
        # Try current selector
        current_selector = config.get("product_selector")
        matches = soup.select(current_selector)
        print(f"   📊 Current selector '{current_selector}' matches: {len(matches)}")
        
        # Try image selector
        if "product_image_selector" in config:
            img_selector = config["product_image_selector"]
            img_matches = soup.select(img_selector)
            print(f"   🖼️  Current image selector '{img_selector}' matches: {len(img_matches)}")
            
    except Exception as e:
        print(f"   ❌ Error during dump: {e}")
        
    finally:
        # We don't close the browser here to allow reuse if needed, 
        # but main() will shut it down.
        pass

async def main():
    sites = [
        "stokomani.fr"
    ]
    
    for site_key in sites:
        try:
            await dump_search_html(site_key)
        except Exception as e:
            print(f"❌ Error: {e}")
        await asyncio.sleep(1)
    
    await browserless_service.shutdown()

if __name__ == "__main__":
    asyncio.run(main())
