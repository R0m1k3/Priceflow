# Task Board: Vision-Based Price Extraction

## 🚀 Current Focus

- [ ] Fix Catalog Images (Generic/Missing icons)

## 📋 Master Plan

- [x] Analyze `verify_extraction_logic.py`, `ai_service.py`, `ai_schema.py`, `tracking_scraper_service.py`.
- [x] Proposal Phase: Vision Priority accepted.
- [x] Implementation Phase:
  - [x] Update `ai_schema.py`.
  - [x] Fix `scheduler_service.py` (Disable conflicting Text AI).
- [x] Verification Phase: Verified with `verify_vision_priority.py`.
- [x] **Catalog Retrieval Fix**:
  - [x] Reproduce failure (Confirmed Browserless issue).
  - [x] Fix `cataloguemate_scraper.py` with HTTP fallback.
  - [x] Cleanup debug files.
- [ ] **Catalog Image Fix**:
  - [x] Analyze page HTML for correct image selectors (Found `data-src`).
  - [x] Refine `cataloguemate_scraper.py` image extraction logic.

## 📝 Progress Log

- **2025-12-22**: Vision Priority implemented and verified.
- **2025-12-22**: Fixed Catalog Retrieval using HTTP fallback.
- **2025-12-22**: User reports images are generic icons. Investigating image selectors.
