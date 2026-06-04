# Step 1 — Research

Gather raw material on the prospect's COMPANY and the INDIVIDUAL recipient. You only collect; you do not yet pick what to compliment.

## Inputs
- first_name, email, org_name (as typed at signup), email_domain

## Do
1. Find and read the company's real website (start from email_domain; verify it's actually them). Read homepage, about, product/services.
2. Understand what they actually do, in plain terms.
3. Research the INDIVIDUAL recipient too: who they are, their role at the company, anything findable. (Role matters: a founder's personal story is only usable if the recipient IS the founder.)
4. Web search is allowed for context/news. News is CONTEXT only, not a compliment basis. Do NOT collect "something they posted on LinkedIn" as a hook — overdone, unreliable.
5. First-party / company-published sources are primary and trusted. Note source URLs and any dates.

## Output (JSON only)
{
  "company": {"website": "...", "what_they_do": "...", "raw_notes": "everything potentially interesting, in plain words", "source_urls": ["..."]},
  "individual": {"name": "...", "role_if_found": "... or null", "notes": "...", "source_urls": ["..."]},
  "could_not_find": ["gaps / things to flag"]
}
Assert only what sources support.
