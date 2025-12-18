# Task: Fix Screenshot Update Issue

## Context

The user reports that in the "Suivi prix" (Tracking) section, triggering an update ("Mise à jour") does not update the screenshot. This has been identified as a caching issue due to static filenames.

## Current Focus

Implementing logic to generate unique timestamped filenames for screenshots to bypass browser caching and ensure the latest image is displayed.

## Master Plan

- [x] Modify `tracking_scraper_service.py` to use timestamped filenames for tracking screenshots <!-- id: 0 -->
- [x] Verify that `item_service.py` correctly picks up the new files <!-- id: 1 -->
- [x] Create verification script `verify_screenshot_update.py` <!-- id: 2 -->
- [x] Run verification and confirm fix <!-- id: 3 -->
- [x] Modify `ItemService.get_items` to scan filesystem for latest screenshot <!-- id: 4 -->
- [x] Update `ItemService.delete_item` to clean up all related screenshots <!-- id: 6 -->
- [x] Create `verify_fix_item_service.py` to test the new logic <!-- id: 5 -->

## Current Focus

Improving price extraction reliability for B&M Stores and others.

- [x] Analyze `ai_schema.py` to check the extraction prompt <!-- id: 7 -->
- [x] Improve `ScraperService._extract_text` to be more targeted (e.g. main content only) <!-- id: 8 -->
- [x] Update AI prompt to better handle multiple prices (unit vs package) <!-- id: 9 -->
- [x] Verify extraction logic with simulation script <!-- id: 10 -->

## Progress Log

- Identified the issue: `ScraperService` overwrites `item_{id}.png`.
- Created implementation plan.
- User approved plan.
- Implemented filesystem scanning in `ItemService`.
- Verified fix with `verify_fix_item_service.py` successfully.
- Improved AI prompt to ignore unit prices (like "Prix au litre").
- Enhanced text extraction to remove menu/footer noise.
- Verified logic with `verify_extraction_logic.py` (simulated).
