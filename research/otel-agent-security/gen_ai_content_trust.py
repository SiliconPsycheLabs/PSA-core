#!/usr/bin/env python3
"""
Reference implementation of the proposed `gen_ai.content.trust` attribute.

Part of a trust-boundary proposal to the OpenTelemetry GenAI semantic
conventions group. See the README for the proposal and its references.
conventions group.

Why this file exists
--------------------
Proposal A was prose. Prose does not convince a semantic-conventions review.
This module is the smallest working implementation of the proposal, so a
conventions PR can point at something runnable:

  1. `TRUST` / `CONTENT_ATTRIBUTES` - the attribute, its value set, and the
     mapping from the existing GenAI content attributes to a default trust
     class. Nothing here changes the OTLP data model; it is one more string
     attribute.
  2. `mark_span` - the PRODUCER side, what an instrumentation library calls at
     capture time, which is the only point where provenance is still known.
     `apply_trust_markers` is the weaker retrofit path for instrumentation
     already deployed.
  3. `quarantine` - the CONSUMER/COLLECTOR side. Withholds content below a trust
     floor before it reaches an automated reader. It stands in for a Collector
     processor and is not one: a real deployment expresses this as OTTL in the
     `transform` processor, or as a custom processor in a distro built with the
     OpenTelemetry Collector Builder.
  4. `trust_from_mcp_annotations` / `should_mark` - the two design decisions
     taken from neighbouring work rather than invented here :
     interop with MCP SEP-1913's annotations, and #386's positive-indicator-only
     pattern.

The point of the pairing: (2) alone is documentation, (3) alone is guesswork
based on attribute names. Together they are an enforceable control, and that
is the argument for adding the attribute to the standard.

The idea of a trust annotation is NOT ours: MCP is designing the same thing one
layer down (SEP-1913), and trust labelling is established defence practice. What
is unproposed is carrying it on the telemetry plane, which is where the
injection literature says the attack lands. See the References section of
the README.

Dependency-free apart from the OpenTelemetry SDK.
"""

from __future__ import annotations

# --------------------------------------------------------------------------- #
# The proposed attribute
# --------------------------------------------------------------------------- #

TRUST = "gen_ai.content.trust"

# Value set, ordered from least to most trusted. A consumer applies handling by
# comparing against its own floor rather than by pattern-matching attribute
# names.
USER_SUPPLIED = "user_supplied"      # came from the end user
TOOL_OUTPUT = "tool_output"          # came from a tool / external service
RETRIEVED = "retrieved"              # came from a retrieval corpus
MODEL_GENERATED = "model_generated"  # produced by the model under observation
OPERATOR = "operator"                # authored by the deploying operator

TRUST_ORDER = [USER_SUPPLIED, TOOL_OUTPUT, RETRIEVED, MODEL_GENERATED, OPERATOR]

# Interop with MCP's in-flight annotations (SEP-1913, Extensions Track, incubating in
# `experimental-ext-tool-annotations`). A host that receives an MCP tool response carrying
# `openWorldHint` already knows the provenance; this mapping lets it carry that fact onto the
# span instead of a fifth unrelated vocabulary appearing in the ecosystem. Interop is the
# argument for the proposal, not novelty: MCP is designing the same annotation one layer down.
MCP_ANNOTATION_MAP = {
    "openWorldHint": TOOL_OUTPUT,   # "untrusted/external data sources"
    "privateHint": OPERATOR,        # internal/organisational data
}

# Deliberately NOT implemented: propagation of the marker across spans or across a session.
# MCP's draft carried exactly that (sensitivity escalates and never decreases within a session;
# boolean hints union; attribution accumulates) and REMOVED it on the Extensions Track migration
# as structurally unresolved. The same gap exists here: a model output derived from poisoned tool
# input is marked `model_generated` and sits above a default floor, so per-span marking does not
# see laundered taint. That is a known-hard problem in a sibling standard, and the honest position
# is to stay per-span and say so rather than ship a propagation rule nobody has made work.

# Content-bearing attributes in the current GenAI conventions, mapped to the
# trust class their content carries by construction. This mapping is the
# default an instrumentation library would ship; an application can override it
# when it knows better (for example, `operator` for a system prompt it authored
# itself and never interpolates user text into).
CONTENT_ATTRIBUTES = {
    "gen_ai.input.messages": USER_SUPPLIED,
    "gen_ai.output.messages": MODEL_GENERATED,
    "gen_ai.system_instructions": OPERATOR,
    "gen_ai.tool.call.arguments": MODEL_GENERATED,
    "gen_ai.tool.call.result": TOOL_OUTPUT,
    "gen_ai.retrieval.documents": RETRIEVED,
    "gen_ai.retrieval.query.text": USER_SUPPLIED,
    # Added 2026-07-28  after the registry recheck. Agent memory is a
    # textbook injection-persistence store: content written once is re-read on
    # later turns, which is the passive-prompt-injection shape (arXiv:2607.14493)
    # inside the agent rather than inside the telemetry store.
    "gen_ai.memory.records": RETRIEVED,
    "gen_ai.memory.query.text": USER_SUPPLIED,
    # Prompt template variables are interpolated into the prompt and are commonly
    # filled from user input, which is how an "operator-authored" system prompt
    # stops being operator-authored in practice.
    "gen_ai.prompt.variable": USER_SUPPLIED,
}

# Everything the GenAI attribute registry defines, extracted mechanically on
# 2026-07-28 from the raw markdown at
# https://raw.githubusercontent.com/open-telemetry/semantic-conventions-genai/main/docs/registry/attributes/gen-ai.md
#
# NOTE ON THE SOURCE (2026-07-28). An earlier snapshot of 50 names was taken from
# https://opentelemetry.io/docs/specs/semconv/registry/attributes/gen-ai/ on
# 2026-07-25. That page now marks every `gen_ai.*` attribute deprecated with
# "Moved to the OpenTelemetry GenAI semantic conventions repository", so it is no
# longer the authority and the old snapshot was of a superseded page. The list
# below comes from the repository the attributes moved to.
#
# Kept here so `no_provenance_attribute_exists()` is a check anyone can re-run and
# falsify. It cannot detect upstream drift on its own: this module has no network
# access by design, so the snapshot only tells you what was true when it was
# taken. Re-fetching the source before quoting the result anywhere is a manual
# step, and skipping it is exactly how the moved-registry defect survived three
# revisions of the accompanying note.
GEN_AI_REGISTRY_SNAPSHOT_2026_07 = [
    "gen_ai.agent.description", "gen_ai.agent.id",
    "gen_ai.agent.name", "gen_ai.agent.version",
    "gen_ai.conversation.compacted", "gen_ai.conversation.id",
    "gen_ai.data_source.id", "gen_ai.embeddings.dimension.count",
    "gen_ai.evaluation.explanation", "gen_ai.evaluation.name",
    "gen_ai.evaluation.score.label", "gen_ai.evaluation.score.value",
    "gen_ai.input.messages", "gen_ai.memory.query.text",
    "gen_ai.memory.record.count", "gen_ai.memory.record.id",
    "gen_ai.memory.records", "gen_ai.memory.store.id",
    "gen_ai.operation.name", "gen_ai.output.messages",
    "gen_ai.output.type", "gen_ai.prompt.name",
    "gen_ai.prompt.variable", "gen_ai.prompt.variable.language",
    "gen_ai.prompt.variable.user_name", "gen_ai.prompt.version",
    "gen_ai.provider.name", "gen_ai.request.choice.count",
    "gen_ai.request.encoding_formats", "gen_ai.request.frequency_penalty",
    "gen_ai.request.max_tokens", "gen_ai.request.model",
    "gen_ai.request.presence_penalty", "gen_ai.request.previous_response.id",
    "gen_ai.request.reasoning.level", "gen_ai.request.seed",
    "gen_ai.request.stop_sequences", "gen_ai.request.stream",
    "gen_ai.request.temperature", "gen_ai.request.top_k",
    "gen_ai.request.top_p", "gen_ai.response.finish_reasons",
    "gen_ai.response.id", "gen_ai.response.model",
    "gen_ai.response.time_to_first_chunk", "gen_ai.retrieval.documents",
    "gen_ai.retrieval.query.text", "gen_ai.retrieval.top_k",
    "gen_ai.system_instructions", "gen_ai.token.type",
    "gen_ai.tool.call.arguments", "gen_ai.tool.call.id",
    "gen_ai.tool.call.result", "gen_ai.tool.definitions",
    "gen_ai.tool.description", "gen_ai.tool.name",
    "gen_ai.tool.type", "gen_ai.usage.cache_creation.input_tokens",
    "gen_ai.usage.cache_read.input_tokens", "gen_ai.usage.input_tokens",
    "gen_ai.usage.output_tokens", "gen_ai.usage.reasoning.output_tokens",
    "gen_ai.workflow.name",
]

# Words that would appear in the name of an attribute expressing trust,
# provenance or taint. Deliberately generous: a generous predicate that still
# matches nothing is stronger evidence than a narrow one.
_PROVENANCE_TERMS = (
    "trust", "trusted", "untrusted", "provenance", "origin", "taint",
    "tainted", "source.kind", "sanitiz", "authenticity", "integrity",
    "confidence.origin",
)


def looks_like_provenance(attribute_name: str) -> bool:
    """True if the attribute name plausibly expresses content trust/provenance."""
    lowered = attribute_name.lower()
    return any(term in lowered for term in _PROVENANCE_TERMS)


def no_provenance_attribute_exists(registry=None) -> tuple[bool, list]:
    """Check the registry snapshot for any trust/provenance attribute.

    Returns (True, []) when none exists, which is the gap Proposal A closes.
    Re-run against a fresher registry to falsify.
    """
    registry = registry or GEN_AI_REGISTRY_SNAPSHOT_2026_07
    hits = [a for a in registry if looks_like_provenance(a)]
    return (len(hits) == 0, hits)


# --------------------------------------------------------------------------- #
# Producer side: mark the content as it is recorded
# --------------------------------------------------------------------------- #

def default_trust_for(attribute_name: str):
    """The trust class the named content attribute carries by construction."""
    return CONTENT_ATTRIBUTES.get(attribute_name)


def trust_from_mcp_annotations(annotations: dict):
    """Least-trusted class implied by a set of MCP response annotations, or None.

    Lets a host translate SEP-1913 annotations it already received into the span
    attribute, rather than the two planes carrying unrelated vocabularies.
    """
    implied = [
        MCP_ANNOTATION_MAP[key]
        for key, value in (annotations or {}).items()
        if value and key in MCP_ANNOTATION_MAP
    ]
    if not implied:
        return None
    return min(implied, key=TRUST_ORDER.index)


def should_mark(trust: str | None) -> bool:
    """Positive-indicator-only: mark what is NOT operator-authored, leave the rest unset.

    Follows the pattern stated in OTel GenAI semconv #386 (`gen_ai.evidence.origin`), where the
    attribute stays unset by default and absence is semantically distinct from any value. It
    matters for a security attribute: an instrumentation that has never heard of the marker must
    never be mistaken for one asserting `operator`. Silence means unknown, never safe.
    """
    return trust is not None and trust != OPERATOR


def trust_of_span(attributes: dict):
    """The least-trusted class among the content attributes present on a span.

    A span carrying both a model output and an untrusted tool result is only as
    trustworthy as its weakest content, which is the whole point of a marker
    that a consumer can act on without reading the content.
    """
    present = [
        CONTENT_ATTRIBUTES[k] for k in attributes if k in CONTENT_ATTRIBUTES
    ]
    if not present:
        return None
    return min(present, key=TRUST_ORDER.index)


def mark_span(span, attribute_name: str, value, trust: str | None = None):
    """Set a content attribute together with its trust marker.

    This is the primary producer-side API and what an instrumentation library
    would call: one extra string attribute per content attribute. No data-model
    change, no new signal, no new endpoint, no SDK change.

    When a span carries several content attributes the marker settles on the
    least-trusted one, so a consumer reading a single field is never told the
    span is safer than its weakest content.
    """
    span.set_attribute(attribute_name, value)
    marker = trust or default_trust_for(attribute_name)
    if marker is None:
        return
    existing = (getattr(span, "attributes", None) or {}).get(TRUST)
    if existing is None or TRUST_ORDER.index(marker) < TRUST_ORDER.index(existing):
        span.set_attribute(TRUST, marker)


def apply_trust_markers(spans: list) -> list:
    """Retrofit path: derive the marker from the content attributes present.

    For instrumentation already deployed that cannot be changed today. It runs
    on the decoded payload (a Collector processor would do exactly this), and it
    is strictly weaker than `mark_span`: it can only infer trust from the
    conventional attribute names, so a vendor-specific or custom content
    attribute is invisible to it. That weakness is the argument for putting the
    marker in the standard instead of leaving consumers to infer it.
    """
    out = []
    for span in spans:
        attrs = dict(span.get("attributes", {}))
        if TRUST not in attrs:
            marker = trust_of_span(attrs)
            if marker is not None:
                attrs[TRUST] = marker
        new = dict(span)
        new["attributes"] = attrs
        out.append(new)
    return out


# --------------------------------------------------------------------------- #
# Consumer / Collector side: act on the marker
# --------------------------------------------------------------------------- #

QUARANTINE_PLACEHOLDER = "[QUARANTINED: untrusted content withheld from automated reader]"


def quarantine(spans: list, floor: str = MODEL_GENERATED, also_redact=()) -> tuple[list, int]:
    """Collector-equivalent processor: withhold content below a trust floor.

    `spans` is a list of dicts shaped like the decoded OTLP payload
    (`{"name":..., "attributes": {...}}`). Any span whose marker is less
    trusted than `floor` has its content attributes replaced before the payload
    reaches an automated consumer. `also_redact` names resource-level keys the
    consumer has no need for (secrets adjacent to the untrusted content).

    Returns (processed_spans, quarantined_count).

    This is the control the marker enables. Without the marker a Collector can
    only guess from attribute names, which fails the moment a vendor or a
    custom instrumentation uses a different name for the same content.
    """
    out = []
    count = 0
    for span in spans:
        attrs = dict(span.get("attributes", {}))
        marker = attrs.get(TRUST)
        below_floor = (
            marker is not None
            and TRUST_ORDER.index(marker) < TRUST_ORDER.index(floor)
        )
        if below_floor:
            count += 1
            for key in list(attrs):
                if key in CONTENT_ATTRIBUTES:
                    attrs[key] = QUARANTINE_PLACEHOLDER
        for key in also_redact:
            if key in attrs:
                attrs[key] = "[REDACTED]"
        new = dict(span)
        new["attributes"] = attrs
        out.append(new)
    return out, count


def quarantine_resource(resource: dict, keys=()) -> dict:
    """Strip named resource attributes (deployment secrets) before a consumer."""
    return {
        k: ("[REDACTED]" if k in keys else v) for k, v in resource.items()
    }


if __name__ == "__main__":
    ok, hits = no_provenance_attribute_exists()
    print(f"GenAI registry snapshot: {len(GEN_AI_REGISTRY_SNAPSHOT_2026_07)} attributes")
    print(f"attributes expressing content trust/provenance: {len(hits)} {hits}")
    print(f"gap confirmed (Proposal A is not redundant): {ok}")
