"""Shared helpers: env, Claude client, Slack I/O, leads store, web fetch.

Standalone — no inflow-ats dependency. Patterns adapted from
thought-leadership-automation/scripts/utils.py (call_anthropic retry wrapper,
Slack post helper) but rewritten for this pipeline.
"""
from __future__ import annotations

import csv
import json
import os
import time
from pathlib import Path
from typing import Any, Iterable

import requests

try:
    from dotenv import load_dotenv
    _env = Path(__file__).resolve().parent.parent / ".env"
    if _env.exists():
        load_dotenv(_env, override=True)
except Exception:
    pass

REPO_ROOT = Path(__file__).resolve().parent.parent
PROMPTS_DIR = REPO_ROOT / "scripts" / "prompts"
LIBRARY_PATH = REPO_ROOT / "reference-files" / "first_touch_library.jsonl"
LEADS_PATH = REPO_ROOT / "state" / "leads.csv"

LEADS_FIELDS = [
    "lead_id", "slack_ts", "company_name", "recipient_name", "email",
    "email_domain", "careers_slug", "status", "skip_reason",
    "qualified_at", "serviced_at", "gmail_draft_id", "notes",
]

RESEARCH_MODEL = os.environ.get("RESEARCH_MODEL", "claude-sonnet-4-6")
DRAFT_MODEL = os.environ.get("DRAFT_MODEL", "claude-opus-4-8")


def env(key: str, default: str | None = None) -> str | None:
    return os.environ.get(key, default)


# --------------------------------------------------------------------------- #
# Claude
# --------------------------------------------------------------------------- #
def _anthropic_client():
    import anthropic
    return anthropic.Anthropic()  # reads ANTHROPIC_API_KEY


def call_anthropic(
    *,
    model: str,
    messages: list[dict],
    system: str | None = None,
    max_tokens: int = 4096,
    tools: list[dict] | None = None,
    max_retries: int = 5,
    initial_delay: float = 60.0,
    label: str = "",
) -> Any:
    """Call the Messages API with retry/backoff on overload (429/529).

    Streams when max_tokens is large to avoid the non-streaming ceiling.
    Returns the raw response object; use extract_text() for the text.
    """
    client = _anthropic_client()
    kwargs: dict[str, Any] = {"model": model, "max_tokens": max_tokens, "messages": messages}
    if system:
        kwargs["system"] = system
    if tools:
        kwargs["tools"] = tools

    delay = initial_delay
    last_exc: Exception | None = None
    for attempt in range(1, max_retries + 1):
        try:
            if max_tokens > 16384:
                text_parts: list[str] = []
                with client.messages.stream(**kwargs) as stream:
                    for chunk in stream.text_stream:
                        text_parts.append(chunk)
                    final = stream.get_final_message()
                return final
            return client.messages.create(**kwargs)
        except Exception as exc:  # noqa: BLE001
            last_exc = exc
            status = getattr(exc, "status_code", None)
            retryable = status in (429, 529) or "overloaded" in str(exc).lower()
            if attempt == max_retries or not retryable:
                raise
            print(f"[call_anthropic{(' ' + label) if label else ''}] attempt {attempt} "
                  f"failed ({status}); retrying in {delay:.0f}s")
            time.sleep(delay)
            delay *= 2
    raise last_exc  # pragma: no cover


def extract_text(response: Any) -> str:
    parts = []
    for block in getattr(response, "content", []) or []:
        if getattr(block, "type", None) == "text":
            parts.append(block.text)
    return "".join(parts).strip()


def parse_json(text: str) -> Any:
    """Best-effort JSON parse: strip code fences, find the first {...} or [...]."""
    t = text.strip()
    if t.startswith("```"):
        t = t.split("```", 2)[1]
        if t.startswith("json"):
            t = t[4:]
        t = t.strip()
    try:
        return json.loads(t)
    except Exception:
        for opener, closer in (("[", "]"), ("{", "}")):
            i, j = t.find(opener), t.rfind(closer)
            if i != -1 and j != -1 and j > i:
                try:
                    return json.loads(t[i:j + 1])
                except Exception:
                    continue
        raise


WEB_SEARCH_TOOL = {"type": "web_search_20250305", "name": "web_search"}


# --------------------------------------------------------------------------- #
# Prompts & library
# --------------------------------------------------------------------------- #
def load_prompt(name: str) -> str:
    p = PROMPTS_DIR / (name if name.endswith(".md") else f"{name}.md")
    return p.read_text(encoding="utf-8")


def load_library() -> list[dict]:
    rows = []
    with LIBRARY_PATH.open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def library_jsonl_text() -> str:
    """Raw JSONL string of the 88 examples, for embedding in a draft prompt."""
    return LIBRARY_PATH.read_text(encoding="utf-8")


# --------------------------------------------------------------------------- #
# Leads store (git-committed CSV)
# --------------------------------------------------------------------------- #
def read_leads() -> list[dict]:
    if not LEADS_PATH.exists():
        return []
    with LEADS_PATH.open(encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


def _write_leads(rows: list[dict]) -> None:
    LEADS_PATH.parent.mkdir(parents=True, exist_ok=True)
    with LEADS_PATH.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=LEADS_FIELDS)
        writer.writeheader()
        for row in rows:
            writer.writerow({k: row.get(k, "") for k in LEADS_FIELDS})


def find_lead(lead_id: str) -> dict | None:
    for row in read_leads():
        if row.get("lead_id") == lead_id:
            return row
    return None


def lead_exists(*, email: str = "", slack_ts: str = "") -> bool:
    for row in read_leads():
        if email and row.get("email") == email:
            return True
        if slack_ts and row.get("slack_ts") == slack_ts:
            return True
    return False


def upsert_lead(row: dict) -> None:
    rows = read_leads()
    for i, existing in enumerate(rows):
        if existing.get("lead_id") == row.get("lead_id"):
            rows[i] = {**existing, **row}
            _write_leads(rows)
            return
    rows.append(row)
    _write_leads(rows)


def update_lead(lead_id: str, **fields: Any) -> None:
    rows = read_leads()
    for row in rows:
        if row.get("lead_id") == lead_id:
            row.update({k: ("" if v is None else str(v)) for k, v in fields.items()})
            _write_leads(rows)
            return
    raise KeyError(lead_id)


def leads_by_status(status: str) -> list[dict]:
    return [r for r in read_leads() if r.get("status") == status]


# --------------------------------------------------------------------------- #
# Slack
# --------------------------------------------------------------------------- #
SLACK_API = "https://slack.com/api"


def _slack_token() -> str:
    tok = os.environ.get("SLACK_BOT_TOKEN")
    if not tok:
        raise RuntimeError("SLACK_BOT_TOKEN not set")
    return tok


def slack_post(channel: str, *, text: str | None = None,
               blocks: list[dict] | None = None, thread_ts: str | None = None) -> dict:
    payload: dict[str, Any] = {"channel": channel}
    if text is not None:
        payload["text"] = text
    if blocks is not None:
        payload["blocks"] = blocks
    if thread_ts:
        payload["thread_ts"] = thread_ts
    resp = requests.post(
        f"{SLACK_API}/chat.postMessage",
        headers={"Authorization": f"Bearer {_slack_token()}",
                 "Content-Type": "application/json; charset=utf-8"},
        data=json.dumps(payload), timeout=30,
    )
    data = resp.json()
    if not data.get("ok"):
        print(f"[slack_post] error: {data.get('error')}")
    return data


def slack_history(channel: str, *, oldest: str | None = None, limit: int = 200) -> list[dict]:
    """Read messages from a channel (newest-first), paginated. Backs off on 429."""
    messages: list[dict] = []
    cursor: str | None = None
    while True:
        params: dict[str, Any] = {"channel": channel, "limit": limit}
        if oldest:
            params["oldest"] = oldest
        if cursor:
            params["cursor"] = cursor
        while True:
            resp = requests.get(
                f"{SLACK_API}/conversations.history",
                headers={"Authorization": f"Bearer {_slack_token()}"},
                params=params, timeout=30,
            )
            if resp.status_code == 429:
                time.sleep(int(resp.headers.get("Retry-After", "2")))
                continue
            break
        data = resp.json()
        if not data.get("ok"):
            print(f"[slack_history] error: {data.get('error')}")
            break
        messages.extend(data.get("messages", []))
        cursor = data.get("response_metadata", {}).get("next_cursor")
        if not cursor:
            break
    return messages


def slack_reactions(channel: str, timestamp: str) -> list[str]:
    """Return the reaction emoji names present on a message (e.g. ['white_check_mark'])."""
    resp = requests.get(
        f"{SLACK_API}/reactions.get",
        headers={"Authorization": f"Bearer {_slack_token()}"},
        params={"channel": channel, "timestamp": timestamp, "full": "true"}, timeout=30,
    )
    data = resp.json()
    if not data.get("ok"):
        return []
    msg = data.get("message", {}) or {}
    return [r.get("name") for r in (msg.get("reactions") or [])]


def post_error_to_slack(message: str, *, channel: str | None = None) -> None:
    ch = channel or os.environ.get("SLACK_REVIEW_CHANNEL_ID")
    if ch:
        try:
            slack_post(ch, text=f":warning: first-touch pipeline error: {message}")
        except Exception:  # noqa: BLE001
            pass


# --------------------------------------------------------------------------- #
# Web fetch
# --------------------------------------------------------------------------- #
def fetch_url(url: str, *, timeout: int = 20, retries: int = 3) -> str:
    """Fetch a URL and return main-content text (trafilatura), with backoff."""
    delay = 2.0
    last = ""
    for attempt in range(1, retries + 1):
        try:
            resp = requests.get(
                url, timeout=timeout,
                headers={"User-Agent": "Mozilla/5.0 (compatible; PolymerFirstTouch/1.0)"},
            )
            if resp.status_code == 200:
                try:
                    import trafilatura
                    extracted = trafilatura.extract(resp.text) or ""
                    return extracted or resp.text
                except Exception:
                    return resp.text
            last = f"HTTP {resp.status_code}"
        except Exception as exc:  # noqa: BLE001
            last = str(exc)
        time.sleep(delay)
        delay *= 2
    return f"[fetch failed: {last}]"
