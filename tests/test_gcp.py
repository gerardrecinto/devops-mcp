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


def _fresh_gcp():
    for key in list(sys.modules.keys()):
        if "google" in key or key == "devops_mcp.tools.gcp":
            sys.modules.pop(key, None)
    import importlib

    return importlib.import_module("devops_mcp.tools.gcp")


def test_get_logs_demo_returns_entries(no_audit):
    gcp = _fresh_gcp()
    mcp = _FakeMCP()
    gcp.register(mcp, no_audit)

    result = json.loads(mcp.tools["gcp_get_logs"](filter_str='severity="ERROR"'))
    assert isinstance(result, list)
    assert len(result) > 0
    assert "ERROR" in [e["severity"] for e in result]


def test_get_metric_demo_returns_points(no_audit):
    gcp = _fresh_gcp()
    mcp = _FakeMCP()
    gcp.register(mcp, no_audit)

    result = json.loads(
        mcp.tools["gcp_get_metric"](
            metric_type="compute.googleapis.com/instance/cpu/utilization"
        )
    )
    assert isinstance(result, list)
    assert len(result) > 0
    assert "value" in result[0]


def test_gke_status_demo_returns_running(no_audit):
    gcp = _fresh_gcp()
    mcp = _FakeMCP()
    gcp.register(mcp, no_audit)

    result = json.loads(
        mcp.tools["gcp_get_gke_cluster_status"](
            cluster_name="prod-cluster", location="us-central1"
        )
    )
    assert result["status"] == "RUNNING"
    assert len(result["node_pools"]) > 0


def test_cloud_run_demo_returns_uri(no_audit):
    gcp = _fresh_gcp()
    mcp = _FakeMCP()
    gcp.register(mcp, no_audit)

    result = json.loads(
        mcp.tools["gcp_get_cloud_run_status"](
            service_name="api-service", region="us-central1"
        )
    )
    assert "uri" in result
    assert result["traffic"][0]["percent"] == 100
