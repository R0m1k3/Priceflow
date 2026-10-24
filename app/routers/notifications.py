from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from app import database, models, schemas
from app.dependencies import get_admin_user, get_current_user
from app.services.notification_service import NotificationService

router = APIRouter(
    prefix="/notifications",
    tags=["notifications"],
    dependencies=[Depends(get_current_user)],
)

@router.get("/channels", response_model=list[schemas.NotificationChannelResponse])
def get_channels(
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(get_current_user),
):
    channels = db.query(models.NotificationChannel).all()
    if current_user.is_admin:
        return channels
    # Non-admin users only need id/name to pick a channel: hide the
    # configuration (Apprise URLs / webhook tokens).
    return [
        schemas.NotificationChannelResponse(
            id=c.id,
            name=c.name,
            type=c.type,
            configuration="",
            is_active=c.is_active,
            created_at=c.created_at,
        )
        for c in channels
    ]

@router.post("/channels", response_model=schemas.NotificationChannelResponse, dependencies=[Depends(get_admin_user)])
def create_channel(channel: schemas.NotificationChannelCreate, db: Session = Depends(database.get_db)):
    db_channel = models.NotificationChannel(**channel.model_dump())
    db.add(db_channel)
    db.commit()
    db.refresh(db_channel)
    return db_channel

@router.put("/channels/{channel_id}", response_model=schemas.NotificationChannelResponse, dependencies=[Depends(get_admin_user)])
def update_channel(channel_id: int, channel_update: schemas.NotificationChannelUpdate, db: Session = Depends(database.get_db)):
    db_channel = db.query(models.NotificationChannel).filter(models.NotificationChannel.id == channel_id).first()
    if not db_channel:
        raise HTTPException(status_code=404, detail="Channel not found")
    
    for key, value in channel_update.model_dump(exclude_unset=True).items():
        setattr(db_channel, key, value)
    
    db.commit()
    db.refresh(db_channel)
    return db_channel

@router.delete("/channels/{channel_id}", dependencies=[Depends(get_admin_user)])
def delete_channel(channel_id: int, db: Session = Depends(database.get_db)):
    db_channel = db.query(models.NotificationChannel).filter(models.NotificationChannel.id == channel_id).first()
    if not db_channel:
        raise HTTPException(status_code=404, detail="Channel not found")
    
    db.delete(db_channel)
    db.commit()
    return {"ok": True}

@router.post("/channels/{channel_id}/test", dependencies=[Depends(get_admin_user)])
async def test_channel(channel_id: int, background_tasks: BackgroundTasks, db: Session = Depends(database.get_db)):
    db_channel = db.query(models.NotificationChannel).filter(models.NotificationChannel.id == channel_id).first()
    if not db_channel:
        raise HTTPException(status_code=404, detail="Channel not found")
    
    # Send test notification in background
    background_tasks.add_task(NotificationService.send_test_notification, db_channel)
    
    return {"message": "Test notification queued"}
