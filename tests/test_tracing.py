import pytest

pytest.importorskip("opentelemetry.sdk")

from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from opentelemetry.trace import StatusCode

from devops_mcp.tracing import configure_tracing, traced


@pytest.fixture
def spans():
    exporter = InMemorySpanExporter()
    provider = configure_tracing(exporter)
    yield exporter
    provider.shutdown()


def test_span_records_tool_name_and_arg_names_only(spans):
    @traced("k8s_get_failing_pods")
    def tool(namespace, token):
        return "ok"

    assert tool(namespace="prod", token="s3cret") == "ok"
    (span,) = spans.get_finished_spans()
    assert span.name == "tool.k8s_get_failing_pods"
    assert span.attributes["devops_mcp.tool"] == "k8s_get_failing_pods"
    assert list(span.attributes["devops_mcp.arg_names"]) == ["namespace", "token"]
    assert "s3cret" not in str(span.attributes)


def test_exception_marks_span_as_error_and_propagates(spans):
    @traced("boom")
    def tool():
        raise RuntimeError("down")

    with pytest.raises(RuntimeError):
        tool()
    (span,) = spans.get_finished_spans()
    assert span.status.status_code == StatusCode.ERROR
    assert span.events[0].name == "exception"
