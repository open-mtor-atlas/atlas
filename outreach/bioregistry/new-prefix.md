<!--
outreach/bioregistry/new-prefix.md -- UNSENT DRAFT (SEO P0 Ukol 8.1)
WHAT THIS IS: field values for a new-prefix request to Bioregistry
(https://github.com/biopragmatics/bioregistry/issues/new/choose ->
"New Prefix" issue template). Nothing submitted -- no GitHub issue
opened from this session, per the brief's hard rule.

2026-09-02 update: fetched the live issue template
(.github/ISSUE_TEMPLATE/new-prefix.yml on biopragmatics/bioregistry)
to confirm the actual field list, which is longer than originally
assumed. All 20 fields are mapped below, in the template's own order.
-->

# Bioregistry new-prefix request: mtoratlas

Paste field-by-field into https://github.com/biopragmatics/bioregistry/issues/new/choose
-> "New Prefix" template. Fields marked **(fill in)** need a value only
Petr/Oliver can supply -- not guessed here.

1. **Prefix:** `mtoratlas`

2. **Name:** Oliver's mTOR Atlas

3. **Homepage:** https://mtor-atlas.org/

4. **Source Code Repository:** https://github.com/open-mtor-atlas/atlas
   (confirmed public, 2026-09-02)

5. **Description:** An evidence-graded database of curated primary
   research studies on mTOR (mechanistic target of rapamycin)
   signaling. Each study record is graded by evidence tier (A =
   systematic review/meta-analysis through D = mechanistic/in-vitro)
   and linked to the pathway entities and processes it involves. 354
   studies, 146 pathway entities. Free, non-commercial, no login
   required.

6. **License:** CC BY 4.0

7. **Publications:** none yet indexed in PubMed -- a preprint
   manuscript is in preparation (see the Research Square draft under
   `outreach/research-square/`). Leave blank or note "preprint in
   preparation."

8. **Example Local Unique Identifier:** `ABR2026` (a real study SID
   from the corpus)

9. **Regular Expression Pattern for Local Unique Identifier:**
   `^[A-Z]+\d{4,8}[A-Z]?$`

   Note for the reviewer: the brief's originally suggested pattern
   (`^[A-Z]+\d{4}[A-Z]?$`, exactly 4 digits) does not match all 354
   SIDs -- one record uses a clinical-trial NCT identifier as its SID
   (`NCT05835999`, 8 digits). Widened the digit-count quantifier to
   `{4,8}` and re-verified against every one of the 354 SIDs in
   `atlas_data/studies_baked.json`: 0 non-matches, 0 duplicates, 0
   lowercase.

10. **URI Format String:** `https://mtor-atlas.org/study/$1/`

11. **Wikidata Property:** (leave blank -- this identifier is not yet
    represented as a Wikidata property; it's a new registration, not a
    link to an existing one)

12. **Contributor Name:** Oliver Barton

13. **Contributor GitHub:** **(fill in -- your GitHub username)**

14. **Contributor ORCiD:** 0009-0008-2025-2148

15. **Contributor Email:** **(fill in)**

16. **Contact Name:** Oliver Barton

17. **Contact ORCiD:** 0009-0008-2025-2148

18. **Contact GitHub:** **(fill in -- same as Contributor GitHub)**

19. **Contact Email:** **(fill in)**

20. **Additional Comments:** Also registered with FAIRsharing (ID:
    8905) and bio.tools (ID: `olivers_mtor_atlas`). Dataset DOI
    (Zenodo, concept): 10.5281/zenodo.22059963. See field 9 above for
    a note on why the regex pattern was widened beyond the project's
    original 4-digit assumption.

## Manual next steps for Petr/Oliver

1. Fill in the three **(fill in)** fields above (GitHub username,
   email) -- not guessed here since this session doesn't have them on
   file.
2. Open a new issue at
   https://github.com/biopragmatics/bioregistry/issues/new/choose,
   pick the "New Prefix" template, and paste the fields above in
   order -- the template's field labels now match this list exactly
   (verified against the live YAML on 2026-09-02).
3. Bioregistry maintainers typically review within days to a few
   weeks; no account beyond a GitHub login is required.
