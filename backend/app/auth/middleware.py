"""JWT 认证 + 角色访问控制中间件.

合并了原 middleware.py（JWT 解码）和 access_control.py（RBAC 访问控制），
两者都是 Starlette 中间件，且注册顺序有依赖关系（JWT 先于 RBAC）。

Intercepts every request and, when an ``Authorization: Bearer <token>``
header is present, decodes the JWT and:
1. Stores the user payload on ``request.state.user`` (backward compat)
2. Sets the ``AuthContext`` ContextVar for dependency injection

AgentScope endpoints use FastAPI's dependency_overrides to extract the
user ID from request.state instead of relying on the X-User-ID header.

When no Authorization header is present the request passes through
unchanged, preserving backward compatibility with the dev-mode
``X-User-ID`` header used by the Setup page.
"""

from __future__ import annotations

from typing import Optional

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from app.auth.deps import AuthContext, auth_context, set_auth_context
from app.auth.models import Role
from app.auth.security import (
    PermissionInfo,
    TokenInfo,
    decode_token,
    extract_bearer_token,
)


# ── Path rules (access control) ──────────────────────────────────────────────
# End users are blocked from any path starting with these prefixes.
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


class AuthMiddleware(BaseHTTPMiddleware):
    """Decode JWT and populate ``request.state.user`` + ``AuthContext``.

    Does **not** reject unauthenticated requests — that is the job of
    route-level dependencies (``get_current_user`` / ``require_role``).
    This keeps public endpoints (docs, health, token) accessible and
    allows the dev-mode ``X-User-ID`` fallback to work transparently.
    """

    async def dispatch(self, request: Request, call_next):  # type: ignore[no-untyped-def]
        auth_header = request.headers.get("Authorization", "")
        token = extract_bearer_token(auth_header)

        user_payload: Optional[dict] = None
        ctx_token = None

        if token:
            payload = decode_token(token)
            if payload and payload.get("type") == "access":
                user_payload = payload

                token_info = TokenInfo(
                    active=True,
                    user_id=str(payload.get("sub", "")),
                    username=payload.get("username"),
                    expires_at=payload.get("exp"),
                    extra={"type": payload.get("type", "access")},
                )
                perm_info = PermissionInfo(
                    user_id=token_info.user_id,
                    roles=payload.get("roles", [payload.get("role", "")]),
                    permissions=payload.get("permissions", []),
                )
                ctx = AuthContext(
                    token=token,
                    token_info=token_info,
                    permissions=perm_info,
                )
                ctx_token = set_auth_context(ctx)

        # Store on request state for dependencies to read
        request.state.user = user_payload

        try:
            return await call_next(request)
        finally:
            if ctx_token is not None:
                auth_context.reset(ctx_token)


class AccessControlMiddleware(BaseHTTPMiddleware):
    """Block end_user accounts from developer-only endpoints.

    Must be registered **after** ``AuthMiddleware`` in the middleware
    stack so that ``request.state.user`` is already populated when this
    middleware runs.
    """

    async def dispatch(self, request: Request, call_next):
        path = request.url.path

        # Public paths — always pass through
        if path in PUBLIC_PATHS:
            return await call_next(request)

        # Check if the user is authenticated via JWT
        user_payload = getattr(request.state, "user", None)
        if not user_payload:
            return await call_next(request)

        role = user_payload.get("role", "")
        if role != Role.END_USER:
            return await call_next(request)

        # End user — check against developer-only prefixes
        for prefix in DEVELOPER_ONLY_PREFIXES:
            if path.startswith(prefix):
                return JSONResponse(
                    status_code=403,
                    content={"detail": "Insufficient permissions for this action"},
                )

        return await call_next(request)
