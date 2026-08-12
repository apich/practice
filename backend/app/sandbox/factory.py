"""Sandbox factory: creates the appropriate manager based on configuration.

Selection is via the ``SANDBOX_BACKEND`` environment variable:
    - ``local``  (default) — no isolation, uses LocalWorkspaceManager
    - ``docker`` — Docker containers via DockerSandboxManager
    - ``k8s``    — Kubernetes pods via K8sSandboxManager
"""
import os
from typing import Optional

from app.sandbox.base import SandboxManager


def get_sandbox_backend() -> str:
    """Return the configured sandbox backend name."""
    return os.getenv("SANDBOX_BACKEND", "local").lower()


def create_sandbox_manager() -> Optional[SandboxManager]:
    """Create a sandbox manager based on the SANDBOX_BACKEND env var.

    Returns ``None`` when ``SANDBOX_BACKEND=local`` (no isolation),
    signalling that the caller should use ``LocalWorkspaceManager``.
    """
    backend = get_sandbox_backend()

    if backend == "local":
        return None

    if backend == "docker":
        from app.sandbox.docker_manager import DockerSandboxManager
        return DockerSandboxManager(
            image=os.getenv("SANDBOX_IMAGE", "agent-platform-sandbox:latest"),
            resource_limits={
                "cpu": int(os.getenv("SANDBOX_CPU", "1")),
                "memory": os.getenv("SANDBOX_MEMORY", "512m"),
                "disk": os.getenv("SANDBOX_DISK", "100m"),
            },
            network=os.getenv("SANDBOX_NETWORK"),  # None = default network
        )

    if backend == "k8s":
        from app.sandbox.k8s_manager import K8sSandboxManager
        return K8sSandboxManager(
            image=os.getenv("SANDBOX_IMAGE", "agent-platform-sandbox:latest"),
            namespace=os.getenv("SANDBOX_NAMESPACE", "agent-sessions"),
            resource_limits={
                "cpu": os.getenv("SANDBOX_CPU", "1"),
                "memory": os.getenv("SANDBOX_MEMORY", "512Mi"),
                "disk": os.getenv("SANDBOX_DISK", "100Mi"),
            },
            storage_class=os.getenv("SANDBOX_STORAGE_CLASS", "standard"),
        )

    raise ValueError(
        f"Unknown SANDBOX_BACKEND: {backend}. "
        f"Must be 'local', 'docker', or 'k8s'."
    )
