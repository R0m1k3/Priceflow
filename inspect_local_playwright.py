import asyncio
import logging
import os
from playwright.async_api import async_playwright

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def inspect_local():
    url = "https://www.lincroyable.fr/recherche-query=iphone/"
    print(f"Inspecting {url} using local Playwright...")

    async with async_playwright() as p:
        # Launch local browser (headless=True matches server environment usually, but we can try False to see)
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        page = await context.new_page()

        try:
            logging.info(f"Navigating to {url}")
            await page.goto(url, timeout=30000)
            logging.info("Navigation successful")

            content = await page.content()
            with open("lincroyable_local_dump.html", "w", encoding="utf-8") as f:
                f.write(content)
            print("HTML dumped to lincroyable_local_dump.html")

            await page.screenshot(path="lincroyable_local.png")
            print("Screenshot saved to lincroyable_local.png")

        except Exception as e:
            logging.error(f"Error: {e}")
            try:
                await page.screenshot(path="lincroyable_error.png")
            except:
                pass
        finally:
            await browser.close()


if __name__ == "__main__":
    asyncio.run(inspect_local())
