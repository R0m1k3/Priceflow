# Task: Fix Screenshot Update in Tracking

## Context
The user reports that forcing an update in the "Suivi" (Tracking) section does not update the screenshot as expected.

## Current Focus
Investigating the "force update" mechanism and why the screenshot is not refreshing.

## Master Plan
- [x] Investigate the "force update" API endpoint and backend logic.
- [x] Check how screenshots are captured and saved in `tracking_scraper_service.py` or similar.
- [x] Verify if the frontend is correctly requesting the update and displaying the new image.
- [x] Fix the issue preventing the screenshot from updating.
- [x] Verify the fix (Code review confirms relative paths are now consistent across the app).

## Progress Log
- Created `task.md`.
