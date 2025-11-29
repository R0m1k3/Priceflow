from datetime import UTC, datetime

from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from .database import Base


class User(Base):
    """User model for authentication"""
    __tablename__ = "users"

    id: int = Column(Integer, primary_key=True, index=True)  # type: ignore
    username: str = Column(String, unique=True, nullable=False, index=True)  # type: ignore
    password_hash: str = Column(String, nullable=False)  # type: ignore
    is_admin: bool = Column(Boolean, default=False)  # type: ignore
    is_active: bool = Column(Boolean, default=True)  # type: ignore
    created_at: datetime = Column(DateTime, default=lambda: datetime.now(UTC))  # type: ignore
    last_login: datetime | None = Column(DateTime, nullable=True)  # type: ignore





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
    is_available: bool | None = Column(Boolean, nullable=True, default=True)  # type: ignore  # Product still exists
    category: str | None = Column(String, nullable=True)  # type: ignore  # User-defined category
    tags: str | None = Column(String, nullable=True)  # type: ignore
    description: str | None = Column(String, nullable=True)  # type: ignore

    # Confidence scores for latest extraction
    current_price_confidence: float | None = Column(Float, nullable=True)  # type: ignore
    in_stock_confidence: float | None = Column(Float, nullable=True)  # type: ignore

    is_active: bool = Column(Boolean, default=True)  # type: ignore
    last_checked: datetime | None = Column(DateTime, nullable=True)  # type: ignore
    is_refreshing: bool = Column(Boolean, default=False)  # type: ignore
    last_error: str | None = Column(String, nullable=True)  # type: ignore

    price_history = relationship("PriceHistory", back_populates="item", cascade="all, delete-orphan")

    notification_channel_id: int | None = Column(Integer, ForeignKey("notification_channels.id"), nullable=True)  # type: ignore
    notification_channel = relationship("NotificationChannel", back_populates="items")


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
    debug_enabled: bool = Column(Boolean, default=False)  # type: ignore  # Activer le dump HTML pour ce site
    price_selector: str | None = Column(String, nullable=True)  # type: ignore  # Sélecteur CSS pour le prix
    search_url: str | None = Column(String, nullable=True)  # type: ignore  # URL de recherche avec {query} placeholder
    product_link_selector: str | None = Column(String, nullable=True)  # type: ignore  # Sélecteur CSS pour les liens produits
    created_at: datetime = Column(DateTime, default=lambda: datetime.now(UTC))  # type: ignore
    updated_at: datetime = Column(DateTime, default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC))  # type: ignore


class NotificationChannel(Base):
    __tablename__ = "notification_channels"

    id: int = Column(Integer, primary_key=True, index=True)  # type: ignore
    name: str = Column(String, nullable=False)  # type: ignore
    type: str = Column(String, nullable=False)  # type: ignore  # "email", "discord", "mattermost"
    configuration: str = Column(Text, nullable=False)  # type: ignore  # JSON or encrypted string
    is_active: bool = Column(Boolean, default=True)  # type: ignore
    created_at: datetime = Column(DateTime, default=lambda: datetime.now(UTC))  # type: ignore

    items = relationship("Item", back_populates="notification_channel")


# === CATALOG MODULE MODELS ===

class Enseigne(Base):
    """Stores/brands for promotional catalogs"""
    __tablename__ = "enseignes"

    id: int = Column(Integer, primary_key=True, index=True)  # type: ignore
    nom: str = Column(String, nullable=False)  # type: ignore  # "Gifi"
    slug_bonial: str = Column(String, unique=True, nullable=False, index=True)  # type: ignore  # "Gifi"
    logo_url: str | None = Column(String, nullable=True)  # type: ignore
    couleur: str = Column(String, nullable=False)  # type: ignore  # "#E30613"
    site_url: str | None = Column(String, nullable=True)  # type: ignore
    description: str | None = Column(String, nullable=True)  # type: ignore
    is_active: bool = Column(Boolean, default=True)  # type: ignore
    ordre_affichage: int = Column(Integer, default=0)  # type: ignore
    created_at: datetime = Column(DateTime, default=lambda: datetime.now(UTC))  # type: ignore
    updated_at: datetime = Column(DateTime, default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC))  # type: ignore

    # Relationships
    catalogues = relationship("Catalogue", back_populates="enseigne", cascade="all, delete-orphan")
    scraping_logs = relationship("ScrapingLog", back_populates="enseigne")


class Catalogue(Base):
    """Promotional catalogs from stores"""
    __tablename__ = "catalogues"

    id: int = Column(Integer, primary_key=True, index=True)  # type: ignore
    enseigne_id: int = Column(Integer, ForeignKey("enseignes.id"), nullable=False, index=True)  # type: ignore
    titre: str = Column(String, nullable=False)  # type: ignore
    description: str | None = Column(Text, nullable=True)  # type: ignore
    date_debut: datetime = Column(DateTime, nullable=False, index=True)  # type: ignore
    date_fin: datetime = Column(DateTime, nullable=False, index=True)  # type: ignore
    image_couverture_url: str = Column(String, nullable=False)  # type: ignore
    catalogue_url: str = Column(String, nullable=False)  # type: ignore  # URL Bonial viewer
    nombre_pages: int = Column(Integer, default=0)  # type: ignore
    statut: str = Column(String, default="actif", index=True)  # type: ignore  # actif, termine, erreur
    content_hash: str = Column(String(64), unique=True, nullable=False, index=True)  # type: ignore  # SHA256
    metadonnees: str | None = Column(Text, nullable=True)  # type: ignore  # JSON for additional data
    created_at: datetime = Column(DateTime, default=lambda: datetime.now(UTC))  # type: ignore
    updated_at: datetime = Column(DateTime, default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC))  # type: ignore

    # Relationships
    enseigne = relationship("Enseigne", back_populates="catalogues")
    pages = relationship("CataloguePage", back_populates="catalogue", cascade="all, delete-orphan")


class CataloguePage(Base):
    """Individual pages of a catalog"""
    __tablename__ = "catalogue_pages"

    id: int = Column(Integer, primary_key=True, index=True)  # type: ignore
    catalogue_id: int = Column(Integer, ForeignKey("catalogues.id"), nullable=False, index=True)  # type: ignore
    numero_page: int = Column(Integer, nullable=False)  # type: ignore
    image_url: str = Column(String, nullable=False)  # type: ignore
    image_thumbnail_url: str | None = Column(String, nullable=True)  # type: ignore
    largeur: int | None = Column(Integer, nullable=True)  # type: ignore
    hauteur: int | None = Column(Integer, nullable=True)  # type: ignore
    created_at: datetime = Column(DateTime, default=lambda: datetime.now(UTC))  # type: ignore

    # Relationship
    catalogue = relationship("Catalogue", back_populates="pages")


class ScrapingLog(Base):
    """Logs of scraping executions"""
    __tablename__ = "scraping_logs"

    id: int = Column(Integer, primary_key=True, index=True)  # type: ignore
    date_execution: datetime = Column(DateTime, default=lambda: datetime.now(UTC), index=True)  # type: ignore
    enseigne_id: int | None = Column(Integer, ForeignKey("enseignes.id"), nullable=True)  # type: ignore  # NULL = all stores
    statut: str = Column(String, nullable=False)  # type: ignore  # success, error, partial
    catalogues_trouves: int = Column(Integer, default=0)  # type: ignore
    catalogues_nouveaux: int = Column(Integer, default=0)  # type: ignore
    catalogues_mis_a_jour: int = Column(Integer, default=0)  # type: ignore
    duree_secondes: float | None = Column(Float, nullable=True)  # type: ignore
    message_erreur: str | None = Column(Text, nullable=True)  # type: ignore
    details: str | None = Column(Text, nullable=True)  # type: ignore  # JSON

    # Relationship
    enseigne = relationship("Enseigne", back_populates="scraping_logs")

    @property
    def enseigne_nom(self) -> str | None:
        return self.enseigne.nom if self.enseigne else None

