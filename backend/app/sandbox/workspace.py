"""Sandbox workspace manager.

Wraps a ``SandboxManager`` and a ``WorkspaceManagerBase`` delegate to
provide a workspace manager that integrates sandbox lifecycle with
AgentScope's workspace system.

When the sandbox backend is ``local``, this module is not used —
AgentScope's own ``LocalWorkspaceManager`` runs directly.

When a sandbox backend (Docker/K8s) is active:
    1. ``get_workspace`` → creates sandbox if needed, returns workspace
    2. Agent tool calls are routed into the sandbox
    3. ``close`` → destroys the sandbox for that workspace
    4. ``close_all`` → tears down all active sandboxes
"""
import logging
from typing import Optional

from agentscope.app.workspace_manager import WorkspaceManagerBase
from agentscope.app.workspace_manager import LocalWorkspaceManager
from agentscope.workspace import WorkspaceBase

from app.sandbox.base import SandboxInstance, SandboxManager

logger = logging.getLogger(__name__)


class SandboxWorkspaceManager(WorkspaceManagerBase):
    """Workspace manager that integrates sandbox lifecycle with
    AgentScope's workspace system.

    Delegates workspace ID assignment and directory operations to an
    internal ``LocalWorkspaceManager``, while managing sandbox
    lifecycle (create/destroy) around workspace access.

    When ``get_workspace`` is called for a workspace that doesn't yet
    have a sandbox, one is created automatically. The sandbox is
    destroyed when ``close`` is called for that workspace.
    """

    def __init__(
        self,
        sandbox_manager: SandboxManager,
        delegate: LocalWorkspaceManager,
    ) -> None:
        """Bind the sandbox manager and the delegate workspace manager.

        Args:
            sandbox_manager: The sandbox backend (Docker/K8s).
            delegate: A ``LocalWorkspaceManager`` used for workspace ID
                assignment and as a fallback for workspace operations.
        """
        super().__init__()
        self._sandbox = sandbox_manager
        self._delegate = delegate
        # Track which workspace_ids have active sandboxes
        self._active_sandboxes: dict[str, SandboxInstance] = {}

    async def get_workspace(
        self,
        user_id: str,
        agent_id: str,
        session_id: str,
        workspace_id: str | None = None,
    ) -> WorkspaceBase:
        """Return a workspace, creating a sandbox if needed.

        Delegates to the internal ``LocalWorkspaceManager`` for the
        actual workspace object, and ensures a sandbox is running for
        the workspace. The sandbox can be used for isolated execution
        in future iterations (e.g. proxying tool calls via
        ``docker exec`` / ``kubectl exec``).
        """
        workspace = await self._delegate.get_workspace(
            user_id, agent_id, session_id, workspace_id,
        )

        # Ensure a sandbox is running for this workspace
        resolved_wid = workspace.workspace_id
        if resolved_wid not in self._active_sandboxes:
            try:
                sandbox = await self._sandbox.create(resolved_wid)
                self._active_sandboxes[resolved_wid] = sandbox
                logger.info(
                    "Created sandbox for workspace %s (session=%s)",
                    resolved_wid, session_id,
                )
            except Exception:
                logger.warning(
                    "Failed to create sandbox for workspace %s, "
                    "falling back to local execution",
                    resolved_wid,
                    exc_info=True,
                )

        return workspace

    async def close(self, workspace_id: str) -> None:
        """Close a workspace and destroy its sandbox."""
        # Destroy the sandbox if one exists for this workspace
        sandbox = self._active_sandboxes.pop(workspace_id, None)
        if sandbox is not None:
            try:
                await self._sandbox.destroy(workspace_id)
                logger.info(
                    "Destroyed sandbox for workspace %s", workspace_id,
                )
            except Exception:
                logger.warning(
                    "Failed to destroy sandbox for workspace %s",
                    workspace_id,
                    exc_info=True,
                )

        # Delegate to local workspace manager for cleanup
        await self._delegate.close(workspace_id)

    async def close_all(self) -> None:
        """Close all workspaces and destroy all sandboxes."""
        # Destroy all active sandboxes
        for workspace_id in list(self._active_sandboxes):
            try:
                await self._sandbox.destroy(workspace_id)
            except Exception:
                logger.warning(
                    "Failed to destroy sandbox for workspace %s",
                    workspace_id,
                    exc_info=True,
                )
        self._active_sandboxes.clear()

        # Delegate to local workspace manager
        await self._delegate.close_all()

    async def on_session_create(self, session_id: str) -> SandboxInstance:
        """Explicitly create a sandbox for a session.

        This can be called from session creation hooks to pre-provision
        the sandbox before the first workspace access.
        """
        logger.info("Creating sandbox for session %s", session_id)
        return await self._sandbox.create(session_id)

    async def on_session_destroy(self, session_id: str) -> None:
        """Explicitly destroy a sandbox for a session.

        This can be called from session destruction hooks to tear down
        the sandbox eagerly.
        """
        logger.info("Destroying sandbox for session %s", session_id)
        await self._sandbox.destroy(session_id)

    async def get_sandbox(
        self, session_id: str,
    ) -> Optional[SandboxInstance]:
        """Get the sandbox instance for a session."""
        return await self._sandbox.get_workspace(session_id)
