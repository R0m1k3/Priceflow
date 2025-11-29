"""
Unified JSON schema for AI extraction responses.

This module defines the canonical schema for all AI model responses,
including confidence scores and metadata tracking.
"""

import re
from typing import Literal

from pydantic import BaseModel, Field, field_validator

from app.utils.text import filter_relevant_text

# Schema version for tracking prompt/schema changes
PROMPT_VERSION = "v2.0"

# Default confidence thresholds
DEFAULT_PRICE_CONFIDENCE_THRESHOLD = 0.5
DEFAULT_STOCK_CONFIDENCE_THRESHOLD = 0.5
DEFAULT_MULTI_SAMPLE_THRESHOLD = 0.6

# Text filtering constants
MIN_SNIPPET_LENGTH = 10
SNIPPET_MERGE_DISTANCE = 50
SNIPPET_CONTEXT_WINDOW = 100


class AIExtractionResponse(BaseModel):
    """
    Canonical schema for AI extraction responses.

    All AI models must return data matching this schema.
    """

    price: float | None = Field(
        None,
        description="Extracted price as a number, or null if no price found",
    )
    currency: str = Field(
        "EUR",
        description="Currency code (ISO 4217)",
    )
    in_stock: bool | None = Field(
        None,
        description="Stock status: true if in stock, false if out of stock, null if unclear",
    )
    price_confidence: float = Field(
        0.0,
        ge=0.0,
        le=1.0,
        description="Confidence in price extraction (0.0 to 1.0)",
    )
    in_stock_confidence: float = Field(
        0.0,
        ge=0.0,
        le=1.0,
        description="Confidence in stock status extraction (0.0 to 1.0)",
    )
    source_type: Literal["image", "text", "both"] = Field(
        "image",
        description="Source of extraction: image, text, or both",
    )

    @field_validator("price_confidence", "in_stock_confidence", mode="before")
    @classmethod
    def clamp_confidence(cls, v):
        """Clamp confidence values to [0.0, 1.0] range."""
        if v is None:
            return 0.0
        return max(0.0, min(1.0, float(v)))

    @field_validator("price", mode="before")
    @classmethod
    def normalize_price(cls, v):
        """Normalize price to float or None, handling French format."""
        if v is None or v in ("null", ""):
            return None
        if isinstance(v, str):
            # Handle French format: "1 234,56" -> "1234.56"
            # First, remove spaces (thousand separators)
            cleaned = v.replace(" ", "").replace("\u00a0", "")
            # Replace comma with dot (French decimal separator)
            # But only if there's no dot already (to handle "1.234,56" format)
            if "," in cleaned and "." in cleaned:
                # Format "1.234,56" - remove dots, replace comma with dot
                cleaned = cleaned.replace(".", "").replace(",", ".")
            elif "," in cleaned:
                # Format "12,99" - just replace comma with dot
                cleaned = cleaned.replace(",", ".")
            # Remove currency symbols and other non-numeric chars (except dot)
            cleaned = re.sub(r"[^\d.]", "", cleaned)
            if cleaned:
                try:
                    return float(cleaned)
                except ValueError:
                    return None
            return None
        return float(v)

    @field_validator("in_stock", mode="before")
    @classmethod
    def normalize_stock(cls, v):
        """Normalize stock status to boolean or None."""
        if v is None or v == "null":
            return None
        if isinstance(v, str):
            v_lower = v.lower().strip()
            if v_lower in ("true", "yes", "in stock", "available", "1"):
                return True
            if v_lower in ("false", "no", "out of stock", "unavailable", "0"):
                return False
            return None
        return bool(v)


class AIExtractionMetadata(BaseModel):
    """
    Metadata about an AI extraction operation.

    Tracks which model was used, whether repair was needed, etc.
    """

    model_name: str = Field(..., description="AI model identifier (e.g., 'gpt-4o')")
    provider: str = Field(..., description="AI provider (e.g., 'openai', 'ollama')")
    prompt_version: str = Field(PROMPT_VERSION, description="Version of the extraction prompt used")
    repair_used: bool = Field(False, description="Whether JSON repair fallback was used")
    multi_sample: bool = Field(False, description="Whether multi-sample validation was used")
    sample_count: int = Field(1, description="Number of samples generated (for multi-sample)")


# Prompt template for schema-first extraction
EXTRACTION_PROMPT_TEMPLATE = """Extract product price and stock status from this French e-commerce page.

**PRICE (IMPORTANT - French format):**
- **FIRST**: Look for "PRIX DÉTECTÉ:" at the start of text - this is the extracted price
- French prices use COMMA for decimals: "12,99 €" means 12.99
- Thousands separator is SPACE or DOT: "1 234,56 €" or "1.234,56 €" means 1234.56
- Currency symbol is usually € at the end
- Look for: "PRIX DÉTECTÉ:", price tags, "Prix:", "€", numbers near "Ajouter au panier"
- Extract as DECIMAL NUMBER (convert comma to dot): 12,99 -> 12.99
- Ignore crossed-out/barré prices (old prices)
- If multiple prices, take the current/main price (not the original)

**CRITICAL - Read digits carefully:**
- PAY CLOSE ATTENTION to first digit: "1,99 €" is NOT "9,99 €"
- Double-check: Is it 1, 7, 8, or 9? These look similar
- Small prices (< 5€) are common: 0,99 €, 1,49 €, 1,99 €, 2,99 €, 3,99 €, 4,99 €
- VERIFY the price makes sense for the product type

- Examples of valid prices:
  * "1,99 €" -> 1.99 (NOT 9.99)
  * "0,99 €" -> 0.99 (NOT 9.99)
  * "89,99 €" -> 89.99
  * "1 234,56 €" -> 1234.56
  * "PRIX DÉTECTÉ: 89,99 €" -> 89.99
- If you find ANY price with € symbol, extract it with confidence >= 0.8
- If digits are unclear or blurry, reduce confidence to 0.5-0.7
- If unclear: set null and confidence < 0.5

**STOCK:**
- TRUE if: "Ajouter au panier", "Acheter", "En stock", "Disponible", "Add to Cart"
- FALSE if: "Rupture", "Indisponible", "Épuisé", "Out of Stock", "Notify Me"
- NULL if unclear or not shown

**CONFIDENCE (0.0 to 1.0):**
- 0.9-1.0: Price clearly visible
- 0.5-0.8: Price found but partially obscured or uncertain
- Below 0.5: Cannot find price reliably

Respond ONLY with valid JSON:
{{
  "price": <number or null>,
  "currency": "EUR",
  "in_stock": <true, false, or null>,
  "price_confidence": <0.0 to 1.0>,
  "in_stock_confidence": <0.0 to 1.0>,
  "source_type": "both"
}}

{context_section}"""

# Repair prompt template
REPAIR_PROMPT_TEMPLATE = """Convert the following text into valid JSON matching this schema:

{{
  "price": <number or null>,
  "currency": "<ISO currency code, default USD>",
  "in_stock": <true, false, or null>,
  "price_confidence": <number from 0.0 to 1.0>,
  "in_stock_confidence": <number from 0.0 to 1.0>,
  "source_type": "<image, text, or both>"
}}

Rules:
- Extract numeric price value only (no symbols)
- Boolean values must be true, false, or null (not strings)
- Confidence values must be numbers between 0.0 and 1.0
- Respond with ONLY the JSON object, no other text

Text to convert:
{raw_output}"""


def get_extraction_prompt(page_text: str | None = None) -> str:
    """
    Generate the extraction prompt with optional text context.

    Args:
        page_text: Optional webpage text to include as context

    Returns:
        Formatted prompt string
    """
    if page_text:
        # Apply smart filtering to extract only relevant snippets
        filtered_text = filter_relevant_text(page_text, max_length=1500)
        context_section = f"""**Relevant text from page:**
{filtered_text}"""
    else:
        context_section = ""

    return EXTRACTION_PROMPT_TEMPLATE.format(context_section=context_section)


def get_repair_prompt(raw_output: str) -> str:
    """
    Generate the repair prompt for fixing invalid JSON.

    Args:
        raw_output: Raw AI output that failed parsing

    Returns:
        Formatted repair prompt
    """
    return REPAIR_PROMPT_TEMPLATE.format(raw_output=raw_output[:1000])
