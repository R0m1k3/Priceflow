import sys
try:
    from app.services import improved_search_service
    print("Import successful")
except Exception as e:
    print(f"Import failed: {e}")
    sys.exit(1)
