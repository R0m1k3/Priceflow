"""
Search Configuration
Centralizes all configuration for the search system:
- Site definitions (selectors, URLs)
- Proxy configurations
- User Agents
"""

import os
import random

# === BROWSERLESS CONFIGURATION ===
BROWSERLESS_URL = os.getenv("BROWSERLESS_URL", "ws://browserless:3000")
DEBUG_DUMPS_DIR = "/app/debug_dumps"

# === PROXY CONFIGURATION ===
# Format from user: ip:port:username:password
AMAZON_PROXY_LIST_RAW = [
    "142.111.48.253:7030:jasuwwjr:elbsx170nmnl",
    "31.59.20.176:6754:jasuwwjr:elbsx170nmnl",
    "23.95.150.145:6114:jasuwwjr:elbsx170nmnl",
    "198.23.239.134:6540:jasuwwjr:elbsx170nmnl",
    "107.172.163.27:6543:jasuwwjr:elbsx170nmnl",
    "198.105.121.200:6462:jasuwwjr:elbsx170nmnl",
    "64.137.96.74:6641:jasuwwjr:elbsx170nmnl",
    "84.247.60.125:6095:jasuwwjr:elbsx170nmnl",
    "216.10.27.159:6837:jasuwwjr:elbsx170nmnl",
    "142.111.67.146:5611:jasuwwjr:elbsx170nmnl",
]

def get_amazon_proxies() -> list[dict]:
    """Convert raw proxy list to Playwright format"""
    proxies = []
    for proxy in AMAZON_PROXY_LIST_RAW:
        parts = proxy.split(":")
        if len(parts) == 4:
            proxies.append({
                "server": f"http://{parts[0]}:{parts[1]}",
                "username": parts[2],
                "password": parts[3]
            })
    return proxies

# === USER AGENTS ===
USER_AGENT_POOL = [
    # Chrome Windows
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
    # Chrome Mac
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    # Firefox Windows
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:133.0) Gecko/20100101 Firefox/133.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36 Edg/131.0.0.0",
]

def get_random_user_agent() -> str:
    return random.choice(USER_AGENT_POOL)

# === SITE CONFIGURATIONS ===
SITE_CONFIGS = {
    # === MAGASINS DISCOUNT ===
    "gifi.fr": {
        "name": "Gifi",
        "search_url": "https://www.gifi.fr/resultat-recherche?q={query}",
        "product_selector": "a.link, .product-item a.link, .product-tile a.link",
        "wait_selector": ".product-item, .product-tile, .products-grid",
        "category": "Discount",
        "requires_proxy": False,
    },
    "stokomani.fr": {
        "name": "Stokomani",
        "search_url": "https://www.stokomani.fr/search?options%5Bprefix%5D=last&q={query}",
        "product_selector": "a[href^='/products/']",
        "wait_selector": "a[href^='/products/']",
        "category": "Discount",
        "requires_proxy": False,
    },
    "bmstores.fr": {
        "name": "B&M",
        "wait_selector": ".product-card, .search-results",
        "category": "Discount",
        "requires_proxy": False,
    },
    "lafoirfouille.fr": {
        "name": "La Foir'Fouille",
        "search_url": "https://www.lafoirfouille.fr/catalogsearch/result/?q={query}",
        "product_selector": ".product-item a.product-item-link, .product-item-info a",
        "wait_selector": ".products-grid, .product-items",
        "category": "Discount",
        "requires_proxy": False,
    },
    "centrakor.com": {
        "name": "Centrakor",
        "search_url": "https://www.centrakor.com/catalogsearch/result/?q={query}",
        "product_selector": ".product-item a.product-item-link, .product-item-info a",
        "wait_selector": ".products-grid, .product-items",
        "category": "Déco & Maison",
        "requires_proxy": False,
        "pre_search_selector": "text=\"C'est parti !\"",
    },
    "lincroyable.fr": {
        "name": "L'Incroyable",
        "search_url": "https://www.lincroyable.fr/recherche-query={query}/?",
        "product_selector": "a[href^='/p']",
        "wait_selector": ".products, .product-miniature",
        "category": "Déco & Maison",
        "requires_proxy": False,
    },
    "action.com": {
        "name": "Action",
        "search_url": "https://www.action.com/fr-fr/search/?q={query}",
        "product_selector": "a[href^='/fr-fr/p/']",
        "wait_selector": "a[href^='/fr-fr/p/']",
        "category": "Discount",
        "requires_proxy": False,
    },
    # === GRANDES SURFACES ===
    "e.leclerc": {
        "name": "E.Leclerc",
        "search_url": "https://www.e.leclerc/recherche?q={query}",
        "product_selector": "a[href*='/fp/'][href*='-']:not([href*='promo'])",
        "wait_selector": "[data-testid='product-grid'], .search-results-list",
        "category": "Grande Surface",
        "requires_proxy": False,
    },
    # === E-COMMERCE GÉNÉRALISTE ===
    "amazon.fr": {
        "name": "Amazon France",
        "search_url": "https://www.amazon.fr/s?k={query}",
        "product_selector": "div[data-asin]:not([data-asin='']) h2 a",
        "wait_selector": "[data-component-type='s-search-result']",
        "category": "E-commerce",
        "requires_proxy": True,
    },
    "cdiscount.com": {
        "name": "Cdiscount",
        "search_url": "https://www.cdiscount.com/search/10/{query}.html",
        "product_selector": "a.prdtBImg[href*='/f-'][href*='.html']",
        "wait_selector": ".prdtBILDetails, .product-list",
        "category": "E-commerce",
        "requires_proxy": False,
    },
    # === ÉLECTRONIQUE / HIGH-TECH ===
    "darty.com": {
        "name": "Darty",
        "search_url": "https://www.darty.com/nav/recherche?text={query}",
        "product_selector": "a[href*='/nav/achat/'][href*='.html']",
        "wait_selector": ".product-card, .product-list",
        "category": "Électronique",
        "requires_proxy": False,
    },
    "boulanger.com": {
        "name": "Boulanger",
        "search_url": "https://www.boulanger.com/resultats?tr={query}",
        "product_selector": "a[href*='/ref/'][href*='_']",
        "wait_selector": ".product-list, .product-card",
        "category": "Électronique",
        "requires_proxy": False,
    },
    "fnac.com": {
        "name": "Fnac",
        "search_url": "https://www.fnac.com/SearchResult/ResultList.aspx?Search={query}",
        "product_selector": "a.Article-title[href*='/a']",
        "wait_selector": ".Article-item, .Article-list",
        "category": "Culture & Tech",
        "requires_proxy": False,
    },
}

# === COOKIE BANNERS ===
COOKIE_ACCEPT_SELECTORS = [
    "#sp-cc-accept", # Amazon
    "#onetrust-accept-btn-handler", # Many sites
    ".onetrust-accept-btn-handler",
    "#popin_tc_privacy_button_2", # Auchan/Cdiscount
    ".popin_tc_privacy_button",
    "#didomi-notice-agree-button", # Many French sites
    ".didomi-continue-without-agreeing",
    "[data-testid='accept-cookies-button']", # Carrefour
    ".bcom-consent-accept-all", # Boulanger
    "#cookieBanner-accept",
    ".action-primary.action-accept", # Magento
    "#btn-cookie-allow",
    "button:has-text('Tout accepter')",
    "button:has-text('Accepter tout')",
    "button:has-text('Accepter')",
    "button:has-text('J\\'accepte')",
    # Promotional Popups / Modals
    ".modal-close",
    ".close-modal",
    ".popup-close",
    "button[aria-label='Close']",
    "button[aria-label='Fermer']",
    ".js-modal-close",
    "div[class*='popup'] button[class*='close']",
    "div[class*='modal'] button[class*='close']",
    # Specific Gifi/Discount popups
    ".popin-close",
    "#popin-close",
    "a.close-popin",
    # Centrakor Store Overlay
    "div.mod-shops button.close",
    ".mod-shops .close",
    "#shops-modal .close-button",
    ".ui-dialog-titlebar-close",
]
