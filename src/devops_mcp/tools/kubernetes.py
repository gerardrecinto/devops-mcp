from __future__ import annotations

import json
import os
from collections.abc import Callable
from pathlib import Path
from typing import Any

from devops_mcp.demo import demo_response

_SERVICE_ACCOUNT_TOKEN = Path("/var/run/secrets/kubernetes.io/serviceaccount/token")


_LOG_LIMIT_BYTES = 256 * 1024


def _mark_truncated(text: str) -> str:
    """The API stops at the byte limit; say so instead of returning a silent cut."""
    if len(text.encode()) < _LOG_LIMIT_BYTES:
        return text
    return text + f"\n[truncated: output capped at {_LOG_LIMIT_BYTES // 1024} KiB]"


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


def _event_time(event: Any) -> str | None:
    """Most recent time the event fired, as ISO-8601, or None if unknown."""
    meta = getattr(event, "metadata", None)
    ts = (
        getattr(event, "last_timestamp", None)
        or getattr(event, "event_time", None)
        or getattr(meta, "creation_timestamp", None)
    )
    return ts.isoformat() if ts else None


def _pod_problem(pod: Any) -> dict[str, Any] | None:
    """Describe why a pod is unhealthy, or None if it is fine.

    A crash-looping pod has phase "Running"; the reason lives on the container
    state, so checking the phase alone misses CrashLoopBackOff and ImagePullBackOff.
    """
    phase = pod.status.phase
    if phase == "Succeeded":
        return None
    statuses = pod.status.container_statuses or []
    reason = message = None
    for cs in statuses:
        state = cs.state
        waiting = state.waiting if state else None
        terminated = state.terminated if state else None
        if waiting and waiting.reason:
            reason, message = waiting.reason, waiting.message
            break
        if terminated and terminated.exit_code != 0:
            reason = terminated.reason or f"exit {terminated.exit_code}"
            message = terminated.message
            break
    if phase == "Running" and reason is None:
        if all(cs.ready for cs in statuses):
            return None
        reason = "NotReady"
    return {
        "name": pod.metadata.name,
        "namespace": pod.metadata.namespace,
        "status": reason or phase,
        "phase": phase,
        "restarts": sum(cs.restart_count for cs in statuses),
        "message": message,
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
                return demo_response("Kubernetes", _demo_failing_pods())
            v1 = _core()
            pods = v1.list_namespaced_pod(namespace=namespace)
            failing = [row for row in map(_pod_problem, pods.items) if row]
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
                return demo_response("Kubernetes", _demo_pod_logs())
            v1 = _core()
            text = v1.read_namespaced_pod_log(
                name=pod_name,
                namespace=namespace,
                tail_lines=min(max(tail_lines, 1), 1000),
                limit_bytes=_LOG_LIMIT_BYTES,
            )
            return _mark_truncated(text)

        @mcp.tool()
        def k8s_describe_pod(pod_name: str, namespace: str = "default") -> str:
            """Describe a pod: status, containers, recent events."""
            audit("k8s_describe_pod", {"pod_name": pod_name, "namespace": namespace})
            if not _kube_configured():
                return demo_response("Kubernetes", _demo_describe_pod())
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
                return demo_response("Kubernetes", _demo_events())
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
                    "last_seen": _event_time(e),
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
                return demo_response("Kubernetes", _demo_deployment_status())
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
            """List pods not in Running/Succeeded state. (demo mode, kubernetes not installed)"""
            audit("k8s_get_failing_pods", {"namespace": namespace})
            return demo_response("Kubernetes", _demo_failing_pods())

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
            return demo_response("Kubernetes", _demo_pod_logs())

        @mcp.tool()
        def k8s_describe_pod(pod_name: str, namespace: str = "default") -> str:  # type: ignore[misc]
            """Describe a pod. (demo mode)"""
            audit("k8s_describe_pod", {"pod_name": pod_name, "namespace": namespace})
            return demo_response("Kubernetes", _demo_describe_pod())

        @mcp.tool()
        def k8s_get_events(namespace: str = "default", field_selector: str = "") -> str:  # type: ignore[misc]
            """List cluster events. (demo mode)"""
            audit(
                "k8s_get_events",
                {"namespace": namespace, "field_selector": field_selector},
            )
            return demo_response("Kubernetes", _demo_events())

        @mcp.tool()
        def k8s_get_deployment_status(deployment_name: str, namespace: str = "default") -> str:  # type: ignore[misc]
            """Get rollout status of a deployment. (demo mode)"""
            audit(
                "k8s_get_deployment_status",
                {"deployment_name": deployment_name, "namespace": namespace},
            )
            return demo_response("Kubernetes", _demo_deployment_status())
