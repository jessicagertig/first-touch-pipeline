"""Stage B orchestrator — service one qualified lead end-to-end.

research → extract → verify-loop (per candidate) → draft N variations →
score → revise-and-rescore any below the ship threshold (up to a cap) →
write variations.json → mark the lead serviced → post the variations to Slack.

The whole run is wrapped so any failure marks the lead ``error`` (with notes)
and posts to Slack, but never deletes the lead — a later sweep can retry.

Run:  python -m scripts.service_lead --lead <lead_id>
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from scripts.utils import (
    REPO_ROOT,
    env,
    find_lead,
    post_error_to_slack,
    update_lead,
)
from scripts.research import _fetch_homepage, research_lead
from scripts.extract import extract_candidates
from scripts.verify import verify_with_loop
from scripts.draft import draft_variations
from scripts.review import score_variations
from scripts.revise import revise_variation


# --------------------------------------------------------------------------- #
# Email assembly
# --------------------------------------------------------------------------- #
_TEMPLATE = (
    "Hello {first_name},\n\n"
    "Thanks for checking out Polymer! {compliment}\n\n"
    "Happy to answer any questions you might have about Polymer.\n\n"
    "Cheers,\nJessica\n\n\n"
    "Jessica Gertig\nPolymer | polymer.co"
)


def build_email(recipient_name: str, compliment: str) -> str:
    """Assemble the full fixed-template email.

    ``{first_name}`` is the first token of ``recipient_name``. There are EXACTLY
    two blank lines above "Jessica Gertig" so Gmail grays the signature.
    """
    first_name = (recipient_name or "").strip().split(" ")[0] if recipient_name else ""
    return _TEMPLATE.format(first_name=first_name, compliment=(compliment or "").strip())


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _output_path(lead_id: str, name: str) -> Path:
    d = REPO_ROOT / "output" / lead_id
    d.mkdir(parents=True, exist_ok=True)
    return d / name


def _collect_verified_facts(
    company_name: str,
    candidates: list[dict],
    homepage_url: str = "",
    homepage_text: str = "",
) -> list[dict]:
    """Verify each candidate with its loop; return the verified-current facts."""
    facts: list[dict] = []
    for candidate in candidates:
        verdict = verify_with_loop(
            company_name, candidate,
            homepage_url=homepage_url, homepage_text=homepage_text,
        )
        if verdict.get("verdict") == "verified_current":
            fact = verdict.get("verified_fact") or candidate.get("item", "")
            source = ""
            evidence = verdict.get("evidence") or []
            if evidence and isinstance(evidence, list):
                source = evidence[0].get("source_url", "") if isinstance(evidence[0], dict) else ""
            if not source:
                source = candidate.get("source_url", "")
            if fact:
                facts.append({"fact": fact, "source_url": source})
    return facts


# --------------------------------------------------------------------------- #
# Review / revise loop
# --------------------------------------------------------------------------- #
def _review_loop(
    recipient_name: str,
    variations: list[dict],
    verified_facts: list[dict],
    ship_score: int,
    max_rounds: int,
) -> list[dict]:
    """Score, then revise+rescore any sub-threshold variation up to max_rounds."""
    scored = score_variations(variations)

    final: list[dict] = []
    for variation in scored:
        rounds = 0
        while variation.get("score", 0) < ship_score and rounds < max_rounds:
            revised = revise_variation(
                {**variation, "_recipient_name": recipient_name},
                variation.get("tells", []),
                verified_facts,
            )
            (rescored,) = score_variations([revised])
            variation = rescored
            rounds += 1
        variation = {
            k: v for k, v in variation.items() if k != "_recipient_name"
        }
        variation["ship"] = variation.get("score", 0) >= ship_score
        final.append(variation)
    return final


# --------------------------------------------------------------------------- #
# Orchestration
# --------------------------------------------------------------------------- #
def service_lead(lead_id: str) -> None:
    """Service one lead through Stage B; write artifacts and post to Slack."""
    lead = find_lead(lead_id)
    if lead is None:
        raise KeyError(f"lead not found: {lead_id}")

    n = int(env("DRAFT_VARIATIONS", "5") or "5")
    ship_score = int(env("REVIEW_SHIP_SCORE", "8") or "8")
    max_rounds = int(env("REVIEW_MAX_ROUNDS", "5") or "5")

    try:
        research = research_lead(lead)
        candidates_doc = extract_candidates(lead, research)
        candidates = candidates_doc.get("candidates", [])

        homepage_url, homepage_text = _fetch_homepage(lead.get("email_domain", ""))
        verified_facts = _collect_verified_facts(
            lead.get("company_name", ""), candidates, homepage_url, homepage_text,
        )
        _output_path(lead_id, "verified.json").write_text(
            json.dumps(verified_facts, indent=2), encoding="utf-8"
        )

        if not verified_facts:
            msg = f"no usable verified facts for lead {lead_id}"
            update_lead(lead_id, notes=msg)
            post_error_to_slack(msg)
            return

        variations = draft_variations(lead, verified_facts, n)
        final = _review_loop(
            lead.get("recipient_name", ""),
            variations,
            verified_facts,
            ship_score,
            max_rounds,
        )

        variations_doc = {
            "lead_id": lead_id,
            "company_name": lead.get("company_name", ""),
            "recipient_name": lead.get("recipient_name", ""),
            "email": lead.get("email", ""),
            "variations": final,
        }
        _output_path(lead_id, "variations.json").write_text(
            json.dumps(variations_doc, indent=2), encoding="utf-8"
        )

        update_lead(lead_id, status="serviced", serviced_at=_utcnow_iso())

        from scripts.slack_post_variations import post_variations  # owned elsewhere
        post_variations(lead_id)

    except Exception as exc:  # noqa: BLE001
        update_lead(lead_id, status="error", notes=str(exc))
        post_error_to_slack(f"servicing lead {lead_id} failed: {exc}")
        raise


def main() -> None:
    parser = argparse.ArgumentParser(description="Service one qualified lead (Stage B).")
    parser.add_argument("--lead", required=True, help="lead_id to service")
    args = parser.parse_args()
    service_lead(args.lead)


if __name__ == "__main__":
    main()
