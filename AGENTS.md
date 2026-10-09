# AGENTS.md — Oliver's mTOR Atlas (data + source repo)

Instructions for coding agents (Codex and others) working on this repository.
Read this whole file before changing anything. The constraints below come from
real incidents; most of them looked harmless until they broke the live site.

## 1. What this project is

Oliver's mTOR Atlas (https://mtor-atlas.org) is a curated, evidence-labelled
database of mTOR research: ~400 hand-picked studies, entities (genes, drugs,
diseases), signed pathway relations with supporting and conflicting studies,
open questions, author profiles, an Academy with lessons and games, a public
JSON API and an MCP server.

- The name is always **Oliver's mTOR Atlas**, never "Open mTOR Atlas".
- All site content is in **English**, written so a motivated high-school
  student can follow it, without losing scientific accuracy.
- Curators: Oliver (scientific owner, public face) and Petr.

## 2. The three places things live

| Place | What it holds | Who writes it |
|---|---|---|
| **Airtable** base `appt2U6ObDHUcRlrj` | Source of truth for Studies, Entities, Relations (pathway edges), Events, Authors, Knowledge_Gaps | Curators, daily check task, `sync_*` scripts read it |
| **This repo** `open-mtor-atlas/atlas`, branch `main` | Baked JSON (`atlas_data/`), Python generators, Academy, pathway model, gates, the old single-page app `index.html` | Build scripts; humans edit generators, not generated output |
| **`open-mtor-atlas/atlas-v2`** (folder `../Atlas_v2`) | The Astro site that is actually served. Reads baked data and prose from `main` | Humans edit `src/` and `scripts/` there |

The live site is served from branch **`gh-pages`** of this repo, which is
produced by `Atlas_v2/deploy_v2.bat`. `main` itself is no longer the website,
but it is still the **source** the website is built from. Never stop running
`build_pages.py` / `generate.py`: V2 reads curated prose from their output
(`Atlas_v2/scripts/sync_prose.py`).

Expected folder layout on the deploying machine (Windows):

```
Projects\
  Oliver biology Cowork\   <- clone of open-mtor-atlas/atlas (main)   [this repo]
  Atlas_v2\                <- clone of open-mtor-atlas/atlas-v2
  atlas-pages\             <- git worktree of this repo on gh-pages (created by deploy_v2.bat)
```

`deploy_all.bat` looks for `..\Atlas_v2\deploy_v2.bat`; the folder names matter.

## 3. Deploy (the only supported path)

Run **`deploy_all.bat`** from this folder on Windows. It runs:

1. `deploy.bat` — step 1: reconcile with origin, refresh data from Airtable
   (only if `AIRTABLE_TOKEN` is set), build Academy, pathway model, static
   pages, prerender, run all gates, commit and push to `main`.
2. `..\Atlas_v2\deploy_v2.bat` — step 2: snapshot from `origin/main`, Astro
   build, gates K1–K9, mirror `dist/` into `gh-pages`, push, IndexNow ping.

Facts that matter:

- Running only `deploy.bat` changes **nothing** on the website, silently.
- Step 2 builds from **`origin/main`**, not from the working copy. Anything not
  pushed in step 1 is invisible to step 2.
- If step 2 fails, fix it and rerun only `deploy_v2.bat`.
- `AIRTABLE_TOKEN` must be set in the environment (never in a file) or the
  Airtable refresh and the edge refresh are **skipped with only a log line**.
  Then the site ships whatever baked data is already in the repo.
- `deploy.bat` is not in its own `git add` list and aborts when it differs
  from `origin/main`. After editing `deploy.bat`, commit and push it
  explicitly before deploying.
- Network: `api.airtable.com`, `api.indexnow.org` and GitHub must be
  reachable. Cloud sandboxes usually cannot reach Airtable or IndexNow, so a
  full deploy runs on a local Windows machine, not in a cloud task.
- After a deploy, check https://mtor-atlas.org/ returns 200 and look at the
  page you changed. Headless checks do not prove the deployed page works
  (CDN cache, lazy loading and layout bugs have slipped through before).

There is no `deploy.sh` any more. If you need to deploy from macOS/Linux,
port the steps deliberately; do not improvise a partial pipeline.

## 4. Non-negotiable rules

1. **Airtable is the source of truth for data.** Never hand-edit
   `atlas_data/*_baked.json`, `ATLAS_STUDIES` / `ATLAS_EDGES` / `ATLAS_GAPS`
   in `index.html`, or `pathway/model.json` to fix content. Fix it in
   Airtable, then rebake. Manual edits in generated files are overwritten on
   the next deploy without a trace (this has happened).
   Exceptions that are edited directly in the repo:
   `atlas_data/author_bios_baked.json` (author profiles),
   `atlas_data/oliver_bio_baked.json` (Oliver's bio, `focus_studies`,
   `thanks[]`, `on_the_horizon`), `data/branches.json`,
   `academy_data/*.json`, `atlas_data/drug_pipeline.json` (/pipeline/ page,
   hand-curated, every status sourced and dated).
2. **Pathway edges** come only from Airtable `Relations`
   (`sync_relations.py`). Pathway nodes live in code
   (`build_pathway_model.py`). After touching edges, run
   `py sync_relations.py` without `--write` first and read the dry-run diff.
   Every edge needs at least one linked study. Reviews (R), preprints (PP)
   and registered trials (RT) are never evidence for an edge.
3. **Never write a PMID, DOI or author from memory.** Retrieve it from PubMed
   (or the DOI resolver) and verify the metadata before it goes anywhere.
4. **Evidence codes describe study design, not quality.** Displayed codes:
   S synthesis of human data, H human study, A animal model, M molecular /
   in vitro, R review, PP preprint, RT registered trial. Internally Airtable
   still stores A–D (`A→S, B→H, C→A, D→M or R` via the `pyramid` field).
   `Evidence_Tier` must agree with `Pyramid_Level` (A↔1, B↔2/3, C↔4, D↔5),
   otherwise `validate_claims.py` rule R7 blocks the deploy.
   The display layer has one source: `chrome_shared.py` (`TIER_LABEL`,
   `tier_bits()` which returns a **4-tuple**, `tier_badge()`). Never copy the
   palette into a generator. Every badge needs a `title`/`aria-label`.
5. **Epistemic calibration in all prose.** No marketing absolutes ("the
   first", "none of them", "proven"). Use hedged wording ("to our knowledge",
   "few"). Never upgrade a cell or mouse result to a human claim; keep species
   qualifiers. A lower evidence code does not mean worse science. The section
   is called **Open Questions**, not "Gaps & Hypotheses".
   `validate_claims.py --strict` checks this and must pass.
6. **URLs never change** (R5). GitHub Pages has no redirects, so V2 output
   must be a superset of every file V1 served. Removing a file = hard 404.
   In V2, paths are built only in `src/lib/urls.ts`.
7. **No secrets in files.** `AIRTABLE_TOKEN`, `GEMINI_API_KEY` and any other
   key live in environment variables only. `.env` and `*.token` are ignored.
8. **Don't commit drafts, internal notes or logs** to this public repo:
   `*-zpracovano.md`, `*_DRAFT.md`, working notes, `Claude outputs/`,
   `_to_delete/`, `dedup_index_cache.json`.
9. **No e-mail address anywhere on the site**, not even obfuscated. The
   "Report an error" button sends a GA4 `correction_report` event instead.
10. **Changelog scope:** `/changelog/` (`method_changes` in `build_pages.py`)
    lists methodology and grading changes only, never bug or rendering fixes.

## 5. Editorial decisions that are settled (do not "fix")

- `/authors/` deliberately shows only researchers with **3+ studies**
  (driven by the curated Airtable `Authors.Bio_Studies` allowlist). The count
  of profiles elsewhere is supposed to differ.
- Study pages are not `noindex`ed, thin or not.
- Lineage (six bands) and Branches (`data/branches.json`) are complementary
  axes, not competing taxonomies. "Signal dynamics" is not a seventh band yet.
- Contested edges stay public; a contradiction in the data is a finding.
- Homepage positioning: "The mTOR pathway, mapped by what the evidence can
  actually carry". The homepage text exists in two independent places
  (`index.html` meta/h1/lede and `Atlas_v2/src/pages/index.astro` `desc` +
  `ldDesc`); `/about/` too (SPA pane and `about_page()` in `build_pages.py`).
  Change both copies.
- Academy: audience is a motivated individual, English, XP as the point unit,
  closed list of 10 badges. Game rules live in `academy_data/practice.json`,
  not in code.
- Target audience for titles and descriptions: researchers, not commercial
  longevity searchers.

## 6. Author profiles

- Single source: `atlas_data/author_bios_baked.json` (keys like
  `"Sabatini DM"`, the short corpus form from `Studies.Authors`). Nothing goes
  into `index.html`; the SPA fetches the JSON at runtime.
- Fields: `full`, `role`, `sub`, `mono`, `init`, `lab_name`, `lab_url`,
  `photo`, `thumb`, `credit`, `story[]`, `highlights{SID: line}`, optional
  `bluesky`.
- `lab_name` is **required**, format
  `Lab name, Institution (City, State, Country)`; for China and European
  countries omit the state, e.g. `(Ganzhou, China)`. Add `lab_url` when
  verified. `build_lab_map.py` regenerates the lab map on every build and
  warns about missing `lab_name` or a city without coordinates; add missing
  coordinates to `atlas_data/lab_geo.json`.
- Create a profile for every new first/senior author whose identity is
  certain (institutional page, ORCID, or matching PubMed fore name +
  affiliation). Ambiguous "Surname Initial" keys get nothing. Authors with
  2+ studies, and every author of a study in Oliver's `focus_studies`, get a
  photo.
- Photos: institutional portraits only, never stock or look-alikes.
  `img/people/<first-last>.jpg` at 236×300 and `-thumb.jpg` at 132×168,
  cropped around the face, JPEG ~88, `credit: "Portrait: <institution>"`.
  Watch for embedded ICC profiles when cropping; check the result visually.
- Insert new keys without reformatting the whole file, then confirm the file
  parses and no existing key changed.
- `focus_studies[].authors` in `oliver_bio_baked.json` is an **array of two
  strings** `["first author", "senior author"]`, never one string (a string
  once broke the V2 build).
- Thanks on `/author/oliver-barton/` render in three places from the same
  JSON: `build_pages.py`, `renderOliverBio()` in `index.html`, and the V2
  `index.astro` for that page. Change the data shape in all three.

## 7. Adding a study (summary of the curation workflow)

1. Find candidate, confirm it is genuinely new: dedup against the corpus by
   PMID (digits only), normalised DOI, and normalised title. A title match
   with a different DOI is a preprint/published pair: do not add a second
   record, flag it.
2. Relevance bar: substantive primary study or major review clearly in scope,
   comparable to what is already curated. Negative results are wanted
   (`Category = Negative_result`, sign `no-effect`). Inclusion rules IN1–IN5 /
   exclusion EX1–EX4 are on `/about/` and in `build_pages.py`.
3. Write to Airtable Studies with the real PubMed abstract and all fields the
   existing records use. `Study_ID` = first 3 letters of first author's
   surname uppercased + year (`KOR2011`), then `B`, `C`… if taken.
4. Wire it into the knowledge layer in Airtable: `Linked Entities` (1–5
   entities it is substantively about), extend existing `Relations` edges only
   when the study's own data show that step (supporting or conflicting, with
   a dated `Curator_Note`), link open questions H1–H10 when it directly bears
   on them (append to `Supporting_Studies` and `Revision_Log`).
   `check_consistency.py` (a deploy gate) reports studies left unlinked.
5. Link/create authors (section 6), then `deploy_all.bat`.

Batch Airtable writes (one create/update call per table, up to 50 records).
Linked-record fields are replaced wholesale: send the full existing list plus
the new id. Never use `search_records` for dedup: it misses numeric tokens.

## 8. Adding a new static page (checklist)

A new page that skips any of these passes in V1 and then fails gate K1/K9 in
step 2, or is never committed:

- Build it through `build_pages.shell()` (chrome, GA4 `G-420TPC8J46`,
  canonical, footer) and verify they are present in the output.
- Breadcrumb must match the JSON-LD `BreadcrumbList`
  (`assert_crumb_matches_ld`). No HTML entities in titles.
- Add the URL to the right sitemap and an entry to `llms.txt`.
- **Add a row to `PAGES` in `Atlas_v2/scripts/sync_prose.py`** (most often
  forgotten; without it V2 never copies the page).
- New images outside `img/people/` (e.g. `img/moments/`) must be added to
  `ASSETS` in `Atlas_v2/scripts/sync_assets.py`.
- Check the `git add` loops in `deploy.bat`: subfolders of existing dirs are
  picked up, but a new top-level folder, a new root `.py` script or a new
  sitemap must be added explicitly. `git add -u` never picks up untracked
  files.

## 9. Gates (run after any change to generators)

```
py validate_claims.py --strict     # claim calibration, R1–R7, prose too
py check_tier_palette.py --strict  # evidence-code colours/labels everywhere
py check_consistency.py            # every study has entity/edge/question
py build_pathway_model.py && py validate_pathway.py --strict
node pathway/smoke_test.js         # hangs under Linux/jsdom; fine on Windows
py stamp_pathway_version.py        # mandatory cache-bust after model changes
py verify_academy.py
py verify_practice.py
node prerender_tabs.js && py verify_prerender.py
py verify_index_html.py
```

In `Atlas_v2`: `py scripts/gates.py --v1 "../Oliver biology Cowork" --v2 dist`
and `py scripts/verify_parity.py --v1 "../Oliver biology Cowork" --v2 dist --files`.

A failing gate means do not ship. Do not weaken a gate to make it pass.
Verify visual changes with a real browser screenshot (Playwright), not only
asserts; several "passing" builds were visibly broken.

## 10. Traps that recur

- **`index.html` is ~1 MB, CRLF on disk, LF in git** (`.gitattributes`).
  Never rewrite it in Python text mode (silently converts all line endings).
  Write to a temp file, `os.replace()`, then independently check it ends with
  `</html>`, that `ATLAS_STUDIES` / `ATLAS_EVENTS` parse as JSON, and diff
  against `git show HEAD:index.html` after normalising CRLF. Partial,
  silently truncated writes have happened on the OneDrive-synced folder.
- `about/index.html` is CRLF, `build_pages.py` is LF. Preserve each file's
  line endings.
- **Events** have no automatic Airtable path: MCP/REST dump →
  `map_events_dump.py` → `atlas_data/events_baked.json` →
  `bake_from_mcp.py` → `index.html`, then rerun `prerender_tabs.js`.
  `mTOR_Relevance` must start with `TIER 1 — ` / `TIER 2 — ` / `TIER 3 — `.
- Two mapping paths into baked data (`sync_airtable.py` via REST and
  `map_*_dump.py` via MCP) must map the same fields. If you change one, change
  the other, or one silently erases the other's fields.
- Python strings holding CSS/JS (`CHALLENGE_JS`, Academy CSS): escapes like
  `\2713` or `\n` must be doubled.
- SVG elements have no `.click()`; dispatch a `MouseEvent`. SVG edges need
  `pointer-events:none` so they don't steal clicks from nodes.
- `pathway.js` runs in both the old SPA and V2. Anything reading `window.*`
  needs a fallback, and V2 must supply it explicitly.
- Stale `.git/*.lock` files can appear when the folder is touched from a VM;
  `deploy.bat` clears them on Windows.

## 11. Working with others on this repo

- Petr runs a scheduled daily check that adds studies, authors and photos to
  Airtable and to his local working copy. Profile and photo files reach git
  only when he runs `deploy_all.bat`, and others may push to `main` at any
  time. Always `git pull` before starting work, keep commits
  small and focused, and let `deploy.bat` step 0 (`reconcile_with_origin.py`)
  merge; it stops on real conflicts instead of overwriting.
- Commit messages: plain, descriptive, no AI attribution trailers.
- Oliver signs off the science. Edge `Status` in Airtable (Proposed /
  Confirmed / Contested) records his review; agents never set it to
  Confirmed.
- External actions (posting on Bluesky, contacting researchers, registering
  accounts) are never done by an agent.

## 12. Useful references in this repo

`README.md`, `CONTRIBUTING.md`, `docs/TECH_SOLUTION_airtable.md`,
`atlas_skill/mtor-atlas-pipeline/SKILL.md` (original pipeline design, partly
historical), comments at the top of `deploy.bat` and `deploy_all.bat`.
