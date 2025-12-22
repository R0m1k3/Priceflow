import sys
import unittest

# Mock modules to avoid ImportError for app dependencies we don't need for this specific test
from unittest.mock import MagicMock
sys.modules["sqlalchemy"] = MagicMock()
sys.modules["sqlalchemy.orm"] = MagicMock()
sys.modules["app.database"] = MagicMock()
sys.modules["app.utils.image"] = MagicMock()
sys.modules["app.utils.text"] = MagicMock()
sys.modules["app.utils.text"].filter_relevant_text = lambda text, max_length: text

# Mock pydantic
mock_pydantic = MagicMock()
class MockBaseModel:
    pass
mock_pydantic.BaseModel = MockBaseModel
mock_pydantic.Field = MagicMock(return_value=None)
mock_pydantic.field_validator = MagicMock(return_value=lambda x: x)
sys.modules["pydantic"] = mock_pydantic

# Import the schema module
from app.ai_schema import get_extraction_prompt

class TestVisionPriorityPrompt(unittest.TestCase):
    def test_vision_first_directives(self):
        """Verify that the prompt contains the Vision-First directives."""
        
        # Scenario: Some random text context
        page_text = "Some random text content from the page."
        prompt = get_extraction_prompt(page_text)
        
        print("\nGenerated Prompt Snippet:\n", prompt[:500], "...\n")

        # Check for Critical Directives
        self.assertIn("Vision-First Price Extraction Agent", prompt)
        self.assertIn("**SOURCE OF TRUTH = IMAGE**", prompt)
        self.assertIn("IF IMAGE AND TEXT CONFLICT, TRUST THE IMAGE", prompt)
        
        # Check for stock rules
        self.assertIn("STOCK STATUS RULES", prompt)
        
    def test_prompt_without_text(self):
        """Verify prompt structure when no text is provided."""
        prompt = get_extraction_prompt(None)
        self.assertIn("**SOURCE OF TRUTH = IMAGE**", prompt)
        self.assertNotIn("**Relevant text from page:**", prompt)

if __name__ == "__main__":
    unittest.main()
