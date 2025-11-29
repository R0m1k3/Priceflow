import sys
import os

# Add app to path
sys.path.append(os.getcwd())

from app.core.database import SessionLocal
from app.models import SearchSite
from app.core.search_config import SITE_CONFIGS

def debug_sites():
    db = SessionLocal()
    try:
        print("=== SITE_CONFIGS Keys ===")
        for key in SITE_CONFIGS.keys():
            print(f"- {key}")
            
        print("\n=== DB SearchSites ===")
        sites = db.query(SearchSite).all()
        for site in sites:
            print(f"ID: {site.id} | Name: {site.name} | Domain: {site.domain} | Active: {site.is_active}")
            print(f"   URL: {site.search_url}")
            print(f"   Selector: {site.product_link_selector}")
            print("-" * 20)
            
    finally:
        db.close()

if __name__ == "__main__":
    debug_sites()
