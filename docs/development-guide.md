# Development Guide

## Prerequisites

- **Docker** and **Docker Compose**
- **Node.js** (for frontend development)
- **Python 3.12+** (for backend development)
- **Git**

## Environment Setup

1. Clone the repository:

    ```bash
    git clone https://github.com/R0m1k3/Priceflow.git
    cd Priceflow
    ```

2. Configure environment variables:

    ```bash
    cp .env.example .env
    # Edit .env to set your specific configurations (Database, AI keys, etc.)
    ```

3. Create the Docker network (if using specific network setup):

    ```bash
    docker network create nginx_default
    ```

## Local Development

### Backend (FastAPI)

1. Navigate to the backend directory:

    ```bash
    cd app
    ```

2. Install dependencies (recommended to use a virtual environment):

    ```bash
    pip install -r requirements.txt  # Or use a package manager like uv/poetry if configured
    ```

3. Run the development server with hot reload:

    ```bash
    uvicorn app.main:app --reload --port 8555
    ```

    The API will be available at `http://localhost:8555`.

### Frontend (React)

1. Navigate to the frontend directory:

    ```bash
    cd frontend
    ```

2. Install dependencies:

    ```bash
    npm install
    ```

3. Run the development server:

    ```bash
    npm run dev
    ```

    The frontend will be available at the URL provided by Vite (usually `http://localhost:5173`).

## Database Migrations

This project uses Alembic for database migrations.

1. **Create a new migration** (after modifying models):

    ```bash
    alembic revision --autogenerate -m "description of changes"
    ```

2. **Apply migrations**:

    ```bash
    alembic upgrade head
    ```

## Testing

*(To be configured - check `tests/` directory for `pytest` usage)*

```bash
pytest
```
