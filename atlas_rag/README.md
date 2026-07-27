# Atlas RAG — Phase 1 MVP

Local, **free** retrieval over 250 curated mTOR studies + assembly of a prompt for an LLM that returns an answer in 4 sections (Answer / Evidence / Key Papers / Knowledge Gaps) with citations and evidence tiers.

## What's inside

```
atlas_rag/
├── studies_enriched.jsonl   # corpus (from Phase 0): metadata + abstract + embedding_text
├── build_index.py           # builds the vector index (TF-IDF, offline)
├── query.py                 # retrieval + LLM prompt assembly (importable and CLI)
├── index/                   # generated index (vectorizer + matrix + meta)
├── example_output.md        # sample Atlas answer to a real question
└── README.md
```

## Running it

```bash
pip install scikit-learn scipy numpy      # the only dependencies
python3 build_index.py                     # build the index once
python3 query.py "your mTOR question" -k 12                 # top-k studies
python3 query.py "your mTOR question" --prompt             # ready-made LLM prompt
```

Paste the prompt from `--prompt` into any LLM (this Cowork/Claude, or the free Gemini API) → you get the answer in 4 sections. `example_output.md` shows what the result looks like.

## How it works (and why this way)

1. **Retrieval is local and free.** It uses TF-IDF cosine — no model downloads, no API, runs offline. For a curated corpus of 250 studies with rich abstracts it gives very relevant results (see `example_output.md`).
2. **Evidence-aware.** Each hit carries its `Evidence_Tier` (A–D) and a flag for whether it has a free full text. The LLM is instructed to grade each claim by strength of evidence.
3. **Citations required.** The prompt forces a citation [n] + PMID on every claim; no inventing facts outside the context.
4. **Differentiator = the Knowledge Gaps section.** The LLM is explicitly asked to name what the studies don't answer, contradictions, and 1–2 testable hypotheses.

## Path to production (no architecture change)

The interface is deliberately decoupled — you only swap one layer:

| Layer | MVP (now, free) | Production |
|---|---|---|
| Embedding | TF-IDF (offline) | sentence-transformers `all-MiniLM` (free, local) or Voyage/OpenAI/Gemini API |
| Vector index | scipy sparse matrix | Chroma / LanceDB / pgvector |
| Chunks | 1 study = 1 abstract | OA full text (163/250 available) split by section |
| LLM | manually / this Cowork | Claude / Gemini via API |
| UI | CLI | Streamlit (free) → later Next.js |

Concretely: in `build_index.py` and `query.py` you only replace the TF-IDF matrix construction and `search()` with a call to an embedder — `format_hits()`, the prompt, and the metadata stay the same.

## MVP limitations (honestly)
- TF-IDF is lexical, not semantic: it matches on words, not meaning. For biomedical queries with concrete terms (proteins, genes, pathways) it works well; for very abstractly phrased questions, moving to neural embeddings helps.
- It currently runs over **abstracts**, not full texts (that's the intent of Phase 1). Details like doses and limitations come with full texts in Phase 4.
- Generating the answer requires an LLM step (the prompt is prepared); in this MVP you do it via your existing subscription, not a paid API.
