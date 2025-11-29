import asyncio
import logging
import sys
import os

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), ".")))

from app.services.search_service import new_search_service
from app.services.browserless_service import browserless_service

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler()]
)

async def verify_search():
    query = "iphone 15"
    print(f"--- Starting Verification Search for '{query}' ---")
    
    # 1. Test Browserless Connection
    print("\n[1] Testing Browserless Connection...")
    try:
        await browserless_service.start()
        print("✅ Browserless connected successfully")
    except Exception as e:
        print(f"❌ Browserless connection failed: {e}")
        return

    # 2. Test Specific Sites
    sites_to_test = ["gifi.fr", "amazon.fr", "e.leclerc"]
    
    for site in sites_to_test:
        print(f"\n[2] Testing Search on {site}...")
        try:
            results = await new_search_service.search_site(site, query)
            if results:
                print(f"✅ Found {len(results)} results for {site}")
                for r in results[:2]:
                    print(f"   - {r.title} ({r.url})")
            else:
                print(f"⚠️ No results found for {site}")
        except Exception as e:
            print(f"❌ Error searching {site}: {e}")

    # 3. Cleanup
    await browserless_service.stop()
    print("\n--- Verification Complete ---")

if __name__ == "__main__":
    asyncio.run(verify_search())
