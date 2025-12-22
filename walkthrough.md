# Walkthrough: Price Extraction & Catalog Fixes

## 1. Vision Priority Strategy

**Problem**: The AI was prioritizing text data (often hidden/outdated) over the visual price on the screenshot, extracting incorrect prices (e.g. 0.99€ instead of 1.27€).

**Solution**:

- **Prompt Engineering**: Rewrote the system prompt in `ai_schema.py` to explicitly declare the **IMAGE AS THE SOURCE OF TRUTH**.
- **Logic Fix**: Disabled the `AIPriceExtractor` (Text-only AI) in `scheduler_service.py` which was short-circuiting the logic before the Vision AI could run.

## 2. Catalog Scraper Fix (Connectivity)

**Problem**: Catalogs were not updating because the `browserless` service was failing (likely blocked or network issues).

**Solution**:

- **HTTP Fallback**: Modified `cataloguemate_scraper.py` to use a robust fallback mechanism (Browserless -> Fallback to HTTPX).

## 3. Catalog Images Fix (Lazy Loading)

**Problem**: Catalog pages displayed generic icons or placeholders instead of the actual catalog images.
**Analysis**: The website uses lazy loading. Structure: `<img src="loader.svg" data-src="REAL_IMAGE_URL" ... />`.
**Solution**:

- **Smart Extraction**: Updated `cataloguemate_scraper.py` to checking `data-src` and `data-original` attributes first.
- **Improved Filtering**: Added `loader` to the ignore list and `thumbor` to the whitelist to ensure only high-quality catalog images are selected.

## 4. Cleanup

- Removed temporary debug/verification scripts to keep the production environment clean.
