"""Shared workspace directory for Docker-based tools.

All containers mount this directory at /workspace, so files created
by one tool (e.g. PythonExecTool) are visible to another (e.g. BashTool).
"""

from __future__ import annotations

import os
import tempfile

_WORKSPACE_DIR = os.environ.get(
    "HYREX_WORKSPACE_DIR",
    tempfile.mkdtemp(prefix="hyrex-workspace-"),
)
"""Absolute path to the shared temp directory mounted as /workspace in containers."""
