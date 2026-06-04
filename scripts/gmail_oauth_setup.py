"""One-time helper to mint a Gmail refresh token for jessica@polymer.co.

Run this ONCE locally. It opens a browser, you consent as jessica@polymer.co,
and it prints the three values to paste into .env:
    GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET, GOOGLE_REFRESH_TOKEN

The pipeline (Stage C, scripts/gmail_draft.py) uses that refresh token to create
drafts via the Gmail API — it never needs the browser again.

## Google Cloud setup (do once, in the Google Cloud Console)
1. Create/Select a project. Enable the **Gmail API** (APIs & Services → Library).
2. OAuth consent screen: User type can be Internal (Workspace) — add
   jessica@polymer.co as a test/allowed user if External.
3. Credentials → Create Credentials → **OAuth client ID** → Application type
   **Desktop app**. Download the JSON (call it client_secret.json).
4. Run:  python -m scripts.gmail_oauth_setup --client-secret client_secret.json
   (or pass --client-id / --client-secret-value instead of the file).

Scope requested: https://www.googleapis.com/auth/gmail.compose  (create drafts;
cannot read your mail).
"""
from __future__ import annotations

import argparse
import json
import sys
import tempfile

SCOPES = ["https://www.googleapis.com/auth/gmail.compose"]


def _flow_from_client_config(client_id: str, client_secret: str):
    from google_auth_oauthlib.flow import InstalledAppFlow
    config = {
        "installed": {
            "client_id": client_id,
            "client_secret": client_secret,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": ["http://localhost"],
        }
    }
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as fh:
        json.dump(config, fh)
        path = fh.name
    return InstalledAppFlow.from_client_secrets_file(path, SCOPES)


def main() -> int:
    ap = argparse.ArgumentParser(description="Mint a Gmail refresh token (one-time).")
    ap.add_argument("--client-secret", help="path to the downloaded OAuth client_secret.json")
    ap.add_argument("--client-id", help="OAuth client id (instead of the json file)")
    ap.add_argument("--client-secret-value", help="OAuth client secret (with --client-id)")
    args = ap.parse_args()

    try:
        from google_auth_oauthlib.flow import InstalledAppFlow
    except ImportError:
        print("Missing deps. Run:  pip install -r requirements.txt", file=sys.stderr)
        return 1

    if args.client_secret:
        flow = InstalledAppFlow.from_client_secrets_file(args.client_secret, SCOPES)
    elif args.client_id and args.client_secret_value:
        flow = _flow_from_client_config(args.client_id, args.client_secret_value)
    else:
        print("Provide --client-secret <client_secret.json>  OR  "
              "--client-id <id> --client-secret-value <secret>", file=sys.stderr)
        return 2

    creds = flow.run_local_server(port=0, prompt="consent")  # opens browser

    print("\n=== Paste these into .env ===")
    print(f"GOOGLE_CLIENT_ID={creds.client_id}")
    print(f"GOOGLE_CLIENT_SECRET={creds.client_secret}")
    print(f"GOOGLE_REFRESH_TOKEN={creds.refresh_token}")
    if not creds.refresh_token:
        print("\n(!) No refresh_token returned — revoke prior access at "
              "myaccount.google.com/permissions and re-run; the prompt=consent "
              "flag should force one.", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
