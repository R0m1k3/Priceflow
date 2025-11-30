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
    level=logging.DEBUG, # Enable DEBUG logging
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler()]
)
# Set other loggers to INFO to avoid noise
logging.getLogger("urllib3").setLevel(logging.INFO)
logging.getLogger("asyncio").setLevel(logging.INFO)
logging.getLogger("websockets").setLevel(logging.INFO)

async def verify_search():
    query = "chaise" # Updated query
    print(f"--- Starting Verification Search for '{query}' ---")
    
    # 1. Test Browserless Connection
    print("\n[1] Testing Browserless Connection...")
    try:
        await browserless_service.initialize()
        print("✅ Browserless connected successfully")
    except Exception as e:
        print(f"❌ Browserless connection failed: {e}")
        return

    # 2. Test Specific Sites
    # sites_to_test = ["gifi.fr", "lincroyable.fr", "stokomani.fr"] # Excluded amazon.fr
    sites_to_test = ["stokomani.fr"] # Focus on Stokomani for now as requested/implied context
    
    for site in sites_to_test:
        print(f"\n[2] Testing Search on {site}...")
        try:
            count = 0
            async for r in new_search_service.search_site_generator(site, query):
                count += 1
                print(f"✅ Found result: {r.title} ({r.url})")
                print(f"   Price: {r.price} {r.currency}")
                print(f"   Image: {r.image_url}")
                if count >= 1:
                    break
            if count == 0:
                print(f"⚠️ No results found for {site}")
                # Dump HTML for debugging
                try:
                    content, _ = await browserless_service.get_page_content(
                        SITE_CONFIGS[site]["search_url"].format(query=query),
                        use_proxy=SITE_CONFIGS[site].get("requires_proxy", False),
                        wait_selector=SITE_CONFIGS[site].get("wait_selector")
                    )
                    with open(f"/app/debug_dumps/{site}_failed_verification.html", "w", encoding="utf-8") as f:
                        f.write(content)
                    print(f"📄 Saved HTML dump to /app/debug_dumps/{site}_failed_verification.html")
                except Exception as dump_e:
                    print(f"❌ Failed to save HTML dump: {dump_e}")
        except Exception as e:
            print(f"❌ Error searching {site}: {e}")

    # 3. Cleanup
    await browserless_service.shutdown()
    print("\n--- Verification Complete ---")

if __name__ == "__main__":
    asyncio.run(verify_search())
