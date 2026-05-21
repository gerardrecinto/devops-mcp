import json
import sys
import pytest


class _FakeMCP:
    def __init__(self):
        self.tools = {}

    def tool(self):
        def decorator(fn):
            self.tools[fn.__name__] = fn
            return fn
        return decorator


def _fresh_aws():
    sys.modules.pop("boto3", None)
    sys.modules.pop("devops_mcp.tools.aws", None)
    import importlib
    return importlib.import_module("devops_mcp.tools.aws")


def test_cloudwatch_logs_demo_returns_events(no_audit):
    """Demo mode should return a list with at least one ERROR event."""
    aws = _fresh_aws()
    mcp = _FakeMCP()
    aws.register(mcp, no_audit)

    result = json.loads(mcp.tools["aws_get_cloudwatch_logs"](log_group="/app/backend"))
    assert isinstance(result, list)
    assert len(result) > 0
    messages = " ".join(e["message"] for e in result)
    assert "ERROR" in messages


def test_get_metric_demo_returns_datapoints(no_audit):
    aws = _fresh_aws()
    mcp = _FakeMCP()
    aws.register(mcp, no_audit)

    result = json.loads(
        mcp.tools["aws_get_metric"](
            namespace="AWS/ECS",
            metric_name="CPUUtilization",
        )
    )
    assert isinstance(result, list)
    assert len(result) > 0
    assert "Average" in result[0]


def test_ecs_service_status_demo_shows_degraded(no_audit):
    """Demo ECS service should show running < desired to reflect a degraded state."""
    aws = _fresh_aws()
    mcp = _FakeMCP()
    aws.register(mcp, no_audit)

    result = json.loads(
        mcp.tools["aws_get_ecs_service_status"](cluster="prod-cluster", service="api-service")
    )
    assert result["running"] < result["desired"]
    assert result["deployments"][0]["failed_tasks"] > 0
