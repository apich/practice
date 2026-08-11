# Agent Platform

A dual-role agent development platform based on AgentScope.

## Structure

```
agent-platform/
├── service/          # Python backend (FastAPI)
│   └── main.py
├── web_ui/           # Frontend + Node.js backend
│   ├── frontend/     # React (Vite)
│   └── backend/      # Express.js
└── pyproject.toml    # Python dependencies
```

## Quick Start

```bash
# Backend
uv sync
uv run python service/main.py

# Frontend
cd web_ui && pnpm install && pnpm dev
```
