"""Sandbox workspace manager.

Wraps a ``SandboxManager`` to provide a workspace-like interface that
agentscope can use in place of ``LocalWorkspaceManager``. When the
sandbox backend is ``local``, this module is not used — agentscope's
own ``LocalWorkspaceManager`` runs directly.

When a sandbox backend (Docker/K8s) is active:
    1. Session creation → sandbox.create(session_id) spins up the env
    2. Agent tool calls are routed into the sandbox
    3. Session end → sandbox.destroy(session_id) tears it down
"""
import logging
from typing import Optional

from app.sandbox.base import SandboxInstance, SandboxManager

logger = logging.getLogger(__name__)


class SandboxWorkspaceManager:
    """Adapter that connects a SandboxManager to the session lifecycle.

    This is not a full ``WorkspaceBase`` implementation — it manages
    the sandbox lifecycle and delegates actual file operations to the
    sandbox's internal environment. In a future iteration, this could
    implement ``WorkspaceBase`` fully by proxying file operations via
    ``docker exec`` or ``kubectl exec``.
    """

    def __init__(self, sandbox_manager: SandboxManager):
        self.sandbox = sandbox_manager

    async def on_session_create(self, session_id: str) -> SandboxInstance:
        """Called when a new session is created. Spins up the sandbox."""
        logger.info(f"Creating sandbox for session {session_id}")
        return await self.sandbox.create(session_id)

    async def on_session_destroy(self, session_id: str) -> None:
        """Called when a session is destroyed. Tears down the sandbox."""
        logger.info(f"Destroying sandbox for session {session_id}")
        await self.sandbox.destroy(session_id)

    async def get_sandbox(self, session_id: str) -> Optional[SandboxInstance]:
        """Get the sandbox instance for a session."""
        return await self.sandbox.get_workspace(session_id)

    async def cleanup_all(self) -> None:
        """Destroy all active sandboxes (e.g. on app shutdown)."""
        await self.sandbox.cleanup_all()
