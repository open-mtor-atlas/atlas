<!--
outreach/bioregistry/new-prefix.md -- UNSENT DRAFT (SEO P0 Ukol 8.1)
WHAT THIS IS: field values for a new-prefix request to Bioregistry
(https://github.com/biopragmatics/bioregistry/issues/new/choose -->
"New Prefix" issue template). Nothing submitted -- no GitHub issue
opened from this session, per the brief's hard rule.
-->

# Bioregistry new-prefix request: mtoratlas

**Prefix:** `mtoratlas`

**Name:** Oliver's mTOR Atlas

**Homepage:** https://mtor-atlas.org/

**Description:** An evidence-graded database of curated primary research
studies on mTOR (mechanistic target of rapamycin) signaling. Each study
record is graded by evidence tier (A = systematic review/meta-analysis
through D = mechanistic/in-vitro) and linked to the pathway entities and
processes it involves. 354 studies, 146 pathway entities. Free,
non-commercial, no login required.

**Example local unique identifier:** `ABR2026`
(a real study SID from the corpus)

**URI format string:** `https://mtor-atlas.org/study/$1/`

**Regex pattern:** `^[A-Z]+\d{4,8}[A-Z]?$`

NOTE on the pattern: the brief's suggested starting pattern
(`^[A-Z]+\d{4}[A-Z]?$`, exactly 4 digits) does **not** match all 354
SIDs -- one record uses a clinical-trial NCT identifier as its SID
(`NCT05835999`, 8 digits). I widened the digit-count quantifier to
`{4,8}` and re-verified it against every one of the 354 SIDs in
`atlas_data/studies_baked.json` (0 non-matches, 0 duplicates, 0
lowercase). Use the widened pattern above, not the brief's original.

**License:** CC BY 4.0

**Contact:** Oliver Barton (ORCID: [0009-0008-2025-2148](https://orcid.org/0009-0008-2025-2148))

**Additional context for the reviewer (not a form field):** Also
registered with FAIRsharing (ID 8905) and bio.tools (ID
`olivers_mtor_atlas`). Dataset DOI (Zenodo): 10.5281/zenodo.22059963.

## Manual next steps for Petr/Oliver

1. Open a new issue at
   https://github.com/biopragmatics/bioregistry/issues/new/choose,
   pick the "New Prefix" template, and paste the fields above into the
   matching form fields (the template's exact field labels may differ
   slightly from this draft's headings -- match by meaning, not by
   exact wording, since this VM has no network egress to confirm the
   template's current exact field names).
2. Bioregistry maintainers typically review within days to a few weeks;
   no account beyond a GitHub login is required.
