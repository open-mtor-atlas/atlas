# BRIEF 2: second pass for author keys that failed the identity gate (Oliver's mTOR Atlas, 2026-10-30)

First read BRIEF.md in this folder (tools, profile fields, writing rules, patch format). This second pass uses the same output format (`patch2_N.json`) and the same writing rules. Only the identity gate changes.

Input: `candidates2_N.json`. Each key failed the first pass because PubMed gave no affiliation for the author in the Atlas study (older records list affiliations only for the first author), or gave only initials as the given name. `failed_reason` and `failed_note` say which.

## Recovery method (identity by co-author chain)
You may search PubMed for other papers by the same person and use them as evidence. Tools: `search_articles` and `get_article_metadata`.
1. Search `"<Surname> <Initials>"[Author]` combined with a distinctive term from the Atlas study title or with mTOR/rapamycin. Also try the corpus first and last author of the Atlas study with the key's surname.
2. For a candidate paper P, fetch its metadata. P counts as evidence only if (a) it lists the author with the same surname and initials, (b) it shares at least 2 other authors with the Atlas study's author list (at least 3 if the surname is very common: Wang, Zhang, Li, Chen, Kim, Liu, Yang, Lee, Wu, Zhou, Xu, Huang), and (c) it gives a full given name and an affiliation for that author.
3. Pass the key only if all full given names found (in P and in any Atlas study that has one) agree, and the affiliation from P is compatible with the lab of the Atlas study (same institution or an obvious neighbour such as hospital plus university). Then the verified studies are those Atlas studies where the author's position and the co-author overlap fit; list the others under `unverified_sids`.
4. For "initials only" keys the same chain gives the full given name. If two different given names fit the same initials, the key is unresolved ("Více lidí").
5. Budget: at most 8 PubMed calls per key. Stop at the first sufficient chain. If no chain is found, leave the key in `unresolved` with the reason and what you tried (one line).
6. In the profile text say where the information came from in plain words, for example "PubMed lists X at ... in a related paper from the same group", and keep the claims to what the chain shows. `lab_name` only when the affiliation is clear.
7. Do not use web search for this pass.

## Output
`patch2_N.json` with the same four lists as in BRIEF.md (`bios`, `airtable`, `unresolved`, `needs_photo`). `airtable` entries also carry `evidence_pmids` (the PMIDs of the chain papers). Write after every ~5 keys. Final reply: counts only, plus anything odd.
