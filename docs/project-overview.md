# PriceFlow

**Suivi de prix intelligent propulsé par l'IA**

## Executive Summary

PriceFlow est une application auto-hébergée de suivi de prix qui utilise l'intelligence artificielle pour analyser visuellement les pages produits. Elle détecte les prix et l'état des stocks via des captures d'écran, supporte de multiples fournisseurs d'IA (OpenAI, Anthropic, Ollama, OpenRouter), et envoie des notifications via Apprise.

## Technology Stack

| Component | Technology | Details |
|-----------|------------|---------|
| **Frontend** | React 18 | Vite, Tailwind CSS, Radix UI, i18next |
| **Backend** | Python 3.12 | FastAPI, Uvicorn, SQLAlchemy |
| **Database** | PostgreSQL | Managed via Docker |
| **Scraping** | Playwright | Browserless service, Beautiful Soup 4, Crawl4AI |
| **AI** | LiteLLM | Supports OpenAI, Anthropic, Ollama, OpenRouter |
| **Infrastructure** | Docker | Docker Compose, Nginx (network) |

## Architecture Type

**Type:** Multi-part (Client/Server)
**Repository Type:** Monorepo/Multi-part structure

The project is divided into two distinct parts:

1. **Frontend**: A React-based Single Page Application (SPA).
2. **Backend**: A Python/FastAPI application acting as the API and worker service.

## Key Features

- **Visual AI Analysis**: Extracts price and stock from screenshots.
- **Multi-provider AI Support**: Flexible configuration for LLMs.
- **Smart Scrolling & History**: Historical tracking of price changes.
- **Multi-channel Notifications**: Discord, Telegram, Email via Apprise.
- **Dockerized Deployment**: Easy setup with Docker Compose.

## Documentation Links

- [Source Tree Analysis](./source-tree-analysis.md)
- [Development Guide](./development-guide.md)
- [Deployment Guide](./deployment-guide.md)
