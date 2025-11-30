"""
Tiendeo.fr Scraper Service - Powered by Crawl4AI

Scrapes promotional catalogs from Tiendeo.fr for configured enseignes.
Uses Crawl4AI for intelligent content extraction instead of fragile CSS selectors.
"""

import asyncio
import hashlib
import logging
import re
from datetime import datetime, timedelta
from typing import Any

from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig, CacheMode
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.models import Enseigne, Catalogue, CataloguePage, ScrapingLog

logger = logging.getLogger(__name__)

# Tiendeo site base URL
TIENDEO_BASE_URL = "https://www.tiendeo.fr"

# Date pattern for Tiendeo: "Expire le 31/12" or "mar. 25/11 - lun. 08/12"
DATE_PATTERN = r"(\d{1,2}[/-]\d{1,2}(?:[/-]\d{2,4})?)"


# ============================================================================
# PYDANTIC SCHEMAS FOR EXTRACTION
# ============================================================================

class CatalogueCard(BaseModel):
    """Schema for catalog card extraction"""
    title: str = Field(description="Catalogue title")
    url: str = Field(description="Full URL to the catalogue viewer")
    image_url: str | None = Field(default=None, description="Cover image URL")
    date_text: str | None = Field(default=None, description="Date validity text")


class CataloguePageSchema(BaseModel):
    """Schema for catalog page image extraction"""
    page_number: int = Field(description="Page number in sequence")
    image_url: str = Field(description="Full resolution image URL")
    width: int | None = Field(default=None, description="Image width in pixels")
    height: int | None = Field(default=None, description="Image height in pixels")


# ============================================================================
# DATE PARSING
# ============================================================================

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


# ============================================================================
# SCRAPING FUNCTIONS
# ============================================================================

async def scrape_catalog_list(crawler: AsyncWebCrawler, enseigne: Enseigne) -> list[dict[str, Any]]:
    """Scrape the list of catalogs for an enseigne from Tiendeo using Crawl4AI."""
    # Tiendeo uses store URLs like: /Magasins/{city}/{enseigne-slug}
    url = f"{TIENDEO_BASE_URL}/Magasins/nancy/{enseigne.slug_bonial.lower()}"
    logger.info(f"Scraping catalog list for {enseigne.nom} from {url}")
    
    # Configure crawler for this page
    config = CrawlerRunConfig(
        cache_mode=CacheMode.BYPASS,
        wait_for_images=True,
        process_iframes=False,
        remove_overlay_elements=True,
        wait_until="networkidle",
    )
    
    result = await crawler.arun(url=url, config=config)
    
    if not result.success:
        logger.error(f"Failed to crawl {url}: {result.error_message}")
        return []
    
    # Extract catalog cards using JavaScript
    catalog_data = await crawler.crawler_strategy.execute_js(
        """
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
                    });
                }
            });
            
            return results;
        }
        """
    )
    
    logger.info(f"Found {len(catalog_data)} catalog links for {enseigne.nom}")
    
    catalogues = []
    
    for idx, cat_data in enumerate(catalog_data):
        try:
            titre = cat_data.get('title', 'Catalogue')
            image_url = cat_data.get('image')
            catalogue_url = cat_data.get('url')
            container_text = cat_data.get('containerText', '')
            
            if not catalogue_url:
                logger.warning(f"Skipping catalog {idx}: missing URL")
                continue
            
            # Clean title - remove extra info
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


async def scrape_catalog_pages(crawler: AsyncWebCrawler, catalogue_url: str) -> list[dict[str, Any]]:
    """Scrape all pages of a catalog from the Tiendeo viewer using Crawl4AI."""
    logger.info(f"Scraping catalog pages from {catalogue_url}")
    
    # Configure crawler to wait for images
    config = CrawlerRunConfig(
        cache_mode=CacheMode.BYPASS,
        wait_for_images=True,
        process_iframes=True,
        remove_overlay_elements=True,
        wait_until="networkidle",
        delay_before_return_html=3.0,  # Wait for viewer to fully load
    )
    
    result = await crawler.arun(url=catalogue_url, config=config)
    
    if not result.success:
        logger.error(f"Failed to crawl {catalogue_url}: {result.error_message}")
        return []
    
    # Extract catalog page images using JavaScript with intelligent filtering
    pages_data = await crawler.crawler_strategy.execute_js(
        """
        () => {
            const results = [];
            const seenUrls = new Set();
            
            // Find all images - prioritize those in viewer containers
            const allImages = document.querySelectorAll('img');
            
            allImages.forEach((img) => {
                // Get image source (try multiple attributes)
                let src = img.src || img.getAttribute('data-src');
                
                // Try srcset as fallback
                if (!src && img.srcset) {
                    const srcsetParts = img.srcset.split(',')[0].trim().split(' ');
                    src = srcsetParts[0];
                }
                
                if (!src || seenUrls.has(src)) return;
                
                // Skip obvious non-catalog images
                if (src.includes('logo') || src.includes('icon') || src.includes('avatar')) {
                    return;
                }
                
                // Get dimensions
                const width = img.naturalWidth || img.width;
                const height = img.naturalHeight || img.height;
                
                // Filter by dimensions - catalog pages are typically portrait and high-res
                // Minimum 400px width, aspect ratio close to 3:4 or similar
                if (width < 400 || height < 400) return;
                
                const aspectRatio = width / height;
                
                // Portrait images (0.5 to 0.9 ratio) - catalog pages are usually portrait
                if (aspectRatio > 0.5 && aspectRatio < 0.9) {
                    seenUrls.add(src);
                    results.push({
                        image_url: src,
                        width: width,
                        height: height,
                    });
                }
            });
            
            // Sort by area (largest first) to prioritize full resolution images
            results.sort((a, b) => (b.width * b.height) - (a.width * a.height));
            
            // Assign page numbers
            return results.map((item, index) => ({
                ...item,
                numero_page: index + 1,
            }));
        }
        """
    )
    
    logger.info(f"Found {len(pages_data)} pages in catalog")
    return pages_data


async def scrape_enseigne(enseigne: Enseigne, db: Session) -> ScrapingLog:
    """Scrape all catalogs for a specific enseigne from Tiendeo using Crawl4AI."""
    start_time = datetime.now()
    log = ScrapingLog(
        enseigne_id=enseigne.id,
        statut="error",
        catalogues_trouves=0,
        catalogues_nouveaux=0,
        catalogues_mis_a_jour=0,
    )
    
    try:
        # Configure browser for Crawl4AI
        browser_config = BrowserConfig(
            headless=True,
            verbose=False,
            extra_args=["--disable-gpu", "--no-sandbox", "--disable-dev-shm-usage"],
        )
        
        async with AsyncWebCrawler(config=browser_config) as crawler:
            catalogues_data = await scrape_catalog_list(crawler, enseigne)
            log.catalogues_trouves = len(catalogues_data)
            
            if not catalogues_data:
                log.statut = "success"
                log.message_erreur = "No catalogs found (may be normal)"
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
                    pages_data = await scrape_catalog_pages(crawler, cat_data["catalogue_url"])
                    
                    if not pages_data:
                        logger.warning(f"No pages found for catalog: {cat_data['titre']}")
                        continue
                    
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
                            largeur=page_data.get("width"),
                            hauteur=page_data.get("height"),
                        )
                        db.add(catalogue_page)
                    
                    log.catalogues_nouveaux += 1
                    logger.info(f"Added new catalog: {cat_data['titre']} with {len(pages_data)} pages")
                    
                except Exception as e:
                    logger.error(f"Error processing catalog: {e}")
                    continue
            
            db.commit()
            log.statut = "success"
        
    except Exception as e:
        logger.error(f"Error scraping {enseigne.nom}: {e}")
        log.statut = "error"
        log.message_erreur = str(e)
        db.rollback()
    
    log.duree_secondes = (datetime.now() - start_time).total_seconds()
    db.add(log)
    db.commit()
    
    return log


async def scrape_all_enseignes(db: Session) -> list[ScrapingLog]:
    """Scrape all active enseignes from Tiendeo."""
    enseignes = db.query(Enseigne).filter_by(is_active=True).all()
    logger.info(f"Starting Tiendeo scraping for {len(enseignes)} active enseignes")
    
    logs = []
    
    for enseigne in enseignes:
        try:
            await asyncio.sleep(2)
            log = await scrape_enseigne(enseigne, db)
            logs.append(log)
        except Exception as e:
            logger.error(f"Failed to scrape {enseigne.nom}: {e}")
    
    logger.info(f"Tiendeo scraping complete: {len(logs)} enseignes processed")
    return logs
