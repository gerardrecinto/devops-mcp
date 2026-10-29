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

    result = load(mcp.tools["jenkins_get_build_status"](job_name="backend-deploy"))
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

    result = load(mcp.tools["jenkins_list_failing_jobs"]())
    assert isinstance(result, list)
    assert len(result) > 0
    for job in result:
        assert "name" in job
        assert "url" in job


def test_job_path_handles_folders_and_quoting():
    from devops_mcp.tools.jenkins import _job_path

    assert _job_path("build") == "/job/build"
    assert _job_path("team/app deploy") == "/job/team/job/app%20deploy"
    assert _job_path("/team/app/") == "/job/team/job/app"


def test_build_log_streams_and_keeps_only_tail(no_audit, monkeypatch):
    import sys
    from types import SimpleNamespace as NS

    monkeypatch.setenv("JENKINS_URL", "https://j.example.com")
    monkeypatch.setenv("JENKINS_USER", "u")
    monkeypatch.setenv("JENKINS_TOKEN", "t")
    sys.modules.pop("devops_mcp.tools.jenkins", None)
    import importlib

    jenkins = importlib.import_module("devops_mcp.tools.jenkins")
    seen = {}

    def fake_get(url, **kwargs):
        seen.update(kwargs)
        return NS(
            raise_for_status=lambda: None,
            iter_lines=lambda decode_unicode=True: iter(
                f"line {i}" for i in range(100_000)
            ),
            close=lambda: None,
        )

    monkeypatch.setattr("requests.get", fake_get)
    registered = {}

    class M:
        def tool(self):
            return lambda fn: registered.setdefault(fn.__name__, fn)

    jenkins.register(M(), no_audit)
    out = registered["jenkins_get_build_log"](job_name="a/b", tail_lines=3)
    assert out.splitlines() == ["line 99997", "line 99998", "line 99999"]
    assert seen["stream"] is True
