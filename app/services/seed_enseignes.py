"""
Seed default enseignes (stores) for the catalog module
"""

import logging
from sqlalchemy.orm import Session

from app.models import Enseigne

logger = logging.getLogger(__name__)

# Liste des enseignes vidée - migration vers Amazon France uniquement
# Les magasins discount ne sont plus gérés via le système de catalogues
ENSEIGNES_DATA = []


def seed_enseignes(db: Session) -> int:
    """
    Seed the default enseignes if they don't exist.
    
    Returns:
        Number of enseignes created
    """
    created = 0
    
    for data in ENSEIGNES_DATA:
        # Check if enseigne already exists
        existing = db.query(Enseigne).filter_by(slug_bonial=data["slug_bonial"]).first()
        
        if not existing:
            enseigne = Enseigne(**data)
            db.add(enseigne)
            created += 1
            logger.info(f"Created enseigne: {data['nom']}")
        else:
            logger.debug(f"Enseigne already exists: {data['nom']}")
    
    db.commit()
    logger.info(f"Seeding complete: {created} enseigne(s) created")
    
    return created


def get_enseigne_by_slug(db: Session, slug: str) -> Enseigne | None:
    """Get an enseigne by its Bonial slug"""
    return db.query(Enseigne).filter_by(slug_bonial=slug).first()


def get_all_active_enseignes(db: Session) -> list[Enseigne]:
    """Get all active enseignes ordered by display order"""
    return (
        db.query(Enseigne)
        .filter_by(is_active=True)
        .order_by(Enseigne.ordre_affichage)
        .all()
    )
