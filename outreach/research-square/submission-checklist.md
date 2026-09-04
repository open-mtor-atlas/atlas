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
acceptance.

**VERIFIED LIVE 2026-09-03: no fee.** researchsquare.com/researchers/preprints
states plainly, as of today: "Our preprints are: Free to post / Posted
in full-text HTML / Issued a DOI / Indexed in Google Scholar, Meta,
Researcher, Europe PMC, PubMed (Covid-related research), and Scite /
Screened for complete author information, appropriate declaration
statements, and potential risks to human health." No mention of any
author-facing charge anywhere on the site's preprint pages -- the paid
offerings (AJE Professional Editing, AJE Rubriq, Research Promotion)
are clearly separate, optional add-on services, not a condition of
posting. The fee concern that killed F1000Research does not apply
here.

## Steps

1. ~~Confirm no posting fee~~ -- DONE, verified free (see above).
2. Create or log in to a Research Square account -- Oliver/Petr does
   this; not something this session can or should do. **Verified live
   2026-09-03:** it's a standard email+password registration
   (First Name, Last Name, Email, Password, Institution, Country,
   agree to Terms), NOT ORCID single-sign-on -- ORCID iD is just one
   optional field on the form, not a login method. Sign-up URL:
   https://www.researchsquare.com/signup (typing the manuscript title
   on /submit first and clicking "Get Started" redirects here with the
   title carried through, so it's pre-filled once the account exists).
3. Start a new preprint submission.
4. **Category / "area of study":** Life Sciences -> Cell Biology (or
   Bioinformatics/Computational Biology, if offered as a more specific
   fit for a database/software resource -- pick whichever the live
   form's category list actually offers once past the account/login
   wall; the exact current category tree still needs checking from
   inside the logged-in flow).
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

## Verified live (2026-09-03), from https://www.researchsquare.com/submit

The submission wizard is exactly these steps, confirmed from the live
(logged-out) page before it redirects to sign-up:
1. Upload a manuscript file
2. Add title for your preprint
3. Add article type for your preprint
4. Add area of study for your preprint
5. Add author information for your preprint
6. Add abstract for your preprint
7. Add keywords for your preprint
8. Add the figure files for your preprint
9. Add supplementary files for your preprint
10. Add institution information
11. Add funder information
12. Add the necessary declarations
13. Add the necessary competing interests
14. Submit

## Manuscript stats to sanity-check the PDF preview against

(All computed from repo data by
`tools/seo/build_research_square_manuscript.py` -- re-run it and
re-generate this checklist if these have changed since.)

- 354 studies, 146 pathway entities
  (46 with standalone pages)
- 310/354 (87.6%) have a PMID;
  180/354 (50.8%) have a PMCID
- Current validator run: 17 findings, 0 ERROR
