import asyncio
import logging
import sys
from playwright.async_api import async_playwright

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

URL = "https://www.gifi.fr/meuble-et-deco/decoration/bougie-et-senteur/diffuseur-et-senteur/encens-nag-champa-15-g/000000000000540823.html"

async def reproduce_scrape():
    logger.info("Starting reproduction script...")
    async with async_playwright() as p:
        # Launch browser (headless=True by default which is what we want for reproduction usually)
        # But for debugging blocking, sometimes headless=False helps. Let's start with True (default)
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            viewport={"width": 1920, "height": 1080},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        
        page = await context.new_page()
        
        logger.info(f"Navigating to {URL}...")
        try:
            await page.goto(URL, wait_until="domcontentloaded", timeout=60000)
            logger.info("Page loaded.")
            
            # Wait a bit for dynamic content
            await page.wait_for_timeout(5000)
            
            # Extract title
            title = await page.title()
            logger.info(f"Page Title: {title}")
            
            # Extract body text
            content = await page.content()
            body_text = await page.inner_text("body")
            
            logger.info(f"Content Length: {len(content)}")
            logger.info(f"Body Text Length: {len(body_text)}")
            
            # Check for price
            if "€" in body_text:
                logger.info("Found '€' in body text.")
            else:
                logger.warning("'€' NOT found in body text.")
                
            # specific check for likely price
            import re
            prices = re.findall(r'\d+[,\.]\d{2}\s*€', body_text)
            logger.info(f"Prices found in text: {prices}")

            # Save content for review
            with open("gifi_reproduction.html", "w", encoding="utf-8") as f:
                f.write(content)
            logger.info("Saved gifi_reproduction.html")
            
        except Exception as e:
            logger.error(f"Error during navigation/scraping: {e}")
            
        finally:
            await browser.close()

if __name__ == "__main__":
    asyncio.run(reproduce_scrape())
