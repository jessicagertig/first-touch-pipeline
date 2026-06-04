"""Step 6 — Revise a flagged variation.

Rewrites a flagged variation's compliment from scratch in Jessica's voice
(06-revise prompt), eliminating the reviewer's flagged tells and using only the
verified facts. Returns a new variation dict with the rebuilt email.
"""
from __future__ import annotations

import json
from typing import Any

from scripts.utils import (
    DRAFT_MODEL,
    call_json,
    extract_text,
    library_compliments_text,
    load_prompt,
    parse_json,
)


def revise_variation(
    variation: dict,
    tells: list[str],
    verified_facts: list[dict],
) -> dict:
    """Rewrite a flagged variation's compliment; return an updated variation.

    A from-scratch rewrite (not an edit) per 06-revise. Keeps the fixed
    template, changing only the [compliment]; the full email is reassembled via
    build_email().
    """
    from scripts.service_lead import build_email  # local import avoids cycle

    prompt = load_prompt("06-revise")
    system = (
        f"{prompt}\n\n"
        "## Her real compliments (the voice — match these)\n"
        "Each line is one real compliment Jessica sent. Do not copy any line "
        "verbatim; write a new one that would fit right in.\n"
        f"{library_compliments_text()}\n\n"
        "## Output format (JSON only)\n"
        'Return ONLY JSON: {"compliment": "<the rewritten single-sentence '
        'compliment>", "source_urls": ["..."]}\n'
        "The compliment MUST lead with the company name, be ONE sentence, and "
        "use only the verified facts provided."
    )
    user = (
        "The flagged draft:\n"
        f"{variation.get('email', '')}\n\n"
        "Reviewer tells to eliminate:\n"
        f"{json.dumps(tells, indent=2)}\n\n"
        "Verified details (verbatim, with sources) — use ONLY these:\n"
        f"{json.dumps(verified_facts, indent=2)}\n\n"
        "Rewrite the compliment. Return the JSON described."
    )

    parsed: Any = call_json(
        model=DRAFT_MODEL,
        messages=[{"role": "user", "content": user}],
        system=system,
        label="revise",
    )
    if isinstance(parsed, list):  # model sometimes wraps the object in a list
        parsed = next((x for x in parsed if isinstance(x, dict)), {})
    if not isinstance(parsed, dict):
        parsed = {}
    compliment = (parsed.get("compliment") or "").strip()
    source_urls = parsed.get("source_urls", variation.get("source_urls", []))

    recipient_name = variation.get("recipient_name", "") or variation.get("_recipient_name", "")
    return {
        **variation,
        "compliment": compliment,
        "email": build_email(recipient_name, compliment),
        "source_urls": source_urls,
    }
