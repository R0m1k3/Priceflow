# Integration Architecture

## System Overview

PriceFlow operates as a distributed system with three main components interacting over the network:

1. **Frontend (Client)**: React SPA running in the user's browser.
2. **Backend (API)**: Python FastAPI service.
3. **Browserless Service**: Headless Chrome instance.

## Communication Patterns

### Frontend ↔ Backend

- **Protocol**: HTTP/REST
- **Format**: JSON
- **Authentication**: (To be determined - check auth middleware)
- **Endpoints**: Exposed via `app/routers`

### Backend ↔ Database

- **Protocol**: PostgreSQL Wire Protocol (TCP)
- **Driver**: `psycopg2-binary` / SQLAlchemy
- **Connection**: Persistent pool

### Backend ↔ Browserless

- **Protocol**: WebSocket
- **Library**: Playwright
- **Flow**: The backend connects to the remote browser to execute scraping scripts and retrieving page content/screenshots.

### Backend ↔ External AI Providers

- **Protocol**: HTTPS (API Calls)
- **Services**: OpenAI, Anthropic, OpenRouter, Ollama (Local/Network)
- **Library**: `litellm`

## Data Flow Diagram (Conceptual)

```mermaid
graph TD
    User[User Browser] <-->|HTTP/REST| API[FastAPI Backend]
    API <-->|SQL| DB[(PostgreSQL)]
    API <-->|WebSocket| Chrome[Browserless]
    API <-->|HTTPS| AI[AI Providers (OpenAI/Ollama)]
    Chrome -->|HTTP| Web[Target Websites]
```
