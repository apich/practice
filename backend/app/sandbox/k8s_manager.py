"""Kubernetes sandbox manager.

Creates a K8s Pod per session with resource limits and a PersistentVolumeClaim
for workspace storage. The Pod runs a non-root user and provides an isolated
environment for the agent's tools.

Requires the ``kubernetes`` Python client and a valid kubeconfig.
"""
import asyncio
import logging
from typing import Optional

from app.sandbox.base import SandboxInstance, SandboxManager

logger = logging.getLogger(__name__)

# Default resource limits (K8s format)
DEFAULT_CPU_REQUEST = "1"
DEFAULT_MEMORY_REQUEST = "512Mi"
DEFAULT_STORAGE_REQUEST = "100Mi"


class K8sSandboxManager(SandboxManager):
    """Kubernetes-based sandbox implementation.

    Each session gets its own Pod with a PVC for workspace storage.
    The Pod runs in a configurable namespace with resource quotas.
    """

    def __init__(
        self,
        image: str = "agent-platform-sandbox:latest",
        namespace: str = "agent-sessions",
        resource_limits: Optional[dict] = None,
        storage_class: str = "standard",
    ):
        self.image = image
        self.namespace = namespace
        self.resource_limits = resource_limits or {}
        self.storage_class = storage_class
        self._instances: dict[str, SandboxInstance] = {}

        # Lazy import — kubernetes client may not be installed in dev mode
        try:
            from kubernetes import client, config  # noqa: F401
            self._k8s_available = True
            # Load kubeconfig
            try:
                config.load_incluster_config()
            except Exception:
                config.load_kubeconfig()
        except ImportError:
            self._k8s_available = False
            logger.warning(
                "kubernetes client not installed. K8sSandboxManager will not work. "
                "Install with: pip install kubernetes"
            )

    async def create(self, session_id: str) -> SandboxInstance:
        """Create a K8s Pod + PVC for the session."""
        if not self._k8s_available:
            raise RuntimeError("Kubernetes client is not installed")

        from kubernetes import client as k8s_client

        cpu_req = self.resource_limits.get("cpu", DEFAULT_CPU_REQUEST)
        mem_req = self.resource_limits.get("memory", DEFAULT_MEMORY_REQUEST)
        storage_req = self.resource_limits.get("disk", DEFAULT_STORAGE_REQUEST)
        pod_name = f"sandbox-{session_id}"
        pvc_name = f"sandbox-vol-{session_id}"

        def _create_resources():
            core_v1 = k8s_client.CoreV1Api()

            # 1 — Create PVC
            pvc = k8s_client.V1PersistentVolumeClaim(
                metadata=k8s_client.V1ObjectMeta(
                    name=pvc_name,
                    labels={"agent-platform": "sandbox", "session-id": session_id},
                ),
                spec=k8s_client.V1PersistentVolumeClaimSpec(
                    access_modes=["ReadWriteOnce"],
                    storage_class_name=self.storage_class,
                    resources=k8s_client.V1ResourceRequirements(
                        requests={"storage": storage_req},
                    ),
                ),
            )
            try:
                core_v1.create_namespaced_persistent_volume_claim(
                    self.namespace, pvc,
                )
            except k8s_client.ApiException as e:
                if e.status != 409:  # Already exists is OK
                    raise

            # 2 — Create Pod
            pod = k8s_client.V1Pod(
                metadata=k8s_client.V1ObjectMeta(
                    name=pod_name,
                    labels={"agent-platform": "sandbox", "session-id": session_id},
                ),
                spec=k8s_client.V1PodSpec(
                    containers=[
                        k8s_client.V1Container(
                            name="sandbox",
                            image=self.image,
                            command=["sleep", "infinity"],
                            working_dir="/home/sandbox/workspace",
                            user="sandbox",
                            resources=k8s_client.V1ResourceRequirements(
                                requests={"cpu": cpu_req, "memory": mem_req},
                                limits={"cpu": cpu_req, "memory": mem_req},
                            ),
                            volume_mounts=[
                                k8s_client.V1VolumeMount(
                                    name="workspace",
                                    mount_path="/home/sandbox/workspace",
                                ),
                            ],
                        ),
                    ],
                    volumes=[
                        k8s_client.V1Volume(
                            name="workspace",
                            persistent_volume_claim=k8s_client.V1PersistentVolumeClaimVolumeSource(
                                claim_name=pvc_name,
                            ),
                        ),
                    ],
                    restart_policy="Never",
                ),
            )
            core_v1.create_namespaced_pod(self.namespace, pod)

        await asyncio.get_event_loop().run_in_executor(None, _create_resources)

        instance = SandboxInstance(
            session_id=session_id,
            pod_name=pod_name,
            workspace_path="/home/sandbox/workspace",
            status="running",
        )
        self._instances[session_id] = instance
        logger.info(f"Created K8s sandbox for session {session_id}: {pod_name}")
        return instance

    async def destroy(self, session_id: str) -> None:
        """Delete the Pod and PVC."""
        if session_id not in self._instances:
            return

        if not self._k8s_available:
            return

        from kubernetes import client as k8s_client

        instance = self._instances[session_id]
        pod_name = instance.pod_name or f"sandbox-{session_id}"
        pvc_name = f"sandbox-vol-{session_id}"

        def _destroy_resources():
            core_v1 = k8s_client.CoreV1Api()
            try:
                core_v1.delete_namespaced_pod(pod_name, self.namespace)
            except k8s_client.ApiException as e:
                if e.status != 404:
                    logger.warning(f"Failed to delete pod {pod_name}: {e}")

            try:
                core_v1.delete_namespaced_persistent_volume_claim(
                    pvc_name, self.namespace,
                )
            except k8s_client.ApiException as e:
                if e.status != 404:
                    logger.warning(f"Failed to delete PVC {pvc_name}: {e}")

        await asyncio.get_event_loop().run_in_executor(None, _destroy_resources)

        del self._instances[session_id]
        logger.info(f"Destroyed K8s sandbox for session {session_id}")

    async def get_workspace(self, session_id: str) -> Optional[SandboxInstance]:
        """Return the sandbox instance for the session."""
        return self._instances.get(session_id)

    async def cleanup_all(self) -> None:
        """Destroy all active sandboxes."""
        for session_id in list(self._instances.keys()):
            await self.destroy(session_id)
