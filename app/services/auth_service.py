"""
Authentication service for user management and JWT tokens.
"""
import hashlib
import os
import secrets
from datetime import UTC, datetime, timedelta

import jwt
from sqlalchemy.orm import Session

from app import models

# JWT Configuration
JWT_SECRET = os.getenv("JWT_SECRET", secrets.token_hex(32))
JWT_ALGORITHM = "HS256"
JWT_EXPIRATION_HOURS = 24

# Default admin credentials
DEFAULT_ADMIN_USERNAME = "admin"
DEFAULT_ADMIN_PASSWORD = "admin"


def hash_password(password: str) -> str:
    """Hash password using SHA-256 with salt."""
    salt = secrets.token_hex(16)
    password_hash = hashlib.sha256(f"{salt}{password}".encode()).hexdigest()
    return f"{salt}:{password_hash}"


def verify_password(password: str, password_hash: str) -> bool:
    """Verify password against hash."""
    try:
        salt, stored_hash = password_hash.split(":")
        computed_hash = hashlib.sha256(f"{salt}{password}".encode()).hexdigest()
        return computed_hash == stored_hash
    except ValueError:
        return False


def create_token(user_id: int, username: str, is_admin: bool) -> str:
    """Create JWT token for authenticated user."""
    payload = {
        "user_id": user_id,
        "username": username,
        "is_admin": is_admin,
        "exp": datetime.now(UTC) + timedelta(hours=JWT_EXPIRATION_HOURS),
        "iat": datetime.now(UTC),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def decode_token(token: str) -> dict | None:
    """Decode and validate JWT token."""
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None


def get_user_by_username(db: Session, username: str) -> models.User | None:
    """Get user by username."""
    return db.query(models.User).filter(models.User.username == username).first()


def get_user_by_id(db: Session, user_id: int) -> models.User | None:
    """Get user by ID."""
    return db.query(models.User).filter(models.User.id == user_id).first()


def authenticate_user(db: Session, username: str, password: str) -> models.User | None:
    """Authenticate user with username and password."""
    user = get_user_by_username(db, username)
    if not user:
        return None
    if not verify_password(password, user.password_hash):
        return None
    if not user.is_active:
        return None
    return user


def create_user(
    db: Session,
    username: str,
    password: str,
    is_admin: bool = False,
) -> models.User:
    """Create a new user."""
    password_hash = hash_password(password)
    user = models.User(
        username=username,
        password_hash=password_hash,
        is_admin=is_admin,
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def update_password(db: Session, user: models.User, new_password: str) -> None:
    """Update user password."""
    user.password_hash = hash_password(new_password)
    db.commit()


def update_last_login(db: Session, user: models.User) -> None:
    """Update user's last login timestamp."""
    user.last_login = datetime.now(UTC)
    db.commit()


def get_all_users(db: Session) -> list[models.User]:
    """Get all users."""
    return db.query(models.User).all()


def delete_user(db: Session, user_id: int) -> bool:
    """Delete a user by ID."""
    user = get_user_by_id(db, user_id)
    if not user:
        return False
    db.delete(user)
    db.commit()
    return True


def toggle_user_active(db: Session, user_id: int) -> models.User | None:
    """Toggle user active status."""
    user = get_user_by_id(db, user_id)
    if not user:
        return None
    user.is_active = not user.is_active
    db.commit()
    db.refresh(user)
    return user


def seed_default_admin(db: Session) -> bool:
    """Create default admin user if no users exist."""
    user_count = db.query(models.User).count()
    if user_count == 0:
        create_user(db, DEFAULT_ADMIN_USERNAME, DEFAULT_ADMIN_PASSWORD, is_admin=True)
        return True
    return False
