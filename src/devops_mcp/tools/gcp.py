from __future__ import annotations

import json
import os
from datetime import datetime, timedelta, timezone
from typing import Any, Callable


def register(mcp: Any, audit: Callable[[str, dict], None]) -> None:
    try:
        from google.cloud import logging as gcp_logging  # type: ignore
        from google.cloud import monitoring_v3  # type: ignore
        from google.cloud import container_v1  # type: ignore
        from google.cloud import run_v2  # type: ignore

        default_project = os.getenv("GCP_PROJECT_ID", "")

        @mcp.tool()
        def gcp_get_logs(
            filter_str: str,
            hours: int = 1,
            project: str = "",
        ) -> str:
            """Query Cloud Logging using a GCP log filter expression."""
            pid = project or default_project
            audit("gcp_get_logs", {"project": pid, "filter": filter_str})
            client = gcp_logging.Client(project=pid)
            end = datetime.now(timezone.utc)
            start = end - timedelta(hours=hours)
            time_filter = f'timestamp>="{start.isoformat()}" AND timestamp<="{end.isoformat()}"'
            full_filter = f"({filter_str}) AND {time_filter}" if filter_str else time_filter
            entries = []
            for entry in client.list_entries(filter_=full_filter, max_results=100):
                entries.append({
                    "timestamp": str(entry.timestamp),
                    "severity": str(entry.severity),
                    "resource_type": entry.resource.type if entry.resource else None,
                    "payload": str(entry.payload),
                })
            if not entries:
                return json.dumps({"message": "No log entries found."})
            return json.dumps(entries, indent=2)

        @mcp.tool()
        def gcp_get_metric(
            metric_type: str,
            minutes: int = 60,
            project: str = "",
        ) -> str:
            """
            Query a Cloud Monitoring metric.
            metric_type example: 'compute.googleapis.com/instance/cpu/utilization'
            """
            pid = project or default_project
            audit("gcp_get_metric", {"project": pid, "metric_type": metric_type})
            from google.protobuf.timestamp_pb2 import Timestamp  # type: ignore
            client = monitoring_v3.MetricServiceClient()
            end = datetime.now(timezone.utc)
            start = end - timedelta(minutes=minutes)
            interval = monitoring_v3.TimeInterval(
                start_time=Timestamp(seconds=int(start.timestamp())),
                end_time=Timestamp(seconds=int(end.timestamp())),
            )
            results = client.list_time_series(
                request={
                    "name": f"projects/{pid}",
                    "filter": f'metric.type="{metric_type}"',
                    "interval": interval,
                    "view": monitoring_v3.ListTimeSeriesRequest.TimeSeriesView.FULL,
                }
            )
            points = []
            for ts in results:
                labels = dict(ts.metric.labels)
                for point in ts.points:
                    val = point.value
                    points.append({
                        "timestamp": str(datetime.fromtimestamp(point.interval.end_time.seconds, tz=timezone.utc)),
                        "labels": labels,
                        "value": val.double_value or val.int64_value or val.bool_value,
                    })
            if not points:
                return json.dumps({"message": "No data points found."})
            return json.dumps(points[:100], indent=2)

        @mcp.tool()
        def gcp_get_gke_cluster_status(
            cluster_name: str,
            location: str,
            project: str = "",
        ) -> str:
            """Get GKE cluster status including node pool counts and Kubernetes version."""
            pid = project or default_project
            audit("gcp_get_gke_cluster_status", {"project": pid, "cluster": cluster_name, "location": location})
            client = container_v1.ClusterManagerClient()
            name = f"projects/{pid}/locations/{location}/clusters/{cluster_name}"
            cluster = client.get_cluster(name=name)
            pools = [
                {
                    "name": pool.name,
                    "status": pool.status.name,
                    "node_count": pool.initial_node_count,
                    "machine_type": pool.config.machine_type if pool.config else None,
                    "version": pool.version,
                }
                for pool in cluster.node_pools
            ]
            return json.dumps({
                "cluster": cluster.name,
                "location": cluster.location,
                "status": cluster.status.name,
                "kubernetes_version": cluster.current_master_version,
                "node_count": cluster.current_node_count,
                "node_pools": pools,
            }, indent=2)

        @mcp.tool()
        def gcp_get_cloud_run_status(
            service_name: str,
            region: str,
            project: str = "",
        ) -> str:
            """Get Cloud Run service revision status and traffic split."""
            pid = project or default_project
            audit("gcp_get_cloud_run_status", {"project": pid, "service": service_name, "region": region})
            client = run_v2.ServicesClient()
            name = f"projects/{pid}/locations/{region}/services/{service_name}"
            service = client.get_service(name=name)
            return json.dumps({
                "service": service_name,
                "region": region,
                "uri": service.uri,
                "latest_ready_revision": service.latest_ready_revision,
                "conditions": [
                    {"type": c.type_, "state": c.state.name, "message": c.message}
                    for c in service.conditions
                ],
                "traffic": [
                    {"revision": t.revision, "percent": t.percent, "tag": t.tag}
                    for t in service.traffic
                ],
            }, indent=2)

    except ImportError:

        @mcp.tool()
        def gcp_get_logs(  # type: ignore[misc]
            filter_str: str,
            hours: int = 1,
            project: str = "",
        ) -> str:
            """Query Cloud Logging. (demo mode -- google-cloud-logging not installed)"""
            audit("gcp_get_logs", {"filter": filter_str})
            return json.dumps([
                {"timestamp": "2024-01-15T09:08:00+00:00", "severity": "ERROR", "resource_type": "k8s_container", "payload": "OOMKilled: container exceeded memory limit"},
                {"timestamp": "2024-01-15T09:08:02+00:00", "severity": "WARNING", "resource_type": "k8s_container", "payload": "Readiness probe failed: connection refused"},
                {"timestamp": "2024-01-15T09:09:15+00:00", "severity": "ERROR", "resource_type": "cloudsql_database", "payload": "Too many connections: max_connections=100 reached"},
            ], indent=2)

        @mcp.tool()
        def gcp_get_metric(  # type: ignore[misc]
            metric_type: str,
            minutes: int = 60,
            project: str = "",
        ) -> str:
            """Query Cloud Monitoring metric. (demo mode)"""
            audit("gcp_get_metric", {"metric_type": metric_type})
            return json.dumps([
                {"timestamp": "2024-01-15T09:00:00+00:00", "labels": {"instance_name": "web-01"}, "value": 0.23},
                {"timestamp": "2024-01-15T09:05:00+00:00", "labels": {"instance_name": "web-01"}, "value": 0.71},
                {"timestamp": "2024-01-15T09:10:00+00:00", "labels": {"instance_name": "web-01"}, "value": 0.94},
            ], indent=2)

        @mcp.tool()
        def gcp_get_gke_cluster_status(  # type: ignore[misc]
            cluster_name: str,
            location: str,
            project: str = "",
        ) -> str:
            """Get GKE cluster status. (demo mode)"""
            audit("gcp_get_gke_cluster_status", {"cluster": cluster_name, "location": location})
            return json.dumps({
                "cluster": cluster_name,
                "location": location,
                "status": "RUNNING",
                "kubernetes_version": "1.29.4-gke.1043001",
                "node_count": 9,
                "node_pools": [
                    {"name": "default-pool", "status": "RUNNING", "node_count": 3, "machine_type": "e2-standard-4", "version": "1.29.4-gke.1043001"},
                    {"name": "highmem-pool", "status": "RUNNING", "node_count": 6, "machine_type": "n2-highmem-8", "version": "1.29.4-gke.1043001"},
                ],
            }, indent=2)

        @mcp.tool()
        def gcp_get_cloud_run_status(  # type: ignore[misc]
            service_name: str,
            region: str,
            project: str = "",
        ) -> str:
            """Get Cloud Run service status. (demo mode)"""
            audit("gcp_get_cloud_run_status", {"service": service_name, "region": region})
            return json.dumps({
                "service": service_name,
                "region": region,
                "uri": f"https://{service_name}-abc123-uc.a.run.app",
                "latest_ready_revision": f"{service_name}-00042-xyz",
                "conditions": [
                    {"type": "Ready", "state": "CONDITION_SUCCEEDED", "message": ""},
                    {"type": "ConfigurationsReady", "state": "CONDITION_SUCCEEDED", "message": ""},
                ],
                "traffic": [
                    {"revision": f"{service_name}-00042-xyz", "percent": 100, "tag": ""},
                ],
            }, indent=2)
