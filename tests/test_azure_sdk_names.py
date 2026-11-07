import pytest


def test_azure_monitor_query_names_used_by_the_azure_tools_exist():
    """The Azure tools import these names lazily, so a missing one only shows up at call time.
    This fails when a new azure-monitor-query release removes or renames one of them."""
    pytest.importorskip("azure.monitor.query")
    from azure.monitor.query import (  # noqa: F401
        LogsQueryClient,
        LogsQueryStatus,
        MetricAggregationType,
        MetricsQueryClient,
    )
