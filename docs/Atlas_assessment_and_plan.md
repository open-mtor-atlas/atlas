# Oliver's mTOR Atlas — critical assessment, low-cost technical plan, and concrete procedure

*Decision brief. Date: 2026-07-08. Written as a senior scientist who also builds AI systems would advise you — but kept understandable without an engineering background.*

---

## One-paragraph summary

The idea is good, and the direction "What don't we know yet — and why?" is genuinely what will set you apart. But a **generic scientific RAG is no longer an innovation** — it is a solved, partly commoditized problem (open-source tools already do it better than you would from scratch). Your real advantage lies elsewhere, and **you already have much of it in Airtable**: a curated selection of ~250 landmark studies, an evidence hierarchy (Pyramid_Level, Evidence_Tier), and an entity layer (the Entities table = a nascent knowledge graph). Recommendation: do not rebuild what already exists for free. Build a thin layer on top — evidence grading + gap finding + generation of testable hypotheses — and borrow the RAG core. The whole thing can be built **free or nearly free**.

---

## 1) Critically: does this already exist, and how could ours be better?

### Yes, it exists — and there is a lot of it. Split into the three layers your proposal mixes together:

**a) RAG over papers with citations (the core of your proposal).** This is the most crowded field.
- **PaperQA2** (FutureHouse, open-source, free) is currently state-of-the-art. On the scientific RAG-QA Arena benchmark it is 10+ points ahead of everything else, and on retrieving information from the literature (LitQA2) it beats PhD and postdoc biologists. It does exactly what you describe in steps 2–3 and 6–7: chunking, metadata-aware embeddings, LLM re-ranking and contextual summarization, answers with in-text citations. 7,000+ GitHub stars.
- **Commercial:** Elicit (structured extraction tables, systematic reviews), Consensus (yes/no synthesis from study findings), Undermind (recursive semantic search), Scite (citation context — whether a citing paper supported, contradicted, or merely mentioned a finding), Semantic Scholar, Perplexity.

> **Conclusion:** Steps 1–3, 6, 7 of your proposal are not a differentiator. Anyone can do them in a weekend with PaperQA2. Do not build them from scratch.

**b) Structured biological knowledge layer / knowledge graph.** Also exists, at a scale one person cannot build alone:
- **SemMedDB** (subject–predicate–object relations mined from all of PubMed), **INDRA**, **SPOKE**, **PrimeKG**, **Hetionet** — large biomedical graphs of proteins, genes, pathways, drugs.

> **Conclusion:** You do not need to build the full knowledge graph (step 5). For mTOR a small, curated subgraph is enough — and you are already starting it in the Airtable Entities table. That is the right call; don't try to compete with SPOKE.

**c) Hypothesis generation and knowledge-gap finding (your "true differentiator").** This is the least crowded field, but NOT empty:
- **Google/DeepMind AI co-scientist** (Feb 2025): a multi-agent system (Generation, Reflection, Ranking, Evolution, Meta-review agents) that generates and tournament-refines hypotheses. Cut early hypothesis generation from weeks to days; experts rated proposals as more novel.
- **Literature-Based Discovery (LBD):** an old, proven discipline. Swanson's ABC model (if A–B in one literature and B–C in another, propose an untested A–C link — this is how Swanson found the fish oil ↔ Raynaud's connection). Classical systems Arrowsmith, BITOLA; today LLM variants.

> **Conclusion:** "What we don't know and why" is a real market gap for a *cohesive, domain-focused product*, but the concept itself is not new. The AI co-scientist is general and not public; LBD tools are academic and awkward to use.

### So where can we objectively be better (and where not)

**Real advantages to build on:**
1. **Single-domain focus (mTOR) + a curated corpus.** General tools (Elicit, PaperQA) take all of PubMed and are "broad but shallow." You have a narrow, hand-picked corpus of landmark studies. For a narrow domain a curated corpus gives more accurate, less noisy answers. This is your strongest and most defensible card.
2. **Explicit evidence hierarchy.** You have Pyramid_Level and Evidence_Tier (GRADE-style A–D) in Airtable. Almost no scientific RAG distinguishes "mouse in vitro" from "human RCT" in the answer itself. Color-coding every sentence of the answer by evidence strength is immediately visible value that Consensus and PaperQA don't do this explicitly.
3. **A gap/hypothesis layer tied to the curated corpus and evidence tiers.** Not "generate a hypothesis from the whole internet," but "show me pairs of entities linked only by weak (tier C/D) evidence, or not at all — those are testable gaps." That is concrete, defensible, and nobody offers it packaged this way.

**Where you cannot win (and shouldn't try):**
- Breadth of literature coverage (Elicit/Undermind have all of PubMed).
- Quality of the generic RAG core (PaperQA2 is SOTA with a team behind it).
- Size of the knowledge graph (SPOKE/PrimeKG).

**Honest risk:** the biggest trap is spending 3 months building a FastAPI + Next.js + pgvector + LangGraph pipeline that ends up doing the same thing as `pip install paper-qa`. The value is not in the infrastructure. It is in the curation (done), the evidence grading (done), and the gap layer (missing). Put 80% of your energy there.

---

## 2) Improved technical plan — free / minimal resources

### Key shift vs. the attachment
The attachment proposes a full production stack (FastAPI, PostgreSQL, pgvector, Pinecone, LangGraph, Next.js, Claude Opus/GPT). That is the right goal for a *finished product*, but for now it's needlessly expensive and slow. **First prove the value on a minimal stack, then scale.** And critically: most of the "infrastructure" already exists for you.

### What you already HAVE (and what it replaces from the proposal)

| You have | Replaces in the proposal |
|---|---|
| Airtable base "mTOR Studies" — Studies (Evidence_Tier, Pyramid_Level, PubMed abstract, DOI), **Entities** (linked layer), Authors | the "curatorial database" **and the seed of the Knowledge Graph (step 5)** |
| PubMed / PMC tool with full-text access + copyright checking | step 1 (getting full texts) — legally and for free |
| This Cowork assistant (Claude) | the LLM for both extraction and answers — no API cost during development |

### Low-cost/free stack (MVP)

| Layer | Proposal (expensive/complex) | Free/low-cost variant | Why |
|---|---|---|---|
| RAG core | custom pipeline (LangGraph + LlamaIndex) | **PaperQA2** (open-source) or a thin **LlamaIndex** script | Don't write SOTA RAG from scratch; it's free and better |
| Full texts | "download PDF/XML" (grey area) | **Europe PMC OA subset + Unpaywall + PMC** (via the PubMed tool) | Millions of full texts free and **legally**; OA licenses only |
| Embeddings | OpenAI text-embedding-3-large (paid) | **open-source embeddings free** (local) or Gemini free tier; paid only in production | No need to pay for thousands of chunks |
| Vector DB | Pinecone / Qdrant (hosted) | **LanceDB / Chroma / sqlite-vec locally** | For ~250 studies (thousands of chunks) a local file is more than enough; pgvector later |
| Knowledge graph | Neo4j | **stay in Airtable (Entities) + a relations table**; Neo4j once it outgrows it | The KG is half-built; migrate when it hurts |
| LLM | Claude Opus / GPT-5.5 (paid) | **this Cowork / Claude** for development; Gemini free API has a generous limit | Don't pay for API until you have value |
| Frontend | Next.js + Vercel | **Streamlit** (Community Cloud free) or a simple HTML artifact | Chat UI in an hour instead of a week |

**MVP cost estimate: $0.** Paid APIs (better embeddings, production hosting) are added once you have something to show.

### What to add to the plan (missing from the attachment)

- **A legal/copyright gate as the first step, not a footnote.** Before you store or embed anything from full text, check the license (you have the `get_copyright_status` tool). Store and chunk full texts **only for OA licenses** (CC-BY, etc.). For paywalled papers, stay at abstract + metadata. This protects you and is itself a feature ("respects licenses").
- **Evidence-aware answers.** The four answer sections (Answer / Evidence / Key Papers / Knowledge Gaps) are great — but add that each claim carries its Evidence_Tier from Airtable. That is your visible differentiator.
- **The gap layer as a first-class feature, not "later."** It is exactly what sells the project to mentors. Don't put it at the end of the roadmap — do a simple version right away (see Phase 3 below).

---

## 3) Concrete procedure — and the answer to "full texts first, or embeddings first?"

### Direct answer to your question
**No, don't start by fetching full texts.** It is the slowest and most legally sensitive step, and **you don't need it for a first working prototype.** You already have the PubMed abstracts in Airtable — build the MVP on those today. Add full texts in a second wave, and **only for the OA subset** (free, legal). The correct order is:

**metadata (have it) → embed abstracts → index → chat with citations → AI extraction back into Airtable → gap analysis → *only then* OA full texts for depth.**

Why: the abstract of a landmark study contains ~80% of what RAG needs for a good answer (mechanism, model, main result). Full texts improve details (doses, limitations, numbers) — that is optimization, not a precondition for starting.

### Phased plan

**Phase 0 — data prep (a few hours) — DONE**
- Export Studies from Airtable (Title, Authors, Year, DOI, PubMed abstract, Evidence_Tier, Pyramid_Level, Related_Entities).
- Fill in missing abstracts and PMIDs via the PubMed tool.
- Output: one clean file (CSV/JSON) = source of truth for embeddings. → `atlas_data/`

**Phase 1 — RAG MVP over abstracts (one weekend) — DONE**
- Chunk the abstracts (for an abstract, 1 chunk = 1 study is fine), attach metadata (paper_id, year, species/model, evidence_tier).
- Embeddings (free, local) → local vector DB.
- Chat: query → 10–20 most relevant passages → LLM → answer **always in four sections (Answer / Evidence / Key Papers / Knowledge Gaps) with PMID/DOI citations**. → `atlas_rag/`

**Phase 2 — AI extraction back into Airtable (a few days) — IN PROGRESS**
- For each study, have the LLM extract a structured JSON: {model_organism, intervention, effect_direction, dose, side_effects, evidence_level, confidence}.
- Write it back into Airtable (new `AI_` fields). This turns the database into a machine-queryable biological DB (your step 4) — and feeds the knowledge graph.

**Phase 3 — Gap & hypothesis layer (your differentiator, simple version now)**
- Over the Entities table + extracted relations, find: (a) entity pairs linked only by tier C/D evidence, (b) entities mentioned but not directly linked (ABC/Swanson pattern), (c) contradictions (studies with opposite effect direction in the same model).
- The LLM formulates 3–5 **testable hypotheses** + experiment sketches, each linked to the studies that define the gap.
- This is the answer to "What we don't know and why" — built on *your* curated, evidence-graded corpus, not the whole internet. Here you are unique.

**Phase 4 — full texts (OA) and depth (later)**
- Via Europe PMC OA + Unpaywall + PMC, download full text only for OA studies (license check).
- Chunk by semantic sections (Methods/Results/Discussion, ideally Mechanism/Dose/Limitations), re-embed.
- Only now consider better paid embeddings and a move to pgvector/production hosting.

**Phase 5 — productization (only after validation with mentors)**
- Migrate to FastAPI + Next.js, optionally PaperQA2 as the engine, Neo4j for the graph — if the data outgrows Airtable.

### Decision rules so you don't get lost
- **Don't build infrastructure until you've proven value.** Streamlit + local DB until it works on content.
- **Don't compete on breadth.** Your strength is the narrow curated corpus + evidence grading + gaps.
- **Legal data only.** OA full text yes; scraping paywalls no — you'll get far with abstracts anyway.
- **Differentiator before polish.** A rough gap analysis in Phase 3 is worth more than a prettier UI.

---

## What I can do right now (here in Cowork)
I have access to your "mTOR Studies" Airtable base, to PubMed/PMC (full texts + copyright checking), and to this LLM. Without paying for anything I can:
1. Export and clean Studies into one file for embeddings. *(done)*
2. Fill in missing PMIDs/abstracts and flag which studies have a **legally available OA full text**. *(done)*
3. Run the AI structured-data extraction (Phase 2) and write it back into Airtable. *(in progress — 50/250 done)*
4. Build a first list of **knowledge gaps and testable hypotheses** (Phase 3) directly from your corpus — as a proof of concept for mentors.
