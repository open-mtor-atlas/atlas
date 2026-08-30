#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
verify_academy.py -- integritni brana pro /academy/.

PROC TOHLE EXISTUJE
-------------------
Academy je jedina cast webu, ktera odkazuje NAPRIC vsemi ostatnimi vrstvami
najednou: na stranky studii (build_pages.py), na stranky entit (jen ty nad
prahem 3 studii!), na open questions (gaps_baked.json) a na guided routes
(pathway/model.json). Kazda z techto vrstev se meni nezavisle. Bez teto brany
staci, aby se entita propadla pod prah nebo se prejmenovala trasa, a lekce
tise odkazuje do prazdna -- presne ten druh chyby, kterou nikdo neuvidi, dokud
na ni nekdo neklikne.

Kontroluje se:
  1  kazdy SID v lessons.json existuje v studies_baked.json
  2  kazda entita (proteins/pathways/processes/organelles/nutrients) existuje
     A MA vlastni stranku (>= PAGE_THRESHOLD studii)
  3  kazda guided route existuje v pathway/model.json
  4  kazdy open-question slug existuje v gaps_baked.json
  5  previousLesson / nextLesson ukazuji na existujici lekci, retez je
     konzistentni s poradim v modules.json
  6  kazdy publikovany lesson slug ma vygenerovanou stranku na disku
  7  vsechny interni odkazy z vygenerovanych academy stranek ukazuji na soubor,
     ktery existuje (mimo hash-routy do SPA)
  8  kazda stranka nese svuj <h1> a sekci Evidence PRIMO V HTML (bez JS)
  9  redakcni minima: >=3 studie na lekci, >=1 think question, neprazdne
     uncertainty nebo openQuestions
 10  proza pouziva jen povolenou inline sadu znacek

Usage: python verify_academy.py     (exit 0 = OK, 1 = nalezy)
"""

import os
import re
import sys
import json

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import build_pages as BP  # noqa: E402

ADATA = os.path.join(HERE, "academy_data")
DATA = os.path.join(HERE, "atlas_data")
ACADEMY = os.path.join(HERE, "academy")

ALLOWED = re.compile(r"</?(?:strong|em|code|sub|sup)>|<a href=\"[^\"<>]*\">|</a>")
TAG = re.compile(r"<[^>]+>")

problems = []


def bad(where, msg):
    problems.append("%-34s %s" % (where, msg))


def entity_pages():
    out = {}
    for x in json.load(open(os.path.join(DATA, "entities_baked.json"), encoding="utf-8")):
        st = x.get("studies")
        if isinstance(st, str):
            try:
                st = json.loads(st.replace("'", '"'))
            except Exception:
                st = [t.strip(" '\"") for t in st.strip("[]").split(",") if t.strip()]
        out[x["name"].lower()] = len(st or [])
    return out


def main():
    lessons = json.load(open(os.path.join(ADATA, "lessons.json"), encoding="utf-8"))["lessons"]
    modules = json.load(open(os.path.join(ADATA, "modules.json"), encoding="utf-8"))
    studies = {s["sid"] for s in json.load(open(os.path.join(DATA, "studies_baked.json"),
                                               encoding="utf-8")) if s.get("sid")}
    ents = entity_pages()
    routes = set()
    mp = os.path.join(HERE, "pathway", "model.json")
    if os.path.exists(mp):
        routes = {r["id"] for r in json.load(open(mp, encoding="utf-8")).get("routes", [])}
    gaps = set()
    gp = os.path.join(DATA, "gaps_baked.json")
    if os.path.exists(gp):
        gaps = {BP.slugify(g["title"]) for g in json.load(open(gp, encoding="utf-8"))}

    by_slug = {l["slug"]: l for l in lessons}

    for l in lessons:
        w = "lesson:" + l["slug"]

        # 1 studie
        for sid in l.get("studies") or []:
            if sid not in studies:
                bad(w, "neznamy SID %r" % sid)
        # 9 redakcni minima
        if len(l.get("studies") or []) < 3:
            bad(w, "ma jen %d studii, minimum jsou 3 (spec §11)" % len(l.get("studies") or []))
        if not (l.get("thinkQuestions") or []):
            bad(w, "chybi Think question (spec §11)")
        if not (l.get("uncertainty") or l.get("openQuestions")):
            bad(w, "nepojmenovava zadnou nejistotu ani open question (spec §17)")

        # 2 entity
        for key in ("proteins", "pathways", "processes", "organelles", "nutrients"):
            for name in l.get(key) or []:
                n = ents.get(name.lower())
                if n is None:
                    bad(w, "entita %r neni v entities_baked.json" % name)
                elif n < BP.PAGE_THRESHOLD:
                    bad(w, "entita %r ma jen %d studii -> nema stranku, odkaz by byl 404"
                        % (name, n))
        # 3 routes
        for r in l.get("guidedRoutes") or []:
            if r["id"] not in routes:
                bad(w, "neznama guided route %r" % r["id"])
        # 4 open questions
        for s in l.get("openQuestions") or []:
            if s not in gaps:
                bad(w, "neznamy open-question slug %r" % s)
        # 5 retez
        for key in ("previousLesson", "nextLesson"):
            v = l.get(key)
            if v and v not in by_slug:
                bad(w, "%s ukazuje na neexistujici lekci %r" % (key, v))
        # 10 proza
        blobs = list(l.get("coreIdea") or []) + [l.get("uncertainty") or ""]
        for sec in l.get("sections") or []:
            blobs += list(sec.get("body") or [])
        for t in l.get("thinkQuestions") or []:
            blobs += [t.get("prompt") or "", t.get("hint") or "", t.get("reveal") or ""]
        for b in blobs:
            for m in TAG.finditer(b):
                if not ALLOWED.fullmatch(m.group(0)):
                    bad(w, "nepovolena znacka %r v proze" % m.group(0))

    # 5b poradi v modules.json vs prev/next
    for mod in modules["modules"]:
        pub = [r["lesson"] for r in mod["lessons"] if r["status"] == "published"]
        for r in mod["lessons"]:
            if r["status"] == "published" and r["lesson"] not in by_slug:
                bad("module:" + mod["slug"], "publikovana lekce %r chybi v lessons.json"
                    % r["lesson"])
            if r["status"] != "published" and not r.get("title"):
                bad("module:" + mod["slug"], "planovana lekce %r nema title" % r["lesson"])
        for i, slug in enumerate(pub):
            if slug not in by_slug:
                continue
            exp_prev = pub[i - 1] if i > 0 else None
            exp_next = pub[i + 1] if i + 1 < len(pub) else None
            if by_slug[slug].get("previousLesson") != exp_prev:
                bad("module:" + mod["slug"],
                    "%s.previousLesson=%r, podle poradi ma byt %r"
                    % (slug, by_slug[slug].get("previousLesson"), exp_prev))
            if by_slug[slug].get("nextLesson") != exp_next:
                bad("module:" + mod["slug"],
                    "%s.nextLesson=%r, podle poradi ma byt %r"
                    % (slug, by_slug[slug].get("nextLesson"), exp_next))

    # 6/7/8 vygenerovane stranky
    pages = []
    for root, _, files in os.walk(ACADEMY):
        for fn in files:
            if fn == "index.html":
                pages.append(os.path.join(root, fn))
    if not pages:
        bad("academy/", "zadne vygenerovane stranky -- spust nejdriv build_academy.py")

    for mod in modules["modules"]:
        for r in mod["lessons"]:
            if r["status"] != "published":
                continue
            p = os.path.join(ACADEMY, mod["slug"], r["lesson"], "index.html")
            if not os.path.exists(p):
                bad("academy/", "chybi vygenerovana stranka %s" % p)

    href = re.compile(r'href="([^"#][^"]*)"')
    for p in pages:
        rel = os.path.relpath(p, HERE)
        h = open(p, encoding="utf-8").read()
        if "<h1>" not in h:
            bad(rel, "stranka nema <h1> primo v HTML")
        is_lesson = rel.count(os.sep) >= 3        # academy/<module>/<lesson>/index.html
        if is_lesson and "What does the evidence say?" not in h:
            bad(rel, "lekce nema sekci Evidence primo v HTML (crawler bez JS by ji nevidel)")
        if "mtor-atlas.org" not in h:
            bad(rel, "stranka neobsahuje kanonickou domenu -- poskozena sablona?")
        for u in set(href.findall(h)):
            if u.startswith("http") and not u.startswith(BP.SITE):
                continue          # externi odkaz, neresime
            path = u[len(BP.SITE):] if u.startswith(BP.SITE) else u
            path = path.split("#")[0].split("?")[0]
            if not path.startswith("/") or path in ("/",):
                continue
            target = os.path.join(HERE, path.strip("/"))
            if os.path.isdir(target):
                target = os.path.join(target, "index.html")
            if not os.path.exists(target):
                bad(rel, "odkaz na neexistujici cil %s" % u)

    if problems:
        print("verify_academy: %d NALEZU\n" % len(problems))
        for x in problems:
            print("  " + x)
        return 1
    print("verify_academy: OK -- %d lekci, %d stranek, vsechny odkazy sedi"
          % (len(lessons), len(pages)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
