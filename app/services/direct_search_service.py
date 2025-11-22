"""
Direct Search Service - Recherche sur les sites e-commerce via Browserless
Utilise Playwright/Browserless pour gérer JavaScript et contourner la détection de bots.
"""

import asyncio
import logging
import os
import re
from urllib.parse import quote_plus, urljoin, urlparse

from bs4 import BeautifulSoup
from playwright.async_api import async_playwright

logger = logging.getLogger(__name__)

BROWSERLESS_URL = os.getenv("BROWSERLESS_URL", "ws://browserless:3000")


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
        "product_selector": "div[data-component-type='s-search-result'] h2 a",
        "wait_selector": "div[data-component-type='s-search-result']",
    },
    "amazon.com": {
        "search_url": "https://www.amazon.com/s?k={query}",
        "product_selector": "div[data-component-type='s-search-result'] h2 a",
        "wait_selector": "div[data-component-type='s-search-result']",
    },
    "action.com": {
        "search_url": "https://www.action.com/fr-fr/search/?q={query}",
        "product_selector": "a.product-card__link, .product-card a, a[href*='/p/']",
        "wait_selector": ".product-card, .search-results",
    },
    "fnac.com": {
        "search_url": "https://www.fnac.com/SearchResult/ResultList.aspx?Search={query}",
        "product_selector": "a.Article-title, .Article-item a.js-minifa-title",
        "wait_selector": ".Article-item",
    },
    "cdiscount.com": {
        "search_url": "https://www.cdiscount.com/search/10/{query}.html",
        "product_selector": "a.prdtBImg, .prdtBILDetails a",
        "wait_selector": ".prdtBILDetails",
    },
    "darty.com": {
        "search_url": "https://www.darty.com/nav/recherche?text={query}",
        "product_selector": ".product-card a, a[href*='/product']",
        "wait_selector": ".product-card",
    },
    "boulanger.com": {
        "search_url": "https://www.boulanger.com/resultats?tr={query}",
        "product_selector": ".product-list__item a, a[href*='/ref/']",
        "wait_selector": ".product-list",
    },
    # Magasins discount français
    "stokomani.fr": {
        "search_url": "https://www.stokomani.fr/recherche?q={query}",
        "product_selector": "a.product-card, .product-item a, a[href*='/product']",
        "wait_selector": ".product-card, .product-item, .search-results",
    },
    "gifi.fr": {
        "search_url": "https://www.gifi.fr/catalogsearch/result/?q={query}",
        "product_selector": ".product-item a.product-item-link, a[href*='/produit/']",
        "wait_selector": ".product-item, .products-grid",
    },
    "bmstores.fr": {
        "search_url": "https://www.bmstores.fr/search?q={query}",
        "product_selector": "a.product-card, .product a, a[href*='/products/']",
        "wait_selector": ".product-card, .product-grid",
    },
    "centrakor.com": {
        "search_url": "https://www.centrakor.com/recherche?search={query}",
        "product_selector": "a.product-card, .product-item a",
        "wait_selector": ".product-card, .product-list",
    },
    "lafoirfouille.fr": {
        "search_url": "https://www.lafoirfouille.fr/recherche?q={query}",
        "product_selector": "a.product-item-link, .product-card a",
        "wait_selector": ".product-item, .products",
    },
    "tedi.fr": {
        "search_url": "https://www.tedi.fr/search?q={query}",
        "product_selector": "a.product-card, .product a",
        "wait_selector": ".product-card, .search-results",
    },
    "leclerc.fr": {
        "search_url": "https://www.e.leclerc/recherche?q={query}",
        "product_selector": "a.product-card, .product-tile a",
        "wait_selector": ".product-card, .products-grid",
    },
    "carrefour.fr": {
        "search_url": "https://www.carrefour.fr/s?q={query}",
        "product_selector": "a.product-card, .product-item a",
        "wait_selector": ".product-card, .product-list",
    },
    "auchan.fr": {
        "search_url": "https://www.auchan.fr/recherche?text={query}",
        "product_selector": "a.product-card, .product-tile a",
        "wait_selector": ".product-card, .products",
    },
}


async def search(
    query: str,
    sites: list[dict],
    max_results: int = 20,
    timeout: float = 30.0,
) -> list[SearchResult]:
    """
    Recherche sur les sites e-commerce via Browserless.

    Args:
        query: Terme de recherche
        sites: Liste de dicts avec {domain, search_url, product_link_selector, name}
        max_results: Nombre maximum de résultats
        timeout: Timeout par site

    Returns:
        Liste de SearchResult
    """
    if not sites:
        logger.warning("Aucun site configuré pour la recherche")
        return []

    all_results = []
    results_per_site = max(5, max_results // len(sites))

    # Rechercher sur chaque site en séquence (pour éviter de surcharger Browserless)
    for site in sites:
        try:
            results = await _search_site_browserless(query, site, results_per_site, timeout)
            all_results.extend(results)
            logger.info(f"Site {site.get('domain')}: {len(results)} résultats")
        except Exception as e:
            logger.error(f"Erreur recherche sur {site.get('domain')}: {e}")

        if len(all_results) >= max_results:
            break

    logger.info(f"Recherche Browserless: {len(all_results)} résultats totaux")
    return all_results[:max_results]


async def _search_site_browserless(
    query: str,
    site: dict,
    max_results: int,
    timeout: float,
) -> list[SearchResult]:
    """Recherche sur un site via Browserless (Playwright)"""
    raw_domain = site.get("domain", "").lower()
    # Nettoyer le domaine (enlever protocole, www, slash final)
    domain = _clean_domain(raw_domain)

    search_url = site.get("search_url") or _get_default_search_url(domain)
    product_selector = site.get("product_link_selector") or _get_default_product_selector(domain)
    wait_selector = _get_default_wait_selector(domain)

    if not search_url:
        logger.warning(f"Pas d'URL de recherche configurée pour {domain}")
        return []

    # Construire l'URL de recherche
    encoded_query = quote_plus(query)
    final_url = search_url.replace("{query}", encoded_query)

    logger.info(f"Recherche Browserless sur {domain}: {final_url}")

    try:
        async with async_playwright() as p:
            # Se connecter à Browserless
            browser = await p.chromium.connect_over_cdp(BROWSERLESS_URL)

            try:
                context = await browser.new_context(
                    viewport={"width": 1920, "height": 1080},
                    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                    locale="fr-FR",
                )
                page = await context.new_page()

                # Bloquer les ressources inutiles pour accélérer
                await page.route("**/*.{png,jpg,jpeg,gif,webp,svg,ico}", lambda route: route.abort())
                await page.route("**/analytics*", lambda route: route.abort())
                await page.route("**/tracking*", lambda route: route.abort())

                # Naviguer vers la page de recherche
                await page.goto(final_url, wait_until="domcontentloaded", timeout=int(timeout * 1000))

                # Attendre que les résultats se chargent
                if wait_selector:
                    try:
                        await page.wait_for_selector(wait_selector, timeout=10000)
                    except Exception:
                        logger.debug(f"Selector {wait_selector} non trouvé, on continue...")

                # Attendre un peu pour le JS
                await asyncio.sleep(2)

                # Extraire le HTML
                html_content = await page.content()

                await context.close()

            finally:
                await browser.close()

        # Parser le HTML avec BeautifulSoup
        soup = BeautifulSoup(html_content, "lxml")
        results = []
        seen_urls = set()

        # Trouver les liens produits
        if product_selector:
            # Essayer plusieurs sélecteurs séparés par virgule
            selectors = [s.strip() for s in product_selector.split(",")]
            links = []
            for sel in selectors:
                try:
                    found = soup.select(sel)
                    links.extend(found)
                except Exception:
                    continue
        else:
            links = _find_product_links(soup, domain)

        logger.info(f"{domain}: {len(links)} liens trouvés avec sélecteur")

        for link in links:
            href = link.get("href", "")
            if not href:
                continue

            # Construire l'URL complète
            if href.startswith("/"):
                href = f"https://{domain}{href}"
            elif not href.startswith("http"):
                href = urljoin(final_url, href)

            # Nettoyer l'URL
            href = _clean_product_url(href, domain)

            # Éviter les doublons
            if href in seen_urls:
                continue
            seen_urls.add(href)

            # Vérifier que c'est bien un lien vers ce domaine
            url_domain = _extract_domain(href)
            if domain not in url_domain and url_domain not in domain:
                continue

            # Filtrer les liens non-produits
            if _is_non_product_url(href):
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

    except Exception as e:
        logger.error(f"Erreur Browserless sur {domain}: {e}")
        return []


def _get_default_search_url(domain: str) -> str | None:
    """Retourne l'URL de recherche par défaut pour un domaine"""
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


def _get_default_wait_selector(domain: str) -> str | None:
    """Retourne le sélecteur d'attente par défaut pour un domaine"""
    for key, config in DEFAULT_SITE_CONFIGS.items():
        if key in domain or domain in key:
            return config.get("wait_selector")
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
        ".product a",
        ".product-card a",
        ".product-tile a",
    ]

    for pattern in patterns:
        try:
            found = soup.select(pattern)
            if found:
                links.extend(found)
        except Exception:
            continue

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
    if title and len(title) > 3:
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


def _clean_product_url(url: str, domain: str) -> str:
    """Nettoie une URL produit"""
    # Pour Amazon, simplifier l'URL
    if "amazon." in url and "/dp/" in url:
        match = re.search(r"(/dp/[A-Z0-9]{10})", url)
        if match:
            domain_match = re.search(r"(https?://[^/]+)", url)
            if domain_match:
                return domain_match.group(1) + match.group(1)

    return url.split("?")[0] if "?" in url else url


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


def _clean_domain(domain: str) -> str:
    """Nettoie un domaine (enlève protocole, www, slash final)"""
    if not domain:
        return ""

    domain = domain.strip().lower()

    # Enlever le protocole
    if domain.startswith("https://"):
        domain = domain[8:]
    elif domain.startswith("http://"):
        domain = domain[7:]

    # Enlever www.
    if domain.startswith("www."):
        domain = domain[4:]

    # Enlever le slash final
    domain = domain.rstrip("/")

    return domain


def _is_non_product_url(url: str) -> bool:
    """Vérifie si l'URL n'est pas une page produit"""
    non_product_patterns = [
        "/search", "/category", "/categories", "/brand", "/brands",
        "/help", "/contact", "/about", "/account", "/cart", "/checkout",
        "/login", "/register", "/wishlist", "/compare", "/reviews",
        "/terms", "/privacy", "/faq", "/shipping", "/returns",
    ]
    url_lower = url.lower()
    return any(pattern in url_lower for pattern in non_product_patterns)


async def health_check() -> bool:
    """Vérifie la connectivité avec Browserless"""
    try:
        async with async_playwright() as p:
            browser = await p.chromium.connect_over_cdp(BROWSERLESS_URL)
            await browser.close()
            return True
    except Exception as e:
        logger.warning(f"Browserless health check failed: {e}")
        return False
