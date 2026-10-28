"""MCP server entry point for devops-mcp."""

from __future__ import annotations

import json
import logging
import threading
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

try:
    # mcp SDK 2.x renamed FastMCP -> MCPServer and moved the module.
    from mcp.server.mcpserver import MCPServer as FastMCP
except ImportError:
    # mcp SDK 1.x
    from mcp.server.fastmcp import FastMCP

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)

mcp = FastMCP(
    "devops-mcp",
    instructions=(
        "Live DevOps assistant. Query Kubernetes, Jenkins, GitHub Actions, AWS, Azure, GCP, "
        "ServiceNow, Slack, and Microsoft Teams in plain English."
    ),
)

_audit_path: Path | None = None
_audit_lock = threading.Lock()
_AUDIT_MAX_BYTES = 10 * 1024 * 1024
_SECRET_KEYS = ("token", "secret", "password", "authorization", "webhook")


def _init_audit() -> None:
    global _audit_path
    audit_dir = Path.home() / ".devops-mcp"
    audit_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
    _audit_path = audit_dir / "audit.log"
    _audit_path.touch(mode=0o600, exist_ok=True)


def _redact(params: dict[str, Any]) -> dict[str, Any]:
    return {
        k: "[redacted]" if any(w in k.lower() for w in _SECRET_KEYS) else v
        for k, v in params.items()
    }


def _audit(tool: str, params: dict[str, Any]) -> None:
    """Append one JSON line per tool call. A logging failure never fails the tool."""
    if _audit_path is None:
        return
    entry = {
        "ts": datetime.now(UTC).isoformat(),
        "tool": tool,
        "params": _redact(params),
    }
    try:
        with _audit_lock:
            if _audit_path.exists() and _audit_path.stat().st_size > _AUDIT_MAX_BYTES:
                _audit_path.replace(_audit_path.with_suffix(".log.1"))
                _audit_path.touch(mode=0o600)
            with open(_audit_path, "a") as f:
                f.write(json.dumps(entry, default=str) + "\n")
    except OSError as exc:
        logger.warning("audit log write failed: %s", exc)


def main() -> None:
    _init_audit()

    from devops_mcp.tools import (
        aws,
        azure,
        gcp,
        github_actions,
        jenkins,
        kubernetes,
        servicenow,
        slack,
        teams,
    )

    modules = [
        kubernetes,
        jenkins,
        github_actions,
        aws,
        azure,
        gcp,
        servicenow,
        slack,
        teams,
    ]
    registered: list[str] = []
    for mod in modules:
        name = mod.__name__.split(".")[-1]
        try:
            mod.register(mcp, _audit)
            registered.append(name)
        # One broken tool module must not stop the others.
        except Exception as exc:  # noqa: BLE001
            logger.warning("tool module %s failed to load: %s", name, exc)

    try:
        from importlib.metadata import PackageNotFoundError
        from importlib.metadata import version as _pkg_version

        _version = _pkg_version("devops-mcp")
    except PackageNotFoundError:
        _version = "dev"

    logger.info(
        "devops-mcp v%s started, registered: %s", _version, ", ".join(registered)
    )
    mcp.run()


if __name__ == "__main__":
    main()
