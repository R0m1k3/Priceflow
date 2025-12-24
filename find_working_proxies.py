import urllib.request
import logging
import concurrent.futures

# Setup logging
logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger("proxy_finder")

# Target URL for verification
TARGET_URL = "https://www.amazon.fr"


def fetch_proxy_list(url):
    try:
        req = urllib.request.Request(
            url, data=None, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
        )
        with urllib.request.urlopen(req, timeout=10) as response:
            if response.status == 200:
                text = response.read().decode("utf-8")
                proxies = [p.strip() for p in text.splitlines() if p.strip() and ":" in p]
                logger.info(f"Fetched {len(proxies)} proxies from {url}")
                return proxies
    except Exception as e:
        logger.error(f"Failed to fetch from {url}: {e}")
    return []


def check_proxy_fast(proxy):
    try:
        proxy_handler = urllib.request.ProxyHandler({"http": proxy, "https": proxy})
        opener = urllib.request.build_opener(proxy_handler)
        opener.addheaders = [("User-Agent", "Mozilla/5.0")]
        with opener.open(TARGET_URL, timeout=5) as response:
            # 200, 403, 503 all mean the proxy is alive (amazon may block but proxy works)
            if response.status in [200, 403, 503]:
                return proxy
    except:
        pass
    return None


def main():
    logger.info("Starting proxy finder (FAST MODE)...")

    sources = [
        "https://api.proxyscrape.com/v2/?request=getproxies&protocol=http&timeout=10000&country=all&ssl=all&anonymity=all",
        "https://raw.githubusercontent.com/TheSpeedX/PROXY-List/master/http.txt",
        "https://raw.githubusercontent.com/ShiftyTR/Proxy-List/master/http.txt",
        "https://raw.githubusercontent.com/monosans/proxy-list/main/proxies/http.txt",
    ]

    # 1. Fetch all proxies
    all_proxies = set()
    for url in sources:
        proxies = fetch_proxy_list(url)
        if proxies:
            all_proxies.update(proxies)

    # Add local raw proxies
    local_raw = [
        "164.68.110.241:8091",
        "164.68.110.241:9992",
        "173.212.246.157:3128",
        "142.111.48.253:7030",
        "31.59.20.176:6754",
        "23.95.150.145:6114",
        "198.23.239.134:6540",
        "107.172.163.27:6543",
        "198.105.121.200:6462",
        "64.137.96.74:6641",
        "84.247.60.125:6095",
        "216.10.27.159:6837",
        "142.111.67.146:5611",
    ]
    all_proxies.update(local_raw)

    print(f"\nTesting {len(all_proxies)} unique proxies against {TARGET_URL}...")

    working_proxies = []

    # Use ThreadPoolExecutor for speed
    with concurrent.futures.ThreadPoolExecutor(max_workers=100) as executor:
        future_to_proxy = {executor.submit(check_proxy_fast, p): p for p in all_proxies}

        count = 0
        total = len(all_proxies)

        for future in concurrent.futures.as_completed(future_to_proxy):
            count += 1
            if count % 500 == 0:
                print(f"Processed {count}/{total} - Found {len(working_proxies)} so far")

            res = future.result()
            if res:
                print(f"ALIVE: {res}")
                working_proxies.append(res)
                # Stop if we have enough
                if len(working_proxies) >= 30:
                    print("Found 30 proxies, stopping.")
                    executor.shutdown(wait=False, cancel_futures=True)
                    break

    print("\n" + "=" * 50)
    print(f"FOUND {len(working_proxies)} WORKING PROXIES")
    print("=" * 50)

    # Format for python list
    formatted_list = "[\n" + ",\n".join([f'    "{p}"' for p in working_proxies]) + "\n]"
    print(formatted_list)

    # Save to file
    with open("working_proxies.txt", "w") as f:
        f.write("\n".join(working_proxies))


if __name__ == "__main__":
    main()
