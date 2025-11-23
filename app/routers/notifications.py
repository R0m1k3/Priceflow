from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from app import database, models, schemas
from app.services.notification_service import NotificationService

router = APIRouter(
    prefix="/notifications",
    tags=["notifications"],
)

@router.get("/channels", response_model=list[schemas.NotificationChannelResponse])
def get_channels(db: Session = Depends(database.get_db)):
    return db.query(models.NotificationChannel).all()

@router.post("/channels", response_model=schemas.NotificationChannelResponse)
def create_channel(channel: schemas.NotificationChannelCreate, db: Session = Depends(database.get_db)):
    db_channel = models.NotificationChannel(**channel.model_dump())
    db.add(db_channel)
    db.commit()
    db.refresh(db_channel)
    return db_channel

@router.put("/channels/{channel_id}", response_model=schemas.NotificationChannelResponse)
def update_channel(channel_id: int, channel_update: schemas.NotificationChannelUpdate, db: Session = Depends(database.get_db)):
    db_channel = db.query(models.NotificationChannel).filter(models.NotificationChannel.id == channel_id).first()
    if not db_channel:
        raise HTTPException(status_code=404, detail="Channel not found")
    
    for key, value in channel_update.model_dump(exclude_unset=True).items():
        setattr(db_channel, key, value)
    
    db.commit()
    db.refresh(db_channel)
    return db_channel

@router.delete("/channels/{channel_id}")
def delete_channel(channel_id: int, db: Session = Depends(database.get_db)):
    db_channel = db.query(models.NotificationChannel).filter(models.NotificationChannel.id == channel_id).first()
    if not db_channel:
        raise HTTPException(status_code=404, detail="Channel not found")
    
    db.delete(db_channel)
    db.commit()
    return {"ok": True}

@router.post("/channels/{channel_id}/test")
async def test_channel(channel_id: int, background_tasks: BackgroundTasks, db: Session = Depends(database.get_db)):
    db_channel = db.query(models.NotificationChannel).filter(models.NotificationChannel.id == channel_id).first()
    if not db_channel:
        raise HTTPException(status_code=404, detail="Channel not found")
    
    # Send test notification in background
    background_tasks.add_task(NotificationService.send_test_notification, db_channel)
    
    return {"message": "Test notification queued"}
