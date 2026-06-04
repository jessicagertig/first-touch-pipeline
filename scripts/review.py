"""Step 5 — Adversarial review of draft variations.

Scores each variation on how much it reads like Jessica's real compliments
(05-adversarial-reviewer prompt). This judges the WRITING, not the facts.
Adds {score:int, tells:list, verdict} to each variation.
"""
from __future__ import annotations

import json
from typing import Any

from scripts.utils import (
    DRAFT_MODEL,
    call_anthropic,
    extract_text,
    load_prompt,
    parse_json,
)


def _score_one(prompt: str, variation: dict) -> dict:
    user = (
        "Critique this draft. The fact(s) it used are already verified — judge "
        "only the writing/voice.\n\n"
        "Draft email:\n"
        f"{variation.get('email', '')}\n\n"
        "Fact source(s) it used:\n"
        f"{json.dumps(variation.get('source_urls', []), indent=2)}\n\n"
        "Return the review JSON exactly as specified."
    )
    response = call_anthropic(
        model=DRAFT_MODEL,
        messages=[{"role": "user", "content": user}],
        system=prompt,
        label="review",
    )
    review: dict[str, Any] = parse_json(extract_text(response))
    try:
        score = int(review.get("score", 0))
    except (TypeError, ValueError):
        score = 0
    return {
        "score": score,
        "tells": review.get("tells", []),
        "verdict": review.get("verdict", "revise"),
    }


def score_variations(variations: list[dict]) -> list[dict]:
    """Score each variation in place-ish; return new dicts with review fields.

    Adds {score, tells, verdict} to each variation per 05-adversarial-reviewer.
    """
    prompt = load_prompt("05-adversarial-reviewer")
    scored: list[dict] = []
    for variation in variations:
        review = _score_one(prompt, variation)
        scored.append({**variation, **review})
    return scored
