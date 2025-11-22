"""
Direct Search Service - Recherche directement sur les sites e-commerce
Au lieu d'utiliser un moteur de recherche externe, scrape les pages de recherche de chaque site.
"""

import asyncio
import logging
import re
from urllib.parse import quote_plus, urljoin, urlparse

import httpx
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)


class SearchResult:
    """Résultat de recherche"""

    def __init__(self, url: str, title: str, snippet: str, source: str):
        self.url = url
        self.title = title
        self.snippet = snippet
        self.source = source

    def __repr__(self):
        return f"SearchResult(url={self.url}, title={self.title[:30]}...)"


# Configuration des sites avec leurs sélecteurs par défaut
DEFAULT_SITE_CONFIGS = {
    "amazon.fr": {
        "search_url": "https://www.amazon.fr/s?k={query}",
        "product_selector": "div[data-component-type='s-search-result'] a.a-link-normal[href*='/dp/']",
        "title_selector": "span.a-text-normal",
    },
    "amazon.com": {
        "search_url": "https://www.amazon.com/s?k={query}",
        "product_selector": "div[data-component-type='s-search-result'] a.a-link-normal[href*='/dp/']",
        "title_selector": "span.a-text-normal",
    },
    "action.com": {
        "search_url": "https://www.action.com/fr-fr/search/?q={query}",
        "product_selector": "a.product-card__link",
        "title_selector": ".product-card__title",
    },
    "fnac.com": {
        "search_url": "https://www.fnac.com/SearchResult/ResultList.aspx?Search={query}",
        "product_selector": "a.Article-title",
        "title_selector": "a.Article-title",
    },
    "cdiscount.com": {
        "search_url": "https://www.cdiscount.com/search/10/{query}.html",
        "product_selector": "a.prdtBImg",
        "title_selector": ".prdtTit",
    },
    "darty.com": {
        "search_url": "https://www.darty.com/nav/recherche?text={query}",
        "product_selector": "a.product-card__link",
        "title_selector": ".product-card__title",
    },
    "boulanger.com": {
        "search_url": "https://www.boulanger.com/resultats?tr={query}",
        "product_selector": "a.product-list__link",
        "title_selector": ".product-list__title",
    },
}


async def search(
    query: str,
    sites: list[dict],
    max_results: int = 20,
    timeout: float = 15.0,
) -> list[SearchResult]:
    """
    Recherche directement sur les sites e-commerce.

    Args:
        query: Terme de recherche
        sites: Liste de dicts avec {domain, search_url, product_link_selector, name}
        max_results: Nombre maximum de résultats
        timeout: Timeout par requête

    Returns:
        Liste de SearchResult
    """
    if not sites:
        logger.warning("Aucun site configuré pour la recherche")
        return []

    all_results = []
    results_per_site = max(5, max_results // len(sites))

    # Rechercher sur chaque site en parallèle
    tasks = []
    for site in sites:
        task = asyncio.create_task(
            _search_site(query, site, results_per_site, timeout)
        )
        tasks.append(task)

    results = await asyncio.gather(*tasks, return_exceptions=True)

    for site, result in zip(sites, results):
        if isinstance(result, Exception):
            logger.error(f"Erreur recherche sur {site.get('domain')}: {result}")
            continue
        if result:
            all_results.extend(result)

    logger.info(f"Recherche directe: {len(all_results)} résultats totaux")
    return all_results[:max_results]


async def _search_site(
    query: str,
    site: dict,
    max_results: int,
    timeout: float,
) -> list[SearchResult]:
    """Recherche sur un site spécifique"""
    domain = site.get("domain", "").lower()
    search_url = site.get("search_url") or _get_default_search_url(domain)
    product_selector = site.get("product_link_selector") or _get_default_product_selector(domain)
    site_name = site.get("name", domain)

    if not search_url:
        logger.warning(f"Pas d'URL de recherche configurée pour {domain}")
        return []

    # Construire l'URL de recherche
    encoded_query = quote_plus(query)
    final_url = search_url.replace("{query}", encoded_query)

    logger.info(f"Recherche directe sur {domain}: {final_url}")

    try:
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
            response = await client.get(
                final_url,
                headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
                    "Accept-Language": "fr-FR,fr;q=0.9,en;q=0.8",
                    "Accept-Encoding": "gzip, deflate, br",
                    "DNT": "1",
                    "Connection": "keep-alive",
                    "Upgrade-Insecure-Requests": "1",
                },
            )
            response.raise_for_status()

            # Parser le HTML
            soup = BeautifulSoup(response.text, "html.parser")
            results = []

            # Extraire les liens produits
            if product_selector:
                links = soup.select(product_selector)
            else:
                # Fallback: chercher tous les liens qui ressemblent à des produits
                links = _find_product_links(soup, domain)

            logger.info(f"{domain}: {len(links)} liens produits trouvés")

            seen_urls = set()
            for link in links[:max_results * 2]:  # Prendre plus pour filtrer
                href = link.get("href", "")
                if not href:
                    continue

                # Construire l'URL complète
                if href.startswith("/"):
                    href = f"https://{domain}{href}"
                elif not href.startswith("http"):
                    href = urljoin(final_url, href)

                # Nettoyer l'URL
                href = _clean_product_url(href)

                # Éviter les doublons
                if href in seen_urls:
                    continue
                seen_urls.add(href)

                # Vérifier que c'est bien un lien vers ce domaine
                url_domain = _extract_domain(href)
                if domain not in url_domain:
                    continue

                # Extraire le titre
                title = _extract_title(link)
                if not title or len(title) < 3:
                    continue

                results.append(SearchResult(
                    url=href,
                    title=title,
                    snippet="",
                    source=domain,
                ))

                if len(results) >= max_results:
                    break

            logger.info(f"{domain}: {len(results)} résultats extraits")
            return results

    except httpx.TimeoutException:
        logger.error(f"Timeout lors de la recherche sur {domain}")
        return []
    except httpx.HTTPStatusError as e:
        logger.error(f"Erreur HTTP {e.response.status_code} sur {domain}")
        return []
    except Exception as e:
        logger.error(f"Erreur lors de la recherche sur {domain}: {e}")
        return []


def _get_default_search_url(domain: str) -> str | None:
    """Retourne l'URL de recherche par défaut pour un domaine"""
    # Chercher une correspondance exacte ou partielle
    for key, config in DEFAULT_SITE_CONFIGS.items():
        if key in domain or domain in key:
            return config.get("search_url")
    return None


def _get_default_product_selector(domain: str) -> str | None:
    """Retourne le sélecteur de produits par défaut pour un domaine"""
    for key, config in DEFAULT_SITE_CONFIGS.items():
        if key in domain or domain in key:
            return config.get("product_selector")
    return None


def _find_product_links(soup: BeautifulSoup, domain: str) -> list:
    """Trouve les liens produits de manière générique"""
    links = []

    # Patterns communs pour les liens produits
    patterns = [
        "a[href*='/product']",
        "a[href*='/p/']",
        "a[href*='/dp/']",
        "a[href*='/item']",
        "a[href*='/article']",
        "a.product",
        "a.product-link",
        "a.product-card",
        ".product a",
        ".product-card a",
        ".product-tile a",
        ".item a",
    ]

    for pattern in patterns:
        found = soup.select(pattern)
        if found:
            links.extend(found)

    # Dédupliquer
    seen = set()
    unique_links = []
    for link in links:
        href = link.get("href", "")
        if href and href not in seen:
            seen.add(href)
            unique_links.append(link)

    return unique_links


def _extract_title(element) -> str:
    """Extrait le titre d'un élément"""
    # Essayer différentes méthodes
    title = element.get("title", "")
    if title:
        return title.strip()

    # Texte de l'élément
    text = element.get_text(strip=True)
    if text and len(text) > 3:
        return text[:200]

    # Attribut aria-label
    label = element.get("aria-label", "")
    if label:
        return label.strip()

    # Image alt text
    img = element.find("img")
    if img:
        alt = img.get("alt", "")
        if alt:
            return alt.strip()

    return ""


def _clean_product_url(url: str) -> str:
    """Nettoie une URL produit (retire les paramètres de tracking, etc.)"""
    # Pour Amazon, simplifier l'URL
    if "amazon." in url and "/dp/" in url:
        match = re.search(r"(/dp/[A-Z0-9]{10})", url)
        if match:
            domain_match = re.search(r"(https?://[^/]+)", url)
            if domain_match:
                return domain_match.group(1) + match.group(1)

    return url


def _extract_domain(url: str) -> str:
    """Extrait le domaine d'une URL"""
    try:
        parsed = urlparse(url)
        domain = parsed.netloc.lower()
        if domain.startswith("www."):
            domain = domain[4:]
        return domain
    except Exception:
        return ""


async def health_check() -> bool:
    """Vérifie la connectivité"""
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get("https://www.google.com")
            return response.status_code == 200
    except Exception:
        return False
