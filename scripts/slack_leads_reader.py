"""Stage A — ingest New-Company Slack posts, qualify, notify.

Reads the New-Company Slack channel (SLACK_LEADS_CHANNEL_ID), parses each
"[production] New Company" message into a lead, qualifies it via
scripts.qualify, and either records a qualified lead and posts a "good lead"
notification to the review channel, or records a skipped lead. A small
high-water-mark file (state/last_ts.txt) tracks the newest processed Slack ts
so each run only sees new messages.
"""
from __future__ import annotations

import argparse
import re
from datetime import datetime, timezone
from pathlib import Path

from scripts import qualify
from scripts.utils import (
    REPO_ROOT,
    env,
    lead_exists,
    post_error_to_slack,
    slack_history,
    slack_post,
    upsert_lead,
)

STATE_TS_PATH = REPO_ROOT / "state" / "last_ts.txt"

# Tolerant of Slack's <url> / <url|label> wrappers and surrounding markup.
NAME_RE = re.compile(r"Name:\s*<?([^>\n|]+?)>?\s*$", re.IGNORECASE | re.MULTILINE)
CREATED_BY_RE = re.compile(
    r"Created By:\s*<?([^>\n|<]+?)>?\s*-\s*<?(?:mailto:)?"
    r"([A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,})",
    re.IGNORECASE,
)
CAREERS_SLUG_RE = re.compile(r"jobs\.polymer\.co/([A-Za-z0-9._\-]+)", re.IGNORECASE)


def slugify(text: str) -> str:
    """Lowercase, non-alphanumerics collapsed to single hyphens, trimmed."""
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _read_last_ts() -> str | None:
    if STATE_TS_PATH.exists():
        ts = STATE_TS_PATH.read_text(encoding="utf-8").strip()
        return ts or None
    return None


def _write_last_ts(ts: str) -> None:
    STATE_TS_PATH.parent.mkdir(parents=True, exist_ok=True)
    STATE_TS_PATH.write_text(ts, encoding="utf-8")


def _is_new_company_message(text: str) -> bool:
    return "[production]" in text and "New Company" in text


def _parse_message(text: str) -> dict | None:
    """Extract lead fields from a New-Company message text, or None if unusable."""
    created = CREATED_BY_RE.search(text)
    if not created:
        return None
    recipient_name = created.group(1).strip()
    email = created.group(2).strip()

    name_match = NAME_RE.search(text)
    company_name = name_match.group(1).strip() if name_match else ""

    slug_match = CAREERS_SLUG_RE.search(text)
    careers_slug = slug_match.group(1).strip() if slug_match else ""

    return {
        "company_name": company_name,
        "recipient_name": recipient_name,
        "email": email,
        "careers_slug": careers_slug,
    }


def _good_lead_blocks(lead: dict) -> list[dict]:
    slug = lead.get("careers_slug", "")
    link = f"https://jobs.polymer.co/{slug}" if slug else "(no careers link)"
    text = (
        f":white_check_mark: *Good lead* — {lead['company_name']}\n"
        f"*Recipient:* {lead['recipient_name']}\n"
        f"*Email:* {lead['email']}\n"
        f"*Careers:* {link}"
    )
    return [{"type": "section", "text": {"type": "mrkdwn", "text": text}}]


def _process_message(msg: dict) -> bool:
    """Process one Slack message. Returns True if it became a lead row."""
    ts = msg.get("ts", "")
    text = msg.get("text", "") or ""
    if not _is_new_company_message(text):
        return False

    parsed = _parse_message(text)
    if not parsed:
        return False

    email = parsed["email"]
    if lead_exists(email=email) or lead_exists(slack_ts=ts):
        return False

    email_domain = qualify.domain_of(email)
    lead_id = parsed["careers_slug"] or slugify(f"{parsed['company_name']}-{ts}")

    row: dict = {
        "lead_id": lead_id,
        "slack_ts": ts,
        "company_name": parsed["company_name"],
        "recipient_name": parsed["recipient_name"],
        "email": email,
        "email_domain": email_domain,
        "careers_slug": parsed["careers_slug"],
    }

    passes, reason = qualify.qualify(email)
    if passes:
        row["status"] = "qualified"
        row["qualified_at"] = _utcnow_iso()
        upsert_lead(row)
        good_leads_channel = env("SLACK_GOOD_LEADS_CHANNEL_ID")
        if good_leads_channel:
            slack_post(good_leads_channel, blocks=_good_lead_blocks(row))
    else:
        row["status"] = "skipped"
        row["skip_reason"] = reason
        upsert_lead(row)
    return True


def main() -> None:
    """CLI entry point: read new messages, qualify, notify, advance the HWM."""
    parser = argparse.ArgumentParser(description="Stage A: ingest New-Company Slack leads.")
    parser.add_argument("--limit", type=int, default=200,
                        help="Per-page Slack history limit (default 200).")
    args = parser.parse_args()

    channel = env("SLACK_LEADS_CHANNEL_ID")
    if not channel:
        post_error_to_slack("SLACK_LEADS_CHANNEL_ID not set; cannot read leads")
        raise SystemExit("SLACK_LEADS_CHANNEL_ID not set")

    oldest = _read_last_ts()
    messages = slack_history(channel, oldest=oldest, limit=args.limit)

    newest_ts = oldest
    processed = 0
    for msg in messages:
        ts = msg.get("ts", "")
        try:
            if _process_message(msg):
                processed += 1
        except Exception as exc:  # noqa: BLE001
            post_error_to_slack(f"slack_leads_reader failed on ts={ts}: {exc}")
        if ts and (newest_ts is None or float(ts) > float(newest_ts)):
            newest_ts = ts

    if newest_ts:
        _write_last_ts(newest_ts)

    print(f"[slack_leads_reader] scanned {len(messages)} messages, "
          f"created {processed} lead rows; last_ts={newest_ts}")


if __name__ == "__main__":
    main()
