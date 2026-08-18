"""请求上下文与 FastAPI 依赖注入.

合并了原 context.py（ContextVar 鉴权上下文）和 dependencies.py
（FastAPI 依赖注入函数），因为两者紧密耦合：
- AuthContext 通过 ContextVar 在请求生命周期内传递用户信息
- get_current_user / require_role 从 request.state 和 AuthContext 解析用户

Resolves the current user from the request via:
1. JWT payload placed on ``request.state.user`` by ``AuthMiddleware``
2. ``AuthContext`` ContextVar (set by AuthMiddleware when JWT is valid)
3. ``X-User-ID`` header (dev-mode fallback — returns a lightweight
   user stub so agentscope endpoints remain usable without login)
"""

from __future__ import annotations

from contextvars import ContextVar, Token
from dataclasses import dataclass, field
import functools
from typing import Optional, TYPE_CHECKING

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import Role, User
from app.core.database import get_db

if TYPE_CHECKING:
    from app.auth.security import PermissionInfo, TokenInfo


# ── AuthContext (ContextVar) ─────────────────────────────────────────────────


@dataclass
class AuthContext:
    """当前请求的鉴权上下文.

    通过 contextvars 在请求生命周期内传递用户信息和权限，
    避免在每层函数签名中显式传递。
    """

    token: str = ""
    token_info: TokenInfo | None = None
    permissions: PermissionInfo | None = None
    extra: dict[str, str] = field(default_factory=dict)

    @property
    def user_id(self) -> str:
        """当前用户 ID."""
        if self.token_info:
            return self.token_info.user_id
        return "anonymous"

    @property
    def username(self) -> str:
        """当前用户名."""
        if self.token_info:
            return self.token_info.username or self.token_info.name or self.user_id
        return "anonymous"

    @property
    def role(self) -> str:
        """当前用户角色."""
        if self.permissions and self.permissions.roles:
            return self.permissions.roles[0]
        return ""

    @property
    def is_authenticated(self) -> bool:
        """是否已认证."""
        return self.token_info is not None and self.token_info.active

    def has_permission(self, permission: str) -> bool:
        """检查是否拥有指定权限码."""
        if self.permissions is None:
            return False
        return permission in self.permissions.permissions

    def has_role(self, role: str) -> bool:
        """检查是否拥有指定角色."""
        if self.permissions is None:
            return False
        return role in self.permissions.roles


# 请求级别的 ContextVar（使用 sentinel 模式避免 mutable default 警告）
_UNSET = object()
auth_context: ContextVar[AuthContext | object] = ContextVar(
    "auth_context",
    default=_UNSET,
)


def get_auth_context() -> AuthContext:
    """获取当前请求的鉴权上下文."""
    ctx = auth_context.get()
    if ctx is _UNSET:
        return AuthContext()
    return ctx  # type: ignore[return-value]


def set_auth_context(ctx: AuthContext) -> Token[AuthContext | object]:
    """设置当前请求的鉴权上下文.

    Returns:
        ContextVar Token，用于在请求结束后调用 ``auth_context.reset(token)`` 清理上下文。
    """
    return auth_context.set(ctx)


# ── FastAPI Dependencies ─────────────────────────────────────────────────────


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
    from app.core.config.py import get_settings
    settings = get_setting()
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
    if settings.is_production: # 生产模式则禁止X-User-ID回退机制
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="no authenticated",
            headers={"WWWAuthenticate":"Bearer"}
        )
        
    x_user_id = request.headers.get("X-User-ID", "")
    if x_user_id:
        result = await db.execute(
            select(User).where(User.user_id == x_user_id),
        )
        user = result.scalar_one_or_none()
        if user:
            return user

        result = await db.execute(
            select(User).where(User.username == x_user_id),
        )
        user = result.scalar_one_or_none()
        if user:
            return user

        # Not in the DB — create a transient dev user stub
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
    """Like ``get_current_user`` but returns ``None`` instead of 401."""
    try:
        return await get_current_user(request, db)
    except HTTPException:
        return None


def require_role(*allowed_roles: str):
    """Dependency factory that enforces one or more roles.

    Usage::

        @router.get("/admin-only", dependencies=[Depends(require_role(Role.DEVELOPER))])
        async def admin_endpoint(): ...
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


def _read_permissions_from_cookies(request: Request) -> list[str]:
    """从 Cookie 中读取用户权限集合（gzip 压缩 + base64 编码 + 分片存储）."""
    import base64
    import gzip
    import json

    count_str = request.cookies.get("user_permissions_count", "0")
    try:
        count = int(count_str)
    except ValueError:
        return []

    if count <= 0:
        return []

    chunks = []
    for i in range(count):
        chunk = request.cookies.get(f"user_permissions_{i}", "")
        if not chunk:
            return []
        chunks.append(chunk)

    try:
        encoded = "".join(chunks)
        compressed = base64.b64decode(encoded)
        data = gzip.decompress(compressed)
        return json.loads(data)
    except Exception:
        return []


def require_permissions(
    permissions: list[str],
    logic: str = "OR",
):
    """权限验证依赖工厂，支持 AND/OR 逻辑.

    从 Cookie 中读取用户权限集合，验证是否满足接口要求的权限。

    Args:
        permissions: 所需权限码列表，如 ["agent:publish", "agent:config:create"]
        logic: 多权限逻辑，"OR"（满足其一）或 "AND"（全部满足）

    Usage::

        @router.post("/agent/publish", dependencies=[Depends(require_permissions(["agent:publish"]))])
        async def publish_agent(): ...

        # AND 逻辑：必须同时拥有两个权限
        @router.post("/agent/config", dependencies=[Depends(require_permissions(["agent:create", "agent:update"], logic="AND"))])
        async def create_config(): ...
    """

    async def _checker(request: Request) -> None:
        user_permissions = _read_permissions_from_cookies(request)
        if not user_permissions:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="No permissions found. Please login first.",
            )

        user_perm_set = set(user_permissions)

        if logic == "AND":
            missing = set(permissions) - user_perm_set
            if missing:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Missing required permissions: {', '.join(missing)}",
                )
        else:  # OR
            if not (user_perm_set & set(permissions)):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Requires at least one of: {', '.join(permissions)}",
                )

    return _checker


def check_permissions(
    permissions: list[str],
    logic: str = "OR",
):
    """权限验证装饰器，支持 AND/OR 逻辑.

    从 Cookie 中读取用户权限集合，验证是否满足接口要求的权限。
    与 require_permissions（依赖工厂）功能相同，但使用装饰器语法。

    Args:
        permissions: 所需权限码列表，如 ["agent:publish", "agent:config:create"]
        logic: 多权限逻辑，"OR"（满足其一）或 "AND"（全部满足）

    Usage::

        @router.post("/agent/publish")
        @check_permissions(["agent:publish"])
        async def publish_agent(request: Request): ...

        # AND 逻辑：必须同时拥有两个权限
        @router.post("/agent/config")
        @check_permissions(["agent:create", "agent:update"], logic="AND")
        async def create_config(request: Request): ...
    """
    def decorator(func):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            # 从参数中提取 Request 对象（FastAPI 会自动注入）
            request: Request | None = kwargs.get("request") or next(
                (a for a in args if isinstance(a, Request)), None,
            )
            if request is None:
                raise RuntimeError(
                    "check_permissions 装饰器要求被装饰的函数必须包含 request: Request 参数",
                )

            user_permissions = _read_permissions_from_cookies(request)
            if not user_permissions:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="No permissions found. Please login first.",
                )

            user_perm_set = set(user_permissions)

            if logic == "AND":
                missing = set(permissions) - user_perm_set
                if missing:
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail=f"Missing required permissions: {', '.join(missing)}",
                    )
            else:  # OR
                if not (user_perm_set & set(permissions)):
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail=f"Requires at least one of: {', '.join(permissions)}",
                    )

            return await func(*args, **kwargs)
        return wrapper
    return decorator
