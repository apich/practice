# -*- coding: utf-8 -*-
"""The main entry point for the agent platform service.

Integrates AgentScope's create_app with platform-level extensions:
- Centralized configuration via pydantic-settings (_config.py)
- JWT auth + OAuth2.0 password grant delegation (_auth/)
- Agent publishing / versioning (_publish/)
- Sandboxed execution (_sandbox/)
"""
import os

import uvicorn
from fastapi.middleware import Middleware
from fastapi.middleware.cors import CORSMiddleware

# ── Platform configuration ───────────────────────────────────────────────────
from app.config import get_settings

# ── Platform extension modules ───────────────────────────────────────────────
from app.auth.access_control import AccessControlMiddleware
from app.auth.exceptions import register_exception_handlers
from app.auth.middleware import AuthMiddleware
from app.auth.router import router as auth_router, create_default_admin
from app.auth.security import close_security_service
from app.auth.service import close_auth_service
from app.db.engine import init_db, get_session_factory, create_tables, close_db
from app.publish.router import router as publish_router, unpublish_router
from app.sandbox.factory import create_sandbox_manager, get_sandbox_backend

from agentscope.app import create_app, SubAgentTemplate
from agentscope.app.channel import DiscordChannel, FeishuChannel
from agentscope.app.hub import ClawSkillHub, GitHubMCPHub
# from agentscope.app.message_bus import InMemoryMessageBus
from agentscope.app.message_bus import RedisMessageBus
from agentscope.app.rag.knowledge_base_manager import CollectionPerKbManager
from agentscope.app.storage import RedisStorage
from agentscope.app.workspace_manager import LocalWorkspaceManager
from agentscope.mcp import MCPClient, StdioMCPConfig, HttpMCPConfig
from agentscope.middleware import AgenticMemoryMiddleware, MiddlewareBase
from agentscope.permission import PermissionContext, PermissionMode
from agentscope.rag import QdrantStore
from agentscope.workspace import WorkspaceBase

# ── Load centralized settings ────────────────────────────────────────────────
settings = get_settings()

# ── Platform database initialization ────────────────────────────────────────
# Initialize DB at module level (not in on_event) because agentscope's
# create_app uses its own lifespan handler, which may prevent on_event
# callbacks from firing reliably.
init_db(settings)


# ── Wrap agentscope's lifespan to add platform DB initialization ───────────
# agentscope's create_app sets its own lifespan handler, which prevents
# @app.on_event("startup") from firing. We wrap the original lifespan to
# inject our async initialization (create tables, seed admin).
from contextlib import asynccontextmanager
from agentscope.app._lifespan import lifespan as _agentscope_lifespan


@asynccontextmanager
async def _platform_lifespan(app):
    """Platform lifespan that wraps agentscope's lifespan."""
    # Startup: create tables and seed default admin
    await create_tables()
    session_factory = get_session_factory()
    async with session_factory() as db:
        await create_default_admin(db)
    # Enter agentscope's lifespan
    async with _agentscope_lifespan(app) as result:
        yield result


default_mcps = [
    MCPClient(
        name="browser-use",
        mcp_config=StdioMCPConfig(
            command="npx",
            args=["@playwright/mcp@latest"],
        ),
        is_stateful=True,
    ),
]

if os.getenv("AMAP_API_KEY"):
    default_mcps.append(
        MCPClient(
            name="amap",
            mcp_config=HttpMCPConfig(
                url=f"https://mcp.amap.com/mcp?key="
                f"{os.environ['AMAP_API_KEY']}",
            ),
            is_stateful=False,
        ),
    )

storage = RedisStorage(
    host="localhost",
    port=6379,
    db=10
)

vector_store = QdrantStore(location=":memory:")


async def longterm_memory_factory(
    user_id: str,
    agent_id: str,
    session_id: str,
    workspace: WorkspaceBase,
) -> list[MiddlewareBase]:
    """Attach Markdown-file long-term memory, stored under the session's
    workspace so it is reachable through whichever backend is bound."""
    del user_id, agent_id, session_id
    return [
        AgenticMemoryMiddleware(
            workdir=workspace.workdir,
            backend=workspace.get_backend(),
        ),
    ]


app = create_app(
    storage=storage,
    # message_bus=InMemoryMessageBus(),
    # -- To use a Redis-backed message bus instead (recommended for
    # -- multi-process / production deployments), uncomment the lines
    # -- below and replace the InMemoryMessageBus() above:
    #
    # from agentscope.app.message_bus import RedisMessageBus
    message_bus=RedisMessageBus(
        host="localhost",
        port=6379,
    ),
    workspace_manager=LocalWorkspaceManager(
        basedir=settings.effective_workspace_basedir,
        # The default MCP servers that will be added into the workspace
        default_mcps=default_mcps,
    ),
    # NOTE: Sandbox mode (Docker/K8s) is configured via SANDBOX_BACKEND
    # env var. When set to 'docker' or 'k8s', the sandbox manager is
    # created and available for session-level isolation. Full integration
    # (proxying file operations through the sandbox) is a TODO.
    # See _sandbox/factory.py for configuration details.
    # Knowledge base feature — backed by an in-memory Qdrant store. The
    # CollectionPerKbManager allocates one collection per knowledge base,
    # so any embedding dimension is allowed.
    knowledge_base_manager=CollectionPerKbManager(
        storage=storage,
        vector_store=vector_store,
    ),
    # Resource hubs the UI browses under /hub. Neither needs credentials
    # of its own — an individual MCP card declares whatever key it wants
    # from the user in its ``inputs_schema``. Passing a ClawHub token
    # only raises the rate limit.
    mcp_hubs=[GitHubMCPHub()],
    skill_hubs=[ClawSkillHub(api_token=os.getenv("CLAWHUB_API_TOKEN"))],
    # Customize your own subagent templates
    custom_subagent_templates=[
        SubAgentTemplate(
            type="explorer",
            description=(
                "Read-only agents specialized in exploration tasks. It can "
                "read files but cannot modify, create, or delete them. Use "
                "this agent type when you need to investigate the codebase, "
                "understand its structure, or gather information from files "
                "to support planning—without making any changes."
            ),
            system_prompt_template="""You are {member_name}, an explorer \
agent in team '{team_name}' led by {leader_name}.

Team purpose: {team_description}

Your role: {member_description}

## Responsibilities
- Complete the exploration tasks assigned by the team leader.
- You are read-only: you may inspect files and the codebase, but you must \
never modify, create, or delete anything.

## Reporting
- Always report the task result back to {leader_name} using the TeamSay \
tool, whether the task succeeds or fails.
- Keep your private reasoning private; only share conclusions and findings \
that the leader needs.

Note: `TeamSay` is your ONLY channel to communicate with {leader_name} and \
the other team members. Any other output you produce is invisible to them, \
so anything you want them to see MUST be sent through `TeamSay`.""",
            permission_context=PermissionContext(
                # Read-only
                mode=PermissionMode.EXPLORE,
            ),
        ),
    ],
    # Long-term memory. The default PER_AGENT workspace isolation makes
    # the memory survive across sessions of the same agent.
    extra_agent_middlewares=longterm_memory_factory,
    channels=[
        DiscordChannel,
        FeishuChannel,
    ],
)

# Override agentscope's lifespan with our platform lifespan
app.router.lifespan_context = _platform_lifespan


# ── Register platform extensions on the agentscope app ─────────────────────
app.include_router(auth_router)
app.include_router(publish_router)
app.include_router(unpublish_router)


# ── Override /health to remove auth requirement ──────────────────────────────
# The agentscope health endpoint requires X-User-ID header (returns 422 if
# missing). For a liveness probe, authentication is unnecessary. We remove
# the original route first, then register our own.
from fastapi import Request as FastAPIRequest, Response as FastAPIResponse
from agentscope.app._router._schema import HealthResponse, ComponentStatus

# Remove the agentscope /health route (it depends on get_current_user_id).
# agentscope wraps routers in _IncludedRouter objects, so we clear the
# original health_router's routes list directly.
from agentscope.app._router import health_router as _health_router
_health_router.routes.clear()

_EAGER_COMPONENTS = ("storage", "message_bus", "workspace_manager")
_LIFESPAN_COMPONENTS = (
    "background_task_manager",
    "chat_run_registry",
    "scheduler_manager",
    "resource_access_service",
    "chat_service",
    "session_service",
)
_OPTIONAL_HUBS = ("mcp_hubs", "skill_hubs")


@app.get("/health", response_model=HealthResponse, tags=["health"])
async def platform_health(
    request: FastAPIRequest,
    response: FastAPIResponse,
) -> HealthResponse:
    """Health check without authentication requirement."""
    state = request.app.state
    components: dict[str, ComponentStatus] = {
        name: "ok" if getattr(state, name, None) is not None else "not_ready"
        for name in _EAGER_COMPONENTS + _LIFESPAN_COMPONENTS
    }
    for name in _OPTIONAL_HUBS:
        components[name] = "ok" if getattr(state, name, None) else "disabled"

    if getattr(state, "knowledge_base_manager", None) is None:
        components["knowledge_base"] = "disabled"
    elif getattr(state, "knowledge_base_service", None) is not None:
        components["knowledge_base"] = "ok"
    else:
        components["knowledge_base"] = "not_ready"

    ready = all(value != "not_ready" for value in components.values())
    if not ready:
        response.status_code = 503

    return HealthResponse(
        status="ok" if ready else "not_ready",
        version=request.app.version,
        components=components,
    )

# ── Global exception handlers ────────────────────────────────────────────────
register_exception_handlers(app)

# Register AccessControl BEFORE Auth so Auth is the outermost layer
# (Auth populates request.state.user, then AccessControl checks the role).
app.add_middleware(AccessControlMiddleware)
app.add_middleware(AuthMiddleware)

# CORS must be the OUTERMOST middleware (added last) so it handles
# preflight OPTIONS before Auth/AccessControl and always adds CORS
# headers to responses, even if inner BaseHTTPMiddleware misbehave.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Session-Id", "X-User-Id"],
)

# ── Sandbox configuration ───────────────────────────────────────────────────
# The sandbox manager is created at import time so it's available for
# the startup/shutdown lifecycle. When SANDBOX_BACKEND=local (default),
# this is None and LocalWorkspaceManager is used directly.
sandbox_manager = create_sandbox_manager()
if sandbox_manager:
    print(f"[sandbox] Backend: {get_sandbox_backend()} — isolated execution enabled")


@app.on_event("shutdown")
async def _shutdown_cleanup() -> None:
    """Clean up platform resources on shutdown."""
    await close_security_service()
    await close_auth_service()
    if sandbox_manager:
        await sandbox_manager.cleanup_all()
    await close_db()


if __name__ == "__main__":
    # Start the service
    uvicorn.run(
        "app.main:app",
        host=settings.app_host,
        port=settings.app_port,
        reload=settings.app_debug,
    )
