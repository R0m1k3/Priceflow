"""
Bonial.fr Scraper Service

Scrapes promotional catalogs from Bonial.fr for configured enseignes.
Uses Playwright for browser automation.
"""

import asyncio
import hashlib
import logging
import re
import os
from datetime import datetime
from typing import Any

from playwright.async_api import async_playwright, Page, Browser
from sqlalchemy.orm import Session

from app.models import Enseigne, Catalogue, CataloguePage, ScrapingLog

logger = logging.getLogger(__name__)

# Bonial CSS selectors (based on browser inspection - updated for new structure)
BONIAL_SELECTORS = {
    "catalog_card": "div:has(> a[href*='/contentViewer/'])",
    "catalog_title": "a[href*='/contentViewer/'] h2",
    "catalog_image": "a[href*='/contentViewer/'] img",
    "catalog_link": "a[href*='/contentViewer/']",
    "cookie_accept": "button:has-text('Accepter')",
}

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
        date = parsed_dates[0]
        if date > today:
            return today, date
        else:
            return date, date
    
    return parsed_dates[0], parsed_dates[0]


def compute_catalog_hash(enseigne_id: int, titre: str, date_debut: datetime) -> str:
    """Compute SHA256 hash for duplicate detection."""
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


async def scrape_catalog_list(page: Page, enseigne: Enseigne) -> list[dict[str, Any]]:
    """Scrape the list of catalogs for an enseigne from Bonial."""
    url = f"https://www.bonial.fr/Enseignes/{enseigne.slug_bonial}"
    logger.info(f"Scraping catalog list for {enseigne.nom} from {url}")
    
    await page.goto(url, wait_until="networkidle")
    await accept_cookies(page)
    
    try:
        await page.wait_for_selector(BONIAL_SELECTORS["catalog_card"], timeout=10000)
    except Exception as e:
        logger.error(f"No catalog cards found for {enseigne.nom}: {e}")
        return []
    
    cards = await page.query_selector_all(BONIAL_SELECTORS["catalog_card"])
    logger.info(f"Found {len(cards)} catalog cards for {enseigne.nom}")
    
    catalogues = []
    
    for idx, card in enumerate(cards):
        try:
            title_el = await card.query_selector(BONIAL_SELECTORS["catalog_title"])
            titre = await title_el.inner_text() if title_el else "Catalogue"
            
            dates_text = await card.inner_text()
            
            image_el = await card.query_selector(BONIAL_SELECTORS["catalog_image"])
            image_url = await image_el.get_attribute("src") if image_el else None
            if image_url and image_url.startswith("//"):
                image_url = "https:" + image_url
            
            link_el = await card.query_selector(BONIAL_SELECTORS["catalog_link"])
            catalogue_url = await link_el.get_attribute("href") if link_el else None
            
            if catalogue_url and not catalogue_url.startswith("http"):
                catalogue_url = f"https://www.bonial.fr{catalogue_url}"
            
            # Validate URL
            if catalogue_url and ("adjust.com" in catalogue_url or "/Mobile" in catalogue_url):
                logger.debug(f"Skipping app/mobile link: {catalogue_url}")
                continue
            
            if catalogue_url and "/contentViewer/" not in catalogue_url:
                logger.debug(f"Skipping non-catalog URL: {catalogue_url}")
                continue
            
            # Filter generic titles
            if titre:
                lower_title = titre.lower()
                ignored_titles = [
                    "restez informé", "catalogues bazar", "toutes les offres",
                    "voir les offres", "téléchargez l'application", "newsletter"
                ]
                if any(ignored in lower_title for ignored in ignored_titles):
                    logger.info(f"Skipping generic/banner card: {titre}")
                    continue
            
            has_url = bool(catalogue_url)
            has_image = bool(image_url)
            
            date_debut, date_fin = datetime.now(), datetime.now()
            try:
                date_debut, date_fin = parse_bonial_dates(dates_text)
            except ValueError:
                if "semaine" in dates_text.lower() or "valable" in dates_text.lower():
                    date_fin = datetime.now().replace(day=datetime.now().day + 7)
            
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
                if not has_url:
                    logger.warning(f"Skipping card {idx} (No URL): {titre}")
                elif not has_image:
                    logger.warning(f"Skipping card {idx} (No Image): {titre}")
        
        except Exception as e:
            logger.error(f"Error extracting catalog {idx} for {enseigne.nom}: {e}")
            continue
    
    logger.info(f"Successfully extracted {len(catalogues)} catalogs for {enseigne.nom}")
    return catalogues


async def scrape_catalog_pages(page: Page, catalogue_url: str) -> list[dict[str, Any]]:
    """Scrape all pages of a catalog from the Bonial viewer."""
    logger.info(f"Scraping catalog pages from {catalogue_url}")
    
    await page.goto(catalogue_url, wait_until="networkidle")
    await asyncio.sleep(2)
    
    try:
        await page.click("button:has-text('Continuer'), button:has-text('Fermer')", timeout=2000)
        await asyncio.sleep(1)
    except Exception:
        pass
    
    images = await page.query_selector_all("img[src*='content-media.bonial.biz']")
    
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
    """Scrape all catalogs for a specific enseigne."""
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
                
                await asyncio.sleep(3)
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
    """Scrape all active enseignes. Uses Browserless service via WebSocket."""
    enseignes = db.query(Enseigne).filter_by(is_active=True).all()
    logger.info(f"Starting scraping for {len(enseignes)} active enseignes")
    
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
    
    logger.info(f"Scraping complete: {len(logs)} enseignes processed")
    return logs
