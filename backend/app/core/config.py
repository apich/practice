"""应用集中式配置模块.

使用 pydantic-settings 从环境变量 / .env 文件加载全部配置，
所有配置项均有默认值，可通过 .env 文件或环境变量覆盖。

参考 agent-archetype 的实现模式。
"""

from __future__ import annotations

from functools import lru_cache
import os
from typing import Literal

from pydantic import computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """应用配置.

    通过 pydantic-settings 自动从 .env 文件和环境变量加载，
    所有字段有默认值，无需显式传参即可实例化。
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ===== 应用 =====
    app_name: str = "Agent Platform"
    app_env: Literal["development", "staging", "production"] = "development"
    app_debug: bool = True
    app_host: str = "0.0.0.0"
    app_port: int = 9000

    # ===== CORS =====
    cors_origins: str = "http://localhost:5173,http://localhost:3000"

    # ===== 数据库 =====
    # 默认 SQLite (零配置开发)；生产环境设置 DATABASE_URL 指向 PostgreSQL
    database_url: str = ""
    database_echo: bool = False
    database_pool_size: int = 10
    database_max_overflow: int = 20
    database_pool_recycle: int = 3600

    # ===== JWT / 常规登录 =====
    jwt_secret_key: str = "agent-platform-dev-secret-key-change-in-production"  # noqa: S105
    jwt_algorithm: str = "HS256"
    jwt_access_expire_minutes: int = 30
    jwt_refresh_expire_days: int = 7
    # 是否启用本地密码登录
    enable_password_login: bool = True
    # 是否启用用户注册（developer 可注册 end_user）
    enable_register: bool = True
    # 是否在首次启动时自动创建默认 admin 账户
    seed_default_admin: bool = True
    # 默认 admin 账户的用户名和密码（生产环境务必修改）
    seed_admin_username: str = "admin"
    seed_admin_password: str = "admin"  # noqa: S105

    # ===== OAuth2.0 =====
    # 当配置了 oauth_auth_server_url 时，login 端点会委托外部鉴权服务
    # 进行身份验证，验证通过后同步用户并签发本地 JWT。
    # 留空则使用本地 bcrypt 密码校验。
    oauth_auth_server_url: str = ""
    oauth_client_id: str = "agent-platform"
    oauth_client_secret: str = ""
    oauth_redirect_uri: str = "http://localhost:5173/auth/callback"
    oauth_scopes: str = "openid profile email"
    # OAuth2.0 端点路径（相对于 oauth_auth_server_url）
    oauth_authorize_path: str = "/oauth2/authorize"
    oauth_token_path: str = "/oauth2/token"  # noqa: S105
    # OAuth2.0 userinfo 端点 URL（完整 URL，可选）
    oauth_userinfo_url: str = ""
    # Token / 权限缓存 TTL（秒）
    oauth_token_cache_ttl: int = 300

    # ===== AgentScope / 模型 =====
    model_api_key: str = ""
    model_api_base: str = "https://api.openai.com/v1"
    model_name: str = "gpt-4o"

    # ===== 向量存储 (Qdrant) =====
    # 默认 :memory: 表示内存模式（重启后数据丢失）
    # 生产环境配置为持久化路径（如 ./qdrant_data）或远程地址（如 http://localhost:6333）
    qdrant_location: str = ":memory:"

    # ===== 工作空间 =====
    workspace_basedir: str = ""

    # ===== 沙盒 =====
    # 后端选择: disabled | local | docker | k8s
    sandbox_backend: Literal["disabled", "local", "docker", "k8s"] = "local"

    # ===== Redis =====
    redis_host: str = "localhost"
    redis_port: int = 6379
    redis_db: int = 10
    redis_password: str = ""

    # ===== 日志 =====
    log_level: str = "DEBUG"

    @computed_field  # type: ignore[prop-deprecated]
    @property
    def cors_origins_list(self) -> list[str]:
        """将逗号分隔的 CORS 来源转为列表."""
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @computed_field  # type: ignore[prop-deprecated]
    @property
    def oauth_scopes_list(self) -> list[str]:
        """将逗号分隔的 scopes 转为列表."""
        return [scope.strip() for scope in self.oauth_scopes.split(",") if scope.strip()]

    @property
    def is_production(self) -> bool:
        """是否为生产环境."""
        return self.app_env == "production"

    @property
    def is_oauth_enabled(self) -> bool:
        """是否启用了 OAuth2.0 外部鉴权委托."""
        return bool(self.oauth_auth_server_url)

    @property
    def effective_workspace_basedir(self) -> str:
        """实际使用的工作空间根目录.

        若 workspace_basedir 为空，回退到 app/ 上的 workspaces 目录。
        """
        if self.workspace_basedir:
            return self.workspace_basedir
        return os.path.join(
            os.path.dirname(
                os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            ),
            "workspaces",
        )

    @property
    def effective_database_url(self) -> str:
        """实际使用的数据库 URL.

        若 database_url 为空，回退到本地 SQLite（零配置开发）。
        """
        if self.database_url:
            return self.database_url
        return "sqlite+aiosqlite:///" + os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            "agent_platform.db",
        )


@lru_cache
def get_settings() -> Settings:
    """获取全局配置单例.

    使用 lru_cache 确保整个应用生命周期内只实例化一次。
    """
    return Settings()
