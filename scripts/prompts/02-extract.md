# Step 2 — Extract proposed interesting things

From the research output, pull out the candidate facts/items worth complimenting. Verification (step 3) runs on these named candidates, so be specific.

## Input
- The research JSON from step 1.

## Do
- Surface only the genuinely COOL / clever / surprising / distinctive — a striking name, a quirk, a bold stance, or a genuinely novel capability (something that makes a person go "huh, that's neat"). NOT generic features every competitor has ("custom curriculum," "no lock-in," "a record of your work") and NOT the mundane core function — you can't react to a generic service, only restate it. If nothing clears the bar, say so rather than dressing up a plain feature.
- Uniqueness test — for anything you're about to highlight, stop and ask: does every company of this kind do this, or is it unique to THEM? Skip the generic ("you can talk to the AI 24/7" — every AI does that; every trucking line hauls freight). Keep only what's specific to them ("the AI sets your curriculum"). It's the specific thing that made it different that matters.
- Capture each `item` as a verbatim quote from its source (site/blog/etc.).
- Mark each candidate `level`: `company` (safe to send any employee) or `individual` (only usable if the recipient is that specific person). Default to `company` when the recipient's role is unknown.
- Flag any `sensitivity` (politically charged, polarizing, private).

## Output (JSON only)
{
  "candidates": [
    {"item": "...", "why_interesting": "...", "level": "company|individual",
     "source_url": "...", "as_of_date_if_known": "...", "recency_note": "...",
     "sensitivity": "none | describe"}
  ]
}
