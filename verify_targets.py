import asyncio
import logging
import sys
import os

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

async def test_specific_sites():
    target_sites = ["auchan.fr", "carrefour.fr", "lafoirfouille.fr", "stokomani.fr"]
    query = "chaise"
    
    print(f"Testing {target_sites} with query '{query}'...")
    
    await browserless_service.initialize()
    
    for site_key in target_sites:
        if site_key not in SITE_CONFIGS:
            print(f"Skipping {site_key} (not in config)")
            continue
            
        print(f"\n--- Testing {site_key} ---")
        try:
            results = await new_search_service.search_site(site_key, query)
            print(f"Found {len(results)} results")
            for r in results[:3]:
                print(f"  - {r.title} ({r.price}€) [Image: {r.image_url}]")
        except Exception as e:
            print(f"Error testing {site_key}: {e}")
            
    await browserless_service.shutdown()

if __name__ == "__main__":
    asyncio.run(test_specific_sites())
