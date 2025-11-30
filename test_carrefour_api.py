"""
Test Carrefour via API endpoint (production-like)
"""
import requests
import json

url = "http://localhost:8555/api/search"
params = {
    "q": "chaise",
    "sites": "7",  # Carrefour site ID
    "max_results": 10
}

print(f"Testing: {url}")
print(f"Params: {params}\n")

response = requests.get(url, params=params, stream=True)

print(f"Status: {response.status_code}")
print(f"Headers: {dict(response.headers)}\n")

count = 0
for line in response.iter_lines():
    if line:
        try:
            # Each line should be JSON
            data = json.loads(line.decode('utf-8'))
            count += 1
            
            title = data.get('title', 'N/A')[:60]
            price = data.get('price', 'N/A')
            image = "✅" if data.get('image_url') else "❌"
            
            print(f"{count}. [{image}] {title} - {price}€")
            
            if count >= 10:
                break
        except json.JSONDecodeError as e:
            print(f"JSON Error: {e}")
            print(f"Line: {line[:100]}")

print(f"\nTotal: {count} results")
