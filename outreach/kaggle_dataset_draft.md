<!--
outreach/kaggle_dataset_draft.md -- UNSENT DRAFT (SEO P0 Ukol 3)

WHAT THIS IS: exact copy for Kaggle's "New Dataset" form fields, plus
upload steps. Nothing has been submitted -- per the brief's hard rule,
this session never creates accounts or submits external forms. This is
for Petr/Oliver to review and submit by hand.

HOW TO ACTUALLY DO THIS (manual, ~10 minutes):
1. Create a Kaggle account (or use an existing one) at
   https://www.kaggle.com -- outside this session's remit (rule: no
   account creation).
2. Go to https://www.kaggle.com/datasets -> "New Dataset".
3. Upload the four files from data/exports/: studies.csv, studies.json,
   entities.csv, entities.json (re-run
   `python3 tools/seo/build_data_exports.py` first if the corpus has
   grown since this draft).
4. Fill the form fields exactly as below.
5. Submit -- Kaggle datasets publish immediately (no review queue),
   unlike a formal registry submission.

===FORM FIELDS===

Title:
  Oliver's mTOR Atlas

Subtitle (max ~120 chars):
  354 evidence-graded studies + 146 pathway entities on mTOR signaling, aging, and rapamycin

Description (paste as-is, Markdown supported):

  A curated, evidence-graded database of mTOR (mechanistic target of
  rapamycin) pathway research. Every study earned its place through
  manual curation, not a keyword search -- and every included study is
  rated by evidence tier (A = systematic review/meta-analysis, B =
  human trial, C = animal model, D = mechanistic/in-vitro/review; tier
  describes study design, not a 1-5 quality score) and linked to a
  knowledge graph of genes, proteins, complexes, drugs, interventions,
  biological processes, diseases, outcomes, organelles, and
  nutrients/metabolites.

  **What's included:**
  - `studies.csv` / `studies.json` -- 354 studies: title, authors,
    year, journal, evidence tier, study category/model, DOI/PMID/PMCID,
    a curated one-line finding, the PubMed abstract, and (where
    available) AI-assisted deep-extraction fields: intervention,
    target, species, effect, dose, sample size, effect size,
    limitations.
  - `entities.csv` / `entities.json` -- 146 pathway entities with
    technical + plain-language descriptions, synonyms, and study-count
    per entity.

  **Live, browsable version:** https://mtor-atlas.org (every row here
  links back to a full record page there).

  **Curator:** Oliver Barton (ORCID 0009-0008-2025-2148).

  **Citation:** Barton, O. (2026). *Oliver's mTOR Atlas* [Data set].
  Zenodo. https://doi.org/10.5281/zenodo.22059963

License: CC BY 4.0 (Kaggle's own "Attribution 4.0 International
  (CC BY 4.0)" license option)

Tags/categories to select: biology, health, medicine, aging,
  research (Kaggle's tag picker -- pick whichever subset of these
  exist as exact Kaggle tags at submission time; the list may have
  changed since this draft was written)

Visibility: Public
