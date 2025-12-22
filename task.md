# Task Board: Vision-Based Price Extraction

## 🚀 Current Focus

- [ ] Debug Catalog Scraper

## 📋 Master Plan

- [x] Analyze `verify_extraction_logic.py`, `ai_service.py`, `ai_schema.py`, `tracking_scraper_service.py`.
- [x] Proposal Phase: Vision Priority accepted.
- [ ] Implementation Phase:
  - [x] Update `ai_schema.py`.
  - [x] Fix `scheduler_service.py` (Disable conflicting Text AI).
- [x] Verification Phase: Verified with `verify_vision_priority.py`.
- [ ] **Catalog Issue**:
  - [x] Reproduce failure (Confirmed Browserless issue via analysis).
  - [x] Fix `cataloguemate_scraper.py` with HTTP fallback.

- [x] **Cleanup**:
  - [x] Deleted `debug_*.py` and `verify_*.py` files.

## 📝 Progress Log

- **2025-12-22**: Vision Priority implemented and verified.
- **2025-12-22**: User reported Catalog issue. Logic identified as `cataloguemate.fr`.
- **2025-12-22**: Initial debug script failed (missing dependencies). Creating v2 using internal services.
