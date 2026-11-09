# BRIEF 3: research and rewrite author profiles properly (Oliver's mTOR Atlas, 2026-10-30)

The profiles in your `research_cand_N.json` were written today from PubMed metadata only. Many say little more than "first author of X, PubMed lists the affiliation as ...". Petr wants real profiles: who the scientist is, where they trained, where they work now, what their own research is about, and why their Atlas paper matters. Your job: research each person and rewrite the profile text.

## Inputs
`research_cand_N.json`: per key the current profile (`current`), the PubMed affiliation, and the Atlas studies with title, year, journal, PMID, DOI, author position and the curated `finding`.
`canonical_locations.json`: location strings already used on the site. Reuse them exactly when the city is the same.
Style examples (read 3 of them before writing): in `../atlas_data/author_bios_baked.json` the keys "Salmon AB", "Korolchuk VI", "Latek RR", "Wang Rong". Read with python via device_bash.

## Tools
ToolSearch first, one call: `select:mcp__remote-devices__device_bash,mcp__PubMed__search_articles,mcp__PubMed__get_article_metadata`. Use WebSearch and WebFetch for the web. Budget per person: up to 4 web searches, 3 page fetches, 2 PubMed calls. Do not download or save any image.

## What to find (in this order of value)
1. Current position and institution (official university, institute, lab or company page; ORCID record; obituary if deceased).
2. Training: PhD (where, with whom, year) and postdoc labs, from an official bio, CV, thesis record or lab alumni page.
3. Own lab or main research theme, if they have one. For people who left research (industry, clinic), say what they do now if an official source shows it.
4. Other work: use PubMed `search_articles` with `"Surname Initials"[Author]` plus a topic or institution term to see the person's main line of papers. Only count papers whose affiliation or co-authors tie them to this person.
5. Why the Atlas paper matters, explained for a motivated high-school reader, from the `finding` text and title. Keep the study's boundary (cells, flies, mice, people).

## Identity rule (strict)
A web or PubMed fact goes in only if the source clearly is the same person: same name AND (same institution at the right time, or same field plus a named collaborator or paper from the Atlas record). Very common names (Wang, Zhang, Li, Chen, Kim, Liu, Yang, Lee, Wu, Zhou, Xu, Huang, Smith, Johnson) need two independent ties. If unsure, leave it out. If you find nothing beyond PubMed, still improve the text: explain the study properly and use the PubMed publication record (with years and institutions) to describe the career path; say plainly when a current position could not be confirmed.
Never guess gender; avoid pronouns unless a source uses them for the person.
If a source shows the person has died, say so with the date and source in `note`, and mention it respectfully in the story.
If a paper of theirs in the Atlas was retracted or carries an expression of concern, do NOT write about it in the profile; put it in `note` for the curator.

## Fields to return (replace the current text fields; never output photo, thumb or credit)
- `full`: full name as the person uses it (keep diacritics). Change only with a source.
- `lab_name`: current lab or unit and institution, ending with the location in parentheses. Location rules (a build gate checks them, a mistake blocks the deploy):
  - USA, Canada, United Kingdom, Australia: exactly three parts "(City, State/Province/Nation, Country)", for example "(Boston, Massachusetts, USA)", "(Cambridge, England, United Kingdom)", "(Dundee, Scotland, United Kingdom)", "(Toronto, Ontario, Canada)".
  - Country names in full: USA, United Kingdom, South Korea, Netherlands, China, Czech Republic, Germany ... never UK, US, Korea, The Netherlands.
  - Other countries: "(City, Region, Country)" where a region is customary, else "(City, Country)"; city states "(Singapore)".
  - If the city already appears in `canonical_locations.json`, copy that string exactly.
  - If the current position is unknown, use the most recent confirmed affiliation and say "(at the time of the study)" in `sub`, NOT inside lab_name. lab_name must end with the location parenthesis.
- `lab_url`: official lab or profile page you actually opened and confirmed. Omit if none.
- `orcid`: only if seen on the ORCID record or an official page for this person (format 0000-0000-0000-0000).
- `role`: one sentence, who this person is and what they are known for, ending without a full stop like the style examples. Not "First author of X".
- `sub`: short line of positions separated by " &middot; " (current first, then earlier ones with years when known), HTML entities as in existing profiles (&amp;, &ndash;).
- `story`: 2 to 4 paragraphs. First the Atlas paper(s) and why they matter, then the person's path and own work, then current role. Each claim must come from a source you saw.
- `highlights`: {sid: one sentence on the person's part in that study}. Keep the same sids as now.
- `sources`: list of URLs and PMIDs you used (not shown on the site).
- `note`: anything for the curator (uncertain points, deaths, retractions, name changes). Empty string if nothing.

## Writing rules
Plain English for a motivated high-school student, accurate for a scientist. Concrete sentences, varied length. No hype or filler ("renowned", "leading", "pioneering", "pivotal", "landscape", "delve", "crucial", "notably", "testament", "groundbreaking", "cutting-edge"). No rhetorical triplets, no "not only X but also Y". No em dashes, no `&mdash;`; use commas or full stops. No invisible or special Unicode, plain ASCII punctuation. No e-mail addresses, no phone numbers, no URLs in text fields, no birth years unless an official source gives them. Explain technical words briefly the first time (for example "mTORC1, the growth-control complex").

## Output
`patch3_N.json` in this folder: {"<key>": {full, lab_name, lab_url?, orcid?, role, sub, story, highlights, sources, note}}. Write it after every 4 people (programmatically with python, not by retyping old content). Every key in your input must appear once; if research added nothing, still rewrite story and role from the study and PubMed record.
Final reply: counts only (rewritten, with current position confirmed, unchanged identity concerns), plus a short list of `note` items that need Petr's attention.
