from __future__ import annotations

import json
import os
from datetime import datetime, timedelta, timezone
from typing import Any, Callable


def register(mcp: Any, audit: Callable[[str, dict], None]) -> None:
    try:
        import boto3  # type: ignore

        def _logs():
            return boto3.client("logs", region_name=os.getenv("AWS_REGION", "us-east-1"))

        def _cw():
            return boto3.client("cloudwatch", region_name=os.getenv("AWS_REGION", "us-east-1"))

        def _s3():
            return boto3.client("s3", region_name=os.getenv("AWS_REGION", "us-east-1"))

        def _ecs():
            return boto3.client("ecs", region_name=os.getenv("AWS_REGION", "us-east-1"))

        @mcp.tool()
        def aws_get_cloudwatch_logs(
            log_group: str,
            log_stream: str = "",
            minutes: int = 30,
            filter_pattern: str = "",
        ) -> str:
            """Fetch recent CloudWatch log events."""
            audit("aws_get_cloudwatch_logs", {"log_group": log_group, "log_stream": log_stream})
            client = _logs()
            end = datetime.now(timezone.utc)
            start = end - timedelta(minutes=minutes)
            kwargs: dict[str, Any] = {
                "logGroupName": log_group,
                "startTime": int(start.timestamp() * 1000),
                "endTime": int(end.timestamp() * 1000),
                "limit": 100,
            }
            if log_stream:
                kwargs["logStreamNames"] = [log_stream]
            if filter_pattern:
                kwargs["filterPattern"] = filter_pattern
            resp = client.filter_log_events(**kwargs)
            events = [
                {"timestamp": e["timestamp"], "message": e["message"].rstrip()}
                for e in resp.get("events", [])
            ]
            if not events:
                return json.dumps({"message": "No log events found in the specified time range."})
            return json.dumps(events, indent=2)

        @mcp.tool()
        def aws_get_metric(
            namespace: str,
            metric_name: str,
            dimensions: str = "",
            minutes: int = 60,
            stat: str = "Average",
        ) -> str:
            """
            Get CloudWatch metric statistics.
            dimensions format: 'Key1=Value1,Key2=Value2'
            """
            audit("aws_get_metric", {"namespace": namespace, "metric_name": metric_name})
            client = _cw()
            end = datetime.now(timezone.utc)
            start = end - timedelta(minutes=minutes)
            dims = []
            if dimensions:
                for pair in dimensions.split(","):
                    k, v = pair.strip().split("=")
                    dims.append({"Name": k.strip(), "Value": v.strip()})
            resp = client.get_metric_statistics(
                Namespace=namespace,
                MetricName=metric_name,
                Dimensions=dims,
                StartTime=start,
                EndTime=end,
                Period=300,
                Statistics=[stat],
            )
            points = sorted(resp["Datapoints"], key=lambda x: x["Timestamp"])
            return json.dumps(
                [{"timestamp": str(p["Timestamp"]), stat: p[stat]} for p in points],
                indent=2,
            )

        @mcp.tool()
        def aws_describe_s3_bucket(bucket_name: str) -> str:
            """Describe S3 bucket: region, versioning, lifecycle rules count."""
            audit("aws_describe_s3_bucket", {"bucket_name": bucket_name})
            client = _s3()
            location = client.get_bucket_location(Bucket=bucket_name)
            versioning = client.get_bucket_versioning(Bucket=bucket_name)
            try:
                lifecycle = client.get_bucket_lifecycle_configuration(Bucket=bucket_name)
                rule_count = len(lifecycle.get("Rules", []))
            except client.exceptions.ClientError:
                rule_count = 0
            return json.dumps(
                {
                    "bucket": bucket_name,
                    "region": location.get("LocationConstraint") or "us-east-1",
                    "versioning": versioning.get("Status", "Disabled"),
                    "lifecycle_rules": rule_count,
                },
                indent=2,
            )

        @mcp.tool()
        def aws_get_ecs_service_status(cluster: str, service: str) -> str:
            """Get ECS service running/desired task counts and deployment status."""
            audit("aws_get_ecs_service_status", {"cluster": cluster, "service": service})
            client = _ecs()
            resp = client.describe_services(cluster=cluster, services=[service])
            svc = resp["services"][0]
            return json.dumps(
                {
                    "service": svc["serviceName"],
                    "cluster": cluster,
                    "status": svc["status"],
                    "desired": svc["desiredCount"],
                    "running": svc["runningCount"],
                    "pending": svc["pendingCount"],
                    "deployments": [
                        {
                            "status": d["status"],
                            "desired": d["desiredCount"],
                            "running": d["runningCount"],
                            "failed_tasks": d["failedTasks"],
                        }
                        for d in svc.get("deployments", [])
                    ],
                },
                indent=2,
            )

    except ImportError:

        @mcp.tool()
        def aws_get_cloudwatch_logs(  # type: ignore[misc]
            log_group: str,
            log_stream: str = "",
            minutes: int = 30,
            filter_pattern: str = "",
        ) -> str:
            """Fetch CloudWatch log events. (demo mode — boto3 not installed)"""
            audit("aws_get_cloudwatch_logs", {"log_group": log_group})
            return json.dumps(
                [
                    {"timestamp": 1705305600000, "message": "ERROR  db connection pool exhausted"},
                    {"timestamp": 1705305601000, "message": "WARN   retrying connection (attempt 1/3)"},
                    {"timestamp": 1705305604000, "message": "ERROR  max retries exceeded, giving up"},
                ],
                indent=2,
            )

        @mcp.tool()
        def aws_get_metric(  # type: ignore[misc]
            namespace: str,
            metric_name: str,
            dimensions: str = "",
            minutes: int = 60,
            stat: str = "Average",
        ) -> str:
            """Get CloudWatch metric statistics. (demo mode)"""
            audit("aws_get_metric", {"namespace": namespace, "metric_name": metric_name})
            return json.dumps(
                [
                    {"timestamp": "2024-01-15 03:00:00+00:00", stat: 12.4},
                    {"timestamp": "2024-01-15 03:05:00+00:00", stat: 67.1},
                    {"timestamp": "2024-01-15 03:10:00+00:00", stat: 94.8},
                ],
                indent=2,
            )

        @mcp.tool()
        def aws_describe_s3_bucket(bucket_name: str) -> str:  # type: ignore[misc]
            """Describe S3 bucket. (demo mode)"""
            audit("aws_describe_s3_bucket", {"bucket_name": bucket_name})
            return json.dumps(
                {
                    "bucket": bucket_name,
                    "region": "us-east-1",
                    "versioning": "Enabled",
                    "lifecycle_rules": 3,
                },
                indent=2,
            )

        @mcp.tool()
        def aws_get_ecs_service_status(cluster: str, service: str) -> str:  # type: ignore[misc]
            """Get ECS service status. (demo mode)"""
            audit("aws_get_ecs_service_status", {"cluster": cluster, "service": service})
            return json.dumps(
                {
                    "service": service,
                    "cluster": cluster,
                    "status": "ACTIVE",
                    "desired": 3,
                    "running": 1,
                    "pending": 0,
                    "deployments": [
                        {"status": "PRIMARY", "desired": 3, "running": 1, "failed_tasks": 2}
                    ],
                },
                indent=2,
            )
