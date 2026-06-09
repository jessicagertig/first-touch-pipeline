"""Step 3 — Verify candidate facts are true and current.

verify_candidate runs a single verify pass (03-verify prompt + web search).
verify_with_loop re-runs verification, doing targeted re-research, while the
verdict is true_but_stale/unverifiable, up to VERIFY_MAX_LOOPS; if it never
reaches verified_current the final verdict is marked "surfaced": True.

The orchestrator calls verify_with_loop per candidate and keeps only the
verified-current facts ({fact, source_url}).
"""
from __future__ import annotations

import json
from typing import Any

from scripts.utils import (
    RESEARCH_MODEL,
    WEB_SEARCH_TOOL,
    call_json,
    env,
    extract_text,
    load_prompt,
    parse_json,
)

_STALE_VERDICTS = {"true_but_stale", "unverifiable"}


def verify_candidate(
    company_name: str,
    candidate: dict,
    homepage_url: str = "",
    homepage_text: str = "",
) -> dict:
    """Run ONE verify pass on a single candidate; return the verdict JSON.

    Uses the 03-verify prompt as the system prompt; web search is enabled so
    Claude can attempt to read the live company site for current confirmation.
    When the live homepage was fetched directly, its content is supplied so a
    first-party fact can be confirmed even if the site is too new to be indexed.
    """
    system = load_prompt("03-verify")
    homepage_block = ""
    if homepage_text:
        homepage_block = (
            f"\nLive homepage content, fetched directly from {homepage_url} just "
            "now (first-party, current — trust it; the site may be too new for "
            "web search to index). If this content supports the candidate, that "
            "is verified_current first-party confirmation:\n"
            f"\"\"\"\n{homepage_text}\n\"\"\"\n"
        )
    user = (
        f"Company: {company_name}\n\n"
        "Candidate to verify:\n"
        f"{json.dumps(candidate, indent=2)}\n"
        f"{homepage_block}\n"
        "Return the verify JSON exactly as specified."
    )
    raw = call_json(
        model=RESEARCH_MODEL,
        messages=[{"role": "user", "content": user}],
        system=system,
        tools=[WEB_SEARCH_TOOL],
        label="verify",
    )
    if isinstance(raw, list):  # model sometimes wraps the verdict object in a list
        raw = next((x for x in raw if isinstance(x, dict)), {})
    return raw if isinstance(raw, dict) else {}


def verify_with_loop(
    company_name: str,
    candidate: dict,
    max_loops: int | None = None,
    homepage_url: str = "",
    homepage_text: str = "",
) -> dict:
    """Verify a candidate, looping while stale/unverifiable up to VERIFY_MAX_LOOPS.

    Each pass after the first instructs a targeted re-research of THIS item for
    its current state (per the 03-verify loop guidance). Returns the final
    verdict dict. If it never reaches verified_current, the returned verdict is
    marked with "surfaced": True so the orchestrator can flag it.
    """
    if max_loops is None:
        max_loops = int(env("VERIFY_MAX_LOOPS", "5") or "5")

    verdict: dict[str, Any] = {}
    for _ in range(max(1, max_loops)):
        verdict = verify_candidate(company_name, candidate, homepage_url, homepage_text)
        if verdict.get("verdict") not in _STALE_VERDICTS:
            break
        # Targeted re-research for current state before the next verify pass.
        current = verdict.get("current_state")
        if current:
            candidate = {**candidate, "recency_note": f"prior finding: {current}"}

    if verdict.get("verdict") != "verified_current":
        verdict["surfaced"] = True
    return verdict
