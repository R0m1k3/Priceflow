import os
import glob
import sys
from unittest.mock import MagicMock

# --- MOCKS SETUP ---
# We need to mock these BEFORE importing app.services.item_service
# to avoid ImportErrors due to missing dependencies in the test env.

# 1. Mock External Libs
sys.modules["fastapi"] = MagicMock()
sys.modules["sqlalchemy"] = MagicMock()
sys.modules["sqlalchemy.orm"] = MagicMock()

# 2. Mock Internal App Modules that have heavy dependencies
# Mock app.database
mock_database = MagicMock()
sys.modules["app.database"] = mock_database

# Mock app.models
# We need models.Item and models.PriceHistory to be accessible attributes
mock_models = MagicMock()
sys.modules["app.models"] = mock_models

# Mock app.schemas
sys.modules["app.schemas"] = MagicMock()

# Mock app.services.settings_service
sys.modules["app.services.settings_service"] = MagicMock()

# Mock app.url_validation
sys.modules["app.url_validation"] = MagicMock()

# --- IMPORT TARGET ---
from app.services.item_service import ItemService

def verify_item_service_fix():
    print("Starting verification of ItemService fix...")
    
    # 1. Setup Mock DB and Item
    # We must ensure that when ItemService does `item.id`, it works.
    mock_db = MagicMock()
    
    # Create a simple class to act as the Item model instance
    class MockItem:
        def __init__(self, id, name):
            self.id = id
            self.name = name
            self.url = "http://test.com"
            self.current_price = 10.0
            self.in_stock = True
            self.screenshot_url = None # This will be set by the service
            
            # Attributes accessed by the service
            self.notification_channel = None
            self.target_price = None
            self.current_price_confidence = 1.0
            self.in_stock_confidence = 1.0
            self.is_active = True
            self.last_checked = None
            self.is_refreshing = False
            self.last_error = None
            self.category = None
            self.tags = None
            self.description = None
            
            # __dict__ is used by the service to create the result
            self.dict_storage = {k:v for k,v in self.__dict__.items()}

        @property
        def __dict__(self):
            # Update dict storage with current attributes
            return {
                "id": self.id,
                "name": self.name,
                "url": self.url
            }

    item_888 = MockItem(888, "Test Item")

    # ItemService.get_items calls db.query(models.Item).all()
    # We need to make sure models.Item is used in the query.
    # The service does: items = db.query(models.Item).all()
    
    mock_db.query.return_value.all.return_value = [item_888]
    
    # It also queries PriceHistory
    # db.query(models.PriceHistory).filter(...).first()
    # Let's mock that to return None to force filesytem check (or check logic priority)
    mock_db.query.return_value.filter.return_value.filter.return_value.order_by.return_value.first.return_value = None

    # 2. Create Dummy Screenshot Files
    os.makedirs("screenshots", exist_ok=True)
    
    # Clean up
    for f in glob.glob("screenshots/item_888_*.png"):
        os.remove(f)
    if os.path.exists("screenshots/item_888.png"):
        os.remove("screenshots/item_888.png")

    # Scenario:
    # 1. item_888.png exists (legacy)
    # 2. item_888_1000.png exists (old timestamp)
    # 3. item_888_2000.png exists (new timestamp)
    
    # Expected: get_items should pick item_888_2000.png
    
    file_legacy = "screenshots/item_888.png"
    file_old = "screenshots/item_888_1000.png"
    file_new = "screenshots/item_888_2000.png"
    
    with open(file_legacy, "w") as f: f.write(".")
    with open(file_old, "w") as f: f.write(".")
    with open(file_new, "w") as f: f.write(".")
    
    print(f"Created files: {file_legacy}, {file_old}, {file_new}")

    try:
        # 3. Test get_items
        print("Testing get_items()...")
        items = ItemService.get_items(mock_db)
        
        if not items:
            print("FAILURE: No items returned")
            exit(1)
            
        result = items[0]
        screenshot_url = result.get("screenshot_url")
        print(f"Returned screenshot_url: {screenshot_url}")
        
        expected_url = f"/screenshots/{os.path.basename(file_new)}"
        
        if screenshot_url == expected_url:
            print("SUCCESS: Correctly identified the latest screenshot!")
        else:
            print(f"FAILURE: Expected {expected_url}, got {screenshot_url}")
            # If it failed, maybe it picked legacy?
            if screenshot_url == f"/screenshots/{os.path.basename(file_legacy)}":
                print("Picked legacy file instead of timestamped one.")
            exit(1)

        # 4. Test delete_item
        print("Testing delete_item()...")
        # Ensure the query returns our item
        mock_db.query.return_value.filter.return_value.first.return_value = item_888
        
        ItemService.delete_item(mock_db, 888)
        
        # Check files
        remaining = glob.glob("screenshots/item_888*.png")
        if not remaining:
            print("SUCCESS: All screenshots deleted.")
        else:
            print(f"FAILURE: Files remaining: {remaining}")
            exit(1)

    finally:
        # Cleanup
        for f in [file_legacy, file_old, file_new]:
            if os.path.exists(f):
                os.remove(f)

if __name__ == "__main__":
    verify_item_service_fix()
