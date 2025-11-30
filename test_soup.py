from bs4 import BeautifulSoup
import sys

try:
    with open("/app/debug_dumps/stokomani.fr_failed_verification.html", "r", encoding="utf-8") as f:
        content = f.read()
    
    print(f"Read {len(content)} bytes")
    
    soup = BeautifulSoup(content, "html.parser")
    print("Soup created")
    
    selector = "div.product-card"
    items = soup.select(selector)
    print(f"Found {len(items)} items with selector '{selector}'")
    
    if items:
        item = items[0]
        print("First item classes:", item.get("class"))
        
        title_selector = "h3.product-card__title a"
        title_el = item.select_one(title_selector)
        if title_el:
            print("Title found:", title_el.get_text(strip=True))
        else:
            print(f"Title NOT found with '{title_selector}'")
            
except Exception as e:
    print(f"Error: {e}")
