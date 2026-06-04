# First-Touch Pipeline

Turns a new Polymer signup into a reviewed, ready-to-send first-touch outreach email in Jessica's voice — automatically, up to the final human pick.

## Tech Stack
Python 3.12, GitHub Actions (all compute/orchestration), Anthropic Claude API, Slack API, Gmail API. No AWS/Lambda. Standalone — no dependency on inflow-ats internals; it only consumes the "New Company" Slack messages.

## Architecture (3 stages, all GitHub Actions)
- **Stage A — Capture** (`.github/workflows/ingest_qualify.yml`, cron): read the new-leads Slack channel → parse leads → dedup → qualify gate → on pass, commit to `state/leads.csv` and post "good lead" to the good-leads channel. Durable: the lead is saved + notified before any servicing, so nothing downstream can drop it.
- **Stage B — Service** (`.github/workflows/service_lead.yml`): for each `qualified` lead, run research → extract → verify-loop → draft (N variations) → review/score-loop until variations ship (score ≥ 8) or caps hit, then post each shipping variation as its own message to the review channel (status → `awaiting_pick`). Retriable; a failure leaves the lead recoverable.
- **Stage C — Pick** (`.github/workflows/poll_picks.yml`, cron): read reactions on the posted variation messages; the one Jessica reacts to with ✅ gets turned into a **Gmail draft** in `jessica@polymer.co` via `users.drafts.create`. No Lambda, no buttons — reactions only.

## Email craft (authoritative)
The 6 step prompts live in `scripts/prompts/`. The reference corpus is `reference-files/first_touch_library.jsonl` (88 of Jessica's real first-touch emails, 10 fields). The full decision record is in the hub: `~/claude-hub/first-touch-pipeline/_in-progress/2026-06-03-first-touch-pipeline-design/approved-decisions.md`. Key rules: lead with the company name; one genuinely-distinctive verified detail; plain words, no parroting their copy, no verdict clichés, no reaction-framing, no fabricated bio; closer "Happy to answer any questions you might have about Polymer."; sign-off `Cheers,\nJessica`; signature `Jessica Gertig` / `Polymer | polymer.co` (two blank lines above so Gmail grays it).

## Qualify gate
Email-domain blocklist: free/consumer mailboxes (gmail, yahoo, hotmail, outlook, icloud, …) and common/shared domains (`.edu`) are automatic outs. Only company-specific domains pass.

## State
`state/leads.csv` is the durable, git-committed status store: `qualified → serviced → awaiting_pick → draft_created` (+ `skipped`, `no_ship`, `error`). Dedup by email + Slack ts.

## Slack
One bot (`content_creation_bot`, shared with thought-leadership). Required scopes: `channels:history`, `groups:history`, `chat:write`, `reactions:read`. The bot must be a member of all three channels:
- `SLACK_LEADS_CHANNEL_ID` — app-prod-new-companies (source: Polymer's "New Company" posts; bot reads)
- `SLACK_GOOD_LEADS_CHANNEL_ID` — new-leads-from-signups (pipeline posts each qualified good lead)
- `SLACK_REVIEW_CHANNEL_ID` — email-review (pipeline posts draft variations; bot reads ✅ reactions)
Pick emoji: ✅ (`white_check_mark`).

## Gotchas
- Secrets live in `.env` locally and as GitHub Actions secrets in CI; never commit them.
- Gmail draft creation uses its own Google OAuth refresh token for `jessica@polymer.co` (scope `gmail.compose`).
- All compute is GitHub Actions; there is no server/Lambda to deploy.
