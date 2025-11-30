"""
Test Centrakor image extraction
"""
import asyncio
import sys
sys.path.insert(0, '/app')

from app.services.improved_search_service import ImprovedSearchService

async def main():
    print("Initializing browser...")
    await ImprovedSearchService.initialize()
    
    print("Searching Centrakor for 'chaise'...\n")
    results = []
    count = 0
    async for result in ImprovedSearchService.search_site_generator("centrakor.com", "chaise"):
        results.append(result)
        count += 1
        has_image = "✅" if result.image_url else "❌"
        print(f"{count}. {has_image} {result.title[:55]} - {result.price}€")
        if result.image_url:
            print(f"   Image: {result.image_url[:70]}...")
        if count >= 10:
            break
    
    print(f"\n==> Got {len(results)} results")
    
    # Count images
    with_images = sum(1 for r in results if r.image_url)
    print(f"Products with images: {with_images}/{len(results)}")
    
    if with_images == len(results):
        print("✅ SUCCESS: All products have images!")
    else:
        print(f"⚠️ WARNING: {len(results) - with_images} products missing images")
    
    print("\nShutting down...")
    await ImprovedSearchService.shutdown()

if __name__ == "__main__":
    asyncio.run(main())
