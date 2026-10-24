"""
Authentication service for user management and JWT tokens.
"""
import base64
import hashlib
import hmac
import logging
import os
import secrets
from datetime import UTC, datetime, timedelta

import bcrypt
import jwt
from sqlalchemy.orm import Session

from app import models

logger = logging.getLogger(__name__)

# JWT Configuration
JWT_SECRET = os.getenv("JWT_SECRET", secrets.token_hex(32))
JWT_ALGORITHM = "HS256"
JWT_EXPIRATION_HOURS = 24

# Default admin account (password from ADMIN_PASSWORD env or randomly generated)
DEFAULT_ADMIN_USERNAME = "admin"

BCRYPT_PREFIXES = ("$2a$", "$2b$", "$2y$")


def _bcrypt_input(password: str) -> bytes:
    """Pre-hash the password so bcrypt's 72-byte limit never truncates it."""
    return base64.b64encode(hashlib.sha256(password.encode()).digest())


def hash_password(password: str) -> str:
    """Hash password using bcrypt."""
    return bcrypt.hashpw(_bcrypt_input(password), bcrypt.gensalt()).decode()


def is_legacy_hash(password_hash: str) -> bool:
    """Legacy format: single-round salted SHA-256 ("salt:hexdigest")."""
    return not password_hash.startswith(BCRYPT_PREFIXES)


def verify_password(password: str, password_hash: str) -> bool:
    """Verify password against hash (bcrypt, or legacy salted SHA-256)."""
    if not password_hash:
        return False
    if not is_legacy_hash(password_hash):
        try:
            return bcrypt.checkpw(_bcrypt_input(password), password_hash.encode())
        except ValueError:
            return False
    try:
        salt, stored_hash = password_hash.split(":")
        computed_hash = hashlib.sha256(f"{salt}{password}".encode()).hexdigest()
        return hmac.compare_digest(computed_hash, stored_hash)
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
    # Transparent upgrade of legacy SHA-256 hashes to bcrypt
    if is_legacy_hash(user.password_hash):
        user.password_hash = hash_password(password)
        db.commit()
        logger.info(f"Password hash upgraded to bcrypt for user '{user.username}'")
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
    """Create the admin user if no users exist.

    The password comes from the ADMIN_PASSWORD env var; otherwise a random
    password is generated and logged once.
    """
    user_count = db.query(models.User).count()
    if user_count == 0:
        password = os.getenv("ADMIN_PASSWORD") or ""
        if password:
            create_user(db, DEFAULT_ADMIN_USERNAME, password, is_admin=True)
            logger.info(f"Utilisateur '{DEFAULT_ADMIN_USERNAME}' créé avec le mot de passe défini dans ADMIN_PASSWORD")
        else:
            password = secrets.token_urlsafe(16)
            create_user(db, DEFAULT_ADMIN_USERNAME, password, is_admin=True)
            logger.warning(
                f"Utilisateur '{DEFAULT_ADMIN_USERNAME}' créé avec le mot de passe généré : {password} "
                "(affiché une seule fois, changez-le après la première connexion)"
            )
        return True
    return False
