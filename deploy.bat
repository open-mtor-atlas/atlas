@echo off
REM ============================================================
REM  Deploy the Open mTOR Atlas to GitHub Pages.
REM  Pushes the two files the live site needs:
REM      index.html                       (the page: abstract RAG + gaps)
REM      atlas_fulltext\chunk_index.json  (the Deep-search full-text index)
REM
REM  Steps:
REM   1) (optional) refresh baked data from Airtable   -> if AIRTABLE_TOKEN is set
REM   2) rebuild the Deep-search chunk index           -> best effort
REM   3) back up the two files to deploy, VERIFY the backup is complete
REM   4) sync local repo to origin/main (nothing on GitHub is deleted)
REM   5) restore the two files, VERIFY again, commit, push
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

set "COMMIT_MSG=Atlas update %date% %time%"

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
echo === Removing any stuck git lock ===
del /f /q ".git\index.lock" 2>nul

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
  echo ABORTED: index.html on GitHub has changed since your last sync.
  echo Another machine or Cowork session already pushed a newer index.html than
  echo the one your local edits are based on. This script restores index.html
  echo wholesale from your local backup - it does not merge - so deploying now
  echo would silently overwrite their changes.
  echo.
  echo Fix: git pull origin main, reconcile or reapply your edits on top of the
  echo current index.html, then re-run deploy.bat.
  pause
  exit /b 1
)
:skip_html_race_gate

echo.
echo === Temporarily renaming colliding untracked files ===
if exist "ChatGPT Image 6. 7. 2026 17_07_15.png" ren "ChatGPT Image 6. 7. 2026 17_07_15.png" "_local_img_backup.png"

echo.
echo === Syncing local repo to origin/main ===
git reset --hard origin/main

echo.
echo === Restoring the files to deploy ===
copy /Y "index_deploy_backup.html" index.html >nul
if not exist "atlas_fulltext" mkdir "atlas_fulltext"
if exist "chunkindex_deploy_backup.json" copy /Y "chunkindex_deploy_backup.json" "atlas_fulltext\chunk_index.json" >nul

echo.
echo === Verifying restored index.html BEFORE commit - the real safety gate ===
py verify_index_html.py index.html
if errorlevel 1 (
  echo.
  echo ABORT