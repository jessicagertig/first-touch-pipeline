# First-Touch Pipeline

Turns a new Polymer signup into a reviewed, ready-to-send first-touch outreach email in Jessica's voice — automatically, up to the final human pick.

## Tech Stack
Python 3.12, AWS SAM (one thin Slack-interactivity Lambda), GitHub Actions (compute/orchestration), Anthropic Claude API, Slack API, Gmail API. Standalone — no dependency on inflow-ats internals; it only consumes the "New Company" Slack messages.

## Architecture (3 stages)
- **Stage A — Capture** (`.github/workflows/ingest_qualify.yml`, cron): read the New-Company Slack channel → parse leads → dedup → qualify gate → on pass, commit to `state/leads.csv` and post "good lead" to the review channel. Durable: the lead is saved + notified before any servicing, so nothing downstream can drop it.
- **Stage B — Service** (`.github/workflows/service_lead.yml`): for each `qualified` lead, run research → extract → verify-loop → draft (N variations) → review/score-loop, until variations ship (score ≥ 8) or caps hit. Retriable; a failure leaves the lead `qualified` for the next sweep.
- **Stage C — Select & Gmail draft** (`.github/workflows/create_draft.yml`): post variations to the review channel → human clicks one (Slack → SAM Lambda → `workflow_dispatch`) → create a Gmail draft in `jessica@polymer.co` via `users.drafts.create`.

## Email craft (authoritative)
The 6 step prompts live in `scripts/prompts/`. The reference corpus is `reference-files/first_touch_library.jsonl` (88 of Jessica's real first-touch emails, 10 fields). The full decision record is in the hub: `~/claude-hub/first-touch-pipeline/_in-progress/2026-06-03-first-touch-pipeline-design/approved-decisions.md`. Key rules: lead with the company name; one genuinely-distinctive verified detail; plain words, no parroting their copy, no verdict clichés, no reaction-framing, no fabricated bio; closer "Happy to answer any questions you might have about Polymer."; sign-off `Cheers,\nJessica`; signature `Jessica Gertig` / `Polymer | polymer.co` (two blank lines above so Gmail grays it).

## Qualify gate
Email-domain blocklist: free/consumer mailboxes (gmail, yahoo, hotmail, outlook, icloud, …) and common/shared domains (`.edu`) are automatic outs. Only company-specific domains pass.

## State
`state/leads.csv` is the durable, git-committed status store: `qualified → serviced → draft_created` (+ `skipped`, `error`). Dedup by email + Slack ts; re-clicks are no-ops once a draft exists.

## AWS
Stack `first-touch-slack`, profile `polymer`, region `us-east-1`. Deploy: `make deploy` (sources `.env`).

## Gotchas
- Secrets are passed at deploy via `make deploy` sourcing `.env`; never commit them.
- Gmail draft creation needs its own Google OAuth refresh token for `jessica@polymer.co` (scope `gmail.compose`) — separate from any Claude session connector.
- The compute tier is GitHub Actions; only the Slack webhook is on Lambda.
