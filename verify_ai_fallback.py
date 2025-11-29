import asyncio
import logging
from unittest.mock import MagicMock, patch
from app.services.ai_service import AIService

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Mock BadRequestError since we might not have litellm installed in the environment running this script
class MockBadRequestError(Exception):
    pass

async def verify_fallback():
    logger.info("Starting AI fallback verification...")
    
    # Mock config
    config = {
        "provider": "openrouter",
        "model": "google/gemini-2.5-flash-image-preview",
        "api_key": "fake-key",
        "api_base": "https://openrouter.ai/api/v1",
        "temperature": 0.1,
        "max_tokens": 100,
        "timeout": 30,
    }
    
    # Mock success response
    mock_response = MagicMock()
    mock_response.choices = [MagicMock(message=MagicMock(content='{"price": 10.0}'))]
    
    # Patch acompletion
    with patch("app.services.ai_service.acompletion") as mock_acompletion:
        # Setup side effect: First call raises BadRequestError, second call succeeds
        mock_acompletion.side_effect = [
            MockBadRequestError("400 Bad Request: The request is not supported by this model."),
            mock_response
        ]
        
        try:
            # We need to patch the exception check in the code if we can't import the real exception
            # But the code uses string check "BadRequestError" in str(type(e).__name__)
            # So MockBadRequestError should work if we name it right or if the code checks "400"
            
            # Actually, let's just run it and see if our logic catches it.
            # The code checks: is_bad_request = "BadRequestError" in str(type(e).__name__) or "400" in str(e)
            # Our MockBadRequestError has "400" in the message, so it should be caught.
            
            logger.info("Calling call_llm...")
            result = await AIService.call_llm("test prompt", "data:image/...", config)
            
            logger.info(f"Result: {result}")
            
            # Verify calls
            assert mock_acompletion.call_count == 2
            logger.info("SUCCESS: acompletion was called twice (retry worked)")
            
            # Verify second call didn't have response_format
            call_args = mock_acompletion.call_args_list[1]
            kwargs = call_args.kwargs
            if "response_format" not in kwargs:
                logger.info("SUCCESS: Second call did not have response_format")
            else:
                logger.error("FAILURE: Second call still had response_format")
                
        except Exception as e:
            logger.error(f"FAILURE: Exception raised: {e}")

if __name__ == "__main__":
    asyncio.run(verify_fallback())
