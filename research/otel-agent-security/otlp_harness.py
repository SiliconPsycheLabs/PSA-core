#!/usr/bin/env python3
"""
The OTLP wire harness the security tests run against.

Part of a trust-boundary proposal to the OpenTelemetry GenAI semantic
conventions group. See the README for the proposal and its references.

Every test in this suite sends its spans through the real path:

    producer -> OTLPSpanExporter (HTTP/protobuf) -> [network] -> receiver
             -> ExportTraceServiceRequest.ParseFromString -> decoded spans

Nothing is asserted against an in-memory exporter. That distinction is the
whole point of the suite: an in-memory exporter shows that the SDK holds the
content in a Python object, which nobody disputes. Sending it over OTLP and
decoding the protobuf at the other end shows that the *protocol payload* is
what carries the untrusted content, unmarked, to whatever consumes it. A
proposal aimed at the OTLP data model has to be evidenced on the data model.

The receiver is a real OTLP/HTTP receiver: it speaks `POST /v1/traces`, decodes
`ExportTraceServiceRequest`, and answers with a serialized
`ExportTraceServiceResponse`, which is what makes the exporter report success.
It stands in for a Collector or a backend ingest endpoint.
"""

from __future__ import annotations

import gzip
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.proto.collector.trace.v1.trace_service_pb2 import (
    ExportTraceServiceRequest,
    ExportTraceServiceResponse,
)
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor


def _attr_value(v):
    """Unwrap an OTLP AnyValue into a plain Python value."""
    which = v.WhichOneof("value")
    if which == "string_value":
        return v.string_value
    if which == "bool_value":
        return v.bool_value
    if which == "int_value":
        return v.int_value
    if which == "double_value":
        return v.double_value
    if which == "array_value":
        return [_attr_value(x) for x in v.array_value.values]
    if which == "kvlist_value":
        return {kv.key: _attr_value(kv.value) for kv in v.kvlist_value.values}
    if which == "bytes_value":
        return v.bytes_value
    return None


def _kvs(pairs):
    return {kv.key: _attr_value(kv.value) for kv in pairs}


class OTLPReceiver:
    """A real OTLP/HTTP receiver that keeps every request it decodes.

    `self.spans` holds the decoded spans as plain dicts; `self.resource` holds
    the decoded resource attributes; `self.raw_payloads` holds the exact bytes
    that came off the wire, so a test can assert on the serialized form rather
    than on anything this harness reconstructs.
    """

    def __init__(self):
        self.spans: list[dict] = []
        self.resource: dict = {}
        self.raw_payloads: list[bytes] = []
        self._server = None
        self._thread = None

    # -- lifecycle ---------------------------------------------------------- #
    def start(self) -> str:
        receiver = self

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):  # noqa: N802 - BaseHTTPRequestHandler API
                length = int(self.headers.get("Content-Length", 0))
                body = self.rfile.read(length)
                if self.headers.get("Content-Encoding") == "gzip":
                    body = gzip.decompress(body)
                receiver.raw_payloads.append(body)
                receiver._ingest(body)
                out = ExportTraceServiceResponse().SerializeToString()
                self.send_response(200)
                self.send_header("Content-Type", "application/x-protobuf")
                self.send_header("Content-Length", str(len(out)))
                self.end_headers()
                self.wfile.write(out)

            def log_message(self, *args):  # keep the test output clean
                return

        self._server = HTTPServer(("127.0.0.1", 0), Handler)
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()
        port = self._server.server_address[1]
        return f"http://127.0.0.1:{port}/v1/traces"

    def stop(self):
        if self._server is not None:
            self._server.shutdown()
            self._server.server_close()
            self._server = None

    # -- decoding ----------------------------------------------------------- #
    def _ingest(self, body: bytes):
        request = ExportTraceServiceRequest()
        request.ParseFromString(body)
        for rs in request.resource_spans:
            self.resource.update(_kvs(rs.resource.attributes))
            for ss in rs.scope_spans:
                for span in ss.spans:
                    self.spans.append(
                        {
                            "name": span.name,
                            "trace_id": span.trace_id.hex(),
                            "span_id": span.span_id.hex(),
                            "parent_span_id": span.parent_span_id.hex(),
                            "attributes": _kvs(span.attributes),
                            "links": [
                                {
                                    "trace_id": link.trace_id.hex(),
                                    "span_id": link.span_id.hex(),
                                    "attributes": _kvs(link.attributes),
                                }
                                for link in span.links
                            ],
                        }
                    )

    # -- convenience -------------------------------------------------------- #
    def span(self, name_fragment: str) -> dict:
        for s in self.spans:
            if name_fragment in s["name"]:
                return s
        raise AssertionError(
            f"no span matching {name_fragment!r}; received {[s['name'] for s in self.spans]}"
        )

    def all_attribute_keys(self) -> set:
        keys = set(self.resource)
        for s in self.spans:
            keys |= set(s["attributes"])
        return keys


class WireSession:
    """A producer wired to a receiver over real OTLP, for the duration of a test."""

    def __init__(self, resource_attributes: dict | None = None, sampler=None):
        self.receiver = OTLPReceiver()
        endpoint = self.receiver.start()
        self.exporter = OTLPSpanExporter(endpoint=endpoint, timeout=10)
        self.provider = TracerProvider(
            resource=Resource.create(resource_attributes or {"service.name": "agent-under-test"}),
            sampler=sampler,
        )
        # Simple (not batched) so a test's spans are on the wire by the time
        # `flush()` returns, without sleeping.
        self.provider.add_span_processor(SimpleSpanProcessor(self.exporter))
        self.tracer = self.provider.get_tracer("otel-agent-security-tests")

    def flush(self):
        self.provider.force_flush()

    def close(self):
        self.provider.shutdown()
        self.receiver.stop()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()
        return False


# --------------------------------------------------------------------------- #
# Consumers. These are the code under test: not the SDK, but the things people
# build on top of captured content.
# --------------------------------------------------------------------------- #

def render_for_model(spans: list, resource: dict) -> str:
    """Flatten a decoded payload the way a 'chat with your traces' feature does.

    Deliberately the naive implementation, because the naive implementation is
    what ships: dump the resource attributes and every span attribute as text
    and hand the block to a model. There is no trust boundary in it because the
    payload offers nothing to build one from.
    """
    lines = [f"resource.{k} = {v}" for k, v in resource.items()]
    for s in spans:
        lines.append(f"span: {s['name']}")
        for k, v in s["attributes"].items():
            lines.append(f"  {k} = {v}")
    return "\n".join(lines)


def flatten_to_logs(spans: list) -> list:
    """Naive trace-to-log flattening: one line per attribute, no escaping.

    This is the log-injection surface. Real pipelines do exactly this when
    traces are mirrored into a log store for search.
    """
    lines = []
    for s in spans:
        for k, v in s["attributes"].items():
            lines.append(f"level=info span={s['name']} attr={k} value={v}")
    return lines


def flatten_to_logs_hardened(spans: list) -> list:
    """The fix: escape the control characters that let content forge a line."""
    lines = []
    for s in spans:
        for k, v in s["attributes"].items():
            safe = (
                str(v)
                .replace("\\", "\\\\")
                .replace("\n", "\\n")
                .replace("\r", "\\r")
                .replace("\x1b", "\\x1b")
                .replace("\x00", "\\x00")
            )
            lines.append(f"level=info span={s['name']} attr={k} value={safe}")
    return lines


def render_dashboard_html(spans: list) -> str:
    """Naive observability-UI rendering: attribute values interpolated as HTML."""
    rows = []
    for s in spans:
        for k, v in s["attributes"].items():
            rows.append(f"<tr><td>{k}</td><td>{v}</td></tr>")
    return "<table>" + "".join(rows) + "</table>"


def render_dashboard_html_hardened(spans: list) -> str:
    """The fix: contextual output encoding before the content reaches the DOM."""
    import html

    rows = []
    for s in spans:
        for k, v in s["attributes"].items():
            rows.append(
                f"<tr><td>{html.escape(str(k))}</td><td>{html.escape(str(v))}</td></tr>"
            )
    return "<table>" + "".join(rows) + "</table>"
