import asyncio
import logging
import sys
import os

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), ".")))

from app.services.browserless_service import browserless_service

# Configure logging
logging.basicConfig(level=logging.INFO)


async def inspect():
    url = "https://www.lincroyable.fr/recherche-query=iphone/"
    print(f"Inspecting {url}...")

    # Use host port for local debugging
    os.environ["BROWSERLESS_URL"] = "ws://localhost:3012"

    await browserless_service.initialize()
    try:
        content, _ = await browserless_service.get_page_content(url, wait_selector="body")
        with open("lincroyable_dump.html", "w", encoding="utf-8") as f:
            f.write(content)
        print("HTML dumped to lincroyable_dump.html")
    finally:
        await browserless_service.shutdown()


if __name__ == "__main__":
    asyncio.run(inspect())
