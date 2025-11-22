"""
SearXNG Service - Client pour le moteur de recherche auto-hébergé
"""

import logging
import os
from urllib.parse import quote_plus

import httpx

logger = logging.getLogger(__name__)

SEARXNG_URL = os.getenv("SEARXNG_URL", "http://searxng:8080")


class SearXNGResult:
    """Résultat de recherche SearXNG"""

    def __init__(self, url: str, title: str, snippet: str, source: str):
        self.url = url
        self.title = title
        self.snippet = snippet
        self.source = source

    def __repr__(self):
        return f"SearXNGResult(url={self.url}, title={self.title[:30]}...)"


async def search(
    query: str,
    domains: list[str],
    max_results: int = 20,
    timeout: float = 15.0,
) -> list[SearXNGResult]:
    """
    Effectue une recherche SearXNG ciblée sur les domaines spécifiés.

    Args:
        query: Terme de recherche (ex: "lutin de noel")
        domains: Liste des domaines à cibler (ex: ["amazon.fr", "fnac.com"])
        max_results: Nombre maximum de résultats à retourner
        timeout: Timeout en secondes

    Returns:
        Liste de SearXNGResult avec url, title, snippet, source
    """
    if not domains:
        logger.warning("Aucun domaine spécifié pour la recherche")
        return []

    # Construire la requête avec site: pour chaque domaine
    site_query = " OR ".join([f"site:{domain}" for domain in domains])
    full_query = f"{query} ({site_query})"

    logger.info(f"Recherche SearXNG: {full_query}")

    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.get(
                f"{SEARXNG_URL}/search",
                params={
                    "q": full_query,
                    "format": "json",
                    "language": "fr",
                    "safesearch": 0,
                    "pageno": 1,
                },
                headers={
                    "Accept": "application/json",
                    "X-Forwarded-For": "127.0.0.1",
                    "X-Real-IP": "127.0.0.1",
                },
            )
            response.raise_for_status()
            data = response.json()

            results = []
            seen_urls = set()

            for item in data.get("results", []):
                url = item.get("url", "")

                # Éviter les doublons
                if url in seen_urls:
                    continue
                seen_urls.add(url)

                # Vérifier que l'URL appartient à un des domaines ciblés
                url_domain = _extract_domain(url)
                if not any(domain in url_domain for domain in domains):
                    continue

                results.append(
                    SearXNGResult(
                        url=url,
                        title=item.get("title", ""),
                        snippet=item.get("content", ""),
                        source=url_domain,
                    )
                )

                if len(results) >= max_results:
                    break

            logger.info(f"SearXNG: {len(results)} résultats trouvés")
            return results

    except httpx.TimeoutException:
        logger.error(f"Timeout SearXNG après {timeout}s")
        return []
    except httpx.HTTPStatusError as e:
        logger.error(f"Erreur HTTP SearXNG: {e.response.status_code}")
        return []
    except Exception as e:
        logger.error(f"Erreur SearXNG: {e}")
        return []


def _extract_domain(url: str) -> str:
    """Extrait le domaine d'une URL"""
    try:
        from urllib.parse import urlparse

        parsed = urlparse(url)
        domain = parsed.netloc.lower()
        # Retirer www. si présent
        if domain.startswith("www."):
            domain = domain[4:]
        return domain
    except Exception:
        return ""


async def health_check() -> bool:
    """Vérifie que SearXNG est accessible"""
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(f"{SEARXNG_URL}/healthz")
            return response.status_code == 200
    except Exception as e:
        logger.warning(f"SearXNG health check failed: {e}")
        return False
