# Task Board: Catalog Image Fix

## 🚀 Current Focus

- [x] Fix Catalog Images (Generic/Missing icons)
- [x] Address "PDF vs Image" question
- [x] Implement "Delete Images" (Cleanup bad data)

## 📋 Master Plan

- [x] Analyze `verify_extraction_logic.py`, `ai_service.py`, `ai_schema.py`, `tracking_scraper_service.py`.
- [x] Proposal Phase: Vision Priority accepted.
- [x] Implementation Phase:
  - [x] Update `ai_schema.py`.
  - [x] Fix `scheduler_service.py`.
- [x] Verification Phase: Verified with `verify_vision_priority.py`.
- [x] **Catalog Retrieval Fix**:
  - [x] Reproduce failure (Confirmed Browserless issue).
  - [x] Fix `cataloguemate_scraper.py` with HTTP fallback.
  - [x] Cleanup debug files.
- [x] **Catalog Image Fix**:
  - [x] Analyze page HTML for correct image selectors (Found Thumbor URL).
  - [x] **Check PDF availability** (Browser Task).
  - [x] **Refine Scraper Logic**:
    - [x] Update `cataloguemate_scraper.py` to grab `src` and prioritize Thumbor.
    - [x] Update `routers/catalogues.py` to clean up bad images.
  - [x] **Cleanup Bad Data**:
    - [x] Run cleanup endpoint.
  - [x] Verify fix with new scrape.

## 📝 Progress Log

- **2025-12-22**: Vision Priority implemented and verified.
- **2025-12-22**: Fixed Catalog Retrieval using HTTP fallback.
- **2025-12-22**: Investigating generic icon issue. Found images are served via Thumbor.
- **2025-12-22**: **FIXED**: Scraper now targets Thumbor images. Wiped bad catalogs.
