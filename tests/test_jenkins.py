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


def _fresh_jenkins():
    sys.modules.pop("devops_mcp.tools.jenkins", None)
    import importlib

    return importlib.import_module("devops_mcp.tools.jenkins")


def test_get_build_status_demo_returns_failure(no_audit, monkeypatch):
    """Without env vars, demo mode returns a FAILURE build."""
    monkeypatch.delenv("JENKINS_URL", raising=False)
    monkeypatch.delenv("JENKINS_USER", raising=False)
    monkeypatch.delenv("JENKINS_TOKEN", raising=False)

    jenkins = _fresh_jenkins()
    mcp = _FakeMCP()
    jenkins.register(mcp, no_audit)

    result = json.loads(
        mcp.tools["jenkins_get_build_status"](job_name="backend-deploy")
    )
    assert result["result"] == "FAILURE"
    assert result["duration_s"] > 0


def test_get_build_log_contains_error(no_audit, monkeypatch):
    monkeypatch.delenv("JENKINS_URL", raising=False)

    jenkins = _fresh_jenkins()
    mcp = _FakeMCP()
    jenkins.register(mcp, no_audit)

    log = mcp.tools["jenkins_get_build_log"](job_name="backend-deploy")
    assert "FAILURE" in log


def test_list_failing_jobs_demo(no_audit, monkeypatch):
    monkeypatch.delenv("JENKINS_URL", raising=False)

    jenkins = _fresh_jenkins()
    mcp = _FakeMCP()
    jenkins.register(mcp, no_audit)

    result = json.loads(mcp.tools["jenkins_list_failing_jobs"]())
    assert isinstance(result, list)
    assert len(result) > 0
    for job in result:
        assert "name" in job
        assert "url" in job
