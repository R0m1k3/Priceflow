"""
Test Gifi price extraction
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
    count = 0
    async for result in ImprovedSearchService.search_site_generator("gifi.fr", "chaise"):
        results.append(result)
        count += 1
        print(f"{count}. {result.title[:60]} - Price: {result.price}€")
        if count >= 5:  # Only test first 5
            break
    
    print(f"\n==> Got {len(results)} results")
    
    # Check if all prices are the same
    prices = [r.price for r in results if r.price]
    if prices:
        unique_prices = set(prices)
        print(f"Unique prices: {unique_prices}")
        if len(unique_prices) == 1:
            print("⚠️ WARNING: All prices are the same!")
    
    print("Shutting down...")
    await ImprovedSearchService.shutdown()

if __name__ == "__main__":
    asyncio.run(main())
