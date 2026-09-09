@echo off
REM ============================================================
REM  refresh_fulltext.bat -- doplni fulltextovy korpus pro Deep search.
REM
REM  PROC EXISTUJE: chunk_index.json obsahoval 30 studii z 360 (8 %),
REM  protoze license_gate.py cetl atlas_gaps\studies_enriched.jsonl --
REM  snimek z 28. 7. 2026 se 168 studiemi. Branka tedy nikdy nevidela
REM  vetsinu korpusu. --from-baked cte atlas_data\studies_baked.json,
REM  tedy 331 studii s PMID (198 z nich uz ma PMCID).
REM
REM  MUSI BEZET Z WINDOWS. Europe PMC ani NCBI nejsou dostupne z Cowork
REM  session (egress politika je odmita), takze tenhle skript je jedine
REM  misto, kde se ta data daji stahnout.
REM
REM  Kroky:
REM    1) license_gate.py --from-baked  -> atlas_gaps\licenses.csv
REM       Europe PMC rekne u kazdeho PMID licenci. Ulozi se jen CC bez
REM       No-Derivatives; nic jineho se nikdy nestahuje.
REM    2) fetch_fulltext.py             -> raw\*.xml + chunks.jsonl + manifest.csv
REM       Resumable: uz stazene studie preskoci, nove pripoji.
REM    3) build_chunk_index.py          -> chunk_index.json
REM    4) coverage_report.py            -> kolik studii z korpusu je pokryto
REM
REM  Trva radove minuty (1 s pauza mezi studiemi, at je to k EPMC slusne).
REM  Po dobehnuti zkontroluj coverage a teprve pak deploy.bat.
REM ============================================================
cd /d "%~dp0.."

echo.
echo === 1/4 Licencni branka nad zivym korpusem ===
py atlas_gaps\license_gate.py --from-baked
if errorlevel 1 goto :fail

echo.
echo === 2/4 Stahovani fulltextu (jen CC, bez ND) ===
py atlas_fulltext\fetch_fulltext.py
if errorlevel 1 goto :fail

echo.
echo === 3/4 Prestavba vyhledavaciho indexu ===
py atlas_fulltext\build_chunk_index.py
if errorlevel 1 goto :fail

echo.
echo === 4/4 Pokryti ===
py atlas_fulltext\coverage_report.py
if errorlevel 1 goto :fail

echo.
echo Hotovo. Zmenene soubory: atlas_gaps\licenses.csv, atlas_fulltext\raw\*.xml,
echo chunks.jsonl, manifest.csv, chunk_index.json.
echo Nasazuje se az pres deploy.bat.
goto :eof

:fail
echo.
echo PRERUSENO: krok vyse skoncil chybou. Nic dalsiho nebezelo.
exit /b 1
