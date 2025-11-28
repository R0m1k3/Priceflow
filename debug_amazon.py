import asyncio
import logging
import os
from playwright.async_api import async_playwright

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

BROWSERLESS_URL = os.getenv("BROWSERLESS_URL", "ws://browserless:3000")

async def debug_amazon():
    logger.info("Starting Amazon Debug Script")
    
    async with async_playwright() as p:
        try:
            logger.info(f"Connecting to Browserless at {BROWSERLESS_URL}")
            browser = await p.chromium.connect_over_cdp(BROWSERLESS_URL)
            
            # Use a very standard, recent User-Agent
            user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            
            context = await browser.new_context(
                user_agent=user_agent,
                viewport={"width": 1920, "height": 1080},
                locale="fr-FR",
                timezone_id="Europe/Paris"
            )
            
            page = await context.new_page()
            
            url = "https://www.amazon.fr/s?k=iphone"
            logger.info(f"Navigating to {url}")
            
            response = await page.goto(url, wait_until="domcontentloaded", timeout=30000)
            
            if response:
                status = response.status
                logger.info(f"Response Status: {status}")
                
                content = await page.content()
                if "api-services-support@amazon.com" in content or "Toutes nos excuses" in content:
                    logger.error("BLOCK DETECTED: Found blocking message in content")
                else:
                    logger.info("No obvious blocking message found")
                    
                # Save screenshot
                await page.screenshot(path="debug_amazon_screenshot.png")
                logger.info("Screenshot saved to debug_amazon_screenshot.png")
                
            else:
                logger.error("No response received")
                
            await browser.close()
            
        except Exception as e:
            logger.error(f"An error occurred: {e}")

if __name__ == "__main__":
    asyncio.run(debug_amazon())
