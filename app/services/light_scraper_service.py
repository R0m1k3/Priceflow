"""
Light Scraper Service - Scraping HTTP rapide sans navigateur
Utilisé comme première tentative avant le fallback Browserless
"""

import logging
import re
from dataclasses import dataclass

import httpx

logger = logging.getLogger(__name__)

# Headers pour simuler un navigateur
DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "fr-FR,fr;q=0.9,en-US;q=0.8,en;q=0.7",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
    "Cache-Control": "max-age=0",
}

# Patterns regex pour extraire les prix
PRICE_PATTERNS = [
    # Format européen : 1 234,56 € ou 1234,56€
    r'(\d{1,3}(?:\s?\d{3})*[,\.]\d{2})\s*(?:€|EUR|euros?)',
    # Format : €1,234.56 ou € 1234.56
    r'(?:€|EUR)\s*(\d{1,3}(?:[,\s]?\d{3})*[,\.]\d{2})',
    # Prix simples : 12,99 € ou 12.99€
    r'(\d+[,\.]\d{2})\s*(?:€|EUR)',
    # data-price ou price attributes
    r'data-price["\']?\s*[:=]\s*["\']?(\d+[,\.]?\d*)',
    r'price["\']?\s*[:=]\s*["\']?(\d+[,\.]?\d*)',
]

# Patterns pour le stock
STOCK_POSITIVE_PATTERNS = [
    r'en\s*stock',
    r'disponible',
    r'in\s*stock',
    r'available',
    r'ajouter\s*au\s*panier',
    r'add\s*to\s*cart',
    r'acheter',
    r'livraison',
]

STOCK_NEGATIVE_PATTERNS = [
    r'rupture',
    r'indisponible',
    r'out\s*of\s*stock',
    r'épuisé',
    r'sold\s*out',
    r'plus\s*disponible',
    r'non\s*disponible',
]


@dataclass
class LightScraperResult:
    """Résultat du scraping léger"""

    success: bool
    url: str
    title: str | None = None
    price: float | None = None
    currency: str = "EUR"
    in_stock: bool | None = None
    image_url: str | None = None
    error: str | None = None
    requires_js: bool = False  # Indique si le site nécessite JS


async def scrape_url(url: str, timeout: float = 10.0) -> LightScraperResult:
    """
    Tente un scraping léger via HTTP simple.

    Args:
        url: URL du produit à scraper
        timeout: Timeout en secondes

    Returns:
        LightScraperResult avec les données extraites ou requires_js=True
    """
    try:
        async with httpx.AsyncClient(
            timeout=timeout,
            follow_redirects=True,
            headers=DEFAULT_HEADERS,
        ) as client:
            response = await client.get(url)
            response.raise_for_status()

            html = response.text

            # Vérifier si la page nécessite JavaScript
            if _requires_javascript(html):
                logger.debug(f"Page {url} nécessite JavaScript")
                return LightScraperResult(
                    success=False,
                    url=url,
                    requires_js=True,
                    error="Page requires JavaScript",
                )

            # Extraire les données
            title = _extract_title(html)
            price = _extract_price(html)
            in_stock = _extract_stock_status(html)
            image_url = _extract_image(html, url)

            # Si on n'a pas pu extraire le prix, fallback sur Browserless
            if price is None:
                logger.debug(f"Impossible d'extraire le prix de {url}")
                return LightScraperResult(
                    success=False,
                    url=url,
                    title=title,
                    requires_js=True,
                    error="Could not extract price",
                )

            logger.info(f"Scraping léger réussi pour {url}: {price}€")
            return LightScraperResult(
                success=True,
                url=url,
                title=title,
                price=price,
                in_stock=in_stock,
                image_url=image_url,
            )

    except httpx.TimeoutException:
        logger.warning(f"Timeout HTTP pour {url}")
        return LightScraperResult(
            success=False,
            url=url,
            error="HTTP timeout",
            requires_js=True,
        )
    except httpx.HTTPStatusError as e:
        logger.warning(f"Erreur HTTP {e.response.status_code} pour {url}")
        return LightScraperResult(
            success=False,
            url=url,
            error=f"HTTP {e.response.status_code}",
            requires_js=True,
        )
    except Exception as e:
        logger.error(f"Erreur scraping léger {url}: {e}")
        return LightScraperResult(
            success=False,
            url=url,
            error=str(e),
            requires_js=True,
        )


def _requires_javascript(html: str) -> bool:
    """Détecte si la page nécessite JavaScript pour afficher le contenu"""
    indicators = [
        "Please enable JavaScript",
        "JavaScript is required",
        "You need to enable JavaScript",
        "__NEXT_DATA__",  # Next.js SSR mais peut nécessiter JS
        "window.__INITIAL_STATE__",
        "React.createElement",
        '<div id="root"></div>',  # React SPA vide
        '<div id="app"></div>',  # Vue SPA vide
        "Loading...",
    ]

    html_lower = html.lower()

    # Vérifier si le body est presque vide
    body_match = re.search(r"<body[^>]*>(.*?)</body>", html, re.DOTALL | re.IGNORECASE)
    if body_match:
        body_content = body_match.group(1)
        # Retirer les scripts et styles
        body_clean = re.sub(r"<script[^>]*>.*?</script>", "", body_content, flags=re.DOTALL | re.IGNORECASE)
        body_clean = re.sub(r"<style[^>]*>.*?</style>", "", body_clean, flags=re.DOTALL | re.IGNORECASE)
        body_clean = re.sub(r"<[^>]+>", "", body_clean)
        body_clean = body_clean.strip()

        if len(body_clean) < 500:  # Page très peu de contenu texte
            return True

    for indicator in indicators:
        if indicator.lower() in html_lower:
            return True

    return False


def _extract_title(html: str) -> str | None:
    """Extrait le titre de la page"""
    # Essayer og:title d'abord
    og_match = re.search(r'<meta[^>]+property=["\']og:title["\'][^>]+content=["\']([^"\']+)["\']', html, re.IGNORECASE)
    if og_match:
        return og_match.group(1).strip()

    # Fallback sur <title>
    title_match = re.search(r"<title[^>]*>([^<]+)</title>", html, re.IGNORECASE)
    if title_match:
        title = title_match.group(1).strip()
        # Nettoyer les suffixes de site courants
        title = re.sub(r"\s*[-|]\s*(Amazon|Fnac|Cdiscount|Darty).*$", "", title, flags=re.IGNORECASE)
        return title

    return None


def _extract_price(html: str) -> float | None:
    """Extrait le prix de la page"""
    prices = []

    for pattern in PRICE_PATTERNS:
        matches = re.findall(pattern, html, re.IGNORECASE)
        for match in matches:
            try:
                # Normaliser le format
                price_str = match.replace(" ", "").replace(",", ".")
                price = float(price_str)
                if 0.01 < price < 100000:  # Prix raisonnable
                    prices.append(price)
            except ValueError:
                continue

    if not prices:
        return None

    # Retourner le prix le plus fréquent ou le premier
    from collections import Counter

    price_counts = Counter(prices)
    most_common = price_counts.most_common(1)
    if most_common:
        return most_common[0][0]

    return prices[0]


def _extract_stock_status(html: str) -> bool | None:
    """Extrait le statut de stock"""
    html_lower = html.lower()

    # Chercher les indicateurs négatifs d'abord
    for pattern in STOCK_NEGATIVE_PATTERNS:
        if re.search(pattern, html_lower):
            return False

    # Chercher les indicateurs positifs
    for pattern in STOCK_POSITIVE_PATTERNS:
        if re.search(pattern, html_lower):
            return True

    return None  # Incertain


def _extract_image(html: str, base_url: str) -> str | None:
    """Extrait l'image principale du produit"""
    from urllib.parse import urljoin

    # Essayer og:image d'abord
    og_match = re.search(r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)["\']', html, re.IGNORECASE)
    if og_match:
        return urljoin(base_url, og_match.group(1))

    # Essayer twitter:image
    twitter_match = re.search(r'<meta[^>]+name=["\']twitter:image["\'][^>]+content=["\']([^"\']+)["\']', html, re.IGNORECASE)
    if twitter_match:
        return urljoin(base_url, twitter_match.group(1))

    return None
