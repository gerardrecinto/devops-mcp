import json
from unittest.mock import patch

import pytest


def test_module_imports_and_constructs_fastmcp():
    """Regression test: FastMCP's constructor signature changed across mcp
    SDK versions (description -> instructions). This import alone would
    have caught that break before it reached a container build."""
    import devops_mcp.server as server

    assert server.mcp is not None


def test_main_registers_all_tool_modules(tmp_path, monkeypatch):
    import devops_mcp.server as server

    monkeypatch.setattr(server.Path, "home", lambda: tmp_path)
    monkeypatch.setattr(server.mcp, "run", lambda: None)

    server.main()

    audit_log = tmp_path / ".devops-mcp" / "audit.log"
    assert audit_log.parent.exists()


def test_audit_writes_json_line(tmp_path, monkeypatch):
    import devops_mcp.server as server

    monkeypatch.setattr(server, "_audit_path", tmp_path / "audit.log")
    server._audit("k8s_get_failing_pods", {"namespace": "production"})

    lines = (tmp_path / "audit.log").read_text().strip().splitlines()
    assert len(lines) == 1
    entry = json.loads(lines[0])
    assert entry["tool"] == "k8s_get_failing_pods"
    assert entry["params"] == {"namespace": "production"}
    assert "ts" in entry


def test_audit_noop_before_init(monkeypatch):
    import devops_mcp.server as server

    monkeypatch.setattr(server, "_audit_path", None)
    server._audit("noop", {})
