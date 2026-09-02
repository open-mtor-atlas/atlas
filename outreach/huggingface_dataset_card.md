<!--
outreach/huggingface_dataset_card.md -- UNSENT DRAFT (SEO P0 Ukol 3)

WHAT THIS IS: a ready-to-paste Hugging Face Hub dataset card (the
README.md a HF dataset repo needs), plus the exact upload steps.
Nothing has been submitted or uploaded anywhere -- per the brief's hard
rule, this session never creates accounts or submits external forms.
Petr/Oliver: this is yours to review, edit, and act on by hand whenever
you're ready.

WHY: getting the corpus onto Hugging Face Datasets gives it a second,
independently-indexed home (HF datasets show up in Google Dataset
Search and in HF's own search/recommendation surfaces, and are a common
first stop for anyone building an LLM eval or RAG pipeline on curated
biomedical data) -- a legitimate, no-cost way to widen who finds this
corpus, distinct from anything that touches the live site's own SEO.

HOW TO ACTUALLY DO THIS (manual, ~15 minutes):
1. Create a Hugging Face account (or use an existing one) at
   https://huggingface.co/join -- outside this session's remit to do
   for you (rule: no account creation).
2. Go to https://huggingface.co/new-dataset, name it e.g.
   "olivers-mtor-atlas", visibility Public.
3. Upload the four files from this repo's data/exports/: studies.csv,
   studies.json, entities.csv, entities.json (re-run
   `python3 tools/seo/build_data_exports.py` first if the corpus has
   grown since this draft -- the files should always be the current
   ones from data/exports/, not stale copies).
4. Replace the repo's default README.md with everything below the
   "===CARD STARTS HERE===" line (that becomes the dataset's YAML
   metadata block + description on its Hub page).
5. Done -- no further steps, no waiting for review (HF datasets publish
   immediately, unlike a registry submission).

===CARD STARTS HERE===
---
license: cc-by-4.0
task_categories:
  - text-classification
  - question-answering
language:
  - en
tags:
  - biology
  - biomedical
  - mTOR
  - aging
  - longevity
  - autophagy
  - rapamycin
  - evidence-grading
  - curated
pretty_name: "Oliver's mTOR Atlas"
size_categories:
  - n<1K
---

# Oliver's mTOR Atlas

A curated, evidence-graded database of mTOR (mechanistic target of
rapamycin) pathway research: 354 hand-curated primary studies, each
rated by evidence tier (A = systematic review/meta-analysis, B = human
trial, C = animal model, D = mechanistic/in-vitro/review -- tier
describes study design, not a quality score), linked to a knowledge
graph of 146 pathway entities (genes/proteins, complexes, drugs,
interventions, biological processes, diseases, outcomes, organelles,
nutrients/metabolites, and conditions).

- **Homepage:** https://mtor-atlas.org
- **Curator:** Oliver Barton ([ORCID 0009-0008-2025-2148](https://orcid.org/0009-0008-2025-2148))
- **License:** CC BY 4.0
- **Dataset DOI (Zenodo, permanently versioned):** [10.5281/zenodo.22059963](https://doi.org/10.5281/zenodo.22059963)
- **Also registered with:** [bio.tools](https://bio.tools/olivers_mtor_atlas), [FAIRsharing](https://fairsharing.org/8905)

## Files

- `studies.csv` / `studies.json` -- one row per study: Atlas ID, title,
  authors, year, journal, evidence tier, study category and model
  system, DOI/PMID/PMCID, a curated one-line finding, the PubMed
  abstract, and (where extracted) AI-assisted deep-extraction fields
  (intervention, target, species, effect, dose, sample size, effect
  size, limitations).
- `entities.csv` / `entities.json` -- one row per pathway entity: name,
  type, a technical and a plain-language description, synonyms, and how
  many studies in the corpus reference it.

## Why evidence tiers, not just "included studies"

Every study in this corpus already passed a relevance/quality bar to be
included at all. The tier field answers a different question -- what
*kind* of evidence is this -- so a reader (or a downstream model) can
tell a systematic review apart from a single mechanistic cell-culture
result without reading the abstract. It is not a 1-5 quality score:
tier A-D is a study-design classification.

## Intended uses

- Fine-tuning or evaluating biomedical QA / summarization models on a
  small, high-precision, source-linked corpus (every row traces back to
  a DOI or PMID).
- Building or testing evidence-grading pipelines against a
  human-curated ground truth.
- Knowledge-graph work on the mTOR pathway (the entities file is a
  ready-made node list with study-count-weighted edges implicit in
  `studies.csv`'s content).

## Limitations

This is a curated subset, not a systematic literature review of the
entire mTOR field -- absence of a paper from this corpus is not
evidence against it. Evidence tier reflects study design, not effect
size or statistical power. The corpus is a living dataset that grows
over time; this snapshot's size and content will differ from the live
site at https://mtor-atlas.org going forward. For a permanently
versioned, citable snapshot, use the Zenodo DOI above rather than this
Hub repo's latest state.

## Citation

```bibtex
@misc{olivers_mtor_atlas,
  author       = {Barton, Oliver},
  title        = {Oliver's mTOR Atlas},
  year         = {2026},
  publisher    = {Zenodo},
  doi          = {10.5281/zenodo.22059963},
  url          = {https://doi.org/10.5281/zenodo.22059963}
}
```
