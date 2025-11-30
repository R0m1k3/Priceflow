from bs4 import BeautifulSoup

with open("dump_lafoirfouille_fr.html", "r", encoding="utf-8") as f:
    html = f.read()

soup = BeautifulSoup(html, "html.parser")

# Try to find product containers
print("Searching for product containers...")
potential_selectors = [
    "div.product-miniature", 
    "article", 
    "div[class*='product']",
    "div.product-card",
    "div.item"
]

for selector in potential_selectors:
    matches = soup.select(selector)
    print(f"Selector '{selector}' matches: {len(matches)}")
    if len(matches) > 0 and len(matches) < 5:
        # If few matches, print classes to see if it's a wrapper
        print(f"  Classes: {matches[0].get('class')}")

# Print structure of first potential product
products = soup.select("div.product-miniature")
if not products:
    products = soup.select("div[class*='product-item']")

if products:
    first = products[0]
    print("\n--- First Product Structure ---")
    print(first.prettify()[:1000])
    
    link = first.find("a")
    if link:
        print(f"\nLink found: {link.get('href')}")
    
    img = first.find("img")
    if img:
        print(f"\nImage found: {img.get('src')}")
else:
    print("\nNo obvious products found. Dumping generic structure...")
    # Find any div with many children
    divs = soup.find_all("div")
    for div in divs:
        if len(div.find_all("div", recursive=False)) > 10:
            print(f"Found container with many children: {div.get('class')}")
            # Print first child
            child = div.find("div")
            if child:
                print(child.prettify()[:500])
            break
