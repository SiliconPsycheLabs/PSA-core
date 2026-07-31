"""
Baggage across an agent trust boundary: unsigned, writable by any hop, and
propagated onward by default.

Part of a trust-boundary proposal to the OpenTelemetry GenAI semantic
conventions group. See the README for the proposal and its references.
note, which had no test until now.

Baggage is the part of context propagation that agent frameworks reach for
first, because it is the obvious way to carry a tenant id, a user id or a
budget across a call chain. Two properties make that dangerous once a hop in
the chain is not fully trusted, and both are by design:

* anything a receiver reads from baggage was written by the caller, and the
  caller can write anything;
* anything a service puts in baggage keeps travelling, including outward to
  third parties, unless someone stops it.

The second is the one teams are surprised by. It turns baggage into an
exfiltration channel that runs in the opposite direction to the one they were
thinking about when they put the value in.

Mitigation under test: an ingress allowlist and an egress allowlist, the
concrete mechanism the note proposes. Deterministic throughout.
"""

from __future__ import annotations

from opentelemetry import baggage
from opentelemetry.baggage.propagation import W3CBaggagePropagator

from otlp_harness import WireSession

PROPAGATOR = W3CBaggagePropagator()

# What a receiver believes about itself and its caller.
TRUSTED_INGRESS_KEYS = {"tenant.id", "request.priority"}
ALLOWED_EGRESS_KEYS = {"tenant.id"}


def _extract(header: str):
    return PROPAGATOR.extract({"baggage": header})


def _inject(context) -> str:
    carrier: dict = {}
    PROPAGATOR.inject(carrier, context=context)
    return carrier.get("baggage", "")


def _filter_ingress(context, allowed=TRUSTED_INGRESS_KEYS):
    """Allowlist at ingress: drop every key the receiver did not agree to accept."""
    kept = None
    for key, value in baggage.get_all(context).items():
        if key in allowed:
            kept = baggage.set_baggage(key, value, context=kept)
    return kept or baggage.remove_baggage("", context=None)


def _filter_egress(context, allowed=ALLOWED_EGRESS_KEYS):
    """Allowlist at egress: decide what may leave, rather than forwarding everything."""
    kept = None
    for key, value in baggage.get_all(context).items():
        if key in allowed:
            kept = baggage.set_baggage(key, value, context=kept)
    return kept or baggage.remove_baggage("", context=None)


# --------------------------------------------------------------------------- #
# Injection: the caller decides what the receiver believes
# --------------------------------------------------------------------------- #

def test_a_caller_can_set_any_baggage_key_including_ones_used_for_decisions():
    """There is no distinction between a key we set and a key we were handed.

    A receiver reading `user.role` out of baggage is reading a value the caller
    typed. That is fine inside one trust domain and is an authorization bypass
    across two.
    """
    forged = "tenant.id=victim-corp,user.role=admin,billing.tier=enterprise"
    context = _extract(forged)
    values = baggage.get_all(context)

    assert values["user.role"] == "admin"
    assert values["tenant.id"] == "victim-corp"
    assert values["billing.tier"] == "enterprise"


def test_an_ingress_allowlist_drops_what_the_receiver_never_agreed_to_accept():
    forged = "tenant.id=victim-corp,user.role=admin,billing.tier=enterprise"
    filtered = _filter_ingress(_extract(forged))
    values = baggage.get_all(filtered)

    assert "user.role" not in values, "a decision input cannot arrive from the wire unnoticed"
    assert "billing.tier" not in values
    assert values.get("tenant.id") == "victim-corp", (
        "the allowlisted key still arrives; it is now a claim to verify, not a fact"
    )


def test_injected_baggage_lands_in_the_telemetry_a_consumer_reads():
    """Forged values reach the trace store when instrumentation records baggage.

    Recording baggage on spans is a common and otherwise sensible practice. It
    makes the attacker's claim part of the operator's record.
    """
    context = _extract("tenant.id=victim-corp,user.role=admin")
    with WireSession() as session:
        with session.tracer.start_as_current_span("handle_request") as span:
            for key, value in baggage.get_all(context).items():
                span.set_attribute(f"baggage.{key}", value)
        session.flush()
        attrs = session.receiver.span("handle_request")["attributes"]

    assert attrs["baggage.user.role"] == "admin"
    assert attrs["baggage.tenant.id"] == "victim-corp"


# --------------------------------------------------------------------------- #
# Exfiltration: what we put in keeps travelling
# --------------------------------------------------------------------------- #

def test_internal_baggage_propagates_outward_to_an_external_call():
    """The direction teams do not think about when they set a value.

    An internal key set for internal reasons is serialized into the header of
    the next hop, whoever the next hop is. Calling a third-party tool or a
    partner agent hands it over.
    """
    context = baggage.set_baggage("tenant.id", "acme-corp")
    context = baggage.set_baggage("internal.cost_center", "CC-4471", context=context)
    context = baggage.set_baggage("internal.customer_email", "ceo@acme.example", context=context)

    outbound = _inject(context)

    assert "internal.cost_center=CC-4471" in outbound
    assert "internal.customer_email=ceo%40acme.example" in outbound, (
        "url-encoded, not withheld: it is on the wire to a third party"
    )


def test_an_egress_allowlist_stops_the_outward_leak():
    context = baggage.set_baggage("tenant.id", "acme-corp")
    context = baggage.set_baggage("internal.cost_center", "CC-4471", context=context)
    context = baggage.set_baggage("internal.customer_email", "ceo@acme.example", context=context)

    outbound = _inject(_filter_egress(context))

    assert "tenant.id=acme-corp" in outbound
    assert "internal.cost_center" not in outbound
    assert "customer_email" not in outbound


def test_a_hop_can_add_to_baggage_without_removing_what_is_already_there():
    """Baggage accumulates along a chain, so the last hop sees every earlier hop's keys.

    In a swarm this is the contagion shape: a value set once by one agent is
    visible to, and usable by, every agent downstream of it, and none of them
    can tell which hop wrote it.
    """
    first_hop = _extract("tenant.id=acme-corp")
    second_hop = baggage.set_baggage("agent.trust_level", "high", context=first_hop)
    forwarded = _inject(second_hop)

    assert "tenant.id=acme-corp" in forwarded
    assert "agent.trust_level=high" in forwarded

    at_the_far_end = baggage.get_all(_extract(forwarded))
    assert at_the_far_end["agent.trust_level"] == "high"
    assert at_the_far_end["tenant.id"] == "acme-corp"
    # Nothing in the entry records which hop wrote either value.
    assert set(at_the_far_end) == {"tenant.id", "agent.trust_level"}
