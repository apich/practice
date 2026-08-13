# Agent Platform

> English | [中文](README.md)

An AI Agent building and distribution platform based on AgentScope 2.0. Developers can build and publish agents, while end users can browse and use published agents in the marketplace.

**Core flow:** Build → Publish → Browse → Use

- **Developers**: Build and configure AI agents in the Admin space, then publish them to the marketplace
- **End users**: Browse published agents in the Space space and use them via chat or structured forms

The platform includes built-in authentication (JWT / OAuth2.0 password grant), role-based access control, agent versioning, knowledge base management, MCP / Skill Hub, channel adapters, scheduled tasks, and sandboxed execution.

## Structure

```
agent-platform/
├── backend/                    # Python backend (FastAPI + AgentScope)
│   ├── app/
│   │   ├── main.py             # Entry point — integrates AgentScope create_app + platform extensions
│   │   ├── storage_channel.py  # AsyncSQLAlchemyStorage channel support patch
│   │   ├── core/               # Core infrastructure
│   │   │   ├── config.py       # Centralized configuration (pydantic-settings)
│   │   │   ├── database.py     # SQLAlchemy async engine & session management
│   │   │   └── exceptions.py   # Global exception handlers
│   │   ├── auth/               # Authentication & authorization
│   │   │   ├── router.py       # /auth/* endpoints (login, register, refresh)
│   │   │   ├── service.py      # AuthService — OAuth2.0 password grant delegation
│   │   │   ├── security.py     # JWT utilities, SecurityService (TTLCache)
│   │   │   ├── middleware.py   # AuthMiddleware + AccessControlMiddleware
│   │   │   ├── deps.py         # AuthContext dependency injection
│   │   │   └── models.py       # User ORM model, Role constants
│   │   ├── publish/            # Agent publishing & versioning
│   │   ├── sandbox/            # Docker / K8s sandbox managers
│   │   │   ├── base.py         # Sandbox base class
│   │   │   ├── docker_manager.py
│   │   │   ├── k8s_manager.py
│   │   │   ├── factory.py      # Sandbox factory
│   │   │   └── workspace.py    # SandboxWorkspaceManager
│   │   └── ...
│   ├── .env.example            # Configuration template
│   └── pyproject.toml          # Python dependencies
├── frontend/                   # React frontend (Vite + TailwindCSS)
│   ├── src/
│   │   ├── pages/              # Page modules
│   │   │   ├── chat/           # Admin chat & agent debugging
│   │   │   ├── space/          # End-user marketplace, launchpad, conversation
│   │   │   ├── knowledge/      # Knowledge base management
│   │   │   ├── mcp/            # MCP Hub browsing & management
│   │   │   ├── skill/          # Skill Hub browsing & management
│   │   │   ├── channel/        # Channel adapters (Feishu / Discord)
│   │   │   ├── schedule/       # Scheduled tasks
│   │   │   ├── credential/     # Credential management
│   │   │   ├── login/          # Login page
│   │   │   ├── profile/        # User profile
│   │   │   └── setup/          # Initial setup
│   │   ├── components/         # UI components, auth guards, dialogs, tours
│   │   ├── hooks/              # useAuth, useChat, useAgents, etc.
│   │   └── api/                # API client with JWT support (18 modules)
│   └── package.json
└── Plan.md                     # Development plan & architecture
```

## Prerequisites

| Dependency | Version | Purpose |
|---|---|---|
| Python | >= 3.11 | Backend runtime |
| Node.js | >= 18 | Frontend build |
| pnpm | >= 8 | Frontend package manager |
| Redis | >= 6 | Message bus (SSE event streams, distributed locks) |

> SQLite is used by default for the platform database (zero setup). AgentScope storage and platform storage share the same database. PostgreSQL is optional for production.

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
uv run python -m app.main
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
python -m app.main
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

### Application

| Variable | Default | Description |
|---|---|---|
| `APP_HOST` | `0.0.0.0` | Listen address |
| `APP_PORT` | `9000` | Listen port |
| `APP_DEBUG` | `true` | Debug mode (enables hot reload) |
| `CORS_ORIGINS` | `http://localhost:5173,http://localhost:3000` | Allowed CORS origins (comma-separated) |

### Database

| Variable | Default | Description |
|---|---|---|
| `DATABASE_URL` | *(empty → SQLite)* | PostgreSQL URL for production, e.g. `postgresql+asyncpg://user:pass@localhost:5432/agent_platform` |
| `DATABASE_ECHO` | `false` | Print SQL statements |
| `DATABASE_POOL_SIZE` | `10` | Connection pool size |
| `DATABASE_MAX_OVERFLOW` | `20` | Max pool overflow |
| `DATABASE_POOL_RECYCLE` | `3600` | Connection recycle time (seconds) |

### Redis

| Variable | Default | Description |
|---|---|---|
| `REDIS_HOST` | `localhost` | Redis host |
| `REDIS_PORT` | `6379` | Redis port |
| `REDIS_DB` | `10` | Redis database number |
| `REDIS_PASSWORD` | *(empty)* | Redis password |

### Authentication

| Variable | Default | Description |
|---|---|---|
| `JWT_SECRET_KEY` | `agent-platform-dev-secret-...` | JWT signing secret (**change in production**) |
| `JWT_ACCESS_EXPIRE_MINUTES` | `30` | Access token TTL (minutes) |
| `JWT_REFRESH_EXPIRE_DAYS` | `7` | Refresh token TTL (days) |
| `ENABLE_PASSWORD_LOGIN` | `true` | Enable local bcrypt password login |
| `ENABLE_REGISTER` | `true` | Enable user registration (developer-only endpoint) |
| `SEED_DEFAULT_ADMIN` | `true` | Auto-create default admin on first startup |
| `SEED_ADMIN_USERNAME` | `admin` | Default admin username |
| `SEED_ADMIN_PASSWORD` | `admin` | Default admin password (**change in production**) |

### OAuth2.0 Password Grant Delegation

When `OAUTH_AUTH_SERVER_URL` is configured, the `POST /auth/token` endpoint delegates to an external auth server using the OAuth2.0 Password Grant flow (`grant_type=password`). On success, the user is synced to the local database and a local JWT is issued.

```env
OAUTH_AUTH_SERVER_URL=https://auth.example.com
OAUTH_CLIENT_ID=agent-platform
OAUTH_CLIENT_SECRET=your-client-secret
OAUTH_SCOPES=openid profile email
OAUTH_TOKEN_PATH=/oauth2/token
OAUTH_USERINFO_URL=https://auth.example.com/userinfo
OAUTH_TOKEN_CACHE_TTL=300
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

### LLM Model

| Variable | Default | Description |
|---|---|---|
| `MODEL_API_KEY` | *(empty)* | Model API key |
| `MODEL_API_BASE` | `https://api.openai.com/v1` | Model API base URL |
| `MODEL_NAME` | `gpt-4o` | Default model name |

### Vector Store (Qdrant)

| Variable | Default | Description |
|---|---|---|
| `QDRANT_LOCATION` | `:memory:` | In-memory mode (lost on restart); set to a persistent path or remote URL for production |

### Sandbox Isolation

| Variable | Default | Description |
|---|---|---|
| `SANDBOX_BACKEND` | `local` | `disabled` / `local` / `docker` / `k8s` |

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
┌──────────────────────────────────────────────────────────────┐
│                    Frontend (React + Vite)                     │
│                                                               │
│  ┌────────────────────────────┐  ┌─────────────────────────┐ │
│  │  /admin/*                  │  │  /space/*               │ │
│  │  Developer Space           │  │  End-User Marketplace   │ │
│  │  ├─ chat      Agent debug  │  │  ├─ Browse agents       │ │
│  │  ├─ knowledge KB mgmt      │  │  ├─ Chat / form usage   │ │
│  │  ├─ mcp       MCP Hub     │  │  └─ Task results        │ │
│  │  ├─ skill     Skill Hub   │  │                          │ │
│  │  ├─ channel   Adapters    │  │                          │ │
│  │  ├─ schedule  Tasks       │  │                          │ │
│  │  └─ credential Creds      │  │                          │ │
│  └────────────┬───────────────┘  └────────────┬────────────┘ │
│               └──────── API Client ───────────┘              │
│                  JWT Bearer Token + i18n                      │
└──────────────────────────┬───────────────────────────────────┘
                           │
┌──────────────────────────▼───────────────────────────────────┐
│                  Backend (FastAPI + AgentScope)                │
│                                                                │
│  CORS → AuthMiddleware → AccessControl → AgentScope Routes     │
│                                                                │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────────────┐ │
│  │ auth/    │ │ publish/ │ │ sandbox/ │ │ core/            │ │
│  │JWT+OAuth │ │Versioning│ │Docker/K8s│ │ config + database│ │
│  └──────────┘ └──────────┘ └──────────┘ └──────────────────┘ │
│                                                                │
│  AgentScope Integration:                                       │
│  ┌──────────────┐ ┌──────────────┐ ┌────────────────────────┐│
│  │ Storage      │ │ Message Bus  │ │ Knowledge Base         ││
│  │ (SQLAlchemy) │ │ (Redis)      │ │ (Qdrant + CollectionPer││
│  │              │ │              │ │  KbManager)            ││
│  └──────────────┘ └──────────────┘ └────────────────────────┘│
│  ┌──────────────┐ ┌──────────────┐ ┌────────────────────────┐│
│  │ MCP Hubs     │ │ Skill Hubs   │ │ Channels               ││
│  │ (GitHub)     │ │ (Claw)       │ │ (Feishu / Discord)     ││
│  └──────────────┘ └──────────────┘ └────────────────────────┘│
└────────────────────────────────────────────────────────────────┘
```

## Development

```bash
# Backend — run with hot reload
cd backend && uv run python -m app.main
# (or: python -m app.main with venv activated)

# Frontend — run with hot reload
cd frontend && pnpm dev

# Run backend tests
cd backend && uv run pytest
# (or: pytest with venv activated)
```
