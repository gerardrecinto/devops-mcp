"""MCP server entry point for devops-mcp."""

from __future__ import annotations

import functools
import json
import logging
import os
import threading
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

from devops_mcp.demo import demo_enabled, error_response, writes_enabled

try:
    # mcp SDK 2.x renamed FastMCP -> MCPServer and moved the module.
    from mcp.server.mcpserver import MCPServer as FastMCP
except ImportError:
    # mcp SDK 1.x
    from mcp.server.fastmcp import FastMCP

# The README points people at ~/.devops-mcp/.env; a bare load_dotenv() searches
# from the installed package, so it never found that file. Real env vars win.
load_dotenv(Path.home() / ".devops-mcp" / ".env")
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
    _audit_path = None
    audit_dir = Path.home() / ".devops-mcp"
    try:
        audit_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
        if audit_dir.is_symlink():
            raise OSError("audit directory must not be a symbolic link")
        audit_dir.chmod(0o700)
        path = audit_dir / "audit.log"
        flags = os.O_WRONLY | os.O_APPEND | os.O_CREAT | getattr(os, "O_NOFOLLOW", 0)
        with os.fdopen(os.open(path, flags, 0o600), "a") as log:
            if hasattr(os, "fchmod"):
                os.fchmod(log.fileno(), 0o600)
        _audit_path = path
    except OSError as exc:
        logger.warning("audit logging is unavailable: %s", exc)


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


# Environment variables that mean a module has something to talk to. Any one is enough.
_CONFIG_ENV: dict[str, tuple[str, ...]] = {
    "kubernetes": ("KUBECONFIG", "KUBERNETES_SERVICE_HOST"),
    "jenkins": ("JENKINS_URL",),
    "github_actions": ("GITHUB_TOKEN",),
    "aws": ("AWS_ACCESS_KEY_ID", "AWS_PROFILE", "AWS_ROLE_ARN"),
    "azure": ("AZURE_SUBSCRIPTION_ID",),
    "gcp": ("GCP_PROJECT_ID", "GOOGLE_APPLICATION_CREDENTIALS"),
    "servicenow": ("SNOW_INSTANCE",),
    "slack": ("SLACK_BOT_TOKEN",),
    "teams": ("TEAMS_WEBHOOK_URL", "TEAMS_TENANT_ID"),
}


def _is_configured(module: str) -> bool:
    if any(os.getenv(k) for k in _CONFIG_ENV.get(module, ())):
        return True
    # Kubernetes and AWS also read credentials from files in the home directory.
    home_files = {
        "kubernetes": Path.home() / ".kube" / "config",
        "aws": Path.home() / ".aws" / "credentials",
    }
    path = home_files.get(module)
    return bool(path and path.exists())


def _guard(fn: Callable[..., Any]) -> Callable[..., Any]:
    """Turn an exception inside a tool into {"error","message","hint"}.

    The model gets something it can read and the server never leaks a traceback.
    """

    @functools.wraps(fn)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        try:
            return fn(*args, **kwargs)
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "tool %s failed: %s: %s", fn.__name__, type(exc).__name__, exc
            )
            return error_response(
                type(exc).__name__,
                str(exc)[:300] or "The call failed with no message.",
                "Check the service credentials and the parameters, then retry.",
            )

    return wrapper


class _ToolTap:
    """Passes tool registration through while remembering each tool by name,
    so the incident timeline can call the other modules' tools."""

    def __init__(self, mcp: Any, tools: dict[str, Callable[..., str]]) -> None:
        self._mcp = mcp
        self._tools = tools

    def tool(
        self, *args: Any, **kwargs: Any
    ) -> Callable[[Callable[..., str]], Callable[..., str]]:
        register = self._mcp.tool(*args, **kwargs)

        def decorator(fn: Callable[..., str]) -> Callable[..., str]:
            guarded = _guard(fn)
            self._tools[fn.__name__] = guarded
            return register(guarded)

        return decorator

    def __getattr__(self, name: str) -> Any:
        return getattr(self._mcp, name)


def _health() -> dict[str, Any]:
    configured = sorted(m for m in _CONFIG_ENV if _is_configured(m))
    missing = sorted(m for m in _CONFIG_ENV if not _is_configured(m))
    if configured:
        next_step = "Ask about a configured service, or add credentials to ~/.devops-mcp/.env for the rest."
    else:
        next_step = (
            "Nothing is connected yet. Put credentials in ~/.devops-mcp/.env "
            "(see .env.example) and restart, or set DEVOPS_MCP_DEMO=1 to preview sample data."
        )
    return {
        "configured": configured,
        "not_configured": missing,
        "demo_mode": demo_enabled(),
        "writes_enabled": writes_enabled(),
        "next_step": next_step,
    }


def _register_health(mcp: Any) -> None:
    @mcp.tool()
    def devops_mcp_health() -> str:
        """Which integrations are configured, whether sample data and writes are on, and what to do next."""
        _audit("devops_mcp_health", {})
        return json.dumps(_health(), indent=2)


def _cli_flag() -> bool:
    """Handle --check and --version so people can verify an install in a terminal."""
    import sys

    args = sys.argv[1:]
    if "--version" in args:
        try:
            from importlib.metadata import version

            print(version("mcp-devops"))
        except Exception:  # noqa: BLE001
            print("dev")
        return True
    if "--check" in args:
        h = _health()
        print("devops-mcp is installed and starts.")
        print(f"Configured locally: {', '.join(h['configured']) or 'nothing yet'}")
        print("API connectivity and credentials have not been tested.")
        print(f"Not set up: {', '.join(h['not_configured']) or 'none'}")
        print(f"Sample data (DEVOPS_MCP_DEMO): {'on' if h['demo_mode'] else 'off'}")
        print(f"Next: {h['next_step']}")
        return True
    return False


def main() -> None:
    if _cli_flag():
        return
    _init_audit()

    from devops_mcp.tools import (
        aws,
        azure,
        gcp,
        github_actions,
        incident,
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
    tools: dict[str, Callable[..., str]] = {}
    tap = _ToolTap(mcp, tools)
    for mod in modules:
        name = mod.__name__.split(".")[-1]
        try:
            mod.register(tap, _audit)
            registered.append(name)
        # One broken tool module must not stop the others.
        except Exception as exc:  # noqa: BLE001
            logger.warning("tool module %s failed to load: %s", name, exc)

    try:
        incident.register(mcp, _audit, tools)
        registered.append("incident")
    except Exception as exc:  # noqa: BLE001
        logger.warning("tool module incident failed to load: %s", exc)

    try:
        from importlib.metadata import PackageNotFoundError
        from importlib.metadata import version as _pkg_version

        _version = _pkg_version("mcp-devops")
    except PackageNotFoundError:
        _version = "dev"

    try:
        _register_health(mcp)
    except Exception as exc:  # noqa: BLE001
        logger.warning("health tool failed to load: %s", exc)

    configured = [m for m in registered if _is_configured(m)]
    unconfigured = [m for m in registered if m in _CONFIG_ENV and m not in configured]
    logger.info(
        "devops-mcp v%s started, registered: %s", _version, ", ".join(registered)
    )
    logger.info(
        "configured: %s | not configured: %s | demo=%s writes=%s",
        ", ".join(configured) or "none",
        ", ".join(unconfigured) or "none",
        demo_enabled(),
        writes_enabled(),
    )
    mcp.run()


if __name__ == "__main__":
    main()
