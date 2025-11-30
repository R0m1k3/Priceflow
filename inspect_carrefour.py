from bs4 import BeautifulSoup

with open("dump_carrefour_fr.html", "r", encoding="utf-8") as f:
    html = f.read()

soup = BeautifulSoup(html, "html.parser")
articles = soup.select("article.product-list-card-plp-grid-new")

print(f"Found {len(articles)} articles")

if articles:
    first = articles[0]
    print("\n--- First Article Structure ---")
    print(first.prettify()[:1000]) # Print first 1000 chars
    
    # Check for link
    link = first.select_one("a.product-card-click-wrapper")
    if link:
        print(f"\nLink found: {link.get('href')}")
        print(f"Link classes: {link.get('class')}")
        
        # Check for image INSIDE link
        img = link.select_one("img.product-card-image-new__content")
        if img:
             print(f"\n✅ Image found INSIDE link: {img.get('src')}")
        else:
             print(f"\n❌ Image NOT found inside link")
             # Check if image is elsewhere in article
             img_article = first.select_one("img.product-card-image-new__content")
             if img_article:
                 print(f"   But image exists in article: {img_article.get('src')}")
    else:
        print("\nNo link found with selector a.product-card-click-wrapper")
