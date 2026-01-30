"""
Search Configuration - COMPLETE FIXED VERSION
"""

import os
import random

# === BROWSERLESS CONFIGURATION ===
BROWSERLESS_URL = os.getenv("BROWSERLESS_URL", "ws://browserless:3000")
DEBUG_DUMPS_DIR = "/app/debug_dumps"

# === PROXY CONFIGURATION ===
# NOTE: All free proxies tested are non-functional. Direct connections will be used.
# Add working proxies here when available.
AMAZON_PROXY_LIST_RAW = []


def get_amazon_proxies() -> list[dict]:
    """Convert raw proxy list to Playwright format"""
    proxies = []
    for proxy in AMAZON_PROXY_LIST_RAW:
        parts = proxy.split(":")
        if len(parts) == 4:
            proxies.append({"server": f"http://{parts[0]}:{parts[1]}", "username": parts[2], "password": parts[3]})
        elif len(parts) == 2:
            proxies.append({"server": f"http://{parts[0]}:{parts[1]}"})
    return proxies


# === USER AGENTS & STEALTH ===
USER_AGENT_DATA = [
    {
        "ua": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
        "ch": '"Google Chrome";v="131", "Chromium";v="131", "Not_A Brand";v="24"',
        "platform": '"Windows"',
    },
    {
        "ua": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
        "ch": '"Google Chrome";v="130", "Chromium";v="130", "Not_A Brand";v="99"',
        "platform": '"Windows"',
    },
    {
        "ua": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
        "ch": '"Google Chrome";v="131", "Chromium";v="131", "Not_A Brand";v="24"',
        "platform": '"macOS"',
    },
    {
        "ua": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
        "ch": '"Google Chrome";v="131", "Chromium";v="131", "Not_A Brand";v="24"',
        "platform": '"Linux"',
    },
    {
        "ua": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36 Edg/131.0.0.0",
        "ch": '"Microsoft Edge";v="131", "Chromium";v="131", "Not_A Brand";v="24"',
        "platform": '"Windows"',
    },
]


def get_random_stealth_config() -> dict:
    """Returns a random User-Agent and its corresponding Client Hints"""
    return random.choice(USER_AGENT_DATA)


def get_random_user_agent() -> str:
    """Legacy helper for backward compatibility"""
    return get_random_stealth_config()["ua"]


# === SITE CONFIGURATIONS ===
SITE_CONFIGS = {
    # === MAGASINS DISCOUNT ===
    "gifi.fr": {
        "name": "Gifi",
        "search_url": "https://www.gifi.fr/resultat-recherche?q={query}",
        "product_selector": "div.product-tile",
        "product_link_selector": "a.link",
        "product_title_selector": "div.pdp-link a",
        "product_image_selector": "img.tile-image",
        "wait_selector": "div.product-tile",
        "category": "Discount",
        "requires_proxy": False,
    },
    "stokomani.fr": {
        "name": "Stokomani",
        "search_url": "https://www.stokomani.fr/search?options%5Bprefix%5D=last&q={query}",
        "product_selector": "div.product-card",
        "product_title_selector": "h3.product-card__title a",
        "product_link_selector": "h3.product-card__title a",
        "product_image_selector": "div.media-wrapper img, img[class*='product-card__image']",
        "wait_selector": "div.product-card",
        "category": "Discount",
        "requires_proxy": False,
    },
    "lafoirfouille.fr": {
        "name": "La Foir'Fouille",
        "search_url": "https://www.lafoirfouille.fr/recherche?s={query}",
        "product_selector": "div.product-miniature, article, div[class*='product']",
        "product_image_selector": "img.product-thumbnail, img[src*='product'], img",
        "wait_selector": "div.product-miniature, article, div[class*='product']",
        "category": "Discount",
        "requires_proxy": False,
    },
    "cdiscount.com": {
        "name": "Cdiscount",
        "search_url": "https://www.cdiscount.com/search/10/{query}.html",
        "product_selector": "a[class*='sc-'], a.prdtBILnk, a[href*='/f-'][href*='.html']",
        "product_image_selector": "img.lazy, img[data-src], img[src*='image']",
        "wait_selector": "a[class*='sc-'], .prdtBILDetails, .prdtBIL",
        "category": "E-commerce",
        "requires_proxy": False,
    },
    # === ÉLECTRONIQUE / HIGH-TECH ===
    "darty.com": {
        "name": "Darty",
        "search_url": "https://www.darty.com/nav/recherche?text={query}",
        "product_selector": "a[href*='/nav/achat/'][href*='.html']",
        "product_image_selector": "img.product_img",
        "wait_selector": ".product-card, .product-list",
        "category": "Électronique",
        "requires_proxy": False,
    },
    "boulanger.com": {
        "name": "Boulanger",
        "search_url": "https://www.boulanger.com/resultats?tr={query}",
        "product_selector": "a[href*='/ref/'][href*='_']",
        "product_image_selector": "img.product-image",
        "wait_selector": ".product-list, .product-card",
        "category": "Électronique",
        "requires_proxy": False,
    },
    "fnac.com": {
        "name": "Fnac",
        "search_url": "https://www.fnac.com/SearchResult/ResultList.aspx?Search={query}",
        "product_selector": "a[href*='/a'], a.Article-title, article a",
        "product_image_selector": "img, picture source",
        "wait_selector": ".Article-item",
        "category": "Culture & Tech",
        "requires_proxy": False,
    },
    # === NOUVEAUX SITES ===
    "lincroyable.fr": {
        "name": "L'Incroyable",
        "search_url": "https://www.lincroyable.fr/recherche-query={query}/",
        "product_selector": "div.tailleBlocProdNew a",
        "product_image_selector": "img.imgCoup2coeur, img[class*='product']",
        "wait_selector": "div.tailleBlocProdNew",
        "category": "Discount",
        "requires_proxy": False,
    },
    "amazon.fr": {
        "name": "Amazon",
        "search_url": "https://www.amazon.fr/s?k={query}",
        "product_selector": "div[data-component-type='s-search-result'] h2 a",
        "product_image_selector": "img.s-image",
        "wait_selector": "div[data-component-type='s-search-result']",
        "category": "E-commerce",
        "requires_proxy": False,
    },
    "bmstores.fr": {
        "name": "B&M",
        "search_url": "https://bmstores.fr/module/ambjolisearch/jolisearch?s={query}",
        "product_selector": "a.thumbnail.product-thumbnail",
        "product_image_selector": "img.product-thumbnail",
        "wait_selector": ".products, .product-miniature",
        "category": "Discount",
        "requires_proxy": False,
    },
    "centrakor.com": {
        "name": "Centrakor",
        "search_url": "https://www.centrakor.com/search/{query}",
        "product_selector": "div.product-item",
        "product_image_selector": "img.responsive-image__actual",
        "wait_selector": "div.product-item",
        "category": "Discount",
        "requires_proxy": False,
    },
    "auchan.fr": {
        "name": "Auchan",
        "search_url": "https://www.auchan.fr/recherche?text={query}",
        "product_selector": "article.product-thumbnail a.product-thumbnail__details-wrapper, div[class*='product-card'] a",
        "product_image_selector": ".product-thumbnail__picture img, img[class*='product']",
        "wait_selector": "article.product-thumbnail, div[class*='product-card']",
        "category": "Grande Surface",
        "requires_proxy": False,
    },
    "carrefour.fr": {
        "name": "Carrefour",
        "search_url": "https://www.carrefour.fr/s?q={query}",
        "product_selector": "article.product-list-card-plp-grid-new",
        "product_image_selector": "img.product-card-image-new__content",
        "wait_selector": "article.product-list-card-plp-grid-new",
        "category": "Grande Surface",
        "requires_proxy": False,
    },
    "action.com": {
        "name": "Action",
        "search_url": "https://www.action.com/fr-fr/search/?q={query}",
        "product_selector": "div[data-testid='product-card']",
        "product_image_selector": "img[data-testid='product-card-image']",
        "price_selector": ".product-price, [data-testid='product-price'], .price, .current-price, .product-card__price",
        "wait_selector": "div[data-testid='product-card']",
        "category": "Discount",
        "requires_proxy": False,
    },
    "e-leclerc.com": {
        "name": "E.Leclerc",
        "search_url": "https://www.e.leclerc/recherche?q={query}",
        "product_selector": "a.product-card-link",
        "product_image_selector": "img",
        "wait_selector": "a.product-card-link",
        "category": "Grande Surface",
        "requires_proxy": False,
    },
}

# === COOKIE BANNERS ===
COOKIE_ACCEPT_SELECTORS = [
    "#sp-cc-accept",
    "#onetrust-accept-btn-handler",
    ".onetrust-accept-btn-handler",
    "#popin_tc_privacy_button_2",
    ".popin_tc_privacy_button",
    "#didomi-notice-agree-button",
    ".didomi-continue-without-agreeing",
    "[data-testid='accept-cookies-button']",
    ".bcom-consent-accept-all",
    "#cookieBanner-accept",
    ".action-primary.action-accept",
    "#btn-cookie-allow",
    "button:has-text('Tout accepter')",
    "button:has-text('Accepter tout')",
    "button:has-text('Accepter')",
    "button:has-text('J\\'accepte')",
    ".modal-close",
    ".close-modal",
    ".popup-close",
    "button[aria-label='Close']",
    "button[aria-label='Fermer']",
    ".js-modal-close",
    "div[class*='popup'] button[class*='close']",
    "div[class*='modal'] button[class*='close']",
    ".popin-close",
    "#popin-close",
    "a.close-popin",
    "div.mod-shops button.close",
    ".mod-shops .close",
    "#shops-modal .close-button",
    ".ui-dialog-titlebar-close",
    "#cc-accept",
    ".cc-btn-accept",
    "button[data-testid='uc-accept-all-button']",
    "button:has-text('Accepter tout')",
    "button:has-text('Accepter')",
    "button:has-text('Refuser')",
]
