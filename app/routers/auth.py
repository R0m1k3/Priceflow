"""
Authentication router for login, user management, and admin functions.
"""
import logging
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app import models
from app.database import SessionLocal
from app.services import auth_service
from app.dependencies import get_db, get_current_user, get_admin_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/auth", tags=["auth"])





# Pydantic models
class LoginRequest(BaseModel):
    username: str
    password: str


class LoginResponse(BaseModel):
    token: str
    username: str
    is_admin: bool


class UserResponse(BaseModel):
    id: int
    username: str
    is_admin: bool
    is_active: bool
    created_at: str
    last_login: str | None

    class Config:
        from_attributes = True


class CreateUserRequest(BaseModel):
    username: str
    password: str
    is_admin: bool = False


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str


class AdminChangePasswordRequest(BaseModel):
    new_password: str





@router.post("/login", response_model=LoginResponse)
def login(request: LoginRequest, db: Session = Depends(get_db)):
    """Authenticate user and return JWT token."""
    user = auth_service.authenticate_user(db, request.username, request.password)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Nom d'utilisateur ou mot de passe incorrect",
        )

    # Update last login
    auth_service.update_last_login(db, user)

    # Create token
    token = auth_service.create_token(user.id, user.username, user.is_admin)

    logger.info(f"User '{user.username}' logged in successfully")

    return LoginResponse(
        token=token,
        username=user.username,
        is_admin=user.is_admin,
    )


@router.get("/me", response_model=UserResponse)
def get_current_user_info(current_user: models.User = Depends(get_current_user)):
    """Get current user information."""
    return UserResponse(
        id=current_user.id,
        username=current_user.username,
        is_admin=current_user.is_admin,
        is_active=current_user.is_active,
        created_at=current_user.created_at.isoformat() if current_user.created_at else "",
        last_login=current_user.last_login.isoformat() if current_user.last_login else None,
    )


@router.post("/change-password")
def change_password(
    request: ChangePasswordRequest,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Change current user's password."""
    # Verify current password
    if not auth_service.verify_password(request.current_password, current_user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Mot de passe actuel incorrect",
        )

    # Update password
    auth_service.update_password(db, current_user, request.new_password)

    logger.info(f"User '{current_user.username}' changed password")

    return {"message": "Mot de passe modifié avec succès"}


# Admin endpoints
@router.get("/users", response_model=list[UserResponse])
def list_users(
    admin_user: models.User = Depends(get_admin_user),
    db: Session = Depends(get_db),
):
    """List all users (admin only)."""
    users = auth_service.get_all_users(db)
    return [
        UserResponse(
            id=u.id,
            username=u.username,
            is_admin=u.is_admin,
            is_active=u.is_active,
            created_at=u.created_at.isoformat() if u.created_at else "",
            last_login=u.last_login.isoformat() if u.last_login else None,
        )
        for u in users
    ]


@router.post("/users", response_model=UserResponse)
def create_user(
    request: CreateUserRequest,
    admin_user: models.User = Depends(get_admin_user),
    db: Session = Depends(get_db),
):
    """Create a new user (admin only)."""
    # Check if username already exists
    existing = auth_service.get_user_by_username(db, request.username)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Ce nom d'utilisateur existe déjà",
        )

    user = auth_service.create_user(db, request.username, request.password, request.is_admin)

    logger.info(f"Admin '{admin_user.username}' created user '{user.username}'")

    return UserResponse(
        id=user.id,
        username=user.username,
        is_admin=user.is_admin,
        is_active=user.is_active,
        created_at=user.created_at.isoformat() if user.created_at else "",
        last_login=None,
    )


@router.delete("/users/{user_id}")
def delete_user(
    user_id: int,
    admin_user: models.User = Depends(get_admin_user),
    db: Session = Depends(get_db),
):
    """Delete a user (admin only)."""
    # Prevent self-deletion
    if user_id == admin_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Vous ne pouvez pas supprimer votre propre compte",
        )

    success = auth_service.delete_user(db, user_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Utilisateur non trouvé",
        )

    logger.info(f"Admin '{admin_user.username}' deleted user ID {user_id}")

    return {"message": "Utilisateur supprimé"}


@router.put("/users/{user_id}/toggle-active", response_model=UserResponse)
def toggle_user_active(
    user_id: int,
    admin_user: models.User = Depends(get_admin_user),
    db: Session = Depends(get_db),
):
    """Toggle user active status (admin only)."""
    # Prevent self-deactivation
    if user_id == admin_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Vous ne pouvez pas désactiver votre propre compte",
        )

    user = auth_service.toggle_user_active(db, user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Utilisateur non trouvé",
        )

    logger.info(f"Admin '{admin_user.username}' toggled active status for user '{user.username}'")

    return UserResponse(
        id=user.id,
        username=user.username,
        is_admin=user.is_admin,
        is_active=user.is_active,
        created_at=user.created_at.isoformat() if user.created_at else "",
        last_login=user.last_login.isoformat() if user.last_login else None,
    )


@router.put("/users/{user_id}/password")
def admin_change_user_password(
    user_id: int,
    request: AdminChangePasswordRequest,
    admin_user: models.User = Depends(get_admin_user),
    db: Session = Depends(get_db),
):
    """Change a user's password (admin only)."""
    user = auth_service.get_user_by_id(db, user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Utilisateur non trouvé",
        )

    auth_service.update_password(db, user, request.new_password)

    logger.info(f"Admin '{admin_user.username}' changed password for user '{user.username}'")

    return {"message": "Mot de passe modifié avec succès"}
