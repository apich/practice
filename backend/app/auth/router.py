"""Authentication API routes.

Endpoints:
    POST /auth/login          — JSON login (username + password)
    GET  /auth/oauth/login    — OAuth2.0 authorization URL (PKCE)
    POST /auth/callback       — OAuth2.0 callback (code → local JWT)
    GET  /auth/me             — current user info
    POST /auth/refresh        — refresh access token
    POST /auth/logout         — invalidate session (client-side token clear)
    POST /auth/register       — create a new user (developer only)

Login flow:
    When OAUTH_AUTH_SERVER_URL is configured, the /auth/login endpoint
    delegates to the external auth server using OAuth2.0 password grant
    (grant_type=password). On success, the user is synced locally and a
    local JWT is issued.

    When OAUTH_AUTH_SERVER_URL is empty (default), the endpoint falls
    back to local bcrypt password verification against the users table.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.deps import get_current_user, require_role
from app.auth.models import LoginUrlResponse, Role, User
from app.auth.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)
from app.auth.service import get_auth_service
from app.core.config import get_settings
from app.core.database import get_db

router = APIRouter(prefix="/auth", tags=["auth"])


# ── Request / response schemas ───────────────────────────────────────────────

class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=100)
    password: str = Field(min_length=1)


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user_id: str
    username: str
    role: str


class UserInfoResponse(BaseModel):
    user_id: str
    username: str
    role: str
    created_at: str | None = None


class RefreshRequest(BaseModel):
    refresh_token: str


class RegisterRequest(BaseModel):
    username: str = Field(min_length=1, max_length=100)
    password: str = Field(min_length=1)
    role: str = Field(default=Role.END_USER)

    @field_validator("role")
    @classmethod
    def validate_role(cls, v: str) -> str:
        if v not in Role.ALL:
            raise ValueError(f"Invalid role: {v}. Must be one of {Role.ALL}")
        return v


# ── OAuth2.0 Authorization Code + PKCE ───────────────────────────────────────

class OAuthCallbackRequest(BaseModel):
    code: str = Field(min_length=1)
    state: str = Field(min_length=1)


@router.get("/oauth/login", response_model=LoginUrlResponse)
async def oauth_login() -> LoginUrlResponse:
    """Generate OAuth2.0 authorization URL for Authorization Code + PKCE flow.

    The frontend redirects the user to the returned login_url.
    After login, the auth server redirects back to redirect_uri with
    code and state query parameters.
    """
    settings = get_settings()
    if not settings.is_oauth_enabled:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="OAuth2.0 is not configured",
        )

    auth_service = get_auth_service()
    result = auth_service.generate_login_url()
    return LoginUrlResponse(**result)


@router.post("/callback", response_model=TokenResponse)
async def oauth_callback(
    body: OAuthCallbackRequest,
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    """OAuth2.0 callback: exchange authorization code for local JWT.

    The frontend sends the code and state received from the auth server's
    redirect. The backend exchanges the code for an OAuth access_token,
    fetches user info, syncs the user locally, and issues a local JWT.
    """
    auth_service = get_auth_service()
    try:
        result = await auth_service.exchange_token(body.code, body.state, db)
        return TokenResponse(**result)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e


# ── Endpoints ────────────────────────────────────────────────────────────────

@router.post("/login", response_model=TokenResponse)
async def login(
    body: LoginRequest,
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    """JSON login: authenticate with username + password and return tokens.

    When OAUTH_AUTH_SERVER_URL is configured, delegates to external auth
    server via grant_type=password. Otherwise, verifies against local DB.

    Falls back to local verification if OAuth delegation fails (e.g. auth
    server unreachable) and the user exists locally.
    """
    settings = get_settings()

    # ── Try OAuth2.0 password grant delegation first ──
    if settings.is_oauth_enabled:
        auth_service = get_auth_service()
        try:
            result = await auth_service.login_with_oauth_password(
                body.username, body.password, db,
            )
            if result:
                return TokenResponse(**result)
        except ValueError as e:
            # If the error is "用户名或密码错误", don't fall back — the
            # external auth server explicitly rejected the credentials.
            msg = str(e)
            if "用户名或密码错误" in msg or "Invalid credentials" in msg:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail=msg,
                    headers={"WWW-Authenticate": "Bearer"},
                ) from e
            # For other errors (e.g. auth server unreachable), fall through
            # to local verification if available.

    # ── Local password verification ──
    if not settings.enable_password_login:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Password login is disabled",
        )

    result = await db.execute(
        select(User).where(User.username == body.username),
    )
    user = result.scalar_one_or_none()

    if not user or not user.password_hash or not verify_password(body.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return TokenResponse(
        access_token=create_access_token(user.user_id, user.username, user.role),
        refresh_token=create_refresh_token(user.user_id, user.username, user.role),
        user_id=user.user_id,
        username=user.username,
        role=user.role,
    )


@router.get("/me", response_model=UserInfoResponse)
async def me(
    user: User = Depends(get_current_user),
) -> UserInfoResponse:
    """Return the currently authenticated user's info."""
    return UserInfoResponse(
        user_id=user.user_id,
        username=user.username,
        role=user.role,
        created_at=user.created_at.isoformat() if user.created_at else None,
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh(
    body: RefreshRequest,
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    """Exchange a refresh token for a new access + refresh token pair."""
    payload = decode_token(body.refresh_token)
    if not payload or payload.get("type") != "refresh":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token",
        )

    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token",
        )

    result = await db.execute(
        select(User).where(User.user_id == user_id),
    )
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )

    return TokenResponse(
        access_token=create_access_token(user.user_id, user.username, user.role),
        refresh_token=create_refresh_token(user.user_id, user.username, user.role),
        user_id=user.user_id,
        username=user.username,
        role=user.role,
    )


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    user: User = Depends(get_current_user),
) -> None:
    """Invalidate the current session.

    JWT is stateless, so the server cannot truly revoke a token.
    This endpoint exists as a coordination point — the client is
    expected to clear its stored tokens after calling it.  Future
    token-blacklisting (e.g. via a short-lived deny list) can be
    added here without changing the contract.
    """
    return None


@router.post("/register", response_model=UserInfoResponse)
async def register(
    body: RegisterRequest,
    db: AsyncSession = Depends(get_db),
    _current: User = Depends(require_role(Role.DEVELOPER)),
) -> UserInfoResponse:
    """Create a new user account (developer-only).

    Developers use this to create end_user accounts for the terminal
    user space.
    """
    try:
        body.validate_role()
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e),
        )

    # Check for existing username
    existing = await db.execute(
        select(User).where(User.username == body.username),
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Username already exists",
        )

    user = User(
        username=body.username,
        password_hash=hash_password(body.password),
        role=body.role,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)

    return UserInfoResponse(
        user_id=user.user_id,
        username=user.username,
        role=user.role,
        created_at=user.created_at.isoformat() if user.created_at else None,
    )


# ── Default admin bootstrap ──────────────────────────────────────────────────

async def create_default_admin(db: AsyncSession) -> None:
    """Create a default developer account on first startup.

    Called from ``main.py`` during application startup. The credentials
    are taken from environment variables or default to admin/admin.
    Idempotent — skips if the admin already exists.
    """
    settings = get_settings()
    if not settings.seed_default_admin:
        return

    admin_username = settings.seed_admin_username
    admin_password = settings.seed_admin_password

    result = await db.execute(
        select(User).where(User.username == admin_username),
    )
    if result.scalar_one_or_none():
        return  # already exists

    user = User(
        username=admin_username,
        password_hash=hash_password(admin_password),
        role=Role.DEVELOPER,
    )
    db.add(user)
    await db.commit()
