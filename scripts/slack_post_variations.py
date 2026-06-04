"""Stage C — post draft variations to Slack for the human pick.

Reads output/<lead_id>/variations.json, builds a Slack Block Kit message
listing every shippable variation with a "Use this one" button, and posts it to
the review channel (SLACK_REVIEW_CHANNEL_ID). If nothing cleared the score bar,
posts a note with the best scores instead.
"""
from __future__ import annotations

import argparse
import json

from scripts.slack_leads_reader import slugify  # noqa: F401  (shared helper)
from scripts.utils import REPO_ROOT, env, post_error_to_slack, slack_post


def _load_variations(lead_id: str) -> dict:
    path = REPO_ROOT / "output" / lead_id / "variations.json"
    return json.loads(path.read_text(encoding="utf-8"))


def _header_block(data: dict) -> dict:
    text = (
        f"*Drafts for {data.get('company_name', '')} — "
        f"{data.get('recipient_name', '')} ({data.get('email', '')})*"
    )
    return {"type": "section", "text": {"type": "mrkdwn", "text": text}}


def _variation_blocks(lead_id: str, variation: dict) -> list[dict]:
    variant_n = variation.get("variant_n")
    source_urls = variation.get("source_urls") or []
    source_line = f"\n\n_Source:_ {source_urls[0]}" if source_urls else ""
    body = f"*#{variant_n}*\n{variation.get('email', '')}{source_line}"
    return [
        {"type": "section", "text": {"type": "mrkdwn", "text": body}},
        {
            "type": "actions",
            "elements": [
                {
                    "type": "button",
                    "text": {
                        "type": "plain_text",
                        "text": f"Use this one (#{variant_n})",
                    },
                    "action_id": f"ft_pick_{lead_id}_{variant_n}",
                    "value": f"{lead_id}|{variant_n}",
                }
            ],
        },
    ]


def _no_ship_block(variations: list[dict]) -> dict:
    ranked = sorted(
        variations, key=lambda v: v.get("score") or 0, reverse=True
    )
    scores = ", ".join(
        f"#{v.get('variant_n')}: {v.get('score')}" for v in ranked
    )
    text = (
        ":no_entry: Nothing cleared the score bar.\n"
        f"*Best scores:* {scores}"
    )
    return {"type": "section", "text": {"type": "mrkdwn", "text": text}}


def post_variations(lead_id: str) -> None:
    """Build and post the Block Kit pick message for one lead."""
    channel = env("SLACK_REVIEW_CHANNEL_ID")
    if not channel:
        post_error_to_slack("SLACK_REVIEW_CHANNEL_ID not set; cannot post variations")
        raise SystemExit("SLACK_REVIEW_CHANNEL_ID not set")

    data = _load_variations(lead_id)
    variations = data.get("variations") or []
    shippable = [v for v in variations if v.get("ship") is True]

    blocks: list[dict] = [_header_block(data)]
    if shippable:
        for variation in shippable:
            blocks.append({"type": "divider"})
            blocks.extend(_variation_blocks(lead_id, variation))
        fallback = f"Drafts for {data.get('company_name', '')}"
    else:
        blocks.append(_no_ship_block(variations))
        fallback = f"No drafts cleared the bar for {data.get('company_name', '')}"

    slack_post(channel, text=fallback, blocks=blocks)


def main() -> None:
    """CLI entry point: post variations for one lead by --lead."""
    parser = argparse.ArgumentParser(description="Stage C: post draft variations to Slack.")
    parser.add_argument("--lead", required=True, help="lead_id to post variations for.")
    args = parser.parse_args()
    post_variations(args.lead)


if __name__ == "__main__":
    main()
