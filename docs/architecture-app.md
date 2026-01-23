# Backend Architecture

## Overview

The PriceFlow backend is a high-performance API and worker service built with Python and FastAPI. It handles product management, scraping logic, database operations, and notifications.

## Technology Stack

- **Framework**: FastAPI (Python 3.12)
- **Server**: Uvicorn (ASGI)
- **Database**: PostgreSQL (via SQLAlchemy ORM)
- **Migrations**: Alembic

## Core Components

### 1. API Layer (`app/routers`)

Exposes REST endpoints for the frontend to consume. Handles request validation via Pydantic schemas.

### 2. Service Layer (`app/services`)

Contains the business logic, including:

- **Scraping**: Logic to control Playwright/Browserless.
- **AI Analysis**: Integration with LiteLLM for image processing.
- **Notifications**: Apprise integration.

### 3. Data Layer (`app/models.py`)

Defines the database schema using SQLAlchemy.

- **Models**: Products, Prices, Users (if applicable).

### 4. Background Workers

Uses `APScheduler` or similar mechanisms (implied from deps) to run periodic scraping tasks.

## Scraping Architecture

The backend delegates browser rendering to a separate `Browserless` service (Docker container) via WebSocket, ensuring the main API remains responsive.
