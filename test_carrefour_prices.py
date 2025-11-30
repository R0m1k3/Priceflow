"""
Test if current Carrefour price extraction works
"""
import asyncio
import sys
sys.path.insert(0, '/app')

from app.services.improved_search_service import ImprovedSearchService

async def main():
    print("Initializing browser...")
    await ImprovedSearchService.initialize()
    
    print("Searching Carrefour for 'chaise'...\n")
    results = []
    count = 0
    async for result in ImprovedSearchService.search_site_generator("carrefour.fr", "chaise"):
        results.append(result)
        count += 1
        price_status = f"{result.price}€" if result.price else "N/A"
        print(f"{count}. {result.title[:55]} - {price_status}")
        if count >= 10:
            break
    
    print(f"\n==> Got {len(results)} results")
    
    # Count prices
    with_prices = sum(1 for r in results if r.price)
    print(f"Products with prices: {with_prices}/{len(results)}")
    
    if with_prices == len(results):
        print("✅ SUCCESS: All products have prices!")
    else:
        print(f"⚠️ WARNING: {len(results) - with_prices} products missing prices")
    
    print("\nShutting down...")
    await ImprovedSearchService.shutdown()

if __name__ == "__main__":
    asyncio.run(main())
