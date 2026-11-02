"""Optional OpenTelemetry tracing for tool calls.

Install the extra to use it: pip install "mcp-devops[otel]"

Nothing here is switched on by the server by default. Call configure_tracing()
yourself, then wrap a function with @traced("tool_name"). With no exporter
given it prints spans to the console, which needs no collector.
"""

from __future__ import annotations

import functools
from collections.abc import Callable
from typing import Any

from opentelemetry import trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import (
    BatchSpanProcessor,
    ConsoleSpanExporter,
    SimpleSpanProcessor,
    SpanExporter,
)
from opentelemetry.trace import Status, StatusCode

SERVICE_NAME = "devops-mcp"

_provider: TracerProvider | None = None


def configure_tracing(
    exporter: SpanExporter | None = None, batch: bool = False
) -> TracerProvider:
    """Build a provider and use it for every traced tool.

    It is also registered as the OpenTelemetry global provider if none is set
    yet (the SDK allows that only once per process).

    exporter: any SpanExporter. An OTLP exporter sends to a collector; an
    InMemorySpanExporter is handy in tests. Defaults to the console.
    batch: use a batching processor (production) instead of a simple one (tests).
    """
    provider = TracerProvider(resource=Resource.create({"service.name": SERVICE_NAME}))
    exporter = exporter or ConsoleSpanExporter()
    processor = BatchSpanProcessor(exporter) if batch else SimpleSpanProcessor(exporter)
    provider.add_span_processor(processor)
    global _provider
    _provider = provider
    trace.set_tracer_provider(provider)
    return provider


def traced(tool: str) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Wrap a function in a span named after the tool.

    Records the tool name and the argument names, never the argument values,
    because values can hold tokens or hostnames. Exceptions mark the span as
    an error and are re-raised.
    """

    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            tracer = (_provider or trace.get_tracer_provider()).get_tracer(SERVICE_NAME)
            with tracer.start_as_current_span(f"tool.{tool}") as span:
                span.set_attribute("devops_mcp.tool", tool)
                span.set_attribute("devops_mcp.arg_names", sorted(kwargs))
                try:
                    return func(*args, **kwargs)
                except Exception as exc:
                    span.record_exception(exc)
                    span.set_status(Status(StatusCode.ERROR, type(exc).__name__))
                    raise

        return wrapper

    return decorator
