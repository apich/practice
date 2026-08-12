# Sandbox container image for agent-platform.
# Used by both Docker and K8s sandbox backends.
#
# Build:
#   docker build -t agent-platform-sandbox:latest -f _sandbox/Dockerfile .
#
# The container provides a non-root environment with Python, Node.js,
# and common tools for agent skill/MCP execution.

FROM python:3.11-slim

# ── System packages ──────────────────────────────────────────────────────
# git:     version control for workspace operations
# curl:    HTTP requests for MCP tools
# nodejs:  JavaScript runtime for MCP servers (e.g. @playwright/mcp)
# npm:     Node package manager for MCP installation
RUN apt-get update && apt-get install -y \
    git \
    curl \
    nodejs \
    npm \
    && rm -rf /var/lib/apt/lists/*

# ── Python packages ──────────────────────────────────────────────────────
# Pre-install common Python packages that agents might need.
RUN pip install --no-cache-dir \
    httpx \
    requests

# ── Non-root user ────────────────────────────────────────────────────────
# Security: run everything as the 'sandbox' user, not root.
RUN useradd -m sandbox && chown -R sandbox:sandbox /home/sandbox
USER sandbox
WORKDIR /home/sandbox/workspace

# Default command: keep the container alive (overridden by the manager)
CMD ["sleep", "infinity"]
