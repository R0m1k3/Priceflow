"""
Direct Search Service - Recherche sur les sites e-commerce via Browserless
Utilise Playwright/Browserless pour gérer JavaScript et contourner la détection de bots.
"""

import asyncio
import logging
import os
import re
import random
import time
from urllib.parse import quote_plus, urljoin, urlparse

from bs4 import BeautifulSoup
from playwright.async_api import async_playwright

logger = logging.getLogger(__name__)

BROWSERLESS_URL = os.getenv("BROWSERLESS_URL", "ws://browserless:3000")

# Proxy configuration for Amazon (optional)
# Format: "http://user:pass@host:port" or "http://host:port"
AMAZON_PROXY_URL = os.getenv("AMAZON_PROXY_URL", "")
# If you have multiple proxies, separate them with commas
AMAZON_PROXY_LIST = [p.strip() for p in os.getenv("AMAZON_PROXY_LIST", "").split(",") if p.strip()]

def _get_amazon_proxy() -> str | None:
    """Get a proxy for Amazon requests (random from list or single)"""
    if AMAZON_PROXY_LIST:
        return random.choice(AMAZON_PROXY_LIST)
    if AMAZON_PROXY_URL:
        return AMAZON_PROXY_URL
    return None

# Constants
MIN_TITLE_LENGTH = 3
MIN_LINK_TEXT_LENGTH = 5

# Pool of realistic User-Agents for rotation (Chrome on Windows/Mac)
USER_AGENT_POOL = [
    # Chrome Windows - Latest versions
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
    # Chrome Mac
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
    # Firefox Windows
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:133.0) Gecko/20100101 Firefox/133.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:132.0) Gecko/20100101 Firefox/132.0",
    # Firefox Mac
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:133.0) Gecko/20100101 Firefox/133.0",
    # Edge Windows
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36 Edg/131.0.0.0",
]

# Amazon-specific blocking indicators
AMAZON_BLOCK_INDICATORS = [
    "Toutes nos excuses",
    "Sorry, something went wrong",
    "To discuss automated access to Amazon data",
    "api-services-support@amazon.com",
    "Enter the characters you see below",
    "Saisissez les caractères",
    "Type the characters you see",
    "Sorry! Something went wrong",
    "Service Unavailable",
    "robot check",
    "automated access",
    "ref=cs_503",
]

# Amazon retry configuration
AMAZON_MAX_RETRIES = 4
AMAZON_BASE_DELAY = 3.0  # seconds
AMAZON_MAX_DELAY = 30.0  # seconds


def _get_random_user_agent() -> str:
    """Get a random User-Agent from the pool"""
    return random.choice(USER_AGENT_POOL)


def _is_amazon_blocked(html_content: str) -> bool:
    """Check if Amazon has blocked the request"""
    html_lower = html_content.lower()
    for indicator in AMAZON_BLOCK_INDICATORS:
        if indicator.lower() in html_lower:
            return True
    return False


async def _random_delay(min_seconds: float = 1.0, max_seconds: float = 3.0):
    """Add a random delay to simulate human behavior"""
    delay = random.uniform(min_seconds, max_seconds)
    await asyncio.sleep(delay)


async def _simulate_human_behavior(page):
    """Simulate human-like behavior on the page"""
    try:
        # Random mouse movements
        for _ in range(random.randint(2, 4)):
            x = random.randint(100, 1800)
            y = random.randint(100, 900)
            await page.mouse.move(x, y)
            await asyncio.sleep(random.uniform(0.1, 0.3))

        # Small random scroll
        scroll_amount = random.randint(100, 400)
        await page.evaluate(f"window.scrollBy(0, {scroll_amount})")
        await asyncio.sleep(random.uniform(0.3, 0.7))

        # Scroll back up a bit
        await page.evaluate(f"window.scrollBy(0, -{random.randint(50, 150)})")
        await asyncio.sleep(random.uniform(0.2, 0.5))
    except Exception as e:
        logger.debug(f"Human behavior simulation error (non-critical): {e}")


# Legacy constant for backward compatibility
USER_AGENT = USER_AGENT_POOL[0]


# Stealth JavaScript to inject before page load to hide automation
STEALTH_JS = """
// ============================================
// COMPREHENSIVE STEALTH MODE FOR AMAZON
// ============================================

// 1. Override navigator.webdriver in multiple ways
Object.defineProperty(navigator, 'webdriver', {
    get: () => false,
    configurable: true
});

// Also delete from navigator prototype
delete Object.getPrototypeOf(navigator).webdriver;

// Override the getAttribute method to hide webdriver attribute
const originalGetAttribute = Element.prototype.getAttribute;
Element.prototype.getAttribute = function(name) {
    if (name === 'webdriver') return null;
    return originalGetAttribute.call(this, name);
};

// 2. Override navigator.plugins with realistic plugins
Object.defineProperty(navigator, 'plugins', {
    get: () => {
        const plugins = [
            { name: 'Chrome PDF Plugin', filename: 'internal-pdf-viewer', description: 'Portable Document Format', length: 1 },
            { name: 'Chrome PDF Viewer', filename: 'mhjfbmdgcfjbbpaeojofohoefgiehjai', description: '', length: 1 },
            { name: 'Native Client', filename: 'internal-nacl-plugin', description: '', length: 2 },
            { name: 'Chromium PDF Plugin', filename: 'internal-pdf-viewer', description: 'Portable Document Format', length: 1 },
            { name: 'Chromium PDF Viewer', filename: 'mhjfbmdgcfjbbpaeojofohoefgiehjai', description: '', length: 1 }
        ];
        plugins.item = (i) => plugins[i] || null;
        plugins.namedItem = (name) => plugins.find(p => p.name === name) || null;
        plugins.refresh = () => {};
        plugins.length = plugins.length;
        return plugins;
    },
    configurable: true
});

// 3. Override navigator.mimeTypes
Object.defineProperty(navigator, 'mimeTypes', {
    get: () => {
        const mimeTypes = [
            { type: 'application/pdf', suffixes: 'pdf', description: 'Portable Document Format' },
            { type: 'text/pdf', suffixes: 'pdf', description: 'Portable Document Format' }
        ];
        mimeTypes.item = (i) => mimeTypes[i] || null;
        mimeTypes.namedItem = (name) => mimeTypes.find(m => m.type === name) || null;
        mimeTypes.length = mimeTypes.length;
        return mimeTypes;
    },
    configurable: true
});

// 4. Override navigator.languages
Object.defineProperty(navigator, 'languages', {
    get: () => ['fr-FR', 'fr', 'en-US', 'en'],
    configurable: true
});

// 5. Override permissions API
if (window.navigator.permissions) {
    const originalQuery = window.navigator.permissions.query;
    window.navigator.permissions.query = (parameters) => {
        if (parameters.name === 'notifications') {
            return Promise.resolve({ state: Notification.permission, onchange: null });
        }
        return originalQuery.call(window.navigator.permissions, parameters);
    };
}

// 6. Hide automation-related properties (Chromium DevTools Protocol)
const propsToDelete = [
    'cdc_adoQpoasnfa76pfcZLmcfl_Array',
    'cdc_adoQpoasnfa76pfcZLmcfl_Promise',
    'cdc_adoQpoasnfa76pfcZLmcfl_Symbol',
    '__webdriver_evaluate',
    '__selenium_evaluate',
    '__webdriver_script_function',
    '__webdriver_script_func',
    '__webdriver_script_fn',
    '__fxdriver_evaluate',
    '__driver_unwrapped',
    '__webdriver_unwrapped',
    '__driver_evaluate',
    '__selenium_unwrapped',
    '__fxdriver_unwrapped',
    '_Selenium_IDE_Recorder',
    '_selenium',
    'calledSelenium',
    '$chrome_asyncScriptInfo',
    '$cdc_asdjflasutopfhvcZLmcfl_',
    '$wdc_'
];
propsToDelete.forEach(prop => {
    try { delete window[prop]; } catch(e) {}
});

// 7. Override chrome object with realistic properties
window.chrome = {
    app: {
        isInstalled: false,
        InstallState: { DISABLED: 'disabled', INSTALLED: 'installed', NOT_INSTALLED: 'not_installed' },
        RunningState: { CANNOT_RUN: 'cannot_run', READY_TO_RUN: 'ready_to_run', RUNNING: 'running' }
    },
    runtime: {
        OnInstalledReason: { CHROME_UPDATE: 'chrome_update', INSTALL: 'install', SHARED_MODULE_UPDATE: 'shared_module_update', UPDATE: 'update' },
        OnRestartRequiredReason: { APP_UPDATE: 'app_update', OS_UPDATE: 'os_update', PERIODIC: 'periodic' },
        PlatformArch: { ARM: 'arm', ARM64: 'arm64', MIPS: 'mips', MIPS64: 'mips64', X86_32: 'x86-32', X86_64: 'x86-64' },
        PlatformNaclArch: { ARM: 'arm', MIPS: 'mips', MIPS64: 'mips64', X86_32: 'x86-32', X86_64: 'x86-64' },
        PlatformOs: { ANDROID: 'android', CROS: 'cros', LINUX: 'linux', MAC: 'mac', OPENBSD: 'openbsd', WIN: 'win' },
        RequestUpdateCheckStatus: { NO_UPDATE: 'no_update', THROTTLED: 'throttled', UPDATE_AVAILABLE: 'update_available' },
        connect: function() { return { onDisconnect: { addListener: function() {} }, onMessage: { addListener: function() {} }, postMessage: function() {} }; },
        sendMessage: function() {}
    },
    csi: function() { return {}; },
    loadTimes: function() { return { requestTime: Date.now() / 1000, startLoadTime: Date.now() / 1000, firstPaintAfterLoadTime: 0, firstPaintTime: Date.now() / 1000, navigationType: 'navigate' }; }
};

// 8. WebGL fingerprinting protection
const getParameterProxyHandler = {
    apply: function(target, ctx, args) {
        if (args[0] === 37445) return 'Intel Inc.';
        if (args[0] === 37446) return 'Intel Iris OpenGL Engine';
        if (args[0] === 7937) return 'WebKit';
        if (args[0] === 7936) return 'WebKit WebGL';
        return Reflect.apply(target, ctx, args);
    }
};
try {
    const canvas = document.createElement('canvas');
    const gl = canvas.getContext('webgl') || canvas.getContext('experimental-webgl');
    if (gl) {
        const getParameter = gl.getParameter.bind(gl);
        gl.getParameter = new Proxy(getParameter, getParameterProxyHandler);
    }
    const gl2 = canvas.getContext('webgl2');
    if (gl2) {
        const getParameter2 = gl2.getParameter.bind(gl2);
        gl2.getParameter = new Proxy(getParameter2, getParameterProxyHandler);
    }
} catch(e) {}

// 9. Canvas fingerprinting protection
const originalToDataURL = HTMLCanvasElement.prototype.toDataURL;
HTMLCanvasElement.prototype.toDataURL = function(type) {
    if (type === 'image/png' && this.width === 220 && this.height === 30) {
        // Likely fingerprinting attempt, add noise
        const context = this.getContext('2d');
        if (context) {
            const imageData = context.getImageData(0, 0, this.width, this.height);
            for (let i = 0; i < imageData.data.length; i += 4) {
                imageData.data[i] = imageData.data[i] ^ (Math.random() * 2);
            }
            context.putImageData(imageData, 0, 0);
        }
    }
    return originalToDataURL.apply(this, arguments);
};

// 10. AudioContext fingerprinting protection
if (window.AudioContext || window.webkitAudioContext) {
    const AudioContext = window.AudioContext || window.webkitAudioContext;
    const originalCreateOscillator = AudioContext.prototype.createOscillator;
    AudioContext.prototype.createOscillator = function() {
        const oscillator = originalCreateOscillator.apply(this, arguments);
        oscillator.frequency.value = oscillator.frequency.value + (Math.random() * 0.0001);
        return oscillator;
    };
}

// 11. Override connection properties
Object.defineProperty(navigator, 'connection', {
    get: () => ({
        effectiveType: '4g',
        rtt: 50 + Math.floor(Math.random() * 50),
        downlink: 10 + Math.random() * 5,
        saveData: false
    }),
    configurable: true
});

// 12. Override hardware properties
Object.defineProperty(navigator, 'hardwareConcurrency', {
    get: () => 8,
    configurable: true
});

Object.defineProperty(navigator, 'deviceMemory', {
    get: () => 8,
    configurable: true
});

// 13. Override screen properties
Object.defineProperty(screen, 'colorDepth', {
    get: () => 24,
    configurable: true
});

Object.defineProperty(screen, 'pixelDepth', {
    get: () => 24,
    configurable: true
});

// 14. Spoof Notification API
if (window.Notification) {
    Object.defineProperty(Notification, 'permission', {
        get: () => 'default',
        configurable: true
    });
}

// 15. Override iframe contentWindow checks
const originalContentWindow = Object.getOwnPropertyDescriptor(HTMLIFrameElement.prototype, 'contentWindow');
Object.defineProperty(HTMLIFrameElement.prototype, 'contentWindow', {
    get: function() {
        const win = originalContentWindow.get.call(this);
        if (win) {
            try {
                Object.defineProperty(win.navigator, 'webdriver', {
                    get: () => false,
                    configurable: true
                });
            } catch(e) {}
        }
        return win;
    }
});

// 16. Mock Battery API
if (navigator.getBattery) {
    navigator.getBattery = () => Promise.resolve({
        charging: true,
        chargingTime: 0,
        dischargingTime: Infinity,
        level: 1,
        addEventListener: () => {},
        removeEventListener: () => {}
    });
}

// 17. Hide Playwright/Puppeteer specific objects
delete window.__playwright;
delete window.__pw_manual;
delete window.__PW_inspect;

console.log('Advanced stealth mode activated');
"""


# Chemin absolu pour les dumps de débogage (doit correspondre à celui dans debug.py)
DEBUG_DUMPS_DIR = "/app/debug_dumps"


def _dump_debug_html(html: str, domain: str, query: str):
    """Sauvegarde le HTML pour débogage"""
    try:
        debug_dir = "debug_dumps"
        if not os.path.exists(debug_dir):
            os.makedirs(debug_dir)
            
        filename = f"{debug_dir}/{domain}_{query}_{int(asyncio.get_event_loop().time())}.html"
        with open(filename, "w", encoding="utf-8") as f:
            f.write(html)
        logger.info(f"HTML dump saved to {filename}")
    except Exception as e:
        logger.error(f"Failed to dump HTML: {e}")


class SearchResult:
    """Résultat de recherche"""

    def __init__(
        self,
        url: str,
        title: str,
        snippet: str,
        source: str,
        price: float | None = None,
        currency: str = "EUR",
        in_stock: bool | None = None,
    ):
        self.url = url
        self.title = title
        self.snippet = snippet
        self.source = source
        self.price = price
        self.currency = currency
        self.in_stock = in_stock

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
            # Cibler uniquement les liens produits, pas les catégories
            "a.product-thumbnail[href*='/produits/']:not([href*='/c/']):not([href*='/categorie']), "
            ".product-miniature a[href*='/produits/']:not([href*='/c/']), "
            ".js-product-miniature a[href*='/produits/']"
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
        "search_url": "https://www.lincroyable.fr/recherche-query={query}/?",
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
            # Sélecteurs robustes pour Amazon
            "div[data-asin]:not([data-asin='']) h2 a, "
            ".s-result-item[data-asin] h2 a, "
            "[data-component-type='s-search-result'] h2 a, "
            # Fallback sur les liens d'images si le titre est manqué
            ".s-result-item[data-asin] .s-image-link, "
            "a.a-link-normal.s-no-outline[href*='/dp/']"
        ),
        "wait_selector": "[data-component-type='s-search-result'], .s-result-item",
        "category": "E-commerce",
        "requires_js": True,
        "priority": 11,
    },
    "cdiscount.com": {
        "name": "Cdiscount",
        "search_url": "https://www.cdiscount.com/search/10/{query}.html",
        "product_selector": (
            # Sélecteurs spécifiques Cdiscount - produits uniquement
            "a.prdtBImg[href*='/f-'][href*='.html'], "
            ".prdtBILDetails a[href*='/f-'][href*='.html'], "
            "a[href*='/f-'][href*='.html']:not([href*='/l-']):not([href*='/rayon'])"
        ),
        "wait_selector": ".prdtBILDetails, .product-list, #lpBloc",
        "category": "E-commerce",
        "requires_js": True,
        "priority": 12,
    },
    # === ÉLECTRONIQUE / HIGH-TECH ===
    "darty.com": {
        "name": "Darty",
        "search_url": "https://www.darty.com/nav/recherche?text={query}",
        "product_selector": (
            # Cibler les fiches produits, exclure navigation et catégories
            "a[href*='/nav/achat/'][href*='.html']:not([href*='/rayon']):not([href*='/promo']), "
            ".product-card a[href*='/nav/achat/'], "
            "a.product-link[href*='/nav/achat/']"
        ),
        "wait_selector": ".product-card, .product-list, .product-item",
        "category": "Électronique",
        "requires_js": True,
        "priority": 13,
    },
    "boulanger.com": {
        "name": "Boulanger",
        "search_url": "https://www.boulanger.com/resultats?tr={query}",
        "product_selector": (
            # Cibler uniquement les pages produits avec /ref/
            "a[href*='/ref/'][href*='_']:not([href*='/c/']):not([href*='/rayon']), "
            ".product-list__item a[href*='/ref/'], "
            ".product-card__link[href*='/ref/']"
        ),
        "wait_selector": ".product-list, .product-card, .products-list",
        "category": "Électronique",
        "requires_js": True,
        "priority": 14,
    },
    # === AUTRES (conservés pour compatibilité) ===
    "amazon.com": {
        "name": "Amazon US",
        "search_url": "https://www.amazon.com/s?k={query}",
        "product_selector": (
            # Sélecteurs robustes pour Amazon
            "div[data-asin]:not([data-asin='']) h2 a, "
            ".s-result-item[data-asin] h2 a, "
            "[data-component-type='s-search-result'] h2 a, "
            # Fallback sur les liens d'images si le titre est manqué
            ".s-result-item[data-asin] .s-image-link, "
            "a.a-link-normal.s-no-outline[href*='/dp/']"
        ),
        "wait_selector": "[data-component-type='s-search-result'], .s-result-item",
        "category": "E-commerce",
        "requires_js": True,
        "priority": 99,
    },
    "fnac.com": {
        "name": "Fnac",
        "search_url": "https://www.fnac.com/SearchResult/ResultList.aspx?Search={query}",
        "product_selector": (
            # Sélecteurs Fnac pour les produits
            "a.Article-title[href*='/a'], "
            ".Article-item a.js-minifa-title[href*='/a'], "
            "a[href*='/a'][href*='.html']:not([href*='/rayon']):not([href*='/univers'])"
        ),
        "wait_selector": ".Article-item, .Article-list, #SearchResultList",
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
    browser=None,  # Instance de navigateur partagée optionnelle
) -> list[SearchResult]:
    """
    Recherche sur les sites e-commerce via Browserless.

    Args:
        query: Terme de recherche
        sites: Liste de dicts avec {domain, search_url, product_link_selector, name}
        max_results: Nombre maximum de résultats
        timeout: Timeout par site
        browser: Instance Playwright browser partagée (optionnel)

    Returns:
        Liste de SearchResult
    """
    if not sites:
        logger.warning("Aucun site configuré pour la recherche")
        return []

    all_results = []
    results_per_site = max(5, max_results // len(sites))

    logger.info(f"Démarrage recherche parallèle v2 (Shared Browser) sur {len(sites)} sites pour '{query}'")

    # Si un navigateur est fourni, on l'utilise directement
    if browser:
        return await _execute_search_with_browser(query, sites, results_per_site, timeout, browser)
    
    # Sinon on crée notre propre instance (comportement autonome)
    try:
        async with async_playwright() as p:
            logger.info(f"Connexion autonome à Browserless: {BROWSERLESS_URL}")
            local_browser = await p.chromium.connect_over_cdp(BROWSERLESS_URL)
            try:
                return await _execute_search_with_browser(query, sites, results_per_site, timeout, local_browser)
            finally:
                await local_browser.close()
                logger.info("Navigateur autonome fermé")
    except Exception as e:
        logger.error(f"Erreur globale recherche autonome: {e}")
        return []

async def _execute_search_with_browser(
    query: str,
    sites: list[dict],
    results_per_site: int,
    timeout: float,
    browser,
) -> list[SearchResult]:
    """Exécute la recherche avec un navigateur donné"""
    all_results = []
    try:
        # Créer des tâches pour chaque site
        tasks = []
        for site in sites:
            task = _search_site_browserless(
                query=query,
                site=site,
                max_results=results_per_site,
                timeout=timeout,
                browser=browser,
            )
            tasks.append(task)

        # Exécuter en parallèle avec asyncio.gather
        results_list = await asyncio.gather(*tasks, return_exceptions=True)

        # Agréger les résultats
        for i, result in enumerate(results_list):
            site_domain = sites[i].get("domain", "inconnu")
            
            if isinstance(result, Exception):
                logger.error(f"Erreur fatale recherche {site_domain}: {result}")
                continue
                
            if result:
                all_results.extend(result)
                logger.info(f"Site {site_domain}: {len(result)} résultats")
            else:
                logger.info(f"Site {site_domain}: 0 résultat")
                
    except Exception as e:
        logger.error(f"Erreur exécution recherche: {e}")
        
    return all_results


async def _search_site_browserless(  # noqa: PLR0912, PLR0915
    query: str,
    site: dict,
    max_results: int,
    timeout: float,
    browser,  # Instance de navigateur partagée
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

    context = None
    page = None
    max_retries = 3 if "amazon" in domain else 1

    for attempt in range(max_retries):
        if attempt > 0:
            # Exponential backoff with jitter for Amazon retries
            base_delay = AMAZON_BASE_DELAY * (2 ** attempt)
            jitter = random.uniform(0.5, 1.5)
            delay = min(base_delay * jitter, AMAZON_MAX_DELAY)
            logger.info(f"Amazon retry {attempt + 1}/{max_retries} for '{query}' after {delay:.1f}s delay")
            await asyncio.sleep(delay)

        try:
            # Créer un nouveau contexte isolé pour ce site
            # Utiliser un User-Agent aléatoire pour chaque tentative
            current_user_agent = _get_random_user_agent()
            
            context_options = {
                "viewport": {"width": 1920 + random.randint(-50, 50), "height": 1080 + random.randint(-50, 50)},
                "user_agent": current_user_agent,
                "locale": "fr-FR",
                "timezone_id": "Europe/Paris",
                "extra_http_headers": {
                    "Accept-Language": "fr-FR,fr;q=0.9,en-US;q=0.8,en;q=0.7",
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
                    "DNT": "1",
                    "Upgrade-Insecure-Requests": "1",
                    "Sec-Fetch-Dest": "document",
                    "Sec-Fetch-Mode": "navigate",
                    "Sec-Fetch-Site": "none",
                    "Sec-Fetch-User": "?1",
                }
            }
            
            # Ajouter le proxy si configuré pour Amazon
            if "amazon" in domain:
                proxy = _get_amazon_proxy()
                if proxy:
                    context_options["proxy"] = {"server": proxy}
                    logger.info(f"Using proxy for Amazon: {proxy}")

            context = await browser.new_context(**context_options)
            
            # Injecter le script de stealth
            await context.add_init_script(STEALTH_JS)
            
            # Bloquer les ressources inutiles
            await context.route("**/*.{png,jpg,jpeg,gif,webp,svg,ico}", lambda route: route.abort())
            await context.route("**/analytics*", lambda route: route.abort())
            await context.route("**/tracking*", lambda route: route.abort())
            
            page = await context.new_page()

            # Naviguer vers la page de recherche
            await page.goto(final_url, wait_until="domcontentloaded", timeout=int(timeout * 1000))

            # Simulation de comportement humain
            if "amazon" in domain:
                await _simulate_human_behavior(page)

            # Accepter les cookies si nécessaire
            await _accept_cookies(page, domain)

            # Attendre que les résultats se chargent
            if wait_selector:
                try:
                    await page.wait_for_selector(wait_selector, timeout=10000)
                except Exception:
                    logger.debug(f"Selector {wait_selector} non trouvé sur {domain}, on continue...")

            # Attendre un peu pour le JS (réduit pour parallélisation)
            await asyncio.sleep(1.5)

            # Extraire le HTML
            html_content = await page.content()

            # Check for CAPTCHA
            if "Enter the characters you see below" in html_content or "Saisissez les caractères" in html_content:
                logger.warning(f"CAPTCHA detected on {domain}!")
                _dump_debug_html(html_content, domain, query)
                # Si c'est un captcha, on peut vouloir réessayer ou abandonner. 
                # Ici on retourne vide pour cette tentative, ce qui déclenchera peut-être un retry si on levait une exception,
                # mais le code original retournait [].
                # Pour le retry, on va lever une exception si c'est Amazon
                if "amazon" in domain:
                    raise Exception("CAPTCHA detected")
                return []

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
                    # logger.debug(f"Ignored external link: {href}")
                    continue

                # Filtrer les liens non-produits
                if _is_non_product_url(href):
                    # logger.debug(f"Ignored non-product link: {href}")
                    continue

                # Extraire le titre
                title = _extract_title(link)
                if not title or len(title) < MIN_TITLE_LENGTH:
                    # logger.debug(f"Ignored link with no title: {href}")
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
            
            if len(results) == 0:
                logger.warning(f"{domain}: 0 results found. Dumping HTML for debugging.")
                _dump_debug_html(html_content, domain, query)
                # Si 0 résultats sur Amazon, on peut vouloir réessayer
                if "amazon" in domain:
                     raise Exception("No results found")
                
            return results

        except Exception as e:
            logger.error(f"Erreur Browserless sur {domain} (tentative {attempt+1}): {e}")
            if attempt == max_retries - 1:
                return []
            
        finally:
            # Fermer le contexte et la page, mais PAS le navigateur
            try:
                if page:
                    await page.close()
                if context:
                    await context.close()
            except Exception as e:
                logger.debug(f"Erreur fermeture contexte {domain}: {e}")

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

    # Textes de liens à exclure (navigation, actions, etc.)
    bad_texts = [
        "voir plus", "voir tout", "tout voir", "afficher plus",
        "suivant", "précédent", "next", "previous", "back",
        "accueil", "home", "menu", "filtrer", "trier",
        "conditions", "mentions", "contact", "aide",
        "connexion", "inscription", "panier", "compte",
        "retour", "livraison", "cgv", "cgu",
        "top ventes", "nouveautés", "promotions", "soldes",
        "nos magasins", "découvrir", "en savoir plus",
        "valider", "ok", "fermer", "accepter",
        "choisir", "modifier", "supprimer", "ajouter",
        "comparer", "wishlist", "favoris",
        "imprimer", "partager", "envoyer",
        "plan du site", "sitemap",
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

    # Dédupliquer et filtrer par texte
    seen = set()
    unique_links = []
    for link in links:
        href = link.get("href", "")
        if not href or href in seen:
            continue
            
        # Vérification du texte du lien
        link_text = link.get_text(strip=True).lower()
        
        # Si le texte correspond exactement à un texte banni
        if any(bad_text == link_text for bad_text in bad_texts):
            continue
            
        # Si le texte contient des indicateurs de navigation forts
        if "voir tout" in link_text or "tous les produits" in link_text or "voir la gamme" in link_text:
            continue
            
        seen.add(href)
        unique_links.append(link)

    return unique_links


def _is_navigation_link(href: str) -> bool:
    """Vérifie si un lien est un lien de navigation (pas un produit)"""
    nav_patterns = [
        # Catégories et navigation
        "/category", "/categories", "/categorie", "/c/",
        "/rayon", "/rayons", "/univers", "/famille", "/groupe",
        "/brand", "/brands", "/marque", "/marques", "/fabricant",
        "/boutique", "/boutiques", "/shop", "/store",
        "/collection", "/collections", "/theme", "/themes",
        "/liste", "/list", "/listing",
        "/tag", "/tags", "/sujet", "/topic",
        "/catalog", "/catalogue",
        "/view-all", "/tous-les-produits", "/tout-voir",
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
        # Promotions et offres (patterns communs)
        "/promo/", "/promotions/", "/promotion/",
        "/soldes/", "/solde/",
        "/bon-plan", "/bons-plans",
        "/offres/", "/offre/", "/offre-",
        "/deals/", "/deal/",
        "/ventes-flash", "/vente-flash",
        # Services et pages informatives
        "/services/", "/service/",
        "/magasin", "/magasins", "/stores/", "/store/",
        "/blog", "/actualites", "/news",
        "/recettes", "/recipes",
        "/conseils", "/tips",
        "/guide", "/guides",
        # Patterns e-commerce spécifiques
        "/l-", "/lp-", "/landing",  # Landing pages (Cdiscount, etc.)
        "/selection", "/selections",
        "/top-", "/best-", "/nouveautes",
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
        # Navigation et catégories
        "/search", "/category", "/categories", "/categorie", "/c/",
        "/rayon", "/rayons", "/univers", "/famille", "/groupe",
        "/brand", "/brands", "/marque", "/marques", "/fabricant",
        "/boutique", "/boutiques", "/shop", "/store",
        "/collection", "/collections", "/theme", "/themes",
        "/liste", "/list", "/listing",
        "/tag", "/tags", "/sujet", "/topic",
        "/catalog", "/catalogue",
        "/view-all", "/tous-les-produits", "/tout-voir",
        # Pages utilisateur
        "/help", "/contact", "/about", "/account", "/cart", "/checkout",
        "/login", "/register", "/wishlist", "/compare", "/reviews",
        "/mon-compte", "/connexion", "/inscription", "/panier",
        # Pages légales
        "/terms", "/privacy", "/faq", "/shipping", "/returns",
        "/cgv", "/cgu", "/mentions-legales", "/donnees-personnelles",
        # Erreurs
        "/503", "/error", "/robot", "/captcha",
        # Applications et services
        "/application", "/courses", "/app/", "/mobile",
        # Landing pages et promotions (patterns spécifiques e-commerce français)
        "/l-", "/lp-", "/landing",  # Cdiscount landing pages
        "/promo/", "/soldes/", "/bon-plan", "/offre-", "/deals/",
        "/selection", "/top-", "/best-", "/nouveautes",
        "/guide", "/conseil", "/blog", "/actualites",
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
