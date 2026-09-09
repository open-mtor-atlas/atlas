@echo off
REM ============================================================
REM  deploy_all.bat -- JEDEN prikaz, ktery nasadi vsechno.
REM
REM  Tohle spoustej po kazde zmene obsahu (nova studie, konference,
REM  medailonek, oprava textu). Nahrazuje rucni spousteni deploy.bat
REM  a deploy_v2.bat za sebou.
REM
REM  PROC DVA KROKY: od 9. 9. 2026 se web NEservíruje z korene main,
REM  ale z vetve gh-pages, a jeji obsah vyrabi Astro projekt v
REM  ..\Atlas_v2. main prestal byt webem, ale ZUSTAVA zdrojem: data
REM  z Airtable, prerenderovane stranky, ze kterych V2 cte kuratorsky
REM  text (sync_prose.py), Academy i pathway model. Proto se porad
REM  buildi a commituje - jen uz to nikdo nevidi primo.
REM
REM  Kdyz pustis jen deploy.bat, na webu se NIC nezmeni a nic to
REM  nenahlasi. Presne proto existuje tenhle soubor.
REM
REM  KROK 1  deploy.bat        data, proza, Academy, sitemapy, brany -> main
REM  KROK 2  deploy_v2.bat     snimek z origin/main -> build -> gh-pages
REM                            + IndexNow ping (Bing, Seznam, Yandex)
REM
REM  Google IndexNow nepouziva: ten cte sitemap.xml a leze na web sam.
REM  Po vetsi zmene stoji za to v Search Console znovu odeslat
REM  sitemap.xml - vypise se pripominka na konci.
REM
REM  Rollback celeho prechodu: GitHub -> Settings -> Pages -> Source
REM  zpet na main / (root). main se prvnich 14 dni po prechodu neuklizi.
REM ============================================================
setlocal
cd /d "%~dp0"
set "V2=%~dp0..\Atlas_v2"

if not exist "%V2%\deploy_v2.bat" (
  echo ABORTED: nenasel jsem %V2%\deploy_v2.bat
  echo Ceka se, ze Atlas_v2 lezi vedle teto slozky.
  pause
  exit /b 1
)

echo.
echo ############################################################
echo #  KROK 1 ze 2 -- zdroj: data, proza, Academy, brany
echo ############################################################
REM  "< nul" preskoci pause uvnitr deploy.bat, aby cely retez mohl
REM  probehnout bez zasahu. Chybove navratove kody se tim neztraci.
call "%~dp0deploy.bat" < nul
if errorlevel 1 (
  echo.
  echo PRERUSENO v kroku 1. Na web se nic nenasadilo, zdroj zustal beze zmeny.
  echo Spust deploy.bat samostatne, at vidis jeho hlaseni cele.
  pause
  exit /b 1
)

echo.
echo ############################################################
echo #  KROK 2 ze 2 -- publikace webu do vetve gh-pages
echo ############################################################
call "%V2%\deploy_v2.bat" < nul
if errorlevel 1 (
  echo.
  echo PRERUSENO v kroku 2. Zdroj v main je aktualni, ale WEB JE PORAD STARY.
  echo Oprav chybu vyse a spust "%V2%\deploy_v2.bat" znovu - krok 1 uz opakovat nemusis.
  pause
  exit /b 1
)

echo.
echo === Kontrola, ze web odpovida ===
REM  GitHub Pages po pushi jeste chvili prestavuje. Kod jiny nez 200 hned
REM  po deployi obvykle znamena "jeste se stavi", ne "rozbite".
timeout /t 25 /nobreak >nul
for /f %%C in ('curl -s -o nul -w "%%{http_code}" https://mtor-atlas.org/') do set "CODE=%%C"
if "%CODE%"=="200" (
  echo    mtor-atlas.org odpovida 200
) else (
  echo    mtor-atlas.org vratil %CODE% - pockej minutu a nacti web znovu.
  echo    Kdyz to potrva, mrkni na Settings - Pages, jestli build dobehl.
)

echo.
echo ============================================================
echo  HOTOVO.
echo.
echo  Co jeste stoji za rucni krok, kdyz slo o vetsi zmenu:
echo    - Search Console: znovu odeslat sitemap.xml
echo    - u par novych URL: URL Inspection - Request indexing
echo      (denni kvota je kolem 10-12 zadosti)
echo ============================================================
pause
