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

1. **Hugging Face Datasets** — review `outreach/huggingface_dataset_card.md`,
   create/use a HF account, create a new public dataset, upload the four
   files in `data/exports/` (re-run `tools/seo/build_data_exports.py`
   first if the corpus has grown since this branch), paste the card
   content as the repo's README. ~15 minutes, no review queue.
2. **Kaggle** — review `outreach/kaggle_dataset_draft.md`, create/use a
   Kaggle account, "New Dataset", upload the same four files, paste the
   form-field copy. ~10 minutes, no review queue.

Nothing else needed manual action from Úkol 1–2 (pure site-content
changes). **Nothing has been merged to `main` or deployed.** When you're
ready: review the diff on `seo-p0-2026-09`, merge to `main` yourself,
then run `deploy_with_pathway_refresh.bat` on Windows (cannot be run
from this session).

---

## Úkol 3 — Real downloadable data exports (DONE, committed)

Commits `1541d125` (exports + Dataset distribution) and `e341a022`
(outreach drafts) on `seo-p0-2026-09`.

**What was built:** `tools/seo/build_data_exports.py` generates
`data/exports/{studies,entities}.{csv,json}` (354 studies, 146
entities) plus a `README.md` and a `manifest.json` (name, format, byte
size, sha256 per file) directly from `atlas_data/studies_baked.json` /
`entities_baked.json`. These are **data files, not new HTML pages** —
not in any sitemap, no title/H1 of their own — so this doesn't touch
the "never increase page count" rule; page count is unchanged from
after Úkol 2 (354/46/10/47 study/entity/question/author pages).

The Dataset JSON-LD (`DATASET_REF.distribution`, previously a single
Zenodo entry) now also lists each live export file, read from
`manifest.json` at build time — so this can never silently drift from
what's actually on disk the way a hand-maintained second list would.
The `/data/` page gained a matching "Download the data" section from
the same manifest. Both are wired to regenerate automatically on every
build; if `data/exports/` doesn't exist yet (e.g. a build that skips
the export step), both fall back gracefully to just the Zenodo entry —
no broken links, no crash.

**Why this matters for discoverability:** Google Dataset Search and
similar crawlers weight a `Dataset`'s `distribution` field — a
JSON-LD-only claim to be "a dataset" is weaker evidence than one with
real, checksummed, directly-downloadable files. This also gives
Hugging Face / Kaggle something concrete to point to instead of asking
someone to scrape the live site's HTML.

**Manual next steps:** the two outreach items above (Manual next steps
section). Everything else in Úkol 3 needed no external action.

---

## Úkol 11 — Small technical items (DONE except item 1's pathway/mechanism/events links)

Commit `238ca6ed` on `seo-p0-2026-09`.

**1. `llms.txt` numbers — no action needed, already live.** Read the
generator before touching anything: `llms.txt`'s study/entity counts are
computed from the corpus at build time (`f"{len(studies)}"` etc.), not
hardcoded, so there was nothing stale to update. Added `/data/exports/`
and `/changelog/` to its "Machine-readable" section. **Not added:**
`/pathway/`, `/mechanism/`, `/events/` — the brief asks for these, but
they don't exist as static HTML pages yet (that's Úkol 4/5, not started
this session — see below). Linking to non-existent pages would create
dead links in a file specifically meant to be a reliable map for AI
crawlers, so this is deferred until those pages exist, not silently
dropped.

**2. GitHub topics** — you set these in the GitHub repo UI (Settings →
general → Topics), not something this session can or should do (repo
settings, not repo content). Suggested list from the brief:
`mtor`, `pathway-database`, `knowledge-graph`, `biocuration`,
`evidence-synthesis`, `aging-biology`.

**3. Corrections log — done.** New `/changelog/` page
(`changelog_page()` in `build_pages.py`) lists every correction from
`AUDIT_changelog_studies.json` + `REVIEW_changelog_studies.json`: date
(audit-round approximation — same caveat as Úkol 2's "Record last
updated"), study SID, field changed, one-sentence reason. Currently 46
corrections across 35 study records. `/about/` gained a "Corrections
log" paragraph linking to it — turns the existing "all were addressed
rather than quietly dropped" claim into something a reader can actually
check.

**4. Answers↔question cross-link audit — done, and a real gap was
found and fixed.** Ran the audit myself rather than trusting the
existing fix: the 2026-08-29 patch (`GAP_TO_ANSWER`) added exactly one
hand-picked reverse link. My own scan found the actual state was worse
than one gap — **2 more `/question/` pages were cited by 5 different
`/answers/` pages combined**, a many-to-one relationship a single
hardcoded pair can't represent. Replaced it with a general reverse
index (`ANSWER_GAP_BACKLINKS`, built the same way as Úkol 2's
`ANSWERS_BY_SID`) that renders every matching answer, not just one.
Re-verified after the fix: **zero one-directional answers↔question
links remain** across all 10 answer pages and 10 question pages (was 7
one-directional gaps before this fix).

**Manual next steps:** set the GitHub topics (item 2) whenever
convenient — no urgency, no dependency on anything else.

---

## Úkol 6 — Academy Bioschemas TrainingMaterial + TeSS/MERLOT/OERCommons drafts (DONE, committed)

**What changed.** All 14 published Academy pages (10 lessons + 1
Research Challenge) now carry the Bioschemas `TrainingMaterial`
profile on top of the existing `LearningResource` JSON-LD
(`lesson_page()` / the challenge-page block in `build_academy.py`):

- `"@type"` widened from `"LearningResource"` to
  `["LearningResource", "TrainingMaterial"]`
- `"learningResourceType"` changed from `"lesson"`/`"activity"` to
  `"e-learning"` — the value Bioschemas/TeSS actually recognize
- new `"keywords"` (same list as the existing `"teaches"`/
  `researchSkills`, so it can't drift out of sync)
- new `"audience"`: `{"@type": "Audience", "audienceType": "students
  and self-directed learners with a basic biology background"}`
- `"author"` now includes the curator's ORCID (`url` + `sameAs`),
  previously name-only

**Course/CourseInstance markup needed no changes.** `curriculum_page()`
already emits `Course` + `hasCourseInstance` with `courseMode`, which
is what Google's Course rich-result eligibility actually requires —
that part pre-dates this session and was already correct.

**Outreach drafts (all unsent, per the brief's hard rule — no
accounts created, no forms submitted from this session):**

- `tools/seo/build_tess_dump.py` → `outreach/tess/atlas-academy.json`
  — 1 Course entry + 10 Material entries, generated directly from
  `academy_data/lessons.json` + `modules.json` (not hand-typed), so it
  mirrors exactly what the live lesson pages say and can't silently
  drift from them the way a hand-maintained list could.
- `outreach/merlot/merlot-fields.md` — copy-paste values for MERLOT's
  "Contribute a Material" form.
- `outreach/oercommons/fields.md` — copy-paste values for OER
  Commons' "Add Material" form.

**NEVEROVERENO (unverified):** this VM has no network egress to
tess.elixir-europe.org, merlot.org, or oercommons.org, so the exact
current field names / submission schema on those live forms could not
be checked. The field names used follow each platform's
well-documented, long-stable conventions (Bioschemas TrainingMaterial
for TeSS; MERLOT's and OER Commons' standard contribute-a-resource
fields) — treat these as strong starting drafts, not guaranteed-exact
submission payloads. Sanity-check field labels against the live form
before submitting.

**Manual next steps:**
1. TeSS: submit `outreach/tess/atlas-academy.json`'s 11 entries via
   TeSS's own submission flow (community-curated training registry —
   check whether that's a web form or a content-provider API
   registration at https://tess.elixir-europe.org/).
2. MERLOT: create/use an account, "Contribute Material", paste the
   fields from `outreach/merlot/merlot-fields.md`. Goes through
   editorial review — expect a delay before it's live.
3. OER Commons: create/use an account, "Add Material", paste the
   fields from `outreach/oercommons/fields.md`.

---

## Úkol 7 — NCBI LinkOut submission package (DONE, committed, unsent)

New `tools/seo/build_linkout.py` generates the complete LinkOut
provider application under `outreach/linkout/`, data-driven from
`atlas_data/studies_baked.json`'s own `pmid` field (310 of 354 studies
have one — a wider source than the 267-entry DOI→PMID map used
elsewhere):

- `providerinfo.xml` — one `<Provider>` block; `ProviderId` set to a
  `00000` placeholder pending NCBI's real assignment on approval.
- `resources.csv` — **310 rows** (the brief's bar was ≥300), one per
  PMID-mapped study.
- `application-email.md` — unsent draft to linkout@ncbi.nlm.nih.gov.
- `icon-16x16.png` / `icon-100x20.png` — generated from the site's live
  `favicon.png` (the actual production mark, not an unshipped concept
  from `brand/logo-concepts/`).
- `README.md` — manual next steps, including that `resources.csv`'s
  `IconUrl` points to a path (`outreach-assets/linkout-icon-16x16.png`)
  that doesn't exist on the live site yet and needs to be deployed
  before the application is sent.

**NEVEROVERENO:** NCBI's exact current `SubjectType`/`Attribute` enum
values (this VM has no network egress to
https://www.ncbi.nlm.nih.gov/books/NBK3812/) — `SubjectType` set to
`Data resource` from memory, `Attribute` left blank. Confirm before the
final FTP upload.

**Manual next steps:** host the icon at the path `resources.csv`
references → send the application email → wait for NCBI's ProviderId →
substitute it into both files → FTP the corrected `resources.csv`.

## Úkol 8 — Bioregistry / Database Commons / NAR / Wikidata drafts (DONE, committed, unsent)

Four registration/addition drafts, nothing submitted or edited live:

- `outreach/bioregistry/new-prefix.md` — prefix `mtoratlas`, URI
  pattern `https://mtor-atlas.org/study/$1/`. **Caught a real error in
  the brief's own suggested regex:** `^[A-Z]+\d{4}[A-Z]?$` (exactly 4
  digits) does not match all 354 SIDs — one record
  (`NCT05835999`, a clinical-trial identifier) has 8 digits. Widened to
  `^[A-Z]+\d{4,8}[A-Z]?$` and verified against every SID: 0
  non-matches, 0 duplicates, 0 lowercase.
- `outreach/database-commons/fields.md` — basic info / data / access /
  publication sections, DOI in the publication section.
- `outreach/nar-db-collection/summary.md` — 56-word summary (≤100
  required), category "Literature / Pathways".
- `outreach/wikidata/Q141256074-additions.md` — bio.tools ID
  (`olivers_mtor_atlas`) and FAIRsharing ID (`8905`) statements to add.
  Property IDs (Pxxx) explicitly flagged **"ověřit property ID"** per
  the brief — no network egress to wikidata.org to look them up, so no
  guessed property number is included.

## Úkol 9 — Research Square preprint manuscript (DONE, committed, unsent)

New `tools/seo/build_research_square_manuscript.py` rewrites the
existing OSF (2026-08-29) and F1000Research (2026-09-01) project drafts
into the Resource/Software-description shape this task asks for
(Abstract, Background, Resource description, **Evaluation** — new,
Limitations, Availability, References), and generates
`outreach/research-square/manuscript.md` + `manuscript.docx`
(python-docx, verified to open) + `submission-checklist.md`.

**Every number in the Evaluation section is computed directly from
repo data at generation time** — none typed by hand:

- Tier distribution: A=2, B=35, C=97, D=217, 2 preprints + 1
  registered trial outside the A–D hierarchy (354 studies total).
- PMID coverage 310/354 (87.6%), PMCID coverage 180/354 (50.8%).
- 146 knowledge-graph entities, 46 meeting `build_pages.py`'s own
  `PAGE_THRESHOLD=3` and getting a standalone page.
- Current `validate_claims.py` run: 17 findings, **all WARN, 0 ERROR**.
- External review results quoted from the source documents (not
  recomputed, since they're qualitative): 16 findings / 4 blocking
  (`REVIEW_external_scientific_2026-07-29.md`), all corrected (24
  study records + associated gap/entity/relation records, 49
  repository files regenerated) per
  `AUDIT_scientific_calibration_2026-07-29.md`, with the validator's
  own before/after re-detection (14 ERROR + 10 WARN pre-correction →
  0/0 post-correction on the then-275-study corpus) quoted alongside.

**Important context carried into `submission-checklist.md`:** two
prior venues for this same content were already set aside — bioRxiv
and Preprints.org declined earlier drafts, and **you (Petr) explicitly
declined F1000Research on 2026-09-02, specifically over its ~$1,268
APC**, even though that fee is billed only after acceptance. Research
Square has historically been free for standard preprint posting
(unlike a journal), but this VM has no network egress to confirm that
against its current policy page — the checklist's first line tells you
to re-verify there's no fee **before** creating an account, given your
stated fee-sensitivity on this exact manuscript.

**Manual next steps:** re-verify no posting fee → create/log in with
ORCID → category Life Sciences → upload `manuscript.docx` → CC BY 4.0 →
declarations (no funding, no competing interests) → review the PDF
preview against the stats listed in `submission-checklist.md` → submit.

## Úkol 10 — AI citation baseline (DONE, committed)

A Chrome browser tool was available this session, so this task ran
rather than being skipped. `docs/AI_CITATION_BASELINE_2026-09.md` has
the full table: **10 queries from the brief, run against Google AI
Mode and Bing**, anonymously (no accounts created, no logins performed
by this session), via each engine's direct search URL.

**Headline finding:** on the 8 generic mTOR-biology queries, the Atlas
is cited by **neither** engine yet — both answer from long-established
high-authority sources (NIH/PMC, Wikipedia, Reactome, DrugBank, Cell
Signaling Technology). This matches the "authority is the dominant
lever, takes weeks not days" conclusion already on file from the
2026-08-22 audit — this just gives it a dated, concrete baseline to
compare a future re-run against. On the 2 queries naming the resource
or its category, both engines already know it: "evidence-graded mTOR
database" surfaces the Atlas as the top/only cited source on **both**
engines; the exact brand query gets a 9-of-9 mtor-atlas.org sweep on
Bing, and is described correctly (though not footnote-cited) by Google
AI Mode.

**Engine coverage, honestly:** Perplexity and Microsoft Copilot both
require signing in/up to run even one query — attempted, then not used
further, per the brief's hard rule. ChatGPT search recognized your own
pre-existing logged-in browser session (this session did not log in or
create anything), but reliably automating query submission through its
UI wasn't achieved in the time available — documented as not
completed rather than reported with unreliable partial data. If you
want ChatGPT's numbers too, running the same 10 queries by hand takes
a few minutes since you're already signed in.

**Bing Webmaster Tools — NOT set up, per the brief.** Exact steps (sign
in, add `mtor-atlas.org`, verify via DNS TXT or GSC import, submit the
sitemap, check IndexNow history after ~3 days) are in that same file
for you to run.

---

## Úkol 4 & 5 — investigated, not executed (structural, needs your review)

Both remaining tasks change the site's basic serving structure on a
live production site this session cannot screenshot or visually render
to verify — a materially different risk class from every template/data
change completed above (all of which are reversible, additive, and
independently validated by the pipeline). Rather than guess at
information-architecture decisions that are really yours to make, this
section is a concrete investigation and proposal for each, so a future
session (or you, directly) can execute confidently instead of starting
from zero.

### Úkol 4 — static homepage, SPA moved to `/app/`

**Not investigated in depth this session** — it's the highest-risk
single change in the whole brief (the root URL is the site's most
important page for both search and human visitors) and deserves a
dedicated pass on its own. The brief's own two variants stand as
written:

- **Variant A:** move the current SPA to `/app/`, serve a new static
  page at `/`. Bigger change, cleanest separation of "crawlable
  landing page" from "interactive tool" — but every internal link,
  bookmark, and external backlink pointing at `/` needs a plan (redirect
  the SPA's current hash-routes, or accept that `/#map` etc. stop
  resolving as people expect).
- **Variant B:** keep the SPA at `/`, add a static, crawlable block
  above the fold (rendered HTML, not JS) that a non-JS crawler sees
  immediately, with the interactive app below/behind it. Smaller,
  reversible, no URL changes — closer in spirit to how `prerender_tabs.js`
  already solved this same problem for the Questions and Events tabs
  (crawler and human see the same content, without moving anything).

**Recommendation:** start with Variant B. It reuses a pattern that's
already proven on this exact site (prerender_tabs.js), carries far
less risk of breaking an existing bookmark or backlink, and can be
validated the same way every other change this session made was
validated (build → prerender → verify_prerender.py → diff review)
without needing a visual re-design of the whole homepage.

### Úkol 5 — static `/pathway/`, `/mechanism/`, `/events/` pages

**Investigated in detail.** The good news: the source data is already
clean, structured, and read-only (`pathway/model.json` — 88 nodes, 119
interactions, 11 routes, 6 loops, generated by `build_pathway_model.py`
and never hand-edited, per the hard rule — and `atlas_data/events_baked.json`,
40 conference/meeting events, 24 of them future/ongoing as of today).
Nothing needs new data collection; this is a rendering task, in the
same shape as `changelog_page()` (Úkol 11) and `data_page()` — read an
existing JSON file, render it through `shell()`, wire it into `main()`.

**Why this session didn't just build it anyway:** three real,
site-specific design decisions surfaced during investigation that
change what the pages should contain, and this session has no way to
render and look at the result to check whether the answer is right:

1. **`/events/` currently lives *inside* the Timeline (`lineage`) tab's
   SPA view**, not as its own concept — `#eventsView` is nested in the
   same tab as the recent-studies chronology. A static `/events/` page
   could either (a) mirror that same content standalone, or (b) become
   the canonical source and have the Timeline tab link out to it
   instead of duplicating it. (a) is lower-risk and faster; (b) is
   cleaner but touches the SPA's existing tab structure.
2. **`/pathway/` vs `/mechanism/` is not a distinction the current data
   model makes.** `model.json` has one flat set of `nodes` +
   `interactions` + `routes` — there's no existing split between "the
   pathway" and "a mechanism." Two reasonable readings: (a) `/pathway/`
   = an overview page (compartments, all 11 routes with their
   already-written narrative `story`/`journey` text) and `/mechanism/`
   = a deeper reference page (the full 119-interaction table, grouped
   by route, with each interaction's `mechanism` text and evidence);
   or (b) collapse both into one comprehensive `/pathway/` page and
   treat "mechanism" as a section within it, skipping a second URL
   entirely (a single well-organized page beats two thin ones, and the
   brief's own rule of thumb — no page for content with nothing to say
   — argues for this if the split content would be thin either way).
   **Recommendation: (b)** — one `/pathway/` page, no separate
   `/mechanism/` — unless you specifically want the two as distinct
   crawlable targets for different query types.
3. **The interactive diagram itself (node positions, compartments,
   bands, the visual layout `pathway.js`/`pathway.css` render) is not
   reproducible as static HTML without becoming a second, parallel
   rendering engine to maintain.** The content that actually helps
   AI-search citability, though, is the *text* — the routes' narrative
   walkthroughs and each interaction's mechanism explanation are
   already well-written prose in `model.json`, not the diagram's pixel
   layout. A static `/pathway/` page built as structured text (the 11
   routes' stories in full, a table of the 119 interactions with their
   mechanism/evidence, grouped by route) would be directly useful to a
   text-based crawler without attempting to redraw the diagram.

**Concrete next step, if you want this built:** a `pathway_page(model)`
function in `build_pages.py`, same shape as `changelog_page(studies)`:
read `pathway/model.json` (read-only), render the routes and
interactions through `shell()`, write `pathway/index.html`  — noting
`pathway/` as a directory already exists for the JS/CSS assets, so the
new file would sit alongside `pathway.js`/`pathway.css`, not replace
them — add it to `sitemap-home.xml` alongside `/about/`/`/data/`
/`/changelog/`, and point the "map" tab's `STATIC_TAB_URLS` entry at it
the same way `about` and `learn` already work. `events_page(events)`
follows the same shape from `atlas_data/events_baked.json`. Both are
tractable in a single focused session with the ability to view the
rendered output before it goes live — which is exactly the piece this
session lacks.

This handover will be updated again if either task is picked up.

---

## Consolidated manual next steps (everything in one place)

Every action below is unsent/unmerged/undeployed by this session, per
the brief's hard rules. Roughly in the order it makes sense to do them:

1. **Review the branch, merge, deploy.** Review the diff on
   `seo-p0-2026-09` against `main` yourself; when satisfied, merge it
   and run `deploy_with_pathway_refresh.bat` on Windows (this session
   cannot run it). Nothing on the live site changes until you do this.
2. **Host the LinkOut icon.** Copy `outreach/linkout/icon-16x16.png` to
   wherever `outreach-assets/linkout-icon-16x16.png` should live on the
   deployed site — `resources.csv`'s `IconUrl` column points there and
   the path doesn't exist yet.
3. **NCBI LinkOut** — send `outreach/linkout/application-email.md`'s
   content to linkout@ncbi.nlm.nih.gov with `providerinfo.xml`,
   `resources.csv`, and both icon PNGs attached (do this *after* step 2
   so the icon URL resolves). When NCBI approves and assigns a real
   ProviderId, substitute it into both files and FTP the corrected
   `resources.csv`.
4. **Hugging Face Datasets** — `outreach/huggingface_dataset_card.md`,
   ~15 minutes, no review queue.
5. **Kaggle** — `outreach/kaggle_dataset_draft.md`, ~10 minutes, no
   review queue.
6. **TeSS** — submit `outreach/tess/atlas-academy.json`'s 11 entries via
   TeSS's own submission flow.
7. **MERLOT** — `outreach/merlot/merlot-fields.md`, "Contribute
   Material"; goes through editorial review, expect a delay.
8. **OER Commons** — `outreach/oercommons/fields.md`, "Add Material".
9. **Bioregistry** — open a GitHub issue using
   `outreach/bioregistry/new-prefix.md`'s fields (note: use the
   corrected regex in that file, not the brief's original 4-digit one).
10. **Database Commons** — `outreach/database-commons/fields.md`.
11. **NAR Database Collection** — check the current submission
    mechanism first (see `outreach/nar-db-collection/summary.md`'s
    note — it may require a companion manuscript, not a form).
12. **Wikidata (Q141256074)** — add the two statements in
    `outreach/wikidata/Q141256074-additions.md`; look up the correct
    property IDs yourself in Wikidata's property search first (flagged
    "ověřit property ID" — not guessed in the draft).
13. **Research Square** — **first**, re-verify there's no posting fee
    (see `outreach/research-square/submission-checklist.md`'s opening
    note — you already declined F1000Research on 2026-09-02 over its
    APC, so check this before creating an account); then follow the
    checklist to submit `manuscript.docx`.
14. **GitHub topics** — add `mtor`, `pathway-database`,
    `knowledge-graph`, `biocuration`, `evidence-synthesis`,
    `aging-biology` in the repo's Settings → General → Topics.
15. **Bing Webmaster Tools** — NOT set up by this session, per the
    brief. Steps are in `docs/AI_CITATION_BASELINE_2026-09.md`'s
    closing section: sign in, add `mtor-atlas.org`, verify (DNS TXT or
    GSC import), submit the sitemap, check IndexNow history after ~3
    days.
16. **Úkol 4 & 5** (static homepage variant, `/pathway/`/`/mechanism/`/
    `/events/` pages) — see the design proposal above; pick up in a
    session where the result can be visually reviewed before it goes
    live.

## Noindex SID decision (from Úkol 1/2, carried forward)

`atlas_data/seo_noindex_studies.json` is `[]` — 0 SIDs met the strict
thinness criterion after the Úkol 2 template rebuild. A relaxed
criterion flagged 14 SIDs as borderline-thin; that list was documented
in Úkol 2's section above (not repeated here) and left as your call —
nothing was added to the noindex file without your decision.
