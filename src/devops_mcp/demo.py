"""Demo mode: sample data is opt-in so it can never pass for a real system.

Without DEVOPS_MCP_DEMO=1, a tool whose service is not configured returns a plain
error. With it, the sample data is labelled so an assistant does not report it as fact.
"""

from __future__ import annotations

import functools
import hashlib
import json
import os
from collections.abc import Callable
from typing import Any


def demo_enabled() -> bool:
    return os.getenv("DEVOPS_MCP_DEMO", "").strip().lower() in ("1", "true", "yes")


def writes_enabled() -> bool:
    """Tools that send messages stay off unless the operator opts in."""
    return os.getenv("DEVOPS_MCP_ENABLE_WRITES", "").strip().lower() in (
        "1",
        "true",
        "yes",
    )


def writes_disabled(tool: str) -> str:
    return error_response(
        "writes_disabled",
        f"{tool} sends data to an external system and writes are turned off.",
        "Set DEVOPS_MCP_ENABLE_WRITES=1 in the server environment to allow it.",
    )


def error_response(error: str, message: str, hint: str = "") -> str:
    """The error shape every tool uses: {"error", "message", "hint"}."""
    return json.dumps({"error": error, "message": message, "hint": hint})


def body_hash(body: str) -> str:
    """Audit entries record this instead of the message body."""
    return hashlib.sha256(body.encode()).hexdigest()


# What a person has to set to turn each service on, in the words the README uses.
SETUP_VARS: dict[str, str] = {
    "Kubernetes": "a kubeconfig (~/.kube/config) or KUBECONFIG",
    "Jenkins": "JENKINS_URL, JENKINS_USER and JENKINS_TOKEN",
    "GitHub Actions": "GITHUB_TOKEN",
    "AWS": "AWS_REGION plus AWS_PROFILE or AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY",
    "Azure": "AZURE_TENANT_ID, AZURE_CLIENT_ID, AZURE_CLIENT_SECRET and AZURE_SUBSCRIPTION_ID",
    "GCP": "GCP_PROJECT_ID and GOOGLE_APPLICATION_CREDENTIALS",
    "ServiceNow": "SNOW_INSTANCE, SNOW_USER and SNOW_PASSWORD",
    "Slack": "SLACK_BOT_TOKEN",
    "Microsoft Teams": "TEAMS_WEBHOOK_URL, or TEAMS_TENANT_ID, TEAMS_CLIENT_ID and TEAMS_CLIENT_SECRET",
}


def setup_hint(service: str) -> str:
    needs = SETUP_VARS.get(service, "its credentials")
    return (
        f"To turn on {service}, set {needs} in ~/.devops-mcp/.env, then restart the "
        "MCP server. Call devops_mcp_health to see what is connected. "
        "To preview the output shape first, set DEVOPS_MCP_DEMO=1 (sample data only)."
    )


def not_configured(service: str) -> str:
    return json.dumps(
        {
            "error": "not_configured",
            "message": f"{service} is not set up yet, so nothing was queried or sent.",
            "hint": setup_hint(service),
        }
    )


def demo_response(service: str, data: Any, writes: bool = False) -> str:
    if not demo_enabled():
        return not_configured(service)
    notice = (
        "Demo mode: nothing was sent to a real system."
        if writes
        else "Demo mode: sample data, not from your systems. Do not report it as real."
    )
    return json.dumps({"demo": True, "notice": notice, "data": data}, indent=2)


def demo_tool(
    service: str, writes: bool = False
) -> Callable[[Callable[..., str]], Callable[..., str]]:
    """Wrap a tool that returns hard-coded sample data."""

    def decorator(fn: Callable[..., str]) -> Callable[..., str]:
        @functools.wraps(fn)
        def wrapper(*args: Any, **kwargs: Any) -> str:
            if not demo_enabled():
                return not_configured(service)
            raw = fn(*args, **kwargs)
            try:
                data = json.loads(raw)
            except (TypeError, ValueError):
                data = raw
            return demo_response(service, data, writes=writes)

        return wrapper

    return decorator
