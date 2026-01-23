# Data Models

## Database Schema

The project uses PostgreSQL managed via SQLAlchemy.

> **Note**: This is a high-level summary from a Quick Scan. Run a Deep Scan to generate full schema documentation.

## Tables

Models are defined in `app/models.py`. Key entities likely include:

- **Product** (or Item): The object being tracked.
- **Price**: Historical price points.
- **(Others pending deep scan)**

## Migrations

Database schema changes are managed by Alembic. Migration scripts are located in `app/alembic/versions/`.
