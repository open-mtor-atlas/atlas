# Connecting the web page to Airtable — technical solution

Your `index.html` is a static page that already bakes the studies into a JS constant (`ATLAS_STUDIES`) and computes everything client-side. I kept that architecture and added two things: an **Ask Atlas** tab (client-side RAG) and a data-driven **Gaps & Hypotheses** tab (`ATLAS_GAPS`). Here is how the Airtable connection works and how to grow it.

## The golden rule
**Never put an Airtable token or an LLM API key inside `index.html`.** Anything in the page is public. Secrets live either on your machine (build-time sync) or in a serverless function (runtime proxy) — never in the browser.

## Three tiers — pick based on how "live" you need it

### Tier 0 — Static bake (what you have now, $0, no server)
Data flows: **Airtable → `sync_airtable.py` (on your machine) → rewrites the `ATLAS_STUDIES` + `ATLAS_GAPS` constants in `index.html` → commit → deploy (GitHub Pages / Netlify / Vercel static).**

- Retrieval (Ask Atlas) and the gap cards run entirely in the browser over the baked data. Offline, instant, free.
- Refresh the page after changing the base:
  ```bash
  export AIRTABLE_TOKEN=patXXXX      # read-only PAT scoped to this base
  python3 sync_airtable.py           # rewrites index.html
  # then: git commit && push  (or run deploy.bat)
  ```
- The token only ever touches your machine, not the published page.
- **Trade-off:** the page is a snapshot; you re-sync when the base changes (same cadence your "re-run the Airtable sync" note already implies).

### Tier 1 — Live read via a serverless proxy (still free tier, always fresh)
When you want the page to reflect Airtable without re-deploying, add one tiny serverless function that holds the token and forwards read requests.

```
Browser  ──fetch('/api/studies')──►  Serverless function (Vercel / Cloudflare Worker)
                                       - holds AIRTABLE_TOKEN in its env vars
                                       - calls Airtable REST API
                                       - returns JSON (cached ~5 min)
```
- Example: a Vercel/Cloudflare function reads `process.env.AIRTABLE_TOKEN`, calls `https://api.airtable.com/v0/appt2U6ObDHUcRlrj/Studies`, returns the array. The page fetches `/api/studies` on load instead of using the inlined constant.
- Free tiers (Vercel Hobby, Cloudflare Workers) cover this easily. Add a short cache so you don't hammer Airtable's 5 req/s limit.
- Still zero secrets in the browser.

### Tier 2 — Live RAG answers + write-back (adds an LLM)
Right now Ask Atlas retrieves studies and builds a prompt you paste into an LLM. To generate the four-section answer *in the page*, add an `/api/ask` function:

```
Browser ──POST /api/ask {question}──► Serverless function
                                        1. (optionally) run retrieval server-side
                                        2. call Claude / Gemini with the 4-section prompt
                                        3. return {answer, citations}
                                        (LLM key + Airtable token live in env, never client)
```
- Same pattern lets you **write new gaps back** to the `Knowledge_Gaps` table (e.g. a "Save this as a hypothesis" button) — that needs a token with *write* scope, so it must go through the function, not the page.
- Cost: only the LLM calls (Gemini has a generous free tier; Claude/OpenAI are pay-per-call). Retrieval stays free/client-side if you prefer.

## Recommended path
Stay on **Tier 0** for the demo and mentor conversations — it is genuinely good, costs nothing, and has no moving parts. Move to **Tier 1** only when re-syncing by hand becomes annoying, and to **Tier 2** only when you want in-page AI answers or write-back. The client-side retrieval you now have is the same interface either way — Tier 1/2 just swap where the data and the LLM call live.

## Field mapping (Airtable → page)
`sync_airtable.py` maps Studies fields to the keys the page expects:
`Study_ID→sid, Title→title, Authors→authors, Year→year, Journal→journal, Category→category, Model→model, Key_Finding→finding, Evidence_Tier→tier, Pyramid_Level→pyramid, Peer_Reviewed→peer, DOI→doi, Abstract (PubMed)→abstract` (plus the `AI_*` fields, carried through for future UI). Knowledge_Gaps maps to `ATLAS_GAPS` (Gap_ID, Type, Title, Evidence_Basis, Hypothesis, Proposed_Experiment, Supporting_Studies→study codes, Confidence).

## Production upgrade (optional)
If the corpus grows past a few thousand studies, swap the in-page TF-IDF for real embeddings: precompute vectors at sync time (sentence-transformers, free) and ship them as a compact binary the page loads — the retrieval interface in `renderAsk`/`ragSearch` stays the same. Below ~1–2k studies, client-side TF-IDF is more than enough.
