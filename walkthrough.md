# Walkthrough: Price Extraction & Catalog Fixes

## 1. Vision Priority Strategy

**Problem**: The AI was prioritizing text data (often hidden/outdated) over the visual price on the screenshot, extracting incorrect prices (e.g. 0.99€ instead of 1.27€).

**Solution**:

- **Prompt Engineering**: Rewrote the system prompt in `ai_schema.py` to explicitly declare the **IMAGE AS THE SOURCE OF TRUTH**.
- **Logic Fix**: Disabled the `AIPriceExtractor` (Text-only AI) in `scheduler_service.py` which was short-circuiting the logic before the Vision AI could run.

## 2. Catalog Scraper Fix

**Problem**: Catalogs were not updating because the `browserless` service was failing (likely blocked or network issues), preventing the scraper from loading `cataloguemate.fr`.

**Solution**:

- **HTTP Fallback**: Modified `cataloguemate_scraper.py` to use a robust fallback mechanism.
  - First attempts to use the secure Browserless browser.
  - If that fails, it instantly falls back to a standard `httpx` HTTP request, which is often sufficient for static catalog sites.

## 3. Cleanup

- Removed 20+ temporary debug/verification scripts (`debug_*.py`, `verify_*.py`) from the root directory to keep the production environment clean.
