"""认证服务：本地密码登录 + OAuth2.0 登录.

参考 agent-archetype 的 AuthService 设计：
1. 本地密码登录 — 直接用 bcrypt 校验本地 users 表
2. OAuth2.0 密码模式委托 — 向外部鉴权服务发起 grant_type=password 请求，
   获取 access_token 后请求 userinfo 端点，同步用户到本地并签发本地 JWT
3. OAuth2.0 Authorization Code + PKCE — 前端重定向到鉴权系统登录，
   回调后交换 code 获取 token，同步用户并签发本地 JWT

所有登录方式最终都签发统一的本地 JWT，后续请求校验链路一致。
"""

from __future__ import annotations

import hashlib
import secrets
import time
from typing import Any
from urllib.parse import urlencode

import httpx
import jwt
from cachetools import TTLCache
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import Role, User
from app.auth.security import hash_password
from app.core.config import Settings, get_settings
from app.core.database import get_session_factory


# 默认角色与权限
DEFAULT_ROLES = [Role.DEVELOPER]
DEFAULT_PERMISSIONS = [
    "agent:chat",
    "agent:session:create",
    "agent:session:list",
    "agent:config:create",
    "agent:config:update",
    "agent:config:delete",
]

# OAuth state 存储的 TTL（秒）：超过此时间未完成回调的 state 自动过期
_OAUTH_STATE_TTL = 600  # 10 分钟


class AuthService:
    """认证服务.

    提供：
    - 本地密码登录（bcrypt 校验本地 users 表）
    - OAuth2.0 密码模式委托（向外部鉴权服务验证，同步用户，签发本地 JWT）
    - OAuth2.0 Authorization Code + PKCE（前端重定向登录，回调交换 token）
    - 用户注册
    """

    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()
        # state -> code_verifier (PKCE)，使用 TTLCache 自动过期
        self._state_store: TTLCache[str, str] = TTLCache(
            maxsize=10000,
            ttl=_OAUTH_STATE_TTL,
        )
        self._http_client: httpx.AsyncClient | None = None

    async def _get_http_client(self) -> httpx.AsyncClient:
        """获取 HTTP 客户端单例."""
        if self._http_client is None or self._http_client.is_closed:
            self._http_client = httpx.AsyncClient(timeout=httpx.Timeout(10.0))
        return self._http_client

    async def close(self) -> None:
        """关闭 HTTP 客户端."""
        if self._http_client and not self._http_client.is_closed:
            await self._http_client.aclose()

    # ===== JWT 签发 =====

    def _resolve_oauth_role(self, info: dict[str, Any]) -> str:
        """根据统一认证系统的 roleMap 决定本地角色.

        匹配逻辑：取用户 roleMap 的所有 key，与 .env 中配置的
        role_developer_ids / role_end_user_ids 比对。
        优先判断 developer，未命中任何映射默认 end_user。
        """
        settings = self._settings
        role_map = info.get("roleMap", {})
        user_role_ids = set(role_map.keys()) if role_map else set()

        developer_ids = {
            s.strip() for s in settings.role_developer_ids.split(",") if s.strip()
        }
        end_user_ids = {
            s.strip() for s in settings.role_end_user_ids.split(",") if s.strip()
        }

        if developer_ids and user_role_ids & developer_ids:
            return Role.DEVELOPER
        if end_user_ids and user_role_ids & end_user_ids:
            return Role.END_USER
        # 未配置映射或未命中，默认 end_user
        return Role.END_USER

    def _generate_jwt_token(self, user: User) -> dict[str, Any]:
        """为用户签发本地 JWT Token（access + refresh）.

        Returns:
            包含 access_token / refresh_token / user 信息的字典
        """
        now = int(time.time())
        access_expire = 1  # TODO: 测试用，正式环境改回 self._settings.jwt_access_expire_minutes
        refresh_expire = self._settings.jwt_refresh_expire_days * 24 * 60  # 分钟

        access_payload = {
            "sub": user.user_id,
            "username": user.username,
            "role": user.role,
            "roles": [user.role],
            "permissions": DEFAULT_PERMISSIONS,
            "auth_type": getattr(user, "auth_type", "password"),
            "iat": now,
            "exp": now + access_expire * 60,
            "iss": "agent-platform",
            "type": "access",
        }
        refresh_payload = {
            "sub": user.user_id,
            "username": user.username,
            "role": user.role,
            "roles": [user.role],
            "permissions": DEFAULT_PERMISSIONS,
            "iat": now,
            "exp": now + refresh_expire * 60,
            "iss": "agent-platform",
            "type": "refresh",
        }

        access_token = jwt.encode(
            access_payload,
            self._settings.jwt_secret_key,
            algorithm=self._settings.jwt_algorithm,
        )
        refresh_token = jwt.encode(
            refresh_payload,
            self._settings.jwt_secret_key,
            algorithm=self._settings.jwt_algorithm,
        )

        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer",
            "user_id": user.user_id,
            "username": user.username,
            "role": user.role,
        }

    # ===== OAuth2.0 密码模式委托 =====

    async def _exchange_password_token(
        self,
        username: str,
        password: str,
    ) -> dict[str, Any]:
        """通过 OAuth2 密码模式向认证服务换取 access_token.

        使用 grant_type=password 将用户名/密码发送给认证服务的
        token 端点，验证通过后返回 access_token。

        Args:
            username: 用户名
            password: 密码

        Returns:
            OAuth token 响应数据（含 access_token 等）

        Raises:
            ValueError: 认证失败或认证服务不可达
        """
        token_url = f"{self._settings.oauth_auth_server_url}{self._settings.oauth_token_path}"
        data = {
            "grant_type": "password",
            "username": username,
            "password": password,
            "client_id": self._settings.oauth_client_id,
            "scope": " ".join(self._settings.oauth_scopes_list),
        }

        if self._settings.oauth_client_secret:
            data["client_secret"] = self._settings.oauth_client_secret

        client = await self._get_http_client()
        try:
            response = await client.post(
                token_url,
                data=data,
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 401:
                raise ValueError("用户名或密码错误") from e
            raise ValueError(f"Authentication failed: {e.response.status_code}") from e
        except httpx.RequestError as e:
            raise ValueError("Unable to reach auth server") from e

    async def _fetch_oauth_userinfo(
        self,
        access_token: str,
    ) -> dict[str, Any]:
        """用 OAuth access_token 请求鉴权系统的 userinfo 端点.

        Args:
            access_token: OAuth access_token

        Returns:
            用户信息字典

        Raises:
            ValueError: 用户信息获取失败
        """
        userinfo_url = self._settings.oauth_userinfo_url
        if not userinfo_url:
            # 未配置 userinfo URL，返回 token 中的基本信息
            return {
                "user_id": "oauth-user",
                "username": "oauth_user",
            }

        client = await self._get_http_client()
        try:
            response = await client.get(
                userinfo_url,
                headers={"Authorization": f"Bearer {access_token}"},
            )
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            raise ValueError(f"Fetch userinfo failed: {e.response.status_code}") from e
        except httpx.RequestError as e:
            raise ValueError("Unable to reach auth server") from e

    async def _fetch_oauth_permissions(
        self,
        access_token: str,
    ) -> list[str]:
        """用 OAuth access_token 请求鉴权系统的 /permissions 端点.

        Returns:
            权限标识符列表，如 ["user:create", "role:update", ...]
        """
        permissions_url = self._settings.oauth_permissions_url
        if not permissions_url:
            return []

        client = await self._get_http_client()
        try:
            response = await client.get(
                permissions_url,
                headers={"Authorization": f"Bearer {access_token}"},
            )
            response.raise_for_status()
            result = response.json()
            if isinstance(result.get("data"), list):
                return result["data"]
            return []
        except (httpx.HTTPStatusError, httpx.RequestError):
            return []

    async def _sync_oauth_user(
        self,
        oauth_info: dict[str, Any],
        db: AsyncSession,
    ) -> User:
        """在本地 users 表中 upsert OAuth 用户.

        策略：
        - 根据 oauth_user_id + oauth_provider 查找本地用户
        - 存在则更新 name/email 等信息
        - 不存在则创建新用户（auth_type='oauth'）

        兼容两种 userinfo 响应格式：
        - 扁平结构：{ "user_id"/"sub": ..., "username": ..., ... }
        - 嵌套结构：{ "status": 200, "data": { "userId": ..., ... } }
        """
        # 解包嵌套响应
        if "data" in oauth_info and isinstance(oauth_info["data"], dict):
            info = oauth_info["data"]
        else:
            info = oauth_info

        # 提取用户唯一标识，兼容多种字段名
        oauth_user_id = str(
            info.get("user_id")
            or info.get("userId")
            or info.get("sub")
            or info.get("id")
            or ""
        )
        if not oauth_user_id:
            raise ValueError("OAuth userinfo missing user_id")

        oauth_provider = info.get("provider", "default")
        username = (
            info.get("username")
            or info.get("preferred_username")
            or f"oauth_{oauth_user_id}"
        )
        email = info.get("email")
        name = info.get("name") or info.get("userAlias") or info.get("alias") or username

        # 按 oauth_user_id + provider 查找
        stmt = select(User).where(
            User.oauth_user_id == oauth_user_id,
            User.oauth_provider == oauth_provider,
        )
        result = await db.execute(stmt)
        user = result.scalar_one_or_none()

        if user is not None:
            # 已存在，同步基本信息和角色
            user.email = email
            user.name = name
            user.role = self._resolve_oauth_role(info)
            await db.commit()
            await db.refresh(user)
            return user

        # 根据统一认证系统的角色决定本地角色
        role = self._resolve_oauth_role(info)

        # 检查 username 是否被常规登录用户占用
        stmt_username = select(User).where(User.username == username)
        result_username = await db.execute(stmt_username)
        if result_username.scalar_one_or_none() is not None:
            username = f"{username}_{oauth_user_id[:8]}"

        # 创建新用户
        user = User(
            username=username,
            password_hash="",
            role=role,
            auth_type="oauth",
            oauth_user_id=oauth_user_id,
            oauth_provider=oauth_provider,
            email=email,
            name=name,
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)
        return user

    async def login_with_oauth_password(
        self,
        username: str,
        password: str,
        db: AsyncSession,
    ) -> dict[str, Any] | None:
        """通过 OAuth2.0 密码模式登录.

        Args:
            username: 用户名
            password: 密码
            db: 数据库会话

        Returns:
            JWT Token 信息字典，或 None（OAuth 未启用时）

        Raises:
            ValueError: 认证失败
        """
        if not self._settings.is_oauth_enabled:
            return None

        # 1. OAuth2 密码模式换取 access_token
        oauth_token = await self._exchange_password_token(username, password)

        # 2. 获取用户信息
        oauth_user_info = await self._fetch_oauth_userinfo(oauth_token["access_token"])

        # 3. 同步用户到本地
        user = await self._sync_oauth_user(oauth_user_info, db)

        # 4. 获取用户权限集合
        permissions = await self._fetch_oauth_permissions(oauth_token["access_token"])

        # 5. 签发本地 JWT，附带权限数据
        token_data = self._generate_jwt_token(user)
        token_data["permissions"] = permissions
        return token_data

    # ===== OAuth2.0 Authorization Code + PKCE =====

    def generate_login_url(self) -> dict[str, str]:
        """生成 OAuth2.0 授权 URL（Authorization Code + PKCE）.

        Returns:
            包含 login_url / state / redirect_uri 的字典
        """
        # PKCE: 生成 code_verifier 和 code_challenge
        code_verifier = secrets.token_urlsafe(64)
        code_challenge = hashlib.sha256(code_verifier.encode()).hexdigest()

        # state 用于 CSRF 防护
        state = secrets.token_urlsafe(32)

        # 存储 state -> code_verifier 映射
        self._state_store[state] = code_verifier

        # 构造授权 URL
        params = {
            "response_type": "code",
            "client_id": self._settings.oauth_client_id,
            "redirect_uri": self._settings.oauth_redirect_uri,
            "scope": " ".join(self._settings.oauth_scopes_list),
            "state": state,
            "code_challenge": code_challenge,
            "code_challenge_method": "S256",
        }
        auth_url = (
            f"{self._settings.oauth_auth_server_url}"
            f"{self._settings.oauth_authorize_path}?{urlencode(params)}"
        )

        return {
            "login_url": auth_url,
            "state": state,
            "redirect_uri": self._settings.oauth_redirect_uri,
        }

    async def exchange_token(
        self,
        code: str,
        state: str,
        db: AsyncSession,
    ) -> dict[str, Any]:
        """OAuth2.0 回调：换取 Token → 同步用户 → 签发本地 JWT.

        Args:
            code: OAuth2.0 authorization code
            state: OAuth2.0 state 参数
            db: 数据库会话

        Returns:
            本地 JWT Token 字典

        Raises:
            ValueError: state 无效、token 交换失败或用户信息获取失败
        """
        # 1. 验证 state
        code_verifier = self._state_store.pop(state, None)
        if code_verifier is None:
            raise ValueError("Invalid or expired state parameter")

        # 2. 用 code 换取 OAuth access_token
        oauth_token = await self._exchange_oauth_token(code, code_verifier)

        # 3. 用 access_token 获取用户信息
        oauth_user_info = await self._fetch_oauth_userinfo(oauth_token["access_token"])

        # 4. 在本地 users 表中 upsert 用户
        user = await self._sync_oauth_user(oauth_user_info, db)

        # 5. 签发本地 JWT
        return self._generate_jwt_token(user)

    async def _exchange_oauth_token(
        self,
        code: str,
        code_verifier: str,
    ) -> dict[str, Any]:
        """用 authorization code 换取 OAuth access_token."""
        token_url = (
            f"{self._settings.oauth_auth_server_url}"
            f"{self._settings.oauth_token_path}"
        )
        data = {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": self._settings.oauth_redirect_uri,
            "client_id": self._settings.oauth_client_id,
            "code_verifier": code_verifier,
        }
        if self._settings.oauth_client_secret:
            data["client_secret"] = self._settings.oauth_client_secret

        client = await self._get_http_client()
        try:
            response = await client.post(
                token_url,
                data=data,
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            raise ValueError(f"Token exchange failed: {e.response.status_code}") from e
        except httpx.RequestError as e:
            raise ValueError("Unable to reach auth server") from e

    # ===== 用户注册 =====

    async def register(
        self,
        username: str,
        password: str,
        role: str = Role.END_USER,
        db: AsyncSession | None = None,
    ) -> User:
        """用户注册.

        Args:
            username: 用户名
            password: 密码
            role: 角色
            db: 数据库会话

        Returns:
            创建的 User 对象

        Raises:
            ValueError: 注册关闭或用户名已存在
        """
        if not self._settings.enable_register:
            raise ValueError("Registration is disabled")

        if db is None:
            factory = get_session_factory()
            async with factory() as session:
                return await self.register(username, password, role, session)

        # 检查用户名是否已存在
        stmt = select(User).where(User.username == username)
        result = await db.execute(stmt)
        if result.scalar_one_or_none() is not None:
            raise ValueError("用户名已存在")

        # 创建用户
        user = User(
            username=username,
            password_hash=hash_password(password),
            role=role,
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)
        return user


# ===== 全局单例 =====
_auth_service: AuthService | None = None


def get_auth_service() -> AuthService:
    """获取认证服务单例."""
    global _auth_service
    if _auth_service is None:
        _auth_service = AuthService()
    return _auth_service


async def close_auth_service() -> None:
    """关闭认证服务."""
    global _auth_service
    if _auth_service is not None:
        await _auth_service.close()
        _auth_service = None
