"""Stage C (pick) — read reactions and create the Gmail draft for the chosen one.

Cron Action. For each lead awaiting a pick, check the posted variation messages
for the pick emoji (✅ = "white_check_mark"); the first one reacted wins, and we
hand it to gmail_draft to create the draft.
"""
from __future__ import annotations

import json
from pathlib import Path

from scripts import utils

PICK_EMOJI_NAME = "white_check_mark"  # the Slack name for ✅


def _variations_path(lead_id: str) -> Path:
    return utils.REPO_ROOT / "output" / lead_id / "variations.json"


def poll_once() -> None:
    import scripts.gmail_draft as gmail_draft  # lazy: only needed when a pick lands
    for lead in utils.leads_by_status("awaiting_pick"):
        lead_id = lead["lead_id"]
        try:
            data = json.loads(_variations_path(lead_id).read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            continue
        picked = None
        for v in data["variations"]:
            ts, ch = v.get("slack_ts"), v.get("slack_channel")
            if not ts or not ch:
                continue
            if PICK_EMOJI_NAME in utils.slack_reactions(ch, ts):
                picked = v
                break
        if not picked:
            continue
        try:
            gmail_draft.create_draft(lead_id, int(picked["variant_n"]))
        except Exception as exc:  # noqa: BLE001
            utils.update_lead(lead_id, status="error", notes=f"draft create failed: {exc}")
            utils.post_error_to_slack(f"draft create failed for {lead_id}: {exc}")


def main() -> None:
    poll_once()


if __name__ == "__main__":
    main()
