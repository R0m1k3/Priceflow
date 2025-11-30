"""
Test script to trigger Carrefour search and generate HTML dump
"""
import asyncio
import sys
sys.path.insert(0, '/app')

from app.services.improved_search_service import ImprovedSearchService

async def main():
    print("Initializing browser...")
    await ImprovedSearchService.initialize()
    
    print("Searching Carrefour for 'chaise'...")
    results = []
    async for result in ImprovedSearchService.search_site_generator("carrefour.fr", "chaise"):
        results.append(result)
        print(f"Found: {result.title}")
    
    print(f"\nTotal results: {len(results)}")
    
    print("Shutting down...")
    await ImprovedSearchService.shutdown()

if __name__ == "__main__":
    asyncio.run(main())
