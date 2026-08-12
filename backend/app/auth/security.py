"""安全模块：JWT Token 校验、密码哈希、权限缓存.

参考 agent-archetype 的安全服务设计：
- TokenInfo / PermissionInfo: Pydantic 模型，描述 Token 解析结果
- SecurityService: 带 TTLCache 的 Token 校验服务单例
- 保留函数式 API（hash_password / verify_password / create_access_token 等）
  确保向后兼容

两种登录方式（本地密码登录、OAuth2.0 密码模式委托）在认证通过后
都签发本地 JWT，后续请求统一通过本地 JWT 校验。
"""

from __future__ import annotations

import hashlib
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING, Any, Optional

import jwt
from cachetools import TTLCache
from pydantic import BaseModel, Field

if TYPE_CHECKING:
    from app.config import Settings


# ── Password hashing (bcrypt) ────────────────────────────────────────────────
# Using bcrypt directly to avoid passlib compatibility issues with bcrypt >= 4.1
import bcrypt as _bcrypt


def hash_password(password: str) -> str:
    """Hash a plaintext password using bcrypt.

    Returns the hash as a UTF-8 string.
    """
    return _bcrypt.hashpw(password.encode("utf-8"), _bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    """Verify a plaintext password against its bcrypt hash."""
    return _bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))


# ── Pydantic 模型 ─────────────────────────────────────────────────────────────


class TokenInfo(BaseModel):
    """Token 解析后的用户信息."""

    active: bool = Field(description="Token 是否有效")
    user_id: str = Field(description="用户唯一标识")
    username: str | None = Field(default=None, description="用户名")
    email: str | None = Field(default=None, description="邮箱")
    name: str | None = Field(default=None, description="显示名称")
    scope: str | None = Field(default=None, description="授权范围")
    expires_at: int | None = Field(default=None, description="过期时间戳（秒）")
    client_id: str | None = Field(default=None, description="客户端 ID")
    extra: dict[str, Any] = Field(default_factory=dict, description="扩展字段")


class PermissionInfo(BaseModel):
    """用户权限信息."""

    user_id: str = Field(description="用户唯一标识")
    roles: list[str] = Field(default_factory=list, description="角色列表")
    permissions: list[str] = Field(default_factory=list, description="权限码列表")


# ── JWT Token 工具函数（向后兼容） ───────────────────────────────────────────


def _get_settings() -> Settings:
    from app.config import get_settings
    return get_settings()


def create_access_token(user_id: str, username: str, role: str) -> str:
    """Create a short-lived access token.

    向后兼容函数：使用集中式配置中的 secret_key / algorithm / expire_minutes。
    """
    settings = _get_settings()
    expire = datetime.now(timezone.utc) + timedelta(
        minutes=settings.jwt_access_expire_minutes,
    )
    payload = {
        "sub": user_id,
        "username": username,
        "role": role,
        "roles": [role],
        "permissions": [],
        "exp": expire,
        "iat": int(datetime.now(timezone.utc).timestamp()),
        "iss": "agent-platform",
        "type": "access",
    }
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def create_refresh_token(user_id: str, username: str, role: str) -> str:
    """Create a long-lived refresh token.

    向后兼容函数：使用集中式配置中的 secret_key / algorithm / expire_days。
    """
    settings = _get_settings()
    expire = datetime.now(timezone.utc) + timedelta(
        days=settings.jwt_refresh_expire_days,
    )
    payload = {
        "sub": user_id,
        "username": username,
        "role": role,
        "roles": [role],
        "permissions": [],
        "exp": expire,
        "iat": int(datetime.now(timezone.utc).timestamp()),
        "iss": "agent-platform",
        "type": "refresh",
    }
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def decode_token(token: str) -> Optional[dict]:
    """Decode and verify a JWT token. Returns None if invalid/expired.

    向后兼容函数。
    """
    settings = _get_settings()
    try:
        return jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
            issuer="agent-platform",
        )
    except jwt.PyJWTError:
        return None


def extract_bearer_token(authorization_header: str) -> Optional[str]:
    """Extract the token from an ``Authorization: Bearer <token>`` header."""
    if not authorization_header:
        return None
    parts = authorization_header.split(None, 1)
    if len(parts) != 2 or parts[0].lower() != "bearer":
        return None
    return parts[1].strip()


# ── SecurityService: 带 TTLCache 的 Token 校验服务 ───────────────────────────


class SecurityService:
    """安全服务.

    统一通过本地 JWT 校验 Token，权限信息直接从 JWT payload 中提取。
    保留缓存以减少重复解码。参考 agent-archetype 的 SecurityService。
    """

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._token_cache: TTLCache[str, TokenInfo] = TTLCache(
            maxsize=10000,
            ttl=settings.oauth_token_cache_ttl,
        )
        self._permission_cache: TTLCache[str, PermissionInfo] = TTLCache(
            maxsize=10000,
            ttl=settings.oauth_token_cache_ttl,
        )

    async def validate_token(self, token: str) -> TokenInfo:
        """校验 Bearer Token（本地 JWT）.

        Args:
            token: JWT Token 字符串

        Returns:
            TokenInfo: Token 信息

        Raises:
            AuthenticationError: Token 无效或过期
        """
        # 使用 token 的 SHA256 摘要做缓存 key，避免完整 JWT 字符串长期驻留内存
        cache_key = hashlib.sha256(token.encode()).hexdigest()

        # 检查缓存
        cached = self._token_cache.get(cache_key)
        if cached is not None:
            return cached

        # JWT 本地验证
        info = self._decode_jwt(token)

        if not info.active:
            from app.auth.exceptions import AuthenticationError
            raise AuthenticationError("Token is invalid or expired")

        self._token_cache[cache_key] = info
        return info

    def _decode_jwt(self, token: str) -> TokenInfo:
        """解码并验证 JWT Token.

        Args:
            token: JWT Token 字符串

        Returns:
            TokenInfo: Token 信息（active=False 表示验证失败）

        Raises:
            AuthenticationError: Token 格式不是 JWT
        """
        parts = token.split(".")
        if len(parts) != 3:
            from app.auth.exceptions import AuthenticationError
            raise AuthenticationError("Invalid token format")

        try:
            payload: dict[str, Any] = jwt.decode(
                token,
                self._settings.jwt_secret_key,
                algorithms=[self._settings.jwt_algorithm],
                issuer="agent-platform",
            )
        except jwt.ExpiredSignatureError:
            return TokenInfo(active=False, user_id="")
        except jwt.PyJWTError:
            return TokenInfo(active=False, user_id="")

        return TokenInfo(
            active=True,
            user_id=str(payload.get("sub") or ""),
            username=payload.get("username"),
            email=payload.get("email"),
            name=payload.get("name"),
            scope=payload.get("scope"),
            expires_at=payload.get("exp"),
            client_id=self._settings.oauth_client_id,
            extra={
                "type": payload.get("type", "access"),
                "auth_type": payload.get("auth_type", "password"),
            },
        )

    async def get_user_permissions(self, token: str, user_id: str) -> PermissionInfo:
        """获取用户权限.

        权限信息已嵌入 JWT payload 中，直接解析。
        缓存键使用 token 的 SHA256 摘要（与 token 缓存一致）。
        """
        cache_key = hashlib.sha256(token.encode()).hexdigest()
        cached = self._permission_cache.get(cache_key)
        if cached is not None:
            return cached

        try:
            payload: dict[str, Any] = jwt.decode(
                token,
                self._settings.jwt_secret_key,
                algorithms=[self._settings.jwt_algorithm],
                issuer="agent-platform",
            )
        except jwt.PyJWTError as e:
            from app.auth.exceptions import AuthenticationError
            raise AuthenticationError("Token is invalid or expired") from e

        perm_info = PermissionInfo(
            user_id=user_id,
            roles=payload.get("roles", []),
            permissions=payload.get("permissions", []),
        )
        self._permission_cache[cache_key] = perm_info
        return perm_info

    def invalidate_cache(self, token: str | None = None) -> None:
        """清除缓存.

        Args:
            token: 指定 Token 则只清除该 Token 的缓存，None 则清除全部
        """
        if token:
            cache_key = hashlib.sha256(token.encode()).hexdigest()
            self._token_cache.pop(cache_key, None)
            self._permission_cache.pop(cache_key, None)
        else:
            self._token_cache.clear()
            self._permission_cache.clear()


# ===== 全局单例 =====
_security_service: SecurityService | None = None


async def get_security_service() -> SecurityService:
    """获取安全服务单例."""
    global _security_service
    if _security_service is None:
        from app.config import get_settings
        _security_service = SecurityService(get_settings())
    return _security_service


async def close_security_service() -> None:
    """关闭安全服务."""
    global _security_service
    if _security_service is not None:
        _security_service = None
