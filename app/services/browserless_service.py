"""
Browserless Service
Manages connections to Browserless.io with advanced stealth capabilities.
Handles:
- Connection lifecycle
- Stealth injection
- Proxy rotation
- Human behavior simulation
"""

import asyncio
import logging
import random
import time
from typing import Optional, Any

from playwright.async_api import async_playwright, Browser, BrowserContext, Page
from app.core.search_config import (
    BROWSERLESS_URL, 
    get_amazon_proxies, 
    get_random_user_agent,
    COOKIE_ACCEPT_SELECTORS
)

logger = logging.getLogger(__name__)

# Stealth JS to inject
STEALTH_JS = """
// Advanced Stealth Mode
Object.defineProperty(navigator, 'webdriver', { get: () => false });
delete Object.getPrototypeOf(navigator).webdriver;
window.chrome = { runtime: {} };
Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3, 4, 5] });
Object.defineProperty(navigator, 'languages', { get: () => ['fr-FR', 'fr', 'en-US', 'en'] });
"""

class BrowserlessService:
    def __init__(self):
        self._playwright = None
        self._browser: Optional[Browser] = None
        self._proxies = get_amazon_proxies()

    async def start(self):
        """Initialize the browser connection"""
        if not self._playwright:
            self._playwright = await async_playwright().start()
        
        if not self._browser or not self._browser.is_connected():
            try:
                logger.info(f"Connecting to Browserless at {BROWSERLESS_URL}")
                # Use the stealth endpoint if possible, otherwise standard
                # Note: /chromium/stealth might need specific token or config, 
                # falling back to standard connect_over_cdp which is safer for generic browserless
                self._browser = await self._playwright.chromium.connect_over_cdp(
                    BROWSERLESS_URL,
                    timeout=60000
                )
            except Exception as e:
                logger.error(f"Failed to connect to Browserless: {e}")
                raise

    async def stop(self):
        """Close resources"""
        if self._browser:
            await self._browser.close()
        if self._playwright:
            await self._playwright.stop()

    async def get_context(self, use_proxy: bool = False) -> BrowserContext:
        """Create a new context with stealth settings"""
        await self.start()
        
        user_agent = get_random_user_agent()
        
        options = {
            "viewport": {"width": 1920, "height": 1080},
            "user_agent": user_agent,
            "locale": "fr-FR",
            "timezone_id": "Europe/Paris",
            "java_script_enabled": True,
            "bypass_csp": True,
            "extra_http_headers": {
                "Accept-Language": "fr-FR,fr;q=0.9,en-US;q=0.8,en;q=0.7",
                "Sec-Ch-Ua-Platform": '"Windows"',
                "Upgrade-Insecure-Requests": "1",
            }
        }

        if use_proxy and self._proxies:
            proxy = random.choice(self._proxies)
            options["proxy"] = proxy
            logger.info(f"Using proxy: {proxy['server'].split('//')[1]}")

        context = await self._browser.new_context(**options)
        
        # Inject Stealth JS
        await context.add_init_script(STEALTH_JS)
        
        # Block aggressive tracking but keep images for visual verification if needed
        # (Optimized for speed vs detection)
        await context.route("**/*", lambda route: route.continue_())
        
        return context

    async def simulate_human_behavior(self, page: Page):
        """Simulate random mouse movements and scrolling"""
        try:
            # Mouse movements
            for _ in range(random.randint(2, 5)):
                await page.mouse.move(
                    random.randint(100, 1800),
                    random.randint(100, 900)
                )
                await asyncio.sleep(random.uniform(0.1, 0.3))
            
            # Scrolling
            await page.evaluate("window.scrollBy(0, 300)")
            await asyncio.sleep(random.uniform(0.5, 1.0))
            await page.evaluate("window.scrollBy(0, -100)")
        except Exception:
            pass

    async def handle_popups(self, page: Page):
        """Attempt to close cookie banners and popups"""
        try:
            # Check for multiple popups (cookies + promo)
            # We iterate through all selectors and click any that are visible
            # We do this in a loop to handle sequential popups
            for _ in range(3): # Try up to 3 times for sequential popups
                clicked_something = False
                for selector in COOKIE_ACCEPT_SELECTORS:
                    try:
                        # Use a short timeout for check
                        element = page.locator(selector).first
                        if await element.is_visible(timeout=100):
                            await element.click()
                            logger.info(f"Closed popup/banner with {selector}")
                            await asyncio.sleep(0.5) # Wait for animation
                            clicked_something = True
                    except Exception:
                        continue
                
                if not clicked_something:
                    break
        except Exception:
            pass

    async def get_page_content(self, url: str, use_proxy: bool = False, wait_selector: str = None) -> tuple[str, str]:
        """
        Fetch page content with full stealth lifecycle.
        Returns (html_content, screenshot_path)
        """
        context = await self.get_context(use_proxy=use_proxy)
        page = await context.new_page()
        
        try:
            logger.info(f"Navigating to {url}")
            # Random delay before start
            await asyncio.sleep(random.uniform(0.5, 1.5))
            
            response = await page.goto(url, wait_until="domcontentloaded", timeout=60000)
            
            if response.status == 503:
                logger.warning(f"503 Detected on {url}")
                # Retry logic could be handled here or by caller, 
                # for now we return what we have, caller decides
            
            # Handle pre-search interaction if configured (e.g. Centrakor store selection)
            # We can't easily pass the config here without changing the signature,
            # but we can check if the URL matches a site with pre_search_selector
            from app.core.search_config import SITE_CONFIGS
            for config in SITE_CONFIGS.values():
                if config.get("pre_search_selector") and config["search_url"].split("/")[2] in url:
                    try:
                        selector = config["pre_search_selector"]
                        logger.info(f"Attempting pre-search interaction: {selector}")
                        if await page.locator(selector).is_visible(timeout=5000):
                            await page.click(selector)
                            logger.info("Clicked pre-search selector")
                            await asyncio.sleep(2) # Wait for transition
                    except Exception as e:
                        logger.warning(f"Pre-search interaction failed: {e}")
                    break

            await self.handle_popups(page)
            await self.simulate_human_behavior(page)
            
            if wait_selector:
                try:
                    await page.wait_for_selector(wait_selector, timeout=10000)
                except Exception:
                    logger.warning(f"Wait selector {wait_selector} timed out")

            # Wait for network idle to ensure dynamic content loads
            try:
                await page.wait_for_load_state("networkidle", timeout=5000)
            except Exception:
                pass

            content = await page.content()
            
            # Take screenshot if needed for AI analysis
            screenshot_path = ""
            try:
                import os
                from datetime import datetime
                
                # Ensure directory exists
                screenshots_dir = "/app/screenshots"
                if not os.path.exists(screenshots_dir):
                    os.makedirs(screenshots_dir, exist_ok=True)
                
                timestamp = int(time.time() * 1000)
                safe_name = "".join(c if c.isalnum() else "_" for c in url.split("//")[-1])[:50]
                filename = f"{safe_name}_{timestamp}.jpg"
                screenshot_path = f"{screenshots_dir}/{filename}"
                
                await page.screenshot(path=screenshot_path, full_page=False, quality=80, type="jpeg")
                logger.info(f"Screenshot saved to {screenshot_path}")
            except Exception as e:
                logger.warning(f"Failed to take screenshot: {e}")

            return content, screenshot_path

        except Exception as e:
            logger.error(f"Error fetching {url}: {e}")
            return "", ""
        finally:
            await context.close()

# Global instance
browserless_service = BrowserlessService()
