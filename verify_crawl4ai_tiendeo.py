"""
Script de vérification pour tester Crawl4AI dans le scraper Tiendeo.

Usage:
    python verify_crawl4ai_scraper.py

Ce script teste:
1. Import de Crawl4AI
2. Extraction d'une page catalogue Tiendeo
3. Comptage des pages trouvées
"""

import asyncio
import logging
from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig, CacheMode

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def test_crawl4ai_import():
    """Test 1: Vérifier que Crawl4AI est bien installé"""
    try:
        logger.info("✓ Crawl4AI importé avec succès")
        logger.info(f"  Version: {AsyncWebCrawler.__module__}")
        return True
    except Exception as e:
        logger.error(f"✗ Erreur import Crawl4AI: {e}")
        return False


async def test_catalog_page_extraction():
    """Test 2: Extraire les pages d'un catalogue Tiendeo"""
    # URL de test - catalogue Gifi Nancy (à adapter si nécessaire)
    test_url = "https://www.tiendeo.fr/Catalogues/nancy/gifi"
    
    logger.info(f"\nTest extraction depuis: {test_url}")
    
    try:
        browser_config = BrowserConfig(
            headless=True,
            verbose=False,
            extra_args=["--disable-gpu", "--no-sandbox", "--disable-dev-shm-usage"],
        )
        
        config = CrawlerRunConfig(
            cache_mode=CacheMode.BYPASS,
            wait_for_images=True,
            process_iframes=True,
            remove_overlay_elements=True,
            wait_until="networkidle",
            delay_before_return_html=3.0,
        )
        
        async with AsyncWebCrawler(config=browser_config) as crawler:
            result = await crawler.arun(url=test_url, config=config)
            
            if not result.success:
                logger.error(f"✗ Échec du crawling: {result.error_message}")
                return False
            
            logger.info(f"✓ Page chargée avec succès")
            logger.info(f"  HTML length: {len(result.html)} chars")
            
            # Tester l'extraction JavaScript
            pages_data = await crawler.crawler_strategy.execute_js(
                """
                () => {
                    const results = [];
                    const seenUrls = new Set();
                    
                    const allImages = document.querySelectorAll('img');
                    
                    allImages.forEach((img) => {
                        let src = img.src || img.getAttribute('data-src');
                        
                        if (!src && img.srcset) {
                            const srcsetParts = img.srcset.split(',')[0].trim().split(' ');
                            src = srcsetParts[0];
                        }
                        
                        if (!src || seenUrls.has(src)) return;
                        
                        if (src.includes('logo') || src.includes('icon') || src.includes('avatar')) {
                            return;
                        }
                        
                        const width = img.naturalWidth || img.width;
                        const height = img.naturalHeight || img.height;
                        
                        if (width < 400 || height < 400) return;
                        
                        const aspectRatio = width / height;
                        
                        if (aspectRatio > 0.5 && aspectRatio < 0.9) {
                            seenUrls.add(src);
                            results.push({
                                image_url: src,
                                width: width,
                                height: height,
                            });
                        }
                    });
                    
                    results.sort((a, b) => (b.width * b.height) - (a.width * a.height));
                    
                    return results.map((item, index) => ({
                        ...item,
                        numero_page: index + 1,
                    }));
                }
                """
            )
            
            logger.info(f"✓ Extraction JavaScript réussie")
            logger.info(f"  Pages trouvées: {len(pages_data)}")
            
            if len(pages_data) > 0:
    test2 = await test_catalog_page_extraction()
    
    # Résumé
    logger.info("\n" + "=" * 70)
    logger.info("RÉSUMÉ")
    logger.info("=" * 70)
    logger.info(f"Import Crawl4AI: {'✓ OK' if test1 else '✗ ÉCHEC'}")
    logger.info(f"Extraction pages: {'✓ OK' if test2 else '✗ ÉCHEC'}")
    
    if test1 and test2:
        logger.info("\n✓ TOUS LES TESTS SONT PASSÉS!")
        logger.info("Le scraper Crawl4AI est prêt à être utilisé.")
    else:
        logger.info("\n✗ CERTAINS TESTS ONT ÉCHOUÉ")
        logger.info("Vérifiez les erreurs ci-dessus.")


if __name__ == "__main__":
    asyncio.run(main())
