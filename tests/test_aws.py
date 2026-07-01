import importlib
import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch


class _FakeMCP:
    def __init__(self):
        self.tools = {}

    def tool(self):
        def decorator(fn):
            self.tools[fn.__name__] = fn
            return fn

        return decorator


def _register_configured(monkeypatch, audit):
    """Register the aws tool module with AWS credentials present in the
    environment, exercising the real (non-demo) code path."""
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "fake-key-id")
    sys.modules.pop("devops_mcp.tools.aws", None)
    aws = importlib.import_module("devops_mcp.tools.aws")
    mcp = _FakeMCP()
    aws.register(mcp, audit)
    return aws, mcp


def test_cloudwatch_logs_returns_events(monkeypatch, no_audit):
    _, mcp = _register_configured(monkeypatch, no_audit)

    fake_client = MagicMock()
    fake_client.filter_log_events.return_value = {
        "events": [
            {
                "timestamp": 1705305600000,
                "message": "ERROR db connection pool exhausted\n",
            },
            {"timestamp": 1705305601000, "message": "WARN retrying connection\n"},
        ]
    }
    with patch("boto3.client", return_value=fake_client):
        result = json.loads(
            mcp.tools["aws_get_cloudwatch_logs"](log_group="/app/backend")
        )

    assert isinstance(result, list)
    assert len(result) == 2
    messages = " ".join(e["message"] for e in result)
    assert "ERROR" in messages


def test_get_metric_returns_datapoints(monkeypatch, no_audit):
    _, mcp = _register_configured(monkeypatch, no_audit)

    fake_client = MagicMock()
    fake_client.get_metric_statistics.return_value = {
        "Datapoints": [
            {"Timestamp": "2024-01-15T03:00:00Z", "Average": 12.4},
            {"Timestamp": "2024-01-15T03:05:00Z", "Average": 67.1},
        ]
    }
    with patch("boto3.client", return_value=fake_client):
        result = json.loads(
            mcp.tools["aws_get_metric"](
                namespace="AWS/ECS", metric_name="CPUUtilization"
            )
        )

    assert isinstance(result, list)
    assert len(result) == 2
    assert "Average" in result[0]


def test_describe_s3_bucket_returns_config(monkeypatch, no_audit):
    _, mcp = _register_configured(monkeypatch, no_audit)

    fake_client = MagicMock()
    fake_client.get_bucket_location.return_value = {"LocationConstraint": "us-west-2"}
    fake_client.get_bucket_versioning.return_value = {"Status": "Enabled"}
    fake_client.get_bucket_lifecycle_configuration.return_value = {"Rules": [{}, {}]}
    with patch("boto3.client", return_value=fake_client):
        result = json.loads(
            mcp.tools["aws_describe_s3_bucket"](bucket_name="my-bucket")
        )

    assert result["region"] == "us-west-2"
    assert result["versioning"] == "Enabled"
    assert result["lifecycle_rules"] == 2


def test_ecs_service_status_shows_degraded(monkeypatch, no_audit):
    _, mcp = _register_configured(monkeypatch, no_audit)

    fake_client = MagicMock()
    fake_client.describe_services.return_value = {
        "services": [
            {
                "serviceName": "api-service",
                "status": "ACTIVE",
                "desiredCount": 3,
                "runningCount": 1,
                "pendingCount": 0,
                "deployments": [
                    {
                        "status": "PRIMARY",
                        "desiredCount": 3,
                        "runningCount": 1,
                        "failedTasks": 2,
                    }
                ],
            }
        ]
    }
    with patch("boto3.client", return_value=fake_client):
        result = json.loads(
            mcp.tools["aws_get_ecs_service_status"](
                cluster="prod-cluster", service="api-service"
            )
        )

    assert result["running"] < result["desired"]
    assert result["deployments"][0]["failed_tasks"] > 0


def test_demo_mode_without_credentials(monkeypatch, no_audit):
    """No AWS env markers, no ~/.aws/credentials: falls back to demo data
    instead of attempting a real, unauthenticated AWS call."""
    for key in (
        "AWS_ACCESS_KEY_ID",
        "AWS_PROFILE",
        "AWS_CONTAINER_CREDENTIALS_RELATIVE_URI",
        "AWS_CONTAINER_CREDENTIALS_FULL_URI",
        "AWS_ROLE_ARN",
    ):
        monkeypatch.delenv(key, raising=False)

    sys.modules.pop("devops_mcp.tools.aws", None)
    aws = importlib.import_module("devops_mcp.tools.aws")
    monkeypatch.setattr(Path, "home", lambda: Path("/nonexistent/home"))

    mcp = _FakeMCP()
    aws.register(mcp, no_audit)

    result = json.loads(mcp.tools["aws_get_cloudwatch_logs"](log_group="/app/backend"))
    messages = " ".join(e["message"] for e in result)
    assert "ERROR" in messages


def test_demo_mode_when_boto3_unavailable(monkeypatch, no_audit):
    monkeypatch.setitem(sys.modules, "boto3", None)
    sys.modules.pop("devops_mcp.tools.aws", None)

    aws = importlib.import_module("devops_mcp.tools.aws")
    mcp = _FakeMCP()
    aws.register(mcp, no_audit)

    result = json.loads(mcp.tools["aws_get_cloudwatch_logs"](log_group="/app/backend"))
    messages = " ".join(e["message"] for e in result)
    assert "ERROR" in messages
