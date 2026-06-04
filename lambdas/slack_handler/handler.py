"""
Slack Handler Lambda — First-Touch Pipeline

Handles Slack interactivity (button clicks) for picking a draft variation.

Route (via API Gateway):
  POST /slack/interact   - Slack button clicks -> trigger create_draft.yml

Env vars:
  SLACK_BOT_TOKEN        - Bot token (carried for parity; not required for dispatch)
  SLACK_SIGNING_SECRET   - For verifying Slack requests (HMAC-SHA256)
  GITHUB_TOKEN           - PAT with actions:write for workflow_dispatch
  GITHUB_OWNER           - GitHub repo owner
  GITHUB_REPO            - GitHub repo name (default: first-touch-pipeline)
"""

import base64
import hashlib
import hmac
import json
import logging
import os
import time
import urllib.error
import urllib.parse
import urllib.request

logger = logging.getLogger()
logger.setLevel(logging.INFO)

GITHUB_OWNER = os.environ.get("GITHUB_OWNER", "jessicagertig")
GITHUB_REPO = os.environ.get("GITHUB_REPO", "first-touch-pipeline")


def lambda_handler(event, context):
    path = event.get("path", "")
    method = event.get("httpMethod", "")

    if method == "POST" and path == "/slack/interact":
        return handle_slack_interact(event)

    return {"statusCode": 404, "body": json.dumps({"error": "Not found"})}


# ---------------------------------------------------------------------------
# Body decoding (API Gateway may base64-encode the body)
# ---------------------------------------------------------------------------

def _raw_body(event):
    body = event.get("body", "") or ""
    if event.get("isBase64Encoded"):
        body = base64.b64decode(body).decode("utf-8")
    return body


# ---------------------------------------------------------------------------
# Slack signature verification
# ---------------------------------------------------------------------------

def verify_slack_signature(event, raw_body):
    """Verify the request came from Slack using HMAC-SHA256."""
    signing_secret = os.environ.get("SLACK_SIGNING_SECRET", "")
    if not signing_secret:
        logger.error("SLACK_SIGNING_SECRET not set")
        return False

    headers = event.get("headers", {}) or {}
    timestamp = headers.get("X-Slack-Request-Timestamp") or headers.get("x-slack-request-timestamp", "")
    signature = headers.get("X-Slack-Signature") or headers.get("x-slack-signature", "")

    if not timestamp or not signature:
        return False

    # Reject requests older than 5 minutes
    try:
        if abs(time.time() - int(timestamp)) > 300:
            return False
    except (TypeError, ValueError):
        return False

    sig_basestring = f"v0:{timestamp}:{raw_body}"
    computed = "v0=" + hmac.new(
        signing_secret.encode(),
        sig_basestring.encode(),
        hashlib.sha256,
    ).hexdigest()

    return hmac.compare_digest(computed, signature)


# ---------------------------------------------------------------------------
# POST /slack/interact
# ---------------------------------------------------------------------------

def handle_slack_interact(event):
    raw_body = _raw_body(event)

    if not verify_slack_signature(event, raw_body):
        return {"statusCode": 401, "body": json.dumps({"error": "Invalid signature"})}

    params = urllib.parse.parse_qs(raw_body)
    payload = json.loads(params.get("payload", ["{}"])[0])

    action = (payload.get("actions") or [{}])[0]
    if not action:
        return {"statusCode": 400, "body": json.dumps({"error": "No action found"})}

    action_id = action.get("action_id", "")
    value = action.get("value", "")

    if action_id.startswith("ft_pick_"):
        return handle_pick(value)

    return {
        "statusCode": 200,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps({
            "response_type": "ephemeral",
            "text": f"Unknown action: {action_id}. Nothing dispatched.",
        }),
    }


def handle_pick(value):
    """value is 'lead_id|variant_n' -> dispatch create_draft.yml."""
    parts = value.split("|", 1)
    if len(parts) != 2 or not parts[0] or not parts[1]:
        return {
            "statusCode": 200,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps({
                "response_type": "ephemeral",
                "text": f"Bad pick value: {value!r}. Expected 'lead_id|variant_n'.",
            }),
        }

    lead_id, variant_n = parts[0], parts[1]
    ok, detail = trigger_github_action(
        "create_draft.yml",
        {"lead_id": lead_id, "variant_n": variant_n},
    )
    if not ok:
        return {
            "statusCode": 200,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps({
                "response_type": "ephemeral",
                "text": (
                    "Failed to trigger create_draft.yml. Something went wrong — check CloudWatch logs.\n"
                    f"```{detail}```"
                ),
            }),
        }

    return {
        "statusCode": 200,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps({
            "response_type": "ephemeral",
            "text": "On it — creating your Gmail draft…",
        }),
    }


# ---------------------------------------------------------------------------
# GitHub workflow_dispatch
# ---------------------------------------------------------------------------

def trigger_github_action(workflow_file, inputs):
    """Trigger workflow_file via GitHub API workflow_dispatch.

    Returns (ok: bool, detail: str). On failure, detail is a best-effort
    capture of HTTP status + GitHub response body + payload sent.
    """
    token = os.environ.get("GITHUB_TOKEN", "")
    if not token:
        logger.error("GITHUB_TOKEN not set")
        return False, "GITHUB_TOKEN env var not set on the Lambda."

    url = (
        f"https://api.github.com/repos/{GITHUB_OWNER}/{GITHUB_REPO}"
        f"/actions/workflows/{workflow_file}/dispatches"
    )
    payload = {"ref": "main", "inputs": inputs}
    data = json.dumps(payload).encode()

    req = urllib.request.Request(url, data=data, method="POST")
    req.add_header("Authorization", f"Bearer {token}")
    req.add_header("Accept", "application/vnd.github+json")
    req.add_header("User-Agent", "first-touch-slack-lambda")
    req.add_header("Content-Type", "application/json")

    try:
        resp = urllib.request.urlopen(req)
        logger.info(f"GitHub dispatch triggered ({workflow_file}): {resp.status}")
        return True, ""
    except urllib.error.HTTPError as e:
        try:
            body_text = e.read().decode("utf-8", errors="replace")
        except Exception:
            body_text = "<unreadable response body>"
        detail = f"HTTP {e.code} from GitHub. Response: {body_text}. Payload sent: {json.dumps(payload)}"
        logger.error(detail)
        return False, detail
    except Exception as e:
        detail = f"{type(e).__name__}: {e}. URL: {url}. Payload: {json.dumps(payload)}"
        logger.error(detail)
        return False, detail
