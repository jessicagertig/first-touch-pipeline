"""Step 2 — Extract candidate facts worth complimenting.

Takes the step-1 research JSON and surfaces specific, distinctive candidate
items (verbatim quotes with sources) via the 02-extract prompt. Web search is
enabled so Claude can read the live site for verbatim quotes. Writes the
candidates JSON to output/<lead_id>/candidates.json and returns it.
"""
from __future__ import annotations

import json
from typing import Any

from scripts.utils import (
    RESEARCH_MODEL,
    WEB_SEARCH_TOOL,
    REPO_ROOT,
    call_json,
    extract_text,
    load_prompt,
    parse_json,
)


def extract_candidates(lead: dict, research: dict) -> dict:
    """Surface candidate facts from research; write and return candidates JSON.

    Returns a dict with key "candidates" (a list). Uses the 02-extract prompt as
    the system prompt; the research JSON is passed verbatim in the user message.
    """
    system = load_prompt("02-extract")
    user = (
        "Here is the step-1 research JSON. Extract the candidate facts.\n\n"
        f"{json.dumps(research, indent=2)}\n\n"
        "Return the candidates JSON exactly as specified."
    )
    parsed: Any = call_json(
        model=RESEARCH_MODEL,
        messages=[{"role": "user", "content": user}],
        system=system,
        tools=[WEB_SEARCH_TOOL],
        label="extract",
    )
    if isinstance(parsed, list):
        parsed = {"candidates": parsed}
    if not isinstance(parsed, dict):
        parsed = {}
    parsed.setdefault("candidates", [])

    out = REPO_ROOT / "output" / lead["lead_id"] / "candidates.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(parsed, indent=2), encoding="utf-8")
    return parsed
