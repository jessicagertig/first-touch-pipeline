# Step 3 — Verify (one candidate)

Determine whether ONE candidate fact is TRUE and CURRENT as of today. Run once per candidate. Orchestrator handles the loop.

## Input
- one candidate item (+ company context)

## Principles
- First-party / company-published information is the BEST and primary source. Do NOT discount a fact for being self-published — that's exactly what we compliment from.
- The test is CURRENCY, not provenance: is it still true now, and ideally still reflected on the current live site. A claim ~2 years old with no current confirmation (and not on the current site) is the red flag.
- You MUST attempt to read the LIVE company site. If it 403s/blocks, say so — "not on the current site" cannot be trusted when you couldn't load it.
- Find dated evidence.

## Output (JSON only)
{
  "candidate": "...",
  "verdict": "verified_current | true_but_stale | unverifiable | likely_false",
  "verified_fact": "the verbatim detail to pass to the drafter; null unless verified_current",
  "current_state": "what is actually true now, with dates",
  "evidence": [{"fact": "...", "source_url": "...", "date": "..."}],
  "recommended_action": "use as-is | rephrase to X | re-research for current state | drop",
  "confidence": "high|medium|low"
}

Pass `verified_fact` (verbatim, with its source) to the draft step.

## Loop (orchestration, not this single pass)
- If `true_but_stale` or `unverifiable`: do a TARGETED re-research of THIS item for its current state, then verify again.
- Iterate research→verify per item; max 5 loops/item, then surface the item as an issue.
- A stale candidate does not block the email if another candidate verifies; escalate/hold only when nothing usable verifies.
