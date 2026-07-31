"""
Finding B: trace context is unauthenticated, tested against the real SDK
propagator rather than a hand-written parser.

Part of a trust-boundary proposal to the OpenTelemetry GenAI semantic
conventions group. See the README for the proposal and its references.
samplers, so what is demonstrated is the behaviour a real receiver has, rather
than the behaviour of a hand-written header parser.

None of this is a defect in the W3C specification, which says plainly that
trace context is not authenticated. It is a defect in the assumption that the
mesh a receiver sits in is trusted, and multi-agent deployments break that
assumption without changing the propagation mechanism.

Each attack is paired with tier 1 of the proposal, link-do-not-adopt: at
ingress from an untrusted peer, mint a fresh root and record the incoming
context as a link. It needs no new infrastructure and no spec change, and the
tests show it holds while keeping the cross-trace join analysts need.
"""

from __future__ import annotations

from opentelemetry import trace
from opentelemetry.sdk.trace.sampling import ALWAYS_ON, ParentBased
from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator

from otlp_harness import WireSession

PROPAGATOR = TraceContextTextMapPropagator()

# A trace the attacker does not belong to, and a span id inside it.
VICTIM_TRACE_ID = "4bf92f3577b34da6a3ce929d0e0e4736"
VICTIM_SPAN_ID = "00f067aa0ba902b7"

FORGED_SAMPLED = f"00-{VICTIM_TRACE_ID}-{VICTIM_SPAN_ID}-01"
FORGED_UNSAMPLED = f"00-{VICTIM_TRACE_ID}-{VICTIM_SPAN_ID}-00"


def _trusting_receiver(session, traceparent: str, span_name="handle_request"):
    """What every framework's ingress does by default: continue the caller's trace."""
    ctx = PROPAGATOR.extract({"traceparent": traceparent})
    with session.tracer.start_as_current_span(span_name, context=ctx) as span:
        span.set_attribute("gen_ai.agent.name", "downstream-agent")
    session.flush()


def _link_do_not_adopt_receiver(session, traceparent: str, span_name="handle_request"):
    """Tier 1: fresh root, incoming context kept as a link.

    Six lines, current SDK, no new dependency. The trace join survives as a
    link, so an analyst can still follow the request across the boundary; what
    is gone is the caller's ability to decide our trace id and our parent.
    """
    incoming = PROPAGATOR.extract({"traceparent": traceparent})
    incoming_span_context = trace.get_current_span(incoming).get_span_context()
    link = trace.Link(
        incoming_span_context, {"context.origin": "unverified"}
    ) if incoming_span_context.is_valid else None
    with session.tracer.start_as_current_span(
        span_name, context=trace.set_span_in_context(trace.INVALID_SPAN), links=[link] if link else None
    ) as span:
        span.set_attribute("gen_ai.agent.name", "downstream-agent")
    session.flush()


# --------------------------------------------------------------------------- #
# Span graft and causality rewrite
# --------------------------------------------------------------------------- #

def test_a_forged_traceparent_grafts_the_attackers_span_into_a_victim_trace():
    """The receiver adopts an attacker-chosen trace id and parent, on request.

    Consequence for anything that treats traces as evidence: the causal graph is
    whatever the last caller said it was.
    """
    with WireSession() as session:
        _trusting_receiver(session, FORGED_SAMPLED)
        span = session.receiver.span("handle_request")

    assert span["trace_id"] == VICTIM_TRACE_ID, "the span landed inside a trace it does not belong to"
    assert span["parent_span_id"] == VICTIM_SPAN_ID, "and named its own parent"


def test_link_do_not_adopt_blocks_the_graft_and_keeps_the_join():
    """Tier 1, same forged header, on the real SDK."""
    with WireSession() as session:
        _link_do_not_adopt_receiver(session, FORGED_SAMPLED)
        span = session.receiver.span("handle_request")

    assert span["trace_id"] != VICTIM_TRACE_ID, "our trace id is ours"
    assert span["parent_span_id"] in ("", "0000000000000000"), "no attacker-chosen parent"
    assert len(span["links"]) == 1, "the incoming context is retained"
    assert span["links"][0]["trace_id"] == VICTIM_TRACE_ID, "the join an analyst needs survives"
    assert span["links"][0]["attributes"]["context.origin"] == "unverified", (
        "and it is labelled for what it is"
    )


def test_two_agents_can_be_made_to_appear_causally_linked():
    """Causality rewrite: an attacker places itself, or another agent, in the story.

    The record shows agent B handling a request caused by agent A. Nothing
    corroborates the claim; the trace is the only record, and the trace was
    written from the header.
    """
    with WireSession() as session:
        _trusting_receiver(session, FORGED_SAMPLED, span_name="invoke_agent billing-agent")
        _trusting_receiver(session, FORGED_SAMPLED, span_name="invoke_agent shipping-agent")
        billing = session.receiver.span("billing-agent")
        shipping = session.receiver.span("shipping-agent")

    assert billing["trace_id"] == shipping["trace_id"] == VICTIM_TRACE_ID
    assert billing["parent_span_id"] == shipping["parent_span_id"] == VICTIM_SPAN_ID, (
        "both agents now hang off a parent neither of them ever spoke to"
    )


# --------------------------------------------------------------------------- #
# Sampling evasion
# --------------------------------------------------------------------------- #

def test_the_flags_byte_lets_a_caller_switch_off_recording_downstream():
    """One hex digit decides whether the receiver's work is recorded at all.

    `ParentBased` is the default sampler in the SDK and the recommended one for
    trace completeness. Under it, `flags=00` from an untrusted caller means the
    downstream span is never exported: an agent can act, and leave no trace,
    by asking.
    """
    with WireSession(sampler=ParentBased(root=ALWAYS_ON)) as session:
        _trusting_receiver(session, FORGED_UNSAMPLED)
        assert session.receiver.spans == [], "the caller suppressed the receiver's own record"

        _trusting_receiver(session, FORGED_SAMPLED, span_name="handle_request_sampled")
        assert len(session.receiver.spans) == 1, "and can switch it back on at will"


def test_link_do_not_adopt_restores_the_local_sampling_decision():
    """Tier 1 also fixes the sampling case, because the root is now ours.

    Worth separating from the graft result: teams often read the sampling issue
    as a cost problem. It is an evidence problem, and the same six lines answer
    both.
    """
    with WireSession(sampler=ParentBased(root=ALWAYS_ON)) as session:
        _link_do_not_adopt_receiver(session, FORGED_UNSAMPLED)
        assert len(session.receiver.spans) == 1, (
            "a fresh root is sampled locally, whatever the caller asked for"
        )
        span = session.receiver.spans[0]
        assert span["links"][0]["trace_id"] == VICTIM_TRACE_ID


def test_forged_ids_are_accepted_without_any_validity_check_beyond_format():
    """There is nothing to check: the header carries no evidence of who wrote it.

    This is the finding stated as plainly as it can be. Any two receivers given
    the same header produce the same result, so nothing distinguishes the real
    caller from anyone who copied the header.
    """
    headers = [
        f"00-{VICTIM_TRACE_ID}-{VICTIM_SPAN_ID}-01",
        "00-11111111111111111111111111111111-2222222222222222-01",
        "00-deadbeefdeadbeefdeadbeefdeadbeef-cafebabecafebabe-01",
    ]
    seen = []
    for header in headers:
        with WireSession() as session:
            _trusting_receiver(session, header)
            seen.append(session.receiver.span("handle_request")["trace_id"])

    assert seen == [
        VICTIM_TRACE_ID,
        "11111111111111111111111111111111",
        "deadbeefdeadbeefdeadbeefdeadbeef",
    ], "every well-formed id is accepted on its own say-so"
