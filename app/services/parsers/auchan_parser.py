from bs4 import BeautifulSoup
from app.services.parsers.base_parser import BaseParser, ProductResult
import logging

logger = logging.getLogger(__name__)

class AuchanParser(BaseParser):
    def __init__(self):
                    in_stock=True,
                    image_url=img_url,
                    snippet=f"Product from Auchan"
                ))
                
            except Exception as e:
                logger.error(f"Error parsing Auchan product: {e}")
                continue
                
        logger.info(f"AuchanParser found {len(results)} results")
        return results
