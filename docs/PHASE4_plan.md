# Phase 4 — Full texts (OA) & depth — step plan

*Goal: move from abstract-level to full-text-level Atlas for the studies where it's legal and free. This sharpens answers (real doses, sample sizes, effect sizes, limitations) and makes the gap analysis quantitative. Prepared 2026-07-08.*

## What Phase 4 buys us
Abstracts give mechanism + headline result (~80% of a good answer). Full text adds the last 20% that the gap layer actually needs: exact **dose/schedule**, **sample size (n)**, **effect magnitude + statistics**, **duration**, and **limitations**. That turns hypotheses like H2 (mTORC1-selective dosing) from qualitative into dose-response-grounded.

## Guardrail (non-negotiable, do first)
Only store and chunk full text that is genuinely **open-access licensed** (CC-BY etc.). "In PMC" ≠ "redistributable" — some PMC records are author manuscripts with restrictions. For anything not OA-licensed, stay at abstract level. This is both legal hygiene and a feature ("respects licenses").

---

## Step 0 — Prep & cleanup (fast)
- **Dedup the corpus first.** Phase 2 flagged ~5 near-duplicate study records (e.g. Bodine "Akt/mTOR hypertrophy", Drummond "blocks human MPS", Bjedov "Drosophila rapamycin", CASTOR1 arginine sensing appear twice). Merge/remove before spending full-text effort on duplicates.
- Freeze the input list: the 163 `fulltext_pmc_available = true` studies from `studies_enriched.jsonl`.

## Step 1 — Legal/OA license gate
- Run `get_copyright_status` on the 163 PMIDs → split into **OA-licensed (safe to store/chunk)** vs **PMC-but-restricted (abstract only)**.
- Write the result back to Airtable as a `License` field (e.g. CC-BY / CC-BY-NC / author-manuscript / unknown).
- *Output:* the true "chunkable" subset (likely ~100–140 studies).

## Step 2 — Fetch full texts (OA subset only)
- `get_full_text_article` (PMC JATS/XML) for the OA subset; store raw XML per study.
- *(Optional, later)* for the 87 non-PMC studies, try Unpaywall to find a legal OA copy elsewhere — bonus coverage, not required.

## Step 3 — Section-aware chunking
- Parse JATS/XML into sections (Introduction / Methods / Results / Discussion) and, where present, target-rich blocks (Mechanism, Dose, Limitations).
- Chunk to ~300–500 tokens with light overlap. Each chunk carries metadata: `paper_id, sid, section, evidence_tier, species`.
- *Output:* `chunks.jsonl` (the new retrieval unit; replaces "1 study = 1 abstract").

## Step 4 — Deepen the AI extraction
- From Methods/Results, extract the fields the abstract couldn't give:
  `AI_Dose`, `AI_Schedule`, `AI_SampleSize`, `AI_EffectSize` (magnitude + p/CI), `AI_Duration`, `AI_Limitations`, plus `AI_FullText_Extracted` (checkbox).
- Write back to Airtable Studies (new fields, prefix kept consistent with Phase 2).
- *This is the highest-value step* — it's what makes gaps quantitative.

## Step 5 — Re-index (embeddings decision point)
- Build a **chunk-level** index. Two options:
  - **(a) Stay TF-IDF** over chunks — still free/offline, minimal change.
  - **(b) Upgrade to neural embeddings** (sentence-transformers `all-MiniLM`, free/local) — better for nuanced full-text queries. This is the natural moment to switch, since chunks are now semantic. The `build_index/query` interface is already swap-able, so only the embed function changes.
- Recommendation: try (b); keep (a) as fallback.

## Step 6 — Retrieval upgrade (2-stage)
- Query → retrieve top chunks → group by study → (optional) LLM re-rank → assemble the 4-section prompt with **section-level** context (so answers can cite "Methods: dose X" / "Results: n=Y, p=Z", not just the abstract).

## Step 7 — Serving decision for the web page
- Full-text chunks are too big to bake into `index.html` (would bloat it well past 1 MB). Options:
  - **Keep abstract search inline (fast, current)** and add a **"Deep search"** that calls a **Tier-1 serverless endpoint** backed by the chunk store (per `TECH_SOLUTION_airtable.md`). Recommended.
  - Or ship a compact pre-computed chunk index as a separate lazy-loaded file.

## Step 8 — Refresh the gap layer
- Re-run `gap_finder` with the new quantitative fields → sharper, quantified gaps (e.g. dose-response contradictions, under-powered human trials) and updated `Knowledge_Gaps`.

## Step 9 — Verify
- Spot-check extractions against source (dose/n accuracy on ~10 studies).
- Confirm **no non-OA full text was stored**.
- Unit-test the chunker (sections parsed, no empty/giant chunks).

---

## What I can run here now vs later
- **Doable in this session (free, via MCP):** Step 0 dedup, Step 1 license gate, Step 2 OA full-text fetch, Step 3 chunking, Step 4 deepened extraction back to Airtable, Step 8 refreshed gaps.
- **Constrained here:** Step 5(b) neural embeddings — the sandbox blocks HuggingFace downloads, so I'd stay on TF-IDF here; you'd run the neural embed step on your machine (or I can wire it to a free API).
- **Needs your infra:** Step 7 serverless deep-search endpoint (Vercel/Cloudflare).

## Effort / cost
- Steps 0–4 for ~130 OA studies: roughly a day of processing, **$0** (PMC + your existing LLM). Steps 5–7 are optional polish. No paid services required unless you choose neural embeddings via API or a serverless LLM.

## Suggested first move
Start with **Step 0 (dedup) + Step 1 (license gate)** — small, safe, and it tells us exactly how many studies are legally chunkable before we invest in fetching and extraction.
