"""
Site-Specific Parsers for Robust Product Search
Each parser implements specialized logic for extracting search results and product details
"""

from .base_parser import BaseParser, ProductResult
from .parser_factory import ParserFactory
from .amazon_parser import AmazonParser
from .cdiscount_parser import CdiscountParser
from .fnac_parser import FnacParser
from .darty_parser import DartyParser
from .boulanger_parser import BoulangerParser
from .generic_parser import GenericParser

__all__ = [
    "BaseParser",
    "ProductResult",
    "ParserFactory",
    "AmazonParser",
    "CdiscountParser",
    "FnacParser",
    "DartyParser",
    "BoulangerParser",
    "GenericParser",
]
