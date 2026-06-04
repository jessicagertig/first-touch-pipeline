# first-touch-pipeline

Automated first-touch outreach for new Polymer signups. A signup posted in the new-leads Slack channel is qualified, researched, and turned into reviewed email variations in Jessica's voice; Jessica reacts ✅ to the one she wants and the pipeline drops a ready-to-send draft into her Gmail.

## Flow
```
new-leads-from-signups Slack msg
  → [A] ingest + qualify (drop gmail/.edu/free + common domains)
       → commit lead + post "good lead" to email-review channel        (durable)
  → [B] research → extract → verify-loop → draft ×N → review/score-loop
       → post each shipping variation as its own message
  → [C] Jessica reacts ✅ → poll reads the reaction → Gmail draft created
```
All three stages run as GitHub Actions on a cron. No server/Lambda.

## Layout
- `scripts/` — pipeline logic (qualify, Stage-B step modules, Slack reader/poster, reaction poller, Gmail client, `service_lead.py` orchestrator).
- `scripts/prompts/` — the 6 step prompts (research, extract, verify, draft, review, revise).
- `reference-files/first_touch_library.jsonl` — 88 real first-touch emails (voice corpus).
- `.github/workflows/` — `ingest_qualify.yml` (Stage A), `service_lead.yml` (Stage B), `poll_picks.yml` (Stage C).
- `state/leads.csv` — durable lead status store.

## Setup
1. `make install`
2. `cp .env.example .env` and fill it in (Anthropic, Slack bot token, Slack channel ids, Gmail OAuth — see `gmail-setup.txt`).
3. Add the same values as **GitHub Actions secrets** on this repo (the workflows read `secrets.*`).
4. Slack: the bot needs scopes `channels:history`, `chat:write`, `reactions:read`, and must be invited to both channels.

## Local
- `make ingest` — run Stage A once.
- `make service LEAD=<id>` — run Stage B for one lead.
- `make post LEAD=<id>` — post that lead's variations for the pick.
- `make poll` — read reactions and create Gmail drafts for picks.
- `make draft LEAD=<id> VARIANT=<n>` — create the Gmail draft directly.

See `CLAUDE.md` for architecture and the email-craft rules; the full decision record lives in the hub design dir.
