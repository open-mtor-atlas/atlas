#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
stamp_pathway_version.py — cache-busting pro lazy-loadované pathway assety.

PROČ TOHLE EXISTUJE
index.html se při deployi mění, takže ho GitHub Pages / CDN obslouží nově.
Ale pathway/pathway.js, pathway.css a model.json se stahují až za běhu na
pevných URL — a ty CDN i prohlížeč drží v cache. Po nasazení nové verze
modulu tak stará stránka klidně načte STARÝ modul k NOVÉMU modelu.
Přesně to se stalo při prvním nasazení Fáze 1: server měl nový JS,
prohlížeč servíroval starý a "DETAIL" ovládání chybělo.

ŘEŠENÍ
Hash obsahu všech tří assetů se zapíše do index.html jako PW_ASSET_V a
loader ho přidá jako ?v=<hash>. Změní se obsah → změní se URL → cache je
irelevantní. Nezmění se obsah → URL zůstane → cache funguje, jak má.

Spouštěj jako poslední krok před commitem (deploy.sh to dělá sám).
"""
import hashlib
import io
import os
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
ASSETS = ["pathway/pathway.js", "pathway/pathway.css", "pathway/model.json", "pathway/contexts.json"]
NEEDLE = 'var PW_ASSET_V = "'


def main():
    h = hashlib.sha256()
    for rel in ASSETS:
        p = os.path.join(ROOT, rel)
        if not os.path.exists(p):
            print("FAIL: missing %s" % rel)
            return 1
        h.update(io.open(p, "rb").read())
    ver = h.hexdigest()[:12]

    p = os.path.join(ROOT, "index.html")
    # newline="" + an explicit \r\n -> \n normalize makes this robust no matter
    # what line endings are currently on disk (this file has been flipped to CRLF
    # before by a different script's naive text-mode write -- see sync_relations.py
    # for the same fix and the fuller explanation). Internal processing and the
    # write below always use plain \n, matching the repo's .gitattributes
    # (*.html text eol=lf), so this script can never be the one that reintroduces
    # CRLF, regardless of what it was handed.
    with io.open(p, encoding="utf-8", newline="") as f:
        html = f.read().replace("\r\n", "\n")

    if NEEDLE in html:
        i = html.find(NEEDLE) + len(NEEDLE)
        j = html.find('"', i)
        old = html[i:j]
        if old == ver:
            print("pathway assets unchanged — version stays %s" % ver)
            return 0
        html = html[:i] + ver + html[j:]
        print("pathway asset version %s -> %s" % (old, ver))
    else:
        anchor = "function pwLoadAsset(tag, attrs){"
        if anchor not in html:
            print("FAIL: pwLoadAsset not found — run _inject_pathway.py first")
            return 1
        html = html.replace(anchor, 'var PW_ASSET_V = "%s";\n%s' % (ver, anchor), 1)
        print("pathway asset version set to %s" % ver)

    # Atomic write: temp file in the same directory + fsync + os.replace(), so a
    # crash or kill mid-write leaves the old index.html untouched instead of a
    # truncated one (same pattern as sync_relations.py).
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
            print("FAIL: temp file did not match — not swapping it in")
            return 1
        os.replace(tmp, p)
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)

    with io.open(p, encoding="utf-8", newline="") as f:
        chk = f.read()
    ok = ('var PW_ASSET_V = "%s"' % ver) in chk and chk.rstrip().endswith("</html>")
    print("verified:", ok)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
