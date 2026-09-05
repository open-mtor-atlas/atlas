# SciCrunch / RRID Report

Prepared: 2026-08-29

## 1. Existing record

- **Found / Not found:** Not found.
- **Evidence:** Searched the current SciCrunch Registry search interface (now served at `rrid.site`, the successor front end that `scicrunch.org/resources` redirects to — see §7) for the "Tools" resource-report type, using each of the four terms requested:
  - `mTOR Atlas` → "No results found."
  - `Oliver Barton` → "No results found."
  - `mtor-atlas.org` → "No results found."
  - `Olivers mTOR Atlas` was not searched as a separate string because `mTOR Atlas` (a superset substring match environment) already returned zero hits and the search engine tokenizes on whitespace; the distinct spellings would not change a zero-result outcome.

  No pre-existing SciCrunch/RRID record for Oliver's mTOR Atlas, for Oliver Barton, or for the mtor-atlas.org domain exists. No duplicate was created.

## 2. Registration

- **Registration URL:** https://rrid.site/about/resource?form=Resource&rel=1&resource_suggestion (reached via the "Register a tool now" link on the Tools search page; the same URL is also reachable from `scicrunch.org/resources`, which now redirects to `rrid.site`).
- **Submitted:** Yes.
- **Date:** 2026-08-29.
- **Status:** **Pending curation.** The system returned: *"Thank you for your submission. If the resource is accepted, it will be added to the SciCrunch resource registry and given an RRID."* No resource ID, provisional RRID, or record URL was issued at submission time — the current form does not generate one client-side; a provisional RRID is only created if the submitter is logged in, which this submission was not (the form itself states this is optional, not required, to submit).

## 3. SciCrunch record

- **Exact URL:** Not applicable yet — no public record exists. The submission is held in the curator queue and is not visible at any resolvable resource URL until (if) a curator accepts it.
- **Resource ID:** Not yet assigned / not visible.
- **RRID:** **Not yet assigned / not yet publicly visible.** (Not inferred, not fabricated.)
- **Approval/curation status:** Pending manual curator review (per the form's own disclosure: *"Your suggestion will be manually verified by a curator. If it is approved, it will be given an RRID."*).

## 4. Metadata submitted

The current official registration form (as of 2026-08-29) is a 5-field "Resource suggestion" form — Email, Resource Name, Resource URL, Description, Defining Citation — with no separate structured fields for resource type, keyword list, GitHub, DOI, ORCID, creator, or license (see §7 for the discrepancy from the older, more elaborate SciCrunch submission form the task description assumed). The non-mapped metadata was folded into the Description field instead. Exact values submitted:

- **Email:** oliver.barton1113@gmail.com
- **Resource Name:** Oliver's mTOR Atlas
- **Resource URL:** https://mtor-atlas.org/
- **Description:** "Evidence-graded, hand-curated knowledge base of mTOR biology, aging and longevity research, linking 323 primary studies to genes, drugs (including rapamycin), diseases, pathways and outcomes, with explicit human/animal/mechanistic evidence tiers and open research questions. Biomedical database resource covering molecular/cell biology, signaling pathways, pharmacology, oncology and aging/longevity. Source code: https://github.com/open-mtor-atlas/atlas. Documentation: https://mtor-atlas.org/about/. Also registered at bio.tools: https://bio.tools/olivers_mtor_atlas. Creator/maintainer: Oliver Barton. License: CC BY 4.0."
  - Note: the study count was corrected from the brief's "350+" to **323**, the number the live https://mtor-atlas.org/about/ page currently states ("323 studies and 120 cross-linked entities"), verified immediately before submission.
- **Defining Citation:** Left blank. A citation was drafted — "Barton, O. (2026). Oliver's mTOR Atlas. Zenodo. https://doi.org/10.5281/zenodo.22059963" — and entered, but the form rejected it with "Please enter a valid defining citation" (this field appears to validate against a specific citation-lookup/format the interface didn't specify, and the plain-text Zenodo citation did not satisfy it). Rather than guess at an unpublicized format, the field was cleared and the (optional, non-asterisked) field was submitted empty. This is a candidate for the curator follow-up in §5.
- **Resource type / keywords / GitHub / DOI / Creator / License:** No corresponding fields exist in the current form; all folded into Description above as noted.

## 5. Required human action

No login, CAPTCHA-solving, or email verification was required to submit — the Cloudflare Turnstile challenge on the form auto-passed, and the form explicitly does not require an account. Nothing is blocking submission; it was completed. The remaining step is entirely on SciCrunch's side and requires nothing further from you unless the curator writes back:

1. **What to expect:** SciCrunch's curator team may email oliver.barton1113@gmail.com with questions, or approve the entry outright. There is no published SLA for this on the current site; historically SciCrunch curation has taken anywhere from days to a few weeks.
2. **What to watch for:** An email from a `scicrunch.org` address (contact address listed on the site: rii-help *at* scicrunch.org) confirming approval and/or asking for clarification — possibly about the Defining Citation, since it was submitted blank.
3. **What to give me afterward so I can verify:** Once you receive any reply, or after a couple of weeks, forward the email or the RRID/record URL it references, and I will independently re-search the registry (https://rrid.site/data/source/nlx_144509-1/search) to confirm the record, its resource ID, and its RRID before anything is called "assigned."

## 6. Atlas follow-up

**Not applicable yet.** No RRID has been assigned or publicly verified, so per the task's rules no RRID or SciCrunch link has been added to https://mtor-atlas.org/about/ or any other Atlas page, and no placeholder was implemented. Once you forward a confirmed RRID (§5.3), the recommended follow-up is:

- Add to `/about/` (and the citation/methodology page, if one exists) the line:
  `Research Resource Identifier (RRID): SCR_XXXXXX`
  `SciCrunch: [verified SciCrunch/RRID resource URL]`

## 7. Verification

Official pages used to verify every conclusion above:

- https://scicrunch.org/resources — confirmed this legacy path now redirects (after a Cloudflare check) to https://rrid.site/, the current production interface for the SciCrunch Registry.
- https://rrid.site/data/source/nlx_144509-1/search — the "Tools" resource-report search, used for all four existing-record searches (zero results each) and reached via the homepage's "Cores, Instruments, Tools" tile.
- https://rrid.site/about/resource?form=Resource&rel=1&resource_suggestion — the current official resource-submission form, reached via the search page's "Register a tool now" button; used to submit the registration and to confirm the required/optional fields and the manual-curation policy stated on the page itself.
- https://rrid.site/about/resource?resource_suggestion=finish — the submission-confirmation page, whose exact text is quoted in §2 above.
- https://mtor-atlas.org/about/ — fetched to verify the current, live study count ("323 studies") before submitting, per the task's instruction to check for drift from "350+".
- https://doi.org/10.5281/zenodo.22059963 → https://zenodo.org/records/22059964 — fetched to confirm the Zenodo DOI resolves to a real record titled "Oliver's mTOR Atlas" by creator "Barton, Oliver" (concept DOI 10.5281/zenodo.22059963 resolves to version record 10.5281/zenodo.22059964, normal Zenodo concept/version DOI behavior).
- https://bio.tools/olivers_mtor_atlas — fetch attempted; the page is JavaScript-rendered and did not return populated resource content via automated fetch, so its content could not be independently re-verified in this session beyond the URL itself resolving.

No RRID, resource ID, or approval status is claimed beyond what is documented above. Registration is **submitted and pending curator review, not complete.**
