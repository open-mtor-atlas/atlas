<!--
outreach/research-square/submission-checklist.md -- UNSENT DRAFT (SEO P0 Ukol 9)
Nothing uploaded to Research Square from this session, per the brief's
hard rule.
-->

# Research Square submission checklist

**Context: two prior venues already tried and set aside for this
manuscript's content.** bioRxiv and Preprints.org both declined earlier
drafts of this material (exact rejection reasons not on file in this
repo -- see `claude/osf-preprint-draft-2026-08-29.md` in the project for
what's known). F1000Research was evaluated as a venue (2026-09-01) and
explicitly rejected by Petr on 2026-09-02 over its ~$1,268 USD
article-processing charge, even though that fee is billed only after
acceptance. **Before creating a Research Square account or uploading
anything, re-verify that Research Square's standard preprint posting
carries no author-facing fee** -- this VM has no network egress to
confirm that against Research Square's current policy page
(NEVEROVERENO). Research Square has historically operated as a free
preprint-posting service (distinct from its paid manuscript-editing/
review add-ons), unlike a journal such as F1000Research, but "has
historically" is not the same as "is confirmed today," and given
Petr's stated fee-sensitivity on this exact manuscript, this should be
the very first thing checked, not assumed.

## Steps

1. **Confirm no posting fee** (see above) before doing anything else.
2. Create or log in to a Research Square account (ORCID login is
   supported) -- Oliver/Petr does this; not something this session can
   or should do.
3. Start a new preprint submission.
4. **Category:** Life Sciences -> Cell Biology (or Bioinformatics, if
   offered as a more specific fit for a database/software resource --
   pick whichever the live form's category list actually offers;
   NEVEROVERENO on the exact current category tree).
5. **Title:** "Oliver's mTOR Atlas: an evidence-graded, gap-finding
   resource for mTOR pathway research"
6. **Article type:** select "Resource" / "Method" / "Database" if
   offered as a distinct type from "Original Research" -- match by
   meaning if the exact label differs.
7. Upload `manuscript.docx` (or `manuscript.md` converted to the
   platform's preferred format, if docx is not accepted directly).
8. **License:** CC BY 4.0.
9. **Declarations:** funding -- none; competing interests -- none;
   ethics approval -- not applicable (no human/animal subjects research
   performed by the author; the corpus is a curation of already-
   published third-party studies).
10. **Keywords:** mTOR, mTORC1, mTORC2, evidence grading, knowledge
    graph, gap analysis, retrieval-augmented generation, curated
    database, aging biology.
11. **Data availability statement:** point to the Zenodo DOI
    (https://doi.org/10.5281/zenodo.22059963).
12. Review the auto-generated PDF preview before final submission --
    Research Square typically posts within a few business days without
    peer review (it is a preprint server, not a journal).

## Manuscript stats to sanity-check the PDF preview against

(All computed from repo data by
`tools/seo/build_research_square_manuscript.py` -- re-run it and
re-generate this checklist if these have changed since.)

- 354 studies, 146 pathway entities
  (46 with standalone pages)
- 310/354 (87.6%) have a PMID;
  180/354 (50.8%) have a PMCID
- Current validator run: 17 findings, 0 ERROR
