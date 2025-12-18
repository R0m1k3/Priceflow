import logging
import sys
import os

# Add project root to path
sys.path.append(os.getcwd())

from app.services.parsers.gifi_parser import GifiParser

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def verify_fix():
    print("Verifying Gifi parser fix...")
    
    # Load the dump file (we know it exists from previous steps)
    dump_path = "gifi_full.html"
    if not os.path.exists(dump_path):
        print(f"Error: {dump_path} not found.")
        return

    with open(dump_path, "r", encoding="utf-8") as f:
        html = f.read()
        
    parser = GifiParser()
    # Dummy URL
    url = "https://www.gifi.fr/test-product.html"
    
    print("Parsing product details...")
    details = parser.parse_product_details(html, url)
    
    print("\n--- Extraction Results ---")
    print(f"Bypass Price: {details.get('price')}")
    print(f"Bypass Stock: {details.get('in_stock')}")
    print(f"Currency: {details.get('currency')}")
    
    if details.get('price') is not None:
        print("\nSUCCESS: Price extracted successfully!")
    else:
        print("\nFAILURE: Price not found in dump.")

if __name__ == "__main__":
    verify_fix()
