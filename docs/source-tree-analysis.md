# Source Tree Analysis

## Critical Directories

```
Priceflow/
├── frontend/                  # React Frontend Application (Part: frontend)
│   ├── public/                # Static assets (favicons, logos)
│   ├── src/
│   │   ├── components/        # Reusable UI components (Radix UI, Custom)
│   │   ├── pages/             # Route components (Dashboard, Settings)
│   │   ├── hooks/             # Custom React hooks
│   │   ├── i18n/              # Internationalization configuration & locales
│   │   ├── lib/               # Utility libraries (utils, constants)
│   │   ├── App.jsx            # Main React component
│   │   └── main.jsx           # Application Entry Point
│   ├── package.json           # Frontend dependencies & scripts
│   └── vite.config.js         # Vite build configuration
├── app/                       # FastAPI Backend Application (Part: app)
│   ├── routers/               # API Endpoints (separated by feature)
│   ├── services/              # Business logic & External integrations (AI, Scraping)
│   ├── core/                  # Core configuration & config loading
│   ├── utils/                 # General utilities
│   ├── alembic/               # Database migrations
│   ├── models.py              # SQLAlchemy Database Models
│   ├── schemas.py             # Pydantic Schemas (Request/Response)
│   └── main.py                # Application Entry Point (FastAPI app)
├── docs/                      # Project Documentation
├── tests/                     # Test suite (Pytest)
├── scripts/                   # Utility scripts (e.g. setup)
├── docker-compose.yml         # Container orchestration config
├── Dockerfile                 # Backend container definition
├── init.sql                   # Database initialization script
└── README.md                  # Project Entry Documentation
```

## Entry Points

- **Frontend**: `frontend/src/main.jsx` - Bootstraps the React application and mounts it to the DOM.
- **Backend**: `app/main.py` - Initializes the FastAPI application, mounts routers, and configures middleware.

## Integration Points

- **API Communication**: The frontend communicates with the backend via REST API calls. Axios is likely used as the HTTP client (from package.json).
- **Database**: The backend connects to the PostgreSQL database container defined in `docker-compose.yml`.
- **Scraping**: The backend connects to the `browserless` service via WebSocket (`ws://browserless:3000`) for Playwright operations.

## Critical Files

- `docker-compose.yml`: Defines the entire stack (App, DB, Browserless).
- `frontend/vite.config.js`: Controls the frontend build process.
- `app/core/config.py` (implied): Likely handles environment variables like `DATABASE_URL`, `OPENAI_API_KEY`.
- `app/models.py`: Defines the data structure (Price, Product, etc.).
