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

    # Nettoyer les domaines (enlever protocole, www, etc.)
    clean_domains = [_clean_domain(d) for d in domains]
    clean_domains = [d for d in clean_domains if d]  # Filtrer les vides

    # Construire la requête avec site: pour chaque domaine
    site_query = " OR ".join([f"site:{domain}" for domain in clean_domains])
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
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
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
                if not any(domain in url_domain for domain in clean_domains):
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


def _clean_domain(domain: str) -> str:
    """Nettoie un domaine (enlève protocole, www, slash final, etc.)"""
    if not domain:
        return ""

    domain = domain.strip()

    # Si c'est une URL complète, extraire le domaine
    if domain.startswith(("http://", "https://")):
        domain = _extract_domain(domain)
    else:
        # Nettoyer le domaine directement
        domain = domain.lower()
        if domain.startswith("www."):
            domain = domain[4:]
        # Retirer le slash final
        domain = domain.rstrip("/")

    return domain


async def health_check() -> bool:
    """Vérifie que SearXNG est accessible"""
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(f"{SEARXNG_URL}/healthz")
            return response.status_code == 200
    except Exception as e:
        logger.warning(f"SearXNG health check failed: {e}")
        return False
