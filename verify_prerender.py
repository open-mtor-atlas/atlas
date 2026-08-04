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


def check_index_tabs():
    """#questionsView a #eventsView se plní až za běhu (renderGaps/renderEvents).

    Bez prerenderu je crawler v těch dvou tabech vidí prázdné. Ještě horší stav,
    ve kterém Atlas nějakou dobu byl: v Open Questions zůstal ručně psaný fallback
    Q1-Q7, který se s živým obsahem H1-H10 neshodoval -- crawler tedy indexoval
    JINÉ otázky, než jaké četl člověk.

    Tahle kontrola nepotřebuje Node. Neověřuje HTML znak po znaku (to umí
    `node prerender_tabs.js --check`), ale to jediné, na čem záleží: že se každé
    ID / název z dat opravdu objevuje v statickém HTML. Tím chytí i zastaralost --
    přidaná hypotéza nebo konference, která se nikdy neprerenderovala.
    """
    p = os.path.join(HERE, "index.html")
    if not os.path.exists(p):
        print("CHYBA: index.html nenalezen"); return False
    h = open(p, encoding="utf-8").read()
    ok = True

    for tab in ("questionsView", "eventsView"):
        o, c = "<!--PRERENDER:%s-->" % tab, "<!--/PRERENDER:%s-->" % tab
        i, j = h.find(o), h.find(c)
        if i < 0 or j < 0:
            print("CHYBA: v index.html chybí PRERENDER značky pro #%s" % tab); ok = False; continue
        body = h[i + len(o):j]
        print("%-22s %d znaků statického HTML" % ("#" + tab, len(body)))
        if len(body) < 400:
            print("CHYBA: #%s je prakticky prázdný -- spusť: node prerender_tabs.js" % tab)
            ok = False

    def arr(name):
        m = re.search(r"const %s = (\[.*?\]);" % name, h, re.S)
        return json.loads(m.group(1)) if m else []

    qbody = h.split("<!--PRERENDER:questionsView-->")[-1].split("<!--/PRERENDER:questionsView-->")[0]
    ebody = h.split("<!--PRERENDER:eventsView-->")[-1].split("<!--/PRERENDER:eventsView-->")[0]

    missing = [g["id"] for g in arr("ATLAS_GAPS") if g.get("id") and g["id"] not in qbody]
    if missing:
        print("CHYBA: %d hypotéz z ATLAS_GAPS chybí v prerenderu: %s" % (len(missing), missing[:5]))
        print("       prerender je zastaralý -- spusť: node prerender_tabs.js")
        ok = False

    emiss = [e["name"] for e in arr("ATLAS_EVENTS")
             if e.get("name") and e["name"].replace("&", "&amp;") not in ebody]
    if emiss:
        print("CHYBA: %d akcí z ATLAS_EVENTS chybí v prerenderu: %s" % (len(emiss), emiss[:3]))
        print("       prerender je zastaralý -- spusť: node prerender_tabs.js")
        ok = False

    return ok


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

    # Rozbité interní odkazy. Entity pod prahem stránku nedostanou, ale objevují
    # se jako sousedé -- při prvním generování takhle vzniklo 110 odkazů na 404.
    dead = {}
    nlinks = 0
    for p in pages:
        h = open(p, encoding="utf-8").read()
        for m in re.finditer(r'href="/([^"#?]+?)/"', h):
            nlinks += 1
            if not os.path.exists(os.path.join(HERE, m.group(1), "index.html")):
                dead.setdefault(m.group(1), 0)
                dead[m.group(1)] += 1
    print("interních odkazů  : %d" % nlinks)
    if dead:
        print("CHYBA: %d rozbitých cílů, %d výskytů:"
              % (len(dead), sum(dead.values())))
        for k in sorted(dead, key=lambda x: -dead[x])[:10]:
            print("   %4d×  /%s/" % (dead[k], k))
        ok = False

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

    print("\n--- index.html: taby plněné JavaScriptem ---")
    if not check_index_tabs():
        ok = False

    print("\n%s" % ("OK — crawler bez JS uvidí obsah na všech stránkách."
                    if ok else "NEPROŠLO — nenasazuj."))
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
