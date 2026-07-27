# atlas_fulltext/ — full-text store (open-licensed studies only)

This folder holds full text **only for studies whose `Chunkable` flag is TRUE** in Airtable —
i.e. open-access, Creative-Commons, non-No-Derivatives (the ~35 identified by the Phase 4
license gate). It is safe to commit and redistribute.

## The hard rule (enforced in code)
- Studies with a permissive CC license (`cc by`, `cc0`, `cc by-nc`, `cc by-nc-sa`) → text stored here.
- Studies that are **No-Derivatives** (`cc by-nc-nd`) or have **no open license** → their text is
  **never written to disk**. They still get *derived facts* (dose, n, effect size, limitations)
  extracted into Airtable, but the copyrighted text itself is discarded after extraction.
- `fetch_fulltext.py` refuses to write any record that isn't in the chunkable set, and re-checks
  the license on every fetch as a second guard.

## Layout
```
atlas_fulltext/
├── raw/                 # raw full text per study, one file: <sid>_<PMCID>.txt|xml   (CC only)
├── chunks.jsonl         # section-aware chunks (the retrieval unit for deep-search)
├── manifest.csv         # sid, pmcid, license, section count, chunk count, status
├── fetch_fulltext.py    # local tool: fetch (Europe PMC) -> guard -> chunk -> chunks.jsonl
└── README.md
```

## chunks.jsonl schema (one JSON object per line)
`{ sid, airtable_id, pmcid, license, section, chunk_id, text }`
- `section` = Introduction / Methods / Results / Discussion / … (from the article structure)
- `text` = ~200–300 words, so it fits a retrieval + LLM context window with room to spare.

## Run it (local, free, no secrets)
```bash
python3 atlas_fulltext/fetch_fulltext.py            # fetch + chunk all Chunkable studies
python3 atlas_fulltext/fetch_fulltext.py --limit 5  # try a few first
```
Input: `../atlas_gaps/licenses.csv` (the gate output). Source: Europe PMC full-text XML
(`/{PMCID}/fullTextXML`) — the open-access endpoint. Standard library only.

## Why keep this separate from index.html
The chunk store is far too large to bake into the static page. It powers the **Deep search**
(Tier-1 serverless endpoint, see `../TECH_SOLUTION_airtable.md`). The public web page keeps the
abstract-level `ATLAS_STUDIES`; full-text passages are served from here on demand.

## Deep search on the web page
`build_chunk_index.py` turns the stored passages into `chunk_index.json` — a compact
TF-IDF index the page loads **on demand** for the "Deep search" toggle in the Ask Atlas tab.
```bash
python3 atlas_fulltext/fetch_fulltext.py       # 1. fetch + chunk (CC studies)
python3 atlas_fulltext/build_chunk_index.py    # 2. build chunk_index.json
```
Then commit `chunk_index.json` and deploy it **alongside index.html** (the page fetches
`atlas_fulltext/chunk_index.json`, a relative path). Two notes:
- Deep search needs the page served over **http** (GitHub Pages) — opening index.html as a
  local file blocks the fetch.
- Re-run `build_chunk_index.py` whenever you fetch more studies, so the index stays current.

## Not stored anywhere
Full text for the 122 non-open studies. Those flow through the fact-extraction path only:
fetch → extract numbers → write to Airtable → discard text.
