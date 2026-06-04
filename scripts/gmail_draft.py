"""Stage C — create a Gmail DRAFT for a chosen variation.

Given a lead and a chosen variation, create a draft email in jessica@polymer.co's
Gmail (it does NOT send) so Jessica reviews it and hits send herself.

Reads output/<lead_id>/variations.json, finds the variation whose variant_n
matches, and drafts its "email" body to the lead's address. On success the lead
is advanced to status="draft_created" with the Gmail draft id recorded, and a
confirmation is posted to the review channel. Missing GOOGLE_* OAuth env vars
produce a clear one-time-setup message and a non-zero exit WITHOUT touching the
lead state; any other failure is captured as status="error" with notes.
"""
from __future__ import annotations

import argparse
import base64
import json
from email.message import EmailMessage
from pathlib import Path
from typing import Any

from scripts.utils import (
    REPO_ROOT,
    env,
    find_lead,
    post_error_to_slack,
    slack_post,
    update_lead,
)

GMAIL_SCOPES = ["https://www.googleapis.com/auth/gmail.compose"]
TOKEN_URI = "https://oauth2.googleapis.com/token"
SUBJECT = "Hello"

OAUTH_ENV_VARS = ("GOOGLE_CLIENT_ID", "GOOGLE_CLIENT_SECRET", "GOOGLE_REFRESH_TOKEN")

_OAUTH_SETUP_MESSAGE = (
    "Gmail OAuth is not configured. gmail_draft.py needs a one-time setup so it "
    "can create drafts in jessica@polymer.co's mailbox:\n"
    "  1. In Google Cloud Console, create (or reuse) an OAuth 2.0 Client ID "
    "(Desktop app) and note its client id + client secret.\n"
    "  2. Run the OAuth consent flow once for jessica@polymer.co, granting the "
    f"scope {GMAIL_SCOPES[0]} (compose — create drafts, not send).\n"
    "  3. Capture the resulting refresh token.\n"
    "  4. Set these in the pipeline .env:\n"
    "       GOOGLE_CLIENT_ID=...\n"
    "       GOOGLE_CLIENT_SECRET=...\n"
    "       GOOGLE_REFRESH_TOKEN=...\n"
    "       GMAIL_SENDER=jessica@polymer.co\n"
)


def _variations_path(lead_id: str) -> Path:
    return REPO_ROOT / "output" / lead_id / "variations.json"


def _load_variation(lead_id: str, variant_n: int) -> dict:
    """Load variations.json and return the variation whose variant_n matches.

    Raises FileNotFoundError if the variations file is missing and ValueError if
    no variation with the requested variant_n is present.
    """
    path = _variations_path(lead_id)
    if not path.exists():
        raise FileNotFoundError(f"variations.json not found at {path}")
    data = json.loads(path.read_text(encoding="utf-8"))
    for variation in data.get("variations", []):
        if int(variation.get("variant_n")) == int(variant_n):
            return variation
    raise ValueError(f"variant_n={variant_n} not found in {path}")


def _gmail_service():
    """Build an authenticated Gmail API service from the GOOGLE_* OAuth env vars."""
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build

    creds = Credentials(
        token=None,
        refresh_token=env("GOOGLE_REFRESH_TOKEN"),
        client_id=env("GOOGLE_CLIENT_ID"),
        client_secret=env("GOOGLE_CLIENT_SECRET"),
        token_uri=TOKEN_URI,
        scopes=GMAIL_SCOPES,
    )
    return build("gmail", "v1", credentials=creds)


def _build_raw_message(*, sender: str, recipient: str, subject: str, body: str) -> str:
    """Compose a MIME message and return its base64url-encoded raw form."""
    message = EmailMessage()
    message["From"] = sender
    message["To"] = recipient
    message["Subject"] = subject
    message.set_content(body)
    return base64.urlsafe_b64encode(message.as_bytes()).decode("ascii")


def create_draft(lead_id: str, variant_n: int) -> str:
    """Create a Gmail draft for the chosen variation; return the Gmail draft id.

    Resolves the lead and the matching variation, composes the email to the
    lead's address under the subject "Hello", and creates (not sends) a draft in
    the GMAIL_SENDER mailbox. On success advances the lead to "draft_created",
    records gmail_draft_id, and posts a confirmation to SLACK_REVIEW_CHANNEL_ID.

    Returns the Gmail draft id. Raises if OAuth env vars are missing (after
    printing setup guidance) or if any step fails (after marking the lead
    status="error" with notes and posting the error to Slack).
    """
    missing = [name for name in OAUTH_ENV_VARS if not env(name)]
    if missing:
        print(_OAUTH_SETUP_MESSAGE)
        print(f"Missing env vars: {', '.join(missing)}")
        raise SystemExit(1)

    sender = env("GMAIL_SENDER")
    if not sender:
        print(_OAUTH_SETUP_MESSAGE)
        print("Missing env var: GMAIL_SENDER")
        raise SystemExit(1)

    try:
        lead = find_lead(lead_id)
        if lead is None:
            raise ValueError(f"lead {lead_id} not found in leads store")
        recipient = (lead.get("email") or "").strip()
        if not recipient:
            raise ValueError(f"lead {lead_id} has no email address")

        variation = _load_variation(lead_id, variant_n)
        body = variation.get("email")
        if not body:
            raise ValueError(
                f"variant_n={variant_n} for lead {lead_id} has an empty email body"
            )

        raw = _build_raw_message(
            sender=sender, recipient=recipient, subject=SUBJECT, body=body,
        )
        service = _gmail_service()
        draft = (
            service.users()
            .drafts()
            .create(userId="me", body={"message": {"raw": raw}})
            .execute()
        )
        draft_id = draft["id"]

        update_lead(lead_id, status="draft_created", gmail_draft_id=draft_id)

        company = lead.get("company_name") or lead_id
        review_channel = env("SLACK_REVIEW_CHANNEL_ID")
        if review_channel:
            slack_post(
                review_channel,
                text=f"Draft created in Gmail for {company} — review & send",
            )
        print(f"[gmail_draft] created draft {draft_id} for lead {lead_id} "
              f"-> {recipient}")
        return draft_id
    except SystemExit:
        raise
    except Exception as exc:  # noqa: BLE001
        note = f"gmail_draft failed: {exc}"
        try:
            update_lead(lead_id, status="error", notes=note)
        except Exception:  # noqa: BLE001 — never lose the original error
            pass
        post_error_to_slack(f"{note} (lead {lead_id}, variant {variant_n})")
        print(f"[gmail_draft] {note}")
        raise


def main() -> None:
    """CLI entry point: create a Gmail draft for a lead's chosen variation."""
    parser = argparse.ArgumentParser(
        description="Stage C: create a Gmail draft for a chosen variation."
    )
    parser.add_argument("--lead", required=True, help="lead_id to draft for.")
    parser.add_argument("--variant", required=True, type=int,
                        help="variant_n of the chosen variation.")
    args = parser.parse_args()
    create_draft(args.lead, args.variant)


if __name__ == "__main__":
    main()
