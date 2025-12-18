import asyncio
import logging
import sys
import os

# Add project root to path
sys.path.append(os.getcwd())

from app.services.ai_price_extractor import AIPriceExtractor

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def verify_ai_extractor():
    print("Verifying AIPriceExtractor on Gifi dump...")
    
    # Load the dump file
    dump_path = "gifi_full.html"
    if not os.path.exists(dump_path):
        print(f"Error: {dump_path} not found.")
        return

    with open(dump_path, "r", encoding="utf-8") as f:
        html = f.read()
        
    title = "Gifi Product Test"
    
    print("Calling AIPriceExtractor...")
    price = await AIPriceExtractor.extract_price(html, title)
    
    print("\n--- AI Extraction Results ---")
    print(f"Price: {price}€")
    
    if price is not None:
        print("\nSUCCESS: AIPriceExtractor worked!")
    else:
        print("\nFAILURE: AIPriceExtractor returned None.")

if __name__ == "__main__":
    asyncio.run(verify_ai_extractor())
