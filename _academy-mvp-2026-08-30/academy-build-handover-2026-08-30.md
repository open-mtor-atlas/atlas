# Academy MVP — built, verified, ready to apply

*2026-08-30. Implements `claude/academy-implementation-plan-2026-08-30.md` with the four decisions confirmed there. Built against a fresh clone of `open-mtor-atlas/atlas@main` (`9fcdd42`). Nothing was pushed — this session has read access to the repo but no push credentials.*

---

## 1. How to apply it

Deliverable: **`academy-mvp-source-2026-08-30.patch`** (143 KB).

```bash
cd <your atlas checkout>
git pull                                        # be on current main first
git apply --check academy-mvp-source-2026-08-30.patch   # dry run, should be silent
git apply        academy-mvp-source-2026-08-30.patch
```

The patch carries **only source and hand-baked files**. It deliberately does *not* carry the ~470 regenerated `study/`, `gene/`, `author/`… pages — `deploy.bat` regenerates those itself, and shipping them would have made the patch 1.6 MB of noise to review. `answers/` and `glossary/` **are** included, because `generate.py` is not part of `deploy.bat`.

Verified end to end: applied to a clean clone of `main`, then `build_academy.py` → `verify_academy.py` → `build_pages.py` → `validate_claims.py --strict` all pass, and the generated `academy/` tree comes out byte-identical to the one built here.

Then deploy normally with `deploy.bat`.

> **One manual step.** `deploy.bat` is not in its own `git add` list, and it aborts if it differs from `origin/main`. So before the first deploy:
> ```
> git add deploy.bat && git commit -m "deploy: build + verify Academy, stamp pathway assets" && git push
> ```
> Otherwise the very first run stops at the self-drift gate.

---

## 2. What was built

**5 pages**, real URLs, all statically pre-rendered:

| URL | What |
|---|---|
| `/academy/` | hero, "Your path" strip, three entry cards (Learn · Guided Routes · Research Challenges *coming soon*), first three lessons, bridge back into the Atlas |
| `/academy/core/` | the ten-lesson curriculum; 3 published, 7 listed as *in preparation* |
| `/academy/core/what-is-mtor/` | Lesson 01 — Foundation, 15 min |
| `/academy/core/mtorc1-vs-mtorc2/` | Lesson 02 — Core, 20 min |
| `/academy/core/rheb/` | Lesson 03 — Core, 25 min |

Every lesson runs Question → Core idea → Mechanism (inline SVG) → **What does the evidence say?** → Think → Go deeper → Next, with a sticky right rail that becomes a horizontal strip below 1000 px. Evidence cards are generated from `studies_baked.json` — the lesson file stores only SIDs, so **no study record is duplicated anywhere**. Four hand-drawn inline SVG diagrams; no library, no extra request, no cartoon biology.

Progress is one `localStorage` key (`atlas-academy-progress`) and a "Mark as read" button. No XP, no badges, no streaks.

### New files

```
build_academy.py                  the generator (imports build_pages.shell(), so one template)
verify_academy.py                 cross-layer integrity gate (see §4)
academy_data/lessons.json         3 lessons, IDs only
academy_data/modules.json         curriculum ordering
academy_data/_sid_to_lesson.json  reverse index, generated
academy/…                         5 generated pages
sitemap-academy.xml               generated
```

### Files changed — the complete list

| File | Change |
|---|---|
| `index.html` | **4 hunks, +23/−4.** One `<a class="tab tab-link" href="/academy/">Learn</a>` (an anchor, not a `data-tab` div, so `showView`/`applyHash`/`syncURL` were not touched at all), 2 lines of CSS for it, the additive `&route=` handling, and the re-stamped `PW_ASSET_V`. |
| `pathway/pathway.js` | `+12`: `PathwayApp.openRoute(id)` next to the existing `focusNode(name)`, same contract (returns `false` for an unknown id rather than blanking the panel). |
| `build_pages.py` | `SITE_TABS` += Learn; new `STATIC_TAB_URLS`; `shell()` gains optional `extra_css`/`extra_body` (empty by default, so every existing page renders byte-identically apart from the nav/footer line); `sitemap-academy.xml` in the sitemap index; an Academy section in `llms.txt` built *from* `academy_data` so it cannot drift; the "Learn the biology" block on study pages. |
| `generate.py` | Learn tab + Academy footer link for `/answers/` and `/glossary/`. Also fixed an existing drift: those pages linked the JS-only `#view=about` while every other static page linked `/about/`. |
| `validate_claims.py` | new `check_academy()` — R5 (absolute language) at ERROR level and R3 (mechanistic work described as clinical evidence) over lesson prose, inside the same `--strict` gate. |
| `reconcile_with_origin.py` | `academy/`, `sitemap-academy.xml`, `_sid_to_lesson.json` registered as generated-wholesale. |
| `deploy.bat` | build + verify Academy **before** `build_pages.py`; `academy` and `academy_data` in the folder `git add` loop; `sitemap-academy.xml` in the sitemap loop; the new scripts in the script loop; **and `stamp_pathway_version.py`** — see §3. |
| `deploy.sh` | same build + verify step, same `git add` additions. |
| `llms.txt`, `sitemap.xml`, `answers/`, `glossary/` | regenerated output of the above. |

---

## 3. Two things found along the way

**`deploy.bat` never ran `stamp_pathway_version.py`.** `deploy.sh` has always run it; `deploy.bat` — the supported Windows path — did not. That script writes a content hash of `pathway.js` / `pathway.css` / `model.json` / `contexts.json` into `PW_ASSET_V`, which the loader appends as `?v=`. Without it, a Windows deploy ships a new `pathway.js` on the same URL and the CDN and browser keep serving the old one. That is exactly the failure the script was written for after the Phase 1 incident — and this release changes `pathway.js`, so it would have bitten on the first deploy. Added to `deploy.bat`, and the hash is already re-stamped in the patch.

**A pre-existing console error, not a regression.** `#view=map` logs `<svg> attribute viewBox: Expected number, "112.0 -Infinity 1376.0…"`. Verified against unmodified `main`: it was already there. Harmless in practice (the map renders), but it is a real bug in the pathway camera code when it fits an empty bounding box, and worth a separate look.

---

## 4. Verification

Every deploy gate, on the built tree:

```
build_academy.py          OK      verify_prerender.py         OK
verify_academy.py         OK      verify_index_html.py        OK
build_pages.py            OK      validate_claims.py --strict OK
generate.py               OK      check_tier_palette --strict OK
                                  validate_pathway.py --strict OK
                                  pathway/smoke_test.js       OK  (2699/2699)
```

`verify_academy.py` is new, and it is the piece that keeps this honest over time. Lessons reference four independently-changing layers at once — study SIDs, entity pages (which only exist above the 3-study threshold), open-question slugs, guided-route ids. It checks all of them, plus prev/next chain consistency against `modules.json`, plus that every internal link resolves to a file that exists, plus that each page carries its `<h1>` and its Evidence section **in static HTML**, plus editorial minima (≥3 studies, ≥1 Think question, uncertainty named). Negative-tested: injecting a bad SID, an entity below threshold, a bad route id, a broken chain and a stray `<div>` produced 7 findings and a non-zero exit.

The claim gate earned its keep immediately — it rejected my own sentence *"the least settled part of the field"* (R5, `settled`) in Lesson 01. Reworded to "where the evidence is thinnest".

Browser regression (Chromium, live pages):

- all 8 existing SPA tabs still switch and show their view;
- `#view=studies&tier=B&page=2` still restores state; back/forward unaffected;
- **`#view=map&pw=guided` behaves exactly as before** (opens on the first route) — no existing URL changed;
- `&route=rapa` / `&route=gf` / `&route=aa` each select that route; `&route=nope` falls back to the default rather than blanking;
- no horizontal overflow at 390 / 768 / 1000 / 1280 px;
- no new console errors.

---

## 5. Deliberately not done

AI tutor · badges/XP · certificates · adaptive learning · experiment builder · research notebook · knowledge-graph visualisation · hypothesis management · Research Challenges (homepage card only, disabled) · lessons 04–10 (listed in the curriculum, marked *in preparation*).

Also worth knowing: the static layer has no dark theme (only the SPA does), so Academy pages are light-only like every other static page. Consistent, but it is a real difference from the SPA.

## 6. Adding lesson 04 later

Write the lesson into `academy_data/lessons.json`, flip its `status` to `published` in `modules.json`, fix the `previousLesson`/`nextLesson` on its neighbours, run `build_academy.py` and `verify_academy.py`. Nothing else — no new page file, no template edit, no nav change, no deploy change.
