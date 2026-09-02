# SEO P0/P1 — Handover (Oliver's mTOR Atlas)

**Branch:** `seo-p0-2026-09` (created from `main`, not merged, not deployed)
**Session date:** 2026-09-02
**Source brief:** `docs/ZADANI_SONNET_SEO_P0_P1_2026-09-02.md`

This document is written incrementally as tasks complete, per the brief's
own instructions. It will be extended as Úkol 3–11 progress. Everything
under "Manual next steps for Petr" at the end is cumulative — check back
there before deploying or sending anything.

---

## Úkol 1 — Measure how thin the study pages are (DONE, committed)

Commit `992eab47` on `seo-p0-2026-09`.

**Deliverable:** `tools/seo/measure_study_pages.py` + `atlas_data/seo_study_audit.csv`
(354 rows, one per `study/<SID>/index.html`).

Measures, per study page: total visible text, PubMed-abstract text, and
"unique" (curated) text — finding + Extracted-findings table + entity-tag
links — plus a ratio and content-length bands.

**Important correction (found and fixed during Úkol 2, see below):** the
very first version of this script had two boundary bugs that inflated
`n_entity_links` and `chars_unique` on any page whose "Related topics"
section was the *last* heading on the page (i.e. most pre-rebuild pages,
which had no academy cross-link). The originally-committed baseline
numbers from Úkol 1 were affected by this. The script has since been
fixed (see Úkol 2) and **`atlas_data/seo_study_audit_before.csv`** is
the corrected, apples-to-apples re-measurement of the pre-Úkol-2 pages
(via `git archive HEAD -- study` at the point before the Úkol 2 commit).
Use `_before.csv`, not the original Úkol 1 numbers quoted in earlier
notes, for any before/after comparison.

**Original diagnosis stands:** the dominant content on most study pages
was literal PubMed abstract text; curated/unique content was a small
fraction of the page.

---

## Úkol 2 — Rebuild the study page template (DONE, committed)

Commits `5a3c1922` (main rebuild) and `57e49e1c` (fixed a stale
`seo_study_audit_after.csv` left over from an intermediate measurement
run — see that commit message) on `seo-p0-2026-09`.

### What changed on every `study/<SID>/index.html`

New section order, replacing the old "H1 → At a glance → Extracted
findings (level-gated) → full abstract → Related topics → footer":

1. **What this study shows** — the curated finding, plus a new
   `tier_reason()` sentence explaining *why* this record has this tier
   (design category, not a quality grade — 8 template variants by
   tier×category so a null-result animal study doesn't read the same as
   a mechanistic in-vitro one).
2. **At a glance** table — added a "Record last updated" row.
   *Caveat:* neither changelog JSON carries a true per-field date; a SID
   gets the 2026-07-29 audit-round date if it appears in either
   changelog, else the `CITATION.cff` release date as fallback. This is
   coarser than a real per-record timestamp — flagged here, not hidden.
3. **Extracted findings** — now **always visible** (previously
   level-gated/hidden for beginners) whenever any field is present.
   Also now includes 4 new fields — Dose, Sample size, Effect size,
   Limitations — that existed in Airtable's `AI_Dose` / `AI_SampleSize`
   / `AI_EffectSize` / `AI_Limitations` columns but were **never synced
   down** by `sync_airtable.py` (same class of gap previously found and
   fixed for entities — see project memory `entities-bake-path`).
   `sync_airtable.py`'s `fetch_studies()` now pulls these; 41 of 43
   studies fetched from Airtable gained the fields in
   `atlas_data/studies_baked.json` (2 had no data in Airtable for these
   columns).
4. **In the Atlas** — new section combining every internal cross-link a
   record has, each with a sentence of context instead of a bare list:
   entity tags (unchanged), a new **Open questions that cite this
   study** block (reverse index built from `gaps_baked.json`), a new
   **Answers that reference this study** block (reverse index built by
   scanning the hand-baked `/answers/` pages for `/study/<SID>/` links —
   `/answers/` has no separate machine-readable source, so the published
   HTML is the source of truth here), and the existing "Learn the
   biology" Academy link.
5. **Abstract** — truncated to ~600 characters at a sentence boundary
   (never mid-word), with a "Read the full abstract on PubMed →" link
   when truncated. The **full** abstract stays in the page's JSON-LD
   (`abstract` field) for machine/AI consumption — Google does not treat
   JSON-LD-only text as visible duplicate content, so nothing is lost
   for citation purposes, only for the "wall of pasted abstract" that
   was the thin-content problem.
6. **Cite this record** — new APA + BibTeX block citing the **Atlas
   record** (SID, Atlas URL, dataset DOI), not the original paper.

### Reversible noindex mechanism

`shell()` gained a `robots=` parameter (default `"index, follow"`, so
every non-study page is byte-identical to before). Per-study robots is
now driven by `atlas_data/seo_noindex_studies.json` — a plain, editable
JSON array of SIDs — consumed by both `study_page()` and the
`sitemap-studies.xml` writer (noindexed SIDs are excluded from that
sitemap).

**Currently this list is empty `[]`.** The brief's strict criterion
(`chars_unique < 250 AND n_entity_links == 0 AND has_extracted == 0`)
matches **0 of 354** studies post-rebuild — every study with under 250
characters of unique text has *at least* an Extracted-findings table or
an entity link. That is itself a sign the rebuild helped.

**For your discretion — a relaxed-criterion candidate list** (dropping
the `has_extracted == 0` condition, i.e. `chars_unique < 250 AND
n_entity_links == 0`) surfaces **14 SIDs**. All 14 do have an
Extracted-findings table (so they're not empty pages), but have no
entity tags and under 250 chars of finding+tags text — thin by the
"no cross-links, terse finding" measure, not by "no curated content at
all":

| SID | Tier | chars_unique | chars_total |
|---|---|---|---|
| SCI2014 | D | 192 | 2587 |
| SZW2021 | D | 227 | 2574 |
| DIB2013 | D | 228 | 2542 |
| PEN2017 | D | 231 | 2574 |
| WOLF2017 | D | 233 | 2508 |
| ZON2010 | D | 234 | 2483 |
| POW2006 | C | 239 | 2561 |
| VAL2019 | D | 239 | 2540 |
| CHI2012 | D | 241 | 2615 |
| PAR2014 | D | 241 | 2639 |
| BETZ2013 | D | 243 | 2577 |
| OSH2007 | D | 243 | 2841 |
| BAT2022 | D | 246 | 2534 |
| KIM2012 | D | 247 | 2575 |

**Recommendation:** I did not noindex these — the brief's own strict
rule doesn't flag them, and every one has real curated content
(Extracted findings). Whether to noindex them, add entity tags to them
in Airtable instead (which would organically fix the underlying gap and
is probably the better fix), or leave them as-is is a curatorial call
for you/Oliver, not something to automate. To noindex any of them, add
their SIDs to `atlas_data/seo_noindex_studies.json` (a plain JSON array)
and re-run `build_pages.py`.

### Honest before/after numbers (354 studies, same corrected script both sides)

Before = `atlas_data/seo_study_audit_before.csv` (pre-rebuild pages, via
`git archive`, re-measured with the corrected script for a fair
comparison). After = `atlas_data/seo_study_audit_after.csv` /
`seo_study_audit.csv` (identical — current live pages).

| Metric | Before | After |
|---|---|---|
| Median `ratio_unique` (unique text ÷ total text) | 0.155 | 0.140 |
| Median `chars_unique` | 380 | 405 |
| Pages with `chars_unique` < 400 ("thin") | 187 / 354 | 170 / 354 |
| Pages with `chars_unique` > 800 | 15 / 354 | 46 / 354 |
| Pages with any Extracted-findings content | 342 / 354 | 346 / 354 |
| Pages with zero entity-tag links | 165 / 354 | 165 / 354 (unchanged) |
| Pages with at least one "In the Atlas" cross-link (entities, gaps, answers, or academy combined) | n/a (section didn't exist) | 205 / 354 |

**Read this honestly, not as a clean win on every number.** The median
*ratio* of unique-to-total text barely moved and even dipped slightly —
because the page got *longer* overall (tier-why sentence, cite block,
extra table rows), not because unique content shrank. The real signal
is elsewhere: the >800-char unique-content band roughly tripled (15→46),
the thin (<400) band shrank by 17 pages, four more studies now surface
Extracted findings, and 205 pages gained at least one internal
cross-link they didn't have before (open-question or answer citations,
on top of existing entity tags). Zero-entity-link pages are unchanged at
165 — the entity-linking data itself wasn't touched, confirmed by a
regex-boundary bug hunt that turned up 0 diffs in `n_entity_links`
between the two measurement runs once the extractor's own boundary bugs
were fixed. Whether Google's crawler treats `ratio_unique` or absolute
unique-content length as the stronger thin-content signal isn't
something I can verify from inside this environment — no network
egress to Search Console. This is presented as the honest picture, not
oversold.

### Validation run

Full pre-commit pipeline (`stamp_updated.py` → `build_academy.py` →
`build_pages.py` → `stamp_pathway_version.py` → `prerender_tabs.js` →
`verify_prerender.py` → `validate_claims.py --strict` →
`verify_index_html.py` → `check_tier_palette.py`) completed clean.
`validate_claims.py --strict`: **OK**, 17 findings, all pre-existing and
unrelated to this change (confirmed by diffing against a pre-Úkol-2
validation run). `pathway/model.json` was not touched. Page count is
unchanged (no new pages created — same 354 study pages, same total URL
count). No links to the GitHub repo were added anywhere on the live
site. No `citation_*` Google Scholar meta tags were added.

---

## Manual next steps for Petr (cumulative — updated as tasks complete)

None yet from Úkol 1–2 specifically — no external actions were needed
for either task (both are pure site-content changes on the working
branch). This section will grow as Úkol 3 onward produce outreach
drafts, registration forms, and other items that need a human to send/
submit/approve them. **Nothing has been merged to `main` or deployed.**
When you're ready: review the diff on `seo-p0-2026-09`, merge to `main`
yourself, then run `deploy_with_pathway_refresh.bat` on Windows (cannot
be run from this session).

---

*(Úkol 3–11 sections to follow as each completes.)*
