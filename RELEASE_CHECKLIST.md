# Cutting a dataset release

Since 17 October 2026 the version the API reports (`dataset_version`) is
derived, not typed by hand. `release_status.py` runs in `deploy.bat` after
the pathway model is built and compares a content fingerprint of the live
data with the fingerprint of the latest release in `atlas_data/releases.json`.

| live data vs. latest release | `dataset_version` | `live_matches_release` |
|---|---|---|
| identical | `2.0.1` | `true` |
| changed since | `2.0.1+unreleased` | `false` |

The fingerprint (`sha256/canonical-json/v1`) covers what the API serves:
`studies_baked`, `entities_baked`, `gaps_baked`, `frontier_baked`,
`relations_baked` and `pathway/model.json`, without generator timestamps.
Two deploys with the same data give the same fingerprint.

## Steps for a new release (e.g. 2.0.2)

1. Run `deploy_all.bat` so `main` holds exactly the state to archive.
2. CITATION.cff: set `version: "2.0.2"` and `date-released`. Leave the
   version DOI for step 5. Do not deploy between this step and step 5:
   `release_status.py --check` stops the deploy while CITATION.cff names a
   version that is not in `releases.json`.
3. Commit and push CITATION.cff, tag `v2.0.2` on that commit, and publish
   the GitHub release. Zenodo archives the tag and mints a version DOI.
4. `py release_status.py --ref v2.0.2` prints the fingerprint, counts and
   commit of the tagged state.
5. Add an entry to `atlas_data/releases.json` with that output plus
   `version`, `tag`, `date` and `version_doi`, and add the version DOI to
   the `identifiers` in CITATION.cff.
6. `py release_status.py --check`, then `deploy_all.bat`. Check
   `/api/v1/meta.json`: `dataset_version` must be `2.0.2` and
   `live_matches_release` must be `true`.

## Checking an archive

Download the Zenodo zip and unpack it. Then

    py release_status.py --dir <unpacked folder>

prints the archive's fingerprint and counts and names the release in
`releases.json` it matches (exit code 1 if none). The Zenodo zip wraps the
repository in one top-level folder; point `--dir` at that folder.
