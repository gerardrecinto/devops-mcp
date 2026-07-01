"""MCP server entry point for devops-mcp."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
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


def _init_audit() -> None:
    global _audit_path
    audit_dir = Path.home() / ".devops-mcp"
    audit_dir.mkdir(exist_ok=True)
    _audit_path = audit_dir / "audit.log"


def _audit(tool: str, params: dict[str, Any]) -> None:
    if _audit_path is None:
        return
    entry = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "tool": tool,
        "params": params,
    }
    with open(_audit_path, "a") as f:
        f.write(json.dumps(entry) + "\n")


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
        except Exception as exc:
            logger.warning("tool module %s failed to load: %s", name, exc)

    try:
        from importlib.metadata import version as _pkg_version

        _version = _pkg_version("devops-mcp")
    except Exception:
        _version = "dev"

    logger.info(
        "devops-mcp v%s started — registered: %s", _version, ", ".join(registered)
    )
    mcp.run()


if __name__ == "__main__":
    main()
