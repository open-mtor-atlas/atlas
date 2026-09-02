<!--
outreach/linkout/README.md -- UNSENT DRAFT (SEO P0 Ukol 7)
Generated alongside tools/seo/build_linkout.py's output. Nothing in this
folder has been submitted, emailed, or uploaded anywhere -- per the
brief's hard rule.
-->

# NCBI LinkOut submission package

This folder is a complete, ready-to-send LinkOut provider application.
**Nothing has been sent.** Regenerate the other files by re-running
`python3 tools/seo/build_linkout.py` after any change to
`atlas_data/studies_baked.json` or `favicon.png`.

## Files

- `providerinfo.xml` -- the `<Provider>` block for the application email.
- `resources.csv` -- 310 rows, one per study with a PMID (`PrId,DB,UID,
  url,IconUrl,UrlName,SubjectType,Attribute`), format per
  https://www.ncbi.nlm.nih.gov/books/NBK3812/ (recalled from memory --
  see the NEVEROVERENO note in the script's docstring; this VM has no
  network egress to check the live docs).
- `application-email.md` -- the email text for linkout@ncbi.nlm.nih.gov.
- `icon-16x16.png`, `icon-100x20.png` -- generated from the site's live
  `favicon.png` (the actual production mark, not an unshipped concept
  from `brand/logo-concepts/`).

## Manual steps for Petr/Oliver (in order)

1. **Host the icon files.** `resources.csv`'s `IconUrl` column points to
   `https://mtor-atlas.org/outreach-assets/linkout-icon-16x16.png` --
   this path does not exist on the live site yet. Copy
   `icon-16x16.png` to that path (e.g. as
   `outreach-assets/linkout-icon-16x16.png` at the repo root, or
   wherever fits the site's static-asset convention) as part of the
   next deploy, before submitting.
2. **Send the application email** (`application-email.md`'s content) to
   linkout@ncbi.nlm.nih.gov, with `providerinfo.xml`, `resources.csv`,
   and both icon PNGs attached.
3. **Wait for NCBI's approval reply.** They will assign a real
   `ProviderId`, replacing the `00000` placeholder used throughout this
   draft.
4. **Substitute the real ProviderId** into `providerinfo.xml`'s
   `<ProviderId>` and every `PrId` value in `resources.csv` (a
   find-and-replace, or re-run the build script with the constant
   updated), then upload the corrected `resources.csv` via the FTP
   process NCBI's approval email describes.
5. Re-check `SubjectType` (currently `Data resource`) and `Attribute`
   (currently blank) against NCBI's current documented enum values
   before the final upload -- flagged NEVEROVERENO, see the script's
   docstring.
