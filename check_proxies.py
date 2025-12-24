import asyncio
import os
import sys

# Add app to path
sys.path.insert(0, os.getcwd())

from playwright.async_api import async_playwright
from app.core.search_config import get_amazon_proxies


async def check_proxy(proxy, semaphore):
    async with semaphore:
        proxy_url = proxy["server"]
        print(f"Testing {proxy_url}...")

        async with async_playwright() as p:
            # Connect to browserless or launch local
            # Using launch local for simpler testing without ws dependency if possible
            # But the app uses browserless. Let's try launch first.
            try:
                browser = await p.chromium.launch(headless=True, proxy=proxy)
                page = await browser.new_page()
                try:
                    # amazon.fr might block, use httpbin for connectivity check
                    await page.goto("http://httpbin.org/ip", timeout=15000)
                    content = await page.content()
                    print(f"✅ {proxy_url}: Success")
                    await browser.close()
                    return True
                except Exception as e:
                    print(f"❌ {proxy_url}: Failed - {str(e)[:100]}")
                    await browser.close()
                    return False
            except Exception as e:
                print(f"❌ {proxy_url}: Launch Failed - {str(e)[:100]}")
                return False


async def main():
    proxies = get_amazon_proxies()
    print(f"Checking {len(proxies)} proxies...")

    semaphore = asyncio.Semaphore(3)  # Limit concurrency
    results = await asyncio.gather(*[check_proxy(p, semaphore) for p in proxies])

    working = sum(results)
    print(f"\nSummary: {working}/{len(proxies)} working.")


if __name__ == "__main__":
    asyncio.run(main())
