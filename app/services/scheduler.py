"""
Scheduler for automated catalog scraping

Runs scraping jobs twice daily (6h and 18h) for all active enseignes.
"""

import logging
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from app.database import SessionLocal
from app.services.cataloguemate_scraper import scrape_all_enseignes
# from app.services.bonial_scraper import scrape_all_enseignes

logger = logging.getLogger(__name__)

# Global scheduler instance
scheduler = AsyncIOScheduler()


async def scheduled_scrape_job():
    """Scheduled job to scrape all active enseignes"""
    logger.info("Starting scheduled catalog scraping job")
    
    db = SessionLocal()
    try:
        logs = await scrape_all_enseignes(db)
        
        total_new = sum(log.catalogues_nouveaux for log in logs)
        total_found = sum(log.catalogues_trouves for log in logs)
        
        logger.info(
            f"Scheduled scraping complete: "
            f"{len(logs)} enseignes processed, "
            f"{total_found} catalogues found, "
            f"{total_new} new catalogues created"
        )
    except Exception as e:
        logger.error(f"Error in scheduled scraping job: {e}")
    finally:
        db.close()


async def scheduled_purge_job():
    """Scheduled job to purge old catalogs (expired > 3 months)"""
    logger.info("Starting scheduled catalog purge job")
    
    from datetime import datetime, timedelta
    from app.models import Catalogue
    
    db = SessionLocal()
    try:
        cutoff_date = datetime.now() - timedelta(days=90)
        
        old_catalogues = db.query(Catalogue).filter(
            Catalogue.date_fin < cutoff_date
        ).all()
        
        count = len(old_catalogues)
        for cat in old_catalogues:
            db.delete(cat)
        
        db.commit()
        logger.info(f"Scheduled purge complete: deleted {count} catalogues with date_fin < {cutoff_date}")
    except Exception as e:
        logger.error(f"Error in scheduled purge job: {e}")
    finally:
        db.close()


def start_scheduler():
    """Start the scheduler with configured jobs"""
    # Schedule scraping twice daily at 6:00 and 18:00
    scheduler.add_job(
        scheduled_scrape_job,
        CronTrigger(hour="6,18", minute=0),
        id="catalog_scraping",
        name="Scrape Cataloguemate catalogs",
        replace_existing=True,
    )
    
    # Schedule automatic purge on the 1st of each month at 3:00 AM
    scheduler.add_job(
        scheduled_purge_job,
        CronTrigger(day=1, hour=3, minute=0),
        id="catalog_purge",
        name="Purge old catalogs",
        replace_existing=True,
    )
    
    scheduler.start()
    logger.info("Catalog scraping scheduler started (scraping at 6:00 and 18:00, purge on 1st of month at 3:00)")


def stop_scheduler():
    """Stop the scheduler"""
    if scheduler.running:
        scheduler.shutdown()
        logger.info("Catalog scraping scheduler stopped")
