#!/usr/bin/env python3
"""
fix_deploy_generate_step_2026-09-05.py

Adds the missing /answers/ + /glossary/ build step to deploy.bat.

The gap
-------
generate.py builds the ten /answers/ pages, the answers hub, /glossary/ and
sitemap-answers.xml. deploy.bat names it in exactly one place -- the `git add`
file list near the end -- and never runs it. So those pages only changed when
somebody ran generate.py by hand.

Worse, generate.py writes to its own OUT directory:

    OUT = os.path.join(os.path.dirname(__file__), "out")

so even running it by hand does nothing visible: it fills out/glossary/ and
out/answers/ while the deployed copies sit at the repo root. On 2026-09-05 a
corrected Rheb glossary entry was written, generate.py was run, it reported
"wrote glossary/index.html", and the live page did not change -- twice -- until
someone looked at OUT.

This is the same failure the build_pages.py comment above the insertion point
describes ("deploy.bat never called build_pages.py at all: the pre-rendered
pages only updated when someone ran it by hand"), repeated one directory over.

The fix
-------
Run generate.py after build_pages.py, then copy out\\answers and out\\glossary
and out\\sitemap-answers.xml into the repo root, where the existing staging loop
(`for %%D in (... answers glossary ...)`) already picks them up. Placed after
build_pages.py because build_pages.py links to these pages, and before
stamp_pathway_version.py so the cache-bust hash covers everything.

A gate follows the copy: if /glossary/ still differs from out/glossary/ after
the copy, abort rather than ship a page that silently disagrees with its source.

Run from the repo root:

    py fix_deploy_generate_step_2026-09-05.py --dry-run
    py fix_deploy_generate_step_2026-09-05.py

Idempotent. Standard library only. Does not run deploy.bat.
"""
import os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
BAT = os.path.join(HERE, "deploy.bat")
DRY = "--dry-run" in sys.argv

ANCHOR = """echo.
echo === Cache-bust the lazy-loaded pathway assets ==="""

NEW_STEP = """echo.
echo === Build /answers/ + /glossary/ ===
REM  generate.py byl v deploy.bat uveden JEN v seznamu pro `git add` a nikdy se
REM  nespoustel -- stejna chyba, jakou popisuje komentar u build_pages.py o kus
REM  vys, jen o adresar vedle. Navic zapisuje do vlastniho out\\, ne do korene:
REM  5. 9. 2026 se opravilo heslo Rheb v glossary, generate.py se spustil, vypsal
REM  "wrote glossary/index.html" -- a nasazena stranka se dvakrat po sobe
REM  nezmenila, protoze novy soubor lezel v out\\glossary\\. Proto se tu po buildu
REM  kopiruje do korene, odkud uz ho stavajici staging smycka
REM  (for %%D in (... answers glossary ...)) sebere.
py generate.py
if errorlevel 1 (
  echo.
  echo ABORTED: generate.py failed - /answers/ a /glossary/ by zustaly stale.
  exit /b 1
)

if not exist "out\\glossary\\index.html" (
  echo.
  echo ABORTED: generate.py probehl, ale out\\glossary\\index.html neexistuje -
  echo zmenil se OUT v generate.py? Bez kopie by se nasadila stara stranka.
  exit /b 1
)

xcopy /E /Y /I /Q "out\\answers" "answers" >nul
xcopy /E /Y /I /Q "out\\glossary" "glossary" >nul
if exist "out\\sitemap-answers.xml" copy /Y "out\\sitemap-answers.xml" "sitemap-answers.xml" >nul

REM  Brana: kdyz se kopie nepovedla, radeji spadnout nez nasadit stranku, ktera
REM  se tise rozchazi se svym zdrojem. Presne tohle se 5. 9. stalo bez vsimnuti.
fc /B "out\\glossary\\index.html" "glossary\\index.html" >nul
if errorlevel 1 (
  echo.
  echo ABORTED: glossary\\index.html se po kopii neshoduje s out\\glossary\\index.html.
  exit /b 1
)

echo.
echo === Cache-bust the lazy-loaded pathway assets ==="""


def main():
    if not os.path.exists(BAT):
        sys.exit("ABORT: deploy.bat not found -- run from the repo root.")
    src = open(BAT, encoding="utf-8", errors="surrogateescape").read()

    if "=== Build /answers/ + /glossary/ ===" in src:
        print("deploy.bat: already patched, nothing to do")
        return
    if src.count(ANCHOR) != 1:
        sys.exit("ABORT: expected exactly 1 cache-bust anchor, found %d. Patch by hand."
                 % src.count(ANCHOR))

    out = src.replace(ANCHOR, NEW_STEP, 1)

    # gates
    # Must anchor to line start: the `git add` file list further down contains
    # "...verify_practice.py generate.py..." and matches a bare substring.
    if out.count("\npy generate.py\n") != 1:
        sys.exit("ABORT: generate.py step not inserted exactly once.")
    if "py stamp_pathway_version.py" not in out or "py build_pages.py" not in out:
        sys.exit("ABORT: existing build steps went missing -- nothing written.")
    if out.index("py build_pages.py") > out.index("\npy generate.py\n"):
        sys.exit("ABORT: generate.py landed before build_pages.py -- wrong order.")
    if out.index("\npy generate.py\n") > out.index("py stamp_pathway_version.py"):
        sys.exit("ABORT: generate.py landed after the cache-bust -- wrong order.")

    print("inserting the /answers/ + /glossary/ build step")
    print("   after : py build_pages.py")
    print("   before: py stamp_pathway_version.py")
    print("size: %d -> %d bytes" % (len(src), len(out)))
    if DRY:
        print("--dry-run: nothing written.")
        return
    tmp = BAT + ".tmp"
    with open(tmp, "w", encoding="utf-8", errors="surrogateescape", newline="") as f:
        f.write(out)
    if open(tmp, encoding="utf-8", errors="surrogateescape").read() != out:
        sys.exit("ABORT: read-back mismatch; deploy.bat untouched.")
    os.replace(tmp, BAT)
    print("deploy.bat rewritten and verified.")
    print("\nNOTE: deploy.bat gates itself against origin (it aborts if deploy.bat")
    print("differs from origin/main), so commit and push this change before the")
    print("next deploy, or that gate will stop you.")


if __name__ == "__main__":
    main()
