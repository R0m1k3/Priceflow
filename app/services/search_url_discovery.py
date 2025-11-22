"""
Search URL Discovery Service - Découvre automatiquement l'URL de recherche d'un site
"""

import asyncio
import logging
import os
import re
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup
from playwright.async_api import async_playwright

logger = logging.getLogger(__name__)

BROWSERLESS_URL = os.getenv("BROWSERLESS_URL", "ws://browserless:3000")

# Patterns communs pour les URLs de recherche
COMMON_SEARCH_PATTERNS = [
    "/search?q={query}",
    "/recherche?q={query}",
    "/s?k={query}",
    "/s?q={query}",
    "/catalogsearch/result/?q={query}",
    "/search?query={query}",
    "/recherche?query={query}",
    "/search?text={query}",
    "/recherche?text={query}",
    "/search/{query}",
    "/find?q={query}",
]


async def discover_search_url(domain: str) -> dict:
    """
    Découvre l'URL de recherche d'un site en visitant sa page d'accueil.

    Args:
        domain: Le domaine du site (ex: "amazon.fr", "action.com")

    Returns:
        Dict avec search_url et product_link_selector si trouvés
    """
    # Nettoyer le domaine
    domain = _clean_domain(domain)
    base_url = f"https://www.{domain}"

    logger.info(f"Discovering search URL for {domain}")

    result = {
        "search_url": None,
        "product_link_selector": None,
        "discovered": False,
    }

    try:
        async with async_playwright() as p:
            browser = await p.chromium.connect_over_cdp(BROWSERLESS_URL)

            try:
                context = await browser.new_context(
                    viewport={"width": 1920, "height": 1080},
                    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                    locale="fr-FR",
                )
                page = await context.new_page()

                # Visiter la page d'accueil
                await page.goto(base_url, wait_until="domcontentloaded", timeout=30000)
                await asyncio.sleep(2)  # Attendre le JS

                # Méthode 1: Chercher un formulaire de recherche
                search_url = await _find_search_form(page, base_url, domain)

                if search_url:
                    result["search_url"] = search_url
                    result["discovered"] = True
                    logger.info(f"Found search URL via form: {search_url}")
                else:
                    # Méthode 2: Essayer les patterns communs
                    search_url = await _try_common_patterns(page, base_url, domain)
                    if search_url:
                        result["search_url"] = search_url
                        result["discovered"] = True
                        logger.info(f"Found search URL via pattern: {search_url}")

                # Essayer de trouver un sélecteur de produits si on a une URL de recherche
                if result["search_url"]:
                    selector = await _discover_product_selector(page, result["search_url"], domain)
                    if selector:
                        result["product_link_selector"] = selector

                await context.close()

            finally:
                await browser.close()

    except Exception as e:
        logger.error(f"Error discovering search URL for {domain}: {e}")

    return result


async def _find_search_form(page, base_url: str, domain: str) -> str | None:
    """Trouve le formulaire de recherche sur la page"""
    try:
        # Chercher les formulaires de recherche
        search_selectors = [
            'form[action*="search"]',
            'form[action*="recherche"]',
            'form[action*="/s"]',
            'form[role="search"]',
            'form.search-form',
            'form.search',
            'form#search',
            'form#search-form',
            '.search-form form',
            'header form',
        ]

        for selector in search_selectors:
            try:
                form = await page.query_selector(selector)
                if form:
                    action = await form.get_attribute("action")
                    if action:
                        # Trouver le nom du champ de recherche
                        input_field = await form.query_selector('input[type="search"], input[type="text"], input[name*="q"], input[name*="query"], input[name*="search"]')
                        if input_field:
                            input_name = await input_field.get_attribute("name") or "q"

                            # Construire l'URL de recherche
                            if action.startswith("/"):
                                search_url = f"https://www.{domain}{action}"
                            elif action.startswith("http"):
                                search_url = action
                            else:
                                search_url = urljoin(base_url, action)

                            # Ajouter le paramètre de recherche
                            separator = "&" if "?" in search_url else "?"
                            search_url = f"{search_url}{separator}{input_name}={{query}}"

                            return search_url
            except Exception:
                continue

        # Méthode alternative: chercher les inputs de recherche
        input_selectors = [
            'input[type="search"]',
            'input[name="q"]',
            'input[name="query"]',
            'input[name="search"]',
            'input[name="s"]',
            'input[placeholder*="recherche" i]',
            'input[placeholder*="search" i]',
        ]

        for selector in input_selectors:
            try:
                input_el = await page.query_selector(selector)
                if input_el:
                    # Trouver le formulaire parent
                    form = await input_el.evaluate_handle("el => el.closest('form')")
                    if form:
                        action = await form.get_attribute("action")
                        input_name = await input_el.get_attribute("name") or "q"

                        if action:
                            if action.startswith("/"):
                                search_url = f"https://www.{domain}{action}"
                            elif action.startswith("http"):
                                search_url = action
                            else:
                                search_url = urljoin(base_url, action)

                            separator = "&" if "?" in search_url else "?"
                            search_url = f"{search_url}{separator}{input_name}={{query}}"
                            return search_url
            except Exception:
                continue

    except Exception as e:
        logger.debug(f"Error finding search form: {e}")

    return None


async def _try_common_patterns(page, base_url: str, domain: str) -> str | None:
    """Essaye les patterns de recherche communs"""
    for pattern in COMMON_SEARCH_PATTERNS:
        test_url = f"https://www.{domain}{pattern}".replace("{query}", "test")
        try:
            response = await page.goto(test_url, wait_until="domcontentloaded", timeout=10000)
            if response and response.status == 200:
                # Vérifier qu'on est sur une page de résultats
                content = await page.content()
                if "test" in content.lower() or "résultat" in content.lower() or "result" in content.lower():
                    return f"https://www.{domain}{pattern}"
        except Exception:
            continue

    return None


async def _discover_product_selector(page, search_url: str, domain: str) -> str | None:
    """Découvre le sélecteur CSS pour les liens produits"""
    try:
        # Faire une recherche test
        test_url = search_url.replace("{query}", "test")
        await page.goto(test_url, wait_until="domcontentloaded", timeout=20000)
        await asyncio.sleep(2)

        # Sélecteurs communs pour les produits
        product_selectors = [
            "a.product-card",
            "a.product-link",
            ".product-card a",
            ".product-item a",
            ".product a",
            "a[href*='/product']",
            "a[href*='/p/']",
            "a[href*='/dp/']",
            "a[href*='/item']",
            ".search-result a",
            ".results a.product",
        ]

        for selector in product_selectors:
            try:
                elements = await page.query_selector_all(selector)
                if len(elements) >= 2:  # Au moins 2 produits trouvés
                    return selector
            except Exception:
                continue

    except Exception as e:
        logger.debug(f"Error discovering product selector: {e}")

    return None


def _clean_domain(domain: str) -> str:
    """Nettoie un domaine"""
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
