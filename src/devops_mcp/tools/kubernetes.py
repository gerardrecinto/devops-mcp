from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Callable

_SERVICE_ACCOUNT_TOKEN = Path("/var/run/secrets/kubernetes.io/serviceaccount/token")


def _kube_configured() -> bool:
    """Whether we have any plausible way to reach a cluster.

    Mirrors the credential-presence check the other tool modules use
    (jenkins, slack, teams, servicenow) instead of only guarding on
    ImportError, since the kubernetes client is a hard dependency and is
    always importable.
    """
    if os.getenv("KUBECONFIG"):
        return True
    if _SERVICE_ACCOUNT_TOKEN.exists():
        return True
    return (Path.home() / ".kube" / "config").exists()


def _demo_failing_pods() -> list[dict[str, Any]]:
    return [
        {
            "namespace": "production",
            "name": "api-server-7d9f8b-xk2pq",
            "status": "CrashLoopBackOff",
            "restarts": 14,
            "message": "Back-off restarting failed container",
        }
    ]


def _demo_pod_logs() -> str:
    return (
        "[2024-01-15 03:42:11] ERROR  Failed to connect to database: connection refused\n"
        "[2024-01-15 03:42:11] FATAL  Startup probe failed, exiting\n"
    )


def _demo_describe_pod() -> dict[str, Any]:
    return {
        "name": "api-server-7d9f8b-xk2pq",
        "namespace": "production",
        "node": "node-west-2a",
        "status": "CrashLoopBackOff",
        "containers": [
            {
                "name": "api-server",
                "image": "myapp/api-server:v1.4.2",
                "ready": False,
                "restarts": 14,
                "last_state": "OOMKilled",
            }
        ],
        "events": [
            "Back-off restarting failed container api-server",
            "Liveness probe failed: HTTP probe failed with statuscode: 500",
        ],
    }


def _demo_events() -> list[dict[str, Any]]:
    return [
        {
            "type": "Warning",
            "reason": "BackOff",
            "namespace": "production",
            "object": "Pod/api-server-7d9f8b-xk2pq",
            "message": "Back-off restarting failed container",
            "count": 47,
        },
        {
            "type": "Warning",
            "reason": "OOMKilling",
            "namespace": "production",
            "object": "Pod/worker-6c5d7f-mn3rs",
            "message": "Memory limit reached, killing container",
            "count": 3,
        },
    ]


def _demo_deployment_status() -> dict[str, Any]:
    return {
        "name": "api-server",
        "namespace": "production",
        "desired": 3,
        "ready": 1,
        "available": 1,
        "unavailable": 2,
        "image": "myapp/api-server:v1.4.2",
        "conditions": [
            {
                "type": "Available",
                "status": "False",
                "reason": "MinimumReplicasUnavailable",
            }
        ],
    }


def register(mcp: Any, audit: Callable[[str, dict], None]) -> None:
    try:
        from kubernetes import client, config  # type: ignore

        def _core() -> client.CoreV1Api:
            try:
                config.load_incluster_config()
            except config.ConfigException:
                config.load_kube_config()
            return client.CoreV1Api()

        def _apps() -> client.AppsV1Api:
            try:
                config.load_incluster_config()
            except config.ConfigException:
                config.load_kube_config()
            return client.AppsV1Api()

        @mcp.tool()
        def k8s_get_failing_pods(namespace: str = "default") -> str:
            """List pods not in Running/Succeeded state."""
            audit("k8s_get_failing_pods", {"namespace": namespace})
            if not _kube_configured():
                return json.dumps(_demo_failing_pods(), indent=2)
            v1 = _core()
            pods = v1.list_namespaced_pod(namespace=namespace)
            failing = [
                {
                    "name": p.metadata.name,
                    "namespace": p.metadata.namespace,
                    "status": p.status.phase,
                    "restarts": sum(
                        cs.restart_count for cs in (p.status.container_statuses or [])
                    ),
                }
                for p in pods.items
                if p.status.phase not in ("Running", "Succeeded")
            ]
            return json.dumps(failing, indent=2)

        @mcp.tool()
        def k8s_pod_logs(
            pod_name: str, namespace: str = "default", tail_lines: int = 100
        ) -> str:
            """Fetch recent logs from a pod."""
            audit(
                "k8s_pod_logs",
                {
                    "pod_name": pod_name,
                    "namespace": namespace,
                    "tail_lines": tail_lines,
                },
            )
            if not _kube_configured():
                return _demo_pod_logs()
            v1 = _core()
            return v1.read_namespaced_pod_log(
                name=pod_name, namespace=namespace, tail_lines=tail_lines
            )

        @mcp.tool()
        def k8s_describe_pod(pod_name: str, namespace: str = "default") -> str:
            """Describe a pod: status, containers, recent events."""
            audit("k8s_describe_pod", {"pod_name": pod_name, "namespace": namespace})
            if not _kube_configured():
                return json.dumps(_demo_describe_pod(), indent=2)
            v1 = _core()
            pod = v1.read_namespaced_pod(name=pod_name, namespace=namespace)
            result = {
                "name": pod.metadata.name,
                "namespace": pod.metadata.namespace,
                "node": pod.spec.node_name,
                "status": pod.status.phase,
                "containers": [
                    {
                        "name": cs.name,
                        "image": cs.image,
                        "ready": cs.ready,
                        "restarts": cs.restart_count,
                    }
                    for cs in (pod.status.container_statuses or [])
                ],
            }
            return json.dumps(result, indent=2)

        @mcp.tool()
        def k8s_get_events(namespace: str = "default", field_selector: str = "") -> str:
            """List cluster events, optionally filtered by field selector."""
            audit(
                "k8s_get_events",
                {"namespace": namespace, "field_selector": field_selector},
            )
            if not _kube_configured():
                return json.dumps(_demo_events(), indent=2)
            v1 = _core()
            kwargs = {"namespace": namespace}
            if field_selector:
                kwargs["field_selector"] = field_selector
            events = v1.list_namespaced_event(**kwargs)
            result = [
                {
                    "type": e.type,
                    "reason": e.reason,
                    "object": f"{e.involved_object.kind}/{e.involved_object.name}",
                    "message": e.message,
                    "count": e.count,
                }
                for e in events.items
            ]
            return json.dumps(result, indent=2)

        @mcp.tool()
        def k8s_get_deployment_status(
            deployment_name: str, namespace: str = "default"
        ) -> str:
            """Get rollout status of a deployment."""
            audit(
                "k8s_get_deployment_status",
                {"deployment_name": deployment_name, "namespace": namespace},
            )
            if not _kube_configured():
                return json.dumps(_demo_deployment_status(), indent=2)
            v1 = _apps()
            d = v1.read_namespaced_deployment(name=deployment_name, namespace=namespace)
            result = {
                "name": d.metadata.name,
                "namespace": d.metadata.namespace,
                "desired": d.spec.replicas,
                "ready": d.status.ready_replicas or 0,
                "available": d.status.available_replicas or 0,
                "unavailable": d.status.unavailable_replicas or 0,
                "image": (
                    d.spec.template.spec.containers[0].image
                    if d.spec.template.spec.containers
                    else None
                ),
                "conditions": [
                    {"type": c.type, "status": c.status, "reason": c.reason}
                    for c in (d.status.conditions or [])
                ],
            }
            return json.dumps(result, indent=2)

    except ImportError:

        @mcp.tool()
        def k8s_get_failing_pods(namespace: str = "default") -> str:  # type: ignore[misc]
            """List pods not in Running/Succeeded state. (demo mode — kubernetes not installed)"""
            audit("k8s_get_failing_pods", {"namespace": namespace})
            return json.dumps(_demo_failing_pods(), indent=2)

        @mcp.tool()
        def k8s_pod_logs(pod_name: str, namespace: str = "default", tail_lines: int = 100) -> str:  # type: ignore[misc]
            """Fetch recent logs from a pod. (demo mode)"""
            audit(
                "k8s_pod_logs",
                {
                    "pod_name": pod_name,
                    "namespace": namespace,
                    "tail_lines": tail_lines,
                },
            )
            return _demo_pod_logs()

        @mcp.tool()
        def k8s_describe_pod(pod_name: str, namespace: str = "default") -> str:  # type: ignore[misc]
            """Describe a pod. (demo mode)"""
            audit("k8s_describe_pod", {"pod_name": pod_name, "namespace": namespace})
            return json.dumps(_demo_describe_pod(), indent=2)

        @mcp.tool()
        def k8s_get_events(namespace: str = "default", field_selector: str = "") -> str:  # type: ignore[misc]
            """List cluster events. (demo mode)"""
            audit(
                "k8s_get_events",
                {"namespace": namespace, "field_selector": field_selector},
            )
            return json.dumps(_demo_events(), indent=2)

        @mcp.tool()
        def k8s_get_deployment_status(deployment_name: str, namespace: str = "default") -> str:  # type: ignore[misc]
            """Get rollout status of a deployment. (demo mode)"""
            audit(
                "k8s_get_deployment_status",
                {"deployment_name": deployment_name, "namespace": namespace},
            )
            return json.dumps(_demo_deployment_status(), indent=2)
