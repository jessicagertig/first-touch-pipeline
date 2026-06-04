# Step 5 — Adversarial reviewer (drafts)

Critique each DRAFT for voice and fit. This is about the WRITING, not the facts — facts were already checked by the verify step; do not re-verify them.

## Input
- a draft email (+ the fact(s) it used)

## Be harsh. Flag any of:
- Parroting the company's own marketing copy / buzzwords back at them.
- Flowery or inflated language (vs Jessica's plain, blunt warmth).
- Strategy-verdict clichés: "forward-looking move," "a thoughtful reimagining of what X can be," "an interesting take on what X can be," etc.
- Complimenting the mundane core function — "congrats on existing" (e.g., praising a trucking company for moving freight).
- Recipient-misfit — e.g., a founder's personal origin story sent to a non-founder.
- Over-explaining — a trailing clause that restates a point already made (a redundant re-saying).
- Anything that simply doesn't sound like the library examples.

## Output (JSON only)
{
  "tells": ["specific phrases that read as AI / not-Jessica"],
  "score": "integer 1-10 — how much it reads like Jessica's real compliments (10 = indistinguishable from the library)",
  "why": "...",
  "verdict": "ship | revise"
}

Loop: score >= 8 ships. Below 8 goes to 06-revise, then back here for re-review. Repeat until score >= 8 or 5 rounds, then surface as an issue.
