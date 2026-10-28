import importlib
import sys
import types

from tests.helpers import load


class _FakeMCP:
    def __init__(self):
        self.tools = {}

    def tool(self):
        def decorator(fn):
            self.tools[fn.__name__] = fn
            return fn

        return decorator


class _FakeConfigException(Exception):
    pass


class _FakeCoreApi:
    def __init__(self, pods=None, log="", events=None):
        self._pods = pods or []
        self._log = log
        self._events = events or []

    def list_namespaced_pod(self, namespace):
        return types.SimpleNamespace(items=self._pods)

    def read_namespaced_pod_log(self, name, namespace, tail_lines, **kwargs):
        return self._log

    def read_namespaced_pod(self, name, namespace):
        return self._pods[0]

    def list_namespaced_event(self, **kwargs):
        return types.SimpleNamespace(items=self._events)


class _FakeAppsApi:
    def __init__(self, deployment):
        self._deployment = deployment

    def read_namespaced_deployment(self, name, namespace):
        return self._deployment


def _make_pod(
    name,
    namespace,
    phase,
    restarts,
    image="myapp/api-server:v1.4.2",
    ready=False,
    node="node-west-2a",
):
    # Real clusters report CrashLoopBackOff as a container waiting reason on a
    # Running pod, never as the pod phase.
    waiting = None
    if phase == "CrashLoopBackOff":
        phase = "Running"
        waiting = types.SimpleNamespace(reason="CrashLoopBackOff", message="back-off")
    elif phase == "Running":
        ready = True
    container_status = types.SimpleNamespace(
        name="api-server",
        image=image,
        ready=ready,
        restart_count=restarts,
        state=types.SimpleNamespace(waiting=waiting, terminated=None),
    )
    return types.SimpleNamespace(
        metadata=types.SimpleNamespace(name=name, namespace=namespace),
        spec=types.SimpleNamespace(node_name=node),
        status=types.SimpleNamespace(
            phase=phase, container_statuses=[container_status]
        ),
    )


def _make_event(event_type, reason, kind, obj_name, message, count):
    return types.SimpleNamespace(
        type=event_type,
        reason=reason,
        involved_object=types.SimpleNamespace(kind=kind, name=obj_name),
        message=message,
        count=count,
    )


def _make_deployment(name, namespace, desired, ready, available, unavailable, image):
    container = types.SimpleNamespace(image=image)
    condition = types.SimpleNamespace(
        type="Available", status="False", reason="MinimumReplicasUnavailable"
    )
    return types.SimpleNamespace(
        metadata=types.SimpleNamespace(name=name, namespace=namespace),
        spec=types.SimpleNamespace(
            replicas=desired,
            template=types.SimpleNamespace(
                spec=types.SimpleNamespace(containers=[container])
            ),
        ),
        status=types.SimpleNamespace(
            ready_replicas=ready,
            available_replicas=available,
            unavailable_replicas=unavailable,
            conditions=[condition],
        ),
    )


def _register_configured(monkeypatch, audit, core_api=None, apps_api=None):
    """Register the kubernetes tool module with a stubbed client and a
    reachable kubeconfig, exercising the real (non-demo) code path."""
    monkeypatch.setenv("KUBECONFIG", "/tmp/fake-kubeconfig")

    config_mod = types.SimpleNamespace(
        ConfigException=_FakeConfigException,
        load_incluster_config=lambda: (_ for _ in ()).throw(_FakeConfigException()),
        load_kube_config=lambda: None,
    )
    client_mod = types.SimpleNamespace(
        CoreV1Api=lambda: core_api,
        AppsV1Api=lambda: apps_api,
    )
    fake_kubernetes = types.ModuleType("kubernetes")
    fake_kubernetes.client = client_mod
    fake_kubernetes.config = config_mod
    monkeypatch.setitem(sys.modules, "kubernetes", fake_kubernetes)
    sys.modules.pop("devops_mcp.tools.kubernetes", None)

    kubernetes_tools = importlib.import_module("devops_mcp.tools.kubernetes")
    mcp = _FakeMCP()
    kubernetes_tools.register(mcp, audit)
    return mcp


def test_get_failing_pods_returns_only_non_running(monkeypatch, no_audit):
    pods = [
        _make_pod("api-server-7d9f8b-xk2pq", "production", "CrashLoopBackOff", 14),
        _make_pod("api-server-ok-1", "production", "Running", 0),
    ]
    mcp = _register_configured(monkeypatch, no_audit, core_api=_FakeCoreApi(pods=pods))

    result = load(mcp.tools["k8s_get_failing_pods"](namespace="production"))
    assert isinstance(result, list)
    assert len(result) == 1
    assert result[0]["status"] == "CrashLoopBackOff"


def test_get_failing_pods_crashloop(monkeypatch, no_audit):
    pods = [_make_pod("api-server-7d9f8b-xk2pq", "production", "CrashLoopBackOff", 14)]
    mcp = _register_configured(monkeypatch, no_audit, core_api=_FakeCoreApi(pods=pods))

    result = load(mcp.tools["k8s_get_failing_pods"](namespace="production"))
    statuses = {p["status"] for p in result}
    assert "CrashLoopBackOff" in statuses


def test_pod_logs_returns_string(monkeypatch, no_audit):
    log_text = "[2024-01-15 03:42:11] ERROR  Failed to connect to database: connection refused\n"
    mcp = _register_configured(
        monkeypatch, no_audit, core_api=_FakeCoreApi(log=log_text)
    )

    result = mcp.tools["k8s_pod_logs"](
        pod_name="api-server-7d9f8b-xk2pq", namespace="production"
    )
    assert isinstance(result, str)
    assert "ERROR" in result


def test_describe_pod_has_required_keys(monkeypatch, no_audit):
    pods = [_make_pod("api-server-7d9f8b-xk2pq", "production", "CrashLoopBackOff", 14)]
    mcp = _register_configured(monkeypatch, no_audit, core_api=_FakeCoreApi(pods=pods))

    result = load(mcp.tools["k8s_describe_pod"](pod_name="api-server-7d9f8b-xk2pq"))
    for key in ("name", "namespace", "status", "containers"):
        assert key in result


def test_get_events_returns_warnings(monkeypatch, no_audit):
    events = [
        _make_event(
            "Warning",
            "BackOff",
            "Pod",
            "api-server-7d9f8b-xk2pq",
            "Back-off restarting failed container",
            47,
        )
    ]
    mcp = _register_configured(
        monkeypatch, no_audit, core_api=_FakeCoreApi(events=events)
    )

    result = load(mcp.tools["k8s_get_events"](namespace="production"))
    assert isinstance(result, list)
    assert result[0]["reason"] == "BackOff"


def test_deployment_status_shows_unavailable(monkeypatch, no_audit):
    deployment = _make_deployment(
        "api-server",
        "production",
        desired=3,
        ready=1,
        available=1,
        unavailable=2,
        image="myapp/api-server:v1.4.2",
    )
    mcp = _register_configured(monkeypatch, no_audit, apps_api=_FakeAppsApi(deployment))

    result = load(mcp.tools["k8s_get_deployment_status"](deployment_name="api-server"))
    assert result["unavailable"] > 0
    assert result["ready"] < result["desired"]


def test_demo_mode_without_kubeconfig(monkeypatch, no_audit):
    """No KUBECONFIG, no in-cluster token, no ~/.kube/config: falls back to
    demo data instead of attempting a real cluster connection."""
    from pathlib import Path

    monkeypatch.delenv("KUBECONFIG", raising=False)
    sys.modules.pop("devops_mcp.tools.kubernetes", None)
    kubernetes_tools = importlib.import_module("devops_mcp.tools.kubernetes")

    monkeypatch.setattr(
        kubernetes_tools, "_SERVICE_ACCOUNT_TOKEN", Path("/nonexistent/token")
    )
    monkeypatch.setattr(Path, "home", lambda: Path("/nonexistent/home"))

    mcp = _FakeMCP()
    kubernetes_tools.register(mcp, no_audit)

    result = load(mcp.tools["k8s_get_failing_pods"](namespace="production"))
    assert any(p["status"] == "CrashLoopBackOff" for p in result)


def test_demo_mode_when_kubernetes_package_unavailable(monkeypatch, no_audit):
    monkeypatch.setitem(sys.modules, "kubernetes", None)
    sys.modules.pop("devops_mcp.tools.kubernetes", None)

    kubernetes_tools = importlib.import_module("devops_mcp.tools.kubernetes")
    mcp = _FakeMCP()
    kubernetes_tools.register(mcp, no_audit)

    result = load(mcp.tools["k8s_get_failing_pods"](namespace="production"))
    assert any(p["status"] == "CrashLoopBackOff" for p in result)


def _pod(phase, statuses):
    from types import SimpleNamespace as NS

    return NS(
        metadata=NS(name="api-1", namespace="prod"),
        status=NS(phase=phase, container_statuses=statuses),
    )


def _cs(ready=True, restarts=0, waiting=None, terminated=None):
    from types import SimpleNamespace as NS

    return NS(
        ready=ready,
        restart_count=restarts,
        state=NS(waiting=waiting, terminated=terminated),
    )


def test_pod_problem_flags_crashloop_with_running_phase():
    from types import SimpleNamespace as NS

    from devops_mcp.tools.kubernetes import _pod_problem

    waiting = NS(reason="CrashLoopBackOff", message="back-off 5m")
    row = _pod_problem(_pod("Running", [_cs(False, 14, waiting=waiting)]))
    assert row["status"] == "CrashLoopBackOff"
    assert row["restarts"] == 14


def test_pod_problem_ignores_healthy_and_completed():
    from devops_mcp.tools.kubernetes import _pod_problem

    assert _pod_problem(_pod("Running", [_cs(True)])) is None
    assert _pod_problem(_pod("Succeeded", [])) is None


def test_pod_problem_flags_running_but_not_ready():
    from devops_mcp.tools.kubernetes import _pod_problem

    assert _pod_problem(_pod("Running", [_cs(False)]))["status"] == "NotReady"


def test_pod_problem_flags_pending():
    from devops_mcp.tools.kubernetes import _pod_problem

    assert _pod_problem(_pod("Pending", []))["status"] == "Pending"
