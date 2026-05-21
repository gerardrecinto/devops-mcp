import json
import sys
import types
import pytest


class _FakeMCP:
    def __init__(self):
        self.tools = {}

    def tool(self):
        def decorator(fn):
            self.tools[fn.__name__] = fn
            return fn
        return decorator


def _register_with_stub(stub_k8s):
    sys.modules.pop("kubernetes", None)
    sys.modules.pop("devops_mcp.tools.kubernetes", None)

    k8s_mod = types.ModuleType("kubernetes")
    k8s_mod.client = stub_k8s["client"]
    k8s_mod.config = stub_k8s["config"]
    sys.modules["kubernetes"] = k8s_mod

    from devops_mcp.tools import kubernetes  # noqa: F401
    import importlib
    kubernetes = importlib.import_module("devops_mcp.tools.kubernetes")

    mcp = _FakeMCP()
    kubernetes.register(mcp, lambda t, p: None)
    return mcp


def test_get_failing_pods_returns_only_non_running(no_audit):
    """Only pods outside Running/Succeeded should appear in results."""
    # Use demo mode (no kubernetes installed in test env)
    sys.modules.pop("kubernetes", None)
    sys.modules.pop("devops_mcp.tools.kubernetes", None)

    from devops_mcp.tools import kubernetes
    import importlib
    kubernetes = importlib.import_module("devops_mcp.tools.kubernetes")

    mcp = _FakeMCP()
    kubernetes.register(mcp, no_audit)

    result = json.loads(mcp.tools["k8s_get_failing_pods"](namespace="production"))
    assert isinstance(result, list)
    assert len(result) > 0
    for pod in result:
        assert pod["status"] not in ("Running", "Succeeded")


def test_get_failing_pods_crashloop(no_audit):
    """Demo mode should include a CrashLoopBackOff pod."""
    sys.modules.pop("kubernetes", None)
    sys.modules.pop("devops_mcp.tools.kubernetes", None)

    from devops_mcp.tools import kubernetes
    import importlib
    kubernetes = importlib.import_module("devops_mcp.tools.kubernetes")

    mcp = _FakeMCP()
    kubernetes.register(mcp, no_audit)

    result = json.loads(mcp.tools["k8s_get_failing_pods"](namespace="production"))
    statuses = {p["status"] for p in result}
    assert "CrashLoopBackOff" in statuses


def test_pod_logs_returns_string(no_audit):
    sys.modules.pop("kubernetes", None)
    sys.modules.pop("devops_mcp.tools.kubernetes", None)

    from devops_mcp.tools import kubernetes
    import importlib
    kubernetes = importlib.import_module("devops_mcp.tools.kubernetes")

    mcp = _FakeMCP()
    kubernetes.register(mcp, no_audit)

    result = mcp.tools["k8s_pod_logs"](pod_name="api-server-7d9f8b-xk2pq", namespace="production")
    assert isinstance(result, str)
    assert "ERROR" in result


def test_describe_pod_has_required_keys(no_audit):
    sys.modules.pop("kubernetes", None)
    sys.modules.pop("devops_mcp.tools.kubernetes", None)

    from devops_mcp.tools import kubernetes
    import importlib
    kubernetes = importlib.import_module("devops_mcp.tools.kubernetes")

    mcp = _FakeMCP()
    kubernetes.register(mcp, no_audit)

    result = json.loads(mcp.tools["k8s_describe_pod"](pod_name="api-server-7d9f8b-xk2pq"))
    for key in ("name", "namespace", "status", "containers"):
        assert key in result


def test_deployment_status_shows_unavailable(no_audit):
    sys.modules.pop("kubernetes", None)
    sys.modules.pop("devops_mcp.tools.kubernetes", None)

    from devops_mcp.tools import kubernetes
    import importlib
    kubernetes = importlib.import_module("devops_mcp.tools.kubernetes")

    mcp = _FakeMCP()
    kubernetes.register(mcp, no_audit)

    result = json.loads(mcp.tools["k8s_get_deployment_status"](deployment_name="api-server"))
    assert result["unavailable"] > 0
    assert result["ready"] < result["desired"]
