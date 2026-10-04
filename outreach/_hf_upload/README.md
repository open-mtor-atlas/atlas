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
rapamycin) pathway research: 411 hand-curated primary studies, each
classified by study type -- systematic review of human data (S), human study (H), animal model (A), or molecular/mechanistic work (M) -- a classification of study design, not a quality ranking, linked to a knowledge
graph of 149 pathway entities (genes/proteins, complexes, drugs,
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
result without reading the abstract. It is not a quality score:
the S/H/A/M/R code is a study-design classification, with no ranking
implied between the letters.

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
