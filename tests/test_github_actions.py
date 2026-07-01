import importlib
import json
import sys
from unittest.mock import MagicMock, patch


class _FakeMCP:
    def __init__(self):
        self.tools = {}

    def tool(self):
        def decorator(fn):
            self.tools[fn.__name__] = fn
            return fn

        return decorator


def _fresh_github_actions():
    sys.modules.pop("devops_mcp.tools.github_actions", None)
    return importlib.import_module("devops_mcp.tools.github_actions")


def test_get_workflow_run_returns_details(no_audit):
    gha = _fresh_github_actions()
    mcp = _FakeMCP()
    gha.register(mcp, no_audit)

    fake_resp = MagicMock()
    fake_resp.json.return_value = {
        "id": 123,
        "name": "CI",
        "status": "completed",
        "conclusion": "failure",
        "head_branch": "main",
        "head_sha": "a1b2c3d4e5f6",
        "created_at": "2024-01-15T03:40:00Z",
        "html_url": "https://github.com/gerardrecinto/devops-mcp/actions/runs/123",
    }
    with patch("requests.get", return_value=fake_resp):
        result = json.loads(
            mcp.tools["gh_get_workflow_run"](
                owner="gerardrecinto", repo="devops-mcp", run_id=123
            )
        )

    assert result["conclusion"] == "failure"
    assert result["commit"] == "a1b2c3d4"


def test_list_failed_runs_returns_only_failures(no_audit):
    gha = _fresh_github_actions()
    mcp = _FakeMCP()
    gha.register(mcp, no_audit)

    fake_resp = MagicMock()
    fake_resp.json.return_value = {
        "workflow_runs": [
            {
                "id": 456,
                "name": "CI",
                "head_branch": "main",
                "head_sha": "deadbeefcafe",
                "created_at": "2024-01-15T03:40:00Z",
                "html_url": "https://github.com/gerardrecinto/devops-mcp/actions/runs/456",
            }
        ]
    }
    with patch("requests.get", return_value=fake_resp):
        result = json.loads(
            mcp.tools["gh_list_failed_runs"](owner="gerardrecinto", repo="devops-mcp")
        )

    assert isinstance(result, list)
    assert result[0]["commit"] == "deadbeef"


def test_headers_include_auth_when_token_set(no_audit, monkeypatch):
    monkeypatch.setenv("GITHUB_TOKEN", "ghp_faketoken")
    gha = _fresh_github_actions()
    mcp = _FakeMCP()
    gha.register(mcp, no_audit)

    fake_resp = MagicMock()
    fake_resp.json.return_value = {
        "id": 1,
        "name": "CI",
        "status": "completed",
        "conclusion": "success",
        "head_branch": "main",
        "head_sha": "abc",
        "created_at": "2024-01-15T03:40:00Z",
        "html_url": "https://example.com",
    }
    with patch("requests.get", return_value=fake_resp) as mock_get:
        mcp.tools["gh_get_workflow_run"](
            owner="gerardrecinto", repo="devops-mcp", run_id=1
        )

    _, kwargs = mock_get.call_args
    assert kwargs["headers"]["Authorization"] == "Bearer ghp_faketoken"


def test_demo_mode_when_requests_unavailable(no_audit, monkeypatch):
    monkeypatch.setitem(sys.modules, "requests", None)
    gha = _fresh_github_actions()
    mcp = _FakeMCP()
    gha.register(mcp, no_audit)

    result = json.loads(
        mcp.tools["gh_get_workflow_run"](
            owner="gerardrecinto", repo="devops-mcp", run_id=1
        )
    )
    assert "conclusion" in result
