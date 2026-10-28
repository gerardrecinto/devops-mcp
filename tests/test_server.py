import json


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
