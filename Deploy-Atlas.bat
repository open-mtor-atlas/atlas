@echo off
setlocal enabledelayedexpansion

rem ==================================================================
rem  Deploy-Atlas.bat -- Open mTOR Atlas build and verify
rem
rem  Runs the five build steps in order, then verifies the result.
rem  Never pushes, never merges, never deploys: it ends by printing
rem  the git commands for you to run yourself.
rem
rem  Usage, from the folder containing index.html:
rem
rem      set AIRTABLE_TOKEN=patXXXXXXXX
rem      Deploy-Atlas.bat
rem
rem  Without the token it still runs, but skips the Airtable sync and
rem  says clearly that the build is incomplete.
rem ==================================================================

echo.
echo  Open mTOR Atlas - build and verify
echo  -----------------------------------

rem ---- find a Python launcher --------------------------------------
set "PY="
py --version >nul 2>&1 && set "PY=py"
if not defined PY python --version >nul 2>&1 && set "PY=python"
if not defined PY (
    echo   FAIL  No Python found. Install Python 3 and make sure 'py' or 'python' is on PATH.
    goto :abort
)
for /f "delims=" %%v in ('%PY% --version 2^>^&1') do set "PYVER=%%v"
echo   OK    Python: %PY%  [!PYVER!]

rem ---- confirm we are in the repo root -----------------------------
set "MISSING="
for %%f in (index.html sync_airtable.py build_pathway_model.py validate_claims.py fix_findings_and_prerender.py apply_audit_fixes_2026-09-04.py verify_atlas_build.py) do (
    if not exist "%%f" set "MISSING=!MISSING! %%f"
)
if defined MISSING (
    echo   FAIL  Not in the repo root, or files missing:!MISSING!
    echo         cd to the folder containing index.html and try again.
    goto :abort
)
echo   OK    all pipeline scripts present

where git >nul 2>&1
if errorlevel 1 (
    echo   FAIL  git not found on PATH.
    goto :abort
)

rem ---- token / sync mode -------------------------------------------
set "NOSYNC="
if not defined AIRTABLE_TOKEN (
    echo.
    echo   WARN  AIRTABLE_TOKEN is not set.
    echo         Without it the Airtable sync is skipped, so this build will NOT
    echo         contain the 2026-09-04 edits: the 15 filled PMIDs, the H4 scope
    echo         fix, and dropping JIN2026 / ZHU2026 from two pathway edges.
    echo.
    set /p "GO=  Continue without the sync? [y/N] "
    if /i not "!GO!"=="y" goto :abort
    set "NOSYNC=--no-sync"
) else (
    echo   OK    AIRTABLE_TOKEN is set
)

rem ---- branch ------------------------------------------------------
for /f "delims=" %%b in ('git rev-parse --abbrev-ref HEAD 2^>nul') do set "CURBR=%%b"
for /f "tokens=1-3 delims=/.- " %%a in ("%DATE%") do set "TODAY=%%c-%%b-%%a"
set "BRANCH=audit-fixes-%TODAY%"
echo.
echo   Current branch: !CURBR!
set /p "MKBR=  Create branch !BRANCH! ? [Y/n] "
if /i not "!MKBR!"=="n" (
    git checkout -b !BRANCH! 2>nul || git checkout !BRANCH!
    if errorlevel 1 (
        echo   FAIL  Could not create or switch to !BRANCH!
        goto :abort
    )
)

rem ---- build steps -------------------------------------------------
if defined NOSYNC (
    echo.
    echo == Step 1/5  sync_airtable.py  [SKIPPED, no token]
) else (
    echo.
    echo == Step 1/5  sync_airtable.py
    %PY% sync_airtable.py
    if errorlevel 1 ( set "STEP=Airtable sync" & goto :stepfail )
)

echo.
echo == Step 2/5  apply_audit_fixes_2026-09-04.py
%PY% apply_audit_fixes_2026-09-04.py
if errorlevel 1 ( set "STEP=Audit code fixes" & goto :stepfail )

echo.
echo == Step 3/5  build_pathway_model.py
%PY% build_pathway_model.py
if errorlevel 1 ( set "STEP=Pathway model build" & goto :stepfail )

echo.
echo == Step 4/5  fix_findings_and_prerender.py
%PY% fix_findings_and_prerender.py
if errorlevel 1 ( set "STEP=Findings and prerender" & goto :stepfail )

echo.
echo == Step 5/5  validate_claims.py
%PY% validate_claims.py
if errorlevel 1 ( set "STEP=Validator" & goto :stepfail )

rem ---- verification ------------------------------------------------
echo.
echo == Verification
%PY% verify_atlas_build.py %NOSYNC%
if errorlevel 1 (
    echo.
    echo   One or more checks failed. Do NOT commit until they are resolved.
    goto :abort
)

rem ---- handover ----------------------------------------------------
echo.
echo == Changed files
git status --short

for /f "delims=" %%b in ('git rev-parse --abbrev-ref HEAD') do set "NOWBR=%%b"

echo.
echo  Local preview:
echo     %PY% -m http.server 8000      then open http://localhost:8000
echo     Check Open Questions with JavaScript DISABLED - that is the prerender block.
echo.
echo  Publishing is not automated. Run these yourself when satisfied:
echo.
echo     git add -A
echo     git commit -m "Audit 2026-09-04: carry conflicting evidence, drop mis-attached citations, scope H4, fill PMIDs, refresh baked counts"
echo     git push -u origin !NOWBR!
echo.
echo  Then open the PR on GitHub and merge. Pages redeploys on merge to main;
echo  hard-refresh with Ctrl+F5 before concluding anything is wrong.
echo.
endlocal
exit /b 0

:stepfail
echo.
echo   FAIL  !STEP! failed.
:abort
echo.
echo  ABORTED. Nothing further was run.
endlocal
exit /b 1
