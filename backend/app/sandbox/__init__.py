"""Sandbox module: isolated execution environments for agent tools.

Supports Docker and Kubernetes backends, configurable via the
``SANDBOX_BACKEND`` environment variable. Falls back to local
execution (no isolation) when not configured.
"""
