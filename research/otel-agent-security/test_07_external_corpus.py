"""
The proposed control against an externally authored corpus, not our own payload.

Part of a trust-boundary proposal to the OpenTelemetry GenAI semantic
conventions group. See the README for the proposal and its references.

Every other test in this suite uses a payload we wrote. That answers "does the
control work on the attack we had in mind", which is the weakest question a
security control can be asked. This module runs the same control over the 42
payloads published with LogJack (arXiv:2604.15368, MIT, vendored under
`external_corpus/` with its notice), which were written by someone else, for a
different pipeline, against different agents, before we existed.

The property under test is the one that makes the marker worth standardising:

    quarantine reads ONE ATTRIBUTE and never parses content, so its behaviour
    cannot vary with how clever the payload is.

That is a falsifiable claim and this is what falsifies it. A content-inspecting
defence would be expected to do worse on `obfuscated` than on `obvious`. If ours
varies at all by difficulty or category, the content-agnostic claim is false and
the note has to say so.

Declared before the run (TBB Stage-1):
  32/32 attack payloads withheld, 10/10 benign controls handled identically,
  zero variation across difficulty and category                    -> required
  name-based inference under a vendor attribute withholds 0/42     -> required

What this module does NOT do: reproduce the LogJack paper's results, run their
agents, or measure the models they tested. Their numbers are theirs. We borrow
the corpus, not the findings.
"""

from __future__ import annotations

import json
import pathlib
from collections import Counter

import gen_ai_content_trust as trust
import pytest
from otlp_harness import WireSession, render_for_model

CORPUS_PATH = pathlib.Path(__file__).parent / "external_corpus" / "logjack-30.json"

# The corpus marks its benign controls with these sentinels rather than omitting
# the fields, so "no attack" is explicit rather than inferred from absence.
BENIGN = "none"


def _load():
    payloads = json.loads(CORPUS_PATH.read_text())["payloads"]
    attacks = [p for p in payloads if p["difficulty"] != BENIGN]
    benign = [p for p in payloads if p["difficulty"] == BENIGN]
    return payloads, attacks, benign


@pytest.fixture(scope="module")
def corpus():
    return _load()


def _capture_as_tool_result(session, payload, attribute="gen_ai.tool.call.result"):
    """Land one corpus payload where GenAI telemetry would carry it.

    LogJack's payloads arrive in cloud logs. The same bytes reaching an agent as
    a tool result is the GenAI-conventions shape of the same event, which is the
    translation this suite is about.
    """
    with session.tracer.start_as_current_span(f"execute_tool {payload['category']}") as span:
        span.set_attribute("gen_ai.tool.name", payload["category"])
        span.set_attribute("gen_ai.operation.name", "execute_tool")
        trust.mark_span(span, attribute, payload["message"])
    return payload


def test_the_corpus_is_what_we_think_it_is(corpus):
    """Guard the vendored file, so a silent edit cannot quietly change a result."""
    payloads, attacks, benign = corpus
    assert len(payloads) == 42
    assert len(attacks) == 32
    assert len(benign) == 10
    assert set(Counter(p["category"] for p in payloads)) == {
        "cloudwatch", "ssm_error_report", "cicd", "cloudtrail", "lambda"
    }
    assert set(p["difficulty"] for p in attacks) == {"obvious", "disguised", "obfuscated"}
    # Every attack payload actually carries the command it claims to.
    for p in attacks:
        assert p["injected_command"], f"{p['id']} has no injected command"


def test_quarantine_withholds_every_attack_payload(corpus):
    """The declared threshold: 32/32, over payloads we did not write."""
    _, attacks, _ = corpus
    withheld = 0
    with WireSession() as session:
        for payload in attacks:
            _capture_as_tool_result(session, payload)
        session.flush()
        spans = session.receiver.spans
        safe, quarantined = trust.quarantine(spans, floor=trust.MODEL_GENERATED)

    assert len(spans) == len(attacks)
    assert quarantined == len(attacks), f"withheld {quarantined} of {len(attacks)}"

    # And the payload is genuinely gone from what a consumer would assemble.
    prompt = render_for_model(safe, {})
    for payload in attacks:
        assert payload["injected_command"] not in prompt, (
            f"{payload['id']}: the injected command survived into the consumer prompt"
        )
        withheld += 1
    assert withheld == 32


def test_coverage_does_not_vary_with_difficulty(corpus):
    """The claim that justifies standardising the marker rather than a detector.

    `obvious`, `disguised` and `obfuscated` are the corpus author's grading of how
    hard the injection is to spot. A content-inspecting defence should degrade
    across that axis. This one cannot, because it never looks at the content, and
    this test is what would catch it if that were untrue.
    """
    _, attacks, _ = corpus
    by_difficulty = {}
    for difficulty in ("obvious", "disguised", "obfuscated"):
        group = [p for p in attacks if p["difficulty"] == difficulty]
        with WireSession() as session:
            for payload in group:
                _capture_as_tool_result(session, payload)
            session.flush()
            _, quarantined = trust.quarantine(session.receiver.spans, floor=trust.MODEL_GENERATED)
        by_difficulty[difficulty] = (quarantined, len(group))

    assert by_difficulty == {
        "obvious": (4, 4),
        "disguised": (19, 19),
        "obfuscated": (9, 9),
    }, f"coverage varied by difficulty: {by_difficulty}"


def test_coverage_does_not_vary_with_surface(corpus):
    """Same argument across the five telemetry surfaces the corpus spans."""
    payloads, _, _ = corpus
    for category in ("cloudwatch", "ssm_error_report", "cicd", "cloudtrail", "lambda"):
        group = [p for p in payloads if p["category"] == category]
        with WireSession() as session:
            for payload in group:
                _capture_as_tool_result(session, payload)
            session.flush()
            _, quarantined = trust.quarantine(session.receiver.spans, floor=trust.MODEL_GENERATED)
        assert quarantined == len(group), (
            f"{category}: withheld {quarantined} of {len(group)}"
        )


def test_benign_controls_are_treated_identically(corpus):
    """The control is content-agnostic in both directions, and that is a cost.

    The ten benign payloads are withheld too, because a tool result is a tool
    result and the marker says nothing about whether this particular one is
    hostile. That is the honest trade: the control is a trust-floor decision, not
    a detector, so it cannot give the consumer safe tool output while withholding
    dangerous tool output. A deployment that needs the benign content readable
    has to raise the floor or route it to a human sink, not ask the marker to
    discriminate.
    """
    _, _, benign = corpus
    with WireSession() as session:
        for payload in benign:
            _capture_as_tool_result(session, payload)
        session.flush()
        safe, quarantined = trust.quarantine(session.receiver.spans, floor=trust.MODEL_GENERATED)

    assert quarantined == len(benign) == 10
    # The operational metadata a consumer actually needs still survives.
    for span in safe:
        assert span["attributes"]["gen_ai.operation.name"] == "execute_tool"
        assert span["attributes"]["gen_ai.tool.name"]


def test_name_based_inference_fails_across_the_whole_corpus(corpus):
    """The load-bearing argument, at corpus scale rather than on one example.

    Record identical content under a vendor attribute and a consumer inferring
    trust from conventional attribute names has nothing to match, on all 42.
    """
    payloads, _, _ = corpus
    with WireSession() as session:
        for payload in payloads:
            with session.tracer.start_as_current_span("execute_tool vendor") as span:
                span.set_attribute("llm.tool.output", payload["message"])
        session.flush()
        inferred = trust.apply_trust_markers(session.receiver.spans)
        _, quarantined = trust.quarantine(inferred, floor=trust.MODEL_GENERATED)
        leaked = render_for_model(inferred, {})

    assert quarantined == 0, "name-based inference had nothing to match, as expected"
    attacks = [p for p in payloads if p["difficulty"] != BENIGN]
    assert all(p["message"] in leaked for p in attacks), (
        "every attack payload passed straight through to the consumer"
    )


def test_literal_command_matching_would_miss_a_fifth_of_this_corpus(corpus):
    """An incidental property of the corpus, and a good argument against grepping.

    Found by a failing assertion of ours rather than looked for: in 6 of the 32
    attack payloads the `injected_command` is not a literal substring of the
    `message` that carries it. The corpus obfuscates it with shell line
    continuations, splits it across lines, or embeds it in JSON with escaping.

    A defence that searches captured content for known-bad command strings would
    therefore miss those six while passing the other twenty-six, which is the
    brittleness that makes content matching a poor primary control. Stated
    narrowly: this is a property of one corpus, measured here, not a general
    claim about detector efficacy.

    It also explains why the quarantine tests above do not assert on the command
    string: the control does not look for it, and neither should its test.
    """
    _, attacks, _ = corpus
    literal_miss = [p for p in attacks if p["injected_command"] not in p["message"]]

    assert len(literal_miss) == 6, (
        f"expected 6 obfuscated-command payloads, found {len(literal_miss)}: "
        f"{[p['id'] for p in literal_miss]}"
    )
    # The command is absent as a literal string, and the payload is intact regardless.
    for payload in literal_miss:
        assert payload["message"], f"{payload['id']} still carries its message"
    # Marker-driven quarantine is unaffected, because it never looked.
    with WireSession() as session:
        for payload in literal_miss:
            _capture_as_tool_result(session, payload)
        session.flush()
        _, quarantined = trust.quarantine(session.receiver.spans, floor=trust.MODEL_GENERATED)
    assert quarantined == len(literal_miss) == 6


def test_the_corpus_payloads_survive_the_wire_unmarked_by_default(corpus):
    """Without the proposal, the whole corpus lands on a consumer with no signal.

    This is the baseline the marker changes, restated over someone else's data so
    it is not an artefact of how we wrote our own payload.
    """
    _, attacks, _ = corpus
    sample = attacks[:8]
    with WireSession() as session:
        for payload in sample:
            with session.tracer.start_as_current_span("execute_tool cloud") as span:
                span.set_attribute("gen_ai.tool.call.result", payload["message"])
        session.flush()
        keys = session.receiver.all_attribute_keys()
        received = [s["attributes"]["gen_ai.tool.call.result"] for s in session.receiver.spans]

    assert trust.TRUST not in keys
    assert not [k for k in keys if trust.looks_like_provenance(k)]
    for payload, got in zip(sample, received):
        assert got == payload["message"], "content crosses the wire byte-identical"
