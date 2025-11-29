import logging
import os
from contextlib import asynccontextmanager

from apscheduler.triggers.interval import IntervalTrigger
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from sqlalchemy import text

from app.database import SessionLocal, engine
from app.limiter import limiter
from app.routers import auth, items, jobs, notifications, openrouter, search, search_sites, settings, debug, catalogues
from app.services.scheduler_service import scheduled_refresh, scheduler
from app.services import auth_service, search_service, seed_enseignes
from app.services.scheduler import start_scheduler as start_catalog_scheduler, stop_scheduler as stop_catalog_scheduler

# Configure logging
logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO").upper(),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def run_migrations():
    """Run database migrations for missing tables and columns"""
    with engine.connect() as conn:
        # 0. Create users table if it doesn't exist
        result = conn.execute(text(
            "SELECT 1 FROM information_schema.tables WHERE table_name = 'users'"
        ))
        if not result.fetchone():
            logger.info("Creating users table...")
            conn.execute(text("""
                CREATE TABLE users (
                    id SERIAL PRIMARY KEY,
                    username VARCHAR(255) UNIQUE NOT NULL,
                    password_hash VARCHAR(512) NOT NULL,
                    is_admin BOOLEAN DEFAULT FALSE,
                    is_active BOOLEAN DEFAULT TRUE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_login TIMESTAMP
                )
            """))
            conn.execute(text("CREATE INDEX IF NOT EXISTS idx_users_username ON users(username)"))
            conn.commit()
            logger.info("users table created")

        # 1. Create search_sites table if it doesn't exist
        result = conn.execute(text(
            "SELECT 1 FROM information_schema.tables WHERE table_name = 'search_sites'"
        ))
        if not result.fetchone():
            logger.info("Creating search_sites table...")
            conn.execute(text("""
                CREATE TABLE search_sites (
                    id SERIAL PRIMARY KEY,
                    name VARCHAR(255) NOT NULL,
                    domain VARCHAR(512) UNIQUE NOT NULL,
                    logo_url VARCHAR(1024),
                    category VARCHAR(255),
                    is_active BOOLEAN DEFAULT TRUE,
                    priority INTEGER DEFAULT 0,
                    requires_js BOOLEAN DEFAULT FALSE,
                    price_selector VARCHAR(512),
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """))
            conn.execute(text("CREATE INDEX IF NOT EXISTS idx_search_sites_domain ON search_sites(domain)"))
            conn.execute(text("CREATE INDEX IF NOT EXISTS idx_search_sites_is_active ON search_sites(is_active)"))
            conn.commit()
            logger.info("search_sites table created")
        else:
            # 2. Add missing columns
            columns_to_add = [
                ("price_selector", "VARCHAR(512)"),
                ("search_url", "VARCHAR(1024)"),
                ("product_link_selector", "VARCHAR(512)"),
            ]
            for col_name, col_type in columns_to_add:
                result = conn.execute(text(
                    f"SELECT 1 FROM information_schema.columns WHERE table_name = 'search_sites' AND column_name = '{col_name}'"
                ))
                if not result.fetchone():
                    logger.info(f"Adding {col_name} column to search_sites...")
                    conn.execute(text(f"ALTER TABLE search_sites ADD COLUMN {col_name} {col_type}"))
                    conn.commit()
                    logger.info(f"{col_name} column added")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Run database migrations
    logger.info("Running database migrations...")
    try:
        run_migrations()
        logger.info("Database migrations completed")
    except Exception as e:
        logger.error(f"Migration error: {e}")

    # Seed default sites and admin user
    logger.info("Seeding default data...")
    try:
        db = SessionLocal()
        try:
            # Seed search sites
            created = search_service.seed_default_sites(db)
            if created > 0:
                logger.info(f"{created} site(s) de recherche créé(s)")
            else:
                logger.info("Sites de recherche déjà initialisés")

            # Seed default admin user
            if auth_service.seed_default_admin(db):
                logger.info("Utilisateur admin par défaut créé (admin/admin)")
            else:
                logger.info("Utilisateurs déjà initialisés")
            
            # Seed enseignes for catalog module
            created_enseignes = seed_enseignes.seed_enseignes(db)
            if created_enseignes > 0:
                logger.info(f"{created_enseignes} enseigne(s) de catalogues créée(s)")
            else:
                 logger.info("Enseignes déjà initialisés")
        finally:
            db.close()
    except Exception as e:
        logger.error(f"Error seeding data: {e}")

    logger.info("Starting smart scheduler (Heartbeat: 1 minute)")
    scheduler.add_job(scheduled_refresh, IntervalTrigger(minutes=1), id="refresh_job", replace_existing=True)
    scheduler.start()
    
    # Start catalog scraping scheduler
    logger.info("Starting catalog scraping scheduler (6h and 18h daily)")
    start_catalog_scheduler()
    
    logger.info("Application started")
    yield
    logger.info("Shutting down schedulers...")
    scheduler.shutdown(wait=True)
    stop_catalog_scheduler()
    logger.info("Application shutdown complete")


app = FastAPI(title="PriceFlow API", version="0.1.0", lifespan=lifespan)

# Rate Limiting & CORS
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)  # type: ignore
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("CORS_ORIGINS", "*").split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def log_requests(request: Request, call_next):
    logger.debug(f"Request: {request.method} {request.url}")
    response = await call_next(request)
    logger.debug(f"Response: {response.status_code}")
    return response


# Static Files
if os.path.exists("static"):
    app.mount("/assets", StaticFiles(directory="static/assets"), name="assets")
os.makedirs("screenshots", exist_ok=True)
app.mount("/screenshots", StaticFiles(directory="screenshots"), name="screenshots")

# Routers
for router in [notifications.router, items.router, settings.router, jobs.router, openrouter.router, debug.router]:
    app.include_router(router, prefix="/api")

# Search routers (already have /api prefix)
app.include_router(search.router)
app.include_router(search_sites.router)

# Catalog router (already has /api prefix)
app.include_router(catalogues.router)

# Auth router (already has /api prefix)
app.include_router(auth.router)


@app.get("/api/")
def read_root():
    return {"message": "Welcome to PriceFlow API"}


# Frontend Serving
@app.get("/{full_path:path}")
async def serve_spa(full_path: str):
    if full_path.startswith(("api", "screenshots", "assets")):
        return {"message": "Not found"}

    # Serve static files from root (favicon, logo, etc.)
    static_file_path = f"static/{full_path}"
    if os.path.isfile(static_file_path):
        return FileResponse(static_file_path)

    # Default to SPA index.html
    if os.path.exists("static/index.html"):
        return FileResponse("static/index.html")
    return {"message": "Frontend not built or not found"}
