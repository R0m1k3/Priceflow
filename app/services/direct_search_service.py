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

# Constants
MIN_TITLE_LENGTH = 3
MIN_LINK_TEXT_LENGTH = 5
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)


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
# Liste des sites français configurés en dur
DEFAULT_SITE_CONFIGS = {
    # === MAGASINS DISCOUNT ===
    "gifi.fr": {
        "name": "Gifi",
        "search_url": "https://www.gifi.fr/catalogsearch/result/?q={query}",
        "product_selector": (
            ".product-item a.product-item-link, .product-item-info a, "
            ".product-item a, .products-grid a, a[href$='.html']"
        ),
        "wait_selector": ".products-grid, .product-items, .search-results, .products",
        "category": "Discount",
        "requires_js": True,
        "priority": 1,
    },
    "stokomani.fr": {
        "name": "Stokomani",
        "search_url": "https://www.stokomani.fr/recherche?q={query}",
        "product_selector": (
            ".product-miniature a, .js-product-miniature a, a.product-thumbnail, "
            ".products article a, a[href*='/products/'], a[href*='/produit/']"
        ),
        "wait_selector": ".products, .product-miniature, #js-product-list, .collection-products",
        "category": "Discount",
        "requires_js": True,
        "priority": 2,
    },
    "bmstores.fr": {
        "name": "B&M",
        "search_url": "https://bmstores.fr/module/ambjolisearch/jolisearch?s={query}",
        "product_selector": (
            ".product-miniature a, .js-product-miniature a, a.product-thumbnail, "
            ".products article a, a[href*='/produits/']"
        ),
        "wait_selector": ".products, .product-miniature, #js-product-list, #search_results",
        "category": "Discount",
        "requires_js": True,
        "priority": 3,
    },
    "centrakor.com": {
        "name": "Centrakor",
        "search_url": "https://www.centrakor.com/catalogsearch/result/?q={query}",
        "product_selector": (
            ".product-item a.product-item-link, .product-item-info a, "
            ".products-grid a, a[href$='.html']"
        ),
        "wait_selector": ".products-grid, .product-items, .search-results",
        "category": "Déco & Maison",
        "requires_js": True,
        "priority": 4,
    },
    "lincroyable.fr": {
        "name": "L'Incroyable",
        "search_url": "https://www.lincroyable.fr/recherche?q={query}",
        "product_selector": (
            ".product-miniature a, .js-product-miniature a, a.product-thumbnail, "
            ".products article a, a[href*='/produit']"
        ),
        "wait_selector": ".products, .product-miniature, #js-product-list",
        "category": "Discount",
        "requires_js": True,
        "priority": 5,
    },
    "action.com": {
        "name": "Action",
        "search_url": "https://www.action.com/fr-fr/search/?q={query}",
        "product_selector": "a.product-card__link, .product-card a, a[href*='/p/']",
        "wait_selector": ".product-card, .search-results",
        "category": "Discount",
        "requires_js": True,
        "priority": 6,
    },
    "lafoirfouille.fr": {
        "name": "La Foir'Fouille",
        "search_url": "https://www.lafoirfouille.fr/catalogsearch/result/?q={query}",
        "product_selector": (
            ".product-item a.product-item-link, .product-item-info a, "
            ".products-grid a, a[href$='.html']"
        ),
        "wait_selector": ".products-grid, .product-items, .search-results",
        "category": "Discount",
        "requires_js": True,
        "priority": 7,
    },
    # === GRANDES SURFACES ===
    "e.leclerc": {
        "name": "E.Leclerc",
        # URL correcte: https://www.e.leclerc/recherche?q=lutin
        "search_url": "https://www.e.leclerc/recherche?q={query}",
        "product_selector": (
            # Sélecteurs spécifiques aux produits E.Leclerc (liens /fp/)
            "a[href*='/fp/'][href*='-']:not([href*='promo']):not([href*='promotion']), "
            ".product-card a[href*='/fp/'], "
            "[data-testid='product-card'] a[href*='/fp/']"
        ),
        "wait_selector": "[data-testid='product-grid'], .search-results-list, .products-grid",
        "category": "Grande Surface",
        "requires_js": True,
        "priority": 8,
    },
    "auchan.fr": {
        "name": "Auchan",
        # URL correcte: https://www.auchan.fr/recherche?text=lutin
        "search_url": "https://www.auchan.fr/recherche?text={query}",
        "product_selector": (
            # Sélecteurs spécifiques aux produits Auchan (liens /p/ avec ID produit)
            "a[href*='/p/'][href$='.html'], "
            "a[href*='/p/'][href*='-p-'], "
            ".product-thumbnail a[href*='/p/'], "
            "[data-testid='product-card'] a[href*='/p/']"
        ),
        "wait_selector": ".search-results, .product-grid, [data-testid='search-results']",
        "category": "Grande Surface",
        "requires_js": True,
        "priority": 9,
    },
    "carrefour.fr": {
        "name": "Carrefour",
        # URL correcte: https://www.carrefour.fr/s?q=lutin
        "search_url": "https://www.carrefour.fr/s?q={query}",
        "product_selector": (
            # Sélecteurs spécifiques aux produits Carrefour (liens /p/)
            "a[href*='/p/'][href$='.html'], "
            "a[href*='/p/'][href*='-p-'], "
            ".product-card a[href*='/p/'], "
            "[data-testid='product-card'] a[href*='/p/']"
        ),
        "wait_selector": ".search-results, .product-grid, [data-testid='search-results']",
        "category": "Grande Surface",
        "requires_js": True,
        "priority": 10,
    },
    # === E-COMMERCE GÉNÉRALISTE ===
    "amazon.fr": {
        "name": "Amazon France",
        "search_url": "https://www.amazon.fr/s?k={query}",
        "product_selector": (
            # Sélecteurs simples pour Amazon - les produits ont data-asin
            "div[data-asin]:not([data-asin='']) h2 a, "
            ".s-result-item[data-asin] h2 a, "
            "[data-component-type='s-search-result'] h2 a"
        ),
        "wait_selector": "[data-component-type='s-search-result']",
        "category": "E-commerce",
        "requires_js": True,
        "priority": 11,
    },
    "cdiscount.com": {
        "name": "Cdiscount",
        "search_url": "https://www.cdiscount.com/search/10/{query}.html",
        "product_selector": (
            "a.prdtBImg, .prdtBILDetails a, .product-item a, "
            "a[href*='/f-']"
        ),
        "wait_selector": ".prdtBILDetails, .product-list",
        "category": "E-commerce",
        "requires_js": True,
        "priority": 12,
    },
    # === ÉLECTRONIQUE / HIGH-TECH ===
    "darty.com": {
        "name": "Darty",
        "search_url": "https://www.darty.com/nav/recherche?text={query}",
        "product_selector": (
            ".product-card a, a[href*='/product'], "
            ".product-list-item a"
        ),
        "wait_selector": ".product-card, .product-list",
        "category": "Électronique",
        "requires_js": True,
        "priority": 13,
    },
    "boulanger.com": {
        "name": "Boulanger",
        "search_url": "https://www.boulanger.com/resultats?tr={query}",
        "product_selector": (
            ".product-list__item a, a[href*='/ref/'], "
            ".product-card a"
        ),
        "wait_selector": ".product-list, .product-card",
        "category": "Électronique",
        "requires_js": True,
        "priority": 14,
    },
    # === AUTRES (conservés pour compatibilité) ===
    "amazon.com": {
        "name": "Amazon US",
        "search_url": "https://www.amazon.com/s?k={query}",
        "product_selector": (
            # Sélecteurs simples pour Amazon - les produits ont data-asin
            "div[data-asin]:not([data-asin='']) h2 a, "
            ".s-result-item[data-asin] h2 a, "
            "[data-component-type='s-search-result'] h2 a"
        ),
        "wait_selector": "[data-component-type='s-search-result']",
        "category": "E-commerce",
        "requires_js": True,
        "priority": 99,
    },
    "fnac.com": {
        "name": "Fnac",
        "search_url": "https://www.fnac.com/SearchResult/ResultList.aspx?Search={query}",
        "product_selector": "a.Article-title, .Article-item a.js-minifa-title",
        "wait_selector": ".Article-item",
        "category": "Culture & Tech",
        "requires_js": True,
        "priority": 15,
    },
}

# Sélecteurs communs pour les bannières de cookies
# Ordonnés du plus spécifique au plus générique pour une meilleure détection
COOKIE_ACCEPT_SELECTORS = [
    # === SITES SPÉCIFIQUES FRANÇAIS ===
    # Amazon France
    "#sp-cc-accept",
    "input[name='accept'][type='submit']",
    "[data-action='sp-cc']",
    # E.Leclerc
    "#onetrust-accept-btn-handler",
    ".onetrust-accept-btn-handler",
    # Auchan
    "#popin_tc_privacy_button_2",
    ".popin_tc_privacy_button",
    "#didomi-notice-agree-button",
    # Carrefour
    "#onetrust-accept-btn-handler",
    "[data-testid='accept-cookies-button']",
    # Cdiscount
    "#footer_tc_privacy_button_2",
    ".privacy_prompt_accept",
    # Darty / Fnac
    "#onetrust-accept-btn-handler",
    # Boulanger
    ".bcom-consent-accept-all",
    "#cookieBanner-accept",

    # === CMP (Consent Management Platforms) ===
    "#didomi-notice-agree-button",
    ".didomi-continue-without-agreeing",
    "#onetrust-accept-btn-handler",
    ".onetrust-accept-btn-handler",
    "#tarteaucitronPersonalize2",
    ".tarteaucitronAllow",
    "#tarteaucitronAllDenied2",
    ".cc-btn.cc-allow",
    ".cky-btn-accept",
    "#CybotCookiebotDialogBodyLevelButtonLevelOptinAllowAll",
    "#CybotCookiebotDialogBodyButtonAccept",
    ".qc-cmp2-summary-buttons button:first-child",
    "[data-accept-cookies]",
    "[data-gdpr-accept]",
    "#axeptio_btn_acceptAll",
    ".axeptio_acceptAll",

    # === TEXTE FRANÇAIS (Playwright :has-text) ===
    "button:has-text('Tout accepter')",
    "button:has-text('Accepter tout')",
    "button:has-text('Accepter et fermer')",
    "button:has-text('Accepter les cookies')",
    "button:has-text('Accepter')",
    "button:has-text('J\\'accepte')",
    "button:has-text('OK')",
    "button:has-text('Continuer')",
    "button:has-text('Continuer sans accepter')",
    "a:has-text('Tout accepter')",
    "a:has-text('Accepter')",
    "a:has-text('J\\'accepte')",
    "span:has-text('Tout accepter')",

    # === TEXTE ANGLAIS ===
    "button:has-text('Accept all')",
    "button:has-text('Accept cookies')",
    "button:has-text('Accept')",
    "button:has-text('I accept')",
    "button:has-text('Allow all')",

    # === GÉNÉRIQUES ===
    "button[id*='accept']",
    "button[id*='cookie']",
    "button[class*='accept']",
    "button[class*='cookie']",
    "button[data-testid*='accept']",
    "button[data-testid*='cookie']",
]


async def _accept_cookies(page, domain: str) -> bool:
    """
    Tente d'accepter les cookies sur une page.
    Essaie plusieurs fois et gère les iframes.
    Retourne True si un bouton a été cliqué, False sinon.
    """
    try:
        # Attendre un court moment pour que la bannière apparaisse
        await asyncio.sleep(1.5)

        # Essayer d'abord dans la page principale
        for selector in COOKIE_ACCEPT_SELECTORS:
            try:
                button = page.locator(selector).first
                if await button.is_visible(timeout=300):
                    await button.click(timeout=2000)
                    logger.info(f"{domain}: Cookies acceptés avec sélecteur {selector}")
                    await asyncio.sleep(0.5)
                    return True
            except Exception:
                continue

        # Essayer dans les iframes (certains CMP utilisent des iframes)
        frames = page.frames
        for frame in frames:
            if frame == page.main_frame:
                continue
            for selector in COOKIE_ACCEPT_SELECTORS[:20]:  # Limiter aux premiers sélecteurs
                try:
                    button = frame.locator(selector).first
                    if await button.is_visible(timeout=200):
                        await button.click(timeout=2000)
                        logger.info(f"{domain}: Cookies acceptés dans iframe avec {selector}")
                        await asyncio.sleep(0.5)
                        return True
                except Exception:
                    continue

        # Deuxième tentative après un peu plus d'attente (pour les bannières lentes)
        await asyncio.sleep(1)
        for selector in COOKIE_ACCEPT_SELECTORS[:30]:
            try:
                button = page.locator(selector).first
                if await button.is_visible(timeout=200):
                    await button.click(timeout=2000)
                    logger.info(f"{domain}: Cookies acceptés (2e essai) avec {selector}")
                    await asyncio.sleep(0.5)
                    return True
            except Exception:
                continue

        logger.debug(f"{domain}: Aucune bannière de cookies trouvée")
        return False

    except Exception as e:
        logger.debug(f"{domain}: Erreur lors de l'acceptation des cookies: {e}")
        return False


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


async def _search_site_browserless(  # noqa: PLR0912, PLR0915
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
                    user_agent=USER_AGENT,
                    locale="fr-FR",
                )
                page = await context.new_page()

                # Bloquer les ressources inutiles pour accélérer
                await page.route("**/*.{png,jpg,jpeg,gif,webp,svg,ico}", lambda route: route.abort())
                await page.route("**/analytics*", lambda route: route.abort())
                await page.route("**/tracking*", lambda route: route.abort())

                # Naviguer vers la page de recherche
                await page.goto(final_url, wait_until="domcontentloaded", timeout=int(timeout * 1000))

                # Accepter les cookies si nécessaire
                await _accept_cookies(page, domain)

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
        links = []
        if product_selector:
            # Essayer plusieurs sélecteurs séparés par virgule
            selectors = [s.strip() for s in product_selector.split(",")]
            for sel in selectors:
                try:
                    found = soup.select(sel)
                    links.extend(found)
                except Exception:
                    continue
            logger.info(f"{domain}: {len(links)} liens trouvés avec sélecteur configuré")

        # Fallback: détection générique si le sélecteur n'a rien trouvé
        if not links:
            logger.info(f"{domain}: Sélecteur configuré n'a rien trouvé, utilisation détection générique")
            links = _find_product_links(soup, domain)
            logger.info(f"{domain}: {len(links)} liens trouvés avec détection générique")

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
            if not title or len(title) < MIN_TITLE_LENGTH:
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
    # Nettoyer le domaine pour la comparaison
    clean = domain.lower().strip()
    if clean.startswith("www."):
        clean = clean[4:]

    for key, config in DEFAULT_SITE_CONFIGS.items():
        key_clean = key.lower().strip()
        if key_clean.startswith("www."):
            key_clean = key_clean[4:]

        # Comparaison exacte ou partielle
        if clean == key_clean or key_clean in clean or clean in key_clean:
            return config.get("search_url")
    return None


def _get_default_product_selector(domain: str) -> str | None:
    """Retourne le sélecteur de produits par défaut pour un domaine"""
    # Nettoyer le domaine pour la comparaison
    clean = domain.lower().strip()
    if clean.startswith("www."):
        clean = clean[4:]

    for key, config in DEFAULT_SITE_CONFIGS.items():
        key_clean = key.lower().strip()
        if key_clean.startswith("www."):
            key_clean = key_clean[4:]

        if clean == key_clean or key_clean in clean or clean in key_clean:
            return config.get("product_selector")
    return None


def _get_default_wait_selector(domain: str) -> str | None:
    """Retourne le sélecteur d'attente par défaut pour un domaine"""
    # Nettoyer le domaine pour la comparaison
    clean = domain.lower().strip()
    if clean.startswith("www."):
        clean = clean[4:]

    for key, config in DEFAULT_SITE_CONFIGS.items():
        key_clean = key.lower().strip()
        if key_clean.startswith("www."):
            key_clean = key_clean[4:]

        if clean == key_clean or key_clean in clean or clean in key_clean:
            return config.get("wait_selector")
    return None


def _find_product_links(soup: BeautifulSoup, domain: str) -> list:
    """Trouve les liens produits de manière générique"""
    links = []

    # Patterns très génériques pour les liens produits - ordre du plus spécifique au plus générique
    patterns = [
        # Patterns spécifiques e-commerce
        "a[href*='/product']",
        "a[href*='/products/']",
        "a[href*='/produit']",
        "a[href*='/produits/']",
        "a[href*='/p/']",
        "a[href*='/dp/']",
        "a[href*='/item']",
        "a[href*='/article']",
        "a[href*='/fiche']",
        "a[href*='-p-']",
        "a[href*='_p_']",
        "a[href*='/detail']",
        "a[href$='.html']",
        # Classes communes
        "a.product",
        "a.product-link",
        "a.product-card",
        "a.product-item",
        "a.product-title",
        "a.product-name",
        ".product a",
        ".product-card a",
        ".product-tile a",
        ".product-item a",
        ".product-miniature a",
        ".product-container a",
        # Patterns PrestaShop (très commun en France)
        ".product-miniature a.thumbnail",
        ".product-miniature a.product-thumbnail",
        "a.product-thumbnail",
        ".js-product-miniature a",
        # Patterns Magento
        ".product-item-link",
        "a.product-item-link",
        ".products-grid a",
        ".products-list a",
        # Patterns WooCommerce
        ".woocommerce-loop-product__link",
        "a.woocommerce-LoopProduct-link",
        # Autres patterns génériques
        "[data-product] a",
        "[data-item] a",
        ".search-result a",
        ".results a",
        ".listing a",
        ".catalog a",
        # Images de produits avec liens
        "a:has(img[alt])",
        ".thumbnail a",
        ".thumb a",
    ]

    for pattern in patterns:
        try:
            found = soup.select(pattern)
            if found:
                links.extend(found)
        except Exception:
            continue

    # Si toujours rien, essayer de trouver des liens dans les conteneurs de liste
    if not links:
        containers = soup.select(
            ".search-results, .products, .product-list, .results, "
            ".listing, .catalog, [class*='product'], [class*='result'], "
            "main, #content, .content"
        )
        for container in containers:
            # Trouver tous les liens dans ces conteneurs
            container_links = container.find_all("a", href=True)
            for link in container_links:
                href = link.get("href", "")
                # Filtrer les liens de navigation/footer
                if href and not _is_navigation_link(href):
                    # Vérifier si le lien a une image ou du texte substantiel
                    if link.find("img") or len(link.get_text(strip=True)) > MIN_LINK_TEXT_LENGTH:
                        links.append(link)

    # Dédupliquer
    seen = set()
    unique_links = []
    for link in links:
        href = link.get("href", "")
        if href and href not in seen:
            seen.add(href)
            unique_links.append(link)

    return unique_links


def _is_navigation_link(href: str) -> bool:
    """Vérifie si un lien est un lien de navigation (pas un produit)"""
    nav_patterns = [
        # Catégories et navigation
        "/category", "/categories", "/categorie",
        "/brand", "/brands", "/marque",
        "/page/", "/pages/",
        "/cart", "/panier", "/basket",
        "/checkout", "/commande",
        "/account", "/compte", "/mon-compte",
        "/login", "/connexion", "/register", "/inscription",
        "/search", "/recherche",
        "/contact", "/help", "/aide",
        "/about", "/a-propos",
        "/terms", "/privacy", "/cgv", "/mentions",
        "/faq", "/shipping", "/livraison",
        "/returns", "/retours",
        "javascript:", "mailto:", "tel:",
        "#", "?page=", "&page=",
        # URLs non-produit spécifiques aux sites français
        "/application", "/app/", "/apps/",
        "/courses", "/course/",
        "/ep-", "/endpoint",
        "/promo/", "/promotions/", "/promotion/",
        "/offres/", "/offre/",
        "/services/", "/service/",
        "/magasin", "/magasins", "/stores/", "/store/",
        "/blog", "/actualites", "/news",
        "/recettes", "/recipes",
        "/conseils", "/tips",
        # Amazon spécifique
        "/ref=cs_", "/logo", "/nav_", "/gp/help",
        "/gp/css", "/gp/redirect", "/hz/",
        "/ref=nb_", "/ref=sr_", "amazon.fr/ref=", "amazon.com/ref=",
        "/ap/signin", "/gp/yourstore", "/gp/cart",
        "/503", "/error", "/robot",
        # Liens génériques à exclure
        "/home", "/accueil", "/index",
        "/newsletter", "/subscribe",
        "/wishlist", "/liste-envies",
        "/compare", "/comparaison",
    ]
    href_lower = href.lower()
    return any(pattern in href_lower for pattern in nav_patterns)


def _extract_title(element) -> str:
    """Extrait le titre d'un élément"""
    # Essayer différentes méthodes
    title = element.get("title", "")
    if title and len(title) > MIN_TITLE_LENGTH:
        return title.strip()

    # Texte de l'élément
    text = element.get_text(strip=True)
    if text and len(text) > MIN_TITLE_LENGTH:
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
    url_lower = url.lower()

    # Pour Amazon, on vérifie que l'URL contient /dp/ (page produit)
    if "amazon" in url_lower:
        # Si c'est Amazon mais pas un lien /dp/, c'est pas un produit
        if "/dp/" not in url_lower and "/gp/product/" not in url_lower:
            return True
        # Exclure les liens d'erreur/redirection Amazon
        if "/ref=cs_" in url_lower or "/ref=nb_sb" in url_lower:
            return True
        if "amazon.fr/ref=" in url_lower or "amazon.com/ref=" in url_lower:
            if "/dp/" not in url_lower:
                return True

    non_product_patterns = [
        "/search", "/category", "/categories", "/brand", "/brands",
        "/help", "/contact", "/about", "/account", "/cart", "/checkout",
        "/login", "/register", "/wishlist", "/compare", "/reviews",
        "/terms", "/privacy", "/faq", "/shipping", "/returns",
        "/503", "/error", "/robot", "/captcha",
        "/application", "/courses", "/app/",
    ]
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
