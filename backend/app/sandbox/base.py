"""Sandbox manager abstract base class.

Defines the unified interface that both ``DockerSandboxManager`` and
``K8sSandboxManager`` implement. A sandbox provides:
    - ``create(session_id)``     — spin up an isolated environment
    - ``destroy(session_id)``    — tear it down
    - ``get_workspace(session_id)`` — return a workspace interface
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class SandboxInstance:
    """Represents a running sandbox instance."""
    session_id: str
    container_id: str = ""
    pod_name: str = ""
    workspace_path: str = ""
    status: str = "created"
    metadata: dict = field(default_factory=dict)


class SandboxManager(ABC):
    """Abstract base class for sandbox backends.

    Subclasses implement the create/destroy/get_workspace methods
    appropriate to their backend (Docker containers, K8s pods, etc.).
    """

    @abstractmethod
    async def create(self, session_id: str) -> SandboxInstance:
        """Create a new isolated environment for the given session."""
        ...

    @abstractmethod
    async def destroy(self, session_id: str) -> None:
        """Destroy the isolated environment for the given session."""
        ...

    @abstractmethod
    async def get_workspace(self, session_id: str) -> Optional[SandboxInstance]:
        """Return the sandbox instance for the given session, or None."""
        ...

    async def cleanup_all(self) -> None:
        """Destroy all active sandboxes. Called on application shutdown."""
        ...
