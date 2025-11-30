"""
Debug script to identify correct selectors for missing sites
"""
import asyncio
import sys
import os
from pathlib import Path

# Add app directory to path
sys.path.insert(0, str(Path(__file__).parent))

from app.services.browserless_service import browserless_service
from bs4 import BeautifulSoup

async def analyze_site(name: str, url: str, wait_selector: str = None):
    """Analyze a search results page to identify selectors"""
    print(f"\n{'='*80}")
    print(f"Analyzing: {name}")
    print(f"URL: {url}")
    print(f"{'='*80}\n")
    
    html, screenshot = await browserless_service.get_page_content(
        url,
        use_proxy=False,
        wait_selector=wait_selector,
        wait_timeout=10000
    )
    
    if not html:
        print(f"❌ Failed to get content for {name}")
        return
    
    soup = BeautifulSoup(html, "html.parser")
    
    # Save HTML for manual inspection
    output_file = f"debug_{name.lower().replace(' ', '_')}.html"
    with open(output_file, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"💾 HTML saved to: {output_file}")
    
    # Common product link patterns
    product_patterns = [
        "a[href*='/product']",
        "a[href*='/p/']",
        "a[href*='/produit']",
        "a.product-card",
        "a.product-link",
        "[data-product-id]",
        "article a",
        "div[data-testid*='product'] a",
    ]
    
    print("\n🔍 Searching for product links...")
    for pattern in product_patterns:
        links = soup.select(pattern)
        if links and len(links) >= 3:
            print(f"✅ Found {len(links)} matches for: {pattern}")
            # Show first 3 examples
            for i, link in enumerate(links[:3], 1):
                href = link.get('href', 'NO_HREF')
                text = link.get_text(strip=True)[:50]
                print(f"   {i}. {href[:60]} | {text}")
        elif links:
            print(f"⚠️  Found {len(links)} matches for: {pattern} (too few)")
    
    # Common image patterns
    image_patterns = [
        "img[src*='product']",
        "img.product-image",
        "img.product-img",
        "img[loading='lazy']",
        "picture img",
        "img[data-src]",
    ]
    
    print("\n🖼️  Searching for product images...")
    for pattern in image_patterns:
        images = soup.select(pattern)
        if images and len(images) >= 3:
            print(f"✅ Found {len(images)} matches for: {pattern}")
            for i, img in enumerate(images[:3], 1):
                src = img.get('src') or img.get('data-src', 'NO_SRC')
                alt = img.get('alt', 'NO_ALT')[:50]
                print(f"   {i}. {src[:60]} | {alt}")
        elif images:
            print(f"⚠️  Found {len(images)} matches for: {pattern} (too few)")
    
    print(f"\n✅ Analysis complete for {name}\n")

async def main():
    """Test all missing sites"""
    sites = [
        {
            "name": "E.Leclerc",
            "url": "https://www.e-leclerc.com/recherche?text=chaise",
            "wait": ".product-card, .search-results"
        },
        {
            "name": "Auchan",
            "url": "https://www.auchan.fr/search?text=chaise",
            "wait": ".product-card, .product-item"
        },
        {
            "name": "Carrefour",
            "url": "https://www.carrefour.fr/s?q=chaise",
            "wait": "[data-testid*='product'], .product"
        },
    ]
    
    for site in sites:
        try:
            await analyze_site(site["name"], site["url"], site.get("wait"))
        except Exception as e:
            print(f"❌ Error analyzing {site['name']}: {e}")
        
        # Small delay between sites
        await asyncio.sleep(2)

if __name__ == "__main__":
    asyncio.run(main())
