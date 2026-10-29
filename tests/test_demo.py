import json

from devops_mcp.demo import demo_response, demo_tool


def test_unconfigured_tool_does_not_fabricate_data(monkeypatch):
    monkeypatch.delenv("DEVOPS_MCP_DEMO", raising=False)
    out = json.loads(demo_response("Kubernetes", [{"name": "fake-pod"}]))
    assert "error" in out
    assert "fake-pod" not in json.dumps(out)


def test_demo_data_is_labelled(monkeypatch):
    out = json.loads(demo_response("Kubernetes", [{"name": "x"}]))
    assert out["demo"] is True
    assert out["data"] == [{"name": "x"}]


def test_write_tool_in_demo_says_nothing_sent():
    @demo_tool("Slack", writes=True)
    def post() -> str:
        return json.dumps({"ok": True})

    assert "nothing was sent" in json.loads(post())["notice"].lower()


def test_write_tool_unconfigured_never_reports_ok(monkeypatch):
    monkeypatch.delenv("DEVOPS_MCP_DEMO", raising=False)

    @demo_tool("Slack", writes=True)
    def post() -> str:
        return json.dumps({"ok": True})

    assert "ok" not in json.loads(post())
