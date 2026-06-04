"""Stage C (post) — post each shipping variation as its own Slack message.

Jessica reacts with the pick emoji (default ✅) on the one she wants; the
poll_picks Action then creates the Gmail draft. No buttons, no Lambda — the
per-message ts is recorded so a reaction maps back to a specific variation.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from scripts import utils

PICK_EMOJI = "✅"  # the emoji to react with to choose a variation


def _variations_path(lead_id: str) -> Path:
    return utils.REPO_ROOT / "output" / lead_id / "variations.json"


def post_variations(lead_id: str) -> None:
    """Post the shipping variations to the review channel and record each ts."""
    path = _variations_path(lead_id)
    data = json.loads(path.read_text(encoding="utf-8"))
    channel = utils.env("SLACK_REVIEW_CHANNEL_ID")
    if not channel:
        raise RuntimeError("SLACK_REVIEW_CHANNEL_ID not set")

    ships = [v for v in data["variations"] if v.get("ship")]
    if not ships:
        best = sorted(data["variations"], key=lambda v: v.get("score", 0), reverse=True)
        lines = "\n".join(f"• #{v['variant_n']} (score {v.get('score')})" for v in best)
        utils.slack_post(channel, text=(
            f"No drafts cleared the score bar for *{data['company_name']}* "
            f"({data['email']}).\n{lines}"))
        utils.update_lead(lead_id, status="no_ship")
        return

    utils.slack_post(channel, text=(
        f"*Drafts for {data['company_name']}* — {data['recipient_name']} ({data['email']})\n"
        f"React {PICK_EMOJI} on the one you want sent (it'll land in your Gmail drafts)."))

    for v in ships:
        src = (v.get("source_urls") or [None])[0]
        text = f"*#{v['variant_n']}*\n```{v['email']}```"
        if src:
            text += f"\nsource: {src}"
        resp = utils.slack_post(channel, text=text)
        v["slack_ts"] = resp.get("ts")
        v["slack_channel"] = channel

    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    utils.update_lead(lead_id, status="awaiting_pick")


def main() -> None:
    ap = argparse.ArgumentParser(description="Post draft variations for the human pick.")
    ap.add_argument("--lead", required=True)
    post_variations(ap.parse_args().lead)


if __name__ == "__main__":
    main()
