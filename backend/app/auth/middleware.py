"""JWT authentication middleware.

Intercepts every request and, when an ``Authorization: Bearer <token>``
header is present, decodes the JWT and:
1. Stores the user payload on ``request.state.user`` (backward compat)
2. Sets the ``AuthContext`` ContextVar for dependency injection
3. Injects / overrides the ``X-User-ID`` header in the ASGI scope so that
   agentscope's own endpoints — which read ``X-User-ID`` directly — see
   the authenticated user's id.

When no Authorization header is present the request passes through
unchanged, preserving backward compatibility with the dev-mode
``X-User-ID`` header used by the Setup page.

Reference: agent-archetype's AuthMiddleware, adapted for agent-platform's
hybrid auth model (JWT + dev-mode X-User-ID fallback).
"""

from __future__ import annotations

from typing import Optional

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from app.auth.context import AuthContext, auth_context, set_auth_context
from app.auth.security import decode_token, extract_bearer_token


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

                # Set AuthContext for dependency injection
                from app.auth.security import PermissionInfo, TokenInfo

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

        # Inject X-User-ID into the ASGI scope so agentscope sees it.
        # Headers in the scope are a list of (bytes, bytes) tuples.
        if user_payload:
            user_id = user_payload.get("sub", "")
            scope = request.scope
            existing_headers = scope.get("headers", [])
            # Remove any existing x-user-id and append the JWT-derived one
            filtered = [
                (k, v) for k, v in existing_headers if k != b"x-user-id"
            ]
            filtered.append((b"x-user-id", user_id.encode("utf-8")))
            scope["headers"] = filtered

        try:
            return await call_next(request)
        finally:
            # Clean up ContextVar to prevent context leakage
            if ctx_token is not None:
                auth_context.reset(ctx_token)
