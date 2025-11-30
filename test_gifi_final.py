"""
Final test of Gifi with new selectors
"""
import asyncio
import sys
sys.path.insert(0, '/app')

from app.services.improved_search_service import ImprovedSearchService

async def main():
    print("Initializing browser...")
    await ImprovedSearchService.initialize()
    
    print("Searching Gifi for 'chaise'...")
    results = []
    async for result in ImprovedSearchService.search_site_generator("gifi.fr", "chaise"):
        results.append(result)
        print(f"✓ {result.title[:50]} - {result.price}€")
    
    print(f"\n==> Total: {len(results)} results")
    
    if results:
        print("\nFirst 3 products:")
        for i, r in enumerate(results[:3]):
            print(f"{i+1}. Title: {r.title}")
            print(f"   Price: {r.price}€")
            print(f"   URL: {r.url[:80]}...")
            print()
    
    print("Shutting down...")
    await ImprovedSearchService.shutdown()

if __name__ == "__main__":
    asyncio.run(main())
