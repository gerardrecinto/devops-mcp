import json
import sys


class _FakeMCP:
    def __init__(self):
        self.tools = {}

    def tool(self):
        def decorator(fn):
            self.tools[fn.__name__] = fn
            return fn

        return decorator


def _fresh_teams():
    sys.modules.pop("devops_mcp.tools.teams", None)
    import importlib

    return importlib.import_module("devops_mcp.tools.teams")


def test_post_message_demo_returns_ok(no_audit):
    teams = _fresh_teams()
    mcp = _FakeMCP()
    teams.register(mcp, no_audit)

    result = json.loads(
        mcp.tools["teams_post_message"](
            title="Prod Alert", text="API gateway error rate at 18%"
        )
    )
    assert result["ok"] is True


def test_get_channel_messages_demo_returns_messages(no_audit):
    teams = _fresh_teams()
    mcp = _FakeMCP()
    teams.register(mcp, no_audit)

    result = json.loads(
        mcp.tools["teams_get_channel_messages"](
            team_id="team-abc", channel_id="19:channel@thread.tacv2"
        )
    )
    assert isinstance(result, list)
    assert len(result) > 0
    assert "body" in result[0]


def test_list_channels_demo_returns_channels(no_audit):
    teams = _fresh_teams()
    mcp = _FakeMCP()
    teams.register(mcp, no_audit)

    result = json.loads(mcp.tools["teams_list_channels"](team_id="team-abc"))
    assert isinstance(result, list)
    assert len(result) > 0
    assert "name" in result[0]
