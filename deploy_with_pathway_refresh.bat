@echo off
REM ============================================================
REM  Refresh the pathway model + Mechanism Explorer relations,
REM  THEN run the normal site deploy.
REM
REM  This exists because deploy.bat itself does NOT regenerate
REM  pathway/model.json or the Mechanism Explorer's guided routes
REM  (aa/gf/rapa/out/energy/mtorc2/clin) -- those are curator-
REM  triggered, on purpose, so a stray Airtable edit can't silently
REM  redraw the pathway map. Run this whenever you've changed the
REM  curation tables in build_pathway_model.py, or want the guided
REM  routes' geometry re-solved against whatever is currently in
REM  the Airtable Relations table.
REM
REM  Steps:
REM   1) build_pathway_model.py   -- regenerate pathway/model.json
REM   2) validate_pathway.py --strict -- calibration + integrity gate
REM   3) pathway/smoke_test.js    -- 2699 rendering/pedagogy assertions
REM   4) stamp_pathway_version.py -- cache-bust pathway.js/css/model.json
REM   5) sync_relations.py        -- pull Airtable Relations, re-solve
REM                                   guided-route geometry (needs
REM                                   AIRTABLE_TOKEN for a real refresh;
REM                                   falls back to --layout-only, which
REM                                   needs no network, if it's not set)
REM   6) deploy.bat                -- the normal site deploy: Airtable
REM                                   studies/gaps sync, static pages,
REM                                   chunk index, verification gates,
REM                                   commit, push, IndexNow ping
REM
REM  Each step aborts the whole run on failure, same convention as
REM  deploy.bat itself: fail closed, never ship a half-built state.
REM ============================================================
cd /d "%~dp0"

echo.
echo === Step 1/6: build_pathway_model.py ===
py build_pathway_model.py
if errorlevel 1 (
  echo ABORTED: build_pathway_model.py reported problems - see output above.
  exit /b 1
)

echo.
echo === Step 2/6: validate_pathway.py --strict ===
py validate_pathway.py --strict
if errorlevel 1 (
  echo ABORTED: validate_pathway.py found errors - pathway/model.json is not deployable.
  exit /b 1
)

echo.
echo === Step 3/6: pathway smoke test ===
node pathway\smoke_test.js
if errorlevel 1 (
  echo ABORTED: pathway/smoke_test.js failed - the Pathway explorer would ship broken.
  exit /b 1
)

echo.
echo === Step 4/6: stamp_pathway_version.py ===
py stamp_pathway_version.py
if errorlevel 1 (
  echo ABORTED: stamp_pathway_version.py failed - see message above.
  exit /b 1
)

echo.
echo === Step 5/6: sync_relations.py ===
if defined AIRTABLE_TOKEN (
  py sync_relations.py
) else (
  echo    AIRTABLE_TOKEN not set - skipping the Airtable Relations refresh,
  echo    re-solving guided-route geometry only against what's already baked.
  py sync_relations.py --layout-only
)
if errorlevel 1 (
  echo ABORTED: sync_relations.py could not route every edge cleanly - see output above.
  exit /b 1
)

echo.
echo === Step 6/6: deploy.bat ===
call deploy.bat
if errorlevel 1 (
  echo ABORTED: deploy.bat did not complete - see its output above.
  exit /b 1
)

echo.
echo === All done: pathway model + Mechanism Explorer refreshed and deployed. ===
