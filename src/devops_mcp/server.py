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
    description=(
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
    entry = {"ts": datetime.now(timezone.utc).isoformat(), "tool": tool, "params": params}
    with open(_audit_path, "a") as f:
        f.write(json.dumps(entry) + "\n")


def main() -> None:
    _init_audit()

    from devops_mcp.tools import aws, azure, gcp, github_actions, jenkins, kubernetes, servicenow, slack, teams

    kubernetes.register(mcp, _audit)
    jenkins.register(mcp, _audit)
    github_actions.register(mcp, _audit)
    aws.register(mcp, _audit)
    azure.register(mcp, _audit)
    gcp.register(mcp, _audit)
    servicenow.register(mcp, _audit)
    slack.register(mcp, _audit)
    teams.register(mcp, _audit)

    logger.info("devops-mcp started, 9 tool modules registered")
    mcp.run()


if __name__ == "__main__":
    main()
