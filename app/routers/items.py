from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app import database, models, schemas
from app.limiter import limiter
from app.services.item_service import ItemService
from app.services.scheduler_service import process_item_check

router = APIRouter(prefix="/items", tags=["items"])


@router.get("", response_model=list[schemas.ItemResponse])
def get_items(category: str | None = None, db: Session = Depends(database.get_db)):
    """Get all items, optionally filtered by category"""
    items = ItemService.get_items(db)
    if category:
        items = [item for item in items if item.category == category]
    return items


@router.post("", response_model=schemas.ItemResponse)
def create_item(item: schemas.ItemCreate, db: Session = Depends(database.get_db)):
    return ItemService.create_item(db, item)


@router.put("/{item_id}", response_model=schemas.ItemResponse)
def update_item(item_id: int, item_update: schemas.ItemCreate, db: Session = Depends(database.get_db)):
    return ItemService.update_item(db, item_id, item_update)


@router.delete("/{item_id}")
def delete_item(item_id: int, db: Session = Depends(database.get_db)):
    return ItemService.delete_item(db, item_id)


@router.patch("/{item_id}/category")
def update_item_category(item_id: int, category: str | None = None, db: Session = Depends(database.get_db)):
    """Update the category of an item"""
    item = db.query(models.Item).filter(models.Item.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")

    # Treat empty string as None
    item.category = category if category and category.strip() else None
    db.commit()
    db.refresh(item)
    return {"message": "Category updated", "category": item.category}


@router.get("/categories/list")
def get_categories(db: Session = Depends(database.get_db)):
    """Get list of distinct categories used in items"""
    categories = db.query(models.Item.category).distinct().filter(models.Item.category.isnot(None)).all()
    return [cat[0] for cat in categories if cat[0]]


@router.post("/{item_id}/check")
@limiter.limit("10/minute")
def check_item(
    request: Request, item_id: int, background_tasks: BackgroundTasks, db: Session = Depends(database.get_db)
):
    item = ItemService.get_item(db, item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")

    item.is_refreshing = True
    item.last_error = None
    db.commit()

    background_tasks.add_task(process_item_check, item_id)
    return {"message": "Check triggered"}


@router.get("/{item_id}/price-history", response_model=list[schemas.PriceHistoryResponse])
def get_price_history(item_id: int, db: Session = Depends(database.get_db)):
    """Get price history for a specific item"""
    item = db.query(models.Item).filter(models.Item.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")

    # Get price history sorted by timestamp descending (most recent first)
    price_history = (
        db.query(models.PriceHistory)
        .filter(models.PriceHistory.item_id == item_id)
        .order_by(models.PriceHistory.timestamp.desc())
        .all()
    )

    return price_history


@router.patch("/{item_id}/availability")
def update_item_availability(item_id: int, available: bool = True, db: Session = Depends(database.get_db)):
    """Mark an item as available or unavailable manually"""
    item = db.query(models.Item).filter(models.Item.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")

    item.is_available = available
    # Also clear the error if marking as available
    if available and item.last_error and "indisponible" in item.last_error.lower():
        item.last_error = None
    db.commit()
    db.refresh(item)
    return {
        "message": f"Item marked as {'available' if available else 'unavailable'}",
        "is_available": item.is_available,
    }
