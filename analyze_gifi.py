"""
Analyze Gifi HTML to find correct selectors
"""
with open("/app/debug_dumps/gifi_full.html", "r", encoding="utf-8") as f:
    html = f.read()

# Find product-related divs
import re
matches = re.findall(r'<div[^>]*class="[^"]*"[^>]*>.*?</div>', html[:50000], re.DOTALL)

print(f"Total HTML size: {len(html)} bytes")

# Search for price patterns
price_patterns = re.findall(r'50[.,]00\s*€', html[:50000])
print(f"\nFound {len(price_patterns)} instances of '50,00 €'")

# Find all class names containing specific keywords
for keyword in ['product', 'article', 'item', 'card']:
    classes = re.findall(rf'class="([^"]*{keyword}[^"]*)"', html[:100000], re.IGNORECASE)
    unique_classes = set(classes)
    if unique_classes:
        print(f"\nClasses containing '{keyword}':")
        for cls in sorted(unique_classes):
            print(f"  - {cls}")
