import logging
import json
import os
from typing import Optional
from app.services.ai_service import AIService
from litellm import acompletion

logger = logging.getLogger(__name__)

class AIPriceExtractor:
    # Primary model requested by user (Gemma 3 Free)
    PRIMARY_MODEL = "openrouter/google/gemma-3-27b-it:free"
    # Fallback model (known to work/be free)
    FALLBACK_MODEL = "openrouter/google/gemma-2-9b-it:free"
    
    @classmethod
    async def extract_price(cls, html_content: str, product_title: str) -> Optional[float]:
        """
        Extract price from HTML using AI (Gemma 3 via OpenRouter with fallback).
        """
        try:
            # Get config to retrieve API key
            config = AIService.get_ai_config()
            api_key = config.get("api_key")
            
            # Fallback to env var if not in DB config
            if not api_key:
                api_key = os.getenv("OPENROUTER_API_KEY")
            
            if not api_key:
                logger.warning("No OpenRouter API key found for AI Price Extraction")
                return None

            # Smart truncation: keep first 3000 chars which usually contain the price
            # and product info. 
            clean_html = html_content[:3000]
            
            prompt = f"""
            You are a price extraction expert.
            Task: Extract the CURRENT SELLING PRICE for the product "{product_title}" from the HTML snippet below.
            
            Rules:
            1. Return ONLY the numeric value (e.g., 24.95).
            2. Ignore crossed-out prices (old prices).
            3. If multiple prices exist, choose the one that seems to be the current effective price (usually the lowest non-crossed-out one).
            4. If no price is found, return "null".
            5. Output format: JSON {{ "price": 24.95 }}
            
            HTML Snippet:
            {clean_html}
            """
            
            try:
                # Try Primary Model (Gemma 3)
                response = await acompletion(
                    model=cls.PRIMARY_MODEL,
                    messages=[{"role": "user", "content": prompt}],
                    api_key=api_key,
                    api_base="https://openrouter.ai/api/v1",
                    temperature=0.1,
                    response_format={"type": "json_object"}
                )
            except Exception as e:
                logger.warning(f"Primary model {cls.PRIMARY_MODEL} failed ({e}), trying fallback {cls.FALLBACK_MODEL}...")
                # Try Fallback Model (Gemma 2)
                response = await acompletion(
                    model=cls.FALLBACK_MODEL,
                    messages=[{"role": "user", "content": prompt}],
                    api_key=api_key,
                    api_base="https://openrouter.ai/api/v1",
                    temperature=0.1,
                    response_format={"type": "json_object"}
                )
            
            content = response.choices[0].message.content
            
            content = response.choices[0].message.content
            if not content:
                return None
                
            data = json.loads(content)
            price = data.get("price")
            
            if price:
                # Handle string price "24,95" or "24.95"
                if isinstance(price, str):
                    price = price.replace(',', '.').replace('€', '').strip()
                return float(price)
                
            return None
                
        except Exception as e:
            logger.error(f"AI Price Extraction failed: {e}")
            return None
