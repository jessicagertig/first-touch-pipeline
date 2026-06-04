# first-touch-pipeline

Automated first-touch outreach for new Polymer signups. A signup posted in the "New Company" Slack channel is qualified, researched, and turned into reviewed email variations in Jessica's voice; Jessica picks one in Slack and the pipeline drops a ready-to-send draft into her Gmail.

## Flow
```
New-Company Slack msg
  → [A] ingest + qualify (drop gmail/.edu/free + common domains)
       → commit lead + post "good lead" to review channel        (durable)
  → [B] research → extract → verify-loop → draft ×N → review/score-loop
       → post shipping variations to review channel
  → [C] Jessica clicks one → Gmail draft created in jessica@polymer.co
```

## Layout
- `scripts/` — pipeline logic (qualify, the Stage-B step modules, Slack + Gmail clients, `service_lead.py` orchestrator).
- `scripts/prompts/` — the 6 step prompts (research, extract, verify, draft, review, revise).
- `reference-files/first_touch_library.jsonl` — 88 real first-touch emails (voice corpus).
- `lambdas/slack_handler/` — the SAM Slack-interactivity Lambda (button → `workflow_dispatch`).
- `.github/workflows/` — the compute tier (ingest cron, per-lead service, create-draft).
- `state/leads.csv` — durable lead status store.

## Setup
1. `make install`
2. `cp .env.example .env` and fill it in (Anthropic, Slack, GitHub PAT, Gmail OAuth).
3. `make deploy` to ship the Slack Lambda; set the interactivity Request URL in the Slack app to the `SlackInteractUrl` output.
4. Add the same secrets to the GitHub repo (Actions secrets).

## Local
- `make ingest` — run Stage A once.
- `make service LEAD=<id>` — run Stage B for one lead.
- `make draft LEAD=<id> VARIANT=<n>` — create the Gmail draft for a chosen variation.

See `CLAUDE.md` for architecture and the email-craft rules; the full decision record lives in the hub design dir.
