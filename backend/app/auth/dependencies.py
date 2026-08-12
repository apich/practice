"""FastAPI dependency injection for authentication and authorization.

Resolves the current user from the request via:
1. JWT payload placed on ``request.state.user`` by ``AuthMiddleware``
2. ``AuthContext`` ContextVar (set by AuthMiddleware when JWT is valid)
3. ``X-User-ID`` header (dev-mode fallback — returns a lightweight
   user stub so agentscope endpoints remain usable without login)

Provides:
- get_current_user: resolves User, raises 401 if not authenticated
- get_current_user_optional: like above but returns None instead of 401
- require_role(*roles): dependency factory for role-based access control
"""

from __future__ import annotations

from typing import Optional

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.context import get_auth_context
from app.auth.models import Role, User
from app.db.engine import get_db


async def get_current_user(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> User:
    """Resolve the current user from the request.

    Tries (in order):
    1. JWT payload placed on ``request.state.user`` by ``AuthMiddleware``
    2. ``X-User-ID`` header (dev-mode fallback — returns a lightweight
       user stub so agentscope endpoints remain usable without login)

    Raises 401 if neither is available.
    """
    # 1 — JWT path
    user_payload: Optional[dict] = getattr(request.state, "user", None)
    if user_payload:
        user_id = user_payload.get("sub")
        if user_id:
            result = await db.execute(
                select(User).where(User.user_id == user_id),
            )
            user = result.scalar_one_or_none()
            if user:
                return user
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # 2 — X-User-ID fallback (dev mode / backward compatibility)
    x_user_id = request.headers.get("X-User-ID", "")
    if x_user_id:
        # Look up by username — the Setup page stores a username, not a
        # uuid, in localStorage. If found, return the real record.
        result = await db.execute(
            select(User).where(User.username == x_user_id),
        )
        user = result.scalar_one_or_none()
        if user:
            return user

        # Not in the DB — create a transient dev user stub so the
        # request proceeds without forcing a login. This preserves the
        # zero-setup dev experience.
        return User(
            user_id=x_user_id,
            username=x_user_id,
            password_hash="",
            role=Role.DEVELOPER,
        )

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Not authenticated",
        headers={"WWW-Authenticate": "Bearer"},
    )


async def get_current_user_optional(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> Optional[User]:
    """Like ``get_current_user`` but returns ``None`` instead of 401.

    Useful for endpoints that behave differently for authenticated vs
    anonymous users (e.g. listing public agents vs personalised lists).
    """
    try:
        return await get_current_user(request, db)
    except HTTPException:
        return None


def require_role(*allowed_roles: str):
    """Dependency factory that enforces one or more roles.

    Usage::

        @router.get("/admin-only", dependencies=[Depends(require_role(Role.DEVELOPER))])
        async def admin_endpoint(): ...

    Or to receive the user::

        @router.get("/admin-only")
        async def admin_endpoint(user: User = Depends(require_role(Role.DEVELOPER))): ...
    """

    async def _checker(
        user: User = Depends(get_current_user),
    ) -> User:
        if user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Requires role: {', '.join(allowed_roles)}",
            )
        return user

    return _checker
