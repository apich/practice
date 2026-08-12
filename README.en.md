# Agent Platform

> English | [中文](README.md)

An AI Agent building and distribution platform based on AgentScope 2.0. Developers can build and publish agents, while end users can browse and use published agents in the marketplace.

**Core flow:** Build → Publish → Browse → Use

- **Developers**: Build and configure AI agents in the Admin space, then publish them to the marketplace
- **End users**: Browse published agents in the Space space and use them via chat or structured forms

The platform includes built-in authentication (JWT / OAuth2.0 password grant), role-based access control, agent versioning, and sandboxed execution.

## Structure

```
agent-platform/
├── backend/                # Python backend (FastAPI + AgentScope)
│   ├── main.py             # Application entry point
│   ├── _config.py          # Centralized configuration (pydantic-settings)
│   ├── _auth/              # Authentication & authorization
│   │   ├── router.py       # /auth/* endpoints (login, register, refresh)
│   │   ├── service.py      # AuthService — OAuth2.0 password grant delegation
│   │   ├── security.py     # JWT utilities, SecurityService (TTLCache)
│   │   ├── middleware.py   # AuthMiddleware — JWT decode + AuthContext
│   │   ├── access_control.py  # Role-based API access control
│   │   ├── context.py      # AuthContext (ContextVar)
│   │   ├── exceptions.py   # AuthenticationError / AuthorizationError
│   │   └── models.py       # User ORM model, Role constants
│   ├── _publish/           # Agent publishing & versioning
│   ├── _sandbox/           # Docker / K8s sandbox managers
│   ├── _db/                # SQLAlchemy async engine & session
│   ├── .env.example        # Configuration template
│   └── pyproject.toml      # Python dependencies
├── frontend/               # React frontend (Vite + TailwindCSS)
│   ├── src/
│   │   ├── pages/          # Admin (developer) & Space (end-user) pages
│   │   ├── components/      # UI components, auth guards, dialogs
│   │   ├── hooks/          # useAuth, etc.
│   │   └── api/            # API client with JWT support
│   └── package.json
└── Plan.md                 # Development plan & architecture
```

## Prerequisites

| Dependency | Version | Purpose |
|---|---|---|
| Python | >= 3.11 | Backend runtime |
| Node.js | >= 18 | Frontend build |
| pnpm | >= 8 | Frontend package manager |
| Redis | >= 6 | Message bus & storage backend |

> SQLite is used by default for the platform database (zero setup). PostgreSQL is optional for production.

## Quick Start

### 1. Backend

#### Option A: Using `uv` (recommended)

```bash
cd backend

# Install uv (if not already installed)
pip install uv

# Create virtual environment & install dependencies
uv sync

# Copy configuration template
cp .env.example .env
# Edit .env as needed (all values have defaults — can skip for dev)

# Start the server
uv run python main.py
```

#### Option B: Using standard `venv` + `pip`

```bash
cd backend

# Create virtual environment
python -m venv .venv

# Activate virtual environment
#   Windows (PowerShell):
.venv\Scripts\Activate.ps1
#   Windows (CMD):
.venv\Scripts\activate.bat
#   Linux / macOS:
source .venv/bin/activate

# Install dependencies
pip install -e ".[dev]"

# Copy configuration template
cp .env.example .env   # (or: copy .env.example .env on Windows)

# Start the server
python main.py
```

The backend starts at `http://localhost:9000` with API docs at `http://localhost:9000/docs`.

#### Default credentials

On first startup, a default developer account is automatically created:

| Username | Password | Role |
|---|---|---|
| `admin` | `admin` | developer |

### 2. Frontend

```bash
cd frontend

# Install dependencies
pnpm install

# Start dev server
pnpm dev
```

The frontend starts at `http://localhost:5173`.

## Configuration

All configuration is centralized in `backend/.env` (see `.env.example` for the full template). Key options:

### Database

| Variable | Default | Description |
|---|---|---|
| `DATABASE_URL` | *(empty → SQLite)* | PostgreSQL URL for production, e.g. `postgresql+asyncpg://user:pass@localhost:5432/agent_platform` |

### Authentication

| Variable | Default | Description |
|---|---|---|
| `JWT_SECRET_KEY` | `agent-platform-dev-secret-...` | JWT signing secret (**change in production**) |
| `JWT_ACCESS_EXPIRE_MINUTES` | `30` | Access token TTL (minutes) |
| `JWT_REFRESH_EXPIRE_DAYS` | `7` | Refresh token TTL (days) |
| `ENABLE_PASSWORD_LOGIN` | `true` | Enable local bcrypt password login |
| `ENABLE_REGISTER` | `true` | Enable user registration (developer-only endpoint) |
| `SEED_DEFAULT_ADMIN` | `true` | Auto-create default admin on first startup |

### OAuth2.0 Password Grant Delegation

When `OAUTH_AUTH_SERVER_URL` is configured, the `POST /auth/token` endpoint delegates to an external auth server using the OAuth2.0 Password Grant flow (`grant_type=password`). On success, the user is synced to the local database and a local JWT is issued.

```env
OAUTH_AUTH_SERVER_URL=https://auth.example.com
OAUTH_CLIENT_ID=agent-platform
OAUTH_CLIENT_SECRET=your-client-secret
OAUTH_TOKEN_PATH=/oauth2/token
OAUTH_USERINFO_URL=https://auth.example.com/userinfo
```

When `OAUTH_AUTH_SERVER_URL` is empty (default), the platform uses local bcrypt password verification only.

**Login flow:**

```
POST /auth/token (username, password)
  ├─ OAUTH_AUTH_SERVER_URL set?  →  delegate to external auth server
  │     ├─ grant_type=password  →  access_token
  │     ├─ fetch userinfo
  │     ├─ upsert local user
  │     └─ issue local JWT  →  response
  └─ else / fallback  →  verify against local DB (bcrypt)
        └─ issue local JWT  →  response
```

### Sandbox Isolation

| Variable | Default | Description |
|---|---|---|
| `SANDBOX_BACKEND` | `local` | `local` / `docker` / `k8s` |

For Docker or K8s backends, install the optional dependencies:

```bash
# uv
uv sync --extra sandbox-docker
uv sync --extra sandbox-k8s

# pip
pip install -e ".[sandbox-docker]"
pip install -e ".[sandbox-k8s]"
```

## Architecture

```
┌─────────────────────────────────────────────────┐
│                   Frontend                       │
│  ┌──────────────┐    ┌──────────────────────┐   │
│  │  /admin/*    │    │  /space/*            │   │
│  │  Developer   │    │  End-User Marketplace │   │
│  └──────┬───────┘    └──────────┬───────────┘   │
│         └──────── API Client ───┘               │
│            JWT Bearer Token                      │
└─────────────────┬───────────────────────────────┘
                  │
┌─────────────────▼───────────────────────────────┐
│              Backend (FastAPI)                    │
│                                                   │
│  AuthMiddleware → AccessControl → AgentScope      │
│                                                   │
│  ┌─────────┐  ┌──────────┐  ┌────────────────┐  │
│  │ _auth/  │  │ _publish/ │  │  AgentScope    │  │
│  │ JWT+OAuth│  │ versioning│  │  core (ASGI)  │  │
│  └─────────┘  └──────────┘  └────────────────┘  │
│                                                   │
│  ┌─────────┐  ┌──────────┐                       │
│  │ _db/    │  │ _sandbox/ │                      │
│  │ SQLAlchemy│ │ Docker/K8s│                     │
│  └─────────┘  └──────────┘                       │
└───────────────────────────────────────────────────┘
```

## Development

```bash
# Backend — run with hot reload
cd backend && uv run python main.py
# (or: python main.py with venv activated)

# Frontend — run with hot reload
cd frontend && pnpm dev

# Run backend tests
cd backend && uv run pytest
# (or: pytest with venv activated)
```
