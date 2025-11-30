# Stage 1: Build Frontend
FROM node:22-alpine as frontend-build

WORKDIR /app/frontend

COPY frontend/package.json frontend/package-lock.json* ./
RUN npm install

# Force cache invalidation for frontend source
ARG CACHEBUST=1
COPY frontend/ .
RUN npm run build

# Stage 2: Build Backend and Serve
FROM python:3.12-slim

WORKDIR /app

# Enable unbuffered logging
ENV PYTHONUNBUFFERED=1

# Install system dependencies for crawl4ai and playwright
RUN apt-get update && apt-get install -y \
  wget \
  gnupg \
  # Playwright dependencies for Chromium
  libnss3 \
  libnspr4 \
  libatk1.0-0 \
  libatk-bridge2.0-0 \
  libcups2 \
  libdrm2 \
  libdbus-1-3 \
  libxkbcommon0 \
  libxcomposite1 \
  libxdamage1 \
  libxfixes3 \
  libxrandr2 \
  libgbm1 \
  libasound2 \
  libpango-1.0-0 \
  libcairo2 \
  libatspi2.0-0 \
  fonts-liberation \
  libappindicator3-1 \
  xdg-utils \
  && rm -rf /var/lib/apt/lists/*

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Copy build files
COPY pyproject.toml .
COPY README.md .

# Use uv for faster installation (fixed syntax)
RUN uv pip install --system --no-cache .

# Install Playwright browsers for crawl4ai
RUN playwright install chromium --with-deps

# Copy backend code
COPY app/ ./app
COPY alembic.ini ./
COPY docker-entrypoint.sh ./

# Make entrypoint executable
RUN chmod +x docker-entrypoint.sh

# Copy built frontend static files
COPY --from=frontend-build /app/frontend/dist /app/static

# Create screenshots and debug_dumps directories
RUN mkdir -p screenshots debug_dumps

# Expose port
EXPOSE 8555

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8555/api/')" || exit 1

ENTRYPOINT ["./docker-entrypoint.sh"]
