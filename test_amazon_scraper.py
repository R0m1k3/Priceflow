#!/usr/bin/env python3
"""
Script de test pour le scraper Amazon France
Teste le système anti-détection et l'extraction des produits
"""

import asyncio
import logging
import sys
from pathlib import Path

# Ajouter le répertoire app au path
sys.path.insert(0, str(Path(__file__).parent))

from app.services.amazon_scraper import (
    scrape_amazon_search,
    test_amazon_scraper,
)

# Configuration du logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)


async def test_basic_search():
    """Test basique de recherche"""
    logger.info("=" * 80)
    logger.info("TEST 1: Recherche basique - 'aspirateur'")
    logger.info("=" * 80)

    products = await scrape_amazon_search("aspirateur", max_results=5)

    if not products:
        logger.error("❌ Aucun produit trouvé - possibilité de détection ou problème réseau")
        return False

    logger.info(f"✅ {len(products)} produits trouvés")

    for idx, product in enumerate(products, 1):
        logger.info(f"\n{idx}. {product.title[:60]}...")
        logger.info(f"   💰 Prix: {product.price}€" + (f" (était {product.original_price}€)" if product.original_price else ""))
        logger.info(f"   ⭐ Note: {product.rating}/5" if product.rating else "   ⭐ Pas de note")
        logger.info(f"   📦 {'En stock' if product.in_stock else 'Indisponible'}")
        logger.info(f"   {'🚚 Prime' if product.prime else '📮 Standard'}")
        logger.info(f"   {'📢 Sponsorisé' if product.sponsored else '🔍 Organique'}")

    return True


async def test_multiple_queries():
    """Test avec plusieurs requêtes différentes"""
    logger.info("\n" + "=" * 80)
    logger.info("TEST 2: Requêtes multiples")
    logger.info("=" * 80)

    queries = ["clavier", "souris", "casque"]
    results = {}

    for query in queries:
        logger.info(f"\n🔍 Recherche: '{query}'")
        products = await scrape_amazon_search(query, max_results=3)
        results[query] = len(products)
        logger.info(f"   ✅ {len(products)} produits trouvés")

        # Délai entre requêtes pour respecter les bonnes pratiques
        await asyncio.sleep(3)

    logger.info("\n📊 Résumé:")
    for query, count in results.items():
        logger.info(f"   • {query}: {count} produits")

    total = sum(results.values())
    if total > 0:
        logger.info(f"\n✅ Total: {total} produits extraits")
        return True
    else:
        logger.error("\n❌ Aucun produit extrait - problème possible")
        return False


async def test_anti_detection():
    """Test du système anti-détection"""
    logger.info("\n" + "=" * 80)
    logger.info("TEST 3: Vérification anti-détection")
    logger.info("=" * 80)

    from app.core.search_config import AMAZON_PROXY_LIST_RAW, USER_AGENT_POOL
    from app.services.amazon_scraper import get_random_proxy, AMAZON_USER_AGENTS

    logger.info(f"✓ {len(AMAZON_PROXY_LIST_RAW)} proxies disponibles")
    logger.info(f"✓ {len(USER_AGENT_POOL)} User-Agents standards")
    logger.info(f"✓ {len(AMAZON_USER_AGENTS)} User-Agents Amazon spécifiques")

    # Test proxy
    proxy = get_random_proxy()
    if proxy:
        logger.info(f"✓ Proxy test: {proxy['server']}")
    else:
        logger.warning("⚠️ Pas de proxy configuré")

    # Test d'une recherche simple
    logger.info("\n🧪 Test de recherche avec anti-détection...")
    products = await scrape_amazon_search("livre", max_results=3)

    if products:
        logger.info(f"✅ Anti-détection fonctionnel - {len(products)} produits extraits")
        return True
    else:
        logger.error("❌ Échec - possibilité de blocage")
        return False


async def run_all_tests():
    """Lance tous les tests"""
    logger.info("\n" + "=" * 80)
    logger.info("🚀 DÉMARRAGE DES TESTS DU SCRAPER AMAZON FRANCE")
    logger.info("=" * 80)

    tests = [
        ("Recherche basique", test_basic_search),
        ("Requêtes multiples", test_multiple_queries),
        ("Anti-détection", test_anti_detection),
    ]

    results = {}

    for test_name, test_func in tests:
        try:
            logger.info(f"\n▶️ Exécution: {test_name}")
            success = await test_func()
            results[test_name] = "✅ PASS" if success else "❌ FAIL"
        except Exception as e:
            logger.error(f"❌ Erreur dans {test_name}: {e}", exc_info=True)
            results[test_name] = "❌ ERROR"

    # Résumé final
    logger.info("\n" + "=" * 80)
    logger.info("📊 RÉSUMÉ DES TESTS")
    logger.info("=" * 80)

    for test_name, result in results.items():
        logger.info(f"{result} - {test_name}")

    passed = sum(1 for r in results.values() if "PASS" in r)
    total = len(results)

    logger.info(f"\n🎯 Score: {passed}/{total} tests réussis")

    if passed == total:
        logger.info("✅ TOUS LES TESTS ONT RÉUSSI!")
        return True
    else:
        logger.warning("⚠️ Certains tests ont échoué")
        return False


if __name__ == "__main__":
    try:
        success = asyncio.run(run_all_tests())
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        logger.info("\n⏸️ Tests interrompus par l'utilisateur")
        sys.exit(130)
    except Exception as e:
        logger.error(f"❌ Erreur fatale: {e}", exc_info=True)
        sys.exit(1)
