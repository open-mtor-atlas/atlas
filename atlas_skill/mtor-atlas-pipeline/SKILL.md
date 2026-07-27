---
name: mtor-atlas-pipeline
description: >
  Turn a curated Airtable base of scientific studies into an evidence-graded
  literature engine: a citation-grounded RAG assistant, structured AI extraction,
  a "what we don't know" knowledge-gap + hypothesis layer, full-text deep search,
  and a static (GitHub Pages) web page — all free/offline where possible.
  Use when the user references Oliver's mTOR Atlas or asks to: build/refresh the
  atlas, export/extract studies from Airtable, run a gap analysis, generate testable
  hypotheses, deep-extract full text (dose / sample size / effect size), fetch
  open-access full texts, build a chunk index, wire deep search, or deploy the page.
  Triggers: "run the atlas pipeline", "build the atlas", "gap analysis",
  "knowledge gaps", "extract studies", "deep search", "sync Airtable to the page".
---

# mTOR Atlas pipeline

A repeatable loop that turns a **curated Airtable study base** into an evidence-graded
research tool. Built for Oliver's mTOR Atlas but works for any single-domain corpus.

## Core principles (do not skip)
1. **Curation beats scale.** A few hundred hand-picked landmark studies with evidence
   tiers beat tens of thousands of average ones. Don't rebuild generic RAG — the value
   is curation + evidence grading + the gap layer.
2. **Evidence tiers everywhere.** Every study carries `Evidence_Tier` (A systematic >
   B human > C animal > D mechanistic/review). Answers and gaps must grade claims by it.
3. **Legal split (Phase 4).** Store/serve *verbatim text* only for open-licensed
   (CC, non-No-Derivatives) studies. For everything else, extract *derived facts*
   (numbers) and discard the text. The scripts enforce this.
4. **Free/offline first.** Client-side retrieval, local scripts, free API tiers. Add
   paid services only after value is proven.

## Data model (Airtable base — set BASE id in the scripts)
- **Studies**: Title, Authors, Year, Journal, Category, Model, Key_Finding,
  Evidence_Tier, Pyramid_Level, DOI, Abstract (PubMed). Plus generated fields:
  `AI_Intervention, AI_Target, AI_Species, AI_Effect` (Phase 2);
  `License, Chunkable` (Phase 4 gate);
  `AI_Dose, AI_SampleSize, AI_EffectSize, AI_Limitations, AI_FullText_Extracted` (Phase 4).
- **Entities**: Entity_Name, Entity_Type, Description, Studies (the knowledge-graph nodes).
- **Knowledge_Gaps**: Gap_ID, Type, Title, Evidence_Basis, Hypothesis,
  Proposed_Experiment, Supporting_Studies, Confidence.

## The loop (phases)

**Phase 0 — data prep.** Export Studies from Airtable to `studies_enriched.jsonl`
(one line per study, with an `embedding_text` = Title + Key finding + Abstract).
Enrich with PMID/PMCID via DOI conversion; flag which have free PMC full text.

**Phase 1 — RAG MVP (abstracts).** `scripts/build_index.py` builds a local TF-IDF index
over `embedding_text`; `scripts/query.py` retrieves top-k studies and assembles a strict
4-section LLM prompt (Answer / Evidence / Key Papers / Knowledge Gaps) with citations +
tiers. Retrieval is client-side/offline; the LLM step is swappable.

**Phase 2 — structured extraction (all studies).** Have an LLM extract
`AI_Intervention / AI_Target / AI_Species / AI_Effect` from each abstract and write back
to Airtable. Turns the base into a machine-queryable biological DB. Keep negative/failed
results honest.

**Phase 3 — gap + hypothesis layer (the differentiator).** `scripts/gap_finder.py` joins
the Entities graph to per-study evidence tiers and surfaces: (a) evidence deserts
(entities on tier-D only), (b) mechanism→outcome disconnects, (c) contradictions, and
(d) human-endpoint deserts. Turn the top gaps into testable hypotheses (Evidence_Basis /
Hypothesis / Proposed_Experiment / Supporting studies) and write them to Knowledge_Gaps.

**Phase 4 — full text & depth.**
- `scripts/license_gate.py` — classify full-text studies via Europe PMC (`isOpenAccess`,
  `license`, author-manuscript). Chunkable = CC and NOT No-Derivatives. Writes
  `licenses.csv` and (with `--write-airtable`) the `License` + `Chunkable` fields.
- `scripts/fetch_fulltext.py` — fetch + section-chunk full text for CC studies only
  (Europe PMC JATS -> NCBI fallback). Guarded twice; resumable. Writes `chunks.jsonl`.
- `scripts/extract_facts.py` — deep-extract `AI_Dose / AI_SampleSize / AI_EffectSize /
  AI_Limitations` from full text via a free LLM (Gemini) and write to Airtable. Facts
  only, text discarded, so it's license-safe for ALL full-text studies. Auto-discovers a
  current model. Scope to experimental tiers (B/C) — reviews have no numbers.
- `scripts/pull_ai_facts.py` — export the deep-extracted facts to `ai_facts.jsonl`.
- Re-run the gap analysis with the numbers: gaps become quantitative (dose-response,
  effect sizes, exact failed endpoints). Sex dimorphism often emerges as its own gap.

**Web + deploy.**
- The page (`index.html`) bakes `ATLAS_STUDIES` + `ATLAS_GAPS` as JS constants and runs
  client-side TF-IDF retrieval (Ask Atlas tab) + the gap cards. No backend.
- `scripts/build_chunk_index.py` builds `chunk_index.json` from the stored CC full texts;
  the page's **Deep search** toggle lazy-loads it for passage-level retrieval.
- `scripts/sync_airtable.py` regenerates the baked `ATLAS_STUDIES` / `ATLAS_GAPS`
  constants in `index.html` from Airtable (read-only PAT).
- Deploy `index.html` + `atlas_fulltext/chunk_index.json` to GitHub Pages (serve repo root
  so the relative fetch resolves).

## Config / secrets (env vars — never commit)
- `AIRTABLE_TOKEN` — personal access token (read for sync/pull; write for gate/extract).
  Create at airtable.com/create/tokens, scope to the base, add data.records:read/write.
- `GEMINI_API_KEY` — free key at aistudio.google.com/apikey (for extract_facts.py).
- Set the Airtable `BASE` id (and table names) at the top of each script.

## Typical run order
```
# refresh the page from Airtable
python scripts/sync_airtable.py

# Phase 4 (needs tokens)
python scripts/license_gate.py --write-airtable
python scripts/fetch_fulltext.py
python scripts/extract_facts.py            # tier-C animal studies; edit TIERS to widen
python scripts/pull_ai_facts.py
python scripts/build_chunk_index.py

# then deploy (index.html + chunk_index.json)
```

## Guardrails to enforce every time
- Never store verbatim text for non-CC / No-Derivatives studies — facts only.
- Never put AIRTABLE_TOKEN or GEMINI_API_KEY in index.html or any committed file.
- Preserve failed/negative results faithfully (they power the gap layer).
- `index.html` may carry trailing NUL padding and can be large — edit with python +
  fsync + verify, not naive truncating writers.
