import sys
from app.services.improved_search_service import ImprovedSearchService

print("Attributes of ImprovedSearchService:")
attrs = dir(ImprovedSearchService)
if 'search_site_generator' in attrs:
    print("SUCCESS: search_site_generator found")
else:
    print("FAILURE: search_site_generator NOT found")
    print("Available attributes:", [a for a in attrs if not a.startswith('__')])
