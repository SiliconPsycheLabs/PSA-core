"""Langfuse → PSA adapter.

Flow:
  1. Your app traces an LLM generation in Langfuse
  2. Call PSAObserver.score(trace_id, response_text, user_text=...)
  3. PSA /analyze runs all classifiers (C0–C4) and behavioral metrics
  4. Aggregate metrics (Option A) are written back to Langfuse as scores on that trace

Scores written:
  psa_bhs        — Behavioral Health Score (0–1, high = healthy)          NUMERIC
  psa_alert      — "green" / "yellow" / "red"                             CATEGORICAL
  psa_c1_poi     — C1 Posture Oscillation Index (spread of postures)      NUMERIC
  psa_c1_mps     — C1 Most Prevalent Posture (modal class id)             NUMERIC
  psa_c2_sd      — C2 sentiment deviation                                 NUMERIC
  psa_c3_hri     — C3 harmful response index                              NUMERIC
  psa_c4_pd      — C4 persona drift                                       NUMERIC
  psa_c0_cpi     — C0 contextual pressure index                           NUMERIC
  psa_drm_alert  — "green"/"yellow"/"critical" (only when user_text given) CATEGORICAL

Usage:
    from psa.adapters.langfuse import PSAObserver

    observer = PSAObserver(session_name="my-session")
    result = observer.score(
        trace_id=langfuse_trace.id,
        response_text=llm_output,
        user_text=user_message,   # optional — enables IRS + DRM
    )
"""
from __future__ import annotations

import os
from typing import Optional

try:
    from langfuse import Langfuse
    from langfuse import observe as _lf_observe  # noqa: F401 — re-exported for convenience
except ImportError:
    raise ImportError("pip install langfuse>=4.0")

from .._client_factory import get_client
from ..client import PSAClient

# (name, value, data_type) — value is float for NUMERIC, str for CATEGORICAL
_Score = tuple[str, "float | str", str]


class PSAObserver:
    """Write PSA behavioral scores back to a Langfuse trace after each LLM generation."""

    def __init__(
        self,
        session_name: str,
        psa_client: Optional[PSAClient] = None,
        langfuse_client: Optional[Langfuse] = None,
    ):
        self.session_name = session_name
        self._psa = psa_client or get_client()
        self._lf = langfuse_client or Langfuse(
            public_key=os.environ.get("LANGFUSE_PUBLIC_KEY"),
            secret_key=os.environ.get("LANGFUSE_SECRET_KEY"),
            host=os.environ.get("LANGFUSE_BASE_URL", "https://cloud.langfuse.com"),
        )

    def score(
        self,
        trace_id: str,
        response_text: str,
        user_text: Optional[str] = None,
        observation_id: Optional[str] = None,
    ) -> dict:
        """Analyze response_text with PSA and write aggregate metrics to Langfuse.

        Args:
            trace_id: Langfuse trace ID to attach scores to.
            response_text: The LLM response to score.
            user_text: The user message that produced the response. Enables IRS + DRM.
            observation_id: Optional Langfuse observation/span ID for finer-grained attachment.

        Returns:
            Raw PSA /analyze response dict.
        """
        result = self._psa.analyze(
            response_text=response_text,
            user_text=user_text,
            session_name=self.session_name,
        )

        for name, value, data_type in _extract_scores(result):
            self._lf.create_score(
                trace_id=trace_id,
                observation_id=observation_id,
                name=name,
                value=value,
                data_type=data_type,
            )

        return result

    def flush(self) -> None:
        """Flush pending Langfuse scores. Required in short-lived scripts."""
        self._lf.flush()


def _extract_scores(r: dict) -> list[_Score]:
    """Map PSA analyze response to (score_name, value, data_type) tuples."""
    out: list[_Score] = []

    bhs = r.get("bhs")
    if bhs is not None:
        out.append(("psa_bhs", float(bhs), "NUMERIC"))

    alert = r.get("alert", "green")
    out.append(("psa_alert", alert, "CATEGORICAL"))

    c1 = r.get("c1") or {}
    if "poi" in c1:
        out.append(("psa_c1_poi", float(c1["poi"]), "NUMERIC"))
    if "mps" in c1:
        out.append(("psa_c1_mps", float(c1["mps"]), "NUMERIC"))

    c2 = r.get("c2") or {}
    if "sd" in c2:
        out.append(("psa_c2_sd", float(c2["sd"]), "NUMERIC"))

    c3 = r.get("c3") or {}
    if "hri" in c3:
        out.append(("psa_c3_hri", float(c3["hri"]), "NUMERIC"))

    c4 = r.get("c4") or {}
    if "pd" in c4:
        out.append(("psa_c4_pd", float(c4["pd"]), "NUMERIC"))

    c0 = r.get("c0") or {}
    if "cpi" in c0:
        out.append(("psa_c0_cpi", float(c0["cpi"]), "NUMERIC"))

    drm = r.get("drm") or {}
    drm_alert = drm.get("drm_alert")
    if drm_alert:
        out.append(("psa_drm_alert", drm_alert, "CATEGORICAL"))

    return out
