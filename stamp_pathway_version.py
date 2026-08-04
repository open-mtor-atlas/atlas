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
    html = io.open(p, encoding="utf-8").read()

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

    with io.open(p, "w", encoding="utf-8") as f:
        f.write(html)
        f.flush()
        os.fsync(f.fileno())

    chk = io.open(p, encoding="utf-8").read()
    ok = ('var PW_ASSET_V = "%s"' % ver) in chk and chk.rstrip().endswith("</html>")
    print("verified:", ok)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
