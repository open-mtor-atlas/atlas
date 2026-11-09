# BRIEF 4: web verification round for author profiles (Oliver's mTOR Atlas, 2026-10-30)

The profiles in your `verify_cand_N.json` were rewritten earlier today from PubMed only, because the web search budget ran out. This round adds what only the web can confirm: the person's CURRENT position, official profile page, ORCID, and training (PhD, postdoc). BRIEF3.md in this folder has the full field and style rules; read its sections "Identity rule", "Fields to return" (location rules!) and "Writing rules". Read the current profile text before changing anything.

## Budget (hard)
The web search budget is shared by 8 parallel runs and is about 200 searches in total. You have AT MOST 24 WebSearch calls, which is one per person. Spend one search per person: "<full name>" plus the institution or field. WebFetch is allowed (up to 2 per person) to open and confirm a page found by the search. If WebSearch starts failing because the budget is used up, stop searching, write what you have and say so.
Tools: ToolSearch `select:mcp__remote-devices__device_bash` for files. No PubMed needed in this round.

## Per person
1. One search. Look for an official page: university or institute profile, lab page, company leadership page, ORCID record, obituary.
2. Accept only if the page names the same person and ties to the Atlas affiliation or field (see the identity rule; common names need two ties).
3. If confirmed, update the profile:
   - `lab_name`: current lab or unit and institution with the location parenthesis (follow the location rules exactly; reuse strings from `canonical_locations.json`).
   - `lab_url`: the confirmed official page. `orcid` only if seen on that page or the ORCID record.
   - `sub`: current position first, then earlier positions.
   - `role`: adjust if the person's main identity is now clearer.
   - `story`: edit the paragraph about career and current role with the confirmed facts (training, current title, own research theme). Remove sentences such as "current position could not be confirmed" when it now is. Keep the Atlas-study paragraph as it is unless it is wrong.
   - Do not touch `highlights`, `full` (unless the official page clearly shows the name), photo fields.
4. If nothing is confirmed, do not include the person in the output.

## Output
`patch4_N.json` in this folder: {"<key>": {full, lab_name, lab_url?, orcid?, role, sub, story, sources, note}} only for people you changed, with the complete new values of those fields (copy unchanged ones from the current profile programmatically). Write after every 4 people with python. Final reply: number changed, number with nothing found, whether the search budget ran out, and note items for Petr.
