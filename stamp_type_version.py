#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
stamp_type_version.py -- cache-busting pro assets/type.css v index.html.

PROC TOHLE EXISTUJE
index.html se pri deployi meni, takze ho GitHub Pages / CDN obslouzi znova.
Ale assets/type.css se linkuje pres <link>, ne pres JS loader jako pathway
assety -- takze bez vlastniho kroku by prohlizec/CDN klidne drzel v cache
STAROU verzi CSS i pote, co se zmeni jeho obsah (viz
claude/typography-unification-plan-2026-08-31.md, sekce "Cache-busting").

Staticke stranky (build_pages.py / build_academy.py) resi cache-busting
samy -- pocitaji hash type.css pri kazdem behu a vkladaji ho primo do
generovaneho <link href="...?v=<hash>">. Tenhle skript je potreba jen pro
index.html, ktery neni sablonovany a je udrzovany rucne / injektazi.

Spoustej jako soucast deploy pipeline, po kazde zmene assets/type.css,
stejne jako stamp_pathway_version.py pro pathway assety.
"""
import hashlib
import io
import os
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
ASSET = "assets/type.css"
NEEDLE_OPEN = '<link rel="stylesheet" href="/assets/type.css?v='
MARK_START = "<!-- type-css-link -->"
MARK_END = "<!-- /type-css-link -->"


def main():
    p_asset = os.path.join(ROOT, ASSET)
    if not os.path.exists(p_asset):
        print("FAIL: missing %s" % ASSET)
        return 1
    ver = hashlib.sha256(io.open(p_asset, "rb").read()).hexdigest()[:12]

    p = os.path.join(ROOT, "index.html")
    with io.open(p, encoding="utf-8", newline="") as f:
        html = f.read().replace("\r\n", "\n")

    if NEEDLE_OPEN in html:
        i = html.find(NEEDLE_OPEN) + len(NEEDLE_OPEN)
        j = html.find('"', i)
        old = html[i:j]
        if old == ver:
            print("type.css unchanged -- version stays %s" % ver)
            return 0
        html = html[:i] + ver + html[j:]
        print("type.css version %s -> %s" % (old, ver))
    else:
        anchor = "<style>"
        idx = html.find(anchor)
        if idx == -1:
            print("FAIL: anchor <style> not found in index.html head")
            return 1
        link_tag = ('%s\n<link rel="stylesheet" href="/assets/type.css?v=%s">\n%s\n'
                    % (MARK_START, ver, MARK_END))
        html = html[:idx] + link_tag + html[idx:]
        print("type.css link inserted, version %s" % ver)

    # Atomic write: temp file + fsync + os.replace(), same pattern as
    # stamp_pathway_version.py -- index.html is ~3.3 MB, a crash mid-write
    # must never leave a truncated file on disk.
    blob = html.encode("utf-8")
    tmp = p + ".tmp"
    try:
        with io.open(tmp, "w", encoding="utf-8", newline="") as f:
            f.write(html)
            f.flush()
            os.fsync(f.fileno())
        with io.open(tmp, "rb") as f:
            back = f.read()
        if back != blob:
            print("FAIL: temp file did not match -- not swapping it in")
            return 1
        os.replace(tmp, p)
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)

    with io.open(p, encoding="utf-8", newline="") as f:
        chk = f.read()
    ok = ('href="/assets/type.css?v=%s"' % ver) in chk and chk.rstrip().endswith("</html>")
    print("verified:", ok)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
