# Oliver's mTOR Atlas -- data exports

Machine-readable exports of the curated corpus behind
[Oliver's mTOR Atlas](https://mtor-atlas.org/), generated from the same source data as
the live site. Regenerated on every deploy by
`tools/seo/build_data_exports.py` -- if you're reading this from a
downloaded copy, check https://mtor-atlas.org/data/ for the current version.

## Files

- **studies.csv / studies.json** -- 354 hand-curated
  primary studies on the mTOR signaling pathway. Each row: Atlas ID
  (`sid`), title, authors, year, journal, evidence tier (A = systematic
  review/meta-analysis, B = human trial, C = animal model, D =
  mechanistic/in-vitro/review -- tier describes study design, not
  quality), study category and model system, DOI/PMID/PMCID, the
  curated one-line finding, the PubMed abstract, and (where extracted)
  AI-assisted deep-extraction fields: intervention, target, species,
  effect, dose, sample size, effect size, and limitations. `atlas_url`
  links back to the full record page.
- **entities.csv / entities.json** -- 146 pathway
  entities (genes/proteins, complexes, drugs, interventions, biological
  processes, diseases, outcomes, organelles, nutrients/metabolites,
  conditions) referenced across the corpus, with a technical and a
  plain-language description, synonyms, how many studies link to each,
  and `atlas_url` when the entity has its own page (entities linked
  from fewer than 3 studies don't get a standalone page
  on the live site and so have no `atlas_url` here).

## License & citation

CC BY 4.0 -- free to use, share and adapt, including commercially, with
attribution. Cite as:

Barton, O. ({year}). *Oliver's mTOR Atlas* [Data set]. Zenodo.
https://doi.org/10.5281/zenodo.22059963

Full details: https://mtor-atlas.org/data/ and https://mtor-atlas.org/CITATION.cff.

## Caveats

- Evidence tier is a study-DESIGN classification, not a quality grade
  (a well-run tier-C animal study is not "worse" than a poorly-run
  tier-B human one on every axis -- tier just says what kind of
  evidence it is).
- "Record last updated" dates on individual study pages (not included
  in this export) are approximate for older records -- see
  https://mtor-atlas.org/study/ pages for the caveat, or the site's changelog files.
- This is a living dataset; corpus size and content change as new
  studies are curated. The formally versioned, permanently citable
  snapshot is the Zenodo archive (DOI above), not this export.
