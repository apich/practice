"""Agent publication and version models.

Three tables:
    agent_publications — one row per agent, tracks current publish state
    agent_versions     — one row per publish event, stores config snapshots
    agent_executions   — one row per end-user execution, for audit / analytics
"""
import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class AgentPublication(Base):
    """Publish record for an agent — one row per agent.

    Tracks whether the agent is currently published, its latest version
    number, and the execution mode (chat vs task) + input schema for
    task mode.
    """

    __tablename__ = "agent_publications"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )
    agent_id: Mapped[str] = mapped_column(
        String(100), unique=True, index=True,
    )
    agent_name: Mapped[str] = mapped_column(String(255))
    agent_description: Mapped[str] = mapped_column(Text, default="")
    published: Mapped[bool] = mapped_column(Boolean, default=True)
    current_version: Mapped[str] = mapped_column(String(20), default="")
    published_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime, nullable=True,
    )
    unpublished_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime, nullable=True,
    )
    published_by: Mapped[str] = mapped_column(String(36))
    execution_mode: Mapped[str] = mapped_column(
        String(10), default="chat",
    )  # "chat" | "task"    
    input_schema: Mapped[Optional[dict]] = mapped_column(
        JSON, nullable=True,
    )  # JSON Schema for task mode
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now(),
    )


class AgentVersion(Base):
    """Version history — one row per publish event.

    Stores a snapshot of the agent configuration at publish time so the
    version can be rolled back to.
    """

    __tablename__ = "agent_versions"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )
    publication_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("agent_publications.id"),
        index=True,
    )
    agent_id: Mapped[str] = mapped_column(
        String(100), index=True,
    )
    version: Mapped[str] = mapped_column(String(20))  # short SHA256 hash
    release_notes: Mapped[str] = mapped_column(Text)
    execution_mode: Mapped[str] = mapped_column(String(10), default="chat")
    input_schema: Mapped[Optional[dict]] = mapped_column(
        JSON, nullable=True,
    )
    agent_snapshot: Mapped[Optional[dict]] = mapped_column(
        JSON, nullable=True,
    )  # Agent config snapshot for rollback
    published_by: Mapped[str] = mapped_column(String(36))
    published_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(),
    )
    is_current: Mapped[bool] = mapped_column(Boolean, default=True)


class AgentExecution(Base):
    """End-user execution record — one row per published-agent execution.

    Covers both chat-mode and task-mode invocations.  Used for audit
    trails and usage analytics.
    """

    __tablename__ = "agent_executions"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )
    agent_id: Mapped[str] = mapped_column(
        String(100), index=True,
    )
    user_id: Mapped[str] = mapped_column(
        String(36), index=True,
    )  # end-user who triggered the execution
    session_id: Mapped[str] = mapped_column(
        String(100),
    )  # session created for this execution
    execution_mode: Mapped[str] = mapped_column(
        String(10), default="chat",
    )  # "chat" | "task"
    input_params: Mapped[Optional[dict]] = mapped_column(
        JSON, nullable=True,
    )  # the form parameters submitted by the user (task mode only)
    executed_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(),
    )
