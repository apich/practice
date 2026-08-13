"""Publish API routes.

Endpoints:
    POST   /publish/agent/{agent_id}           — publish / update agent
    POST   /unpublish/agent/{agent_id}         — unpublish agent
    GET    /publish/list                        — list all published (end user)
    GET    /publish/my                          — my published (developer)
    GET    /publish/{agent_id}                  — single published detail
    GET    /publish/{agent_id}/versions         — version history
    GET    /publish/{agent_id}/versions/{ver}   — version detail
    POST   /publish/{agent_id}/rollback/{ver}   — rollback to version
    POST   /publish/{agent_id}/execute          — task mode execute
"""
from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.deps import get_current_user, require_role
from app.auth.models import Role, User
from app.core.database import get_db
from app.publish import service

router = APIRouter(prefix="/publish", tags=["publish"])

# Separate router for unpublish (different prefix)
unpublish_router = APIRouter(prefix="/unpublish", tags=["publish"])


# ── Request / response schemas ───────────────────────────────────────────────

class PublishRequest(BaseModel):
    release_notes: str = Field(min_length=1)
    execution_mode: str = Field(default="chat")  # "chat" | "task"
    input_schema: dict | None = None


class ExecuteRequest(BaseModel):
    input: dict = Field(default_factory=dict)


# ── Endpoints ────────────────────────────────────────────────────────────────

@router.post("/agent/{agent_id}")
async def publish_agent(
    agent_id: str,
    body: PublishRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role(Role.DEVELOPER)),
) -> dict:
    """Publish or update an agent (developer only)."""
    return await service.publish_agent(
        db=db,
        app=request.app,
        agent_id=agent_id,
        user_id=user.user_id,
        release_notes=body.release_notes,
        execution_mode=body.execution_mode,
        input_schema=body.input_schema,
    )


@unpublish_router.post("/agent/{agent_id}")
async def unpublish_agent(
    agent_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role(Role.DEVELOPER)),
) -> dict:
    """Unpublish an agent (developer only)."""
    return await service.unpublish_agent(db, agent_id)


@router.get("/list")
async def list_published(
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    """List all published agents (visible to end users)."""
    return await service.list_published(db)


@router.get("/my")
async def list_my_published(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role(Role.DEVELOPER)),
) -> list[dict]:
    """List agents published by the current developer."""
    return await service.list_my_published(db, user.user_id)


@router.get("/{agent_id}")
async def get_published(
    agent_id: str,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Get a single published agent's details (including input_schema)."""
    return await service.get_published(db, agent_id)


@router.get("/{agent_id}/versions")
async def get_versions(
    agent_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[dict]:
    """Get version history for an agent."""
    return await service.get_versions(db, agent_id)


@router.get("/{agent_id}/versions/{version}")
async def get_version_detail(
    agent_id: str,
    version: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    """Get details of a specific version."""
    return await service.get_version_detail(db, agent_id, version)


@router.post("/{agent_id}/rollback/{version}")
async def rollback_version(
    agent_id: str,
    version: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role(Role.DEVELOPER)),
) -> dict:
    """Rollback an agent to a specific version (developer only)."""
    return await service.rollback_version(db, agent_id, version)


@router.post("/{agent_id}/execute")
async def execute_task(
    agent_id: str,
    body: ExecuteRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    """Execute a task-mode agent with form parameters.

    Creates a new session and injects the parameters as the first user
    message. Returns ``{session_id, agent_id}`` — the frontend then
    navigates to the chat or result page.
    """
    return await service.execute_task(
        db=db,
        app=request.app,
        agent_id=agent_id,
        user_id=user.user_id,
        params=body.input,
    )


@router.post("/{agent_id}/chat")
async def start_chat(
    agent_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    """Start a chat-mode session for a published agent.

    Creates a new session and records the execution for audit / analytics.
    Returns ``{session_id, agent_id}`` — the frontend then navigates to
    the chat page.
    """
    return await service.start_chat(
        db=db,
        app=request.app,
        agent_id=agent_id,
        user_id=user.user_id,
    )
