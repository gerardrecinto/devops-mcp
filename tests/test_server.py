import json
import os


def test_module_imports_and_constructs_fastmcp():
    """Regression test: FastMCP's constructor signature changed across mcp
    SDK versions (description -> instructions). This import alone would
    have caught that break before it reached a container build."""
    from devops_mcp import server

    assert server.mcp is not None


def test_main_registers_all_tool_modules(tmp_path, monkeypatch):
    from devops_mcp import server

    monkeypatch.setattr(server.Path, "home", lambda: tmp_path)
    monkeypatch.setattr(server.mcp, "run", lambda: None)

    server.main()

    audit_log = tmp_path / ".devops-mcp" / "audit.log"
    assert audit_log.parent.exists()


def test_audit_writes_json_line(tmp_path, monkeypatch):
    from devops_mcp import server

    monkeypatch.setattr(server, "_audit_path", tmp_path / "audit.log")
    server._audit("k8s_get_failing_pods", {"namespace": "production"})

    lines = (tmp_path / "audit.log").read_text().strip().splitlines()
    assert len(lines) == 1
    entry = json.loads(lines[0])
    assert entry["tool"] == "k8s_get_failing_pods"
    assert entry["params"] == {"namespace": "production"}
    assert "ts" in entry


def test_audit_noop_before_init(monkeypatch):
    from devops_mcp import server

    monkeypatch.setattr(server, "_audit_path", None)
    server._audit("noop", {})


def test_audit_redacts_secrets_and_survives_write_failure(tmp_path, monkeypatch):
    from devops_mcp import server

    log = tmp_path / "audit.log"
    monkeypatch.setattr(server, "_audit_path", log)
    server._audit(
        "teams_post_message", {"title": "x", "webhook_url": "https://h/secret"}
    )
    assert "https://h/secret" not in log.read_text()
    assert "[redacted]" in log.read_text()

    monkeypatch.setattr(server, "_audit_path", tmp_path / "missing" / "audit.log")
    server._audit("noop", {})  # must not raise


def test_init_audit_log_is_private(tmp_path, monkeypatch):
    import stat

    from devops_mcp import server

    monkeypatch.setattr(server.Path, "home", lambda: tmp_path / "nested" / "home")
    server._init_audit()
    mode = stat.S_IMODE(server._audit_path.stat().st_mode)
    assert mode == 0o600


def test_main_registers_incident_timeline(tmp_path, monkeypatch):
    from devops_mcp import server

    monkeypatch.setattr(server.Path, "home", lambda: tmp_path)
    monkeypatch.setattr(server.mcp, "run", lambda: None)
    server.main()
    import asyncio

    names = {t.name for t in asyncio.run(server.mcp.list_tools())}
    assert "incident_timeline" in names
    assert "k8s_get_failing_pods" in names


def test_tool_exception_becomes_error_object():
    from devops_mcp import server

    def boom() -> str:
        raise RuntimeError("upstream said no")

    out = json.loads(server._guard(boom)())
    assert out["error"] == "RuntimeError"
    assert out["message"] == "upstream said no"
    assert out["hint"]


def test_registered_tools_are_guarded(tmp_path, monkeypatch):
    from devops_mcp import server

    monkeypatch.setattr(server.Path, "home", lambda: tmp_path)
    monkeypatch.setattr(server.mcp, "run", lambda: None)
    seen = {}
    real = server._ToolTap.__init__

    def spy(self, mcp, tools):
        real(self, mcp, tools)
        seen["tools"] = tools

    monkeypatch.setattr(server._ToolTap, "__init__", spy)
    server.main()
    assert seen["tools"]
    assert all(hasattr(fn, "__wrapped__") for fn in seen["tools"].values())


def test_health_tool_reports_modules(tmp_path, monkeypatch):
    from devops_mcp import server

    monkeypatch.setattr(server.Path, "home", lambda: tmp_path)
    monkeypatch.setattr(server.mcp, "run", lambda: None)
    monkeypatch.setenv("JENKINS_URL", "https://j.example.com")
    monkeypatch.delenv("SLACK_BOT_TOKEN", raising=False)
    server.main()
    import asyncio

    result = asyncio.run(server.mcp.call_tool("devops_mcp_health", {}))
    text = next(c.text for c in result.content if hasattr(c, "text"))
    body = json.loads(text)
    assert "jenkins" in body["configured"]
    assert "slack" in body["not_configured"]
    assert body["writes_enabled"] is False


def test_home_env_file_is_loaded(tmp_path, monkeypatch):
    import importlib

    from devops_mcp import server

    (tmp_path / ".devops-mcp").mkdir()
    (tmp_path / ".devops-mcp" / ".env").write_text("DEVOPS_MCP_TEST_FROM_FILE=yes\n")
    monkeypatch.setattr("pathlib.Path.home", lambda: tmp_path)
    monkeypatch.delenv("DEVOPS_MCP_TEST_FROM_FILE", raising=False)
    try:
        importlib.reload(server)
        assert os.environ.get("DEVOPS_MCP_TEST_FROM_FILE") == "yes"
    finally:
        os.environ.pop("DEVOPS_MCP_TEST_FROM_FILE", None)


def test_not_configured_hint_names_the_variables():
    import json

    from devops_mcp.demo import not_configured

    out = json.loads(not_configured("Slack"))
    assert "SLACK_BOT_TOKEN" in out["hint"]
    assert "~/.devops-mcp/.env" in out["hint"]


def test_check_flag_prints_status(monkeypatch, capsys):
    import sys

    from devops_mcp import server

    monkeypatch.setattr(sys, "argv", ["devops-mcp", "--check"])
    server.main()
    out = capsys.readouterr().out
    assert "devops-mcp is installed" in out
    assert "Next:" in out


def test_init_audit_repairs_existing_permissions(tmp_path, monkeypatch):
    import stat

    from devops_mcp import server

    directory = tmp_path / ".devops-mcp"
    directory.mkdir(mode=0o755)
    log = directory / "audit.log"
    log.write_text("existing record\n")
    log.chmod(0o644)
    monkeypatch.setattr(server.Path, "home", lambda: tmp_path)
    server._init_audit()
    assert server._audit_path == log
    assert stat.S_IMODE(directory.stat().st_mode) == 0o700
    assert stat.S_IMODE(log.stat().st_mode) == 0o600
    assert log.read_text() == "existing record\n"


def test_init_audit_failure_disables_logging_without_raising(
    tmp_path, monkeypatch, caplog
):
    from devops_mcp import server

    (tmp_path / ".devops-mcp").write_text("not a directory")
    monkeypatch.setattr(server.Path, "home", lambda: tmp_path)
    monkeypatch.setattr(server, "_audit_path", tmp_path / "previous.log")
    server._init_audit()
    assert server._audit_path is None
    assert "audit logging is unavailable" in caplog.text
    server._audit("still usable", {})


def test_init_audit_rejects_symlink_directory(tmp_path, monkeypatch):
    from devops_mcp import server

    target = tmp_path / "shared"
    target.mkdir()
    (tmp_path / ".devops-mcp").symlink_to(target, target_is_directory=True)
    monkeypatch.setattr(server.Path, "home", lambda: tmp_path)
    server._init_audit()
    assert server._audit_path is None
    assert not (target / "audit.log").exists()


def test_init_audit_does_not_follow_log_symlink(tmp_path, monkeypatch):
    import pytest

    from devops_mcp import server

    if not hasattr(os, "O_NOFOLLOW"):
        pytest.skip("O_NOFOLLOW is a POSIX control")
    directory = tmp_path / ".devops-mcp"
    directory.mkdir()
    target = tmp_path / "other.txt"
    target.write_text("do not change")
    (directory / "audit.log").symlink_to(target)
    monkeypatch.setattr(server.Path, "home", lambda: tmp_path)
    server._init_audit()
    assert server._audit_path is None
    assert target.read_text() == "do not change"


def test_check_distinguishes_configuration_from_connectivity(monkeypatch, capsys):
    import sys

    from devops_mcp import server

    monkeypatch.setenv("JENKINS_URL", "https://unreachable.invalid")
    monkeypatch.setattr(sys, "argv", ["devops-mcp", "--check"])
    server.main()
    output = capsys.readouterr().out
    assert "Configured locally:" in output
    assert "jenkins" in output
    assert "API connectivity and credentials have not been tested." in output
    assert "Connected:" not in output
