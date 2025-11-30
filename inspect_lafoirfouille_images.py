from bs4 import BeautifulSoup

with open("dump_lafoirfouille_fr.html", "r", encoding="utf-8") as f:
    html = f.read()

soup = BeautifulSoup(html, "html.parser")
images = soup.select("img")

print(f"Found {len(images)} images")

for i, img in enumerate(images[:10]):
    print(f"\n--- Image {i+1} ---")
    print(f"Src: {img.get('src')}")
    print(f"Classes: {img.get('class')}")
    
    parent = img.parent
    print(f"Parent: {parent.name} (Classes: {parent.get('class')})")
    
    grandparent = parent.parent
    if grandparent:
        print(f"Grandparent: {grandparent.name} (Classes: {grandparent.get('class')})")
        
    greatgrandparent = grandparent.parent
    if greatgrandparent:
        print(f"Great Grandparent: {greatgrandparent.name} (Classes: {greatgrandparent.get('class')})")
