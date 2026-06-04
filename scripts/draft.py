"""Step 4 — Draft email variations in Jessica's voice.

Builds N first-touch variations grounded only on the verified facts, using the
04-draft prompt and the 88-example library (embedded as JSONL in the prompt).
Each variation's [compliment] is parsed out and assembled into the full fixed
template via build_email().
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


def draft_variations(lead: dict, verified_facts: list[dict], n: int) -> list[dict]:
    """Draft ``n`` variations for a lead from the verified facts.

    Returns a list of {variant_n, compliment, email, source_urls}. The model is
    asked to return only the per-variation compliment (and the source links it
    used); the full email is assembled here with build_email() so the fixed
    template (and the exact blank-line spacing) is guaranteed.
    """
    from scripts.service_lead import build_email  # local import avoids cycle

    recipient_name = lead.get("recipient_name", "")
    prompt = load_prompt("04-draft")

    system = (
        f"{prompt}\n\n"
        "## Her real compliments (the voice — match these)\n"
        "Each line is one real compliment Jessica sent. Do not copy any line "
        "verbatim; write a new one that would fit right in.\n"
        f"{library_compliments_text()}\n\n"
        "## Output format (JSON only)\n"
        "Return ONLY JSON: a list of objects, one per variation, each:\n"
        '{"variant_n": <int>, "compliment": "<a single-sentence compliment, '
        'no greeting/closer/signature>", "source_urls": ["..."]}\n'
        "The compliment MUST lead with the company name, be ONE sentence, and "
        "use only the verified facts provided."
    )
    user = (
        f"first_name: {recipient_name.strip().split(' ')[0] if recipient_name else ''}\n"
        f"org: {lead.get('company_name', '')}\n\n"
        "Verified details (verbatim, with sources) — use ONLY these:\n"
        f"{json.dumps(verified_facts, indent=2)}\n\n"
        f"Write {n} variations. Return the JSON list described."
    )

    parsed: Any = call_json(
        model=DRAFT_MODEL,
        messages=[{"role": "user", "content": user}],
        system=system,
        max_tokens=8192,
        label="draft",
    )
    if isinstance(parsed, dict):
        parsed = parsed.get("variations", [parsed])
    if not isinstance(parsed, list):
        parsed = []

    variations: list[dict] = []
    for i, item in enumerate(parsed, start=1):
        compliment = (item.get("compliment") or "").strip()
        variations.append(
            {
                "variant_n": item.get("variant_n", i),
                "compliment": compliment,
                "email": build_email(recipient_name, compliment),
                "source_urls": item.get("source_urls", []),
            }
        )
    return variations
