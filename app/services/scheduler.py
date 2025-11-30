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


def start_scheduler():
    """Start the scheduler with configured jobs"""
    # Schedule scraping twice daily at 6:00 and 18:00
    scheduler.add_job(
        scheduled_scrape_job,
        CronTrigger(hour="6,18", minute=0),
        id="catalog_scraping",
        name="Scrape Bonial catalogs",
        replace_existing=True,
    )
    
    scheduler.start()
    logger.info("Catalog scraping scheduler started (runs at 6:00 and 18:00)")


def stop_scheduler():
    """Stop the scheduler"""
    if scheduler.running:
        scheduler.shutdown()
        logger.info("Catalog scraping scheduler stopped")
