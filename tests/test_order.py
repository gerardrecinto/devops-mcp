import json
import os
import shutil
import subprocess
import sys

import pytest

from devops_mcp import order

BLOCKED = json.dumps(
    {
        "decision": "blocked",
        "reason": 'step "announce" requires state "looked"',
        "run_first": ["looked_at_system"],
    }
)
CFG = {
    "runbooks": "runbooks.json",
    "workflow": "announce",
    "joltrin": sys.executable,
    "record": {"k8s_get_failing_pods": "looked_at_system"},
    "gated": {"slack_post_message": "announce"},
}


def fake(code, out="", log=None):
    def run(argv, **kw):
        if log is not None:
            log.append(argv)
        return subprocess.CompletedProcess(argv, code, stdout=out, stderr="")

    return run


def make(run, cfg=CFG):
    return order.Order(cfg, "/cfg", "sess", "/tmp/state", run)


def tool(name, result):
    def fn(*a, **k):
        return result

    fn.__name__ = name
    return fn


@pytest.fixture(autouse=True)
def reset():
    yield
    order._current = None


def test_off_by_default():
    order._current = None
    assert order.ordered(tool("slack_post_message", "sent"))() == "sent"


def test_gated_tool_is_refused_until_gate_allows():
    order._current = make(fake(1, BLOCKED))
    out = json.loads(order.ordered(tool("slack_post_message", "sent"))())
    assert out["error"] == "order_not_satisfied" and "looked_at_system" in out["hint"]
    order._current = make(fake(0))
    assert order.ordered(tool("slack_post_message", "sent"))() == "sent"


def test_recording_tool_records_only_real_data():
    log = []
    order._current = make(fake(0, log=log))
    order.ordered(tool("k8s_get_failing_pods", json.dumps({"pods": []})))()
    assert len(log) == 1 and log[0][-1] == "looked_at_system"
    for bad in (json.dumps({"error": "x"}), json.dumps({"demo": True, "data": []})):
        order.ordered(tool("k8s_get_failing_pods", bad))()
    assert len(log) == 1, "errors and demo data must not count as a read"


def test_untracked_tool_never_calls_the_gate():
    log = []
    order._current = make(fake(0, log=log))
    order.ordered(tool("gcp_get_logs", "[]"))()
    assert log == []


def test_missing_binary_refuses_the_write():
    order._current = make(fake(0), dict(CFG, joltrin="no-such-joltrin"))
    out = json.loads(order.ordered(tool("slack_post_message", "sent"))())
    assert out["error"] == "order_not_satisfied" and "not on PATH" in out["message"]


def test_broken_config_refuses_writes_only(monkeypatch, tmp_path):
    monkeypatch.setenv(order.ENV, str(tmp_path / "missing.json"))
    order.init()
    assert (
        json.loads(order.ordered(tool("slack_post_message", "sent"))())["error"]
        == "order_config"
    )
    assert order.ordered(tool("k8s_get_failing_pods", "ok"))() == "ok"


def test_session_name_is_safe(monkeypatch, tmp_path):
    p = tmp_path / "o.json"
    p.write_text(json.dumps(CFG))
    monkeypatch.setenv(order.ENV, str(p))
    monkeypatch.setenv("DEVOPS_MCP_ORDER_SESSION", "../../etc/x")
    o = order.load_from_env()
    assert "/" not in o.session and not o.session.startswith(".")


@pytest.mark.skipif(
    not os.environ.get("JOLTRIN_BIN"),
    reason="set JOLTRIN_BIN to a sop-mcp-server with the gate command",
)
def test_real_gate_post_waits_for_a_read(monkeypatch, tmp_path):
    root = os.path.dirname(os.path.dirname(__file__))
    shutil.copy(
        os.path.join(root, "examples", "runbooks.json"), tmp_path / "runbooks.json"
    )
    cfg = dict(CFG, joltrin=os.environ["JOLTRIN_BIN"])
    (tmp_path / "order.json").write_text(json.dumps(cfg))
    monkeypatch.setenv(order.ENV, str(tmp_path / "order.json"))
    monkeypatch.setenv("TMPDIR", str(tmp_path))
    order.init()
    post = order.ordered(tool("slack_post_message", "sent"))
    assert json.loads(post())["error"] == "order_not_satisfied"
    order.ordered(tool("k8s_get_failing_pods", json.dumps({"pods": []})))()
    assert post() == "sent"


def test_server_registration_applies_the_order():
    from devops_mcp import server

    class MCP:
        def __init__(self):
            self.tools = {}

        def tool(self, *a, **k):
            def deco(fn):
                self.tools[fn.__name__] = fn
                return fn

            return deco

    mcp, tools = MCP(), {}
    tap = server._ToolTap(mcp, tools)

    @tap.tool()
    def slack_post_message(channel: str, text: str) -> str:
        return "sent"

    order._current = make(fake(1, BLOCKED))
    assert (
        json.loads(mcp.tools["slack_post_message"]("#a", "b"))["error"]
        == "order_not_satisfied"
    )
    order._current = make(fake(0))
    assert mcp.tools["slack_post_message"]("#a", "b") == "sent"
