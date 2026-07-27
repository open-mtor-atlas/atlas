# Phase 0 — data preparation (done)

*Date: 2026-07-08. Source: Airtable base "mTOR Studies" (Studies table) + PubMed/PMC ID conversion.*

## What was produced

| File | Contents |
|---|---|
| `studies_enriched.jsonl` | 250 studies, 1 line = 1 study, machine-readable for embeddings |
| `studies_enriched.csv` | same as a table (Excel/Sheets) |

Each record has: `airtable_id, Study_ID, Title, Authors, Year, Journal, Category, Model, Related_Entities, Evidence_Tier, Pyramid_Level, Peer_Reviewed, DOI, PMID, PMCID, fulltext_pmc_available, Abstract_PubMed, Key_Finding` and a ready-made **`embedding_text`** field (Title + Key finding + Abstract combined — the direct input for embeddings).

## Corpus quality

The data is in surprisingly good shape — nothing essential is missing:

- **250 / 250** have a title, DOI, abstract (from PubMed), and Key_Finding
- **249 / 250** have a year (1 missing)
- so "filling in abstracts" **is unnecessary** — they are all already there

## Full-text availability (key for Phase 4)

Via DOI → PMID/PMCID I checked how many studies have a **legally and freely available full text in PubMed Central**:

- **163 / 250 (65%)** have a PMC full text → they can later be downloaded and chunked by section
- **87 / 250 (35%)** are abstract-only for now (paywall / not in PMC) → they stay at the abstract level

Breakdown by strength of evidence (how many have full text):

| Evidence_Tier | Full text / total |
|---|---|
| A – Systematic review | 0 / 1 |
| B – Human | 13 / 22 |
| C – Animal | 40 / 51 |
| D – Mechanistic/Review | 110 / 173 |
| Preprint | 0 / 2 |
| Registered trial | 0 / 1 |

> Note: 65% is decent coverage. For the remaining 35%, Phase 4 can try Unpaywall (which often finds a legal copy elsewhere). For an abstract-based MVP this doesn't matter — we start on all 250.

## Notes
- 1 "DOI" was actually a clinical-trial identifier (`NCT05835999`, registered trial) — it has no PMID, which is expected.
- Before embedding, PMCID is also useful as a stable key for citations (PMID/PMCID are permanent).

## Next step
Phase 1 — turn `embedding_text` into embeddings (free, local) → local vector DB → a simple chat with 4 sections and citations. Say the word and I'll get it going.
