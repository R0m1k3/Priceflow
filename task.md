# Task: Remove Obscuring Windows from Product Screenshots

## Context

The user has reported that screenshots in the "suivi produits" (product tracking) section still contain windows (popups, overlays) that obscure the content. A specific example provided shows a "Stock Inconnu" and "Calendrier de l'Avent" popup on a B&M website.

## Current Focus

Investigating the scraping and screenshot logic to handle these popups.

## Master Plan

- [x] Explore codebase to locate scraping and screenshot logic <!-- id: 0 -->
- [x] Identify specific handling for B&M or generic popup closing <!-- id: 1 -->
- [x] Implement fix to close popups before screenshot <!-- id: 2 -->
- [/] Verify fix (Requires App Rebuild) <!-- id: 3 -->

## Progress Log

- Initialized task.md
- Created implementation plan to expand popup selectors.
- Updated `browserless_service.py` with expanded selectors and retry logic.
- Attempted local verification but failed due to environment restrictions.
