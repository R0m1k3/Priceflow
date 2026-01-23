# Deployment Guide

## Infrastructure Architecture

PriceFlow is designed to be deployed using Docker Compose. The stack consists of:

- **App**: The main FastAPI backend and application logic.
- **Frontend**: Served typically via Nginx or embedded (in this setup, check docker-compose for service details).
- **Database**: PostgreSQL container.
- **Browserless**: Headless Chrome instance for scraping.

## Services & Ports

| Service | Internal Port | Host Port | Description |
|---------|---------------|-----------|-------------|
| **PriceFlow App** | 8555 | 8555 | Main Application API & UI Serving |
| **PostgreSQL** | 5432 | 5488 | Database Access |
| **Browserless** | 3000 | 3012 | Headless Browser Debugger |

## Deployment Steps

1. **Prepare the Host**: Ensure Docker and Docker Compose are installed.

2. **Configuration**:
    - Copy `.env.example` to `.env`.
    - Set critical variables:
        - `DATABASE_URL`: Connection string for PostgreSQL.
        - `BROWSERLESS_URL`: WebSocket URL for Browserless.
        - `OPENAI_API_KEY` / Other AI Keys: For AI analysis features.

3. **Launch**:

    ```bash
    docker compose up -d
    ```

4. **Access**:
    - Application: `http://localhost:8555`

## Networking

The application uses an external Docker network named `nginx_default`. Ensure this is created:

```bash
docker network create nginx_default
```

## Troubleshooting

- **Scraping Issues**: Check `Browserless` container logs. Ensure the app can reach the browserless service URL.
- **Database Connections**: Verify the `DATABASE_URL` matches the container name and credentials in `docker-compose.yml`.
