import json
import sys
import pytest


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

    result = json.loads(mcp.tools["slack_post_message"](channel="#incidents", text="prod is down"))
    assert result["ok"] is True
    assert "ts" in result


def test_get_channel_history_demo_returns_messages(no_audit):
    slack = _fresh_slack()
    mcp = _FakeMCP()
    slack.register(mcp, no_audit)

    result = json.loads(mcp.tools["slack_get_channel_history"](channel="#incidents"))
    assert isinstance(result, list)
    assert len(result) > 0
    assert "text" in result[0]


def test_search_messages_demo_returns_matches(no_audit):
    slack = _fresh_slack()
    mcp = _FakeMCP()
    slack.register(mcp, no_audit)

    result = json.loads(mcp.tools["slack_search_messages"](query="OOMKilled"))
    assert isinstance(result, list)
    assert len(result) > 0
    assert "channel" in result[0]
