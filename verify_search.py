import asyncio
import logging
import sys
from unittest.mock import MagicMock, AsyncMock

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Mock dependencies
sys.modules["sqlalchemy"] = MagicMock()
sys.modules["sqlalchemy.orm"] = MagicMock()
sys.modules["app.database"] = MagicMock()
sys.modules["app.models"] = MagicMock()
sys.modules["app.services.ai_service"] = MagicMock()
sys.modules["app.services.scraper_service"] = MagicMock()
sys.modules["app.services.light_scraper_service"] = MagicMock()
sys.modules["app.services.settings_service"] = MagicMock()

# Define dummy classes for schemas
class MockSearchProgress:
    def __init__(self, status, total, completed, message, results, current_site=None):
        self.status = status
        self.total = total
        self.completed = completed
        self.message = message
        self.results = results
        self.current_site = current_site
        
    def model_dump_json(self):
        return "json"

class MockSearchResultItem:
    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)

# Setup schema mocks
schemas_mock = MagicMock()
schemas_mock.SearchProgress = MockSearchProgress
schemas_mock.SearchResultItem = MockSearchResultItem
sys.modules["app.schemas"] = schemas_mock

# Import services after mocking
# We need to mock direct_search_service before importing search_service
# because search_service imports it.
direct_search_mock = MagicMock()
sys.modules["app.services.direct_search_service"] = direct_search_mock

# Now we can import search_service
# We might need to mock other things that search_service imports
from app.services import search_service

# Define a mock SearchResult class matching the one in direct_search_service
class MockSearchResult:
    def __init__(self, url, title, source, price=None, currency="EUR", in_stock=None):
        self.url = url
        self.title = title
        self.source = source
        self.snippet = "snippet"
        self.price = price
        self.currency = currency
        self.in_stock = in_stock

async def test_search_flow():
    print("--- Starting Search Flow Verification ---")
    
    # Setup mocks
    db = MagicMock()
    
    # Mock SettingsService
    search_service.SettingsService.get_setting_value.side_effect = lambda db, key, default: default
    
    # Mock direct_search_service.search
    mock_results = [
        MockSearchResult("http://site1.com/p1", "Product 1", "site1.com"),
        MockSearchResult("http://site2.com/p2", "Product 2", "site2.com"),
    ]
    direct_search_mock.search = AsyncMock(return_value=mock_results)
    direct_search_mock.SearchResult = MockSearchResult
    
    # Mock light_scraper_service
    search_service.light_scraper_service.scrape_url = AsyncMock(return_value=MagicMock(success=False))
    
    # Mock _scrape_with_browserless (to avoid actual scraping)
    # We need to patch it in the module
    original_scrape = search_service._scrape_with_browserless
    search_service._scrape_with_browserless = AsyncMock(return_value=MagicMock(
        url="http://site1.com/p1",
        title="Product 1",
        price=10.0,
        site_name="Site 1",
        site_domain="site1.com"
    ))
    
    # Mock _get_sites to return some dummy sites
    mock_site1 = MagicMock(domain="site1.com", name="Site 1", requires_js=True)
    mock_site2 = MagicMock(domain="site2.com", name="Site 2", requires_js=True)
    search_service._get_sites = MagicMock(return_value=[mock_site1, mock_site2])
    
    # Run the search
    print("Running search_products...")
    async for progress in search_service.search_products("test query", db):
        print(f"Event: {progress.status} - {progress.message}")
        if progress.results:
            print(f"  Results: {len(progress.results)}")
            
    print("--- Verification Complete ---")

if __name__ == "__main__":
    asyncio.run(test_search_flow())
