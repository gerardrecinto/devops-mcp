import importlib
import sys
from unittest.mock import MagicMock, patch

from tests.helpers import load
from tests.test_github_actions import _FakeMCP


def _fresh():
    sys.modules.pop("devops_mcp.tools.gitlab", None)
    return importlib.import_module("devops_mcp.tools.gitlab")


def test_get_pipeline_encodes_project_and_sends_token(no_audit, monkeypatch):
    monkeypatch.setenv("GITLAB_TOKEN", "glpat-test")
    monkeypatch.setenv("GITLAB_URL", "https://gitlab.example.com/")
    gl = _fresh()
    mcp = _FakeMCP()
    gl.register(mcp, no_audit)
    resp = MagicMock()
    resp.json.return_value = {
        "id": 7,
        "status": "failed",
        "ref": "main",
        "sha": "a1b2c3d4e5f6",
        "duration": 90,
        "created_at": "2024-01-15T03:40:00Z",
        "web_url": "https://gitlab.example.com/grp/app/-/pipelines/7",
    }
    with patch("requests.get", return_value=resp) as get:
        out = load(mcp.tools["gl_get_pipeline"](project="grp/app", pipeline_id=7))
    url = get.call_args.args[0]
    assert url == "https://gitlab.example.com/api/v4/projects/grp%2Fapp/pipelines/7"
    assert get.call_args.kwargs["headers"] == {"PRIVATE-TOKEN": "glpat-test"}
    assert out["status"] == "failed" and out["commit"] == "a1b2c3d4"


def test_list_failed_filters_by_status(no_audit, monkeypatch):
    monkeypatch.delenv("GITLAB_TOKEN", raising=False)
    gl = _fresh()
    mcp = _FakeMCP()
    gl.register(mcp, no_audit)
    resp = MagicMock()
    resp.json.return_value = [
        {"id": 1, "ref": "main", "sha": "deadbeefcafe", "created_at": "t", "web_url": "u"}
    ]
    with patch("requests.get", return_value=resp) as get:
        out = load(mcp.tools["gl_list_failed_pipelines"](project="grp/app", limit=3))
    assert get.call_args.kwargs["params"] == {"status": "failed", "per_page": 3}
    assert get.call_args.kwargs["headers"] == {}
    assert out == [{"id": 1, "ref": "main", "commit": "deadbeef", "created_at": "t", "url": "u"}]
