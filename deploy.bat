@echo off
REM ============================================================
REM  Deploy the Open mTOR Atlas to GitHub Pages.
REM  Pushes the two files the live site needs:
REM      index.html                       (the page: abstract RAG + gaps)
REM      atlas_fulltext\chunk_index.json  (the Deep-search full-text index)
REM
REM  Steps:
REM   0) merge in anything anyone else pushed since your last sync
REM      -> reconcile_with_origin.py; stops only on a real conflict
REM   1) (optional) refresh baked data from Airtable   -> if AIRTABLE_TOKEN is set
REM   2) rebuild the Deep-search chunk index           -> best effort
REM   3) gate on validate_claims.py - refuse to ship claims stronger than
REM      the evidence behind them
REM   4) back up index.html + chunk index, VERIFY the backup is complete
REM   5) move HEAD to origin/main WITHOUT touching the working tree
REM   6) VERIFY again, stage the whole site incl. pre-rendered pages and every
REM      tracked pipeline output, commit, push
REM
REM  Verification (added 2026-07-13): this repo's folder is OneDrive-synced,
REM  and large writes to index.html have repeatedly been silently truncated
REM  mid-file (incident: commit 11fc84f went live missing its closing
REM  html tag and the site broke -- nothing rendered). verify_index_html.py
REM  now gates every commit: if it reports a problem, this script stops
REM  BEFORE committing or pushing instead of shipping a broken file.
REM
REM  NOTE: keep parentheses OUT of any echo text that sits inside an
REM  if (...) ( ... ) block below -- cmd.exe parses the whole block as one
REM  unit and a stray unescaped paren anywhere inside breaks parsing with
REM  "was unexpected at this time", even if that branch never executes.
REM
REM  Target: https://github.com/open-mtor-atlas/atlas  (branch main)
REM  Use ONLY this script (replaces earlier deploy_*.bat / git_*.bat).
REM ============================================================
cd /d "%~dp0"

echo.
echo === Housekeeping: clearing stray git temp objects ===
REM  When a Cowork sandbox session writes git objects through the FUSE bridge to
REM  this Windows folder it can create the object but not unlink its temp file,
REM  leaving .git\objects\??\tmp_obj_* behind - harmless orphans git ignores,
REM  but they accumulate. Deleting them natively from Windows works fine, so the
REM  repo self-cleans on every deploy.
if exist ".git\objects" del /f /q /s ".git\objects\tmp_obj_*" >nul 2>&1
echo    done

echo.
echo === Removing any stuck git locks ===
REM  MUST BE THE FIRST GIT-RELATED STEP. This block used to sit ~100 lines lower,
REM  below the deploy.bat and index.html gates -- which meant those gates ran
REM  while a stale lock was still in place. Observed 2026-07-29: a leftover
REM  refs\remotes\origin\main.lock made the gate's `git fetch` fail silently
REM  (it is redirected to nul), so origin/main still pointed two commits back and
REM  the gate compared deploy.bat against an old blob and aborted a deploy that
REM  was in fact perfectly in sync. A gate reading stale data is worse than no
REM  gate: it fails closed on a healthy repo and teaches you to distrust it.
REM
REM  index.lock alone is not enough: a killed git also leaves ORIG_HEAD.lock or a
REM  ref lock behind, and `git reset` then fails with "Another git process
REM  seems to be running" while this script carries on regardless. Confirmed
REM  2026-07-27: a week-old ORIG_HEAD.lock silently broke every deploy.
del /f /q ".git\index.lock" 2>nul
del /f /q ".git\ORIG_HEAD.lock" 2>nul
del /f /q ".git\HEAD.lock" 2>nul
del /f /q ".git\refs\heads\main.lock" 2>nul
REM  A Cowork session that pushes through the FUSE bridge can leave these two
REM  behind: it creates the object or ref but cannot unlink the lock. Neither
REM  blocks a push, but origin/main.lock stops `git fetch` updating the
REM  remote-tracking ref, which is what poisoned the gate above.
del /f /q ".git\refs\remotes\origin\main.lock" 2>nul
del /f /q ".git\objects\maintenance.lock" 2>nul

set "COMMIT_MSG=Atlas update %date% %time%"

echo.
echo === Reconciling with anything pushed since your last sync ===
REM  Added 2026-08-26. Before this, a push from another machine or another
REM  Cowork session simply stopped the deploy dead further down with
REM  "ABORTED: index.html on GitHub has changed since your last sync -- git pull,
REM  reconcile or reapply your edits". That is not an instruction anyone can
REM  follow: the local edit is a 670 KB machine-generated ATLAS_STUDIES line.
REM
REM  reconcile_with_origin.py does the reconciling instead: a per-file three-way
REM  merge of base = merge-base, theirs = origin/main, ours = the working tree.
REM  Untouched files take theirs; generated artifacts keep ours because ours is
REM  the newer build; index.html gets a real textual merge with the machine
REM  stamps neutralised first, so a re-baked timestamp can never collide with
REM  somebody's prose edit on the adjacent line. It then moves HEAD to
REM  origin/main with the same MIXED reset this script does further down, so the
REM  commit below lands cleanly on top of what everyone else pushed.
REM
REM  It plans everything before writing anything: a genuine conflict leaves the
REM  working tree byte-for-byte untouched and stops here, which is the ONLY case
REM  that now needs a human.
REM
REM  This runs BEFORE the build steps on purpose. Whatever it pulls in is then
REM  re-stamped and re-prerendered by stamp_updated.py / prerender_tabs.js below,
REM  so the shipped file is internally consistent rather than a stitched-together
REM  half of each side.
py reconcile_with_origin.py
if errorlevel 2 (
  echo.
  echo ABORTED: reconcile_with_origin.py hit a git problem - see above.
  echo Nothing was committed or pushed.
  pause
  exit /b 1
)
if errorlevel 1 (
  echo.
  echo ABORTED: someone else's changes could not be merged automatically.
  echo The conflicting files are listed above and NOTHING on disk was changed.
  echo Resolve those by hand, then re-run deploy.bat.
  pause
  exit /b 1
)

echo.
echo === Checking deploy.bat itself matches origin ===
REM  ORIGINAL REASON (2026-07-27): this file is tracked, so the old
REM  `git reset --hard origin/main` rewrote deploy.bat WHILE cmd.exe was
REM  executing it. cmd.exe reads a batch file by byte offset as it goes, so a
REM  file that changes length underneath it either stops mid-run or jumps to a
REM  garbage offset and re-runs an earlier block. Both were observed.
REM
REM  THAT HAZARD IS GONE as of 2026-07-29: the reset below is MIXED and never
REM  touches the working tree, so this script can no longer be rewritten while
REM  it runs.
REM
REM  The check is kept because it now guards something else, and something real:
REM  deploy.bat is NOT in the `git add` list below, so a local edit to it never
REM  ships. Without this gate a changed deploy.bat would sit unpushed forever
REM  while every deploy quietly kept using the origin version - the local and
REM  live deploy logic drifting apart with no signal. Aborting forces the edit
REM  to be pushed before it can matter.
git fetch origin >nul 2>&1
set "LOCAL_BAT="
set "REMOTE_BAT="
REM  --path makes hash-object apply .gitattributes, i.e. the eol=crlf clean
REM  filter, so a correctly CRLF working file hashes to the LF blob git
REM  stores. Without it this comparison depends on core.autocrlf and can
REM  report a false difference on a machine configured differently.
for /f "delims=" %%i in ('git hash-object --path=deploy.bat deploy.bat 2^>nul') do set "LOCAL_BAT=%%i"
for /f "delims=" %%i in ('git rev-parse origin/main:deploy.bat 2^>nul') do set "REMOTE_BAT=%%i"
if not defined REMOTE_BAT goto :bat_check_done
if not defined LOCAL_BAT goto :bat_check_done
if not "%LOCAL_BAT%"=="%REMOTE_BAT%" (
  echo.
  echo ABORTED: deploy.bat differs from the version on origin/main.
  echo deploy.bat is not staged by this script, so your local change would never
  echo reach GitHub - every future deploy would keep running the origin version
  echo while your edit sat here unused.
  echo.
  echo Note: the reconcile step above deliberately skips .bat/.cmd/.ps1, because
  echo cmd.exe is reading THIS file by byte offset right now and rewriting it
  echo mid-run has already cost this project two deploys. So if the difference
  echo came from someone else's push rather than your own edit, take theirs by
  echo hand first:  git checkout origin/main -- deploy.bat
  echo.
  echo Otherwise commit and push your deploy.bat, then re-run:
  echo     git add deploy.bat
  echo     git commit -m "update deploy.bat"
  echo     git push
  pause
  exit /b 1
)
:bat_check_done

echo.
echo === Stamping last-updated timestamp ===
py stamp_updated.py
if errorlevel 1 (
  echo.
  echo ABORTED: stamp_updated.py failed or refused to run - see message above.
  pause
  exit /b 1
)

echo.
echo === optional: Refresh ATLAS_STUDIES/ATLAS_GAPS from Airtable ===
if defined AIRTABLE_TOKEN (
  py sync_airtable.py
) else (
  echo    AIRTABLE_TOKEN not set - skipping data refresh, deploying current index.html
)

echo.
echo === Rebuild Deep-search chunk index - best effort ===
py atlas_fulltext\build_chunk_index.py
if errorlevel 1 echo    build_chunk_index.py failed - deploying existing chunk_index.json if present

echo.
echo === Regenerate pre-rendered pages (study/entity/author/about/data/...) ===
REM  This is what AI crawlers without JS actually read (build_pages.py's own
REM  header comment explains why) -- and it is also now the only place that
REM  stamps DATASET_REF's version (read from CITATION.cff) and dateModified
REM  onto every one of those pages AND onto index.html's own Dataset JSON-LD
REM  block (patch_dataset_meta()). Before this step existed, deploy.bat never
REM  called build_pages.py at all: the pre-rendered pages only updated when
REM  someone ran it by hand, so a routine deploy could silently ship
REM  weeks-stale study/entity/data pages next to a freshly-synced index.html.
py build_pages.py
if errorlevel 1 (
  echo.
  echo ABORTED: build_pages.py failed - the pre-rendered pages crawlers read
  echo would be missing or stale relative to the data just synced above.
  exit /b 1
)

echo.
echo === Prerender JS-only tabs so crawlers see what humans see ===
REM  #questionsView and #eventsView are filled at runtime by renderGaps() and
REM  renderEvents(). Bots that do not execute JS (GPTBot, ClaudeBot, PerplexityBot,
REM  Common Crawl) would otherwise see those two tabs empty. Worse, Open Questions
REM  used to carry a hand-written Q1-Q7 fallback that no longer matched the live
REM  H1-H10 content, so a crawler read a DIFFERENT set of questions than a human.
REM  prerender_tabs.js runs those same two functions in Node and bakes the result
REM  into the HTML. It must run AFTER the Airtable refresh above, or it bakes stale
REM  data. Missing Node is a hard stop, not a warning: shipping a stale prerender is
REM  exactly the failure mode this step exists to prevent.
where node >nul 2>nul
if errorlevel 1 (
  echo.
  echo ABORTED: Node.js not found on PATH, so the JS-only tabs cannot be prerendered.
  echo Install Node from https://nodejs.org and re-run, or deploy from the sandbox via deploy.sh.
  exit /b 1
)
node prerender_tabs.js
if errorlevel 1 (
  echo.
  echo ABORTED: prerender_tabs.js failed - see the error above.
  exit /b 1
)
echo.
echo === Crawler-parity gate: every hypothesis and event must be in the HTML ===
REM  Backstop for the step above. Asserts that every ATLAS_GAPS id and every
REM  ATLAS_EVENTS name actually appears in the prerendered blocks - which is what
REM  catches a stale prerender, e.g. a hypothesis added in Airtable but never baked.
py verify_prerender.py
if errorlevel 1 (
  echo.
  echo ABORTED: verify_prerender.py failed - crawlers would see different content than humans.
  exit /b 1
)
echo.
echo === Scientific claim calibration gate ===
py validate_claims.py --strict --json atlas_data\claim_validation.json
if errorlevel 1 (
  echo.
  echo ABORTED: validate_claims.py found claims stronger than the evidence behind them.
  echo Fix the wording ^(or the tier^) listed above, or re-run without --strict if you
  echo have reviewed each finding and decided it is acceptable. NOT deploying.
  exit /b 1
)

echo.
echo === Verifying index.html BEFORE backup - catch corruption early ===
py verify_index_html.py index.html
if errorlevel 1 (
  echo.
  echo ABORTED: index.html already looks corrupted - not backing it up or deploying it.
  echo Restore a known-good index.html, e.g. from the last good git commit, and re-run.
  pause
  exit /b 1
)

echo.
echo === Backing up the files to deploy ===
copy /Y index.html "index_deploy_backup.html" >nul
if exist "atlas_fulltext\chunk_index.json" copy /Y "atlas_fulltext\chunk_index.json" "chunkindex_deploy_backup.json" >nul

echo.
echo === Verifying the backup copy is complete ===
py verify_index_html.py index_deploy_backup.html
if errorlevel 1 (
  echo.
  echo ABORTED: the backup copy of index.html looks corrupted - the copy itself
  echo may have been truncated. Not proceeding. Re-run deploy.bat.
  pause
  exit /b 1
)

echo.
echo === Fetching state from GitHub ===
git fetch origin

echo.
echo === Checking nobody else already pushed a newer index.html ===
set "LOCAL_BASE_HTML="
set "REMOTE_NOW_HTML="
for /f "delims=" %%i in ('git rev-parse HEAD:index.html 2^>nul') do set "LOCAL_BASE_HTML=%%i"
for /f "delims=" %%i in ('git rev-parse origin/main:index.html 2^>nul') do set "REMOTE_NOW_HTML=%%i"
if not defined LOCAL_BASE_HTML (
  echo    WARNING: could not read HEAD:index.html - skipping this check.
  goto :skip_html_race_gate
)
if not defined REMOTE_NOW_HTML (
  echo    WARNING: could not read origin/main:index.html - skipping this check.
  goto :skip_html_race_gate
)
if not "%LOCAL_BASE_HTML%"=="%REMOTE_NOW_HTML%" (
  echo.
  echo ABORTED: somebody pushed a newer index.html WHILE this deploy was running.
  echo The reconcile step at the top of this script already merged everything
  echo origin had at that moment, so this can only mean a push landed in the
  echo last minute or two - after that merge and before this final check.
  echo This script restores index.html wholesale from your local backup, so
  echo continuing would silently overwrite whatever just arrived.
  echo.
  echo Fix: just re-run deploy.bat. The reconcile step will merge their change
  echo in the same way. Nothing was committed or pushed, and your build is safe
  echo in index_deploy_backup.html.
  pause
  exit /b 1
)
:skip_html_race_gate

echo.
echo === Temporarily renaming colliding untracked files ===
REM  A leftover _local_img_backup.png from an interrupted run makes ren fail with
REM  "A duplicate file name exists" - clear the target first.
if exist "ChatGPT Image 6. 7. 2026 17_07_15.png" (
  if exist "_local_img_backup.png" del /f /q "_local_img_backup.png" 2>nul
  ren "ChatGPT Image 6. 7. 2026 17_07_15.png" "_local_img_backup.png"
)

echo.
echo === Backing up baked data - belt and braces ===
REM  The reset below is MIXED as of 2026-07-29, so it no longer touches the
REM  working tree and this backup is no longer load-bearing. It is kept because
REM  the verify-after-restore step underneath it is the corruption gate that
REM  caught the truncated index.html incident, and that gate is worth keeping
REM  even when the thing it guards against has become unlikely.
if exist "atlas_data\studies_baked.json" copy /Y "atlas_data\studies_baked.json" "studiesbaked_deploy_backup.json" >nul

echo.
echo === Syncing local repo to origin/main ===
REM  WAS `git reset --hard origin/main` until 2026-07-29. That reverted EVERY
REM  tracked file to origin, and only index.html, chunk_index.json and
REM  studies_baked.json were copied back afterwards - so anything else the build
REM  had just regenerated was silently thrown away. That bit during the claim
REM  calibration audit: build_pages.py had rewritten 43 pre-rendered pages under
REM  study\ and the entity folders, and a --hard reset would have reverted all of
REM  them to the old wording while the SPA shipped the corrected text. The
REM  pre-rendered pages are what AI crawlers read, so the fix would have gone
REM  live for humans and not for GPTBot or ClaudeBot.
REM
REM  A MIXED reset does the one thing this step is actually for - move HEAD and
REM  the index to origin/main so the commit below is a clean fast-forward - and
REM  leaves the working tree completely untouched. Files are then committed
REM  because they are named in the `git add` list, never because they survived a
REM  reset. Nothing generated can be lost here any more.
git reset origin/main
if errorlevel 1 (
  echo.
  echo ABORTED: git reset to origin/main failed - see the error above.
  echo Nothing was committed or pushed. Your build is safe in index_deploy_backup.html.
  pause
  exit /b 1
)

echo.
echo === Restoring the files to deploy ===
copy /Y "index_deploy_backup.html" index.html >nul
if not exist "atlas_fulltext" mkdir "atlas_fulltext"
if exist "chunkindex_deploy_backup.json" copy /Y "chunkindex_deploy_backup.json" "atlas_fulltext\chunk_index.json" >nul
if not exist "atlas_data" mkdir "atlas_data"
if exist "studiesbaked_deploy_backup.json" copy /Y "studiesbaked_deploy_backup.json" "atlas_data\studies_baked.json" >nul

echo.
echo === Verifying restored index.html BEFORE commit - the real safety gate ===
py verify_index_html.py index.html
if errorlevel 1 (
  echo.
  echo ABORTED: index.html looks corrupted after being restored from backup -
  echo the restore or copy step itself may have been truncated. NOT committing
  echo or pushing. The backup file index_deploy_backup.html has been left in
  echo place for inspection instead of being cleaned up. Re-run deploy.bat.
  pause
  exit /b 1
)

echo.
echo === Staging and committing the site ===
REM  This list is the deploy's contract: a file that is not named here does not
REM  reach the live site, however freshly it was generated. When you add a new
REM  build artifact, add it here in the same commit.
git add index.html
if exist "atlas_fulltext\chunk_index.json" git add atlas_fulltext\chunk_index.json
if exist "atlas_data\studies_baked.json" git add atlas_data\studies_baked.json
if exist "atlas_data\entities_baked.json" git add atlas_data\entities_baked.json
if exist "atlas_data\events_baked.json" git add atlas_data\events_baked.json

REM  2026-08-15: author/, condition/, question/ + sitemap-authors.xml,
REM  sitemap-questions.xml, llms.txt, atlas_data\author_bios_baked.json were
REM  generated by build_pages.py back on 2026-08-04 but were never in the lists
REM  below, so they sat untracked on disk for 11 days and never reached the live
REM  site. Fixed by adding them to the loops. If build_pages.py grows a new
REM  TYPE_DIR entry, add the resulting folder name to the %%D loop below too.
REM  2026-08-23: same fix for `about` (new static page, SEO_GEO_AUDIT.md §14)
REM  before it ever shipped -- added here in the same commit as the page itself.
REM  Pre-rendered pages from build_pages.py - the version of the Atlas that AI
REM  crawlers actually read, since they do not run the SPA's JavaScript.
echo    including pre-rendered pages and sitemaps
for %%D in (study gene complex drug disease outcome process intervention nutrient organelle condition author question browse answers glossary about data) do (
  if exist "%%D" git add "%%D"
)
if exist "sitemap.xml" git add sitemap.xml
for %%F in (sitemap-home.xml sitemap-studies.xml sitemap-entities.xml sitemap-authors.xml sitemap-questions.xml sitemap-answers.xml robots.txt llms.txt) do (
  if exist "%%F" git add "%%F"
)
if exist "lineage_1.html" git add lineage_1.html

REM  Claim-calibration report from the gate that ran at the top of this script.
if exist "atlas_data\claim_validation.json" git add atlas_data\claim_validation.json

REM  Everything else the pipeline scripts write. None of this is served to a
REM  browser - the live site is index.html plus the pre-rendered pages above -
REM  but all of it is TRACKED, so a deploy that does not stage it lets the copy
REM  in git drift away from the copy on disk. That drift is exactly what bit
REM  events_baked.json: hand-fixed on disk, never committed, silently reverted
REM  on the next reset, and the fix had to be redone after every deploy.
REM
REM  Written by: bake_from_mcp.py, backfill_pmids.py, normalize_entities.py,
REM  build_chunk_index.py. `git add` on an unchanged file is a no-op, so listing
REM  one that this particular run did not touch costs nothing.
echo    including pipeline data and reports
for %%F in (gaps_baked.json pmid_map.json pmid_map.csv pmid_report.md entities_auto.json entities_review.csv relation_candidates.csv relation_candidates_new.csv PHASE6_normalize_report.md studies_enriched.jsonl studies_enriched.csv author_bios_baked.json) do (
  if exist "atlas_data\%%F" git add "atlas_data\%%F"
)
if exist "atlas_fulltext\chunks.jsonl" git add atlas_fulltext\chunks.jsonl

REM  The pipeline scripts themselves, the validators and the repo config. These
REM  are not site content, but if a deploy does not stage them the generator on
REM  origin drifts away from the generator on disk - and the next person to run
REM  build_pages.py regenerates every page from the OLD template, silently
REM  undoing whatever the last session changed. That is not hypothetical: the
REM  mobile-optimisation pass on 2026-07-29 rewrote build_pages.py to emit media
REM  queries, and without this block the 311 regenerated pages would have shipped
REM  while the generator that produced them stayed behind.
echo    including pipeline scripts and repo config
for %%F in (build_pages.py bake_from_mcp.py sync_airtable.py sync_relations.py stamp_updated.py normalize_entities.py backfill_pmids.py validate_claims.py verify_index_html.py verify_prerender.py reconcile_with_origin.py prerender_tabs.js finish_review_fixes.py .gitignore .gitattributes) do (
  if exist "%%F" git add "%%F"
)

REM  BACKSTOP. Everything above names files explicitly, which is good for reading
REM  intent and bad at catching what nobody thought to name - twice now a tracked
REM  file changed, went unstaged, and drifted: events_baked.json, then
REM  build_pages.py. `git add -u` stages modifications AND DELETIONS of files git
REM  already tracks, and touches nothing untracked, so scratch files and the
REM  ignored test scaffolding stay out. It also stages the two deletions from the
REM  mobile pass, which no `if exist` line could ever catch - the whole point of a
REM  deletion is that the file is gone.
git add -u

git commit -m "%COMMIT_MSG%"

echo.
echo === Status before push ===
git status

echo.
echo === Push to GitHub ===
git push origin main

REM  IndexNow ping (added 2026-08-29): tell Bing/Yandex/Seznam.cz/Naver that
REM  sitemap URLs changed, right after a successful push. Google does not
REM  participate in IndexNow -- this is on top of, not instead of, the normal
REM  sitemap/URL-Inspection path for Google. Best-effort like
REM  build_chunk_index.py above: a failure here (no network, API hiccup, etc.)
REM  must never abort a deploy that already pushed successfully.
if errorlevel 1 (
  echo    skipping IndexNow ping - push above did not succeed
) else (
  echo.
  echo === Pinging IndexNow (Bing/Yandex/Seznam.cz/Naver) ===
  py indexnow_ping.py
  if errorlevel 1 echo    indexnow_ping.py reported a problem - see above, deploy continues regardless
)

echo.
echo === Cleaning up temp files ===
del "index_deploy_backup.html" 2>nul
del "chunkindex_deploy_backup.json" 2>nul
del "studiesbaked_deploy_backup.json" 2>nul
if exist "_local_img_backup.png" ren "_local_img_backup.png" "ChatGPT Image 6. 7. 2026 17_07_15.png"

echo.
echo ============================================================
echo  Check above that the push finished without error - Writing... done.
echo  Live site updates in about 1 minute. Deep search loads
echo  atlas_fulltext/chunk_index.json on demand.
echo ============================================================
pause
