from __future__ import annotations

import json
import os
from datetime import datetime, timedelta, timezone
from typing import Any, Callable


def register(mcp: Any, audit: Callable[[str, dict], None]) -> None:
    try:
        from azure.identity import DefaultAzureCredential  # type: ignore
        from azure.monitor.query import LogsQueryClient, LogsQueryStatus, MetricsQueryClient  # type: ignore
        from azure.mgmt.containerservice import ContainerServiceClient  # type: ignore

        subscription_id = os.getenv("AZURE_SUBSCRIPTION_ID", "")
        credential = DefaultAzureCredential()

        @mcp.tool()
        def azure_get_monitor_logs(
            workspace_id: str,
            query: str,
            hours: int = 1,
        ) -> str:
            """Run a KQL query against an Azure Log Analytics workspace."""
            audit("azure_get_monitor_logs", {"workspace_id": workspace_id, "query": query})
            client = LogsQueryClient(credential)
            end = datetime.now(timezone.utc)
            start = end - timedelta(hours=hours)
            response = client.query_workspace(
                workspace_id=workspace_id,
                query=query,
                timespan=(start, end),
            )
            if response.status == LogsQueryStatus.SUCCESS:
                rows = []
                for table in response.tables:
                    for row in table.rows:
                        rows.append(dict(zip(table.columns, row)))
                if not rows:
                    return json.dumps({"message": "No results returned."})
                return json.dumps(rows[:100], indent=2, default=str)
            return json.dumps({"error": "Query failed", "details": str(response.partial_error)})

        @mcp.tool()
        def azure_get_metric(
            resource_uri: str,
            metric_name: str,
            minutes: int = 60,
            aggregation: str = "Average",
        ) -> str:
            """
            Get an Azure Monitor metric for any resource (VM, App Service, AKS, etc.).
            resource_uri: full ARM resource ID
            """
            audit("azure_get_metric", {"resource_uri": resource_uri, "metric_name": metric_name})
            from azure.monitor.query import MetricAggregationType  # type: ignore
            agg_map = {
                "Average": MetricAggregationType.AVERAGE,
                "Total": MetricAggregationType.TOTAL,
                "Maximum": MetricAggregationType.MAXIMUM,
                "Minimum": MetricAggregationType.MINIMUM,
                "Count": MetricAggregationType.COUNT,
            }
            client = MetricsQueryClient(credential)
            end = datetime.now(timezone.utc)
            start = end - timedelta(minutes=minutes)
            response = client.query_resource(
                resource_uri=resource_uri,
                metric_names=[metric_name],
                timespan=(start, end),
                granularity=timedelta(minutes=5),
                aggregations=[agg_map.get(aggregation, MetricAggregationType.AVERAGE)],
            )
            results = []
            for metric in response.metrics:
                for ts in metric.timeseries:
                    for point in ts.data:
                        val = getattr(point, aggregation.lower(), None)
                        if val is not None:
                            results.append({"timestamp": str(point.timestamp), aggregation: val})
            return json.dumps(results, indent=2)

        @mcp.tool()
        def azure_get_aks_node_status(resource_group: str, cluster_name: str) -> str:
            """Get AKS cluster agent pool provisioning state and node counts."""
            audit("azure_get_aks_node_status", {"resource_group": resource_group, "cluster_name": cluster_name})
            client = ContainerServiceClient(credential, subscription_id)
            cluster = client.managed_clusters.get(resource_group, cluster_name)
            pools = [
                {
                    "name": pool.name,
                    "provisioning_state": pool.provisioning_state,
                    "vm_size": pool.vm_size,
                    "count": pool.count,
                    "os_type": pool.os_type,
                    "mode": pool.mode,
                }
                for pool in (cluster.agent_pool_profiles or [])
            ]
            return json.dumps({
                "cluster": cluster_name,
                "kubernetes_version": cluster.kubernetes_version,
                "provisioning_state": cluster.provisioning_state,
                "power_state": cluster.power_state.code if cluster.power_state else "Unknown",
                "agent_pools": pools,
            }, indent=2)

        @mcp.tool()
        def azure_get_resource_health(resource_uri: str) -> str:
            """Get Azure Resource Health availability status for any ARM resource."""
            audit("azure_get_resource_health", {"resource_uri": resource_uri})
            import requests as _req  # type: ignore
            token = credential.get_token("https://management.azure.com/.default").token
            url = (
                f"https://management.azure.com{resource_uri}"
                "/providers/Microsoft.ResourceHealth/availabilityStatuses/current"
                "?api-version=2022-10-01"
            )
            resp = _req.get(url, headers={"Authorization": f"Bearer {token}"}, timeout=15)
            resp.raise_for_status()
            props = resp.json().get("properties", {})
            return json.dumps({
                "resource_uri": resource_uri,
                "availability_state": props.get("availabilityState"),
                "summary": props.get("summary"),
                "reason_type": props.get("reasonType"),
                "occurred_time": props.get("occurredTime"),
            }, indent=2)

    except ImportError:

        @mcp.tool()
        def azure_get_monitor_logs(  # type: ignore[misc]
            workspace_id: str,
            query: str,
            hours: int = 1,
        ) -> str:
            """Run a KQL query against Log Analytics. (demo mode -- azure-monitor-query not installed)"""
            audit("azure_get_monitor_logs", {"workspace_id": workspace_id, "query": query})
            return json.dumps([
                {"TimeGenerated": "2024-01-15T09:08:12Z", "Level": "Error", "Message": "Connection pool exhausted", "Computer": "aks-node-001"},
                {"TimeGenerated": "2024-01-15T09:08:14Z", "Level": "Warning", "Message": "Retry attempt 1 of 3", "Computer": "aks-node-001"},
                {"TimeGenerated": "2024-01-15T09:09:01Z", "Level": "Error", "Message": "Request timeout after 30s", "Computer": "aks-node-002"},
            ], indent=2)

        @mcp.tool()
        def azure_get_metric(  # type: ignore[misc]
            resource_uri: str,
            metric_name: str,
            minutes: int = 60,
            aggregation: str = "Average",
        ) -> str:
            """Get an Azure Monitor metric. (demo mode)"""
            audit("azure_get_metric", {"resource_uri": resource_uri, "metric_name": metric_name})
            return json.dumps([
                {"timestamp": "2024-01-15T09:00:00+00:00", aggregation: 18.3},
                {"timestamp": "2024-01-15T09:05:00+00:00", aggregation: 72.1},
                {"timestamp": "2024-01-15T09:10:00+00:00", aggregation: 91.4},
            ], indent=2)

        @mcp.tool()
        def azure_get_aks_node_status(resource_group: str, cluster_name: str) -> str:  # type: ignore[misc]
            """Get AKS cluster node status. (demo mode)"""
            audit("azure_get_aks_node_status", {"resource_group": resource_group, "cluster_name": cluster_name})
            return json.dumps({
                "cluster": cluster_name,
                "kubernetes_version": "1.29.2",
                "provisioning_state": "Succeeded",
                "power_state": "Running",
                "agent_pools": [
                    {"name": "system", "provisioning_state": "Succeeded", "vm_size": "Standard_D4s_v3", "count": 3, "os_type": "Linux", "mode": "System"},
                    {"name": "user", "provisioning_state": "Succeeded", "vm_size": "Standard_D8s_v3", "count": 5, "os_type": "Linux", "mode": "User"},
                ],
            }, indent=2)

        @mcp.tool()
        def azure_get_resource_health(resource_uri: str) -> str:  # type: ignore[misc]
            """Get Azure Resource Health status. (demo mode)"""
            audit("azure_get_resource_health", {"resource_uri": resource_uri})
            return json.dumps({
                "resource_uri": resource_uri,
                "availability_state": "Available",
                "summary": "This resource is healthy.",
                "reason_type": None,
                "occurred_time": None,
            }, indent=2)
