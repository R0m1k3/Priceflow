"""
DuckDuckGo Search Service - Recherche de produits via DuckDuckGo
"""

import asyncio
import logging
from urllib.parse import urlparse

from duckduckgo_search import DDGS

logger = logging.getLogger(__name__)


class SearchResult:
    """Résultat de recherche DuckDuckGo"""

    def __init__(self, url: str, title: str, snippet: str, source: str):
        self.url = url
        self.title = title
        self.snippet = snippet
        self.source = source

    def __repr__(self):
        return f"SearchResult(url={self.url}, title={self.title[:30]}...)"


async def search(
    query: str,
    domains: list[str],
    max_results: int = 20,
    timeout: float = 15.0,
) -> list[SearchResult]:
    """
    Effectue une recherche DuckDuckGo ciblée sur les domaines spécifiés.

    Args:
        query: Terme de recherche (ex: "lutin de noel")
        domains: Liste des domaines à cibler (ex: ["amazon.fr", "fnac.com"])
        max_results: Nombre maximum de résultats à retourner
        timeout: Timeout en secondes

    Returns:
        Liste de SearchResult avec url, title, snippet, source
    """
    if not domains:
        logger.warning("Aucun domaine spécifié pour la recherche")
        return []

    # Nettoyer les domaines (enlever protocole, www, etc.)
    clean_domains = [_clean_domain(d) for d in domains]
    clean_domains = [d for d in clean_domains if d]

    # Construire la requête avec site: pour chaque domaine
    site_query = " OR ".join([f"site:{domain}" for domain in clean_domains])
    full_query = f"{query} ({site_query})"

    logger.info(f"Recherche DuckDuckGo: {full_query}")

    try:
        # Exécuter la recherche dans un thread séparé (duckduckgo_search est synchrone)
        loop = asyncio.get_event_loop()
        results = await loop.run_in_executor(
            None,
            lambda: _do_search(full_query, max_results * 2, timeout),
        )

        # Filtrer pour ne garder que les domaines ciblés
        filtered_results = []
        seen_urls = set()

        for item in results:
            url = item.get("href", "") or item.get("link", "")
            if not url:
                continue

            # Éviter les doublons
            if url in seen_urls:
                continue
            seen_urls.add(url)

            # Vérifier que l'URL appartient à un des domaines ciblés
            url_domain = _extract_domain(url)
            if not any(domain in url_domain for domain in clean_domains):
                continue

            filtered_results.append(
                SearchResult(
                    url=url,
                    title=item.get("title", ""),
                    snippet=item.get("body", "") or item.get("snippet", ""),
                    source=url_domain,
                )
            )

            if len(filtered_results) >= max_results:
                break

        logger.info(f"DuckDuckGo: {len(filtered_results)} résultats trouvés")
        return filtered_results

    except Exception as e:
        logger.error(f"Erreur DuckDuckGo: {e}")
        return []


def _do_search(query: str, max_results: int, timeout: float) -> list[dict]:
    """Effectue la recherche synchrone DuckDuckGo"""
    try:
        with DDGS() as ddgs:
            results = list(ddgs.text(
                query,
                region="fr-fr",
                safesearch="off",
                max_results=max_results,
            ))
            return results
    except Exception as e:
        logger.error(f"Erreur lors de la recherche DuckDuckGo: {e}")
        return []


def _extract_domain(url: str) -> str:
    """Extrait le domaine d'une URL"""
    try:
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
    """Vérifie que DuckDuckGo est accessible"""
    try:
        loop = asyncio.get_event_loop()
        results = await loop.run_in_executor(
            None,
            lambda: _do_search("test", 1, 5.0),
        )
        return len(results) > 0
    except Exception as e:
        logger.warning(f"DuckDuckGo health check failed: {e}")
        return False
