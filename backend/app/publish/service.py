"""Publish service: business logic for agent publication and versioning.

All functions are async and take an ``AsyncSession`` as the first
argument. They raise ``HTTPException`` on error so they can be called
directly from route handlers.
"""
import hashlib
import json
from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import HTTPException, status
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.publish.models import AgentPublication, AgentVersion

# ── Version number generation ────────────────────────────────────────────────

def generate_version(
    agent_id: str,
    release_notes: str,
    timestamp: datetime,
) -> str:
    """Generate a 7-character version hash from publish content.

    Uses SHA256 of (agent_id + release_notes + timestamp) and takes the
    first 7 hex chars, e.g. ``a3f2c8d``.
    """
    content = f"{agent_id}:{release_notes}:{timestamp.isoformat()}"
    return hashlib.sha256(content.encode()).hexdigest()[:7]


# ── Agent snapshot helpers ───────────────────────────────────────────────────

async def _fetch_agent_snapshot(app: Any, agent_id: str, user_id: str) -> dict:
    """Fetch the current agent configuration from storage.

    Directly accesses the storage layer instead of making an HTTP call,
    since AgentScope doesn't expose a GET /agent/{id} endpoint.
    """
    storage = getattr(app.state, "storage", None)
    if storage is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Storage service not available",
        )

    record = await storage.get_agent(user_id, agent_id)
    if record is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Agent {agent_id} not found",
        )

    # Convert AgentRecord to a dict format expected by callers
    data = record.data
    return {
        "name": data.name,
        "system_prompt": data.system_prompt,
        "context_config": data.context_config.model_dump() if data.context_config else None,
        "react_config": data.react_config.model_dump() if data.react_config else None,
        "invite_config": data.invite_config.model_dump() if data.invite_config else None,
    }


# ── Publish / unpublish ──────────────────────────────────────────────────────

async def publish_agent(
    db: AsyncSession,
    app: Any,
    agent_id: str,
    user_id: str,
    release_notes: str,
    execution_mode: str,
    input_schema: Optional[dict] = None,
) -> dict:
    """Publish or update an agent.

    Creates a new ``AgentPublication`` on first publish, or updates the
    existing one and adds a new ``AgentVersion`` on subsequent publishes.
    Returns ``{version, agent_id, published_at}``.
    """
    if not release_notes.strip():
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="release_notes is required and must not be empty",
        )

    if execution_mode not in ("chat", "task"):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="execution_mode must be 'chat' or 'task'",
        )

    if execution_mode == "task" and not input_schema:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="input_schema is required for task mode",
        )

    # Fetch agent info from agentscope
    agent_data = await _fetch_agent_snapshot(app, agent_id, user_id)
    agent_name = agent_data.get("name", agent_id)
    agent_description = agent_data.get("system_prompt", "")[:500]

    now = datetime.utcnow()
    version = generate_version(agent_id, release_notes, now)

    # Snapshot the agent config for rollback
    agent_snapshot = {
        "name": agent_name,
        "system_prompt": agent_data.get("system_prompt", ""),
        "context_config": agent_data.get("context_config"),
        "react_config": agent_data.get("react_config"),
        "invite_config": agent_data.get("invite_config"),
    }

    # Check for existing publication
    result = await db.execute(
        select(AgentPublication).where(AgentPublication.agent_id == agent_id),
    )
    publication = result.scalar_one_or_none()

    if publication:
        # Update existing publication
        publication.agent_name = agent_name
        publication.agent_description = agent_description
        publication.published = True
        publication.current_version = version
        publication.published_at = now
        publication.unpublished_at = None
        publication.published_by = user_id
        publication.execution_mode = execution_mode
        publication.input_schema = input_schema
        publication.updated_at = now

        # Mark old current version as not current
        await db.execute(
            update(AgentVersion)
            .where(
                AgentVersion.publication_id == publication.id,
                AgentVersion.is_current == True,  # noqa: E712
            )
            .values(is_current=False),
        )
    else:
        # Create new publication
        publication = AgentPublication(
            agent_id=agent_id,
            agent_name=agent_name,
            agent_description=agent_description,
            published=True,
            current_version=version,
            published_at=now,
            published_by=user_id,
            execution_mode=execution_mode,
            input_schema=input_schema,
        )
        db.add(publication)
        await db.flush()  # get the id

    # Create version record
    version_record = AgentVersion(
        publication_id=publication.id,
        agent_id=agent_id,
        version=version,
        release_notes=release_notes,
        execution_mode=execution_mode,
        input_schema=input_schema,
        agent_snapshot=agent_snapshot,
        published_by=user_id,
        published_at=now,
        is_current=True,
    )
    db.add(version_record)
    await db.commit()

    return {
        "version": version,
        "agent_id": agent_id,
        "published_at": now.isoformat(),
    }


async def unpublish_agent(
    db: AsyncSession,
    agent_id: str,
) -> dict:
    """Unpublish an agent (set published=False)."""
    result = await db.execute(
        select(AgentPublication).where(AgentPublication.agent_id == agent_id),
    )
    publication = result.scalar_one_or_none()

    if not publication:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Agent {agent_id} is not published",
        )

    publication.published = False
    publication.unpublished_at = datetime.utcnow()
    await db.commit()

    return {"agent_id": agent_id, "published": False}


# ── Query endpoints ──────────────────────────────────────────────────────────

async def list_published(db: AsyncSession) -> list[dict]:
    """List all published agents (for end users)."""
    result = await db.execute(
        select(AgentPublication).where(
            AgentPublication.published == True,  # noqa: E712
        ),
    )
    pubs = result.scalars().all()
    return [_publication_to_dict(p) for p in pubs]


async def list_my_published(db: AsyncSession, user_id: str) -> list[dict]:
    """List agents published by the current user (for developers)."""
    result = await db.execute(
        select(AgentPublication).where(
            AgentPublication.published_by == user_id,
        ),
    )
    pubs = result.scalars().all()
    return [_publication_to_dict(p) for p in pubs]


async def get_published(db: AsyncSession, agent_id: str) -> dict:
    """Get a single published agent's details."""
    result = await db.execute(
        select(AgentPublication).where(
            AgentPublication.agent_id == agent_id,
            AgentPublication.published == True,  # noqa: E712
        ),
    )
    pub = result.scalar_one_or_none()
    if not pub:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Agent {agent_id} is not published",
        )
    return _publication_to_dict(pub)


async def get_versions(db: AsyncSession, agent_id: str) -> list[dict]:
    """Get version history for an agent."""
    result = await db.execute(
        select(AgentVersion)
        .where(AgentVersion.agent_id == agent_id)
        .order_by(AgentVersion.published_at.desc()),
    )
    versions = result.scalars().all()
    return [_version_to_dict(v) for v in versions]


async def get_version_detail(
    db: AsyncSession,
    agent_id: str,
    version: str,
) -> dict:
    """Get details of a specific version."""
    result = await db.execute(
        select(AgentVersion).where(
            AgentVersion.agent_id == agent_id,
            AgentVersion.version == version,
        ),
    )
    v = result.scalar_one_or_none()
    if not v:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Version {version} not found for agent {agent_id}",
        )
    return _version_to_dict(v, include_detail=True)


# ── Rollback ─────────────────────────────────────────────────────────────────

async def rollback_version(
    db: AsyncSession,
    agent_id: str,
    version: str,
) -> dict:
    """Rollback an agent to a specific version."""
    # Find the target version
    result = await db.execute(
        select(AgentVersion).where(
            AgentVersion.agent_id == agent_id,
            AgentVersion.version == version,
        ),
    )
    target = result.scalar_one_or_none()
    if not target:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Version {version} not found for agent {agent_id}",
        )

    # Find the publication
    pub_result = await db.execute(
        select(AgentPublication).where(
            AgentPublication.agent_id == agent_id,
        ),
    )
    pub = pub_result.scalar_one_or_none()
    if not pub:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Agent {agent_id} is not published",
        )

    # Mark all versions as not current, then mark target as current
    await db.execute(
        update(AgentVersion)
        .where(AgentVersion.publication_id == pub.id)
        .values(is_current=False),
    )
    target.is_current = True

    # Update publication to reflect the rolled-back version
    pub.current_version = target.version
    pub.execution_mode = target.execution_mode
    pub.input_schema = target.input_schema
    pub.updated_at = datetime.utcnow()

    await db.commit()

    return {
        "agent_id": agent_id,
        "version": version,
        "rolled_back": True,
    }


# ── Task mode execution ──────────────────────────────────────────────────────

def _format_task_parameters(params: dict) -> str:
    """Format task parameters into a structured user message.

    The parameters become the first user message sent to the agent,
    so the agent receives them as context without modifying its
    system_prompt.
    """
    lines = ["以下是任务参数："]
    for key, value in params.items():
        if isinstance(value, (dict, list)):
            lines.append(f"- {key}: {json.dumps(value, ensure_ascii=False)}")
        else:
            lines.append(f"- {key}: {value}")
    lines.append("")
    lines.append("请根据以上参数执行任务。")
    return "\n".join(lines)


async def execute_task(
    db: AsyncSession,
    app: Any,
    agent_id: str,
    user_id: str,
    params: dict,
) -> dict:
    """Execute a task-mode agent with form parameters.

    Creates a new session and sends the formatted parameters as the
    first user message. Returns ``{session_id, agent_id}``.
    """
    from httpx import ASGITransport, AsyncClient

    # Verify the agent is published in task mode
    pub = await get_published(db, agent_id)
    if pub["execution_mode"] != "task":
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="This agent is not in task mode",
        )

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://internal",
    ) as client:
        headers = {"X-User-ID": user_id, "Content-Type": "application/json"}

        # 1 — Create a session
        create_resp = await client.post(
            "/sessions/",
            json={"agent_id": agent_id},
            headers=headers,
        )
        if create_resp.status_code != 200:
            raise HTTPException(
                status_code=create_resp.status_code,
                detail=f"Failed to create session: {create_resp.text}",
            )
        session_id = create_resp.json().get("session_id")

        # 2 — Send the formatted parameters as the first user message
        message_text = _format_task_parameters(params)
        chat_resp = await client.post(
            "/chat/",
            json={
                "agent_id": agent_id,
                "session_id": session_id,
                "input": {
                    "role": "user",
                    "content": [{"type": "text", "text": message_text}],
                },
            },
            headers=headers,
        )
        if chat_resp.status_code != 200:
            raise HTTPException(
                status_code=chat_resp.status_code,
                detail=f"Failed to start chat: {chat_resp.text}",
            )

    return {"session_id": session_id, "agent_id": agent_id}


# ── Serialization helpers ────────────────────────────────────────────────────

def _publication_to_dict(pub: AgentPublication) -> dict:
    return {
        "id": pub.id,
        "agent_id": pub.agent_id,
        "agent_name": pub.agent_name,
        "agent_description": pub.agent_description,
        "published": pub.published,
        "current_version": pub.current_version,
        "execution_mode": pub.execution_mode,
        "input_schema": pub.input_schema,
        "published_at": pub.published_at.isoformat() if pub.published_at else None,
        "unpublished_at": pub.unpublished_at.isoformat() if pub.unpublished_at else None,
        "published_by": pub.published_by,
    }


def _version_to_dict(v: AgentVersion, include_detail: bool = False) -> dict:
    d = {
        "id": v.id,
        "version": v.version,
        "release_notes": v.release_notes,
        "execution_mode": v.execution_mode,
        "published_by": v.published_by,
        "published_at": v.published_at.isoformat() if v.published_at else None,
        "is_current": v.is_current,
    }
    if include_detail:
        d["input_schema"] = v.input_schema
        d["agent_snapshot"] = v.agent_snapshot
    return d
