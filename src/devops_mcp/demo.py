"""Demo mode: sample data is opt-in so it can never pass for a real system.

Without DEVOPS_MCP_DEMO=1, a tool whose service is not configured returns a plain
error. With it, the sample data is labelled so an assistant does not report it as fact.
"""

from __future__ import annotations

import functools
import json
import os
from collections.abc import Callable
from typing import Any


def demo_enabled() -> bool:
    return os.getenv("DEVOPS_MCP_DEMO", "").strip().lower() in ("1", "true", "yes")


def not_configured(service: str) -> str:
    return json.dumps(
        {
            "error": f"{service} is not configured, so nothing was queried or sent.",
            "hint": "Set the credentials in .env, or set DEVOPS_MCP_DEMO=1 to try sample data.",
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
