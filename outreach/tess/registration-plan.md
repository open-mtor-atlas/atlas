<!--
outreach/tess/registration-plan.md -- verified 2026-09-03
Supersedes the "submit atlas-academy.json manually" assumption in
docs/SEO_P0_HANDOVER_2026-09.md Ukol 6 / manual step 6.
-->

# TeSS registration -- verified approach

**Live-checked on tess.elixir-europe.org (2026-09-03).** TeSS offers two
registration paths (see https://tess.elixir-europe.org/about/registering):

1. **Automatic registration** via a Bioschemas-structured source URL that
   TeSS periodically crawls/ingests.
2. **Manual registration** -- log in, then use "Register material" /
   "Register event" to paste in each item one at a time (this is what
   `outreach/tess/atlas-academy.json`'s 11 entries were originally
   drafted for).

**Recommendation: use path 1, not path 2.** Reasons:
- The site already emits live Bioschemas `TrainingMaterial`/`Course`
  JSON-LD on every Academy page (verified live on
  `/academy/core/what-is-mtor/`: `"@type":
  ["LearningResource","TrainingMaterial"]`, `"learningResourceType":
  "e-learning"`, `keywords`, `audience` all present -- this was Ukol 6's
  work, already deployed).
- A sitemap already exists at
  `https://mtor-atlas.org/sitemap-academy.xml`, listing exactly the 14
  Academy URLs (course index, 10 lessons, 1 research-challenges page +
  its 1 challenge).
- Once registered as a TeSS "Source" with ingestion method
  "Bioschemas", TeSS re-crawls this automatically -- new lessons added
  later appear in TeSS without any manual re-submission. Manual
  registration (path 2) is a one-time snapshot that goes stale.

## Steps (requires a human -- account creation, not automatable here)

1. Register a free TeSS account (or log in) at
   https://tess.elixir-europe.org/users/sign_up -- "Members of academic
   institutions may be able to log in via LS-Login" is also offered.
2. Go to "Register provider" (https://tess.elixir-europe.org/content_providers/new
   once logged in) and register **Oliver's mTOR Atlas** / **mTOR
   Academy** as a content provider. Suggested field values:
   - Name: `Oliver's mTOR Atlas -- mTOR Academy`
   - Homepage: `https://mtor-atlas.org/academy/`
   - Description: reuse the Academy's own tagline/description (see
     `academy_data/lessons.json` or the live `/academy/` page).
3. On the new provider's **Sources** tab, register a new Source:
   - URL: `https://mtor-atlas.org/sitemap-academy.xml`
   - Ingestion method: **Bioschemas**
4. Submit for approval. Per TeSS's own docs: "a source will need to be
   approved by an administrator before it is active, but can be tested
   to see exactly what metadata TeSS can extract from the source" --
   use the "test" function first to confirm all 14 pages parse cleanly
   before waiting on admin approval.

## Fallback

If the Bioschemas source is rejected or doesn't parse correctly,
`outreach/tess/atlas-academy.json` remains available as the manual
fallback (path 2, one entry at a time via "Register material").

## Status

DONE -- 2026-09-21. Petr logged in to tess.elixir-europe.org as OliverPrague;
Claude filled in the rest via Claude in Chrome (same Chrome profile/session):

1. Registered content provider "Oliver's mTOR Atlas -- mTOR Academy"
   (https://tess.elixir-europe.org/content_providers/oliver-s-mtor-atlas-mtor-academy),
   Type: Project, URL https://mtor-atlas.org/academy/, contact
   oliver.barton1113@gmail.com, keywords mTOR / signal transduction / aging biology.
2. Added a Source (id 75) on the provider: URL
   https://mtor-atlas.org/sitemap-academy.xml, ingestion method Bioschemas, enabled,
   default language English.
3. Ran "Test Source" before requesting approval: 18 URLs in the sitemap, parsed into
   11 Courses / 11 CourseInstances / 13 LearningResources. Only the 3 non-lesson app
   pages (/academy/, /academy/badges/, /academy/progress/) had no Bioschemas markup,
   which is expected -- they're UI shells, not lessons.
4. Clicked "Request Approval" -- confirmed "Approval request was sent successfully.",
   status is now "Approval requested", pending a TeSS administrator.

Nothing left to do here until an admin approves the source. Once approved, TeSS
re-crawls the sitemap automatically -- no manual re-submission needed when new
lessons are added. Fallback path 2 (outreach/tess/atlas-academy.json, manual
"Register material") is unused and can stay as a backup only if this source ever
gets rejected.
