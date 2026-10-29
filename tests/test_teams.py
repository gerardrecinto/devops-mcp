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


def _fresh_teams():
    sys.modules.pop("devops_mcp.tools.teams", None)
    import importlib

    return importlib.import_module("devops_mcp.tools.teams")


def test_post_message_demo_returns_ok(no_audit):
    teams = _fresh_teams()
    mcp = _FakeMCP()
    teams.register(mcp, no_audit)

    result = load(
        mcp.tools["teams_post_message"](
            title="Prod Alert", text="API gateway error rate at 18%"
        )
    )
    assert result["ok"] is True


def test_get_channel_messages_demo_returns_messages(no_audit):
    teams = _fresh_teams()
    mcp = _FakeMCP()
    teams.register(mcp, no_audit)

    result = load(
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

    result = load(mcp.tools["teams_list_channels"](team_id="team-abc"))
    assert isinstance(result, list)
    assert len(result) > 0
    assert "name" in result[0]


def test_post_message_rejects_non_microsoft_webhook(no_audit, monkeypatch):
    monkeypatch.setenv("DEVOPS_MCP_ENABLE_WRITES", "1")
    monkeypatch.setenv("TEAMS_WEBHOOK_URL", "https://contoso.webhook.office.com/x")
    teams = _fresh_teams()
    mcp = _FakeMCP()
    teams.register(mcp, no_audit)
    posted = []
    monkeypatch.setattr(teams._requests, "post", lambda *a, **k: posted.append(a))

    for bad in (
        "https://evil.example.com/hook",
        "http://a.webhook.office.com/x",
        "https://webhook.office.com.evil.com/x",
    ):
        out = load(
            mcp.tools["teams_post_message"](title="t", text="s", webhook_url=bad)
        )
        assert "error" in out
    assert posted == []


def test_allowed_webhook_hosts():
    teams = _fresh_teams()
    assert teams._allowed_webhook("https://contoso.webhook.office.com/webhookb2/x")
    assert teams._allowed_webhook("https://prod-1.westus.logic.azure.com/workflows/x")
    assert not teams._allowed_webhook("https://169.254.169.254/latest")


class _Resp:
    status_code = 200

    def raise_for_status(self):
        pass


def _live_teams(monkeypatch, allowlist=None, writes=True):
    monkeypatch.setenv(
        "TEAMS_WEBHOOK_URL", "https://contoso.webhook.office.com/x/secret"
    )
    if writes:
        monkeypatch.setenv("DEVOPS_MCP_ENABLE_WRITES", "1")
    else:
        monkeypatch.delenv("DEVOPS_MCP_ENABLE_WRITES", raising=False)
    if allowlist:
        monkeypatch.setenv("DEVOPS_MCP_TEAMS_WEBHOOK_ALLOWLIST", allowlist)
    else:
        monkeypatch.delenv("DEVOPS_MCP_TEAMS_WEBHOOK_ALLOWLIST", raising=False)
    teams = _fresh_teams()
    posted = []
    monkeypatch.setattr(
        teams._requests, "post", lambda url, **k: posted.append(url) or _Resp()
    )
    audited = []
    mcp = _FakeMCP()
    teams.register(mcp, lambda tool, params: audited.append(params))
    return mcp, posted, audited


def test_post_blocked_without_opt_in(monkeypatch):
    mcp, posted, audited = _live_teams(monkeypatch, writes=False)
    out = load(mcp.tools["teams_post_message"](title="t", text="body text"))
    assert out["error"] == "writes_disabled"
    assert posted == []
    assert "body text" not in str(audited)


def test_post_uses_default_webhook_and_audits_hash_only(monkeypatch):
    mcp, posted, audited = _live_teams(monkeypatch)
    out = load(mcp.tools["teams_post_message"](title="t", text="body text"))
    assert out["ok"] is True
    assert posted == ["https://contoso.webhook.office.com/x/secret"]
    entry = audited[0]
    assert entry["destination"] == "contoso.webhook.office.com"
    assert len(entry["body_sha256"]) == 64
    assert "body text" not in str(entry) and "secret" not in str(entry)


def test_override_needs_allowlist(monkeypatch):
    other = "https://other.webhook.office.com/y"
    mcp, posted, _ = _live_teams(monkeypatch)
    out = load(mcp.tools["teams_post_message"](title="t", text="s", webhook_url=other))
    assert out["error"] == "webhook_rejected"
    assert posted == []

    mcp, posted, _ = _live_teams(monkeypatch, allowlist="other.webhook.office.com")
    out = load(mcp.tools["teams_post_message"](title="t", text="s", webhook_url=other))
    assert out["ok"] is True
    assert posted == [other]
