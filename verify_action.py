import asyncio
import logging
from playwright.async_api import async_playwright

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def verify_action():
    async with async_playwright() as p:
        # Use a standard User Agent
        ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(user_agent=ua)
        page = await context.new_page()
        
        # 1. Perform Search
        logger.info("--- Step 1: Searching for 'Chaise' on Action ---")
        search_url = "https://www.action.com/fr-fr/search/?q=Chaise"
        
        try:
            await page.goto(search_url, wait_until="domcontentloaded", timeout=30000)
            # Wait a bit for any JS redirects or challenges
            await page.wait_for_timeout(5000)
        except Exception as e:
            logger.error(f"Navigation error: {e}")

        # 2. Take Screenshot
        await page.screenshot(path="action_debug.png")
        logger.info("Screenshot saved: action_debug.png")
        
        # 3. Dump Content
        content = await page.content()
        logger.info(f"HTML Content Length: {len(content)}")
        
        # 4. Check for specific text
        text = await page.inner_text("body")
        logger.info(f"Page Text (first 500 chars): {text[:500]}")
        
        if "Challenge" in text or "human" in text or "Cloudflare" in text:
            logger.warning("⚠️ Cloudflare Challenge detected in text!")
            
        # 5. Analyze Content for Product Links
        # Action product URLs contain "/p/"
        links = await page.evaluate("""
            Array.from(document.querySelectorAll('a'))
            .map(a => a.href)
            .filter(href => href.includes('/p/'))
        """)
        
        logger.info(f"Found {len(links)} product links")
        if links:
            logger.info(f"First 5 links: {links[:5]}")
            
            # Find the parent container of the first link
            parent_html = await page.evaluate("""
                (() => {
                    const link = document.querySelector("a[href*='/p/']");
                    return link ? link.parentElement.outerHTML : "Not found";
                })()
            """)
            logger.info(f"Parent HTML of first link: {parent_html[:500]}")
            
            # Find the class of the link itself
            link_class = await page.evaluate("""
                (() => {
                    const link = document.querySelector("a[href*='/p/']");
                    return link ? link.className : "Not found";
                })()
            """)
            logger.info(f"Class of first link: {link_class}")


        
        await browser.close()

if __name__ == "__main__":
    asyncio.run(verify_action())
