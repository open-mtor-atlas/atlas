# BRIEF: author profiles (medailonky) for Oliver's mTOR Atlas, batch 2026-10-30

You get one file `candidates_N.json` (same folder as this brief). Each entry is a corpus author key ("Surname Initials", as in Studies.Authors) that is first or last author of a study, or appears in 2+ studies, and has NO profile yet. Studies per key are listed with sid, record_id, pmid, doi, title, finding, and the position of the key in the author list (first / last / middle).

Your job per key: (1) verify it is ONE identifiable person, (2) if yes write a profile, (3) if not, record why. Fail closed: a missing profile is fine, a wrong one is not.

## Tools
Load first with ToolSearch (one call): `select:mcp__PubMed__get_article_metadata,mcp__PubMed__search_articles,mcp__remote-devices__device_bash`.
- PubMed: `get_article_metadata` with up to 8 PMIDs per call (answers are large). It returns per author last_name, fore_name, initials, affiliations. This is the ONLY identity source you must use. Direct internet from the shell is blocked.
- Files: `mcp__remote-devices__device_bash` runs on the user's Windows machine in a Linux VM. Work folder: `$HOME/mnt/Oliver biology Cowork/_work_bios_2026-10-30/`. Use python3 for JSON. Each call is a fresh shell.
- WebSearch/WebFetch are allowed but optional. Use them only for people with 2+ verified studies or who are senior (last) author, max 2 searches per person, and only to confirm a position or lab. If a web fact is not clearly about the same person, leave it out.
- Do NOT write to `atlas_data/`, Airtable, or any file except your own `patch_N.json`. Do not commit anything.

## Identity gate (per key)
1. For every study of the key take the PubMed record (find the PMID via the candidate file; if there is no pmid, try `search_articles` with `"<doi>"[DOI]`; if still nothing, that study cannot be verified).
2. Find the author in the PubMed author list: by position when pos is first/last (first = index 0, last = final entry), otherwise by last_name + initials. Compare with the key: particles (de, van, von), diacritics, hyphens and case are ignored. If two PubMed authors in one study match a middle key, the study is ambiguous.
3. Pass only if the fore_name is a real given name (not just initials) and is the same person in all verified studies: same given name (a middle initial may be present in one record and absent in another) AND compatible affiliations (same institution, or an obvious move between related institutions). Very common names (Wang, Zhang, Li, Chen, Kim, Liu, Yang...) need the affiliation match to be clear.
4. Single-study key (first or last author): passes if PubMed gives a full given name and an affiliation.
5. If a key hides several people (different given names or unrelated affiliations): NO profile. Put it in `unresolved` with reason "Více lidí" and a split note: given name, affiliation, sids per person.
6. If only some of a key's studies verify, the profile covers only those (bio_studies). Studies you could not verify are listed under `unverified_sids` for that key.
7. A key whose PubMed names cannot be matched or has no PMID anywhere goes to `unresolved` with the reason.

## Profile fields (JSON, same schema as atlas_data/author_bios_baked.json)
See an example in `../_work_bios_2026-10-18/bios_patch_HK_2026-10-18.json` (key "new") and the style below. Fields:
- `full`: given name + family name exactly as PubMed gives them (proper diacritics). Drop a middle initial if PubMed gives it only as an initial in some studies.
- `lab_name`: "<Department or Institute>, <Institution> (<City>, <State if USA/Canada/Australia>, <Country>)". Remove street, postal code, e-mail. Add the "(City, State, Country)" tail only when you are certain from the institution name; if you are not, omit `lab_name` entirely. Write "<Surname> Lab" only if a source says the person leads a lab; otherwise use the department/institute.
- `role`: ONE sentence: what this person did in the Atlas studies (first author of..., senior author of..., co-author of...), taken from the candidate file. No career claims.
- `init`: two initials, upper case. `mono`: pick one of #3E6E3E #4B3E6E #6E3E4B #5A3E6E #6E5A3E #2F6F8F #3E7A5C #7A1626 #4E7C6E (vary them).
- `sub`: affiliation line, HTML entities as in existing profiles (`&middot;` as separator, `&amp;`, `&ndash;`). Only what PubMed or a cited web page shows.
- `story`: list of 1 to 2 short paragraphs, plain English a motivated high-school student can follow. 1 paragraph (2 to 4 sentences) for a person with one study, up to 2 paragraphs for 2+ studies. Say what the study or studies in the Atlas found, in your own words from the `finding` text, and what the person's part was (position in the author list, institution). Nothing else.
- `highlights`: object {sid: one sentence on the person's part in that study}. One entry per verified study.
- `orcid`: only if you actually saw it in a source about this person, otherwise omit the key.
- Do NOT include: `photo`, `thumb`, `credit`, `lab_url`, e-mail, phone, any URL in text, birth year, titles you cannot source (no "Professor" unless a source says so), guesses about current position.

## Writing rules (important)
- Only facts from PubMed metadata, the candidate file, or a clearly matching web page. Nothing from memory about a person.
- Plain, concrete sentences. No filler or hype ("renowned", "leading", "pioneering", "pivotal", "landscape", "delve", "crucial", "notably", "testament"). No rhetorical triplets, no "not only X but also Y". Vary sentence length. No em dashes and no `&mdash;`; use commas or full stops. Do not use invisible or special Unicode characters; plain ASCII punctuation plus normal accented letters in names.
- If the person's identity or role is only known from one affiliation line, say so briefly rather than padding ("PubMed lists her at ...").
- Keep science honest: say what kind of study it was (cells, mice, people, review) and keep the study's boundary from the `finding` text when it matters.

## Output: `patch_N.json` in the work folder (write it after every ~10 keys so nothing is lost; final version must be valid JSON)
{
 "bios": { "<corpus key exactly as in candidates>": { ...profile fields... } },
 "airtable": [ {"key": "...", "full": "...", "affiliation": "<first PubMed affiliation of the most recent verified study, trimmed>", "name_status": "Jeden člověk", "studies": [all sids of the key verified as this person], "bio_studies": [same sids]} ],
 "unresolved": [ {"key": "...", "reason": "...", "note": "split / details"} ],
 "needs_photo": [keys with 2+ verified studies]
}
Every key from your candidates file must end up in exactly one of: `bios` (and `airtable`), or `unresolved`.

## Final reply (short)
Counts only: profiles written, unresolved by reason, needs_photo count, and anything odd (for example PubMed disagreeing with the corpus author list). No profile text in the reply.
