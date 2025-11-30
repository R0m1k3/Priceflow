from bs4 import BeautifulSoup
from app.services.parsers.base_parser import BaseParser, ProductResult
import logging

logger = logging.getLogger(__name__)

class LaFoirFouilleParser(BaseParser):
    def __init__(self):
        super().__init__("lafoirfouille.fr", "https://www.lafoirfouille.fr")
                    in_stock=True,
                    image_url=img_url,
                    snippet=f"Product from La Foir'Fouille"
                ))
                
            except Exception as e:
                logger.error(f"Error parsing La Foir'Fouille product: {e}")
                continue
                
        logger.info(f"LaFoirFouilleParser found {len(results)} results")
        return results
