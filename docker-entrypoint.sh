#!/bin/sh
set -e

echo "Setting up screenshots directory..."
mkdir -p screenshots

echo "Running database migrations..."
alembic upgrade heads

echo "Starting application..."
exec uvicorn app.main:app --host 0.0.0.0 --port 8555
