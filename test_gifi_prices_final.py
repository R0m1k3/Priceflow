"""
Test fixed Gifi price extraction
"""
import asyncio
import sys
sys.path.insert(0, '/app')

from app.services.improved_search_service import ImprovedSearchService

async def main():
    print("Initializing browser...")
    await ImprovedSearchService.initialize()
    
    print("Searching Gifi for 'chaise'...\n")
    results = []
    count = 0
    async for result in ImprovedSearchService.search_site_generator("gifi.fr", "chaise"):
        results.append(result)
        count += 1
        print(f"{count}. {result.title[:60]} - {result.price}€")
        if count >= 10:
            break
    
    print(f"\n==> Got {len(results)} results")
    
    # Check price diversity
    prices = [r.price for r in results if r.price]
    if prices:
        unique_prices = set(prices)
        print(f"Unique prices: {sorted(unique_prices)}")
        print(f"Price range: {min(prices)}€ - {max(prices)}€")
        if len(unique_prices) > 1:
            print("✅ SUCCESS: Multiple different prices found!")
        else:
            print("⚠️ WARNING: All prices are the same")
    
    print("\nShutting down...")
    await ImprovedSearchService.shutdown()

if __name__ == "__main__":
    asyncio.run(main())
