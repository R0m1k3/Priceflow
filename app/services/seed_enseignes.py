"""
Seed default enseignes (stores) for the catalog module
"""

import logging
from sqlalchemy.orm import Session

from app.models import Enseigne

logger = logging.getLogger(__name__)

# Data for the 9 enseignes
ENSEIGNES_DATA = [
    {
        "nom": "Gifi",
        "slug_bonial": "Gifi",
        "couleur": "#E30613",
        "site_url": "https://www.gifi.fr",
        "description": "Décoration, maison, bazar",
        "ordre_affichage": 1,
    },
    {
        "nom": "Action",
        "slug_bonial": "Action",
        "couleur": "#0066B3",
        "site_url": "https://www.action.com/fr-fr/",
        "description": "Discount non-alimentaire",
        "ordre_affichage": 2,
    },
    {
        "nom": "Centrakor",
        "slug_bonial": "Centrakor",
        "couleur": "#E94E1B",
        "site_url": "https://www.centrakor.com",
        "description": "Décoration, maison",
        "ordre_affichage": 3,
    },
    {
        "nom": "La Foir'Fouille",
        "slug_bonial": "La-Foir-Fouille",
        "couleur": "#009639",
        "site_url": "https://www.lafoirfouille.fr",
        "description": "Bazar, décoration",
        "ordre_affichage": 4,
    },
    {
        "nom": "Stokomani",
        "slug_bonial": "Stokomani",
        "couleur": "#FF6600",
        "site_url": "https://www.stokomani.fr",
        "description": "Déstockage textile et maison",
        "ordre_affichage": 5,
    },
    {
        "nom": "B&M",
        "slug_bonial": "BM",
        "couleur": "#D4145A",
        "site_url": "https://bmstores.fr",
        "description": "Discount britannique",
        "ordre_affichage": 6,
    },
    {
        "nom": "L'Incroyable",
        "slug_bonial": "L-incroyable",
        "couleur": "#8B0000",
        "site_url": "https://www.lincroyable.fr",
        "description": "Décoration et mobilier discount (Groupe Althys, siège à Denain)",
        "ordre_affichage": 7,
    },
    {
        "nom": "Bazarland",
        "slug_bonial": "Bazarland",
        "couleur": "#FFCC00",
        "site_url": None,
        "description": "Bazar discount",
        "ordre_affichage": 8,
    },
    {
        "nom": "Noz",
        "slug_bonial": "Noz",
        "couleur": "#003366",
        "site_url": "https://www.noz.fr",
        "description": "Déstockage généraliste",
        "ordre_affichage": 9,
    },
]


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
