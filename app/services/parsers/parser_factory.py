"""
Parser Factory - Selects the appropriate parser for each site
"""

import logging

from .base_parser import BaseParser
from .amazon_parser import AmazonParser
from .cdiscount_parser import CdiscountParser
from .fnac_parser import FnacParser
from .darty_parser import DartyParser
from .boulanger_parser import BoulangerParser
from .generic_parser import GenericParser

logger = logging.getLogger(__name__)


class ParserFactory:
    """
    Factory for creating site-specific parsers

    Automatically selects the specialized parser based on the site key,
    or falls back to the generic parser for sites without specific implementation.
    """

    # Mapping of site keys to their specialized parsers
    _PARSERS = {
        "amazon.fr": AmazonParser,
        "cdiscount.com": CdiscountParser,
        "fnac.com": FnacParser,
        "darty.com": DartyParser,
        "boulanger.com": BoulangerParser,
    }

    # Cache for parser instances (singleton pattern)
    _instances = {}

    @classmethod
    def get_parser(cls, site_key: str) -> BaseParser:
        """
        Get the appropriate parser for a site

        Args:
            site_key: Site identifier (e.g., "amazon.fr", "cdiscount.com")

        Returns:
            Parser instance (specialized or generic)
        """
        # Check cache first
        if site_key in cls._instances:
            return cls._instances[site_key]

        # Check if we have a specialized parser
        parser_class = cls._PARSERS.get(site_key)

        if parser_class:
            logger.info(f"✓ Using specialized parser for {site_key}: {parser_class.__name__}")
            parser = parser_class()
        else:
            logger.info(f"⚠ No specialized parser for {site_key}, using GenericParser")
            parser = GenericParser(site_key)

        # Cache the instance
        cls._instances[site_key] = parser

        return parser

    @classmethod
    def register_parser(cls, site_key: str, parser_class: type[BaseParser]):
        """
        Register a new parser for a site

        Args:
            site_key: Site identifier
            parser_class: Parser class (must inherit from BaseParser)
        """
        if not issubclass(parser_class, BaseParser):
            raise ValueError(f"Parser class must inherit from BaseParser")

        cls._PARSERS[site_key] = parser_class
        # Clear cache for this site
        if site_key in cls._instances:
            del cls._instances[site_key]

        logger.info(f"Registered parser {parser_class.__name__} for {site_key}")

    @classmethod
    def list_specialized_parsers(cls) -> list[str]:
        """Get list of sites with specialized parsers"""
        return list(cls._PARSERS.keys())

    @classmethod
    def clear_cache(cls):
        """Clear parser instance cache"""
        cls._instances.clear()
        logger.info("Parser cache cleared")
