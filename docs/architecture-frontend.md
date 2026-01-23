# Frontend Architecture

## Overview

The PriceFlow frontend is a Single Page Application (SPA) built with React 18 and Vite. It provides the user interface for tracking products, viewing history, and configuring settings.

## Technology Stack

- **Core**: React 18
- **Build Tool**: Vite
- **Styling**: Tailwind CSS
- **Components**: Radix UI (headless), Lucide React (icons)
- **Routing**: React Router DOM
- **Internationalization**: i18next

## Key Directories

- `src/components/`: Reusable UI components.
- `src/pages/`: Page-level components mapped to routes.
- `src/api/` (implied): API integration logic.
- `src/lib/`: Utilities and helper functions.

## State Management

State is likely managed via React's built-in `useState`/`useContext` hooks, with `axios` handling async data fetching.

## Design System

The UI utilizes Tailwind CSS for utility-first styling and Radix UI primitives for accessible component logic (Dialogs, Tooltips, etc.).
