"""User model, role definitions, and auth Pydantic schemas."""
import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field
from sqlalchemy import DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Role:
    """User role constants."""
    DEVELOPER = "developer"
    END_USER = "end_user"

    ALL = (DEVELOPER, END_USER)


class User(Base):
    """Platform user stored in the relational database.

    Supports both local password login (auth_type='password') and
    OAuth2.0 login (auth_type='oauth').
    """

    __tablename__ = "users"

    user_id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )
    username: Mapped[str] = mapped_column(
        String(100),
        unique=True,
        index=True,
    )
    password_hash: Mapped[str] = mapped_column(String(255), default="")
    role: Mapped[str] = mapped_column(String(20), default=Role.DEVELOPER)

    # OAuth2.0 fields (empty for local password users)
    auth_type: Mapped[str] = mapped_column(
        String(16), default="password", server_default="password",
    )
    oauth_user_id: Mapped[Optional[str]] = mapped_column(
        String(128), nullable=True, index=True,
    )
    oauth_provider: Mapped[Optional[str]] = mapped_column(
        String(64), nullable=True,
    )
    email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    name: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=func.now(),
    )

    def to_dict(self) -> dict:
        """Serialize for API responses (never exposes password_hash)."""
        return {
            "user_id": self.user_id,
            "username": self.username,
            "role": self.role,
            "email": self.email,
            "name": self.name,
            "auth_type": self.auth_type,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


# ── Auth Pydantic schemas ────────────────────────────────────────────────────

class LoginUrlResponse(BaseModel):
    """OAuth2.0 login URL response."""
    login_url: str = Field(description="Auth server login page URL")
    state: str = Field(description="OAuth2.0 state for CSRF protection")
    redirect_uri: str = Field(description="Callback redirect URI")
