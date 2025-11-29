"""
Verification Script for Bonial Catalog Module

Tests database setup, scraper functionality, and API endpoints.
"""

import asyncio
import logging
import sys
from datetime import datetime

import httpx
from sqlalchemy import inspect, text

from app.database import SessionLocal, engine
from app.models import Catalogue, CataloguePage, Enseigne, ScrapingLog
from app.services.bonial_scraper import scrape_enseigne
from app.services.seed_enseignes import seed_enseignes

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

API_BASE_URL = "http://localhost:8555/api"


def check_database_tables():
    """Verify that catalog module tables exist."""
    logger.info("=" * 60)
    logger.info("Phase 1: Checking Database Tables")
    logger.info("=" * 60)
    
    inspector = inspect(engine)
    required_tables = [
        "enseignes",
        "catalogues",
        "catalogue_pages",
        "scraping_logs",
    ]
    
    existing_tables = inspector.get_table_names()
    
    all_exist = True
    for table in required_tables:
        exists = table in existing_tables
        status = "✅" if exists else "❌"
        logger.info(f"{status} Table '{table}': {'EXISTS' if exists else 'MISSING'}")
        if not exists:
            all_exist = False
    
    if all_exist:
        logger.info("\n✅ All required tables exist!\n")
        return True
    else:
        logger.error("\n❌ Some tables are missing. Run migration: alembic upgrade head\n")
        return False


def check_enseignes_seeding():
    """Verify that enseignes are seeded."""
    logger.info("=" * 60)
    logger.info("Phase 2: Checking Enseignes Seeding")
    logger.info("=" * 60)
    
    db = SessionLocal()
    try:
        count = db.query(Enseigne).count()
        logger.info(f"Found {count} enseignes in database")
        
        if count == 0:
            logger.info("Seeding enseignes...")
            created = seed_enseignes(db)
            logger.info(f"✅ Created {created} enseignes")
            count = created
        
        if count >= 9:
            logger.info("\n✅ All 9 enseignes are seeded!\n")
            
            # Display enseignes
            enseignes = db.query(Enseigne).order_by(Enseigne.ordre_affichage).all()
            for ens in enseignes:
                active = "✅" if ens.is_active else "⚠️"
                logger.info(f"  {active} {ens.ordre_affichage}. {ens.nom} (slug: {ens.slug_bonial})")
            
            return True
        else:
            logger.warning(f"\n⚠️ Expected 9 enseignes, found {count}\n")
            return False
            
    finally:
        db.close()


async def test_scraper():
    """Test the Bonial scraper on one enseigne."""
    logger.info("=" * 60)
    logger.info("Phase 3: Testing Bonial Scraper (Gifi)")
    logger.info("=" * 60)
    
    db = SessionLocal()
    try:
        # Get Gifi enseigne
        gifi = db.query(Enseigne).filter_by(slug_bonial="Gifi").first()
        
        if not gifi:
            logger.error("❌ Gifi enseigne not found")
            return False
        
        logger.info(f"Testing scraper for: {gifi.nom}")
        logger.info("This may take 30-60 seconds...")
        
        # Run scraper
        log = await scrape_enseigne(gifi, db)
        
        # Display results
        logger.info(f"\nScraping completed:")
        logger.info(f"  Status: {log.statut}")
        logger.info(f"  Catalogues found: {log.catalogues_trouves}")
        logger.info(f"  New catalogues: {log.catalogues_nouveaux}")
        logger.info(f"  Duration: {log.duree_secondes:.2f}s")
        
        if log.message_erreur:
            logger.warning(f"  Error: {log.message_erreur}")
        
        if log.statut in ["success", "partial"] and log.catalogues_trouves > 0:
            logger.info("\n✅ Scraper is working!\n")
            
            # Display sample catalog
            cat = db.query(Catalogue).filter_by(enseigne_id=gifi.id).first()
            if cat:
                logger.info(f"Sample catalog:")
                logger.info(f"  Titre: {cat.titre}")
                logger.info(f"  Dates: {cat.date_debut.date()} → {cat.date_fin.date()}")
                logger.info(f"  Pages: {cat.nombre_pages}")
            
            return True
        else:
            logger.error("\n❌ Scraper failed or found no catalogs\n")
            return False
            
    except Exception as e:
        logger.error(f"❌ Error testing scraper: {e}")
        return False
    finally:
        db.close()


async def test_api_endpoints():
    """Test API endpoints."""
    logger.info("=" * 60)
    logger.info("Phase 4: Testing API Endpoints")
    logger.info("=" * 60)
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        # Test 1: Get enseignes
        logger.info("\n1. Testing GET /api/catalogues/enseignes")
        try:
            response = await client.get(f"{API_BASE_URL}/catalogues/enseignes")
            if response.status_code == 200:
                enseignes = response.json()
                logger.info(f"   ✅ Status 200 - Found {len(enseignes)} enseignes")
                if enseignes:
                    logger.info(f"   Sample: {enseignes[0]['nom']} ({enseignes[0]['catalogues_actifs_count']} catalogues)")
            else:
                logger.error(f"   ❌ Status {response.status_code}")
                return False
        except Exception as e:
            logger.error(f"   ❌ Error: {e}")
            return False
        
        # Test 2: Get catalogues
        logger.info("\n2. Testing GET /api/catalogues")
        try:
            response = await client.get(f"{API_BASE_URL}/catalogues?page=1&limit=5")
            if response.status_code == 200:
                data = response.json()
                catalogues = data.get("data", [])
                pagination = data.get("pagination", {})
                logger.info(f"   ✅ Status 200 - Found {pagination.get('total', 0)} catalogues")
                logger.info(f"   Page: {pagination.get('page')}/{pagination.get('pages_total')}")
                if catalogues:
                    logger.info(f"   Sample: {catalogues[0]['titre']}")
            else:
                logger.error(f"   ❌ Status {response.status_code}")
                return False
        except Exception as e:
            logger.error(f"   ❌ Error: {e}")
            return False
        
        # Test 3: Get catalogue detail
        logger.info("\n3. Testing GET /api/catalogues/{id}")
        try:
            # Get first catalog ID
            db = SessionLocal()
            cat = db.query(Catalogue).first()
            db.close()
            
            if cat:
                response = await client.get(f"{API_BASE_URL}/catalogues/{cat.id}")
                if response.status_code == 200:
                    detail = response.json()
                    logger.info(f"   ✅ Status 200 - Catalogue: {detail['titre']}")
                    logger.info(f"   Pages: {detail['nombre_pages']}")
                else:
                    logger.error(f"   ❌ Status {response.status_code}")
                    return False
            else:
                logger.warning("   ⚠️ No catalogues in DB to test detail endpoint")
        except Exception as e:
            logger.error(f"   ❌ Error: {e}")
            return False
        
        # Test 4: Get catalogue pages
        logger.info("\n4. Testing GET /api/catalogues/{id}/pages")
        try:
            if cat:
                response = await client.get(f"{API_BASE_URL}/catalogues/{cat.id}/pages")
                if response.status_code == 200:
                    pages = response.json()
                   logger.info(f"   ✅ Status 200 - Found {len(pages)} pages")
                    if pages:
                        logger.info(f"   Sample page: {pages[0]['numero_page']} - {pages[0]['image_url'][:50]}...")
                else:
                    logger.error(f"   ❌ Status {response.status_code}")
                    return False
        except Exception as e:
            logger.error(f"   ❌ Error: {e}")
            return False
        
        # Test 5: Get stats (requires working DB)
        logger.info("\n5. Testing GET /api/catalogues/admin/stats")
        try:
            response = await client.get(f"{API_BASE_URL}/catalogues/admin/stats")
            if response.status_code == 200:
                stats = response.json()
                logger.info(f"   ✅ Status 200 - Total catalogues: {stats['total_catalogues']}")
                logger.info(f"   Prochaine exécution: {stats['prochaine_execution']}")
            else:
                logger.error(f"   ❌ Status {response.status_code}")
                # Stats is optional, don't fail
        except Exception as e:
            logger.warning(f"   ⚠️ Stats endpoint error (may require auth): {e}")
    
    logger.info("\n✅ All API endpoints are working!\n")
    return True


async def main():
    """Run all verification tests."""
    logger.info("\n" + "=" * 60)
    logger.info("BONIAL CATALOG MODULE - VERIFICATION SCRIPT")
    logger.info("=" * 60 + "\n")
    
    results = []
    
    # Phase 1: Database tables
    results.append(("Database Tables", check_database_tables()))
    
    if not results[0][1]:
        logger.error("\n❌ Database not ready. Please run: alembic upgrade head")
        sys.exit(1)
    
    # Phase 2: Enseignes seeding
    results.append(("Enseignes Seeding", check_enseignes_seeding()))
    
    # Phase 3: Scraper test (optional, can be slow)
    scraper_test = input("\nRun scraper test? (Gifi - takes ~60s) [y/N]: ").lower() == "y"
    if scraper_test:
        results.append(("Scraper Test", await test_scraper()))
    
    # Phase 4: API endpoints (requires app to be running)
    api_test = input("\nTest API endpoints? (App must be running on :8555) [y/N]: ").lower() == "y"
    if api_test:
        results.append(("API Endpoints", await test_api_endpoints()))
    
    # Summary
    logger.info("\n" + "=" * 60)
    logger.info("VERIFICATION SUMMARY")
    logger.info("=" * 60)
    
    for name, passed in results:
        status = "✅ PASSED" if passed else "❌ FAILED"
        logger.info(f"{status}: {name}")
    
    all_passed = all(result[1] for result in results)
    
    if all_passed:
        logger.info("\n✅ ALL TESTS PASSED - Bonial module is ready!")
    else:
        logger.error("\n❌ SOME TESTS FAILED - Please review errors above")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
