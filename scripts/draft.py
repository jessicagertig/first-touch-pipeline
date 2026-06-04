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
    call_anthropic,
    extract_text,
    library_jsonl_text,
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
        "## The library (the 88 real example emails, as JSONL)\n"
        "Treat each line below as one of Jessica's real first-touch emails. "
        "Study HOW she writes; do not copy any line verbatim.\n"
        "```jsonl\n"
        f"{library_jsonl_text()}\n"
        "```\n\n"
        "## Output format (JSON only)\n"
        "Return ONLY JSON: a list of objects, one per variation, each:\n"
        '{"variant_n": <int>, "compliment": "<just the compliment sentence(s), '
        'no greeting/closer/signature>", "source_urls": ["..."]}\n'
        "The compliment MUST lead with the company name and use only the "
        "verified facts provided."
    )
    user = (
        f"first_name: {recipient_name.strip().split(' ')[0] if recipient_name else ''}\n"
        f"org: {lead.get('company_name', '')}\n\n"
        "Verified details (verbatim, with sources) — use ONLY these:\n"
        f"{json.dumps(verified_facts, indent=2)}\n\n"
        f"Write {n} variations. Return the JSON list described."
    )

    response = call_anthropic(
        model=DRAFT_MODEL,
        messages=[{"role": "user", "content": user}],
        system=system,
        max_tokens=8192,
        label="draft",
    )
    parsed: Any = parse_json(extract_text(response))
    if isinstance(parsed, dict):
        parsed = parsed.get("variations", [parsed])

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
