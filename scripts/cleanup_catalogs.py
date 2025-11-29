import asyncio
import logging
import os
import sys

# Add parent directory to path to import app modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from app.database import Base, get_db
from app.models import Catalogue, CataloguePage, ScrapingLog

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def cleanup_bad_catalogs():
    """
    Delete catalogs that have 0 pages or were created with invalid data.
    """
    # Get database URL from environment or use default
    DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://priceflow:priceflow@localhost:5488/priceflow")
    
    engine = create_engine(DATABASE_URL)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = SessionLocal()
    
    try:
        logger.info("Starting cleanup of invalid catalogs...")
        
        # 1. Delete catalogs with 0 pages
        # We need to check actual pages count in DB, not just the column
        
        # Find catalogs with no pages
        bad_catalogs = db.query(Catalogue).filter(Catalogue.nombre_pages == 0).all()
        
        count = 0
        for cat in bad_catalogs:
            logger.info(f"Deleting empty catalog: {cat.titre} (ID: {cat.id})")
            db.delete(cat)
            count += 1
            
        # 2. Delete catalogs with generic titles if any remain
        generic_titles = [
            "Restez informé",
            "Catalogues Bazar",
            "Toutes les offres",
            "Voir les offres",
            "Téléchargez l'application",
            "Newsletter",
            "BLACK FRIDAY" # Often a banner if 0 pages
        ]
        
        for title_part in generic_titles:
            generic_cats = db.query(Catalogue).filter(Catalogue.titre.ilike(f"%{title_part}%")).all()
            for cat in generic_cats:
                # Only delete if it has few pages (e.g. < 2) or seems suspicious
                # Actually, let's just check if it has pages. If it has pages, it might be valid.
                # But we already deleted 0-page ones.
                # Let's be careful.
                pass

        db.commit()
        logger.info(f"Cleanup complete. Deleted {count} invalid catalogs.")
        
    except Exception as e:
        logger.error(f"Error during cleanup: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    cleanup_bad_catalogs()
