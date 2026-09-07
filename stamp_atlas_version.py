#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
stamp_atlas_version.py -- cache-busting pro assets/atlas.css v index.html.

Zrcadli stamp_type_version.py (viz ten soubor pro plne zduvodneni): assets/atlas.css
se linkuje pres <link>, ne pres JS loader, takze bez teto stamp cesty by
prohlizec/CDN mohl drzet v cache STAROU verzi CSS i po zmene obsahu.

assets/atlas.css vznikl 2026-09-07 (SEO P0 Ukol 3) vytazenim hlavniho <style>
bloku z <head> index.html (96 KB) -- homepage predtim posilala tenhle CSS
inline pri KAZDE navsteve, misto aby ho prohlizec / CDN mohl cachovat mezi
strankami jako externi soubor.

Spoustej jako soucast deploy pipeline, po kazde zmene assets/atlas.css,
stejne jako stamp_type_version.py pro assets/type.css.
"""
import hashlib
import io
import os
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
ASSET = "assets/atlas.css"
NEEDLE_OPEN = '<link rel="stylesheet" href="/assets/atlas.css?v='
MARK_START = "<!-- atlas-css-link -->"
MARK_END = "<!-- /atlas-css-link -->"


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
            print("atlas.css unchanged -- version stays %s" % ver)
            return 0
        html = html[:i] + ver + html[j:]
        print("atlas.css version %s -> %s" % (old, ver))
    else:
        print("FAIL: %s marker not found in index.html head -- run the "
              "2026-09-07 CSS-extraction patch first" % NEEDLE_OPEN)
        return 1

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
    ok = ('href="/assets/atlas.css?v=%s"' % ver) in chk and chk.rstrip().endswith("</html>")
    print("verified:", ok)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
