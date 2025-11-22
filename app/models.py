from datetime import UTC, datetime

from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from .database import Base


class NotificationProfile(Base):
    __tablename__ = "notification_profiles"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True)
    apprise_url = Column(String)
    notify_on_price_drop = Column(Boolean, default=True)
    notify_on_target_price = Column(Boolean, default=True)
    price_drop_threshold_percent = Column(Float, default=10.0)
    notify_on_stock_change = Column(Boolean, default=True)
    check_interval_minutes = Column(Integer, default=60)

    items = relationship("Item", back_populates="notification_profile")


class Item(Base):
    __tablename__ = "items"

    id: int = Column(Integer, primary_key=True, index=True)  # type: ignore
    url: str = Column(String, index=True)  # type: ignore
    name: str = Column(String)  # type: ignore
    selector: str | None = Column(String, nullable=True)  # type: ignore
    target_price: float | None = Column(Float, nullable=True)  # type: ignore
    check_interval_minutes: int = Column(Integer, default=60)  # type: ignore

    # New fields
    current_price: float | None = Column(Float, nullable=True)  # type: ignore
    in_stock: bool | None = Column(Boolean, nullable=True)  # type: ignore
    tags: str | None = Column(String, nullable=True)  # type: ignore
    description: str | None = Column(String, nullable=True)  # type: ignore

    # Confidence scores for latest extraction
    current_price_confidence: float | None = Column(Float, nullable=True)  # type: ignore
    in_stock_confidence: float | None = Column(Float, nullable=True)  # type: ignore

    is_active: bool = Column(Boolean, default=True)  # type: ignore
    last_checked: datetime | None = Column(DateTime, nullable=True)  # type: ignore
    is_refreshing: bool = Column(Boolean, default=False)  # type: ignore
    last_error: str | None = Column(String, nullable=True)  # type: ignore

    notification_profile_id: int | None = Column(Integer, ForeignKey("notification_profiles.id"), nullable=True)  # type: ignore
    notification_profile = relationship("NotificationProfile", back_populates="items")

    price_history = relationship("PriceHistory", back_populates="item", cascade="all, delete-orphan")


class PriceHistory(Base):
    __tablename__ = "price_history"

    id: int = Column(Integer, primary_key=True, index=True)  # type: ignore
    item_id: int = Column(Integer, ForeignKey("items.id"))  # type: ignore
    price: float = Column(Float)  # type: ignore
    timestamp: datetime = Column(DateTime, default=lambda: datetime.now(UTC))  # type: ignore
    screenshot_path: str | None = Column(String, nullable=True)  # type: ignore

    # Confidence scores and AI metadata
    price_confidence: float | None = Column(Float, nullable=True)  # type: ignore
    in_stock_confidence: float | None = Column(Float, nullable=True)  # type: ignore
    ai_model: str | None = Column(String, nullable=True)  # type: ignore
    ai_provider: str | None = Column(String, nullable=True)  # type: ignore
    prompt_version: str | None = Column(String, nullable=True)  # type: ignore
    repair_used: bool | None = Column(Boolean, nullable=True, default=False)  # type: ignore

    item = relationship("Item", back_populates="price_history")


class Settings(Base):
    __tablename__ = "settings"

    key = Column(String, primary_key=True, index=True)
    value = Column(Text)


class SearchSite(Base):
    """Sites configurés pour la recherche de produits"""
    __tablename__ = "search_sites"

    id: int = Column(Integer, primary_key=True, index=True)  # type: ignore
    name: str = Column(String, nullable=False)  # type: ignore  # "Amazon France"
    domain: str = Column(String, unique=True, nullable=False, index=True)  # type: ignore  # "amazon.fr"
    logo_url: str | None = Column(String, nullable=True)  # type: ignore
    category: str | None = Column(String, nullable=True)  # type: ignore  # "Tech", "Déco", "Généraliste"
    is_active: bool = Column(Boolean, default=True)  # type: ignore
    priority: int = Column(Integer, default=0)  # type: ignore  # Ordre d'affichage
    requires_js: bool = Column(Boolean, default=False)  # type: ignore  # Force Browserless si True
    price_selector: str | None = Column(String, nullable=True)  # type: ignore  # Sélecteur CSS pour le prix
    created_at: datetime = Column(DateTime, default=lambda: datetime.now(UTC))  # type: ignore
    updated_at: datetime = Column(DateTime, default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC))  # type: ignore
