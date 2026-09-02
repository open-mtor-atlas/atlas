# AI citation baseline -- Oliver's mTOR Atlas

**Date measured:** 2026-09-02, ~14:55-15:11 UTC (Prague browser session, Czech locale/region)
**Method:** Claude in Chrome, driving Petr's real browser. 10 queries from the brief, run
against Google AI Mode and Bing (both reachable anonymously via a direct search URL) --
no accounts created, no logins performed by this session. Perplexity and Microsoft
Copilot were also attempted; both require signing in/up to run a query and were **not**
used further, per the brief's hard rule against creating accounts or logging in. ChatGPT
search was attempted using Petr's own pre-existing, already-logged-in browser session
(not a login performed by this session) but reliably automating query submission through
its UI was not achievved within this session's time budget; it is not included below.
See "Engine coverage" at the end for the honest state of all four requested engines.

## Results table

| # | Query | Google AI Mode: cites Atlas? | Domains cited instead (Google) | Bing: cites Atlas? | Domains cited instead (Bing) |
|---|---|---|---|---|---|
| 1 | does rapamycin extend lifespan in humans | No | NIH/PMC, Frontiers, Aging-US, eLife, gethealthspan.com | No (AI overview box) | regenerated.com, Frontiers, NIH/PMC, Medical News Today |
| 2 | mTORC1 vs mTORC2 difference | No | NIH/PMC, Touro Scholar | No (AI overview box) | difbetween.com, thisvsthat.io, NIH/PMC, biologyinsights.com |
| 3 | list of mTOR inhibitors | No | Wikipedia, NIH/PMC, DrugBank | No (plain results, no AI box) | Drugs.com, Wikipedia, drugslib.com, GoodRx, DrugBank |
| 4 | what is Rheb | No | Wikipedia, ScienceDirect, NIH/PMC, Reactome | No (plain results, no AI box) | Wikipedia, ScienceDirect, GeneCards, UniProt |
| 5 | is autophagy required for rapamycin lifespan extension | No | NIH/PMC (dominant) | No (AI overview box) | pierrehealth.com, Nature, NIH/PMC, Life Extension |
| 6 | rapamycin vs metformin longevity | No | Healthspan, Harvard Health, PMC, My Longevity Centre, Aging-US, Medical News Today | No (AI overview box) | designinglongevity.com, vialaudit.com, Meer |
| 7 | what does TSC2 do in mTOR signaling | No | MedlinePlus, Cell Press, NIH/PMC, ScienceDirect | No (AI overview box) | bioRxiv, ScienceDirect, Cell Press, Harvard Chan |
| 8 | mTOR pathway diagram | No | Cell Signaling Technology, ResearchGate, Abcam, Assay Genie | No (plain results, no AI box) | Cell Signaling Technology, ResearchGate, R&D Systems, Wikipedia |
| 9 | evidence-graded mTOR database | **Yes** -- 3 citations (homepage, About & Methodology, Data & Citation) | -- | **Yes** -- top result, AI overview box quotes the Atlas directly | GitHub (open-mtor-atlas/atlas, our own repo, indexed independently of any on-site link), GeneCards, LOVD, Nature |
| 10 | Oliver's mTOR Atlas | Partial -- AI overview text correctly describes and names the Atlas (mentions mtor-atlas.org), but the 3 citation sources shown below the answer are NOT mtor-atlas.org (NIH/PMC, WikiSkripta, PMC) | NIH/PMC, WikiSkripta | **Yes** -- 9 of ~9 shown results are mtor-atlas.org pages (homepage, /gene/mtor/, a study page, /condition/energy-cellular-stress/, /outcome/longevity/, 4 more study pages) | -- |

## What this shows

**On generic mTOR biology questions (queries 1-8), the Atlas is not yet cited by either
engine.** Both engines answer these from long-established, high-authority sources (NIH/
PMC, Wikipedia, Reactome, ScienceDirect, Cell Signaling Technology, DrugBank) that have
years of accumulated citations and backlinks the Atlas does not have yet. This is the
expected state for a resource this young and matches the "authority is the dominant
lever, and takes weeks not days" conclusion already on file from the 2026-08-22 SEO/GEO
audit -- this baseline doesn't change that conclusion, it just gives it a concrete,
dated measurement to compare against later.

**On queries naming the resource or its exact category (queries 9-10), both engines
already know about it and Bing cites it prominently.** "Evidence-graded mTOR database"
-- a description close to, but not identical to, the Atlas's own tagline -- surfaces the
Atlas as the literal top/only cited source on both engines. The exact brand-name query
("Oliver's mTOR Atlas") gets a 9-of-9 mtor-atlas.org result sweep on Bing; on Google AI
Mode it's described correctly in the generated text but the citation footnotes point
elsewhere (NIH/PMC, WikiSkripta) rather than to the site itself -- worth re-checking in
a future baseline run to see whether that's noise (a single AI-generation quirk) or a
persistent pattern.

**One incidental finding, not an action item:** Bing's own index surfaces
`github.com/open-mtor-atlas/atlas` on query 9, independent of anything on the live site
(the brief's rule against linking to the GitHub repo governs what mtor-atlas.org itself
links to; a search engine crawling and indexing a public GitHub repo on its own is
outside that rule's scope and outside this session's control).

## Engine coverage (honest accounting against the brief's 4 requested engines)

- **Google AI Mode** -- done, all 10 queries, via `google.com/search?q=...&udm=50`
  (anonymous, no login).
- **Bing** -- done, all 10 queries, via `bing.com/search?q=...`. Note this is Bing's
  in-search-results AI answer box (present on 6 of 10 queries here), not the dedicated
  Bing Copilot chat product at copilot.microsoft.com, which requires signing in with a
  Microsoft/Apple/Google account (screen: "Přihlásit se k funkci Copilot") and was
  therefore not used, per the brief's hard rule.
- **Perplexity** -- attempted (query 1 only): after the first anonymous query,
  perplexity.ai responded "Sign up and repeat your request." rather than an answer --
  blocked by a signup wall, not used further.
- **ChatGPT search** -- attempted: chatgpt.com recognized Petr's own existing,
  already-logged-in session ("Ahoj, Petr" / "Rád tě vidím, Petr" -- this session did not
  log in or create anything, it found Petr already signed in on his own browser,
  consistent with how this environment treats an existing session as the user's own).
  Reliably automating query submission through ChatGPT's UI (the query kept landing in
  the input box without triggering a send) was not achieved within this session's time
  budget, so no ChatGPT results are reported above. If a repeat baseline run is done,
  this is worth a fresh, more patient attempt, or simply running the 10 queries by hand
  in a couple of minutes -- Petr is already logged in.

## Bing Webmaster Tools -- manual setup only, per the brief ("nezakládej", do not set up from this session)

1. Go to https://www.bing.com/webmasters and sign in with a Microsoft account (Petr's
   own).
2. Add site: `mtor-atlas.org`.
3. Verify ownership -- either add the DNS TXT record Bing gives you to the domain's DNS
   settings, or use the "import from Google Search Console" option if GSC is already
   verified for this domain (faster, since GSC is already set up per prior SEO work).
4. Once verified, submit `https://mtor-atlas.org/sitemap.xml` (or `sitemap-home.xml` /
   whichever is the canonical top-level sitemap) under Sitemaps.
5. Check the IndexNow submission history after about 3 days to confirm Bing is picking
   up pages pushed via IndexNow (if IndexNow is already wired into the deploy pipeline;
   if not, that's a separate, larger task outside this session's scope).

## Re-running this baseline later

Re-run the same 10 queries (see the table's "Query" column) against
`https://www.google.com/search?q=<query>&udm=50` and `https://www.bing.com/search?q=<query>`
and compare against this dated snapshot to see whether authority-building work (backlinks,
FAIRsharing/bio.tools/Bioregistry registrations, the LinkOut and Academy outreach from
Ukol 6-9 above) is moving the needle on the generic-question queries (1-8), where the
Atlas currently has zero citation share.
