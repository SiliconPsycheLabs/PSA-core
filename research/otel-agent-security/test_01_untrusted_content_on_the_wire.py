"""
Finding A, base case: captured GenAI content crosses the OTLP wire as untrusted
input that the payload gives a consumer no way to recognise as untrusted.

Part of a trust-boundary proposal to the OpenTelemetry GenAI semantic
conventions group. See the README for the proposal and its references.

These are the deterministic tests behind every claim the hardening note makes
about the protocol itself. They run without a model and without a network
beyond localhost.

What each test establishes, in order:

  1. attacker-controlled bytes reach the receiver byte-identical, so a consumer
     downstream is handling adversary-authored text;
  2. the serialized protobuf carries them verbatim, so this is a property of the
     payload and not of the harness that decoded it;
  3. nothing on the wire says the content is untrusted;
  4. nothing in the GenAI conventions could have said it, which is the gap the
     proposal closes rather than a mistake by any implementer.

Read together they say: content capture moved adversary-influenceable text onto
the operational data plane, and the data plane has no field for the one fact a
consumer needs about it.
"""

from __future__ import annotations

import gen_ai_content_trust as trust
from conftest import FIRST_ORDER_TOOL_RESULT, XSS_TOOL_RESULT
from otlp_harness import WireSession


def _emit_agent_turn(session, tool_result: str):
    """One ordinary instrumented agent turn with content capture enabled."""
    tracer = session.tracer
    with tracer.start_as_current_span("invoke_agent shopping-agent") as root:
        root.set_attribute("gen_ai.operation.name", "invoke_agent")
        root.set_attribute("gen_ai.agent.name", "shopping-agent")
        root.set_attribute("gen_ai.provider.name", "openai")
        root.set_attribute("gen_ai.input.messages", "What's the weather in Milan?")
        with tracer.start_as_current_span("execute_tool get_weather") as tool:
            tool.set_attribute("gen_ai.operation.name", "execute_tool")
            tool.set_attribute("gen_ai.tool.name", "get_weather")
            tool.set_attribute("gen_ai.tool.call.arguments", '{"city": "Milan"}')
            tool.set_attribute("gen_ai.tool.call.result", tool_result)
    session.flush()


def test_attacker_controlled_tool_result_survives_the_wire_byte_identical():
    """The receiver gets exactly what the attacker wrote.

    Nothing between the tool and the consumer is in a position to alter it: the
    SDK treats content as opaque, and OTLP is a transport. That is correct
    behaviour for a transport and is precisely why the handling obligation has
    to be stated for the consumer.
    """
    with WireSession() as session:
        _emit_agent_turn(session, FIRST_ORDER_TOOL_RESULT)
        received = session.receiver.span("execute_tool")["attributes"]["gen_ai.tool.call.result"]

    assert received == FIRST_ORDER_TOOL_RESULT
    assert "IMPORTANT SYSTEM UPDATE" in received, "the injection is intact, not merely present"


def test_the_serialized_protobuf_itself_carries_the_payload():
    """Asserted on the raw bytes, so the finding does not depend on our decoder.

    A reviewer can hexdump `raw_payloads[0]` and find the attack string in it.
    """
    with WireSession() as session:
        _emit_agent_turn(session, FIRST_ORDER_TOOL_RESULT)
        raw = b"".join(session.receiver.raw_payloads)

    assert b"IMPORTANT SYSTEM UPDATE" in raw
    assert raw, "no OTLP payload reached the receiver at all"


def test_no_attribute_on_the_wire_marks_the_content_as_untrusted():
    """The core gap: the consumer cannot tell tool output from operator text.

    Both land as strings on a span. The only signal available is the attribute
    name, and inferring a security property from a name breaks as soon as an
    instrumentation uses a vendor-specific one.
    """
    with WireSession() as session:
        _emit_agent_turn(session, FIRST_ORDER_TOOL_RESULT)
        keys = session.receiver.all_attribute_keys()

    provenance_keys = [k for k in keys if trust.looks_like_provenance(k)]
    assert provenance_keys == [], (
        f"expected no provenance marker on the wire, found {provenance_keys}"
    )
    assert trust.TRUST not in keys, "the proposed marker is absent, as expected before adoption"
    # The content is there; only the fact that it is untrusted is missing.
    assert "gen_ai.tool.call.result" in keys


def test_the_gen_ai_conventions_define_no_provenance_attribute():
    """No implementer could have marked it: the vocabulary has no word for it.

    Checked against a snapshot of the registry, extracted mechanically on
    2026-07-28 from the repository the `gen_ai.*` attributes moved to, using a
    deliberately generous name predicate. Keeping the list in the repository is
    what makes the claim falsifiable rather than asserted in prose.

    What this test CANNOT do, stated because getting it wrong cost us three
    revisions: it has no network access, so it compares a frozen list against
    itself and will keep passing while upstream moves underneath it. It did
    exactly that when the whole namespace migrated out of the page the first
    snapshot was taken from. Re-fetching the source is a manual step before the
    claim is quoted anywhere outward-facing.
    """
    gap_confirmed, hits = trust.no_provenance_attribute_exists()
    assert gap_confirmed, f"registry now defines provenance attributes: {hits}"
    assert len(trust.GEN_AI_REGISTRY_SNAPSHOT_2026_07) == 63, (
        "snapshot changed; re-check the finding against the current registry at "
        "open-telemetry/semantic-conventions-genai"
    )


def test_every_content_attribute_is_reachable_by_an_adversary():
    """The exposure is not one attribute, it is the content class.

    Each attribute in the mapping carries text that a user, a tool, a retrieval
    corpus or a model produced. Only the operator-authored one is not adversary
    influenced by construction, and it stops being so the moment an application
    interpolates user text into its system prompt.
    """
    adversary_reachable = {
        name: cls
        for name, cls in trust.CONTENT_ATTRIBUTES.items()
        if cls != trust.OPERATOR
    }
    assert len(adversary_reachable) >= 6
    assert "gen_ai.tool.call.result" in adversary_reachable
    assert "gen_ai.input.messages" in adversary_reachable
    assert "gen_ai.retrieval.documents" in adversary_reachable


def test_markup_in_content_reaches_the_receiver_unescaped():
    """Same channel, a different consumer's problem, and no encoding applied.

    OTLP is right not to escape it: escaping is contextual and the transport
    does not know the context. The consumer does, which is why the obligation
    belongs in consumer guidance.
    """
    with WireSession() as session:
        _emit_agent_turn(session, XSS_TOOL_RESULT)
        received = session.receiver.span("execute_tool")["attributes"]["gen_ai.tool.call.result"]

    assert "<img src=x onerror=" in received
    assert "&lt;img" not in received
