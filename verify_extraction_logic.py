import asyncio
import logging
import sys
from unittest.mock import MagicMock, AsyncMock

# Mock sqlalchemy
sys.modules["sqlalchemy"] = MagicMock()
sys.modules["sqlalchemy.orm"] = MagicMock()

# Mock pydantic
mock_pydantic = MagicMock()
# Mock BaseModel
class MockBaseModel:
    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)
mock_pydantic.BaseModel = MockBaseModel
mock_pydantic.Field = MagicMock(return_value=None)
mock_pydantic.field_validator = MagicMock(return_value=lambda x: x)

sys.modules["pydantic"] = mock_pydantic

# Mock app.utils.text which is imported by ai_schema
mock_utils_text = MagicMock()
sys.modules["app.utils.text"] = mock_utils_text
mock_utils_text.filter_relevant_text = lambda text, max_length: text[:max_length]
mock_utils_text.clean_text = lambda text: text.strip()

# Mock app.strings (if used) or other utils
sys.modules["app.utils"] = MagicMock()

# Mock app.utils.image
sys.modules["app.utils.image"] = MagicMock()

# Mock app.database
sys.modules["app.database"] = MagicMock()

# Mock playwright
mock_playwright = MagicMock()
sys.modules["playwright"] = mock_playwright
sys.modules["playwright.async_api"] = mock_playwright

# Mock generic types for type hints if needed
mock_playwright.Browser = MagicMock
mock_playwright.BrowserContext = MagicMock
mock_playwright.Page = MagicMock
mock_playwright.TimeoutError = Exception

# Now import the schema
from app.ai_schema import get_extraction_prompt, get_repair_prompt

# We can't import ScraperService easily if it inherits from things or uses decorators
# But for this test we only need get_extraction_prompt which is in ai_schema
# So we can skip importing ScraperService if it causes issues, 
# BUT we wanted to verify ScraperService text cleaning logic... 
# Let's mock ScraperService dependencies completely.

try:
    from app.services.tracking_scraper_service import ScraperService
except ImportError:
    print("Warning: Could not import ScraperService due to dependencies. Skipping Service tests.")
    ScraperService = None

# Mock litellm and tenacity
sys.modules["litellm"] = MagicMock()
sys.modules["tenacity"] = MagicMock()
mock_retry = MagicMock()
sys.modules["tenacity.retry"] = mock_retry

# Make sure imports inside ai_service don't fail
# It imports: retry, retry_if_exception_type, stop_after_attempt, wait_exponential from tenacity
# We need to mock these specifically if the module imports them directly
mock_tenacity = MagicMock()
mock_tenacity.retry = lambda *args, **kwargs: lambda f: f
mock_tenacity.retry_if_exception_type = MagicMock()
mock_tenacity.stop_after_attempt = MagicMock()
mock_tenacity.wait_exponential = MagicMock()
sys.modules["tenacity"] = mock_tenacity

# Now import AIService
# We will mock the AI response to verify the parsing logic
from app.services.ai_service import AIService

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def verify_extraction_logic():
    print("Verifying Extraction Logic...")

    # 1. Test Text Cleaning in ScraperService
    # We can't mock Playwright page easily in a simple script without launching a browser.
    # But we can test the AI prompt generation which is critical.
    
    # Simulate B&M text
    dirty_text = """
    Menu
    Accueil
    Panier
    
    Boisson energisante ice 25cl
    Red Bull
    
    1.15 €
    Prix au litre : 4,60 € / L
    
    En stock
    Ajouter au panier
    
    Footer
    Mentions légales
    """
    
    print("\n--- Testing Prompt Generation ---")
    prompt = get_extraction_prompt(dirty_text)
    
    # Verify strict instructions are present
    checks = [
        "CRITICAL",
        "Ignore \"Prix au litre\"",
        "B&M STORES Specific",
        "Extract as DECIMAL NUMBER"
    ]
    
    all_passed = True
    for check in checks:
        if check in prompt:
            print(f"[OK] Prompt contains: {check}")
        else:
            print(f"[FAIL] Prompt missing: {check}")
            all_passed = False
            
    if not all_passed:
        print("Prompt verification failed!")
        exit(1)

    print("\n--- Testing Response Parsing (Mock AI) ---")
    
    # Case 1: AI returns Main Price correctly
    mock_response_1 = """
    ```json
    {
        "price": 1.15,
        "currency": "EUR",
        "in_stock": true,
        "price_confidence": 0.95,
        "in_stock_confidence": 1.0,
        "source_type": "text"
    }
    ```
    """
    result = AIService.parse_and_validate_response(mock_response_1)
    if result.price == 1.15 and result.in_stock is True:
        print("[OK] Parsed correct mocked response.")
    else:
        print(f"[FAIL] Failed to parse correct response: {result}")
        exit(1)

    # Case 2: AI returns confusion (simulating what we want to avoid, but checking schema resilience)
    # If AI returns explicit null because it's confused
    mock_response_2 = """
    {
        "price": null,
        "currency": "EUR",
        "in_stock": null,
        "price_confidence": 0.0,
        "in_stock_confidence": 0.0,
        "source_type": "image"
    }
    """
    result = AIService.parse_and_validate_response(mock_response_2)
    if result.price is None:
        print("[OK] Parsed null response correctly.")
    else:
        print(f"[FAIL] Failed to parse null response.")

    print("\nVerification of Logic Flow Complete (Simulated).")
    print("Real-world verification requires running the full scraper.")

if __name__ == "__main__":
    asyncio.run(verify_extraction_logic())
