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


def _fresh_azure():
    for key in list(sys.modules.keys()):
        if "azure" in key or key == "devops_mcp.tools.azure":
            sys.modules.pop(key, None)
    import importlib

    return importlib.import_module("devops_mcp.tools.azure")


def test_monitor_logs_demo_returns_events(no_audit):
    azure = _fresh_azure()
    mcp = _FakeMCP()
    azure.register(mcp, no_audit)

    result = json.loads(
        mcp.tools["azure_get_monitor_logs"](
            workspace_id="ws-123", query="AzureActivity | limit 10"
        )
    )
    assert isinstance(result, list)
    assert len(result) > 0
    assert "Error" in [r["Level"] for r in result]


def test_get_metric_demo_returns_datapoints(no_audit):
    azure = _fresh_azure()
    mcp = _FakeMCP()
    azure.register(mcp, no_audit)

    result = json.loads(
        mcp.tools["azure_get_metric"](
            resource_uri="/subscriptions/sub/resourceGroups/rg/providers/Microsoft.Compute/virtualMachines/vm-01",
            metric_name="Percentage CPU",
        )
    )
    assert isinstance(result, list)
    assert len(result) > 0
    assert "Average" in result[0]


def test_aks_node_status_demo_returns_pools(no_audit):
    azure = _fresh_azure()
    mcp = _FakeMCP()
    azure.register(mcp, no_audit)

    result = json.loads(
        mcp.tools["azure_get_aks_node_status"](
            resource_group="myRG", cluster_name="prod-aks"
        )
    )
    assert result["provisioning_state"] == "Succeeded"
    assert len(result["agent_pools"]) > 0


def test_resource_health_demo_returns_available(no_audit):
    azure = _fresh_azure()
    mcp = _FakeMCP()
    azure.register(mcp, no_audit)

    result = json.loads(
        mcp.tools["azure_get_resource_health"](
            resource_uri="/subscriptions/sub/resourceGroups/rg/providers/Microsoft.Compute/virtualMachines/vm-01"
        )
    )
    assert result["availability_state"] == "Available"
