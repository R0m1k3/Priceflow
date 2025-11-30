"""
Quick diagnostic script to analyze actual HTML structure of search pages
"""
import asyncio
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from app.services.search_service import NewSearchService
from app.core.search_config import SITE_CONFIGS

async def diagnose_site(site_key: str, query: str = "chaise"):
    """Run a search and show detailed diagnostics"""
    config = SITE_CONFIGS.get(site_key)
    if not config:
        print(f"❌ Site '{site_key}' not found in config")
        return
    
    print(f"\n{'='*80}")
    print(f"🔍 Diagnosing: {config['name']} ({site_key})")
    print(f"{'='*80}")
    print(f"Search URL: {config['search_url'].format(query=query)}")
    print(f"Product Selector: {config['product_selector']}")
    print(f"Image Selector: {config.get('product_image_selector', 'NONE')}")
    
    try:
        results = await NewSearchService.search_site(site_key, query)
        
        print(f"\n📊 Results: {len(results)} products found")
        
        if len(results) == 0:
            print("⚠️  NO RESULTS - Check if product_selector is correct")
        else:
            print("\n✅ Sample Results:")
            for i, result in enumerate(results[:3], 1):
                print(f"\n  {i}. {result.title[:60]}")
                print(f"     URL: {result.url[:80]}")
                print(f"     Image: {result.image_url[:80] if result.image_url else '❌ NONE'}")
                print(f"     Price: {result.price}€" if result.price else "     Price: ❌ NONE")
            
            # Count images
            with_images = sum(1 for r in results if r.image_url)
            print(f"\n📈 Images: {with_images}/{len(results)} ({with_images/len(results)*100:.0f}%)")
            
            with_prices = sum(1 for r in results if r.price)
            print(f"💰 Prices: {with_prices}/{len(results)} ({with_prices/len(results)*100:.0f}%)")
            
    except Exception as e:
        print(f"❌ ERROR: {e}")
        import traceback
        traceback.print_exc()

async def main():
    """Diagnose problematic sites"""
    sites_to_check = [
        "e-leclerc.com",
        "auchan.fr", 
        "carrefour.fr",
        "stokomani.fr",
        "centrakor.com",
        "cdiscount.com",
        "lincroyable.fr"
    ]
    
    for site_key in sites_to_check:
        await diagnose_site(site_key)
        print("\n" + "="*80 + "\n")
        await asyncio.sleep(1)  # Rate limiting

if __name__ == "__main__":
    asyncio.run(main())
