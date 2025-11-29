"""
Script de vérification complète du comparateur sur tous les sites configurés
"""
import asyncio
import logging
import sys
import os
from datetime import datetime

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), ".")))

from app.core.search_config import SITE_CONFIGS
from app.services.search_service import new_search_service
from app.services.browserless_service import browserless_service

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler()]
)

logger = logging.getLogger(__name__)

async def test_site(site_key: str, query: str) -> dict:
    """Test a single site and return results"""
    config = SITE_CONFIGS[site_key]
    result = {
        "site": config["name"],
        "site_key": site_key,
        "category": config["category"],
        "success": False,
        "count": 0,
        "error": None,
        "sample_results": []
    }
    
    try:
        print(f"\n🔍 Testing {config['name']} ({site_key})...")
        results = await new_search_service.search_site(site_key, query)
        
        if results:
            result["success"] = True
            result["count"] = len(results)
            # Store first 2 results as samples
            result["sample_results"] = [
                {
                    "title": r.title,
                    "url": r.url,
                    "price": r.price,
                    "in_stock": r.in_stock
                }
                for r in results[:2]
            ]
            print(f"   ✅ Found {len(results)} results")
            for r in results[:2]:
                price_str = f"{r.price}€" if r.price else "N/A"
                stock_str = "✓" if r.in_stock else "✗" if r.in_stock is False else "?"
                print(f"   - {r.title[:60]}... [{price_str}] [Stock: {stock_str}]")
        else:
            print(f"   ⚠️ No results found")
            
    except Exception as e:
        result["error"] = str(e)
        print(f"   ❌ Error: {e}")
        logger.exception(f"Error testing {site_key}")
    
    return result

async def verify_all_sites():
    """Test all configured sites"""
    query = "chaise"  # Test query
    
    print("=" * 80)
    print(f"VERIFICATION DU COMPARATEUR - Query: '{query}'")
    print(f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 80)
    
    # 1. Test Browserless Connection
    print("\n[1] Testing Browserless Connection...")
    try:
        await browserless_service.start()
        print("✅ Browserless connected successfully")
    except Exception as e:
        print(f"❌ Browserless connection failed: {e}")
        return
    
    # 2. Test all sites
    print(f"\n[2] Testing {len(SITE_CONFIGS)} configured sites...")
    
    all_results = []
    for site_key in SITE_CONFIGS.keys():
        result = await test_site(site_key, query)
        all_results.append(result)
        # Small delay between sites to avoid overload
        await asyncio.sleep(1)
    
    # 3. Summary
    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)
    
    successful = [r for r in all_results if r["success"]]
    failed = [r for r in all_results if not r["success"]]
    
    print(f"\n✅ Successful: {len(successful)}/{len(all_results)}")
    for r in successful:
        print(f"   - {r['site']:20s} | {r['count']:2d} results | Category: {r['category']}")
    
    if failed:
        print(f"\n❌ Failed: {len(failed)}/{len(all_results)}")
        for r in failed:
            error_msg = r['error'][:50] if r['error'] else "No results"
            print(f"   - {r['site']:20s} | Error: {error_msg}")
    
    # 4. Detailed results by category
    print("\n" + "=" * 80)
    print("BY CATEGORY")
    print("=" * 80)
    
    categories = {}
    for r in all_results:
        cat = r["category"]
        if cat not in categories:
            categories[cat] = []
        categories[cat].append(r)
    
    for cat, sites in categories.items():
        successful_count = sum(1 for s in sites if s["success"])
        print(f"\n{cat}: {successful_count}/{len(sites)} working")
        for site in sites:
            status = "✅" if site["success"] else "❌"
            count = f"({site['count']} results)" if site["success"] else "(failed)"
            print(f"   {status} {site['site']:20s} {count}")
    
    # 5. Cleanup
    await browserless_service.stop()
    
    print("\n" + "=" * 80)
    print(f"Verification completed at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 80)
    
    return all_results

if __name__ == "__main__":
    asyncio.run(verify_all_sites())
