import asyncio
import logging
import os
import random
from dataclasses import dataclass
from datetime import datetime

from playwright.async_api import Browser, BrowserContext, Page, async_playwright
from playwright.async_api import TimeoutError as PlaywrightTimeoutError

from app.core.search_config import SITE_CONFIGS, get_amazon_proxies, get_random_stealth_config

logger = logging.getLogger(__name__)

BROWSERLESS_URL = os.getenv("BROWSERLESS_URL", "ws://browserless:3000")

POPUP_SELECTORS = [
    "button[aria-label='Close']",
    "button[aria-label='close']",
    ".close-button",
    ".modal-close",
    "svg[data-name='Close']",
    "[class*='popup'] button",
    "[class*='modal'] button",
    "button:has-text('No, thanks')",
    "button:has-text('No thanks')",
    "a:has-text('No, thanks')",
    "div[role='dialog'] button[aria-label='Close']",
    # Amazon Interstitials & Cookies
    "button:has-text('Continuer les achats')",
    "span:has-text('Continuer les achats')",
    "a:has-text('Continuer les achats')",
    "input[value='Continuer les achats']",
    "input[value='Continue shopping']",
    "input[value='Continue shopping']",
    "form:has-text('Continuer les achats') input[type='submit']",
    "[aria-labelledby='continue-shopping-label']",
    "#sp-cc-accept",
    "#sp-cc-rejectall-link",
    "button[data-action='a-popover-close']",
    "[data-action='sp-cc-accept']",
    "input[aria-labelledby='sp-cc-accept-label']",
    # Didomi / Gifi
    "#didomi-notice-agree-button",
    "button[id='didomi-notice-agree-button']",
    "span:has-text('Accepter & Fermer')",
    "button:has-text('Accepter & Fermer')",
    # Common banners
    "#onetrust-accept-btn-handler",
    ".cookie-consent-accept",
    "[data-action='accept-cookies']",
    "button[id*='accept']",
    "button[class*='accept']",
]


# Random User-Agents to alternate fingerprint
AMAZON_USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:133.0) Gecko/20100101 Firefox/133.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Safari/605.1.15",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36 Edg/131.0.0.0",
]


@dataclass
class ScrapeConfig:
    """Configuration for scraping parameters."""

    smart_scroll: bool = False
    scroll_pixels: int = 350
    text_length: int = 0
    timeout: int = 90000


class ScraperService:
    _playwright = None
    _browser: Browser | None = None
    _lock = asyncio.Lock()

    @classmethod
    async def initialize(cls):
        """Initialize the shared browser instance (Public, Thread-Safe)."""
        async with cls._lock:
            await cls._initialize()

    @classmethod
    async def _initialize(cls):
        """Internal initialization logic (Assumes lock is held)."""
        if cls._browser is None:
            logger.info("Initializing ScraperService shared browser...")
            cls._playwright = await async_playwright().start()
            cls._browser = await cls._connect_browser(cls._playwright)
            logger.info("ScraperService initialized.")

    @classmethod
    async def shutdown(cls):
        """Shutdown the shared browser instance."""
        async with cls._lock:
            if cls._browser:
                logger.info("Shutting down ScraperService shared browser...")
                await cls._browser.close()
                cls._browser = None
            if cls._playwright:
                await cls._playwright.stop()
                cls._playwright = None
            logger.info("ScraperService shutdown complete.")

    @classmethod
    async def _ensure_browser_connected(cls) -> bool:
        """Ensure browser is connected, reconnect if needed."""
        async with cls._lock:
            try:
                if cls._browser is None:
                    logger.warning("Browser not initialized, initializing...")
                    await cls._initialize()
                    return cls._browser is not None

                # Test if browser is still alive by trying to create a context
                try:
                    test_context = await cls._browser.new_context()
                    await test_context.close()
                    return True
                except Exception as e:
                    logger.error(f"Browser connection test failed: {e}")
                    logger.info("Attempting to reconnect browser...")
                    # Clear the old browser
                    cls._browser = None
                    if cls._playwright:
                        try:
                            await cls._playwright.stop()
                        except Exception:
                            pass
                        cls._playwright = None
                    # Reconnect
                    await cls._initialize()
                    return cls._browser is not None
            except Exception as e:
                logger.error(f"Failed to ensure browser connection: {e}")
                return False

    @staticmethod
    async def scrape_item(
        url: str,
        selector: str | None = None,
        item_id: int | None = None,
        config: ScrapeConfig | None = None,
        return_html: bool = False,
        retries: int = 3
    ) -> tuple[str | None, str, str, str]:
        """
        Scrapes the given URL using Browserless and Playwright.
        Returns a tuple: (screenshot_path, page_text_or_html, final_url, page_title)
        """
        if config is None:
            config = ScrapeConfig()

        # Input validation & defaults
        scroll_pixels = max(350, config.scroll_pixels if config.scroll_pixels > 0 else 350)
        timeout = max(30000, config.timeout if config.timeout > 0 else 90000)

        for attempt in range(retries):
            # Ensure browser is connected and healthy
            if not await ScraperService._ensure_browser_connected():
                logger.error("Failed to establish browser connection")
                if attempt < retries - 1:
                    await asyncio.sleep(2)
                    continue
                return None, "", url, ""

            try:
                # Determine Proxy & Selector Requirement
                from urllib.parse import urlparse
                domain = urlparse(url).netloc.replace("www.", "")
                
                # Check SITE_CONFIGS for proxy requirement and default selector
                requires_proxy = False
                config_selector = None
                
                if domain in SITE_CONFIGS:
                    requires_proxy = SITE_CONFIGS[domain].get("requires_proxy", False)
                    config_selector = SITE_CONFIGS[domain].get("price_selector")
                elif f"www.{domain}" in SITE_CONFIGS: # Fallback check
                     cfg = SITE_CONFIGS[f"www.{domain}"]
                     requires_proxy = cfg.get("requires_proxy", False)
                     config_selector = cfg.get("price_selector")
                
                # Use config selector if none provided
                if not selector and config_selector:
                    logger.info(f"Using configured price selector for {domain}: {config_selector}")
                    selector = config_selector

                # Special override: If Action.com, force proxy ONLY if strictly needed and proxies are available
                # if "action.com" in domain:
                #    requires_proxy = True

                proxy = None
                if requires_proxy:
                    proxies = get_amazon_proxies() # Reusing Amazon proxies for hard sites
                    if proxies:
                        proxy = random.choice(proxies)
                        # Rotate proxy on retry
                        if attempt > 0:
                             proxy = random.choice(proxies)

                # SPECIALIZED AMAZON HANDLING
                if "amazon" in url:
                    return await ScraperService._scrape_amazon_specific(url, item_id, config, return_html, proxy)

                # SPECIALIZED ACTION HANDLING (Rupture de stock check)
                is_action = "action.com" in url


                context = await ScraperService._create_context(ScraperService._browser, url, proxy=proxy)
                page = await context.new_page()

                try:
                    # Random delay to simulate human lead-in
                    await asyncio.sleep(random.uniform(0.5, 2.0))
                    
                    await ScraperService._navigate_and_wait(page, url, timeout)
                    final_url = page.url
                    page_title = await page.title()
                    
                    # Humanize: scroll a bit and back
                    try:
                        await page.mouse.move(random.randint(100, 500), random.randint(100, 500))
                        await page.evaluate("window.scrollBy(0, 100)")
                        await asyncio.sleep(0.5)
                        await page.evaluate("window.scrollBy(0, -100)")
                    except Exception:
                        pass

                    await ScraperService._handle_popups(page)

                    # FORCER LE MAGASIN NANCY POUR B&M STORES
                    if "bmstores.fr" in url:
                        try:
                            logger.info("B&M Stores detected: checking store selection (Nancy)...")
                            # Check if store is already selected or if modal is needed
                            store_btn = page.locator(".mod-shops .btn-shop, .js-show-shops")
                            if await store_btn.count() > 0:
                                logger.info("Opening store selector...")
                                await store_btn.first.click(timeout=2000)
                                await page.wait_for_timeout(1000)
                                
                                # Type Nancy in the search input
                                search_input = page.locator("#search_mag")
                                if await search_input.count() > 0:
                                    await search_input.fill("Nancy")
                                    await page.keyboard.press("Enter")
                                    await page.wait_for_timeout(1500)
                                    
                                    # Select the first Nancy store (Nancy Essey or Nancy Centre)
                                    select_btn = page.locator(".shop-list .btn-select-shop, button:has-text('Choisir ce magasin')")
                                    if await select_btn.count() > 0:
                                        logger.info("Selecting Nancy store...")
                                        await select_btn.first.click()
                                        await page.wait_for_timeout(2000)
                                        # Refresh page or wait for update
                                        await page.reload(wait_until="domcontentloaded")
                                        await page.wait_for_timeout(1000)
                        except Exception as e:
                            logger.warning(f"Failed to force B&M store Nancy: {e}")

                    if selector:
                        await ScraperService._wait_for_selector(page, selector)
                    else:
                        await ScraperService._auto_detect_price(page)

                    if config.smart_scroll:
                        await ScraperService._smart_scroll(page, scroll_pixels)

                    if return_html:
                        content_data = await page.content()
                    else:
                        content_data = await ScraperService._extract_text(page, config.text_length)
                    
                    screenshot_path = await ScraperService._take_screenshot(page, url, item_id)

                    return screenshot_path, content_data, final_url, page_title

                finally:
                    await context.close()

            except Exception as e:
                logger.error(f"❌ Error scraping {url} (Attempt {attempt+1}/{retries}): {e}")
                
                 # Check for critical browser failure
                error_str = str(e).lower()
                if "target page, context or browser has been closed" in error_str or "connection closed" in error_str:
                    logger.warning("⚠️ Critical browser failure detected. Triggering re-initialization.")
                    # Force re-initialization on next attempt
                    async with ScraperService._lock:
                        if ScraperService._browser:
                            try:
                                await ScraperService._browser.close()
                            except: pass
                            ScraperService._browser = None

                if attempt == retries - 1:
                    return None, "", url, ""
                
                # Exponential backoff
                await asyncio.sleep(2 * (attempt + 1))
        
        return None, "", url, ""

    @staticmethod
    async def _scrape_amazon_specific(
        url: str, item_id: int | None, config: ScrapeConfig, return_html: bool, proxy: dict | None = None
    ) -> tuple[str | None, str, str, str]:
        """
        Specialized scraping flow for Amazon to avoid bot detection and ensure good screenshots.
        Strategy:
        1. Emulate human visiting homepage first
        2. Navigate to product
        3. Aggressively handle popups
        4. Wait for main image to be visible
        """
        logger.info(f"🛒 Starting specialized Amazon scrape for: {url}")

        # Determine base domain
        from urllib.parse import urlparse

        parsed = urlparse(url)
        base_domain = f"{parsed.scheme}://{parsed.netloc}"

        context = await ScraperService._create_context(ScraperService._browser, url, proxy=proxy)
        page = await context.new_page()

        try:
            # 1. Warm-up: Visit Homepage to get cookies/session
            try:
                logger.info(f"🏠 Visiting {base_domain} to establish authentic session...")
                await page.goto(base_domain, wait_until="domcontentloaded", timeout=30000)
                await asyncio.sleep(2)
                await ScraperService._handle_popups(page)
            except Exception as e:
                logger.warning(f"Homepage warm-up failed (continuing anyway): {e}")

            # 2. Navigate to Product
            logger.info(f"➡️ Navigating to product page: {url}")
            await page.goto(url, wait_until="domcontentloaded", timeout=60000)

            final_url = page.url
            try:
                page_title = await page.title()
            except:
                page_title = "Amazon Product"

            # 3. Check for Hard Redirects (URL-based)
            if "/ap/signin" in page.url:
                logger.error("🚫 Amazon Login Redirect detected (URL)!")
                return None, "LOGIN_REQUIRED", final_url, page_title

            # 4. Handle Popups & Location Selectors
            await ScraperService._handle_popups(page)

            # Dismiss "Change Address" or specific Amazon location modals if any
            try:
                await page.evaluate(
                    "document.getElementById('nav-main')?.classList.remove('nav-progressive-attribute')"
                )
            except:
                pass

            # 5. Check for Bot Detection / CAPTCHA / Login (Content-based)
            # We do this AFTER popup removal because sometimes "Identifiez-vous" is in a dismissible modal
            content_check = await page.content()

            if (
                "Type the characters you see in this image" in content_check
                or "Saisissez les caractères que vous voyez" in content_check
            ):
                logger.error("🚫 Amazon CAPTCHA detected!")
                # Attempt refresh once
                logger.info("Retrying with refresh...")
                await page.reload()
                await asyncio.sleep(3)
                # Re-check
                content_check = await page.content()
                if "Type the characters you see in this image" in content_check:
                    return None, "CAPTCHA_DETECTED", final_url, page_title

            if "Identifiez-vous" in content_check or "ap_signin" in content_check:
                # Double check: is it a modal we missed? Try one last specific closure
                try:
                    close_btn = page.locator("button[data-action='a-popover-close'], .a-popover-close")
                    if await close_btn.count() > 0 and await close_btn.first.is_visible():
                        logger.info("Found login modal close button, clicking...")
                        await close_btn.first.click()
                        await page.wait_for_timeout(1000)
                        content_check = await page.content()  # Refresh content
                except:
                    pass

                if "Identifiez-vous" in content_check or "ap_signin" in content_check:
                    # Final Check: Do we have a product title?
                    # If we have a title, it's just a popup we missed/hid. Proceed.
                    # If NO title, it's a hard redirect/gate. Fail.
                    try:
                        title_check = page.locator("#productTitle, #title")
                        if await title_check.count() > 0 and await title_check.first.is_visible():
                            logger.info("⚠️ Login prompt detected but Product Title found. Ignoring/Hiding modal...")
                            # Attempt to brute-force remove the modal overlay again just in case
                            await page.evaluate(
                                "() => document.querySelectorAll('.a-popover-modal, .a-modal-scroller').forEach(e => e.remove())"
                            )
                        else:
                            # No title found, now we can try to reload or fail
                            logger.info("⚠️ Amazon Login/Auth detected and No Title found. Retrying with refresh...")
                            await page.reload()
                            await asyncio.sleep(3)
                            content_check = await page.content()

                            if "Identifiez-vous" in content_check or "ap_signin" in content_check:
                                # Re-check title after reload
                                if await title_check.count() > 0 and await title_check.first.is_visible():
                                    logger.info("⚠️ Title appeared after refresh despite login prompt.")
                                else:
                                    logger.error("🚫 Amazon Login Prompt detected (Blocking)!")
                                    return None, "LOGIN_REQUIRED", final_url, page_title
                    except Exception as e:
                        logger.error(f"🚫 Amazon Login Prompt detected (Error Checking Title: {e})")
                        return None, "LOGIN_REQUIRED", final_url, page_title

            # 6. Wait for Main Image (Critical for screenshot)
            logger.info("🖼️ Waiting for product image...")
            try:
                # Main image container on desktop
                await page.wait_for_selector(
                    "#imgTagWrapperId, #landingImage, #main-image-container, .imgTagWrapper", timeout=10000
                )
            except Exception as e:
                logger.warning(f"Could not find main image container: {e}")

            # 6. Smart User Behavior (Scroll to trigger lazy loading)
            if config.smart_scroll:
                await ScraperService._smart_scroll(page, config.scroll_pixels)
                # Scroll back up to header for good screenshot
                await page.evaluate("window.scrollTo(0, 0)")
                await asyncio.sleep(1)

            # 7. Extract Data
            if return_html:
                content_data = await page.content()
            else:
                content_data = await ScraperService._extract_text(page, config.text_length)

            # 8. Screenshot
            screenshot_path = await ScraperService._take_screenshot(page, url, item_id)

            return screenshot_path, content_data, final_url, page_title

        except Exception as e:
            logger.error(f"❌ Amazon specific scrape failed: {e}")
            return None, "", url, ""
        finally:
            await context.close()

    @staticmethod
    async def _connect_browser(p) -> Browser:
        logger.info(f"Connecting to Browserless at {BROWSERLESS_URL}")
        # Note: Added timeout for connection
        return await p.chromium.connect_over_cdp(BROWSERLESS_URL, timeout=30000)

    @staticmethod
    async def _create_context(browser: Browser, url: str, proxy: dict | None = None) -> BrowserContext:
        """Create context with advanced stealth and headers"""
        
        stealth_config = get_random_stealth_config()
        ua = stealth_config["ua"]
        ch = stealth_config["ch"]
        platform = stealth_config["platform"]

        logger.info(f"🎭 Using stealth profile: {ua[:50]}...")
        if proxy:
            logger.info(f"🛡️ Using Proxy: {proxy['server']}")

        # Determine base domain for referer
        from urllib.parse import urlparse
        parsed = urlparse(url)
        base_domain = f"{parsed.scheme}://{parsed.netloc}/"
        
        # Smart referer selection
        referer = get_random_referer(url)

        context = await browser.new_context(
            viewport={"width": 1920, "height": 1080},
            user_agent=ua,
            locale="fr-FR",
            timezone_id="Europe/Paris",
            java_script_enabled=True,
            bypass_csp=True,
            proxy=proxy,
            extra_http_headers={
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
                "Accept-Language": "fr-FR,fr;q=0.9,en-US;q=0.8,en;q=0.7",
                "Cache-Control": "max-age=0",
                "Sec-Ch-Ua": ch,
                "Sec-Ch-Ua-Mobile": "?0",
                "Sec-Ch-Ua-Platform": platform,
                "Sec-Fetch-Dest": "document",
                "Sec-Fetch-Mode": "navigate",
                "Sec-Fetch-Site": "none",
                "Sec-Fetch-User": "?1",
                "Upgrade-Insecure-Requests": "1",
                "Referer": referer
            }
        )

        # Advanced Stealth mode
        await context.add_init_script("""
            // Redefine webdriver
            Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
            
            // Masquerade plugins
            Object.defineProperty(navigator, 'plugins', { 
                get: () => [
                    { name: 'PDF Viewer', filename: 'internal-pdf-viewer' },
                    { name: 'Chrome PDF Viewer', filename: 'internal-pdf-viewer' },
                    { name: 'Chromium PDF Viewer', filename: 'internal-pdf-viewer' }
                ] 
            });
            
            // Languages
            Object.defineProperty(navigator, 'languages', { get: () => ['fr-FR', 'fr', 'en-US', 'en'] });

            // Chrome runtime
            window.chrome = { 
                runtime: {},
                loadTimes: function() {},
                csi: function() {},
                app: {}
            };

            // Overwrite permissions
            const originalQuery = window.navigator.permissions.query;
            window.navigator.permissions.query = (parameters) => (
                parameters.name === 'notifications' ?
                    Promise.resolve({ state: Notification.permission }) :
                    originalQuery(parameters)
            );
        """)

        await context.route("**/*", lambda route: route.continue_())
        return context

    @staticmethod
    async def _navigate_and_wait(page: Page, url: str, timeout: int):
        logger.info(f"Navigating to {url} (Timeout: {timeout}ms)")
        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=timeout)
            logger.info(f"Page loaded (domcontentloaded): {url}")

            try:
                await page.wait_for_load_state("networkidle", timeout=5000)
                logger.info("Network idle reached")
            except PlaywrightTimeoutError:
                logger.info("Network idle timed out (non-critical), proceeding...")

        except Exception as e:
            logger.warning(f"Navigation warning for {url}: {e}")

        # Wait a bit for dynamic content
        await page.wait_for_timeout(2000)

    @staticmethod
    async def _handle_popups(page: Page):
        """Aggressive multi-pass popup and overlay removal"""
        logger.info("Starting aggressive popup removal...")

        # 1. Multi-pass clicking (some popups appear after others are closed)
        for i in range(2):
            logger.debug(f"Popup removal pass {i + 1}")
            for selector in POPUP_SELECTORS:
                try:
                    locators = page.locator(selector)
                    count = await locators.count()
                    if count > 0:
                        for j in range(count):
                            target = locators.nth(j)
                            if await target.is_visible():
                                logger.info(f"Closing popup: {selector}")
                                await target.click(timeout=1000)
                                await page.wait_for_timeout(500)
                except Exception:
                    pass

            # Hammer Escape key
            try:
                await page.keyboard.press("Escape")
                await page.wait_for_timeout(200)
            except:
                pass

        # 2. Javascript cleanup (Hide pesky overlays and CMPs that won't close)
        logger.info("Injecting CSS/JS cleanup for persistent overlays...")
        await page.evaluate("""
            () => {
                const selectorsToHide = [
                    '#didomi-host', '.didomi-popup-container', '[id*="didomi"]',
                    '#onetrust-banner-sdk', '#onetrust-consent-sdk',
                    '.cookie-banner', '.cookie-consent', '.qc-cmp2-container',
                    '.modal-backdrop', '.modal-overlay', '.fade.show',
                    '.a-popover-modal', '.a-modal-scroller'
                ];
                
                // Hide specific IDs/classes
                selectorsToHide.forEach(s => {
                    const el = document.querySelector(s);
                    if (el) el.style.display = 'none';
                });

                // Clear overlays (fixed/absolute elements with high z-index that cover too much)
                const all = document.getElementsByTagName("*");
                for (let i = 0, max = all.length; i < max; i++) {
                    const el = all[i];
                    const style = window.getComputedStyle(el);
                    if (style.position === 'fixed' || style.position === 'absolute') {
                        const zIndex = parseInt(style.zIndex);
                        if (zIndex > 100) {
                            // Check if it's potentially a popup (covers a lot of area or has modal classes)
                            const rect = el.getBoundingClientRect();
                            if (rect.width > window.innerWidth * 0.5 && rect.height > window.innerHeight * 0.5) {
                                console.log('Hiding potential popup:', el);
                                el.style.setProperty('display', 'none', 'important');
                            }
                        }
                    }
                }
                
                // Unlock scroll if it was locked by a modal
                document.body.style.overflow = 'auto';
                document.documentElement.style.overflow = 'auto';
            }
        """)

        # Wait for any transitions
        await page.wait_for_timeout(1000)

    @staticmethod
    async def _wait_for_selector(page: Page, selector: str):
        try:
            logger.info(f"Waiting for selector: {selector}")
            await page.wait_for_selector(selector, timeout=5000)
            element = page.locator(selector).first
            await element.scroll_into_view_if_needed()
            logger.info(f"Scrolled to selector: {selector}")
        except Exception as e:
            logger.warning(f"Selector {selector} not found or timed out: {e}")

    @staticmethod
    async def _auto_detect_price(page: Page):
        logger.info("No selector provided. Attempting to find price element...")
        try:
            price_locator = page.locator("text=/$[0-9,]+(\\.[0-9]{2})?/")
            if await price_locator.count() > 0:
                await price_locator.first.scroll_into_view_if_needed()
                logger.info("Scrolled to potential price element")
        except Exception as e:
            logger.warning(f"Auto-price detection failed: {e}")

    @staticmethod
    async def _smart_scroll(page: Page, scroll_pixels: int):
        logger.info(f"Performing smart scroll ({scroll_pixels}px)...")
        try:
            await page.evaluate(f"window.scrollBy(0, {scroll_pixels})")
            await page.wait_for_timeout(1000)
        except Exception as e:
            logger.warning(f"Smart scroll failed: {e}")

    @staticmethod
    async def _extract_text(page: Page, text_length: int) -> str:
        if text_length <= 0:
            return ""

        try:
            logger.info(f"Extracting text (limit: {text_length} chars)...")

            # Smart extraction: remove noise (nav, footer, scripts) before getting text
            clean_text = await page.evaluate("""
                () => {
                    // Clone body to not affect the visual page
                    const clone = document.body.cloneNode(true);
                    
                    // Remove noise selectors
                    const noiseSelectors = [
                        'nav', 'header', 'footer', 'script', 'style', 'noscript', 'iframe',
                        '.cookie-banner', '.popup', '#menu', '.menu', '.sidebar',
                        '[role="navigation"]', '[role="banner"]', '[role="contentinfo"]'
                    ];
                    
                    noiseSelectors.forEach(selector => {
                        const elements = clone.querySelectorAll(selector);
                        elements.forEach(el => el.remove());
                    });
                    
                    return clone.innerText;
                }
            """)

            # Extra cleanup to prevent TitlePrice merging
            # If we are on Action, we might need specific spacing logic
            if "action.com" in page.url:
                 clean_text = await page.evaluate("""
                    () => {
                         const title = document.querySelector('h1, .product-title');
                         const price = document.querySelector('.price, .product-price');
                         
                         let text = document.body.innerText;
                         
                         // Manually construct clean string if elements found
                         if(title && price) {
                             return title.innerText + " " + price.innerText + "\\n" + text;
                         }
                         return text;
                    }
                 """)

            # Fallback if cleaning removed everything (unlikely but safe)
            if not clean_text or len(clean_text) < 100:
                logger.warning("Cleaned text too short, falling back to full body text")
                clean_text = await page.inner_text("body")

            # Collapse whitespace
            import re

            clean_text = re.sub(r"\s+", " ", clean_text).strip()

            page_text = clean_text[:text_length]
            logger.info(f"Extracted {len(page_text)} chars")
            return page_text
        except Exception as e:
            logger.error(f"Text extraction failed: {e}")
            return ""

    @staticmethod
    async def _take_screenshot(page: Page, url: str, item_id: int | None) -> str:
        screenshot_dir = "screenshots"
        os.makedirs(screenshot_dir, exist_ok=True)

        if item_id:
            # Use timestamp to ensure unique filenames (fixes caching issues)
            timestamp = int(datetime.now().timestamp())
            filename = f"{screenshot_dir}/item_{item_id}_{timestamp}.png"
        else:
            url_part = url.split("//")[-1].replace("/", "_")
            timestamp = datetime.now().timestamp()
            filename = f"{screenshot_dir}/{url_part}_{timestamp}.png"

        await page.screenshot(path=filename, full_page=False)
        logger.info(f"Screenshot saved to {filename}")
        return filename


def get_random_referer(target_url: str) -> str:
    """Return a random referer, prioritizing Google for Amazon."""
    if "amazon" in target_url:
        return "https://www.google.fr/"
    
    referers = [
        "https://www.google.fr/",
        "https://www.bing.com/",
        "https://www.qwant.com/",
        "https://duckduckgo.com/",
        "https://www.facebook.com/"
    ]
    return random.choice(referers)
