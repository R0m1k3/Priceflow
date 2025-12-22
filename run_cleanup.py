import sys
import os
import logging
from sqlalchemy.orm import Session

# Add project root to path
sys.path.append(os.getcwd())

from app.database import SessionLocal, engine
from app.models import Catalogue

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def cleanup_catalogs():
    db = SessionLocal()
    try:
        logger.info("Starting cleanup...")
        deleted_count = 0

        # 1. Delete catalogs with 0 pages
        bad_catalogs = db.query(Catalogue).filter(Catalogue.nombre_pages == 0).all()
        for cat in bad_catalogs:
            logger.info(f"Deleting empty catalog: {cat.titre}")
            db.delete(cat)
            deleted_count += 1

        # 2. Delete catalogs with iconic/bad images
        all_catalogs = db.query(Catalogue).all()
        for cat in all_catalogs:
            if not cat.image_couverture_url:
                continue

            if any(
                x in cat.image_couverture_url.lower()
                for x in ["icon", "logo", "loader", "facebook", "twitter", "assets/img"]
            ):
                logger.info(f"Deleting catalog with bad image: {cat.titre} ({cat.image_couverture_url})")
                db.delete(cat)
                deleted_count += 1

        db.commit()
        logger.info(f"Cleanup complete. Deleted {deleted_count} catalogs.")

    except Exception as e:
        logger.error(f"Error during cleanup: {e}")
    finally:
        db.close()


if __name__ == "__main__":
    cleanup_catalogs()
