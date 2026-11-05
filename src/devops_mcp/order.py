"""Optional step order, enforced by Joltrin.

Off unless DEVOPS_MCP_ORDER points at a JSON file. With it, a tool that sends a message
(for example slack_post_message) is refused until this server session has really read from a
system, and the check is done by `sop-mcp-server gate`, which remembers allowed steps.

Config file:

    {
      "runbooks": "runbooks.json",          # a Joltrin runbook file, relative to this file
      "workflow": "announce",
      "record": {"k8s_get_deployment_status": "looked_at_system"},   # tool -> step it counts as
      "gated": {"slack_post_message": "announce"},                   # tool -> step it needs
      "joltrin": "sop-mcp-server"           # optional, binary name or path
    }

A read counts only when the tool returned real data: an error, or sample data from demo mode,
does not count. A gated tool that cannot be checked is refused, with the reason.
"""
from __future__ import annotations

import functools
import json
import os
import re
import shutil
import subprocess
import tempfile
import uuid
from collections.abc import Callable
from typing import Any

from devops_mcp.demo import error_response

ENV = "DEVOPS_MCP_ORDER"
# Tools that send data out. If the order file is set but unusable, these are refused.
WRITE_TOOLS = ("slack_post_message", "teams_post_message")


class Order:
    def __init__(self, cfg: dict[str, Any], base: str, session: str, state_dir: str, run: Callable[..., Any] = subprocess.run):
        self.workflow = cfg["workflow"]
        self.runbooks = cfg["runbooks"] if os.path.isabs(cfg["runbooks"]) else os.path.join(base, cfg["runbooks"])
        self.record: dict[str, str] = cfg.get("record", {})
        self.gated: dict[str, str] = cfg.get("gated", {})
        self.binary = cfg.get("joltrin") or "sop-mcp-server"
        self.session, self.state_dir, self._run = session, state_dir, run

    def _gate(self, step: str) -> tuple[bool, dict[str, Any]]:
        """Ask Joltrin about one step. Returns (allowed, details)."""
        if not shutil.which(self.binary):
            return False, {"reason": f"{self.binary} is not on PATH. It needs a Joltrin build with the gate command.", "config": True}
        try:
            p = self._run([self.binary, "gate", "--json", "--state-dir", self.state_dir, self.runbooks, self.workflow, self.session, step],
                          capture_output=True, text=True, timeout=10)
        except (OSError, subprocess.TimeoutExpired) as exc:
            return False, {"reason": f"{self.binary} gate failed to run: {exc}", "config": True}
        if p.returncode == 0:
            return True, {}
        try:
            res = json.loads(p.stdout)
            if res.get("decision") == "blocked":
                return False, res
        except json.JSONDecodeError:
            pass
        return False, {"reason": f"{self.binary} gate said: {(p.stderr or p.stdout).strip()[:200]}", "config": True}

    def before(self, tool: str) -> str | None:
        """None to go ahead, or an error_response string when the tool must wait."""
        step = self.gated.get(tool)
        if step is None:
            return None
        ok, res = self._gate(step)
        if ok:
            return None
        first = res.get("run_first") or []
        hint = f"Read from a system first ({', '.join(first)}), then try again." if first else "Fix the order setup or ask a person."
        return error_response("order_not_satisfied", res.get("reason", "An earlier step has not happened yet."), hint)

    def after(self, tool: str, result: Any) -> None:
        step = self.record.get(tool)
        if step is None or not _is_real_data(result):
            return
        self._gate(step)


def _is_real_data(result: Any) -> bool:
    """False for an error result and for demo-mode sample data."""
    if not isinstance(result, str):
        return True
    try:
        body = json.loads(result)
    except json.JSONDecodeError:
        return True
    return not (isinstance(body, dict) and (body.get("demo") is True or "error" in body))


class _Broken:
    """Stands in when the order file is set but unusable: gated writes are refused, nothing else changes."""

    def __init__(self, message: str):
        self.message = message

    def before(self, tool: str) -> str | None:
        if tool in WRITE_TOOLS:
            return error_response("order_config", f"The step order file could not be used: {self.message}.",
                                  f"Fix the file named in {ENV}, or unset {ENV} to turn step order off.")
        return None

    def after(self, tool: str, result: Any) -> None:
        return None


_current: Order | _Broken | None = None


def load_from_env(run: Callable[..., Any] = subprocess.run) -> Order | _Broken | None:
    path = os.getenv(ENV, "").strip()
    if not path:
        return None
    try:
        with open(path) as f:
            cfg = json.load(f)
        for key in ("runbooks", "workflow"):
            if key not in cfg:
                raise ValueError(f"missing {key!r}")
        for field in ("record", "gated"):
            if not isinstance(cfg.get(field, {}), dict):
                raise TypeError(f"{field!r} must map tool names to step names")
    except (OSError, ValueError, TypeError) as exc:
        return _Broken(str(exc))
    session = re.sub(r"[^A-Za-z0-9._-]", "_", os.getenv("DEVOPS_MCP_ORDER_SESSION", "") or f"devops-mcp-{uuid.uuid4().hex[:12]}")[:128].lstrip("._-") or "devops-mcp"
    state_dir = os.path.join(tempfile.gettempdir(), "devops-mcp-order")
    return Order(cfg, os.path.dirname(os.path.abspath(path)), session, state_dir, run)


def init(run: Callable[..., Any] = subprocess.run) -> None:
    global _current
    _current = load_from_env(run)


def ordered(fn: Callable[..., str]) -> Callable[..., str]:
    """Wrap a tool so a gated tool waits for its steps and a recording tool counts once it returns data."""

    @functools.wraps(fn)
    def wrapper(*args: Any, **kwargs: Any) -> str:
        order = _current
        if order is None:
            return fn(*args, **kwargs)
        blocked = order.before(fn.__name__)
        if blocked is not None:
            return blocked
        result = fn(*args, **kwargs)
        order.after(fn.__name__, result)
        return result

    return wrapper
