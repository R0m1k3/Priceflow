import asyncio
import logging
import sys
import os

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), ".")))

from app.services.search_service import new_search_service
from app.services.browserless_service import browserless_service
from app.core.search_config import SITE_CONFIGS

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler()]
)

async def debug_search():
    print("--- Debugging Search ---")
    
    # Check Config
    print(f"Available Config Keys: {list(SITE_CONFIGS.keys())}")
    
    sites = ["amazon.fr", "stokomani.fr", "lincroyable.fr"]
    query = "iphone"

    try:
        await browserless_service.initialize()
        
        for site in sites:
            print(f"\nTesting {site}...")
            if site not in SITE_CONFIGS:
                print(f"❌ Site {site} NOT found in SITE_CONFIGS")
                continue
                
            try:
                count = 0
                async for r in new_search_service.search_site_generator(site, query):
                    count += 1
                    print(f"✅ Found: {r.title} - {r.price} {r.currency}")
                    if count >= 1:
                        break
                if count == 0:
                    print(f"⚠️ No results for {site}")
            except Exception as e:
                print(f"❌ Error searching {site}: {e}")
                
    finally:
        await browserless_service.shutdown()

if __name__ == "__main__":
    asyncio.run(debug_search())
