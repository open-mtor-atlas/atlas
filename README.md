# Oliver's mTOR Atlas

A curated, evidence-graded database of mTOR pathway research. Every study is rated by evidence tier - from systematic reviews and meta-analyses down to mechanistic and in-vitro work - and traced back to its primary source, alongside a knowledge-graph view of genes, diseases, and interventions, plus a set of AI-identified open questions with proposed testable experiments.

**Live site:** https://mtor-atlas.org

[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.22059963.svg)](https://doi.org/10.5281/zenodo.22059963)

## What's inside

- 360+ hand-curated primary studies on the mTOR signaling pathway (mTORC1/mTORC2, autophagy, rapamycin and related interventions), each labelled by the kind of study behind it and linked back to its DOI/PubMed record.
- A knowledge-graph view connecting genes, diseases, and interventions.
- An "open questions" layer - evidence gaps identified across the corpus, each paired with a proposed testable experiment.
- A citation-grounded research assistant that answers pathway questions using only the indexed corpus, with links back to source studies.

## Evidence grading

Studies are hand-selected from PubMed / Europe PMC and labelled by **study design**, not by quality, importance, or citation count:

- **S** - synthesis of human data (systematic review / meta-analysis)
- **H** - human study (clinical trial or observational)
- **A** - animal model
- **M** - molecular / in-vitro (mechanistic)
- **R** - review

These codes ran A-D until September 2026. They were renamed because a lettered ladder reads as a quality grade, which it never was, and because the old bottom tier merged primary mechanistic work with narrative reviews - two different kinds of claim. The change was prompted by an external critique from a researcher in the field; the underlying data was not re-graded, only the labels shown to readers.

A mechanistic paper is not "worse" than a trial. The code says what kind of claim a study can support, not how good it is.

## About this project

Built and maintained independently by Oliver, a high-school student, together with his father Petr. Not affiliated with any lab, company, or institution. Feedback on the evidence grading, missing studies, or anything that looks wrong is very welcome - please open an issue. See [CONTRIBUTING.md](CONTRIBUTING.md).

## Citing this dataset

If you use this dataset, please cite it via its Zenodo record: https://doi.org/10.5281/zenodo.22059963

A single page with all identifiers, registrations (bio.tools, FAIRsharing, GitHub, ORCID) and a ready-to-use citation is at https://mtor-atlas.org/data/.

## License

This repository is dual-licensed, because it contains two different kinds of thing:

- **Curated content and data** - the study records, evidence grades, curated prose, gap hypotheses, and everything under `atlas_data/` and the generated pages - are licensed under **CC BY 4.0** (see [LICENSE](LICENSE)): https://creativecommons.org/licenses/by/4.0/
- **Source code** - the Python generators, validation and verification scripts, and site JavaScript - is licensed under the **MIT License** (see [LICENSE-CODE](LICENSE-CODE)).

If you reuse the data, attribute it. If you reuse the code, MIT terms apply.
