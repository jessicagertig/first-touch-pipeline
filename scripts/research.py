"""Step 1 — Research a lead's company and individual recipient.

Gathers raw material (company website, what they do, recipient role, notes)
via the 01-research prompt + a web-search-enabled Claude call. Writes the
research JSON to output/<lead_id>/research.json and returns it.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from scripts.utils import (
    RESEARCH_MODEL,
    WEB_SEARCH_TOOL,
    REPO_ROOT,
    call_json,
    extract_text,
    fetch_url,
    load_prompt,
    parse_json,
)

_HOMEPAGE_MAX_CHARS = 8000


def _output_dir(lead_id: str) -> Path:
    d = REPO_ROOT / "output" / lead_id
    d.mkdir(parents=True, exist_ok=True)
    return d


def _first_name(recipient_name: str) -> str:
    return (recipient_name or "").strip().split(" ")[0] if recipient_name else ""


def _fetch_homepage(domain: str) -> tuple[str, str]:
    """Fetch the lead's own site directly (it may be too new to be indexed).

    Returns (url, content). content is "" when nothing usable came back.
    """
    domain = (domain or "").strip().strip("/")
    if not domain:
        return "", ""
    url = domain if domain.startswith("http") else f"https://{domain}"
    text = fetch_url(url)
    if not text or text.startswith("[fetch failed"):
        return url, ""
    return url, text[:_HOMEPAGE_MAX_CHARS]


def research_lead(lead: dict) -> dict:
    """Research a lead's company + recipient; write and return the research JSON.

    Uses the 01-research prompt as the system prompt and a user message carrying
    the concrete signup inputs, with web search enabled so Claude can read the
    live company site.
    """
    system = load_prompt("01-research")
    inputs = {
        "first_name": _first_name(lead.get("recipient_name", "")),
        "email": lead.get("email", ""),
        "org_name": lead.get("company_name", ""),
        "email_domain": lead.get("email_domain", ""),
    }
    home_url, home_text = _fetch_homepage(inputs["email_domain"])
    homepage_block = ""
    if home_text:
        homepage_block = (
            f"\nFirst-party homepage content, fetched directly from {home_url} "
            "(the site may be too new to appear in web search — trust this as a "
            "primary source and use it):\n"
            f"\"\"\"\n{home_text}\n\"\"\"\n"
        )

    user = (
        "Research this signup. Inputs:\n"
        f"{json.dumps(inputs, indent=2)}\n"
        f"{homepage_block}\n"
        "Return the research JSON exactly as specified."
    )
    research = call_json(
        model=RESEARCH_MODEL,
        messages=[{"role": "user", "content": user}],
        system=system,
        tools=[WEB_SEARCH_TOOL],
        label="research",
    )
    if not isinstance(research, dict):
        research = {}

    out = _output_dir(lead["lead_id"]) / "research.json"
    out.write_text(json.dumps(research, indent=2), encoding="utf-8")
    return research
