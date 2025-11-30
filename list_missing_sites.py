"""
Script to list all sites in database and check which ones are missing from search_config.py
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from app.database import SessionLocal
from app.models import SearchSite
from app.core.search_config import SITE_CONFIGS

def main():
    """List all sites in DB and identify missing configurations"""
    db = SessionLocal()
    
    try:
        # Get all sites from database
        sites = db.query(SearchSite).order_by(SearchSite.name).all()
        
        print(f"\n{'='*80}")
        print(f"Sites in Database: {len(sites)}")
        print(f"Sites in SITE_CONFIGS: {len(SITE_CONFIGS)}")
        print(f"{'='*80}\n")
        
        # Check each DB site
        missing = []
        configured = []
        
        for site in sites:
            domain_clean = site.domain.replace("www.", "").lower()
            
            # Check if configured
            is_configured = False
            for key in SITE_CONFIGS.keys():
                if key in domain_clean or domain_clean in key:
                    configured.append((site.id, site.name, site.domain, key))
                    is_configured = True
                    break
            
            if not is_configured:
                missing.append((site.id, site.name, site.domain))
        
        # Display results
        if configured:
            print("✅ CONFIGURED SITES:")
            for sid, name, domain, key in configured:
                print(f"   [{sid:2d}] {name:20s} ({domain:25s}) → {key}")
        
        if missing:
            print(f"\n❌ MISSING {len(missing)} SITES:")
            for sid, name, domain in missing:
                print(f"   [{sid:2d}] {name:20s} ({domain})")
        else:
            print("\n✅ All sites are configured!")
        
        print(f"\n{'='*80}\n")
        
    finally:
        db.close()

if __name__ == "__main__":
    main()
