#!/usr/bin/env python3
"""
verify_prerender.py -- brána kvality pro Fázi 6.

Ověřuje jedinou věc, ale tu, na které celá fáze stojí: že stránka obsahuje
skutečný text i po odstranění všech <script> bloků. GPTBot, PerplexityBot,
ClaudeBot ani Common Crawl JavaScript zpravidla nespouštějí -- pokud po
odstranění skriptů zbude jen navigace, stránka je pro ně prázdná a veškerá
práce fáze 6 je k ničemu.

    py verify_prerender.py

Návratový kód 1 = něco neprošlo, nenasazuj.
"""

import os, re, sys, glob, json

HERE = os.path.dirname(os.path.abspath(__file__))
MIN_CHARS = 900          # pod tímhle je to navigace, ne obsah
MIN_PAGES = 250

def visible_text(path):
    h = open(path, encoding="utf-8").read()
    body = h.split("<body", 1)[1] if "<body" in h else h
    body = re.sub(r"<script.*?</script>", " ", body, flags=re.S)
    body = re.sub(r"<style.*?</style>", " ", body, flags=re.S)
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", body)).strip(), h


def main():
    pages = sorted(glob.glob(os.path.join(HERE, "study", "*", "index.html")))
    for d in ("gene", "complex", "drug", "process", "disease", "outcome",
              "organelle", "nutrient", "intervention"):
        pages += sorted(glob.glob(os.path.join(HERE, d, "*", "index.html")))

    if not pages:
        sys.exit("ŽÁDNÉ vygenerované stránky — spusť nejdřív build_pages.py")

    thin, nold, nocanon, sizes = [], [], [], []
    for p in pages:
        txt, raw = visible_text(p)
        sizes.append(len(txt))
        rel = os.path.relpath(p, HERE)
        if len(txt) < MIN_CHARS:
            thin.append((rel, len(txt)))
        if 'application/ld+json' not in raw:
            nold.append(rel)
        if 'rel="canonical"' not in raw:
            nocanon.append(rel)

    sizes.sort()
    print("stránek           : %d" % len(pages))
    print("viditelný text    : min %d / medián %d / max %d znaků"
          % (sizes[0], sizes[len(sizes) // 2], sizes[-1]))

    ok = True
    if len(pages) < MIN_PAGES:
        print("CHYBA: jen %d stránek, čekáno aspoň %d" % (len(pages), MIN_PAGES)); ok = False
    if thin:
        print("CHYBA: %d stránek pod %d znaky viditelného textu:" % (len(thin), MIN_CHARS))
        for r, n in thin[:10]:
            print("   %6d  %s" % (n, r))
        ok = False
    if nold:
        print("CHYBA: %d stránek bez JSON-LD" % len(nold)); ok = False
    if nocanon:
        print("CHYBA: %d stránek bez canonical" % len(nocanon)); ok = False

    for sm in ("sitemap.xml", "sitemap-studies.xml", "sitemap-entities.xml"):
        p = os.path.join(HERE, sm)
        if not os.path.exists(p):
            print("CHYBA: chybí %s" % sm); ok = False
        else:
            n = open(p, encoding="utf-8").read().count("<loc>")
            print("%-22s %d URL" % (sm, n))

    # Kontrola, že v sitemap nejsou adresy, které neexistují na disku.
    smp = os.path.join(HERE, "sitemap-entities.xml")
    if os.path.exists(smp):
        missing = []
        for m in re.finditer(r"<loc>https://mtor-atlas\.org/(.*?)</loc>",
                             open(smp, encoding="utf-8").read()):
            f = os.path.join(HERE, m.group(1).strip("/"), "index.html")
            if not os.path.exists(f):
                missing.append(m.group(1))
        if missing:
            print("CHYBA: %d URL v sitemap bez souboru: %s" % (len(missing), missing[:5]))
            ok = False

    print("\n%s" % ("OK — crawler bez JS uvidí obsah na všech stránkách."
                    if ok else "NEPROŠLO — nenasazuj."))
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
