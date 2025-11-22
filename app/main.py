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

from app.database import engine
from app.limiter import limiter
from app.routers import items, jobs, notifications, openrouter, search, search_sites, settings
from app.services.scheduler_service import scheduled_refresh, scheduler

# Configure logging
logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO").upper(),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def run_migrations():
    """Run database migrations for missing columns"""
    migrations = [
        # Add price_selector to search_sites if missing
        ("search_sites", "price_selector", "ALTER TABLE search_sites ADD COLUMN price_selector VARCHAR(512)"),
    ]

    with engine.connect() as conn:
        for table, column, sql in migrations:
            result = conn.execute(text(
                f"SELECT 1 FROM information_schema.columns WHERE table_name = '{table}' AND column_name = '{column}'"
            ))
            if not result.fetchone():
                logger.info(f"Adding missing column: {table}.{column}")
                conn.execute(text(sql))
                conn.commit()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Run database migrations
    logger.info("Running database migrations...")
    try:
        run_migrations()
        logger.info("Database migrations completed")
    except Exception as e:
        logger.error(f"Migration error: {e}")

    logger.info("Starting smart scheduler (Heartbeat: 1 minute)")
    scheduler.add_job(scheduled_refresh, IntervalTrigger(minutes=1), id="refresh_job", replace_existing=True)
    scheduler.start()
    logger.info("Application started")
    yield
    logger.info("Shutting down scheduler...")
    scheduler.shutdown(wait=True)
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
for router in [notifications.router, items.router, settings.router, jobs.router, openrouter.router]:
    app.include_router(router, prefix="/api")

# Search routers (already have /api prefix)
app.include_router(search.router)
app.include_router(search_sites.router)


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
