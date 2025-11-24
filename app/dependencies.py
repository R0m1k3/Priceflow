"""
Shared dependencies for the application.
"""
from typing import Annotated

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from app import models
from app.database import SessionLocal
from app.services import auth_service


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_current_user(
    authorization: Annotated[str | None, Header()] = None,
    db: Session = Depends(get_db),
) -> models.User:
    """Dependency to get current authenticated user from JWT token."""
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Non authentifié",
        )

    # Extract token from "Bearer <token>" format
    parts = authorization.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Format de token invalide",
        )

    token = parts[1]
    payload = auth_service.decode_token(token)

    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token invalide ou expiré",
        )

    user = auth_service.get_user_by_id(db, payload["user_id"])
    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Utilisateur non trouvé ou désactivé",
        )

    return user


def get_admin_user(
    current_user: models.User = Depends(get_current_user),
) -> models.User:
    """Dependency to require admin privileges."""
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Accès administrateur requis",
        )
    return current_user
