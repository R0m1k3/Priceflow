import asyncio
import logging
import sys
import os

# Add project root to path
sys.path.append(os.getcwd())

from app.services.improved_search_service import ImprovedSearchService

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def debug_gifi():
    print("Initializing search service...")
    await ImprovedSearchService.initialize()
    
    try:
        print("Searching Gifi for 'chaise'...")
        results = await ImprovedSearchService.search_site("gifi.fr", "chaise")
        
        print(f"\nFound {len(results)} results.")
        
        if results:
            print("\n--- First 5 Results ---")
            for i, res in enumerate(results[:5]):
                print(f"\nItem {i+1}:")
                print(f"  Title: {res.title}")
                print(f"  Price: {res.price} {res.currency}")
                print(f"  Image: {res.image_url}")
                print(f"  URL: {res.url}")
                print(f"  In Stock: {res.in_stock}")
                
            # Check for missing critical data
            missing_price = sum(1 for r in results if r.price is None)
            missing_image = sum(1 for r in results if not r.image_url)
            
            print(f"\nStats:")
            print(f"  Total: {len(results)}")
            print(f"  Missing Price: {missing_price}")
            print(f"  Missing Image: {missing_image}")
            
    except Exception as e:
        logger.error(f"Error: {e}", exc_info=True)
    finally:
        await ImprovedSearchService.shutdown()

if __name__ == "__main__":
    asyncio.run(debug_gifi())
