import logging
import os
from datetime import UTC, datetime

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app import models, schemas
from app.services.settings_service import SettingsService
from app.url_validation import URLValidationError, validate_url

logger = logging.getLogger(__name__)


class ItemService:
    @staticmethod
    def get_items(db: Session):
        import glob
        items = db.query(models.Item).all()
        result = []
        for item in items:
            # Strategy: Look for the latest screenshot file on disk
            # Format: item_{id}_{timestamp}.png
            screenshot_url = None
            
            try:
                # Find all timestamped screenshots for this item
                files = glob.glob(f"screenshots/item_{item.id}_*.png")
                
                if files:
                    # Sort by timestamp valid in filename
                    # We expect format item_ID_TIMESTAMP.png
                    def get_timestamp(f):
                        try:
                            # Extract timestamp part: remove extension, split by _, take last part
                            ts_str = os.path.splitext(f)[0].split('_')[-1]
                            return float(ts_str)
                        except (ValueError, IndexError):
                            return 0.0

                    latest_file = max(files, key=get_timestamp)
                    screenshot_url = f"/screenshots/{os.path.basename(latest_file)}"
                
                # Primary fallback: Legacy static file
                elif os.path.exists(f"screenshots/item_{item.id}.png"):
                    screenshot_url = f"/screenshots/item_{item.id}.png"
                
                # Secondary fallback: use DB history if for some reason file scan missed but DB has record
                # (This is less likely to be useful if we assume files exist, but good for safety)
                if not screenshot_url:
                    latest_history = (
                        db.query(models.PriceHistory)
                        .filter(models.PriceHistory.item_id == item.id)
                        .filter(models.PriceHistory.screenshot_path.isnot(None))
                        .order_by(models.PriceHistory.timestamp.desc())
                        .first()
                    )
                    if latest_history and latest_history.screenshot_path:
                         filename = os.path.basename(latest_history.screenshot_path)
                         # Verify it exists
                         if os.path.exists(f"screenshots/{filename}"):
                             screenshot_url = f"/screenshots/{filename}"

            except Exception as e:
                logger.error(f"Error determining screenshot for item {item.id}: {e}")
                # Ultimate fallback
                if os.path.exists(f"screenshots/item_{item.id}.png"):
                     screenshot_url = f"/screenshots/item_{item.id}.png"

            result.append({**item.__dict__, "screenshot_url": screenshot_url})
        return result

    @staticmethod
    def create_item(db: Session, item: schemas.ItemCreate):
        logger.info(f"Creating item: {item.name} - {item.url}")
        try:
            validate_url(item.url)
        except URLValidationError as e:
            raise HTTPException(status_code=400, detail=f"Invalid URL: {e}") from e

        db_item = models.Item(**item.model_dump())
        db.add(db_item)
        db.commit()
        db.refresh(db_item)
        return db_item

    @staticmethod
    def update_item(db: Session, item_id: int, item_update: schemas.ItemCreate):
        db_item = db.query(models.Item).filter(models.Item.id == item_id).first()
        if not db_item:
            raise HTTPException(status_code=404, detail="Item not found")

        for key, value in item_update.model_dump().items():
            setattr(db_item, key, value)

        db.commit()
        db.refresh(db_item)
        return db_item

    @staticmethod
    def delete_item(db: Session, item_id: int):
        import glob
        item = db.query(models.Item).filter(models.Item.id == item_id).first()
        if not item:
            raise HTTPException(status_code=404, detail="Item not found")

        # Delete all associated screenshots (legacy and timestamped)
        for file_path in glob.glob(f"screenshots/item_{item_id}*.png"):
            try:
                os.remove(file_path)
                logger.info(f"Deleted screenshot: {file_path}")
            except OSError as e:
                logger.warning(f"Failed to delete {file_path}: {e}")

        db.delete(item)
        db.commit()
        return {"ok": True}

    @staticmethod
    def get_item(db: Session, item_id: int):
        return db.query(models.Item).filter(models.Item.id == item_id).first()

    @staticmethod
    def get_item_data_for_checking(db: Session, item_id: int):
        item = db.query(models.Item).filter(models.Item.id == item_id).first()
        if not item:
            return None, None

        settings = {s.key: s.value for s in db.query(models.Settings).all()}
        channel = item.notification_channel

        item_data = {
            "id": item.id,
            "url": item.url,
            "selector": item.selector,
            "name": item.name,
            "current_price": item.current_price,
            "in_stock": item.in_stock,
            "target_price": item.target_price,
            "notification_channel": channel,
        }

        config = {
            "smart_scroll": settings.get("smart_scroll_enabled", "false").lower() == "true",
            "smart_scroll_pixels": int(settings.get("smart_scroll_pixels", "350")),
            "text_context_enabled": settings.get("text_context_enabled", "false").lower() == "true",
            "text_length": int(settings.get("text_context_length", "5000"))
            if settings.get("text_context_enabled", "false").lower() == "true"
            else 0,
            "scraper_timeout": int(settings.get("scraper_timeout", "90000")),
        }
        return item_data, config

    @staticmethod
    def get_due_items(db: Session):
        items = db.query(models.Item).filter(models.Item.is_active).all()
        global_interval = int(SettingsService.get_setting_value(db, "refresh_interval_minutes", "60"))
        due_items = []
        now = datetime.now(UTC)

        for item in items:
            if item.is_refreshing:
                continue

            interval = item.check_interval_minutes if item.check_interval_minutes else global_interval

            if not item.last_checked:
                due_items.append((item.id, interval, -1))
                continue

            last_checked = (
                item.last_checked.replace(tzinfo=UTC) if item.last_checked.tzinfo is None else item.last_checked
            )
            time_since = (now - last_checked).total_seconds() / 60
            if time_since >= interval:
                due_items.append((item.id, interval, int(time_since)))

        return due_items
