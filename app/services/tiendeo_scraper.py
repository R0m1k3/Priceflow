"""
Tiendeo.fr Scraper Service

Scrapes promotional catalogs from Tiendeo.fr for configured enseignes.
Much simpler structure than Bonial - catalog cards are clearly defined with direct links.
"""

import asyncio
import hashlib
import logging
import re
import os
from datetime import datetime, timedelta
from typing import Any

from playwright.async_api import async_playwright, Page, Browser
from sqlalchemy.orm import Session

from app.models import Enseigne, Catalogue, CataloguePage, ScrapingLog

logger = logging.getLogger(__name__)

# Tiendeo site base URL
TIENDEO_BASE_URL = "https://www.tiendeo.fr"

# Date pattern for Tiendeo: "Expire le 31/12" or "mar. 25/11 - lun. 08/12"
DATE_PATTERN = r"(\d{1,2}[/-]\d{1,2}(?:[/-]\d{2,4})?)"


def parse_tiendeo_dates(date_str: str) -> tuple[datetime, datetime]:
    """
    Parse Tiendeo date format to datetime objects.
    
    Args:
        date_str: Date string like "Expire le 31/12" or "mar. 25/11 - lun. 08/12"
    
    Returns:
        Tuple of (date_debut, date_fin)
    """
    matches = re.findall(DATE_PATTERN, date_str)
    
    if not matches:
        logger.warning(f"No dates found in '{date_str}', using default duration")
        raise ValueError(f"Invalid date format: {date_str}")
    
    today = datetime.now()
    current_year = today.year
    
    parsed_dates = []
    for date_match in matches:
        date_match = date_match.replace("-", "/")
        parts = date_match.split("/")
        
        day = int(parts[0])
        month = int(parts[1])
        year = int(parts[2]) if len(parts) > 2 else current_year
        
        if year < 100:
            year += 2000
            
        # Handle year rollover
        if len(parts) == 2:
            if month < today.month - 3:
                year += 1
                
        try:
            parsed_dates.append(datetime(year, month, day))
        except ValueError:
            continue
            
    if not parsed_dates:
        raise ValueError("No valid dates parsed")
        
    if len(parsed_dates) >= 2:
        return min(parsed_dates), max(parsed_dates)
    elif len(parsed_dates) == 1:
        # If only one date (expire date), use today as start
        return today, parsed_dates[0]
    
    return parsed_dates[0], parsed_dates[0]


def compute_catalog_hash(enseigne_id: int, titre: str, date_debut: datetime) -> str:
    """Compute SHA256 hash for duplicate detection."""
    content = f"{enseigne_id}|{titre}|{date_debut.isoformat()}"
    return hashlib.sha256(content.encode()).hexdigest()


async def scrape_catalog_list(page: Page, enseigne: Enseigne) -> list[dict[str, Any]]:
    """Scrape the list of catalogs for an enseigne from Tiendeo."""
    # Tiendeo uses store URLs like: /Magasins/{city}/{enseigne-slug}
    # We'll use Nancy as default city for now
    url = f"{TIENDEO_BASE_URL}/Magasins/nancy/{enseigne.slug_bonial.lower()}"
    logger.info(f"Scraping catalog list for {enseigne.nom} from {url}")
    
    await page.goto(url, wait_until="networkidle")
    await asyncio.sleep(2)  # Wait for dynamic content
    
    # Extract catalog data using JavaScript
    catalogs_data = await page.evaluate("""
        () => {
            const results = [];
            
            // Find all links to catalog pages (format: /Catalogues/{id})
            const catalogLinks = document.querySelectorAll('a[href*="/Catalogues/"]');
            
            catalogLinks.forEach((link) => {
                const href = link.href;
                const catalogId = href.split('/Catalogues/')[1];
                
                if (!catalogId) return;
                
                // Extract title from link text or nearby heading
                let title = link.textContent.trim();
                
                // Try to find h3 or h4 near this link for better title
                const parentContainer = link.closest('div, section, article');
                if (parentContainer) {
                    const heading = parentContainer.querySelector('h3, h4, h2');
                    if (heading && heading.textContent.trim().length > title.length) {
                        title = heading.textContent.trim();
                    }
                }
                
                // Look for image in the same container
                let imgSrc = null;
                if (parentContainer) {
                    const img = parentContainer.querySelector('img');
                    if (img) {
                        imgSrc = img.src || img.getAttribute('data-src') || img.getAttribute('srcset')?.split(' ')[0];
                    }
                }
                
                // Extract date information from container text
                const containerText = parentContainer ? parentContainer.textContent : link.textContent;
                
                // Avoid duplicates
                if (!results.some(r => r.url === href)) {
                    results.push({
                        title: title,
                        url: href,
                        image: imgSrc,
                        containerText: containerText.substring(0, 300),  // For date parsing
                        catalogId: catalogId
                    });
                }
            });
            
            return results;
        }
    """)
    
    logger.info(f"Found {len(catalogs_data)} catalog links for {enseigne.nom}")
    
    catalogues = []
    
    for idx, cat_data in enumerate(catalogs_data):
        try:
            titre = cat_data.get('title', 'Catalogue')
            image_url = cat_data.get('image')
            catalogue_url = cat_data.get('url')
            container_text = cat_data.get('containerText', '')
            
            if not catalogue_url:
                logger.warning(f"Skipping catalog {idx}: missing URL")
                continue
            
            # Clean title - remove extra info like distances, "Gifi", etc.
            titre = titre.replace('Gifi', '').replace('Action', '').replace('Centrakor', '')
            titre = re.sub(r'\d+\.\d+\s*km', '', titre)  # Remove "3.2 km"
            titre = re.sub(r'Nancy', '', titre, flags=re.IGNORECASE)
            titre = re.sub(r'Expire\s+le.*', '', titre)  # Remove expire info from title
            titre = titre.strip()
            
            # Skip if title is empty or too short
            if len(titre) < 3:
                logger.warning(f"Skipping catalog {idx}: title too short after cleaning")
                continue
            
            # Ensure absolute URL
            if image_url and image_url.startswith('//'):
                image_url = 'https:' + image_url
            
            # Parse dates from container text
            date_debut, date_fin = datetime.now(), datetime.now() + timedelta(days=30)
            try:
                date_debut, date_fin = parse_tiendeo_dates(container_text)
            except ValueError:
                # Default to 30 days validity
                logger.debug(f"Could not parse dates for '{titre}', using 30 days default")
            
            catalogues.append({
                "titre": titre,
                "date_debut": date_debut,
                "date_fin": date_fin,
                "image_couverture_url": image_url or "",
                "catalogue_url": catalogue_url,
            })
            logger.info(f"Extracted catalog: {titre}")
        
        except Exception as e:
            logger.error(f"Error processing catalog {idx} for {enseigne.nom}: {e}")
            continue
    
    logger.info(f"Successfully extracted {len(catalogues)} catalogs for {enseigne.nom}")
    return catalogues


async def scrape_catalog_pages(page: Page, catalogue_url: str) -> list[dict[str, Any]]:
    """Scrape all pages of a catalog from the Tiendeo viewer."""
    logger.info(f"Scraping catalog pages from {catalogue_url}")
    
    await page.goto(catalogue_url, wait_until="networkidle")
    await asyncio.sleep(3)  # Wait for viewer to load
    
    # Find all catalog page images
    images = await page.query_selector_all("img[src*='tiendeo'], img[src*='cdn']")
    
    if not images:
        logger.warning(f"No images found in catalog viewer: {catalogue_url}")
        return []
    
    seen_urls = set()
    pages = []
    
    for idx, img in enumerate(images):
        try:
            src = await img.get_attribute("src")
            
            if src and src not in seen_urls:
                width = await img.evaluate("el => el.naturalWidth")
                height = await img.evaluate("el => el.naturalHeight")
                
                # Skip small images (thumbnails)
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


async def scrape_enseigne(enseigne: Enseigne, db: Session, browser: Browser | None = None) -> ScrapingLog:
    """Scrape all catalogs for a specific enseigne from Tiendeo."""
    start_time = datetime.now()
    log = ScrapingLog(
        enseigne_id=enseigne.id,
        statut="error",
        catalogues_trouves=0,
        catalogues_nouveaux=0,
        catalogues_mis_a_jour=0,
    )
    
    own_browser = browser is None
    
    try:
        if own_browser:
            browserless_url = os.environ.get("BROWSERLESS_URL", "ws://browserless:3000")
            async with async_playwright() as p:
                browser = await p.chromium.connect_over_cdp(browserless_url)
        
        page = await browser.new_page()
        
        await page.set_extra_http_headers({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        })
        
        catalogues_data = await scrape_catalog_list(page, enseigne)
        log.catalogues_trouves = len(catalogues_data)
        
        if not catalogues_data:
            log.statut = "success"
            log.message_erreur = "No catalogs found (may be normal)"
            await page.close()
            return log
        
        for cat_data in catalogues_data:
            try:
                content_hash = compute_catalog_hash(
                    enseigne.id,
                    cat_data["titre"],
                    cat_data["date_debut"]
                )
                
                existing = db.query(Catalogue).filter_by(content_hash=content_hash).first()
                
                if existing:
                    logger.debug(f"Catalog already exists: {cat_data['titre']}")
                    continue
                
                await asyncio.sleep(2)  # Respectful delay
                pages_data = await scrape_catalog_pages(page, cat_data["catalogue_url"])
                
                catalogue = Catalogue(
                    enseigne_id=enseigne.id,
                    titre=cat_data["titre"],
                    date_debut=cat_data["date_debut"],
                    date_fin=cat_data["date_fin"],
                    image_couverture_url=cat_data["image_couverture_url"],
                    catalogue_url=cat_data["catalogue_url"],
                    statut="actif",
                    nombre_pages=len(pages_data),
                    content_hash=content_hash,
                )
                db.add(catalogue)
                db.flush()
                
                for page_data in pages_data:
                    catalogue_page = CataloguePage(
                        catalogue_id=catalogue.id,
                        numero_page=page_data["numero_page"],
                        image_url=page_data["image_url"],
                        largeur=page_data["largeur"],
                        hauteur=page_data["hauteur"],
                    )
                    db.add(catalogue_page)
                
                log.catalogues_nouveaux += 1
                logger.info(f"Added new catalog: {cat_data['titre']}")
                
            except Exception as e:
                logger.error(f"Error processing catalog: {e}")
                continue
        
        db.commit()
        log.statut = "success"
        await page.close()
        
    except Exception as e:
        logger.error(f"Error scraping {enseigne.nom}: {e}")
        log.statut = "error"
        log.message_erreur = str(e)
        db.rollback()
    
    finally:
        if own_browser and browser:
            await browser.close()
    
    log.duree_secondes = (datetime.now() - start_time).total_seconds()
    db.add(log)
    db.commit()
    
    return log


async def scrape_all_enseignes(db: Session) -> list[ScrapingLog]:
    """Scrape all active enseignes from Tiendeo."""
    enseignes = db.query(Enseigne).filter_by(is_active=True).all()
    logger.info(f"Starting Tiendeo scraping for {len(enseignes)} active enseignes")
    
    logs = []
    
    browserless_url = os.environ.get("BROWSERLESS_URL", "ws://browserless:3000")
    logger.info(f"Connecting to Browserless at {browserless_url}")
    
    async with async_playwright() as p:
        browser = await p.chromium.connect_over_cdp(browserless_url)
        
        for enseigne in enseignes:
            try:
                await asyncio.sleep(2)
                log = await scrape_enseigne(enseigne, db, browser)
                logs.append(log)
            except Exception as e:
                logger.error(f"Failed to scrape {enseigne.nom}: {e}")
        
        await browser.close()
    
    logger.info(f"Tiendeo scraping complete: {len(logs)} enseignes processed")
    return logs
