import asyncio
import logging
import time
from app.services.improved_search_service import ImprovedSearchService
from app.core.search_config import SITE_CONFIGS

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def verify_site(site_key: str):
    print(f"\n{'='*50}")
    print(f"🔍 Verifying {site_key}...")
    print(f"{'='*50}")
    
    start_time = time.time()
    first_result_time = None
    count = 0
    
    try:
        async for result in ImprovedSearchService.search_site_generator(site_key, "chaise"):
            count += 1
            if count == 1:
                first_result_time = time.time()
                elapsed = first_result_time - start_time
                print(f"🚀 First result in {elapsed:.2f}s")
                print(f"   Title: {result.title}")
                print(f"   Price: {result.price} {result.currency}")
                print(f"   Image: {result.image_url}")
            
            # Print a dot for each result to show progress
            print(".", end="", flush=True)
            
        total_time = time.time() - start_time
        print(f"\n✅ Finished {site_key}: {count} results in {total_time:.2f}s")
        
        if count == 0:
            print(f"❌ WARNING: 0 results found for {site_key}")
            return False
        return True

    except Exception as e:
        print(f"\n❌ ERROR verifying {site_key}: {e}")
        return False

async def main():
    await ImprovedSearchService.initialize()
    
    sites = list(SITE_CONFIGS.keys())
    results = {}
    
    # Test all sites sequentially to avoid overwhelming the browser/network
    for site in sites:
        success = await verify_site(site)
        results[site] = success
        # Small pause between sites
        await asyncio.sleep(2)
        
    await ImprovedSearchService.shutdown()
    
    print("\n" + "="*50)
    print("SUMMARY")
    print("="*50)
    for site, success in results.items():
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{status} - {site}")

if __name__ == "__main__":
    asyncio.run(main())
