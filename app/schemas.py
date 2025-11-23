from datetime import datetime

from pydantic import BaseModel, ConfigDict


class ItemCreate(BaseModel):
    url: str
    name: str
    selector: str | None = None
    target_price: float | None = None
    check_interval_minutes: int = 60
    tags: str | None = None
    description: str | None = None


class ItemResponse(ItemCreate):
    id: int
    current_price: float | None
    in_stock: bool | None
    current_price_confidence: float | None = None
    in_stock_confidence: float | None = None
    is_active: bool
    last_checked: datetime | None
    is_refreshing: bool = False
    last_error: str | None = None
    screenshot_url: str | None = None
    model_config = ConfigDict(from_attributes=True)


class PriceHistoryResponse(BaseModel):
    id: int
    price: float
    timestamp: datetime
    price_confidence: float | None = None
    in_stock_confidence: float | None = None
    model_config = ConfigDict(from_attributes=True)


class SettingsUpdate(BaseModel):
    key: str
    value: str


# === Search Sites Schemas ===

class SearchSiteCreate(BaseModel):
    name: str
    domain: str
    logo_url: str | None = None
    category: str | None = None
    is_active: bool = True
    priority: int = 0
    requires_js: bool = False
    price_selector: str | None = None
    search_url: str | None = None  # URL avec {query} placeholder, ex: https://amazon.fr/s?k={query}
    product_link_selector: str | None = None  # Sélecteur CSS pour les liens produits


class SearchSiteUpdate(BaseModel):
    name: str | None = None
    domain: str | None = None
    logo_url: str | None = None
    category: str | None = None
    is_active: bool | None = None
    priority: int | None = None
    requires_js: bool | None = None
    price_selector: str | None = None
    search_url: str | None = None
    product_link_selector: str | None = None


class SearchSiteResponse(BaseModel):
    id: int
    name: str
    domain: str
    logo_url: str | None = None
    category: str | None = None
    is_active: bool
    priority: int
    requires_js: bool
    price_selector: str | None = None
    search_url: str | None = None
    product_link_selector: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
    model_config = ConfigDict(from_attributes=True)


# === Search Results Schemas ===

class SearchQuery(BaseModel):
    query: str
    site_ids: list[int] | None = None  # If None, use all active sites
    max_results: int = 20


class SearchResultItem(BaseModel):
    """Un produit trouvé lors de la recherche"""
    url: str
    title: str
    price: float | None = None
    currency: str = "EUR"
    in_stock: bool | None = None
    image_url: str | None = None
    site_name: str
    site_domain: str
    confidence: float | None = None
    error: str | None = None


class SearchProgress(BaseModel):
    """Progression de la recherche pour SSE"""
    status: str  # "searching", "scraping", "completed", "error"
    total: int
    completed: int
    current_site: str | None = None
    results: list[SearchResultItem] = []
    message: str | None = None
