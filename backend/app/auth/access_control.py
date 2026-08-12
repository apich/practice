"""Role-based API access control middleware.

Restricts ``end_user`` accounts to a whitelist of endpoints needed for
chatting with and executing published agents. Developer accounts and
unauthenticated requests (dev-mode ``X-User-ID`` fallback) are allowed
through unchecked — the latter preserves the zero-setup dev experience.

Must be registered **before** ``AuthMiddleware`` in the middleware
stack so that ``request.state.user`` is already populated when this
middleware runs.
"""
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from app.auth.models import Role

# ── Path rules ───────────────────────────────────────────────────────────────
# End users are blocked from any path starting with these prefixes.
# Everything else is allowed (sessions, chat, publish read/execute, etc.).
DEVELOPER_ONLY_PREFIXES: tuple[str, ...] = (
    "/agent",          # create / update / delete agents
    "/credential",     # credential management
    "/mcp",            # MCP management
    "/skill",          # skill management
    "/knowledge",      # knowledge base management
    "/knowledge_bases",
    "/schedule",       # schedule management
    "/channel",        # channel management
    "/hub",            # resource hubs
    "/embedding-model",
    "/model",          # model listing / config
    "/tts-model",
    "/auth/register",  # user registration
    "/publish/my",     # developer's own publications
    "/publish/agent",  # POST publish
    "/unpublish",      # unpublish
)

# Paths that are always public (no role check needed).
PUBLIC_PATHS: frozenset[str] = frozenset({
    "/",
    "/health",
    "/docs",
    "/redoc",
    "/openapi.json",
    "/auth/token",
    "/auth/refresh",
})


class AccessControlMiddleware(BaseHTTPMiddleware):
    """Block end_user accounts from developer-only endpoints."""

    async def dispatch(self, request: Request, call_next):
        # Public paths — always pass through
        path = request.url.path
        if path in PUBLIC_PATHS:
            return await call_next(request)

        # Check if the user is authenticated via JWT
        user_payload = getattr(request.state, "user", None)
        if not user_payload:
            # No JWT — dev-mode X-User-ID fallback or unauthenticated.
            # Allow through; route-level dependencies handle 401 if needed.
            return await call_next(request)

        role = user_payload.get("role", "")
        if role != Role.END_USER:
            # Developer or unknown role — allow all
            return await call_next(request)

        # End user — check against developer-only prefixes
        for prefix in DEVELOPER_ONLY_PREFIXES:
            if path.startswith(prefix):
                return JSONResponse(
                    status_code=403,
                    content={"detail": "Insufficient permissions for this action"},
                )

        return await call_next(request)
