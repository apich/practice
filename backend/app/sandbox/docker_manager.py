"""Docker sandbox manager.

Creates a Docker container per session with resource limits and an
isolated filesystem. The container runs a non-root user and provides
a workspace directory for the agent's tools to operate in.

Requires the ``docker`` Python SDK and a running Docker Engine.
"""
import logging
from typing import Optional

from app.sandbox.base import SandboxInstance, SandboxManager

logger = logging.getLogger(__name__)

# Default resource limits
DEFAULT_CPU_LIMIT = 1
DEFAULT_MEMORY_LIMIT = "512m"
DEFAULT_DISK_LIMIT = "100m"


class DockerSandboxManager(SandboxManager):
    """Docker-based sandbox implementation.

    Each session gets its own container running the sandbox image.
    The container's filesystem is isolated and resource-limited.
    """

    def __init__(
        self,
        image: str = "agent-platform-sandbox:latest",
        resource_limits: Optional[dict] = None,
        network: Optional[str] = None,
    ):
        self.image = image
        self.resource_limits = resource_limits or {}
        self.network = network
        self._instances: dict[str, SandboxInstance] = {}

        # Lazy import — docker SDK may not be installed in dev mode
        try:
            import docker  # noqa: F401
            self._docker_available = True
        except ImportError:
            self._docker_available = False
            logger.warning(
                "docker SDK not installed. DockerSandboxManager will not work. "
                "Install with: pip install docker"
            )

    async def create(self, session_id: str) -> SandboxInstance:
        """Create a Docker container for the session."""
        if not self._docker_available:
            raise RuntimeError("Docker SDK is not installed")

        import docker
        import asyncio

        client = docker.from_env()

        # Resource limits
        cpu_limit = self.resource_limits.get("cpu", DEFAULT_CPU_LIMIT)
        mem_limit = self.resource_limits.get("memory", DEFAULT_MEMORY_LIMIT)

        # Run the container
        def _create_container():
            return client.containers.run(
                self.image,
                command="sleep infinity",  # keep container alive
                detach=True,
                name=f"sandbox-{session_id}",
                mem_limit=mem_limit,
                cpu_count=cpu_limit,
                network=self.network,
                labels={
                    "agent-platform": "sandbox",
                    "session-id": session_id,
                },
                # Non-root user (set in Dockerfile)
                user="sandbox",
                # Working directory
                working_dir="/home/sandbox/workspace",
                volumes={
                    f"sandbox-vol-{session_id}": {
                        "bind": "/home/sandbox/workspace",
                        "mode": "rw",
                    },
                },
            )

        container = await asyncio.get_event_loop().run_in_executor(
            None, _create_container,
        )

        instance = SandboxInstance(
            session_id=session_id,
            container_id=container.id,
            workspace_path="/home/sandbox/workspace",
            status="running",
        )
        self._instances[session_id] = instance
        logger.info(f"Created Docker sandbox for session {session_id}: {container.id}")
        return instance

    async def destroy(self, session_id: str) -> None:
        """Stop and remove the Docker container."""
        if session_id not in self._instances:
            return

        if not self._docker_available:
            return

        import docker
        import asyncio

        client = docker.from_env()
        instance = self._instances[session_id]

        def _destroy_container():
            try:
                container = client.containers.get(instance.container_id)
                container.stop(timeout=10)
                container.remove(force=True)
            except Exception as e:
                logger.warning(f"Failed to destroy container {instance.container_id}: {e}")

            # Remove the volume
            try:
                client.volumes.get(f"sandbox-vol-{session_id}").remove(force=True)
            except Exception:
                pass

        await asyncio.get_event_loop().run_in_executor(None, _destroy_container)

        del self._instances[session_id]
        logger.info(f"Destroyed Docker sandbox for session {session_id}")

    async def get_workspace(self, session_id: str) -> Optional[SandboxInstance]:
        """Return the sandbox instance for the session."""
        return self._instances.get(session_id)

    async def cleanup_all(self) -> None:
        """Destroy all active sandboxes."""
        for session_id in list(self._instances.keys()):
            await self.destroy(session_id)
