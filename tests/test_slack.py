import sys

from tests.helpers import load


class _FakeMCP:
    def __init__(self):
        self.tools = {}

    def tool(self):
        def decorator(fn):
            self.tools[fn.__name__] = fn
            return fn

        return decorator


def _fresh_slack():
    sys.modules.pop("slack_sdk", None)
    sys.modules.pop("devops_mcp.tools.slack", None)
    import importlib

    return importlib.import_module("devops_mcp.tools.slack")


def test_post_message_demo_returns_ok(no_audit):
    slack = _fresh_slack()
    mcp = _FakeMCP()
    slack.register(mcp, no_audit)

    result = load(
        mcp.tools["slack_post_message"](channel="#incidents", text="prod is down")
    )
    assert result["ok"] is True
    assert "ts" in result


def test_get_channel_history_demo_returns_messages(no_audit):
    slack = _fresh_slack()
    mcp = _FakeMCP()
    slack.register(mcp, no_audit)

    result = load(mcp.tools["slack_get_channel_history"](channel="#incidents"))
    assert isinstance(result, list)
    assert len(result) > 0
    assert "text" in result[0]


def test_search_messages_demo_returns_matches(no_audit):
    slack = _fresh_slack()
    mcp = _FakeMCP()
    slack.register(mcp, no_audit)

    result = load(mcp.tools["slack_search_messages"](query="OOMKilled"))
    assert isinstance(result, list)
    assert len(result) > 0
    assert "channel" in result[0]


class _FakeClient:
    def __init__(self, token=""):
        self.posted = []

    def chat_postMessage(self, channel, text):
        self.posted.append((channel, text))
        return {"ok": True, "ts": "1.2", "channel": channel}


def _live_slack(monkeypatch, token="xoxb-test"):
    import types

    fake = types.ModuleType("slack_sdk")
    fake.WebClient = _FakeClient
    monkeypatch.setitem(sys.modules, "slack_sdk", fake)
    monkeypatch.setenv("SLACK_BOT_TOKEN", token)
    sys.modules.pop("devops_mcp.tools.slack", None)
    import importlib

    return importlib.import_module("devops_mcp.tools.slack")


def test_post_message_blocked_without_opt_in(monkeypatch):
    monkeypatch.delenv("DEVOPS_MCP_ENABLE_WRITES", raising=False)
    slack = _live_slack(monkeypatch)
    mcp = _FakeMCP()
    audited = []
    slack.register(mcp, lambda tool, params: audited.append((tool, params)))

    out = load(mcp.tools["slack_post_message"](channel="#ops", text="secret body"))
    assert out["error"] == "writes_disabled"
    assert {"error", "message", "hint"} <= set(out)
    assert "secret body" not in str(audited)
    assert audited[0][1]["destination"] == "#ops"
    assert len(audited[0][1]["body_sha256"]) == 64


def test_post_message_sends_when_enabled(monkeypatch, no_audit):
    monkeypatch.setenv("DEVOPS_MCP_ENABLE_WRITES", "1")
    slack = _live_slack(monkeypatch)
    mcp = _FakeMCP()
    slack.register(mcp, no_audit)

    out = load(mcp.tools["slack_post_message"](channel="#ops", text="hi"))
    assert out["ok"] is True


def test_empty_token_returns_not_configured(monkeypatch, no_audit):
    monkeypatch.setenv("DEVOPS_MCP_ENABLE_WRITES", "1")
    slack = _live_slack(monkeypatch, token="")
    mcp = _FakeMCP()
    slack.register(mcp, no_audit)

    for name, kwargs in (
        ("slack_post_message", {"channel": "#a", "text": "x"}),
        ("slack_get_channel_history", {"channel": "#a"}),
        ("slack_search_messages", {"query": "x"}),
    ):
        assert load(mcp.tools[name](**kwargs))["error"] == "not_configured"
