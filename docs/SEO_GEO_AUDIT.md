# SEO & GEO Audit — Oliver's mTOR Atlas (mtor-atlas.org)
*2026-08-23. Audit performed by direct inspection of the live site, the GitHub repository (`open-mtor-atlas/atlas`, branch `main`), and Petr's Google Search Console (`sc-domain:mtor-atlas.org`). Builds on, and in places corrects/extends, the 2026-08-22 audit and next-steps notes already in this project.*

## 1. Executive summary

The Atlas is not an SEO-neglected site that needs to be bolted onto — it already has an unusually GEO-literate technical foundation for a project this size: a sitemap index across six sub-sitemaps, a `robots.txt` that explicitly welcomes AI crawlers ("the point of this site is to be cited"), a full static pre-rendered layer (`study/`, `gene/`, `drug/`, `disease/`, `process/`, `complex/`, `organelle/`, `nutrient/`, `outcome/`, `intervention/`, `author/`, `question/`, `answers/`, `glossary/`, `browse/` — 383 URLs) alongside the JS single-page app, and Schema.org structured data (Dataset, ScholarlyArticle, DefinedTerm, FAQPage, BreadcrumbList, Person, CollectionPage) already wired into the page generator. Answer-first content (10 `/answers/` pages targeting real search queries) and a 25-term `/glossary/` shipped to production earlier today (2026-08-23).

The real constraint is not technical debt, it's youth: 74 of 397 pages indexed, 0 confirmed external backlinks in GSC as of this morning, and near-zero organic clicks (~15/28 days). Google's own classification of the other 269 pages — 255 "Discovered — currently not indexed," only 10 "Crawled — currently not indexed," 3 redirect, 1 404 — is the textbook signature of a new, correct, low-authority site, not a broken one. Nothing in this audit found a structural reason Google or an AI crawler can't read the content; the leverage is authority (backlinks, citations) and finishing the content formats that are closest to done.

One real, low-risk defect was found and fixed during this audit (see §17): a stale "about 275 studies" string baked into 324 pages' structured data, left over from an earlier correction that only touched the human-visible meta description, not the Dataset JSON-LD. Everything else below is graded by priority, not implemented, per your instruction to design bigger changes before touching them.

## 2. Current strengths (do not touch these)

- **`robots.txt`** already allow-lists Googlebot, Google-Extended, Bingbot, GPTBot, OAI-SearchBot, ChatGPT-User, ClaudeBot, Claude-Web, anthropic-ai, PerplexityBot, Perplexity-User, CCBot, Applebot and Applebot-Extended, with a comment explaining why. This is more deliberate GEO posture than most funded startups have.
- **Sitemap index** (`sitemap.xml` → `sitemap-{home,studies,entities,questions,authors,answers}.xml`) is correctly structured and current (all six sub-sitemaps last-modified today).
- **Static pre-rendered layer exists specifically because JS crawlers can't see the SPA** — this is the right architecture, already built, not a proposal. 322 study pages, 45 entity pages (above the 3-study quality gate; another 75 entities were correctly *withheld* for having too few studies — see §12), 10 question pages, 5 author pages, browse index, answers, glossary.
- **Schema.org coverage is broader than a typical audit finds already in place**: Dataset (site + nested `isPartOf` refs), ScholarlyArticle with DOI/PMID as `PropertyValue`, Person for authors, DefinedTerm/DefinedTermSet for glossary, FAQPage for answers, BreadcrumbList (both JSON-LD and a *visible* `<nav class="crumb">` — many sites only do one or the other), CollectionPage for `/browse/`.
- **Answer-first structure already matches the format you specified in §5** of your brief: each `/answers/` page leads with a direct 1-2 sentence answer as the FAQPage `acceptedAnswer` text, before any evidence breakdown.
- **E-E-A-T signal that's rare and valuable, not a liability**: every study page footer reads "Curated by Oliver Barton, Prague" — a named, real human curator, not an anonymous "editorial team." Combined with the evidence-tier system (A–D, explicitly defined as study type, not a quality score — see the tier-palette convention in the codebase) and per-claim DOI/PMID/PMC-full-text links, this is exactly the transparent-methodology posture that offsets "built by a high schooler" as a trust concern rather than amplifying it, provided it stays explicit rather than implied (see §14).
- **`llms.txt`** exists and is genuinely useful, not a checkbox — it links directly to the answers index, each answer page, and the glossary, in the format an LLM would actually want.
- **Internal linking on generated pages** is real, not decorative: study pages link to related entity pages, entity pages back to their studies, and every generated page shares a top nav + footer (with links to the SPA, `/browse/`, `/answers/`, `/glossary/`, GitHub) that was retrofitted across all 373 pre-existing static pages as of today's deploy.

## 3. Current weaknesses

- **Authority is at zero.** GSC's Links report shows 0 external links and, as of this morning, 0 internal links (the latter is very likely a reporting lag after today's nav retrofit, not a real internal-linking gap — see §5). This is the dominant constraint on everything else in this report.
- **A stale fact was replicated 324 times.** The Dataset JSON-LD description ("about 275 studies") had drifted behind the real count (322) and, because it's a shared literal, was baked into every study page's `isPartOf` block plus `/browse/` and the homepage — see §17 for the fix already applied.
- **The homepage (`index.html`) is 3.5 MB.** It's a single self-contained SPA with the full studies/gaps/events/author-bio corpus embedded as JSON, which is why the static layer had to be built in the first place — but it also means any human visitor who lands on `/` directly (as opposed to a `/study/…` or `/answers/…` deep link from search) is downloading a multi-megabyte page. This has not been measured against Core Web Vitals thresholds (see §4).
- **No visible "last updated" / freshness signal** on generated pages beyond the sitemap's `lastmod` — the page footer doesn't show `dateModified`, and `write()` in `build_pages.py` deliberately omits a build date to avoid diffing every page on every deploy (a good reason, but it means there's no freshness signal for a *human* reader either, only for crawlers reading the sitemap).
- **Author coverage: 5 of ~488 have a static page — but 46 already have a complete, ready-to-publish bio.** *(Corrected 2026-08-23 — see §21; the original wording here understated this.)* `index.html`'s `AUTHOR_BIOS` object — the same data that powers the Top-5 bio modal — actually holds full profiles (role, institution, narrative bio, study-milestone timeline, photo for 43 of them) for 46 researchers, confirmed by direct inspection, including Zoncu and Shaw from your brief's named list. Only Brunet, of the names you gave, is genuinely absent and needs new content written. The other 41 aren't a writing gap at all: `build_pages.py` builds static `/author/` pages from `atlas_data/author_bios_baked.json`, a manual snapshot of `AUTHOR_BIOS` that was taken once (2026-08-04, at 5 profiles) and never retaken as the other 41 were added straight into `index.html`. Re-exporting that snapshot and re-running `build_pages.py` would turn 41 already-written bios into 41 new static, crawlable pages with no new research or writing required.
- **No topic-level synthesis pages.** Entity pages (`/gene/rheb/`, `/drug/rapamycin/`) and answer pages (`/answers/…`) exist, but nothing sits at the "aging," "autophagy," or "cancer" level to aggregate across entity types the way a topic hub would — this is a genuine content-architecture gap, not just a missing URL (see §6, §13).
- **The site has not yet been benchmarked on PageSpeed Insights / Core Web Vitals** at all — not a known problem, an unknown.

## 4. Technical SEO audit

| Item | Status | Notes |
|---|---|---|
| `robots.txt` | ✅ Good | See §2. No disallow rules block anything that should be crawled. |
| `sitemap.xml` | ✅ Good | Correct sitemap-index format, 6 sub-sitemaps, all current. |
| Canonical URLs | ✅ Good | Every generated page has a self-referential `<link rel="canonical">`; legacy-slug redirect stubs (see `LEGACY_SLUGS` in `build_pages.py`) also carry a canonical to the current URL. |
| Indexability / noindex | ✅ Good | `<meta name="robots" content="index, follow">` present on homepage and generated pages; no accidental noindex found. |
| Redirects | ⚠️ Minor | GSC reports 3 pages in "page with redirect" status — worth a one-time URL Inspection check to confirm they're the intended legacy-slug stubs and not something else. |
| HTTP status codes | ⚠️ 1 known 404 | GSC reports exactly 1 URL as 404 — worth identifying and fixing/redirecting (quick check, not yet done in this audit). |
| Duplicate URLs / trailing slash | ✅ Good | Directory-style URLs (`/answers/rapamycin-lifespan-humans/`) are consistent throughout; no `.html`-vs-directory duplication observed. |
| Pagination | N/A | No paginated listings currently (browse is a single flat index). |
| Internal linking | ✅ Good, see §11 | Real, not decorative — but not yet measurable in GSC (0 reported, likely a post-deploy lag). |
| Crawl depth / orphan pages | ⚠️ Not fully verified | Every generated page links back to `/browse/`, and `/browse/` links to (most) entity/study pages — a full orphan sweep against the sitemap's 384 URLs vs. `/browse/`'s outbound links was not run in this pass; recommended as a P1 script (see §16). |
| JS rendering vs. static HTML | ✅ Good | This is the whole point of the static layer — solved, not a gap. |
| Core Web Vitals / page speed | ❌ Unknown | Never benchmarked. The 3.5 MB homepage is a real candidate for a poor LCP on the SPA specifically; generated pages are lightweight single-purpose HTML and unlikely to have the same issue. **Recommend running PageSpeed Insights on both `/` and a representative `/study/…` page** — this needs either API access this session doesn't have, or five minutes in a browser; flagged as next action, not run. |
| Image optimization | ⚠️ Minor | `og-image.png` is ~196 KB, reasonable for a fixed OG asset. The homepage embeds ~92 base64 images inline (author photos, entity icons) — contributes directly to the 3.5 MB size; worth an audit of whether all 92 need to be inline vs. referenced. |
| Title tags | ✅ Good | Descriptive, not clickbait, consistent `{Page topic} | Oliver's mTOR Atlas` pattern (matches your own §11 examples almost exactly already). |
| Meta descriptions | ✅ Good | Present, specific, within reasonable length on every page type checked. |
| H1/H2 hierarchy | ✅ Good | One H1 per page, structured H2 sections (At a glance / Abstract / Extracted findings / Related topics on study pages). |
| Open Graph | ✅ Good | Full set (`og:type`, `site_name`, `title`, `description`, `url`, `image` + dimensions, `locale`) on homepage; `answers/` pages have title/description/url/image but are missing `og:type=article`'s width/height pair — trivial gap. |
| Twitter/X cards | ✅ Good | `summary_large_image` present site-wide. |
| hreflang | N/A | English-only site by deliberate project decision — correctly not implemented. |
| Favicon / site identity | ✅ Good | `favicon.png`, `apple-touch-icon.png`, `theme-color`, consistent wordmark across SPA and static pages. |
| Structured data | ✅ Strong, see §10 | |

## 5. Indexation audit (Google Search Console, verified live 2026-08-23)

- **Indexed: 74. Not indexed: 269** (unchanged from yesterday's check — expected, this moves on a weeks timescale, not a daily one).
  - 255 "Discovered — currently not indexed" — Google knows the URL from the sitemap but hasn't prioritized crawling it yet. This is an authority problem, not a technical one (see §3, §15).
  - 10 "Crawled — currently not indexed" — Google visited and chose not to index; on a evidence-graded near-duplicate-template site like this, worth spot-checking whether any of the 10 are genuinely thin (e.g., a Tier-D entity page with only the 3-study minimum) versus just unlucky in the queue.
  - 3 "Page with redirect," 1 "Not found (404)" — small, fixable (§4).
- **Links report: 0 external, 0 internal**, checked live this morning. External-0 matches the backlink campaign's current stage (posts/edits sent, not yet crawled-and-counted by Google, which lags real-world link placement by days to weeks even after a page is indexed). Internal-0 is almost certainly a reporting lag following today's site-wide nav/footer retrofit landing on all 373 static pages — GSC's internal-links count is one of its slower-to-refresh reports. Recommend re-checking in ~1-2 weeks rather than treating this as a real gap; if it's still 0 then, that would be a genuine anomaly worth investigating.
- **Structured data**: 2 valid Datasets, 1 valid navigation structure, 0 errors, per GSC's Enhancements view (checked 2026-08-22, structurally unchanged since).

## 6. Information architecture

Current URL scheme is already close to ideal and matches almost exactly what you sketched:

```
/                          SPA (home)
/browse/                   flat human-readable index (CollectionPage)
/study/<SID>/               322 pages — ScholarlyArticle
/gene/<slug>/                19 pages
/drug/<slug>/                 5 pages
/disease/<slug>/              5 pages (renal-cell-carcinoma, breast-cancer, Alzheimer's, TSC)
/process/<slug>/              9 pages (autophagy, protein-synthesis, cellular-senescence, …)
/complex/<slug>/               4 pages
/organelle/<slug>/             2 pages
/nutrient/<slug>/              3 pages
/outcome/<slug>/                3 pages (longevity, insulin-resistance, immune-function)
/intervention/<slug>/           2 pages
/condition/<slug>/              2 pages
/author/<slug>/                 5 pages (Top-5 only; 46 bios already exist in index.html — see §21)
/question/<slug>/              10 pages (knowledge-gap hypotheses, long descriptive slugs)
/answers/<slug>/                10 pages + index (FAQPage, answer-first)
/glossary/                      1 page, 25 terms (DefinedTermSet)
```

This is not the doorway-page architecture your brief warns against — every entity page passed a real quality gate (≥3 studies; 75 candidate entities were deliberately withheld for having fewer). The one structural gap is a **topic layer above entities** (`/topic/aging/`, `/topic/autophagy/`, `/topic/cancer/`) that your brief also names. Recommendation: **do not build this as a new generated page type from `build_pages.py` yet** — a topic page that just re-lists the same entities/studies with no new synthesis would be exactly the thin/duplicate content your constraints warn against. It only earns its place if it does something the entity pages can't: synthesize across entity types (e.g., "aging" = longevity outcome + autophagy process + rapamycin/everolimus drugs + cellular-senescence + relevant Tier A/B studies) with real editorial framing, similar to what an `/answers/` page already does for a single question. Treat this as a P2 content project, not a P0/P1 technical task — see §13.

Question-page slugs are long, hypothesis-style sentences (e.g. `/question/is-autophagy-actually-required-for-the-mammalian-lifespan-benefit/`) rather than short keyword slugs — this is fine for uniqueness and matches natural-language search/AI-query phrasing well, but is worth being aware of if you ever want a shorter canonical slug convention; **do not rename existing slugs** without adding the old one to `LEGACY_SLUGS` (build_pages.py is explicit that renaming silently breaks inbound links, which is the one thing this project can least afford right now).

## 7. Keyword / search-intent map

Grounded in what the corpus actually supports (not generic volume-chasing), cross-referenced against existing pages:

| Category | Intent | Existing coverage | Gap / opportunity | Priority |
|---|---|---|---|---|
| mTOR general / "what is mTOR" | Informational, beginner | `/answers/what-is-mtor/`, `/gene/mtor/` | Well covered | — |
| mTOR pathway overview | Informational | SPA Pathway tab (not statically rendered) | A static `/pathway/` overview page would help both SEO and GEO — currently pathway map is JS-only | P1 |
| mTORC1 / mTORC2 | Informational, comparison | `/complex/mtorc1/`, `/complex/mtorc2/`, `/answers/mtorc1-vs-mtorc2/` | Well covered | — |
| Rapamycin | Informational, branded | `/drug/rapamycin/`, 3 answer pages | Well covered | — |
| Rapamycin + aging/longevity | High-intent, competitive (geroevidence.com, progevita.com rank here per 2026-08-22 competitor check) | `/answers/rapamycin-lifespan-humans/`, `/outcome/longevity/` | Strongest page (`rapamycin-lifespan-humans`) should be a primary backlink/PR target — see §15 | P0 (promote, don't build) |
| mTOR + cancer | Informational/clinical | `/answers/mtor-cancer-connection/`, `/disease/breast-cancer/`, `/disease/renal-cell-carcinoma-rcc/` | Reasonable coverage; no dedicated "mTOR inhibitors in cancer treatment" synthesis page | P2 |
| mTOR + autophagy | Informational | `/process/autophagy/`, `/answers/autophagy-required-lifespan/` | Well covered | — |
| mTOR + metabolism | Informational | `/gene/ampk/`, various | Thin — no outcome page dedicated to metabolic effects broadly | P2 |
| mTOR + exercise/muscle | Informational | `/process/muscle-growth/` | Single entity page, 3-study minimum — genuinely thin corpus, don't force more content here yet | — (data-limited) |
| mTOR + nutrition | Informational | `/nutrient/` (3 entities), no answer page | Real gap if the corpus supports it — check study count before committing | P2 |
| mTOR + diabetes | Clinical | `/outcome/insulin-resistance/` | No dedicated diabetes disease page | P3 (check corpus depth first) |
| mTOR + immune system | Informational | `/outcome/immune-function/` | Reasonable | — |
| mTOR + disease (general) | Informational | `/disease/` (5 pages) | Reasonable given corpus size | — |
| mTOR drugs/inhibitors (list) | High-intent | `/answers/mtor-inhibitors-list/` | Strong answer-first page already targets this exact query pattern | — |
| Specific drugs (everolimus, temsirolimus…) | Branded | `/drug/everolimus/`; **no `/drug/temsirolimus/`** despite being named throughout your brief and in Atlas data conventions | Verify study count; add if ≥3 | P2 |
| Specific genes/proteins | Informational | 19 gene pages, strong coverage (Raptor, Rictor, Rheb, TSC1/2, S6K1, 4E-BP1, AMPK, PI3K, AKT, ULK1, TFEB, Rag GTPases, etc.) | Well covered | — |
| Specific researchers | Branded/authority (GEO-relevant — AI systems cite named-entity pages) | 5 author pages published; 46 bios already written (§21) | Not a content gap, a publishing gap — re-export + rebuild adds 41 pages for free; only Brunet genuinely needs a new bio written | P1 (cheap) |
| Specific papers | Informational, citation | 322 study pages | Well covered | — |
| Clinical trials | Informational | Referenced inline (e.g. NCT numbers in study data) but no dedicated `/trial/` page type | Real gap only if corpus has enough registered-trial-linked studies to clear the 3-item quality gate | P3 |
| Negative/null results | Differentiator (nobody else does this well) | Present within study pages' extracted findings, not surfaced as its own page/filter | High-uniqueness, low-effort opportunity — see §13 | P1 |
| Open research questions | Differentiator | 10 `/question/` pages | Well covered, could grow as gap-finder adds more | — |

## 8. GEO / AI visibility analysis

**Why should an AI system cite mTOR Atlas specifically?** Because it is one of very few sources that states, per claim, which evidence tier (A–D) it rests on, links the primary DOI/PMID, and is structured so an LLM doesn't have to infer any of that from prose. That is a genuinely differentiated GEO position — most competing content (including the geroevidence.com/progevita.com pages currently ranking for "does rapamycin extend lifespan in humans," per the 2026-08-22 competitor check) states conclusions without this scaffolding.

What's already in place for GEO specifically: `llms.txt` pointing directly at the answer pages; FAQPage schema with the direct-answer text as the `acceptedAnswer`; the "answer-first" paragraph structure your brief specifies is already the actual template; `robots.txt` explicitly allowing every major AI crawler; static HTML so non-JS-executing crawlers (GPTBot, PerplexityBot, ClaudeBot, CCBot) see full content, not an empty shell.

What would move the needle further, roughly in order of leverage:

1. **Backlinks/citations are the single biggest GEO lever right now**, same as for classic SEO — AI answer engines weight citation graphs and cross-references heavily, and the Atlas currently has none that Google has counted yet. This is already the active workstream (§15) and should stay P0.
2. **A visible `dateModified`/"last verified" stamp** on answer and study pages would help AI systems trust freshness signals, which they weight for medical/health content specifically.
3. **Testing actual citation behavior** — the 2026-08-22 notes correctly flag that nobody has yet checked whether Perplexity/ChatGPT search/Gemini currently surface the Atlas for test queries like "does rapamycin extend lifespan in humans." This is a fast, free, high-information check that wasn't re-run in this pass — recommended as a next action (§20).
4. **The methodology article** (proposed 2026-08-22, not yet written) — a self-contained piece explaining evidence-tiering and gap-finding as a system, independent of mTOR content — is exactly the kind of content GEO-savvy audiences (r/slatestarcodex-adjacent, rationalist science communicators) cite and share on its own merits, which compounds both backlinks and AI-citation graph presence. Still P1, still not started.
5. **Named-author pages are also a GEO asset**, not just an SEO one — AI systems increasingly resolve entities (researchers) and prefer sources that correctly attribute claims to real named people. The 5-of-488 author-page coverage gap in §3 has a GEO dimension, not just an SEO one — and per the §21 correction, closing 41 of those pages is a rebuild, not a research project, which makes it unusually cheap GEO leverage.

## 9. Knowledge graph strategy

The relationship types your brief specifies are largely already expressed, just not always as an explicit typed edge:

- **Study → targets/affects → Entity**: expressed via each study page's "Related topics"/"Related entities" links (built from the Airtable Entities relation) — real, but implicit in HTML links rather than an explicit `about`/`mentions` JSON-LD property.
- **Study → provides → Evidence Tier**: explicit, both visually (tier badge) and in the "At a glance" table — not yet in structured data as a formal property (ScholarlyArticle has no standard "evidence tier" field in schema.org; this would need a custom `additionalProperty` or a `PropertyValue`, which is a reasonable P2 addition).
- **Author → authored → Study**: expressed on author bio pages (5 published; 46 already written — §21) via the study-milestone timeline; not yet expressed as a reciprocal link/schema on the studies whose authors don't yet have a *published* bio page.
- **Drug → inhibits → Complex, Complex → regulates → Process, Protein → activates/inhibits → Complex**: this is exactly what the "Mechanism Explorer" (Airtable Relations table, 43 signed evidence-graded edges, per project memory) already models — it currently powers an in-SPA tab, not the static pages. **Exposing a subset of these 43 signed relations as explicit `about`/`mentions` links or a lightweight `PropertyValue` block on the relevant entity pages is a concrete, scoped P1/P2 project** — the data exists, it just isn't surfaced outside the JS-only Mechanism tab yet.
- **Disease → associated with → Pathway**: expressed via disease pages' related-entities links.

**Recommendation, not yet implemented**: rather than inventing new relationship types, the highest-value next step is surfacing the already-curated 43 Mechanism-Explorer edges on the relevant static entity pages (as visible "regulates / inhibited by / activates" cross-links plus a matching JSON-LD `about` array) — real knowledge-graph SEO value with zero new data curation required. Flagged as P1 in §16, intentionally not built during this audit pass since it touches `build_pages.py`'s page-generation logic for entity pages and deserves its own design/testing pass rather than being rushed in.

## 10. Structured data strategy

Already implemented and validated (0 GSC structured-data errors): `Dataset` (site + nested refs), `ScholarlyArticle` (with `PropertyValue` for DOI/PMID), `Person`, `DefinedTerm`/`DefinedTermSet`, `FAQPage`, `BreadcrumbList`, `CollectionPage`, `Organization`.

Recommended additions, not yet implemented (all P2 — real but not urgent, and each needs its own care to avoid Google's "doesn't match visible content" rejection):

- **`MedicalCondition`** or `MedicalEntity` typing (schema.org's medical vertical) for `/disease/` and `/condition/` pages, layered *alongside* the existing generic entity markup, not replacing it — Google is stricter about validating medical schema against visible content, so this should be a deliberate, tested addition, not a bulk find-replace.
- **`ScholarlyArticle.citation`** cross-links between study pages that cite each other (data may already exist implicitly via shared entity tags; would need a real "cites/cited by" relation, which doesn't currently exist in the Airtable schema — a data-modeling question before a technical one).
- **`sameAs`** on author pages linking to ORCID/PubMed author pages where verifiable — your brief is right to caution "never invent" here; this needs to be done per-author from verified sources, not templated.
- **Explicit `dateModified`** on generated pages, tied to the real content-change (not build) date — would need a small schema change to `studies_baked.json`/`entities_baked.json` to track a genuine last-changed timestamp per record, since `write()`'s change-detection currently only decides *whether* to write, not *when* the underlying fact last changed.

Not recommended: `WebSite`'s `SearchAction` (no working on-site search endpoint to point it at), `Organization` beyond what already exists (the project is correctly *not* claiming institutional affiliation it doesn't have — see §14).

## 11. Internal linking strategy

Already real and bidirectional at the study↔entity level (§2). The one measurable gap: **question pages and answer pages don't yet cross-link each other** even where they clearly should — e.g. `/answers/autophagy-required-lifespan/` and `/question/is-autophagy-actually-required-for-the-mammalian-lifespan-benefit/` cover overlapping ground but (based on the templates inspected) aren't linked to each other. This is a same-day, low-risk fix once scoped properly, but touches two different generator code paths (`generate_answers.py`-equivalent and `build_pages.py`'s question-page function) so it's listed as P1 rather than implemented live in this pass.

Also worth a scripted orphan-check (§4) rather than manual spot-checking, given 384 URLs.

## 12. Programmatic SEO opportunities

Your brief is right to warn against thin/doorway pages, and the codebase already enforces this correctly: `PAGE_THRESHOLD = 3` studies minimum before an entity gets its own page, with 75 candidate entities currently and deliberately below that bar. That ceiling (~40-70 defensible entity pages, already noted in prior project analysis) has essentially been reached — **the remaining programmatic-SEO upside is not "more entity pages," it's deepening the pages that already exist**:

- **Author pages beyond the Top 5** — not "in principle": for 46 researchers this content (institution, role, narrative bio, milestone timeline) has already been written and lives in `index.html`'s `AUTHOR_BIOS`, just never re-exported to the static-page pipeline (§3, §21). Publishing those 41 additional pages is close to zero new curation cost; only Brunet, among the researchers named in your brief, would need real new content.
- **A "negative/null results" filtered view** — the data exists inside study pages already; a dedicated page/section surfacing "what didn't work" is close to zero new curation cost and directly matches "what's uncertain" — a section type your brief explicitly names in §5 and one almost no competing site does. High uniqueness, low build cost — good P1 candidate.
- **Clinical-trial-linked study pages**, if enough NCT-registered studies exist in the corpus to clear a quality gate — not yet counted in this pass.

Explicitly **not** recommended: generating pages per intervention-dose combination, per single-study "mini pages," or any entity below the 3-study gate — this is exactly the "scaled content abuse" risk your brief and the project's own prior analysis (phase6-discoverability memory) both flag.

## 13. Content gaps

1. **Topic-level synthesis pages** (aging, autophagy-as-a-topic, cancer) — see §6. Real gap, needs editorial synthesis work, not a template change.
2. **Methodology article** explaining evidence-tiering/gap-finding as a system — proposed 2026-08-22, not written. Doubles as GEO content (§8) and link-bait (§15).
3. **Publish the 41 already-written author bios beyond Top 5** (Zoncu, Shaw, and 39 others already have full content in `index.html` — §3, §21); separately, write one new bio for Brunet, the only named researcher genuinely missing content.
4. **A static `/pathway/` overview page** — the pathway map is currently JS-only inside the SPA; a static equivalent would close a real gap in your brief's §3 URL list.
5. **Comparison pages** proposed 2026-08-22 ("rapamycin vs. everolimus") beyond the one that already shipped (`rapamycin-vs-metformin`) — good template already proven, straightforward to extend if corpus supports it.
6. **A "what's uncertain" negative-results view** — see §12.

## 14. E-E-A-T / scientific trust

This is the area where the project's actual posture is *better* than a typical audit finds, and the main risk is regression, not absence. Already in place: named curator ("Curated by Oliver Barton, Prague") on every study page footer; per-claim DOI/PMID/PMC links; an explicit evidence-tier system defined as *study type*, not a quality score (deliberately, to avoid the Tier-D-looks-like-bad-science trap — documented in the codebase's own CSS comments); epistemic-calibration badges distinguishing fact/interpretation/hypothesis (per project history); an "Editorial policy" section (per project history, not re-verified line-by-line in this pass).

What's genuinely missing and matches your brief's explicit call-out: a clear, dedicated **"About / Methodology / Who curates this"** page is referenced from the footer nav (`/#view=about` inside the SPA) but has no static, crawlable equivalent — an AI system or a skeptical human landing on a `/study/…` or `/answers/…` page from search has no static link to a page explaining who Oliver is, why a high-schooler's evidence grading should be trusted, what the correction/changelog policy is, or how to contact the project. **This is the single highest-leverage E-E-A-T fix available and it's a documentation task, not a technical one** — flagged as P1, not attempted in this pass because it requires real editorial content (how the project wants to frame "built by a student, reviewed against primary literature" honestly) rather than a template change.

Also missing: a visible correction/changelog log (project history shows an internal `AUDIT_scientific_calibration_2026-07-29.md` and external-review process exist, but nothing public-facing summarizes "here's what we've corrected and when" — this is exactly the kind of transparency that turns "built by a student" from a liability into a differentiator, per your brief's own framing).

## 15. Link acquisition strategy

Already active (per project memory, verified against GSC showing 0 counted-so-far, which is expected lag, not failure): Zenodo DOI (done), re3data.org (submitted, in review), FAIRsharing.org (submitted, in review), Reddit (r/Rapamycin, r/Biohackers, r/immortalists, r/PeterAttia — posted), Wikipedia (Talk:MTOR, Talk:Sirolimus — posted, awaiting editor response), bioRxiv preprint (submitted, screening ~72h). This audit did not duplicate that work; see `seo-geo-audit-2026-08.md` project memory for full status and don't re-send anything already in flight.

New targets not yet in any prior plan, worth prioritizing once the current backlog resolves:
- **Lifespan.io** — named in 2026-08-22 notes, not yet actioned.
- **Google Scholar / Semantic Scholar profile** — blocked on the bioRxiv DOI landing (in progress).
- **The "student built an AI research tool" media angle** — genuinely has legitimate news value (Root.cz, Živě.cz, iROZHLAS věda domestically; Freethink-type outlets internationally) and would produce editorial backlinks in a different trust tier than forum posts. Not actioned yet, deliberately — this is a decision for Petr/Oliver about how much attention they want, not something to auto-send.
- **SOČ / Regeneron ISEF-style competitions** — institutional backlink category, separate from PR.
- **Product Hunt launch** — different audience than Hacker News, self-promotion norms are more permissive there.

## 16. Prioritized roadmap

**P0 — critical**
- Fix the "about 275 studies" Dataset description drift across 324 pages. **Done — see §17.**

**P1 — high impact**
- Continue the active backlink campaign (§15) — highest-leverage lever for the 255 "discovered, not indexed" pages; already in motion, just needs to keep moving.
- Write the methodology article (proposed 2026-08-22) — doubles as GEO content and natural link-bait.
- Build a static "About / Methodology / Curator" page with a real, honest framing of the project and its provenance (§14).
- Publish the 41 author bios that already exist in `index.html` but were never re-exported to static pages (§3, §21) — cheap, high-leverage, mechanical; separately, write one new bio for Brunet.
- Surface the 43 curated Mechanism-Explorer relations on relevant entity pages, with matching structured data (§9).
- Cross-link overlapping `/answers/` and `/question/` pages (§11).
- Run PageSpeed Insights on `/` and a representative static page; act on findings only if they show a real Core Web Vitals problem (§4).
- Test current AI-search citation behavior (Perplexity/ChatGPT search/Gemini) for 5-10 representative queries (§8, §20).
- Build a "what's uncertain / negative results" view (§12, §13) — high uniqueness, low build cost.

**P2 — medium impact**
- Add `/drug/temsirolimus/` and other named drugs if corpus depth clears the quality gate.
- Extend comparison pages (rapamycin vs. everolimus, etc.) if data supports it.
- Add `MedicalCondition`/`sameAs`/`dateModified` structured-data enhancements (§10), each carefully tested individually.
- Build topic-level synthesis pages (aging, autophagy, cancer) as genuine editorial pieces, not database re-listings (§6, §13).
- Static `/pathway/` overview page.

**P3 — nice to have**
- Clinical-trial-linked pages, if corpus supports a real quality gate.
- Diabetes/metabolism disease pages, if corpus supports it.

## 17. Changes already implemented (this session)

**Fixed a stale fact baked into structured data across the site.** The Dataset JSON-LD `description` field said "about 275 studies" — accurate when written, stale now that the corpus has grown to 322 (the human-visible meta description had already been updated to "322+" at some point, but the separate JSON-LD literal in `build_pages.py`'s `DATASET_REF` constant was missed). This string was replicated into every one of the 322 static study pages plus `/browse/`, because they all embed a nested `isPartOf` reference to the Dataset.

What was done, in order, each step independently verified before moving to the next:
1. Edited the one literal in `build_pages.py` ("about 275" → "over 320"), verified with `py_compile` and a fresh re-read confirming exactly one changed line.
2. Re-ran `build_pages.py` (the project's own tested regeneration script, which only rewrites a file if its content actually changed) — 323 files updated (322 study pages + `/browse/`), 68 unchanged (entity/question/author pages don't reference this field), 0 unrelated files touched. Confirmed via `git diff --stat`: exactly `build_pages.py` + 324 static pages, each a single-line diff, nothing else.
3. Separately fixed the same stale string in `index.html`'s own Dataset block (the homepage isn't generated by `build_pages.py`), using the project's documented safe-write procedure for this specific file (chunked write with `os.write`/`fsync`, independent fresh re-read, exact byte-length check, tail check for `</html>`, and a `git diff` limited to the single intended line). Also ran the repo's own `verify_index_html.py`, which passed.

**Nothing was committed or pushed.** Per the project's own operating rules (documented in project memory — deploys run from Petr's machine only, via `deploy.bat`, which carries its own verification gates), these are working-tree changes waiting for review. `git status` currently shows this fix plus two pre-existing untracked files (`AGENTS.md`, a `build_pages.py` backup) that predate this session and weren't touched. **To ship it: review `git diff`, then run `deploy.bat` as usual.**

## 18. Changes intentionally NOT implemented, and why

Per your own instruction ("bigger architecture changes: design and document first, don't just implement") and the project's documented history of this exact repository silently corrupting large files on write, this audit deliberately stopped short of:

- **Any change to entity/question/answer page templates** (cross-linking, Mechanism-Explorer surfacing, new structured-data fields) — each touches `build_pages.py`'s page-generation logic for hundreds of files at once; each deserves its own scoped edit and full regeneration-and-diff review, not a bundle rushed through inside a 20-section audit.
- **Any new page type** (topic hub pages, static `/pathway/` overview, negative-results view) — these require real content/data decisions (what goes on an "aging" topic page?) that aren't Petr's or Oliver's to delegate to an audit; they need editorial input. **Exception found after this audit was written: the 41 additional author pages are NOT in this category** — the content already exists (§21) and publishing them is a mechanical re-export + rebuild, not an editorial decision. Still not implemented in this pass (per your instruction to design before touching `build_pages.py`), but it no longer belongs on the "needs editorial input" list.
- **PageSpeed/Core Web Vitals fixes** — not implemented because the measurement itself wasn't run (§4); fixing an unmeasured problem risks solving the wrong thing.
- **Any backlink/outreach action beyond what was already in flight** — §15's new targets (Lifespan.io, media outreach, competitions, Product Hunt) are proposals for Petr and Oliver to decide on, consistent with how every prior outreach step in this project has worked (drafted, then explicitly approved before sending).
- **Any GSC action** (manual URL Inspection re-submission, etc.) — read-only verification was performed; no write actions were taken in Search Console during this audit, since that wasn't explicitly asked for this time and the 2026-08-22 audit already did a batch of manual indexing requests.

## 19. Expected impact

The single fix made this session (§17) is cosmetic/consistency, not a ranking lever — its value is correctness (an AI system reading the Dataset schema now gets the right study count) and avoiding a small but real credibility ding if anyone technical inspects the structured data closely. It does not meaningfully move indexation or traffic on its own.

The dominant lever for the 255 "discovered, not indexed" pages and the near-zero organic traffic remains **authority** — backlinks and citations, already the active workstream. Realistically: expect the indexed-page count and organic impressions to start moving only after the in-flight backlink campaign (Wikipedia, bioRxiv, re3data/FAIRsharing, Reddit) is picked up by Google's crawler and counted, which is a matter of weeks, not days, and was already the conclusion of the 2026-08-22 audit — this pass didn't find anything to change that assessment.

The P1 items with the best effort-to-impact ratio, in order: (1) finishing the backlink campaign already in motion, since it unblocks everything else; (2) the methodology article, since it's simultaneously a GEO asset, a natural link target, and a differentiator; (3) the static About/Methodology page, since it's the cheapest fix to the one real trust gap this audit found (§14); (4) surfacing the Mechanism-Explorer relations, since the data already exists and it's pure upside for both knowledge-graph SEO and GEO with no new curation cost.

## 20. Recommended next 10 actions

1. Review the `git diff` from §17 and run `deploy.bat` to ship the study-count fix.
2. Test 5-10 representative queries directly in Perplexity, ChatGPT search, and Gemini to measure current AI-citation behavior as a baseline (§8) — free, fast, high-information.
3. Run PageSpeed Insights on `/` and one `/study/…` page; only act if it surfaces a real problem (§4).
4. Identify and fix/redirect the 1 known 404 and confirm the 3 "page with redirect" URLs in GSC are the intended legacy-slug stubs (§4).
5. Write the methodology article (evidence-tiering + gap-finding as a system) — highest-leverage content piece not yet started (§8, §15).
6. Build the static About/Methodology/Curator page (§14) — the single highest-leverage trust fix identified.
7. Scope and build cross-links between overlapping `/answers/` and `/question/` pages (§11).
8. Re-export `AUTHOR_BIOS` from `index.html` to `atlas_data/author_bios_baked.json` and re-run `build_pages.py` to publish the 41 already-written author bios as static pages (§3, §21) — no data decisions needed, they're already written. Separately, decide whether to write a new bio for Brunet, the one named researcher still genuinely missing content.
9. Re-check the GSC Links report in 1-2 weeks to confirm internal-links-0 was a reporting lag, not a real gap, and to see whether any of the in-flight backlinks have started being counted (§5).
10. Decide, as a Petr/Oliver call rather than a Claude one, whether to pursue the media-angle outreach (§15) — it's the highest-potential single link but also the one requiring the most judgment about how much public attention is wanted.

## 21. Correction — 2026-08-23 (author coverage), addendum after initial publication

The "Author coverage is 5 of ~488" framing used throughout §3, §6, §7, §8, §9, §12, §13, §16, §18 and §20 above understated what already exists, and is corrected here rather than silently rewritten, consistent with this project's own transparency posture (§14).

**What triggered the correction:** Petr pointed out that clicking through the site's Authors tab surfaces bio write-ups ("medailonky") for far more than 5 researchers. Direct inspection of `index.html` confirmed this: the `AUTHOR_BIOS` JavaScript object — the same data structure that powers the Top-5 bio modal (`showAuthorBio()`) — contains **46 complete author profiles** (`full`, `role`, `sub`, `story` narrative paragraphs, `highlights` milestone captions; 43 of the 46 also have a `photo`), not 5. Any author name in the full Authors table that has a matching `AUTHOR_BIOS` entry already shows a small profile icon that opens the same bio modal (`renderAuthorsTable()`, confirmed in the source) — this is a live, working feature today, just not exposed to crawlers.

**Why the static-page count still said 5:** `build_pages.py` doesn't read `AUTHOR_BIOS` out of `index.html` directly — by design (documented in its own comments, added 2026-08-04) it reads a separate baked snapshot, `atlas_data/author_bios_baked.json`, so the Python build has no Node/JS dependency. That snapshot was taken once, when only the original 5 profiles existed, and was never retaken as the other 41 were added directly to `index.html` over time. The generator code that turns a bio into a static page (`author_page()`) already handles all the fields correctly — it has simply never been given more than 5 records to work from.

**Verified against your brief's named researchers:** Zoncu ✅ has a full profile already. Shaw ✅ has a full profile already. Brunet ❌ genuinely has no entry in `AUTHOR_BIOS` — this is the one name from your brief that still needs a real bio written from scratch.

**Net effect on this audit's recommendations:** every place above that framed "add author pages beyond Top 5" as a research/writing task (needing verified institution, ORCID, publication history per researcher) should be read as a **publishing task** for 41 of the 46: re-export `AUTHOR_BIOS` to `atlas_data/author_bios_baked.json` (a small script, same technique used to build the file originally — see the comment at the top of `build_author_index`/`author_page` in `build_pages.py`), re-run `build_pages.py`, review the diff, deploy. This is meaningfully cheaper and lower-risk than the original P1 item implied, and moves the author-page item up in effort-to-impact terms even though its priority tier (P1) doesn't change. Writing a new bio for Brunet remains a real, separate editorial task.

**Not done in this pass, per your standing instruction to design before touching `build_pages.py` output for hundreds of files:** the re-export script and the rebuild itself were not run. This section documents the finding and the corrected recommendation only.

## Recommended primary SEO/GEO landing pages

Based on what already has the strongest content-to-competition ratio: `/answers/rapamycin-lifespan-humans/` (directly targets the query where weaker competitors currently rank), `/answers/mtor-inhibitors-list/`, `/glossary/` (best GEO/definition-citation candidate), `/` (homepage, Dataset schema), `/browse/` (crawl-depth hub), and `/gene/mtor/` + `/complex/mtorc1/` + `/complex/mtorc2/` (core entity pages most likely to accumulate cross-references over time).
