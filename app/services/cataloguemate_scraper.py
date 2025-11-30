"""
Cataloguemate.fr Scraper Service

Scrapes promotional catalogs from Cataloguemate.fr.
Replaces Tiendeo scraper due to better reliability and simpler structure.
Refactored to use BrowserlessService for robust containerized scraping.
"""

import asyncio
import logging
import re
from datetime import datetime, timedelta
from typing import Any, Optional

from bs4 import BeautifulSoup
from sqlalchemy.orm import Session

from app.models import Enseigne, Catalogue, CataloguePage, ScrapingLog
from app.services.browserless_service import browserless_service

logger = logging.getLogger(__name__)

BASE_URL = "https://www.cataloguemate.fr"

async def scrape_catalog_list(enseigne: Enseigne) -> list[dict[str, Any]]:
    """
    Scrape the list of catalogs for an enseigne.
    We use a default city (Paris) because the main page often doesn't list catalogs directly.
    URL format: https://www.cataloguemate.fr/offres/paris/{enseigne_slug}/
    """
    slug = enseigne.slug_bonial.lower()
    # Handle specific slug mapping
    if enseigne.nom.lower() == "b&m":
        slug = "bm"
    elif enseigne.nom.lower() == "la foir'fouille":
        slug = "la-foirfouille"
    
    # Use Paris as default city to find national catalogs
    url = f"{BASE_URL}/offres/paris/{slug}/"
    logger.info(f"Scraping catalog list from: {url}")

    # Use browserless service to get content
    html_content, _ = await browserless_service.get_page_content(url)
    
    if not html_content:
        logger.error(f"Failed to fetch list {url}")
        return []

    soup = BeautifulSoup(html_content, 'html.parser')
    catalogs = []
    
    # Find all links that might be catalogs
    links = soup.find_all('a', href=True)
    seen_urls = set()
    
    logger.info(f"Found {len(links)} links on page {url}")
    
    for link in links:
        href = link['href']
        text = link.get_text(strip=True)
        
        # Normalize href
        if href.startswith(BASE_URL):
            href = href.replace(BASE_URL, "")
            
        # Debug log for potential candidates
        if slug in href:
            logger.debug(f"Checking link: {href}")
            
        # Filter: 
        # 1. Must contain the slug (or be a catalog link for this enseigne)
        # 2. Must NOT be a city search page (/offres/)
        # 3. Must NOT be a product search (/rechercher/)
        # 4. Should usually have a numeric ID at the end
        
        if f"/{slug}/" in href:
            if any(x in href for x in ["/offres/", "/magasins/", "/rechercher/", "page="]):
                logger.debug(f"  -> Rejected (invalid pattern): {href}")
                continue
                
            full_url = f"{BASE_URL}{href}"
            
            if full_url in seen_urls:
                continue
            
            # Check for numeric ID pattern which is typical for catalogs
            # e.g. -61130/
            if re.search(r'-\d+/?$', href) or "catalogue" in href.lower():
                catalogs.append({
                    'url': full_url,
                    'title': text or "Catalogue",
                })
                seen_urls.add(full_url)
                logger.info(f"Found catalog: {full_url}")
            else:
                logger.debug(f"  -> Rejected (no ID/catalogue keyword): {href}")

    logger.info(f"Total catalogs found: {len(catalogs)}")
    return catalogs

async def scrape_catalog_pages(catalog_url: str) -> list[dict[str, Any]]:
    """
    Scrape pages from a specific catalog.
    Iterates through ?page=1, ?page=2 etc.
    """
    pages = []
    page_num = 1
    max_pages = 100 # Safety limit
    
    while page_num <= max_pages:
        # Construct URL for specific page
        current_url = catalog_url if page_num == 1 else f"{catalog_url}?page={page_num}"
        
        logger.info(f"Scraping page {page_num}: {current_url}")
        
        # Use browserless service
        html_content, _ = await browserless_service.get_page_content(current_url)
        
        if not html_content:
            logger.warning(f"Failed to fetch page {page_num}")
            break
            
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # Find the main catalog image
        main_image_url = None
        max_area = 0
        
        all_imgs = soup.find_all('img')
        for img in all_imgs:
            src = img.get('src')
            if not src: continue
            
            # Skip common UI elements
            if any(x in src.lower() for x in ['logo', 'icon', 'facebook', 'twitter', 'instagram']):
                continue
                
            # Calculate area if dimensions exist
            width = img.get('width')
            height = img.get('height')
            area = 0
            if width and height:
                try:
                    area = int(width) * int(height)
                except:
                    pass
            
            # Heuristic: Catalog pages are usually large vertical images
            # Check src for keywords
            is_likely_catalog = any(k in src.lower() for k in ['page', 'flyer', 'catalog', 'upload', 'images'])
            
            # Logic:
            # 1. If keyword match AND decent size -> Strong candidate
            # 2. If no keyword match but HUGE size -> Candidate
            
            if is_likely_catalog:
                if area > max_area:
                    max_area = area
                    main_image_url = src
                elif area == 0 and not main_image_url:
                    main_image_url = src
            elif area > 100000: # Arbitrary large size (e.g. 300x333)
                if area > max_area:
                    max_area = area
                    main_image_url = src
        
        if main_image_url:
            # Ensure absolute URL
            if main_image_url.startswith("//"):
                main_image_url = "https:" + main_image_url
            elif main_image_url.startswith("/"):
                main_image_url = BASE_URL + main_image_url
                
            pages.append({
                'page_number': page_num,
                'image_url': main_image_url
            })
            logger.info(f"Found image for page {page_num}: {main_image_url}")
        else:
            logger.warning(f"No catalog image found on page {page_num}")
            # If we can't find an image, we might have reached the end or it's a bad page
            if page_num > 1:
                break
        
        # Check for pagination "Next" to know if we should continue
        if not main_image_url:
            break
            
        page_num += 1
        # Small delay handled by browserless service already, but adding a tiny one here
        await asyncio.sleep(0.5)

    return pages

async def scrape_enseigne(enseigne: Enseigne, db: Session) -> ScrapingLog:
    """Main entry point for scraping an enseigne"""
    start_time = datetime.now()
    log = ScrapingLog(
        enseigne_id=enseigne.id,
        statut="running",
        # date_execution is set automatically by default
        catalogues_trouves=0,
        catalogues_nouveaux=0,
        catalogues_mis_a_jour=0
    )
    db.add(log)
    db.commit()

    try:
        # 0. Test connection (Implicit in get_page_content, but good to log)
        logger.info(f"Starting scraping for {enseigne.nom} using Browserless...")

        # 1. Get list of catalogs
        catalogs_list = await scrape_catalog_list(enseigne)
        log.catalogues_trouves = len(catalogs_list)
        
        for cat_info in catalogs_list:
            # Check if catalog exists
            existing = db.query(Catalogue).filter(
                Catalogue.catalogue_url == cat_info['url']
            ).first()
            
            if existing:
                continue
                
            # 2. Scrape pages for new catalog
            pages = await scrape_catalog_pages(cat_info['url'])
            
            if not pages:
                continue
                
            # Create catalog entry
            new_cat = Catalogue(
                enseigne_id=enseigne.id,
                titre=cat_info['title'],
                catalogue_url=cat_info['url'],
                date_debut=datetime.now(), # Todo: extract real dates
                date_fin=datetime.now() + timedelta(days=14),
                image_couverture_url=pages[0]['image_url']
            )
            db.add(new_cat)
            db.commit()
            db.refresh(new_cat)
            
            # Add pages
            for page_data in pages:
                new_page = CataloguePage(
                    catalogue_id=new_cat.id,
                    numero_page=page_data['page_number'],
                    image_url=page_data['image_url'],
                )
                db.add(new_page)
            
            db.commit()
            log.catalogues_nouveaux += 1
            logger.info(f"Saved catalog '{new_cat.titre}' with {len(pages)} pages")
            
        log.statut = "success"
    except Exception as e:
        logger.error(f"Scraping failed: {e}")
        log.statut = "error"
        log.message_erreur = str(e)
    finally:
        # Calculate duration
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        log.duree_secondes = duration
        db.commit()
        
    return log

async def scrape_all_enseignes(db: Session) -> list[ScrapingLog]:
    """
    Scrape catalogs for all active enseignes.
    """
    logger.info("Starting scraping for all enseignes...")
    logs = []
    
    enseignes = db.query(Enseigne).filter(Enseigne.is_active == True).all()
    
    for enseigne in enseignes:
        try:
            log = await scrape_enseigne(enseigne, db)
            logs.append(log)
        except Exception as e:
            logger.error(f"Error scraping enseigne {enseigne.nom}: {e}")
            
    return logs
