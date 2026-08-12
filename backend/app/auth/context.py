"""请求上下文：存储当前请求的用户信息和权限.

使用 ContextVar 在请求生命周期内传递鉴权上下文，
避免在每层函数签名中显式传递。参考 agent-archetype 的设计。
"""

from __future__ import annotations

from contextvars import ContextVar, Token
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.auth.security import PermissionInfo, TokenInfo


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
            # 返回第一个角色作为主角色
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
