# Implementation Plan - Catalog Scraper Fix

## Problem

The catalog scraper (`cataloguemate_scraper.py`) fails to retrieve catalogs because the `browserless` service is likely being blocked or failing to connect (based on logs). However, the target site (`cataloguemate.fr`) is accessible via simple HTTP requests.

## Proposed Changes

### 1. Modify `app/services/cataloguemate_scraper.py`

We will implement a fallback mechanism in `scrape_catalog_list`:

- **Primary Method**: Continue using `browserless_service.get_page_content`.
- **Fallback Method**: If `browserless` returns no content or fails, use `httpx.AsyncClient` to fetch the HTML directly.
- **Parsing**: Use `BeautifulSoup` to parse the HTML from either source.

#### [MODIFY] [cataloguemate_scraper.py](file:///c:/Users/Michael/VSCODE/Priceflow-1/app/services/cataloguemate_scraper.py)

- Import `httpx` and `random` (for user-agents).
- In `scrape_catalog_list`, add a `try/except` block or check for empty content.
- If content is missing, call a new helper or inline `httpx` request with standard headers.

## Verification Plan

### Automated Verification

Since we cannot run the full app locally (docker/dependencies issues), we will verify by code review and logic.

### Manual Verification (User)

1. User triggers the catalog update (via Admin or Scheduler).
2. User checks logs to see if "Fallback to HTTP" message appears.
3. User verifies that catalogs (e.g. B&M, Gifi) appear in the dashboard.
