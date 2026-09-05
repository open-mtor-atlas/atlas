#!/usr/bin/env python3
"""
fix_pathway_viewbox_2026-09-05.py

Fixes a console error on the live site:

    Error: <svg> attribute viewBox: Expected number, "112.0 -Infinity 1376.0..."

Cause
-----
Three camera functions in pathway/pathway.js compute the viewport aspect ratio as

    var r = el.canvas.clientWidth / Math.max(1, el.canvas.clientHeight);

The denominator is guarded against zero. The numerator is not. When the pathway
panel is measured while it is still hidden -- which happens on narrow/mobile
layouts, where the tab is display:none until it is opened -- clientWidth is 0,
so r is 0, h = w / r is Infinity, and the y coordinate of the viewBox becomes
-Infinity. The browser then rejects the whole attribute and the diagram does not
frame itself.

The reported numbers confirm this exactly: w = 1376 is canvas.w * 0.86 from the
minimum-width clamp, and x = 112 is (1600 - 1376) / 2. For y to be infinite while
w is finite, h must be infinite, which requires r == 0, which requires
clientWidth == 0.

Fix
---
A single aspect() helper that falls back to the model's own canvas proportions
when the element has not been laid out yet, and clamps to a sane range. The
camera then produces a finite, sensible viewBox even when framed while hidden;
the existing resize handling re-frames once the panel is actually visible.

    py fix_pathway_viewbox_2026-09-05.py --dry-run
    py fix_pathway_viewbox_2026-09-05.py

Verified with node --check. Idempotent. Standard library only.
"""
import os, re, subprocess, sys, tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
JS = os.path.join(HERE, "pathway", "pathway.js")
DRY = "--dry-run" in sys.argv

OLD = "var r = el.canvas.clientWidth / Math.max(1, el.canvas.clientHeight);"
NEW = "var r = aspect();"

HELPER = '''
  /* Viewport aspect ratio, safe to call before layout. clientWidth is 0 while
     the pathway panel is display:none -- which is the normal state on narrow
     layouts until the tab is opened -- and the old inline expression divided by
     it, producing h = Infinity and a viewBox of "112.0 -Infinity 1376.0 ...".
     The browser rejects that attribute outright, so the diagram never framed
     itself. Falling back to the model's own canvas proportions keeps the camera
     finite; the resize path re-frames once the panel has real dimensions. */
  function aspect() {
    var cw = el.canvas ? el.canvas.clientWidth : 0;
    var ch = el.canvas ? el.canvas.clientHeight : 0;
    if (!cw || !ch) {
      return (M && M.meta && M.meta.canvas)
        ? M.meta.canvas.w / Math.max(1, M.meta.canvas.h)
        : 1;
    }
    return Math.min(8, Math.max(0.125, cw / Math.max(1, ch)));
  }
'''


def main():
    if not os.path.exists(JS):
        sys.exit("ABORT: pathway/pathway.js not found -- run from the repo root.")
    if subprocess.call(["node", "--version"], stdout=subprocess.DEVNULL,
                       stderr=subprocess.DEVNULL) != 0:
        sys.exit("ABORT: node not found on PATH; needed to verify the result parses.")

    src = open(JS, encoding="utf-8").read()
    before = len(src)

    if "function aspect()" in src:
        print("pathway.js: already patched, nothing to do")
        return

    n = src.count(OLD)
    if n == 0:
        sys.exit("ABORT: the aspect-ratio expression was not found; patch by hand.")
    print("replacing %d occurrence(s) of the unguarded aspect ratio" % n)
    src = src.replace(OLD, NEW)

    anchor = "  /* ==== camera ========================================================= */"
    if anchor not in src:
        sys.exit("ABORT: camera section marker not found; patch by hand.")
    src = src.replace(anchor, anchor + "\n" + HELPER.rstrip("\n"), 1)
    print("added aspect() helper")

    with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False,
                                     encoding="utf-8") as f:
        f.write(src)
        tmp_js = f.name
    try:
        r = subprocess.run(["node", "--check", tmp_js], capture_output=True, text=True)
        if r.returncode != 0:
            sys.exit("ABORT: patched pathway.js does not parse; nothing written.\n"
                     + r.stderr[:600])
        print("node --check: parses")
    finally:
        os.unlink(tmp_js)

    print("size: %d -> %d bytes" % (before, len(src)))
    if DRY:
        print("--dry-run: nothing written.")
        return
    tmp = JS + ".tmp"
    open(tmp, "w", encoding="utf-8").write(src)
    if open(tmp, encoding="utf-8").read() != src:
        sys.exit("ABORT: read-back mismatch; pathway.js untouched.")
    os.replace(tmp, JS)
    print("pathway.js rewritten and verified.")
    print("\nNOTE: pathway.js is cache-busted by ?v= in index.html. If the browser "
          "keeps serving the old file, that query string needs bumping too.")


if __name__ == "__main__":
    main()
