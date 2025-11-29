"""
Bonial.fr Scraper Service

Scrapes promotional catalogs from Bonial.fr for configured enseignes.
Uses Playwright for browser automation.
"""

import asyncio
import hashlib
import logging
import re
from datetime import datetime
from typing import Any

from playwright.async_api import async_playwright, Page, Browser
from sqlalchemy.orm import Session

from app.models import Enseigne, Catalogue, CataloguePage, ScrapingLog

logger = logging.getLogger(__name__)

# Bonial selectors based on manual analysis
BONIAL_SELECTORS = {
    "catalog_card": "a[href*='/catalogue/']:has(img), section:has(img[src*='content-media.bonial.biz'])",
    "catalog_title": "div[class*='title'], h3, h2, h4, .text-lg, span[class*='text-']",
    "catalog_image": "img[src*='content-media.bonial.biz'], img[src*='bonial']",
    "catalog_link": "a[href*='/catalogue/']",
    "cookie_accept": "button:has-text('OK'), button:has-text('Accepter'), #onetrust-accept-btn-handler",
}

# Date pattern: matches dd/mm or dd/mm/yyyy
DATE_PATTERN = r"(\d{1,2}[/-]\d{1,2}(?:[/-]\d{2,4})?)"


def parse_bonial_dates(date_str: str) -> tuple[datetime, datetime]:
    """
    Parse Bonial date format to datetime objects.
    
    Args:
        date_str: Date string like "mar. 25/11 - lun. 08/12/2025"
    
    Returns:
        Tuple of (date_debut, date_fin)
    
    Raises:
        ValueError: If date format is invalid
    """
    # Find all dates in the string
    matches = re.findall(DATE_PATTERN, date_str)
    
    if not matches:
        # Fallback: try to find "Valable ... jours" or similar
        # For now, default to today + 7 days if no date found
        logger.warning(f"No dates found in '{date_str}', using default duration")
        return datetime.now(), datetime.now().replace(year=datetime.now().year + 1) # Valid for 1 year if unknown? No, better to be safe.
        # Actually, let's raise error to filter out bad data, or handle gracefully
        raise ValueError(f"Invalid date format: {date_str}")
    
    today = datetime.now()
    current_year = today.year
    
    parsed_dates = []
    for date_match in matches:
        # Normalize separators
        date_match = date_match.replace("-", "/")
        parts = date_match.split("/")
        
        day = int(parts[0])
        month = int(parts[1])
        year = int(parts[2]) if len(parts) > 2 else current_year
        
        # Handle 2-digit years
        if year < 100:
            year += 2000
            
        # Handle year rollover (e.g. in Dec, date is Jan)
        if len(parts) == 2: # No year specified
            if month < today.month - 3: # Date is in past months -> likely next year
                year += 1
            elif month > today.month + 3: # Date is far in future -> likely current year (or previous if looking at old catalogs)
                pass
                
        try:
            parsed_dates.append(datetime(year, month, day))
        except ValueError:
            continue
            
    if not parsed_dates:
        raise ValueError("No valid dates parsed")
        
    if len(parsed_dates) >= 2:
        return min(parsed_dates), max(parsed_dates)
    elif len(parsed_dates) == 1:
        # If only one date, assume it's end date if it's in the future
        date = parsed_dates[0]
        if date > today:
            return today, date
        else:
            return date, date # Expired or start date? Assume start
    
    return parsed_dates[0], parsed_dates[0]


def compute_catalog_hash(enseigne_id: int, titre: str, date_debut: datetime) -> str:
    """
    Compute SHA256 hash for duplicate detection.
    
    Args:
        enseigne_id: ID of the enseigne
        titre: Catalog title
        date_debut: Start date
    
    Returns:
        SHA256 hash string
    """
    content = f"{enseigne_id}|{titre}|{date_debut.isoformat()}"
    return hashlib.sha256(content.encode()).hexdigest()


async def accept_cookies(page: Page) -> None:
    """Accept cookie consent banner if present."""
    try:
        await page.click(BONIAL_SELECTORS["cookie_accept"], timeout=3000)
        logger.debug("Accepted cookies")
        await asyncio.sleep(1)
    except Exception:
        logger.debug("No cookie banner found or already accepted")


async def scrape_catalog_list(
    page: Page,
    enseigne: Enseigne
) -> list[dict[str, Any]]:
    """
    Scrape the list of catalogs for an ens enseigne from Bonial.
    
    Args:
        page: Playwright page object
        enseigne: Enseigne object
    
    Returns:
        List of catalog data dictionaries
    """
    url = f"https://www.bonial.fr/Enseignes/{enseigne.slug_bonial}"
    logger.info(f"Scraping catalog list for {enseigne.nom} from {url}")
    
    await page.goto(url, wait_until="networkidle")
    await accept_cookies(page)
    
    # Wait for catalog cards to load
    try:
        await page.wait_for_selector(BONIAL_SELECTORS["catalog_card"], timeout=10000)
    except Exception as e:
        logger.error(f"No catalog cards found for {enseigne.nom}: {e}")
        return []
    
    # Extract all catalog cards
    cards = await page.query_selector_all(BONIAL_SELECTORS["catalog_card"])
    logger.info(f"Found {len(cards)} catalog cards for {enseigne.nom}")
    
    catalogues = []
    
    for idx, card in enumerate(cards):
        try:
            # Extract title
            title_el = await card.query_selector(BONIAL_SELECTORS["catalog_title"])
            titre = await title_el.inner_text() if title_el else "Catalogue"
            
            # Extract dates - look for any element containing date pattern
            dates_text = await card.inner_text()
            
            # Extract image
            image_el = await card.query_selector(BONIAL_SELECTORS["catalog_image"])
            image_url = await image_el.get_attribute("src") if image_el else None
            if image_url and image_url.startswith("//"):
                image_url = "https:" + image_url
            
            # Extract link - try multiple strategies
            # Strategy 1: The card itself is a link
            catalogue_url = await card.get_attribute("href")
            
            # Strategy 2: Look for link inside
            if not catalogue_url:
                link_el = await card.query_selector(BONIAL_SELECTORS["catalog_link"])
                if link_el:
                    catalogue_url = await link_el.get_attribute("href")
            
            # Make URL absolute if relative
            if catalogue_url and not catalogue_url.startswith("http"):
                catalogue_url = f"https://www.bonial.fr{catalogue_url}"
            
            # Validate data
            has_url = bool(catalogue_url)
            has_image = bool(image_url)
            
            # Try to parse dates, but be lenient
            date_debut, date_fin = datetime.now(), datetime.now()
            try:
                date_debut, date_fin = parse_bonial_dates(dates_text)
                has_dates = True
            except ValueError:
                has_dates = False
                # If we have URL and Image, we might still want it, but maybe mark as "dates unknown"
                # For now, let's require dates or default to 1 week validity if title looks like a promo
                if "semaine" in dates_text.lower() or "valable" in dates_text.lower():
                     date_fin = datetime.now().replace(day=datetime.now().day + 7) # Rough approx
            
            if has_url and has_image:
                catalogues.append({
                    "titre": titre.strip(),
                    "date_debut": date_debut,
                    "date_fin": date_fin,
                    "image_couverture_url": image_url,
                    "catalogue_url": catalogue_url,
                })
                logger.debug(f"Extracted catalog: {titre}")
            else:
                logger.warning(f"Incomplete data for catalog {idx}: title={titre}, dates={has_dates}, image={has_image}, url={has_url}")
        
        except Exception as e:
            logger.error(f"Error extracting catalog {idx} for {enseigne.nom}: {e}")
            continue
    
    logger.info(f"Successfully extracted {len(catalogues)} catalogs for {enseigne.nom}")
    return catalogues


async def scrape_catalog_pages(page: Page, catalogue_url: str) -> list[dict[str, Any]]:
    """
    Scrape all pages of a catalog from the Bonial viewer.
    
    Args:
        page: Playwright page object
        catalogue_url: URL of the catalog viewer
    
    Returns:
        List of page data dictionaries
    """
    logger.info(f"Scraping catalog pages from {catalogue_url}")
    
    await page.goto(catalogue_url, wait_until="networkidle")
    await asyncio.sleep(2)  # Wait for viewer to initialize
    
    # Try to close any popup/modal
    try:
        await page.click("button:has-text('Continuer'), button:has-text('Fermer')", timeout=2000)
        await asyncio.sleep(1)
    except Exception:
        pass
    
    # Find all images from content-media.bonial.biz
    images = await page.query_selector_all("img[src*='content-media.bonial.biz']")
    
    if not images:
        logger.warning(f"No images found in catalog viewer: {catalogue_url}")
        return []
    
    # Extract unique image URLs (filter duplicates and thumbnails)
    seen_urls = set()
    pages = []
    
    for idx, img in enumerate(images):
        try:
            src = await img.get_attribute("src")
            
            if src and src not in seen_urls:
                # Filter out blurred/low-res images if possible
                # Full res images are typically larger
                width = await img.evaluate("el => el.naturalWidth")
                height = await img.evaluate("el => el.naturalHeight")
                
                # Skip very small images (likely thumbnails)
                if width < 200 or height < 200:
                    continue
                
                seen_urls.add(src)
                pages.append({
                    "numero_page": len(pages) + 1,
                    "image_url": src,
                    "largeur": width,
                    "hauteur": height,
                })
        
        except Exception as e:
            logger.debug(f"Error processing image {idx}: {e}")
            continue
    
    logger.info(f"Found {len(pages)} pages in catalog")
    return pages


async def scrape_enseigne(
    enseigne: Enseigne,
    db: Session,
    browser: Browser | None = None
) -> ScrapingLog:
    """
    Scrape all catalogs for a specific enseigne.
    
    Args:
        enseigne: Enseigne to scrape
        db: Database session
        browser: Optional existing browser instance
    
    Returns:
        ScrapingLog object with execution details
    """
    start_time = datetime.now()
    log = ScrapingLog(
        enseigne_id=enseigne.id,
        statut="error",  # Will be updated
        catalogues_trouves=0,
        catalogues_nouveaux=0,
        catalogues_mis_a_jour=0,
    )
    
    own_browser = browser is None
    
    try:
        # Create browser if not provided
        if own_browser:
            p = await async_playwright().start()
            browser = await p.chromium.launch(headless=True)
        
        page = await browser.new_page()
        
        # Set realistic user agent
        await page.set_extra_http_headers({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
        })
        
        # Scrape catalog list
        catalogues_data = await scrape_catalog_list(page, enseigne)
        log.catalogues_trouves = len(catalogues_data)
        
        if not catalogues_data:
            log.statut = "success"
            log.message_erreur = "No catalogs found (may be normal)"
            await page.close()
            return log
        
        # Process each catalog
        for cat_data in catalogues_data:
            try:
                # Compute hash for duplicate detection
                content_hash = compute_catalog_hash(
                    enseigne.id,
                    cat_data["titre"],
                    cat_data["date_debut"]
                )
                
                # Check if catalog already exists
                existing = db.query(Catalogue).filter_by(content_hash=content_hash).first()
                
                if existing:
                    logger.debug(f"Catalog already exists: {cat_data['titre']}")
                    continue
                
                # Scrape catalog pages
                await asyncio.sleep(3)  # Respectful delay
                pages_data = await scrape_catalog_pages(page, cat_data["catalogue_url"])
                
                # Create new catalog
                catalogue = Catalogue(
                    enseigne_id=enseigne.id,
                    titre=cat_data["titre"],
                    date_debut=cat_data["date_debut"],
                    date_fin=cat_data["date_fin"],
                    image_couverture_url=cat_data["image_couverture_url"],
                    catalogue_url=cat_data["catalogue_url"],
                    nombre_pages=len(pages_data),
                    content_hash=content_hash,
                    statut="actif" if cat_data["date_fin"] >= datetime.now() else "termine",
                )
                
                db.add(catalogue)
                db.flush()  # Get catalogue.id
                
                # Add pages
                for page_data in pages_data:
                    cat_page = CataloguePage(
                        catalogue_id=catalogue.id,
                        **page_data
                    )
                    db.add(cat_page)
                
                log.catalogues_nouveaux += 1
                logger.info(f"Created catalog: {cat_data['titre']} ({len(pages_data)} pages)")
            
            except Exception as e:
                logger.error(f"Error processing catalog {cat_data.get('titre')}: {e}")
                continue
        
        await page.close()
        
        # Update status
        log.statut = "success" if log.catalogues_nouveaux > 0 else "partial"
        db.commit()
    
    except Exception as e:
        logger.error(f"Error scraping enseigne {enseigne.nom}: {e}")
        log.statut = "error"
        log.message_erreur = str(e)
        db.rollback()
    
    finally:
        if own_browser and browser:
            await browser.close()
        
        # Record duration
        log.duree_secondes = (datetime.now() - start_time).total_seconds()
        db.add(log)
        db.commit()
    
    return log


async def scrape_all_enseignes(db: Session) -> list[ScrapingLog]:
    """
    Scrape all active enseignes.
    Uses Browserless service via WebSocket.
    
    Args:
        db: Database session
    
    Returns:
        List of ScrapingLog objects
    """
    import os
    
    enseignes = db.query(Enseigne).filter_by(is_active=True).all()
    logger.info(f"Starting scraping for {len(enseignes)} active enseignes")
    
    logs = []
    
    # Get Browserless URL from environment
    browserless_url = os.environ.get("BROWSERLESS_URL", "ws://browserless:3000")
    logger.info(f"Connecting to Browserless at {browserless_url}")
    
    async with async_playwright() as p:
        # Connect to Browserless instead of launching local browser
        browser = await p.chromium.connect_over_cdp(browserless_url)
        
        for enseigne in enseignes:
            try:
                await asyncio.sleep(2)  # Delay between enseignes
                log = await scrape_enseigne(enseigne, db, browser)
                logs.append(log)
            except Exception as e:
                logger.error(f"Failed to scrape {enseigne.nom}: {e}")
        
        await browser.close()
    
    logger.info(f"Scraping complete: {len(logs)} enseignes processed")
    return logs
