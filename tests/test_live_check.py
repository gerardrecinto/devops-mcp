import sys

import pytest
import requests

from devops_mcp import live_check, server


class Resp:
    def __init__(self, status=200, body=None):
        self.status_code, self._body = status, body or {}

    def json(self):
        return self._body


def fake(monkeypatch, resp=None, exc=None):
    seen = {}

    def request(method, url, **kw):
        seen.update(method=method, url=url, kw=kw)
        if exc:
            raise exc
        return resp

    monkeypatch.setattr(live_check.requests, "request", request)
    return seen


def test_github_ok_names_the_user_and_sends_the_token(monkeypatch):
    monkeypatch.setenv("GITHUB_TOKEN", "t0ken")
    seen = fake(monkeypatch, Resp(200, {"login": "octo"}))
    r = live_check._github()
    assert (r.status, r.detail) == ("ok", "authenticated as octo")
    assert seen["method"] == "GET" and seen["kw"]["timeout"] == live_check.TIMEOUT


@pytest.mark.parametrize("code", [401, 403])
def test_rejected_credentials_name_the_variable(monkeypatch, code):
    monkeypatch.setenv("GITLAB_TOKEN", "x")
    fake(monkeypatch, Resp(code))
    r = live_check._gitlab()
    assert r.status == "fail" and f"HTTP {code}" in r.detail and "GITLAB_TOKEN" in r.fix


def test_unreachable_and_tls_failures_have_different_fixes(monkeypatch):
    monkeypatch.setenv("JENKINS_URL", "https://ci.example.com")
    monkeypatch.setenv("JENKINS_USER", "u")
    monkeypatch.setenv("JENKINS_TOKEN", "t")
    fake(monkeypatch, exc=requests.exceptions.ConnectionError())
    assert "HTTPS_PROXY" in live_check._jenkins().fix
    fake(monkeypatch, exc=requests.exceptions.SSLError())
    assert "REQUESTS_CA_BUNDLE" in live_check._jenkins().fix


def test_missing_variables_are_named_without_a_network_call(monkeypatch):
    for k in ("SNOW_INSTANCE", "SNOW_USER", "SNOW_PASSWORD"):
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setenv("SNOW_INSTANCE", "dev1.service-now.com")
    seen = fake(monkeypatch, Resp())
    r = live_check._servicenow()
    assert r.status == "fail" and "SNOW_USER, SNOW_PASSWORD" in r.detail and not seen


def test_slack_200_with_ok_false_is_a_failure(monkeypatch):
    monkeypatch.setenv("SLACK_BOT_TOKEN", "xoxb-x")
    fake(monkeypatch, Resp(200, {"ok": False, "error": "invalid_auth"}))
    r = live_check._slack()
    assert r.status == "fail" and "SLACK_BOT_TOKEN" in r.fix


def test_teams_is_never_probed_and_secrets_are_not_printed(monkeypatch):
    monkeypatch.setenv("GITHUB_TOKEN", "super-secret-value")
    fake(monkeypatch, Resp(401))
    results = live_check.run_live(["teams", "github_actions"])
    lines, code = live_check.report(results)
    assert results[0].status == "skipped" and code == 1
    assert "super-secret-value" not in "\n".join(lines)


def test_check_live_exits_1_on_a_failure_and_0_when_all_ok(monkeypatch, capsys):
    for k in list(live_check.os.environ):
        if k.startswith(("JENKINS", "GITLAB", "SNOW", "SLACK", "AWS", "KUBE", "AZURE", "GCP", "TEAMS")):
            monkeypatch.delenv(k)
    monkeypatch.setattr(server.Path, "home", lambda: server.Path("/nonexistent-home"))
    monkeypatch.setenv("GITHUB_TOKEN", "t")
    monkeypatch.setattr(sys, "argv", ["devops-mcp", "--check", "--live"])
    fake(monkeypatch, Resp(200, {"login": "octo"}))
    assert server._cli_flag() is True
    out = capsys.readouterr().out
    assert "OK" in out and "1 of 1 configured services answered" in out

    fake(monkeypatch, Resp(401))
    with pytest.raises(SystemExit) as e:
        server._cli_flag()
    assert e.value.code == 1


def test_plain_check_still_says_nothing_was_tested(monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["devops-mcp", "--check"])
    server._cli_flag()
    assert "Add --live to test them" in capsys.readouterr().out
