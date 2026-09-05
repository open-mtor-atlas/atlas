#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
build_practice.py -- generuje Practice Arenu Academy: /academy/practice/ a
/academy/progress/ (Faze A herni vrstvy).

PROC TOHLE EXISTUJE
-------------------
Learn uci, Research Challenges nechavaji rozhodovat -- chybel trenink mezi tim.
Practice Arena je ctvrty pilir: kratke hry, ktere prověřují, jestli clovek to,
co precetl, opravdu umi pouzit. Faze A pridava BODY A POSTUP nad obsahem, ktery
uz existuje; NEPISE novou vedeckou prozu.

ZASADNI PRAVIDLO: kazda polozka se GENERUJE z dat, ktera uz projdou branami --
pathway/model.json (uzly, hrany, znamenka, routes) a academy_data/lessons.json
(kvizy, model-cviceni s vyjmenovanymi stavy, predict, caution shows/doesNotShow).
Zadna nova tvrzeni o biologii se tady nevymysleji. Kdyz generator neco nenajde
v modelu, polozka nevznikne -- radeji chybejici hra nez vymyslena hrana.

FILTR POKRYTI (dulezite): model ma 88 uzlu, lekce jich probiraji zlomek.
  core pool  -- uzly, ktere lekce jmenuji ve svych seznamech entit
  route pool -- uzly na guided routes, na ktere lekce odkazuji (odemyka se
                az na hodnosti 3, protoze route je "hlubsi" cteni)
Polozka mimo tyhle dve mnoziny se nesmi nabidnout: student by dostal hranu,
o ktere web nikde neuci. verify_practice.py to kontroluje.

CO JE UVNITR
  * generatory poloh: sprint (hrany + kompartmenty), quiz (30 hotovych),
    pert (59 vyjmenovanych stavu modelu), predict (3), limits (caution
    shows/doesNotShow), wire (routes + loops)
  * engine v prohlizeci: XP s kalibraci, mastery s decay, Brier, odznaky,
    hodnosti 1-3, export/import -- vse v localStorage, zadny ucet, zadny fetch
  * dve stranky pres build_pages.shell(), takze hlavicka, paticka, fonty a
    mobilni chovani jsou stejne jako u zbytku webu

TRI VRSTVY (stejny kontrakt jako cviceni Faze 2):
  obsah je v HTML -> <details> fallback bez JS -> JS jen sekvencuje a skoruje.
  Bez JS je stranka porad uzitecna cvicebnice s odpovedmi, jen bez bodu.

VSTUP   academy_data/practice.json      (pravidla hry -- prahy, XP, odznaky)
        academy_data/lessons.json       (kvizy, cviceni)
        pathway/model.json              (uzly, hrany, routes, loops, open_*)
VYSTUP  academy/practice/index.html
        academy/progress/index.html

Spousti se z build_academy.py (na konci main()), takze deploy.bat se nemeni.
Samostatne:  py build_practice.py [--dry-run]
Kontrola:    py verify_practice.py
"""

import os
import sys
import json
import re
import random

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import build_pages as BP
from build_pages import (SITE, shell, breadcrumb_ld, e, DATASET_REF, write)

DRY = "--dry-run" in sys.argv
BP.DRY = BP.DRY or DRY

ACADEMY_DIR = os.path.join(HERE, "academy")
ADATA = os.path.join(HERE, "academy_data")
PW_PATH = os.path.join(HERE, "pathway", "model.json")

# Deterministicky mix: banka se nesmi menit mezi buildy, jinak by se studentovi
# rozpadly ulozene stavy (polozky se pamatuji podle id).
RNG = random.Random(20260905)


# ------------------------------------------------------------------- data ---

def load():
    cfg = json.load(open(os.path.join(ADATA, "practice.json"), encoding="utf-8"))
    les = json.load(open(os.path.join(ADATA, "lessons.json"), encoding="utf-8"))["lessons"]
    pw = json.load(open(PW_PATH, encoding="utf-8"))
    return cfg, les, pw


def coverage(les, pw):
    """Vrati (core, route, meta) -- dve mnoziny id uzlu a slovnik o uzlech.

    core  = uzly jmenovane v seznamech entit lekci (to, co lekce vysvetluje)
    route = uzly na guided routes, na ktere lekce odkazuji (hlubsi cteni)
    """
    ids = {n["id"] for n in pw["nodes"]}
    by_label = {n["label"].lower(): n["id"] for n in pw["nodes"]}
    inter = {i["id"]: i for i in pw["interactions"]}

    core, lesson_of = set(), {}
    for l in les:
        for key in ("proteins", "concepts", "processes", "organelles", "pathways",
                    "outcomes", "drugs", "nutrients"):
            for v in l.get(key) or []:
                name = v if isinstance(v, str) else (v.get("name") or v.get("id") or "")
                nid = name if name in ids else by_label.get(name.lower())
                if nid:
                    core.add(nid)
                    lesson_of.setdefault(nid, l["slug"])

    routes = {r["id"]: r for r in pw.get("routes") or []}
    route_nodes = set()
    for l in les:
        for gr in l.get("guidedRoutes") or []:
            r = routes.get(gr.get("id") if isinstance(gr, dict) else gr)
            if not r:
                continue
            for eid in r.get("spine") or []:
                it = inter.get(eid)
                if not it:
                    continue
                route_nodes.add(it["source"])
                route_nodes.add(it["target"])
                lesson_of.setdefault(it["source"], l["slug"])
                lesson_of.setdefault(it["target"], l["slug"])
    route_nodes -= core

    # URL lekce se sklada z modulu, ktery lekce sama nese -- ne z natvrdo
    # napsaneho "core". Druhy modul by jinak tise ukazoval na neexistujici cil.
    url_of = {l["slug"]: "/academy/%s/%s/" % (l.get("module", "core"), l["slug"]) for l in les}
    meta = {}
    for n in pw["nodes"]:
        if n["id"] in core or n["id"] in route_nodes:
            slug = lesson_of.get(n["id"], "")
            meta[n["id"]] = {
                "label": n["label"], "cls": n["cls"], "comp": n["compartment"],
                "x": n["x"], "y": n["y"],
                "pool": "core" if n["id"] in core else "route",
                "lesson": slug, "url": url_of.get(slug, ""),
            }
    return core, route_nodes, meta


def open_ids(pw):
    """Id uzlu a hran, ktere model sam vede jako nedoresene. Tyhle se na mape
    kresli srafovane a NIKDY nedosahnou plne mastery -- viz practice.json copy."""
    nodes, edges = set(), set()
    for ol in pw.get("open_loops") or []:
        for eid in ol.get("interactions") or []:
            edges.add(eid)
    return nodes, edges


# ------------------------------------------------------------- generatory ---
#
# Kazdy generator vraci seznam polozek v jednotnem tvaru:
#   {id, game, diff (1-3), nodes [id], prompt, options [str], answer (index),
#    explain, lesson (slug|""), pool ("core"|"route")}
# `nodes` je to, cemu se pripise mastery -- proto tam patri jen uzly, o kterych
# polozka skutecne neco tvrdi.

EFFECT_WORD = {"activates": "activates", "inhibits": "inhibits"}


def gen_sprint(pw, meta):
    """Znamenka hran + kde uzel sidli. Dve odpovedi, zadna kalibrace, nizke XP."""
    out = []
    comps = {c["id"]: c["name"] for c in pw["compartments"]}
    for it in pw["interactions"]:
        s, t = it["source"], it["target"]
        if s not in meta or t not in meta:
            continue
        if it["effect"] not in EFFECT_WORD:
            continue
        pool = "core" if meta[s]["pool"] == "core" and meta[t]["pool"] == "core" else "route"
        out.append({
            "id": "sp:%s" % it["id"], "game": "sprint", "diff": 1,
            "nodes": [s, t], "pool": pool,
            "prompt": "%s &rarr; %s" % (e(meta[s]["label"]), e(meta[t]["label"])),
            "options": ["activates", "inhibits"],
            "answer": 0 if it["effect"] == "activates" else 1,
            "explain": e(it.get("mechanism", ""))[:240],
            "lesson": meta[s]["lesson"] or meta[t]["lesson"],
        })
    for nid, m in sorted(meta.items()):
        if m["cls"] not in ("protein", "complex", "organelle"):
            continue
        if m["comp"] in ("input", "outcome"):
            continue
        wrong = [c for c in ("cytosol", "lyso", "pm", "nucleus") if c != m["comp"]]
        RNG.shuffle(wrong)
        opts = [m["comp"], wrong[0]]
        RNG.shuffle(opts)
        out.append({
            "id": "sc:%s" % nid, "game": "sprint", "diff": 1,
            "nodes": [nid], "pool": m["pool"],
            "prompt": "Where does <strong>%s</strong> act?" % e(m["label"]),
            "options": [e(comps[o]) for o in opts],
            "answer": opts.index(m["comp"]),
            "explain": "", "lesson": m["lesson"],
        })
    return out


DIFF_BY_LEVEL = {"easy": 1, "medium": 2, "hard": 3}


def gen_quiz(les, meta):
    """30 hotovych kvizovych polozek z lekci -- uz maji vysvetleni."""
    out = []
    for l in les:
        nodes = [n for n in meta if meta[n]["lesson"] == l["slug"]]
        for i, q in enumerate(l.get("quiz") or []):
            out.append({
                "id": "qz:%s:%d" % (l["slug"], i), "game": "quiz",
                "diff": DIFF_BY_LEVEL.get(q.get("level", "medium"), 2),
                "nodes": nodes[:3], "pool": "core",
                "prompt": q["prompt"], "options": list(q["options"]),
                "answer": q["answer"], "explain": q.get("explain", ""),
                "lesson": l["slug"],
            })
    return out


def gen_predict(les, meta):
    """Rucne napsane predikce z Faze 2 (kind: predict) -- uz maji options."""
    out = []
    for l in les:
        nodes = [n for n in meta if meta[n]["lesson"] == l["slug"]]
        for ex in l.get("exercises") or []:
            if ex.get("kind") != "predict":
                continue
            ob = ex.get("observe") or {}
            out.append({
                "id": "pr:%s" % ex["id"], "game": "predict", "diff": 2,
                "nodes": nodes[:3], "pool": "core",
                "prompt": ex["prompt"], "options": list(ex["options"]),
                "answer": ex["answer"],
                "explain": (ob.get("readout") or ex.get("explain") or ""),
                "sid": ob.get("sid", ""), "lesson": l["slug"],
            })
    return out


def gen_limits(les):
    """Caution bloky maji `shows` a `doesNotShow` -- presne material na otazku
    "co tenhle vysledek NEUKAZUJE". Spravna odpoved je z doesNotShow,
    rozptylovace z shows TEHOZ bloku, takze se nemichaji ruzna tvrzeni."""
    out = []
    for l in les:
        for ex in l.get("exercises") or []:
            if ex.get("kind") != "caution":
                continue
            shows = [s for s in (ex.get("shows") or [])]
            nots = [s for s in (ex.get("doesNotShow") or [])]
            if len(shows) < 2 or not nots:
                continue
            for j, bad in enumerate(nots):
                opts = [bad] + shows[:3]
                idx = list(range(len(opts)))
                RNG.shuffle(idx)
                out.append({
                    "id": "li:%s:%d" % (ex["id"], j), "game": "limits", "diff": 2,
                    "nodes": [], "pool": "core",
                    "prompt": "&lsquo;%s&rsquo; &mdash; which of these does the evidence "
                              "behind this claim <em>not</em> support?" % ex.get("title", ""),
                    "options": [opts[k] for k in idx],
                    "answer": idx.index(0),
                    "explain": ex.get("why", ""),
                    "lesson": l["slug"],
                })
    return out


def gen_pert(les, pw, meta):
    """Perturbation Lab: kazdy vyjmenovany stav modelu je jedna predikce.
    Model se kresli z `layout` (sloupce id uzlu) a z `edges` (id interakci) --
    stejny zdroj jako lekce, takze schema nemuze rict nic, co model nezna."""
    inter = {i["id"]: i for i in pw["interactions"]}
    models, items = [], []
    for l in les:
        for ex in l.get("exercises") or []:
            if ex.get("kind") != "model":
                continue
            states = ex.get("states") or {}
            if len(states) < 2:
                continue
            layout = [[n for n in col] for col in ex.get("layout") or []]
            labels = {}
            for col in layout:
                for nid in col:
                    labels[nid] = meta[nid]["label"] if nid in meta else nid
            readouts = []
            for k, st in states.items():
                r = st.get("readout") or ""
                if r and r not in readouts:
                    readouts.append(r)
            if len(readouts) < 2:
                continue
            edges = []
            for eid in ex.get("edges") or []:
                it = inter.get(eid)
                if it:
                    edges.append({"id": eid, "s": it["source"], "t": it["target"],
                                  "eff": it["effect"]})
            if not edges:
                # Kdyz cviceni hrany nevyjmenuje (6 z 10 modelu), lekce je kresli
                # mezi sousednimi sloupci -- stejne jako model_block() v
                # build_academy.py. Delame totez, ale JEN ty, ktere v modelu
                # opravdu existuji: vynechani hrany je zjednoduseni, vymysleni chyba.
                by_pair = {(i["source"], i["target"]): i for i in pw["interactions"]}
                for ci in range(len(layout) - 1):
                    for a in layout[ci]:
                        for b in layout[ci + 1]:
                            it = by_pair.get((a, b))
                            if it:
                                edges.append({"id": it["id"], "s": a, "t": b,
                                              "eff": it["effect"]})
            models.append({
                "id": ex["id"], "title": ex.get("title", ""), "lesson": l["slug"],
                "caption": ex.get("caption", ""), "layout": layout, "labels": labels,
                "edges": edges,
                "controls": ex.get("controls") or [], "start": ex.get("start") or {},
                "states": {k: {"readout": v.get("readout", ""), "note": v.get("note", ""),
                               "flow": v.get("flow") or [], "cut": v.get("cut") or []}
                           for k, v in states.items()},
                "readouts": readouts,
            })
            nodes = [n for n in labels if n in meta]
            for k, st in states.items():
                if not st.get("readout"):
                    continue
                items.append({
                    "id": "pe:%s:%s" % (ex["id"], k), "game": "pert",
                    "diff": 2 if len(ex.get("controls") or []) <= 2 else 3,
                    "nodes": nodes, "pool": "core",
                    "model": ex["id"], "state": k,
                    "prompt": "", "options": [], "answer": -1,
                    "explain": st.get("note", ""), "lesson": l["slug"],
                })
    return models, items


def gen_wire(pw, meta, core):
    """Wire the Pathway: routes jsou hotove kostry cest.

    Pater route (`spine`) NENI vzdy jeden retez -- vetsina cest se nekde
    rozdvojuje nebo prida bocni vstup (RAGULATOR-RAG uprostred aminokyselinove
    cesty). Prvni verze generatoru na tom padala a vyrobila 5 puzzlu misto
    dvaceti. Bereme proto NEJDELSI LINEARNI USEK patere: je to porad skutecna
    cesta modelem, jen kratsi, a hra zustane hratelna (jedno poradi, zadny
    uzel dvakrat).

    easy   -- tri po sobe jdouci kroky
    medium -- cely nalezeny usek ve spravnem poradi
    hard   -- totez + rozptylovac: uzel, ktery na ceste nelezi. Na hard se
              navic ukazuje, ktery krok je neprimy -- na to se nalitne nejcasteji.
    """
    inter = {i["id"]: i for i in pw["interactions"]}
    puz = []

    def longest_chain(spine):
        """Nejdelsi souvisly usek: kroky jdou za sebou, dokud target jednoho je
        source dalsiho. Uzel se v useku nesmi opakovat (jinak by hra mela dva
        stejne dilky)."""
        best, cur = [], []
        for eid in spine:
            it = inter.get(eid)
            if not it:
                cur = []
                continue
            if cur and cur[-1]["target"] == it["source"] and it["target"] not in _seq(cur):
                cur.append(it)
            else:
                cur = [it]
            if len(cur) > len(best):
                best = cur[:]
        return best

    def _seq(steps):
        out = [steps[0]["source"]]
        for it in steps:
            out.append(it["target"])
        return out

    for r in pw.get("routes") or []:
        steps = longest_chain(r.get("spine") or [])
        if len(steps) < 2:
            continue
        seq = _seq(steps)
        if any(n not in meta for n in seq):
            continue
        allcore = all(meta[n]["pool"] == "core" for n in seq)
        base = {"route": r["id"], "name": r.get("name", ""),
                "pool": "core" if allcore else "route"}
        if len(steps) >= 3:
            puz.append(dict(base, id="wr:%s:easy" % r["id"], diff=1,
                            seq=seq[:3], steps=_wsteps(steps[:2], meta), distractor=None))
        puz.append(dict(base, id="wr:%s:med" % r["id"], diff=2,
                        seq=seq, steps=_wsteps(steps, meta), distractor=None))
        puz.append(dict(base, id="wr:%s:hard" % r["id"], diff=3,
                        seq=seq, steps=_wsteps(steps, meta),
                        distractor=_distractor(seq, meta, core)))
    return puz


def _wsteps(steps, meta):
    return [{"s": it["source"], "t": it["target"],
             "eff": it["effect"], "dir": it.get("directness", "direct"),
             "why": (it.get("mechanism") or "")[:200]} for it in steps]


def _distractor(seq, meta, core):
    """Uzel, ktery na ceste nelezi, ale patri do stejneho kompartmentu jako
    nektery z jejich uzlu -- past musi byt vabna, ne absurdni."""
    comps = {meta[n]["comp"] for n in seq}
    cands = [n for n in sorted(core)
             if n not in seq and n in meta and meta[n]["comp"] in comps]
    return cands[RNG.randrange(len(cands))] if cands else None


# ------------------------------------------------------------------- bank ---

def build_bank(cfg, les, pw):
    core, route, meta = coverage(les, pw)
    fit_labels(meta)
    _, oedges = open_ids(pw)
    models, pert = gen_pert(les, pw, meta)
    items = (gen_sprint(pw, meta) + gen_quiz(les, meta) + gen_predict(les, meta)
             + gen_limits(les) + pert)
    wire = gen_wire(pw, meta, core)

    bands = pw.get("bands") or []
    comps = {c["id"]: {"short": c["short"], "name": c["name"]} for c in pw["compartments"]}
    rest = [[round(n["x"]), round(n["y"])] for n in pw["nodes"] if n["id"] not in meta]

    return {
        "v": cfg["version"], "cfg": cfg,
        "nodes": meta, "items": items, "models": models, "wire": wire,
        "map": {"bands": bands, "comps": comps, "rest": rest,
                "edges": [{"s": i["source"], "t": i["target"], "eff": i["effect"],
                           "dir": i.get("directness", "direct"), "id": i["id"]}
                          for i in pw["interactions"]
                          if i["source"] in meta and i["target"] in meta],
                "openEdges": sorted(oedges),
                "openNote": (pw.get("open_loops") or [{}])[0].get("name", ""),
                "openWhy": (pw.get("open_loops") or [{}])[0].get("why", ""),
                "openLoc": [{"name": o.get("name", ""), "why": o.get("why", "")}
                            for o in (pw.get("open_localisations") or [])][:1]},
        "counts": {"core": len(core), "route": len(route),
                   "atlas": len(pw["nodes"]), "items": len(items), "wire": len(wire)},
    }


# -------------------------------------------------------------------- css ---
# Pripojuje se ZA ACADEMY_CSS, takze smi prepsat cokoli vys. Zadna nova paleta:
# jen tokeny, ktere shell() a assets/type.css uz definuji (vcetne tmaveho
# rezimu pres html[data-theme="dark"]). Radius 3px jako zbytek statickych
# stranek. Prefix .pa- aby se to nemohlo poprat s .ac- z lekci.

PRACTICE_CSS = """
/* ---- Practice Arena (build_practice.py) ---------------------------- */
.pa-tint{--pa-tint:rgba(163,31,52,.09)}
html[data-theme="dark"] .pa-tint{--pa-tint:rgba(108,168,178,.16)}

.pa-rankbar{display:flex;align-items:center;gap:14px 20px;flex-wrap:wrap;
  border:1px solid var(--line);border-radius:3px;padding:14px 18px;margin:0 0 26px}
.pa-rankbar .pa-rk{font-family:'IBM Plex Mono',monospace;font-size:11px;letter-spacing:.12em;
  text-transform:uppercase;color:var(--soft);font-weight:600}
.pa-rankbar .pa-rkname{font-size:19px;font-weight:700;letter-spacing:-.01em;margin:0}
.pa-rankbar .pa-xp{font-family:'IBM Plex Mono',monospace;font-size:12.5px;color:var(--soft)}
.pa-rankbar .pa-xp b{color:var(--ink)}
.pa-meter{flex:1 1 200px;min-width:160px;height:8px;background:var(--line);position:relative;
  border-radius:0}
.pa-meter i{position:absolute;left:0;top:0;bottom:0;background:var(--teal);display:block}
.pa-rankbar .pa-to{font-family:'IBM Plex Mono',monospace;font-size:11px;color:var(--soft);
  letter-spacing:.04em;white-space:nowrap}

.pa-tiles{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,232px),1fr));
  gap:14px;margin:0 0 30px}
.pa-tile{border:1px solid var(--line);border-radius:3px;padding:18px 20px;display:flex;
  flex-direction:column;gap:8px;text-align:left;background:none;color:var(--ink);
  font:inherit;cursor:pointer;min-height:44px}
.pa-tile:hover{border-color:var(--teal)}
.pa-tile[aria-pressed="true"]{border-color:var(--teal);box-shadow:inset 0 0 0 1px var(--teal)}
.pa-tile h3{margin:0;font-size:16px}
.pa-tile p{margin:0;font-size:13.5px;color:var(--soft);line-height:1.5;flex:1}
.pa-tile .pa-skill{font-family:'IBM Plex Mono',monospace;font-size:10.5px;letter-spacing:.08em;
  text-transform:uppercase;color:var(--soft)}
.pa-tile[disabled]{opacity:.5;cursor:not-allowed}
.pa-tile[disabled]:hover{border-color:var(--line)}

.pa-board{border:1px solid var(--line);border-radius:3px;margin:0 0 30px}
.pa-bhead{display:flex;align-items:center;justify-content:space-between;gap:14px;flex-wrap:wrap;
  padding:12px 18px;border-bottom:1px solid var(--line)}
.pa-bhead .pa-t{font-family:'IBM Plex Mono',monospace;font-size:11px;letter-spacing:.12em;
  text-transform:uppercase;font-weight:600}
.pa-bhead .pa-prog{font-family:'IBM Plex Mono',monospace;font-size:11.5px;color:var(--soft)}
.pa-body{padding:20px 18px 22px}
.pa-q{font-size:17px;line-height:1.5;margin:0 0 4px;font-weight:600}
.pa-sub{font-size:13px;color:var(--soft);margin:0 0 16px;font-family:'IBM Plex Mono',monospace;
  letter-spacing:.03em}
.pa-opts{display:flex;flex-direction:column;gap:8px;margin:0 0 18px}
.pa-opt{display:flex;gap:11px;align-items:flex-start;text-align:left;width:100%;
  border:1px solid var(--line);border-radius:3px;background:none;color:var(--ink);
  font:inherit;font-size:15px;line-height:1.5;padding:12px 14px;cursor:pointer;min-height:44px}
.pa-opt:hover{border-color:var(--teal);background:rgba(163,31,52,.04)}
html[data-theme="dark"] .pa-opt:hover{background:rgba(108,168,178,.08)}
.pa-opt .pa-k{font-family:'IBM Plex Mono',monospace;font-size:12px;color:var(--soft);
  flex:none;width:14px;padding-top:2px}
.pa-opt[data-state="right"]{border-color:var(--teal);box-shadow:inset 0 0 0 1px var(--teal)}
.pa-opt[data-state="wrong"]{border-color:var(--amber);opacity:.85}
.pa-opt[disabled]{cursor:default}
.pa-opt[data-state="right"] .pa-k,.pa-opt[data-state="wrong"] .pa-k{color:var(--ink)}

.pa-conf{border-top:1px solid var(--line);padding:14px 0 0;margin:0 0 4px}
.pa-conf .pa-clab{font-family:'IBM Plex Mono',monospace;font-size:10.5px;letter-spacing:.08em;
  text-transform:uppercase;color:var(--soft);display:block;margin:0 0 9px}
.pa-cbtns{display:flex;gap:8px;flex-wrap:wrap}
.pa-cbtn{font-family:'IBM Plex Mono',monospace;font-size:11.5px;letter-spacing:.04em;
  border:1px solid var(--line);border-radius:3px;background:none;color:var(--ink);
  padding:9px 14px;cursor:pointer;min-height:44px}
.pa-cbtn[aria-pressed="true"]{background:var(--teal);color:var(--on-teal,#fff);
  border-color:var(--teal)}
.pa-slider{display:flex;align-items:center;gap:12px;flex-wrap:wrap}
.pa-slider input{flex:1 1 220px;min-width:180px;accent-color:var(--teal)}
.pa-slider output{font-family:'IBM Plex Mono',monospace;font-size:13px;font-weight:600;
  min-width:52px}

.pa-fb{border-left:3px solid var(--teal);padding:2px 0 2px 15px;margin:16px 0 0;
  font-size:14.5px;line-height:1.6;color:var(--soft)}
.pa-fb b{color:var(--ink)}
.pa-fb .pa-xpgain{font-family:'IBM Plex Mono',monospace;font-size:12px;color:var(--teal);
  font-weight:600;display:block;margin-top:6px}
.pa-fb[data-ok="0"]{border-left-color:var(--amber)}

/* Signal Sprint ------------------------------------------------------- */
.pa-sprint{text-align:center;padding:8px 0 4px}
.pa-clock{font-family:'IBM Plex Mono',monospace;font-size:13px;letter-spacing:.1em;
  color:var(--soft)}
.pa-sprintq{font-size:clamp(20px,3.4vw,28px);font-weight:700;margin:18px 0 22px;
  line-height:1.3}
.pa-sprintbtns{display:flex;gap:12px;justify-content:center;flex-wrap:wrap}
.pa-sprintbtns button{font-size:16px;font-weight:600;padding:14px 26px;min-height:52px;
  border:1.5px solid var(--line);border-radius:3px;background:none;color:var(--ink);
  cursor:pointer;font-family:inherit}
.pa-sprintbtns button:hover{border-color:var(--teal);color:var(--teal)}
.pa-flash{font-family:'IBM Plex Mono',monospace;font-size:12px;letter-spacing:.06em;
  margin-top:16px;min-height:18px;color:var(--soft)}

/* Wire the Pathway ---------------------------------------------------- */
.pa-wire{display:flex;flex-direction:column;gap:18px}
.pa-chips{display:flex;flex-wrap:wrap;gap:8px}
.pa-chip{font-size:14px;font-weight:600;border:1.5px solid var(--line);border-radius:3px;
  background:none;color:var(--ink);padding:10px 14px;cursor:pointer;min-height:44px;
  font-family:inherit}
.pa-chip:hover{border-color:var(--teal)}
.pa-chip[aria-pressed="true"]{background:var(--teal);color:var(--on-teal,#fff);
  border-color:var(--teal)}
.pa-chip[data-used="1"]{opacity:.32;cursor:default}
.pa-slots{display:flex;flex-direction:column;gap:0;max-width:420px}
.pa-slot{border:1.5px dashed var(--line);border-radius:3px;min-height:46px;display:flex;
  align-items:center;justify-content:center;font-size:15px;font-weight:600;padding:10px 12px;
  background:none;color:var(--soft);cursor:pointer;font-family:inherit;width:100%}
.pa-slot[data-filled="1"]{border-style:solid;border-color:var(--ink);color:var(--ink)}
.pa-slot[data-ok="1"]{border-color:var(--teal);color:var(--teal)}
.pa-slot[data-ok="0"]{border-color:var(--amber)}
.pa-bond{display:flex;align-items:center;justify-content:center;gap:8px;padding:6px 0}
.pa-bond button{font-family:'IBM Plex Mono',monospace;font-size:15px;line-height:1;
  border:1px solid var(--line);border-radius:3px;background:none;color:var(--soft);
  width:44px;height:38px;cursor:pointer}
.pa-bond button[aria-pressed="true"]{border-color:var(--teal);color:var(--teal);
  background:rgba(163,31,52,.06)}
.pa-bond .pa-bnote{font-family:'IBM Plex Mono',monospace;font-size:10.5px;color:var(--soft);
  letter-spacing:.05em}

/* Perturbation Lab ---------------------------------------------------- */
.pa-ctrls{display:flex;flex-wrap:wrap;gap:14px 22px;margin:0 0 18px}
.pa-ctrl{display:flex;flex-direction:column;gap:6px}
.pa-ctrl .pa-clab2{font-family:'IBM Plex Mono',monospace;font-size:10.5px;letter-spacing:.06em;
  text-transform:uppercase;color:var(--soft)}
.pa-ctrl .pa-cgrp{display:flex;gap:0;border:1px solid var(--line);border-radius:3px;
  overflow:hidden;width:fit-content}
.pa-ctrl button{font-family:'IBM Plex Mono',monospace;font-size:11.5px;border:0;
  background:none;color:var(--ink);padding:10px 14px;cursor:pointer;min-height:44px}
.pa-ctrl button[aria-pressed="true"]{background:var(--teal);color:var(--on-teal,#fff)}
.pa-diagram{overflow-x:auto;margin:0 0 18px}
.pa-diagram svg{display:block;max-width:100%;height:auto}
.pa-dnode rect{fill:none;stroke:var(--line);stroke-width:1.5}
.pa-dnode text{font-size:13px;font-weight:600;fill:var(--ink);text-anchor:middle;
  dominant-baseline:central}
.pa-dnode[data-flow="on"] rect{stroke:var(--teal);stroke-width:2}
.pa-dnode[data-flow="on"] text{fill:var(--teal)}
.pa-dedge{stroke:var(--line);stroke-width:1.6;fill:none}
.pa-dedge[data-flow="off"]{stroke-dasharray:4 5;opacity:.5}
.pa-dedge[data-flow="on"]{stroke:var(--teal);stroke-width:2}

/* progress page ------------------------------------------------------- */
.pa-mapframe{border:1px solid var(--line);border-radius:3px;margin:0 0 28px}
.pa-mapbar{display:flex;align-items:center;justify-content:space-between;gap:14px;
  flex-wrap:wrap;padding:11px 16px;border-bottom:1px solid var(--line)}
.pa-mapbar .pa-stats{font-family:'IBM Plex Mono',monospace;font-size:11.5px;color:var(--soft)}
.pa-mapbar .pa-stats b{color:var(--ink)}
.pa-seg{display:flex;border:1px solid var(--line);border-radius:3px;overflow:hidden}
.pa-seg button{font-family:'IBM Plex Mono',monospace;font-size:10.5px;letter-spacing:.05em;
  text-transform:uppercase;border:0;background:none;color:var(--soft);padding:9px 13px;
  cursor:pointer;min-height:44px}
.pa-seg button[aria-pressed="true"]{background:var(--teal);color:var(--on-teal,#fff)}
.pa-mapwrap{padding:8px 10px 4px;overflow-x:auto}
.pa-map{width:100%;height:auto;display:block}
.pa-band{fill:currentColor;opacity:.03}
.pa-bandlab{font-family:'IBM Plex Mono',monospace;font-size:15px;letter-spacing:.1em;
  fill:var(--soft)}
.pa-bandsub{font-family:'IBM Plex Mono',monospace;font-size:13px;fill:var(--soft);opacity:.6}
.pa-rest{fill:var(--soft);opacity:.22}
.pa-mede{stroke:var(--line);stroke-width:1.5;opacity:.5;fill:none}
.pa-mede[data-on="1"]{stroke:var(--teal);stroke-width:2.2;opacity:.95}
.pa-mede[data-ind="1"]{stroke-dasharray:7 6}
.pa-mehead{fill:var(--line);opacity:.5}
.pa-mehead[data-on="1"]{fill:var(--teal);opacity:.95}
.pa-mn{cursor:pointer}
.pa-mn rect{stroke-width:2}
.pa-mn text{font-size:15px;font-weight:600;text-anchor:middle;dominant-baseline:central;
  fill:var(--ink)}
.pa-mn[data-m="0"] rect{fill:none;stroke:var(--line);stroke-dasharray:5 5;stroke-width:1.6}
.pa-mn[data-m="0"] text{fill:var(--soft);font-weight:500}
.pa-mn[data-m="1"] rect{fill:var(--pa-tint,rgba(163,31,52,.09));stroke:var(--teal);
  stroke-opacity:.5}
.pa-mn[data-m="2"] rect{fill:var(--pa-tint,rgba(163,31,52,.09));stroke:var(--teal)}
.pa-mn[data-m="3"] rect,.pa-mn[data-m="4"] rect{fill:var(--teal);stroke:var(--teal)}
.pa-mn[data-m="3"] text,.pa-mn[data-m="4"] text{fill:var(--on-teal,#fff)}
.pa-mn rect.pa-gold{fill:none;stroke:var(--amber);stroke-width:2.6}
.pa-open rect{fill:url(#paHatch);stroke:var(--soft);stroke-dasharray:5 5;stroke-width:1.6}
.pa-open text{font-size:14px;fill:var(--soft);text-anchor:middle;dominant-baseline:central;
  font-style:italic}
.pa-openedge{fill:none;stroke:var(--soft);stroke-width:2;stroke-dasharray:2 7;
  stroke-linecap:round;opacity:.7}
.pa-opentag{font-family:'IBM Plex Mono',monospace;font-size:13px;fill:var(--soft)}
.pa-legend{display:flex;gap:20px 26px;flex-wrap:wrap;padding:13px 16px;
  border-top:1px solid var(--line)}
.pa-lg{display:flex;align-items:center;gap:9px;font-size:12.5px;color:var(--soft)}
.pa-sw{width:32px;height:19px;flex:none;border:2px solid var(--teal);border-radius:2px}
.pa-sw.s0{border:1.6px dashed var(--line)}
.pa-sw.s1{background:var(--pa-tint,rgba(163,31,52,.09))}
.pa-sw.s3{background:var(--teal)}
.pa-sw.s4{background:var(--teal);box-shadow:inset 0 0 0 2.5px var(--amber)}
.pa-sw.sopen{border:1.6px dashed var(--soft);background:repeating-linear-gradient(45deg,
  transparent,transparent 3px,var(--line) 3px,var(--line) 4.5px)}
.pa-nodepanel{border-top:1px solid var(--line);padding:15px 18px 18px;display:flex;
  gap:22px;flex-wrap:wrap}
.pa-nodepanel .pa-col{flex:1 1 280px;min-width:min(100%,260px)}
.pa-pips{display:flex;gap:5px;margin:9px 0 10px}
.pa-pips i{width:26px;height:7px;background:var(--line);display:block}
.pa-pips i.on{background:var(--teal)}
.pa-pips i.gold{background:var(--amber)}

/* badges -------------------------------------------------------------- */
.pa-shelf{display:flex;flex-wrap:wrap;gap:22px 26px;padding:22px 18px;
  border:1px solid var(--line);border-radius:3px;margin:0 0 12px}
.pa-badge{width:112px;text-align:center}
.pa-badge svg{display:block;margin:0 auto}
.pa-badge .pa-bn{font-size:12px;line-height:1.35;margin-top:8px;font-weight:600}
.pa-badge .pa-bs{font-family:'IBM Plex Mono',monospace;font-size:10px;color:var(--soft);
  margin-top:3px;letter-spacing:.03em}
.pa-badge[data-state="locked"] .pa-bn{color:var(--soft);font-weight:500}
.pa-bring-track{stroke:var(--line);fill:none}
.pa-bring-fill{stroke:var(--teal);fill:none}
.pa-bseal{fill:var(--teal)}
.pa-bseal-h{fill:none;stroke:var(--line);stroke-width:3}
.pa-bglyph{stroke:var(--teal);fill:none;stroke-width:3;stroke-linecap:round;
  stroke-linejoin:round}
.pa-bglyph .pa-solid{fill:var(--teal);stroke:none}
.pa-badge[data-state="locked"] .pa-bglyph{stroke:var(--soft);opacity:.55}
.pa-badge[data-state="locked"] .pa-bglyph .pa-solid{fill:var(--soft)}
.pa-badge[data-state="progress"] .pa-bglyph{stroke:var(--soft);opacity:.85}
.pa-badge[data-state="progress"] .pa-bglyph .pa-solid{fill:var(--soft)}
.pa-pip{fill:var(--line)}
.pa-pip.on{fill:var(--amber)}
.pa-crit{list-style:none;padding:0;margin:0;border-top:1px solid var(--line)}
.pa-crit li{border-bottom:1px solid var(--line);padding:12px 4px;display:flex;gap:14px;
  align-items:flex-start;flex-wrap:wrap}
.pa-crit .pa-cn{font-weight:700;font-size:14.5px;flex:0 0 190px}
.pa-crit .pa-cc{font-size:13.5px;color:var(--soft);flex:1 1 260px;line-height:1.55}
.pa-crit .pa-cv{font-family:'IBM Plex Mono',monospace;font-size:11.5px;color:var(--teal);
  font-weight:600;white-space:nowrap}

/* misc ---------------------------------------------------------------- */
.pa-tools{display:flex;gap:10px;flex-wrap:wrap;margin:0 0 10px}
.pa-tools button{font-family:'IBM Plex Mono',monospace;font-size:11.5px;letter-spacing:.04em;
  border:1px solid var(--line);border-radius:3px;background:none;color:var(--ink);
  padding:10px 14px;cursor:pointer;min-height:44px}
.pa-tools button:hover{border-color:var(--teal);color:var(--teal)}
.pa-note{font-size:13.5px;color:var(--soft);line-height:1.6}
.pa-fallback{margin:26px 0 0}
.pa-fallback details{border-bottom:1px solid var(--line);padding:12px 0}
.pa-fallback summary{cursor:pointer;font-weight:600;font-size:15px;line-height:1.5}
.pa-fallback .pa-ans{font-size:14px;color:var(--soft);margin:10px 0 0;line-height:1.6}
.pa-fallback .pa-ans b{color:var(--ink)}
.pa-hidden{display:none}
@media (max-width:560px){
  .pa-badge{width:96px}
  .pa-crit .pa-cn{flex:1 1 100%}
}
"""


# --------------------------------------------------------------- engine js ---
# Stejny defenzivni vzorec jako PROGRESS_JS v build_academy.py: kazdy read i
# write do localStorage je obaleny, a stranka se vykresli spravne, kdyz uloziste
# neni k dispozici nebo je prazdne. Zadny fetch, zadny ucet, zadna analytika
# navic (gtag uz nacita shell()).
#
# ES5 zamerne: zbytek webu nema build krok ani transpiler, takze zadne sipkove
# funkce, template literaly ani let/const -- ta konzistence uz jednou zachranila
# starsi prohlizec v Entity Browseru.

ENGINE_JS = """
<script>
window.PA = (function(){
  var D = null, S = null, KEY = 'atlas-practice-v1';
  var DAY = 86400000;

  function today(){ return Math.floor(Date.now()/DAY); }
  function clamp(x,a,b){ return x<a?a:(x>b?b:x); }

  function boot(dataId){
    var el = document.getElementById(dataId);
    if(!el) return null;
    try { D = JSON.parse(el.textContent); } catch(err){ return null; }
    KEY = (D.cfg && D.cfg.storageKey) || KEY;
    S = read();
    return D;
  }

  function blank(){
    return {v:1, xp:0, rank:1, m:{}, seen:{}, br:[],
            met:{predictOk:0, predictLessons:[], wirePerfect:0, wirePerfectHard:0,
                 limitsOk:0, sprintOk:0, answered:0},
            bg:{}, day:{d:0, ids:[], done:0}, st:{n:0,d:0}, snaps:[], exam:null};
  }
  function read(){
    var o;
    try { o = JSON.parse(localStorage.getItem(KEY)||'null'); } catch(err){ o = null; }
    if(!o || typeof o !== 'object') return blank();
    var b = blank(), k;
    for(k in b){ if(!(k in o)) o[k] = b[k]; }
    for(k in b.met){ if(!(k in o.met)) o.met[k] = b.met[k]; }
    return o;
  }
  function save(){
    try { localStorage.setItem(KEY, JSON.stringify(S)); } catch(err){}
  }
  function state(){ return S; }
  function data(){ return D; }

  /* ---------------- mastery (with decay) ---------------- */
  /* Mastery is what you can do NOW. A node you stop practising slides back
     towards "learning" -- but never all the way to untouched, because you did
     once know it. That floor is deliberate: the review queue should nag, not
     erase. */
  function mastery(id){
    var rec = S.m[id]; if(!rec) return 0;
    var cf = D.cfg.mastery, lvl = rec[0], age = today() - rec[1];
    if(lvl >= cf.decayFrom && cf.halfLifeDays > 0){
      var drop = Math.floor(age / cf.halfLifeDays);
      lvl = Math.max(cf.decayFrom - 1, lvl - drop);
    }
    return clamp(lvl, 0, cf.max);
  }
  function bumpMastery(ids, ok, sure){
    var cf = D.cfg.mastery, i, id, lvl;
    for(i=0;i<(ids||[]).length;i++){
      id = ids[i];
      lvl = mastery(id);
      if(ok){ lvl += (sure ? cf.gainRightSure : cf.gainRight); }
      else  { lvl -= (sure ? cf.loseWrongSure : cf.loseWrong); }
      S.m[id] = [clamp(lvl,0,cf.max), today()];
    }
  }
  function masteredCount(minLevel){
    var n=0, id;
    for(id in D.nodes){ if(mastery(id) >= minLevel) n++; }
    return n;
  }

  /* ---------------- scoring ---------------- */
  function calibBand(p, ok){
    /* Sure and right pays most; sure and wrong pays nothing. Never negative --
       punishing points teaches people to stop committing to a judgement, which
       is the opposite of what this whole layer is for. */
    var c = D.cfg.xp.calibration, sure = (p >= D.cfg.confidence.sureThreshold);
    if(ok) return sure ? c.sureRight : c.unsureRight;
    return sure ? c.sureWrong : c.unsureWrong;
  }
  function noveltyFor(item){
    var seen = S.seen[item.id];
    if(!seen) return D.cfg.xp.novelty.first;
    if(seen[1] === today() && seen[0] >= D.cfg.xp.novelty.sameDayCap) return 0;
    return D.cfg.xp.novelty.review;
  }
  function scoreItem(item, ok, p){
    var cf = D.cfg.xp;
    var base = cf.base[item.game] || 10;
    var diff = cf.difficulty[String(item.diff||1)] || 1;
    var cal  = (p === null) ? (ok ? 1 : 0) : calibBand(p, ok);
    var nov  = noveltyFor(item);
    var xp = Math.round(base * diff * cal * nov);
    if(ok && nov === cf.novelty.first && !(S.seen[item.id])) xp += cf.firstTryBonus;
    return Math.max(0, xp);
  }

  /* ---------------- Brier ---------------- */
  function pushBrier(p, ok){
    if(p === null) return;
    S.br.push([Math.round(p*100)/100, ok?1:0]);
    var w = D.cfg.confidence.window * 2;
    if(S.br.length > w) S.br = S.br.slice(S.br.length - w);
  }
  function brier(){
    var w = D.cfg.confidence.window;
    var a = S.br.slice(Math.max(0, S.br.length - w));
    if(a.length < 5) return null;
    var s = 0, i;
    for(i=0;i<a.length;i++){ s += Math.pow(a[i][0] - a[i][1], 2); }
    return {v: s/a.length, n: a.length};
  }

  /* ---------------- answering ---------------- */
  function record(item, ok, p){
    var sure = (p !== null && p >= D.cfg.confidence.sureThreshold);
    var xp = scoreItem(item, ok, p);
    var seen = S.seen[item.id];
    S.seen[item.id] = [ (seen?seen[0]:0) + 1, today(), seen ? seen[2] : (ok?1:0) ];
    S.xp += xp;
    S.met.answered++;
    bumpMastery(item.nodes, ok, sure);
    pushBrier(p, ok);
    if(ok){
      if(item.game === 'pert' || item.game === 'predict'){
        S.met.predictOk++;
        if(item.lesson && S.met.predictLessons.indexOf(item.lesson) < 0)
          S.met.predictLessons.push(item.lesson);
      }
      if(item.game === 'limits') S.met.limitsOk++;
      if(item.game === 'sprint') S.met.sprintOk++;
    }
    touchStreak();
    snapshot();
    var gained = evalBadges();
    save();
    return {xp: xp, badges: gained};
  }
  function recordWire(puz, bonds, perfect){
    var cf = D.cfg.xp;
    var xp = Math.round((cf.base.wire + cf.wirePerBond*bonds) *
                        (cf.difficulty[String(puz.diff)]||1) * noveltyFor({id:puz.id}));
    var seen = S.seen[puz.id];
    S.seen[puz.id] = [ (seen?seen[0]:0)+1, today(), seen ? seen[2] : (perfect?1:0) ];
    S.xp += xp;
    S.met.answered++;
    bumpMastery(puz.seq, perfect, false);
    if(perfect){
      S.met.wirePerfect++;
      if(puz.diff >= 3) S.met.wirePerfectHard++;
    }
    touchStreak(); snapshot();
    var gained = evalBadges();
    save();
    return {xp: xp, badges: gained};
  }

  /* ---------------- streak (freezable, never punitive) ---------------- */
  function touchStreak(){
    var t = today(), gap = t - (S.st.d||0);
    if(gap === 0) return;
    if(S.st.d && gap <= (D.cfg.daily.streakFreezeDays||3)) S.st.n++;
    else S.st.n = 1;
    S.st.d = t;
  }

  /* ---------------- snapshots ("a month ago") ---------------- */
  function snapshot(){
    var t = today(), every = D.cfg.snapshotEveryDays || 7;
    var last = S.snaps.length ? S.snaps[S.snaps.length-1][0] : -9999;
    if(t - last < every) return;
    var m = {}, id;
    for(id in D.nodes){ var v = mastery(id); if(v) m[id] = v; }
    S.snaps.push([t, m]);
    if(S.snaps.length > (D.cfg.snapshotKeep||8)) S.snaps.shift();
  }
  function snapshotBack(days){
    var t = today() - days, best = null, i;
    for(i=0;i<S.snaps.length;i++){ if(S.snaps[i][0] <= t) best = S.snaps[i]; }
    if(!best && S.snaps.length) best = S.snaps[0];
    return best ? best[1] : {};
  }

  /* ---------------- badges ---------------- */
  function metricValue(b){
    if(b.metric === 'brier'){ var br = brier(); return br ? br.v : null; }
    if(b.metric === 'coreMastered'){
      var need = 0, have = 0, id;
      for(id in D.nodes){
        if(D.nodes[id].pool !== 'core') continue;
        need++; if(mastery(id) >= D.cfg.mastery.masteredFrom) have++;
      }
      return need && have === need ? 1 : 0;
    }
    return S.met[b.metric] || 0;
  }
  function badgeProgress(b){
    /* -> {tier, next, pct, value} ; tier 0 = not earned yet */
    var v = metricValue(b), tier = 0, i, pct = 0, next = b.tiers[0];
    if(b.metric === 'brier'){
      var br = brier(), min = b.minSamples || 0;
      if(!br || br.n < min){
        return {tier:0, value:v, next:b.tiers[0], pct: br ? Math.min(99, Math.round(br.n/min*100)) : 0,
                gate:'need ' + min + ' judgements'};
      }
      for(i=0;i<b.tiers.length;i++){ if(v <= b.tiers[i]) tier = i+1; }
      next = b.tiers[Math.min(tier, b.tiers.length-1)];
      pct = tier ? 100 : clamp(Math.round((0.25 - v) / (0.25 - b.tiers[0]) * 100), 0, 99);
      return {tier:tier, value:v, next:next, pct:pct};
    }
    if(b.spread && b.spread.min){
      var got = (S.met[b.spread.key]||[]).length || 0;
      if(got < b.spread.min && v >= b.tiers[0]){
        return {tier:0, value:v, next:b.tiers[0],
                pct: Math.min(99, Math.round(got/b.spread.min*100)),
                gate:'across ' + b.spread.min + ' lessons (' + got + ')'};
      }
    }
    for(i=0;i<b.tiers.length;i++){ if(v >= b.tiers[i]) tier = i+1; }
    next = b.tiers[Math.min(tier, b.tiers.length-1)];
    pct = tier >= b.tiers.length ? 100 : clamp(Math.round(v / next * 100), 0, 99);
    return {tier:tier, value:v, next:next, pct: tier ? Math.max(pct, 100/b.tiers.length*tier) : pct};
  }
  function evalBadges(){
    var gained = [], i, b, p;
    for(i=0;i<D.cfg.badges.length;i++){
      b = D.cfg.badges[i];
      if(b.phase !== 'A') continue;
      p = badgeProgress(b);
      if(p.tier > (S.bg[b.id]||0)){
        S.bg[b.id] = p.tier;
        gained.push({id:b.id, name:b.name, tier:p.tier});
      }
    }
    return gained;
  }

  /* ---------------- ranks ---------------- */
  function rankDef(n){
    var i; for(i=0;i<D.cfg.ranks.length;i++){ if(D.cfg.ranks[i].n === n) return D.cfg.ranks[i]; }
    return D.cfg.ranks[0];
  }
  function nextRank(){ return rankDef(S.rank + 1); }
  function rankReady(){
    var r = nextRank();
    if(!r || r.n === S.rank || r.phase !== 'A') return false;
    if(S.xp < r.xp) return false;
    if(masteredCount(r.masteredAt || 3) < (r.masteredNodes||0)) return false;
    if(r.brier){ var br = brier(); if(!br || br.v > r.brier) return false; }
    return true;
  }
  function promote(){ S.rank = Math.min(S.rank+1, 3); save(); }
  function unlocked(what){
    var i, r;
    for(i=0;i<D.cfg.ranks.length;i++){
      r = D.cfg.ranks[i];
      if(r.n > S.rank) continue;
      if((r.unlocks||[]).indexOf(what) >= 0) return true;
    }
    return false;
  }

  /* ---------------- item pools ---------------- */
  function allowed(item){
    if(item.pool === 'route' && !unlocked('routepool')) return false;
    if(item.game === 'pert' && !unlocked('pert')) return false;
    if(item.game === 'limits' && !unlocked('limits')) return false;
    if((item.diff||1) > S.rank + 1) return false;
    return true;
  }
  function pool(game){
    var out = [], i, it;
    for(i=0;i<D.items.length;i++){
      it = D.items[i];
      if(game && it.game !== game) continue;
      if(!allowed(it)) continue;
      out.push(it);
    }
    return out;
  }
  function wirePool(){
    var out = [], i, p;
    for(i=0;i<D.wire.length;i++){
      p = D.wire[i];
      if(p.pool === 'route' && !unlocked('routepool')) continue;
      if(p.diff >= 3 && !unlocked('wirehard')) continue;
      out.push(p);
    }
    return out;
  }
  function shuffle(a){
    var i, j, t;
    for(i=a.length-1;i>0;i--){ j = Math.floor(Math.random()*(i+1)); t=a[i]; a[i]=a[j]; a[j]=t; }
    return a;
  }
  function weakestFirst(list){
    /* review order: lowest current mastery first, oldest first as tie-break */
    return list.slice().sort(function(a,b){
      var ma = itemMastery(a), mb = itemMastery(b);
      if(ma !== mb) return ma - mb;
      var sa = S.seen[a.id], sb = S.seen[b.id];
      return (sa?sa[1]:0) - (sb?sb[1]:0);
    });
  }
  function itemMastery(it){
    if(!it.nodes || !it.nodes.length) return 3;
    var s = 0, i;
    for(i=0;i<it.nodes.length;i++) s += mastery(it.nodes[i]);
    return s / it.nodes.length;
  }
  function daily(){
    var cf = D.cfg.daily, t = today();
    if(S.day.d === t && S.day.ids.length) return S.day.ids;
    var all = pool(null).filter(function(it){ return it.game !== 'sprint'; });
    var seen = [], fresh = [], stretch = [], i, it;
    for(i=0;i<all.length;i++){
      it = all[i];
      if(S.seen[it.id]) seen.push(it);
      else if((it.diff||1) > S.rank) stretch.push(it);
      else fresh.push(it);
    }
    var picked = [];
    picked = picked.concat(weakestFirst(seen).slice(0, cf.review));
    picked = picked.concat(shuffle(fresh).slice(0, cf.fresh));
    picked = picked.concat(shuffle(stretch).slice(0, cf.stretch));
    if(picked.length < cf.size)
      picked = picked.concat(shuffle(all).slice(0, cf.size - picked.length));
    var ids = [], used = {};
    for(i=0;i<picked.length && ids.length<cf.size;i++){
      if(used[picked[i].id]) continue;
      used[picked[i].id] = 1; ids.push(picked[i].id);
    }
    S.day = {d:t, ids:ids, done:0};
    save();
    return ids;
  }
  function itemById(id){
    var i; for(i=0;i<D.items.length;i++){ if(D.items[i].id === id) return D.items[i]; }
    return null;
  }
  function modelById(id){
    var i; for(i=0;i<D.models.length;i++){ if(D.models[i].id === id) return D.models[i]; }
    return null;
  }

  /* ---------------- export / import ---------------- */
  function exportBlob(){
    return JSON.stringify({app:'open-mtor-atlas-practice', v:1, saved:new Date().toISOString(),
                           state:S}, null, 1);
  }
  function importBlob(txt){
    var o;
    try { o = JSON.parse(txt); } catch(err){ return 'That file is not valid JSON.'; }
    var st = o && (o.state || (o.xp !== undefined ? o : null));
    if(!st || typeof st !== 'object') return 'That file does not look like a progress export.';
    S = st;
    var b = blank(), k;
    for(k in b){ if(!(k in S)) S[k] = b[k]; }
    save();
    return null;
  }
  function reset(){ S = blank(); save(); }

  return {boot:boot, state:state, data:data, save:save, today:today,
          mastery:mastery, masteredCount:masteredCount, record:record,
          recordWire:recordWire, brier:brier, badgeProgress:badgeProgress,
          rankDef:rankDef, nextRank:nextRank, rankReady:rankReady, promote:promote,
          unlocked:unlocked, pool:pool, wirePool:wirePool, daily:daily,
          itemById:itemById, modelById:modelById, shuffle:shuffle,
          snapshotBack:snapshotBack, exportBlob:exportBlob, importBlob:importBlob,
          reset:reset};
})();
</script>
"""


# ------------------------------------------------------------- practice js ---
# Ovladac stranky /academy/practice/. Vsechno, co tenhle skript dela, ma v HTML
# ekvivalent (staticka cvicebnice s odpovedmi v <details>), ktery se tady schova
# prave proto, ze uz je nahrazeny necim lepsim -- stejny kontrakt jako u kvizu
# a cviceni Faze 2. Pravidlo verify_practice.py to kontroluje.

PRACTICE_JS = """
<script>
(function(){
  var D = PA.boot('pa-data'); if(!D) return;
  var S = PA.state(), CFG = D.cfg;
  var board = document.getElementById('paBoard');
  var fall = document.getElementById('paFallback');
  if(fall) fall.hidden = true;

  var mode = null, queue = [], qi = 0, session = {ok:0, n:0, xp:0};

  /* ---------------- chrome ---------------- */
  function esc(s){ return String(s==null?'':s); }
  function el(html){ var d = document.createElement('div'); d.innerHTML = html; return d.firstChild; }

  function paintRank(){
    var r = PA.rankDef(S.rank), nx = PA.nextRank();
    var bar = document.getElementById('paRank'); if(!bar) return;
    var pct = 0, to = '';
    if(nx && nx.phase === 'A'){
      var span = Math.max(1, nx.xp - r.xp);
      pct = Math.max(0, Math.min(100, Math.round((S.xp - r.xp) / span * 100)));
      to = (nx.xp - S.xp > 0 ? (nx.xp - S.xp) + ' XP to ' : 'ready for ') + nx.name;
    } else {
      pct = 100; to = 'Phase B ranks open with the next set of games';
    }
    bar.innerHTML =
      '<div><p class="pa-rk">Rank ' + r.n + '</p><p class="pa-rkname">' + esc(r.name) + '</p></div>' +
      '<span class="pa-xp"><b>' + S.xp + '</b> Insight</span>' +
      '<span class="pa-meter"><i style="width:' + pct + '%"></i></span>' +
      '<span class="pa-to">' + esc(to) + '</span>' +
      (PA.rankReady() ? '<button class="pa-cbtn" id="paExam" type="button">Take the rank-up board</button>' : '');
    var ex = document.getElementById('paExam');
    if(ex) ex.addEventListener('click', function(){ startExam(); });
  }

  function paintTiles(){
    var wrap = document.getElementById('paTiles'); if(!wrap) return;
    var html = '', i, g, on;
    for(i=0;i<CFG.games.length;i++){
      g = CFG.games[i];
      on = S.rank >= g.rank;
      html += '<button class="pa-tile" type="button" data-game="' + g.id + '"' +
              (on ? '' : ' disabled') + ' aria-pressed="false">' +
              '<span class="pa-skill">' + esc(g.skill) + (on ? '' : ' &middot; rank ' + g.rank) + '</span>' +
              '<h3>' + esc(g.name) + '</h3><p>' + esc(g.blurb) + '</p></button>';
    }
    wrap.innerHTML = html;
    wrap.querySelectorAll('.pa-tile').forEach(function(b){
      b.addEventListener('click', function(){ start(b.getAttribute('data-game')); });
    });
  }
  function pressTile(id){
    var wrap = document.getElementById('paTiles'); if(!wrap) return;
    wrap.querySelectorAll('.pa-tile').forEach(function(b){
      b.setAttribute('aria-pressed', String(b.getAttribute('data-game') === id));
    });
  }

  /* ---------------- board shell ---------------- */
  function head(title, prog){
    return '<div class="pa-bhead"><span class="pa-t">' + esc(title) + '</span>' +
           '<span class="pa-prog">' + esc(prog||'') + '</span></div>';
  }
  function show(html){ board.innerHTML = html; board.hidden = false; }

  /* ---------------- confidence ---------------- */
  function confHtml(){
    if(S.rank >= CFG.confidence.sliderFromRank){
      return '<div class="pa-conf"><span class="pa-clab">How sure are you?</span>' +
        '<div class="pa-slider"><input type="range" id="paP" min="50" max="99" value="75" step="1" ' +
        'aria-label="Confidence in percent"><output id="paPo">75%</output>' +
        '<button class="pa-cbtn" id="paSubmit" type="button">Submit</button></div></div>';
    }
    var b = CFG.confidence.buttons, html = '', i;
    for(i=0;i<b.length;i++){
      html += '<button class="pa-cbtn" type="button" data-p="' + b[i].p + '">' + esc(b[i].label) + '</button>';
    }
    return '<div class="pa-conf"><span class="pa-clab">How sure are you?</span>' +
           '<div class="pa-cbtns">' + html + '</div></div>';
  }
  function wireConf(onPick){
    var slider = document.getElementById('paP');
    if(slider){
      var out = document.getElementById('paPo');
      slider.addEventListener('input', function(){ out.textContent = slider.value + '%'; });
      document.getElementById('paSubmit').addEventListener('click', function(){
        onPick(parseInt(slider.value,10)/100);
      });
      return;
    }
    board.querySelectorAll('.pa-cbtns .pa-cbtn').forEach(function(b){
      b.addEventListener('click', function(){
        board.querySelectorAll('.pa-cbtns .pa-cbtn').forEach(function(x){
          x.setAttribute('aria-pressed', String(x === b)); });
        onPick(parseFloat(b.getAttribute('data-p')));
      });
    });
  }

  /* ---------------- generic MCQ card ---------------- */
  function mcq(item, title, prog, after){
    var opts = '', i, letters = 'ABCDEFGH';
    for(i=0;i<item.options.length;i++){
      opts += '<button class="pa-opt" type="button" data-i="' + i + '">' +
              '<span class="pa-k">' + letters[i] + '</span><span>' + item.options[i] + '</span></button>';
    }
    show(head(title, prog) + '<div class="pa-body">' +
         '<p class="pa-q">' + item.prompt + '</p>' +
         (item.sub ? '<p class="pa-sub">' + esc(item.sub) + '</p>' : '') +
         '<div class="pa-opts">' + opts + '</div>' +
         '<div id="paConf"></div><div id="paFb"></div></div>');

    var chosen = -1;
    board.querySelectorAll('.pa-opt').forEach(function(b){
      b.addEventListener('click', function(){
        if(chosen >= 0) return;
        chosen = parseInt(b.getAttribute('data-i'),10);
        board.querySelectorAll('.pa-opt').forEach(function(x){ x.setAttribute('aria-pressed', String(x===b)); });
        b.style.borderColor = 'var(--ink)';
        document.getElementById('paConf').innerHTML = confHtml();
        wireConf(function(p){ grade(item, chosen, p, after); });
        var f = board.querySelector('#paConf .pa-cbtn, #paConf input'); if(f) f.focus();
      });
    });
  }

  function grade(item, chosen, p, after){
    var ok = (chosen === item.answer);
    var res = PA.record(item, ok, p);
    session.n++; session.xp += res.xp; if(ok) session.ok++;
    board.querySelectorAll('.pa-opt').forEach(function(b){
      var i = parseInt(b.getAttribute('data-i'),10);
      b.disabled = true; b.style.borderColor = '';
      if(i === item.answer) b.setAttribute('data-state','right');
      else if(i === chosen) b.setAttribute('data-state','wrong');
    });
    var conf = document.getElementById('paConf'); if(conf) conf.innerHTML = '';
    var msg = ok ? 'Correct.' : 'Not this time.';
    if(!ok && p !== null && p >= CFG.confidence.sureThreshold)
      msg += ' You were confident &mdash; that is the combination worth slowing down for.';
    if(ok && p !== null && p < CFG.confidence.sureThreshold)
      msg += ' You had it and did not trust it.';
    document.getElementById('paFb').innerHTML =
      '<div class="pa-fb" data-ok="' + (ok?1:0) + '"><b>' + msg + '</b> ' + esc2(item.explain) +
      (item.sid ? ' <span class="pa-sub">' + esc(item.sid) + '</span>' : '') +
      '<span class="pa-xpgain">+' + res.xp + ' Insight' + badgeLine(res.badges) + '</span></div>' +
      '<div class="pa-tools" style="margin-top:16px"><button id="paNext" type="button">Next &rarr;</button></div>';
    document.getElementById('paNext').addEventListener('click', after);
    document.getElementById('paNext').focus();
    paintRank();
  }
  function esc2(s){ return s == null ? '' : String(s); }
  function badgeLine(bs){
    if(!bs || !bs.length) return '';
    var names = bs.map(function(b){ return b.name + (b.tier>1 ? ' ' + 'I'.repeat(b.tier) : ''); });
    return ' &middot; badge earned: ' + names.join(', ');
  }

  /* ---------------- queue runner (daily / limits / exam) ---------------- */
  function runQueue(title){
    if(qi >= queue.length) return finish(title);
    var item = queue[qi];
    var prog = (qi+1) + ' / ' + queue.length;
    if(item.game === 'pert'){ pertCard(item, title, prog, next); }
    else { mcq(item, title, prog, next); }
    function next(){ qi++; runQueue(title); }
  }
  function finish(title){
    var pass = null;
    if(mode === 'exam'){
      pass = session.ok >= Math.ceil(queue.length * CFG.rankup.passRatio);
      if(pass) PA.promote();
    }
    if(mode === 'daily'){ S.day.done = 1; PA.save(); }
    show(head(title, '') + '<div class="pa-body">' +
      '<p class="pa-q">' + session.ok + ' of ' + session.n + ' &middot; +' + session.xp + ' Insight</p>' +
      (pass === null ? '' :
        '<p class="pa-fb">' + (pass ?
          '<b>Promoted.</b> You are now ' + esc(PA.rankDef(S.rank).name) + '. ' + esc(PA.rankDef(S.rank).blurb) :
          '<b>Not yet.</b> Nothing is lost &mdash; practise the weak nodes and take the board again.') + '</p>') +
      '<div class="pa-tools" style="margin-top:16px">' +
      '<button id="paBack" type="button">Back to the games</button>' +
      '<button id="paMap" type="button">See your pathway &rarr;</button></div></div>');
    document.getElementById('paBack').addEventListener('click', function(){
      board.hidden = true; pressTile(''); paintRank(); });
    document.getElementById('paMap').addEventListener('click', function(){
      location.href = '/academy/progress/'; });
    paintRank();
  }

  /* ---------------- Perturbation Lab ---------------- */
  function pertCard(item, title, prog, after){
    var M = PA.modelById(item.model);
    if(!M){ return mcq(item, title, prog, after); }
    var keys = (M.controls||[]).map(function(c){ return c.id; });
    var vals = item.state.split('|');
    var setting = '', i, c;
    for(i=0;i<(M.controls||[]).length;i++){
      c = M.controls[i];
      setting += '<div class="pa-ctrl"><span class="pa-clab2">' + esc(c.label) + '</span>' +
                 '<div class="pa-cgrp">' + c.options.map(function(o){
                   return '<button type="button" disabled aria-pressed="' +
                          (o === vals[i]) + '">' + esc(o) + '</button>'; }).join('') +
                 '</div></div>';
    }
    var readouts = PA.shuffle(M.readouts.slice()).slice(0,4);
    var right = M.states[item.state].readout;
    if(readouts.indexOf(right) < 0){ readouts[readouts.length-1] = right; }
    var q = dict(item, {options: readouts, answer: readouts.indexOf(right),
                        prompt: 'The controls are set as shown. <strong>Predict the readout</strong> before it is revealed.',
                        sub: M.title});
    show(head(title, prog) + '<div class="pa-body">' +
         '<div class="pa-ctrls">' + setting + '</div>' +
         '<div class="pa-diagram">' + diagram(M, null) + '</div>' +
         '<p class="pa-q">' + q.prompt + '</p><p class="pa-sub">' + esc(M.title) + '</p>' +
         '<div class="pa-opts">' + readouts.map(function(r,i){
            return '<button class="pa-opt" type="button" data-i="' + i + '">' +
                   '<span class="pa-k">' + 'ABCD'[i] + '</span><span>' + r + '</span></button>'; }).join('') +
         '</div><div id="paConf"></div><div id="paFb"></div></div>');

    var chosen = -1;
    board.querySelectorAll('.pa-opt').forEach(function(b){
      b.addEventListener('click', function(){
        if(chosen >= 0) return;
        chosen = parseInt(b.getAttribute('data-i'),10);
        b.style.borderColor = 'var(--ink)';
        document.getElementById('paConf').innerHTML = confHtml();
        wireConf(function(p){
          var st = M.states[item.state];
          document.querySelector('.pa-diagram').innerHTML = diagram(M, st);
          grade(q, chosen, p, after);
        });
      });
    });
  }
  function dict(base, over){
    var o = {}, k;
    for(k in base) o[k] = base[k];
    for(k in over) o[k] = over[k];
    return o;
  }
  function diagram(M, st){
    /* Kresli se z `layout` a `edges` modelu -- tedy z toho, co uz je v lekci.
       Bez stavu jsou vsechny uzly neutralni; se stavem se rozsviti flow a
       preruseny krok se vykresli carkovane. */
    var COLW = 168, BW = 132, BH = 34, GAPY = 52, PADX = 12, PADY = 16;
    var pos = {}, cols = M.layout || [], maxRows = 1, i, j;
    for(i=0;i<cols.length;i++) maxRows = Math.max(maxRows, cols[i].length);
    var H = PADY*2 + maxRows*BH + (maxRows-1)*(GAPY-BH);
    var W = PADX*2 + cols.length*COLW - (COLW-BW);
    for(i=0;i<cols.length;i++){
      for(j=0;j<cols[i].length;j++){
        pos[cols[i][j]] = {x: PADX + i*COLW + BW/2,
                           y: PADY + BH/2 + j*GAPY + (maxRows - cols[i].length)*GAPY/2};
      }
    }
    var on = {}, cut = {};
    if(st){ (st.flow||[]).forEach(function(n){ on[n]=1; }); (st.cut||[]).forEach(function(x){ cut[x]=1; }); }
    var svg = '<svg viewBox="0 0 ' + W + ' ' + H + '" width="' + W + '" height="' + H +
              '" role="img" aria-label="Model diagram">';
    (M.edges||[]).forEach(function(ed){
      var a = pos[ed.s], b = pos[ed.t]; if(!a || !b) return;
      var x1 = a.x + BW/2 + 3, x2 = b.x - BW/2 - 3, flow = st ? (cut[ed.id] ? 'off' : (on[ed.t] ? 'on' : 'off')) : '';
      if(x2 < x1){ x1 = a.x - BW/2 - 3; x2 = b.x + BW/2 + 3; }
      svg += '<path class="pa-dedge" data-flow="' + flow + '" d="M ' + x1 + ' ' + a.y +
             ' L ' + x2 + ' ' + b.y + '"/>';
      var dir = x2 > x1 ? 1 : -1;
      if(ed.eff === 'inhibits'){
        svg += '<path class="pa-dedge" data-flow="' + flow + '" d="M ' + x2 + ' ' + (b.y-7) +
               ' L ' + x2 + ' ' + (b.y+7) + '"/>';
      } else {
        svg += '<path class="pa-dedge" data-flow="' + flow + '" d="M ' + (x2-8*dir) + ' ' + (b.y-5) +
               ' L ' + x2 + ' ' + b.y + ' L ' + (x2-8*dir) + ' ' + (b.y+5) + '"/>';
      }
    });
    for(i=0;i<cols.length;i++){
      for(j=0;j<cols[i].length;j++){
        var id = cols[i][j], p = pos[id];
        svg += '<g class="pa-dnode" data-flow="' + (st ? (on[id]?'on':'off') : '') + '">' +
               '<rect x="' + (p.x-BW/2) + '" y="' + (p.y-BH/2) + '" width="' + BW + '" height="' + BH + '"/>' +
               '<text x="' + p.x + '" y="' + (p.y+1) + '">' + esc(M.labels[id] || id) + '</text></g>';
      }
    }
    return svg + '</svg>';
  }

  /* ---------------- Signal Sprint ---------------- */
  function sprint(){
    var cards = PA.shuffle(PA.pool('sprint').slice()).slice(0, CFG.sprint.cards);
    if(!cards.length) return;
    var left = CFG.sprint.seconds, k = 0, ok = 0, done = 0, timer;
    show(head('Signal Sprint', '') + '<div class="pa-body"><div class="pa-sprint">' +
         '<p class="pa-clock" id="paClock">' + left + 's</p>' +
         '<p class="pa-sprintq" id="paSq"></p>' +
         '<div class="pa-sprintbtns" id="paSb"></div>' +
         '<p class="pa-flash" id="paFlash"></p></div></div>');
    var clock = document.getElementById('paClock');
    timer = setInterval(function(){
      left--; clock.textContent = left + 's';
      if(left <= 0){ clearInterval(timer); end(); }
    }, 1000);
    function draw(){
      if(k >= cards.length) return end();
      var it = cards[k];
      document.getElementById('paSq').innerHTML = it.prompt;
      document.getElementById('paSb').innerHTML = it.options.map(function(o,i){
        return '<button type="button" data-i="' + i + '">' + esc(o) + '</button>'; }).join('');
      document.getElementById('paSb').querySelectorAll('button').forEach(function(b){
        b.addEventListener('click', function(){
          var i = parseInt(b.getAttribute('data-i'),10), good = (i === it.answer);
          var res = PA.record(it, good, null);
          done++; if(good) ok++;
          document.getElementById('paFlash').innerHTML = good
            ? 'correct &middot; +' + res.xp
            : 'no &mdash; ' + esc(it.options[it.answer]);
          k++; draw(); paintRank();
        });
      });
    }
    function end(){
      clearInterval(timer);
      session = {ok: ok, n: done, xp: 0};
      mode = 'sprint';
      show(head('Signal Sprint', '') + '<div class="pa-body">' +
        '<p class="pa-q">' + ok + ' of ' + done + ' in ' + CFG.sprint.seconds + ' seconds</p>' +
        '<p class="pa-note">Sprint is the one game scored on speed &mdash; everything else here rewards ' +
        'judgement instead. It is a warm-up, not a measure.</p>' +
        '<div class="pa-tools" style="margin-top:16px">' +
        '<button id="paAgain" type="button">Again</button>' +
        '<button id="paBack" type="button">Back to the games</button></div></div>');
      document.getElementById('paAgain').addEventListener('click', sprint);
      document.getElementById('paBack').addEventListener('click', function(){
        board.hidden = true; pressTile(''); });
      paintRank();
    }
    draw();
  }

  /* ---------------- Wire the Pathway ---------------- */
  function wire(){
    var puzzles = PA.wirePool();
    if(!puzzles.length) return;
    var P = puzzles[Math.floor(Math.random()*puzzles.length)];
    var labels = {}, i;
    for(i=0;i<P.seq.length;i++) labels[P.seq[i]] = D.nodes[P.seq[i]] ? D.nodes[P.seq[i]].label : P.seq[i];
    var chips = P.seq.slice();
    if(P.distractor){ chips.push(P.distractor); labels[P.distractor] = D.nodes[P.distractor].label; }
    chips = PA.shuffle(chips);
    var slots = new Array(P.seq.length), signs = new Array(P.seq.length-1), sel = null;
    var hard = P.diff >= 3;

    function render(){
      var html = head('Wire the Pathway', P.diff === 1 ? 'easy' : (P.diff === 2 ? 'medium' : 'hard')) +
        '<div class="pa-body"><p class="pa-q">' + esc(P.name || 'Rebuild this route') + '</p>' +
        '<p class="pa-sub">Place the steps in order, then set each arrow: &rarr; activates, &#8867; inhibits.' +
        (hard ? ' One chip does not belong on this route.' : '') + '</p>' +
        '<div class="pa-wire"><div class="pa-chips" id="paChips">' +
        chips.map(function(id){
          var used = slots.indexOf(id) >= 0;
          return '<button class="pa-chip" type="button" data-id="' + id + '" data-used="' + (used?1:0) + '"' +
                 ' aria-pressed="' + (sel===id) + '">' + esc(labels[id]) + '</button>'; }).join('') +
        '</div><div class="pa-slots" id="paSlots">';
      for(i=0;i<P.seq.length;i++){
        html += '<button class="pa-slot" type="button" data-s="' + i + '" data-filled="' +
                (slots[i]?1:0) + '">' + (slots[i] ? esc(labels[slots[i]]) : 'slot ' + (i+1)) + '</button>';
        if(i < P.seq.length-1){
          html += '<div class="pa-bond" data-b="' + i + '">' +
                  '<button type="button" data-sg="activates" aria-pressed="' + (signs[i]==='activates') + '" ' +
                  'title="activates">&rarr;</button>' +
                  '<button type="button" data-sg="inhibits" aria-pressed="' + (signs[i]==='inhibits') + '" ' +
                  'title="inhibits">&#8867;</button></div>';
        }
      }
      html += '</div></div><div class="pa-tools" style="margin-top:18px">' +
              '<button id="paCheck" type="button">Check</button>' +
              '<button id="paBack" type="button">Back to the games</button></div>' +
              '<div id="paFb"></div></div>';
      show(html);
      board.querySelectorAll('.pa-chip').forEach(function(b){
        b.addEventListener('click', function(){
          if(b.getAttribute('data-used') === '1') return;
          sel = (sel === b.getAttribute('data-id')) ? null : b.getAttribute('data-id');
          render();
        });
      });
      board.querySelectorAll('.pa-slot').forEach(function(b){
        b.addEventListener('click', function(){
          var k = parseInt(b.getAttribute('data-s'),10);
          if(slots[k]){ slots[k] = null; }
          else if(sel){ slots[k] = sel; sel = null; }
          render();
        });
      });
      board.querySelectorAll('.pa-bond button').forEach(function(b){
        b.addEventListener('click', function(){
          var k = parseInt(b.parentNode.getAttribute('data-b'),10);
          signs[k] = b.getAttribute('data-sg');
          render();
        });
      });
      document.getElementById('paCheck').addEventListener('click', check);
      document.getElementById('paBack').addEventListener('click', function(){
        board.hidden = true; pressTile(''); });
    }

    function check(){
      var okBonds = 0, wrong = [], i, allPlaced = true;
      for(i=0;i<P.seq.length;i++) if(!slots[i]) allPlaced = false;
      if(!allPlaced){
        document.getElementById('paFb').innerHTML =
          '<div class="pa-fb" data-ok="0"><b>Not finished.</b> Every slot needs a step before this can be checked.</div>';
        return;
      }
      for(i=0;i<P.steps.length;i++){
        var st = P.steps[i];
        var placed = (slots[i] === st.s && slots[i+1] === st.t);
        var signed = (signs[i] === st.eff);
        if(placed && signed) okBonds++;
        else wrong.push({i:i, st:st, placed:placed, signed:signed});
      }
      var perfect = (wrong.length === 0);
      var res = PA.recordWire(P, okBonds, perfect);
      board.querySelectorAll('.pa-slot').forEach(function(b){
        var k = parseInt(b.getAttribute('data-s'),10);
        b.setAttribute('data-ok', slots[k] === P.seq[k] ? '1' : '0');
      });
      var html = '<div class="pa-fb" data-ok="' + (perfect?1:0) + '"><b>' +
        (perfect ? 'The whole route is right.' : okBonds + ' of ' + P.steps.length + ' steps correct.') + '</b>';
      wrong.slice(0,3).forEach(function(w){
        html += '<br>' + esc(D.nodes[w.st.s].label) + ' ' + (w.st.eff === 'inhibits' ? 'inhibits' : 'activates') +
                ' ' + esc(D.nodes[w.st.t].label) +
                (w.st.dir === 'indirect' ? ' <em>(indirect &mdash; it runs through a step not drawn here)</em>' : '') +
                (w.st.why ? ' &mdash; ' + esc2(w.st.why) : '');
      });
      html += '<span class="pa-xpgain">+' + res.xp + ' Insight' + badgeLine(res.badges) + '</span></div>' +
              '<div class="pa-tools" style="margin-top:14px"><button id="paAgain" type="button">Another route</button>' +
              '<button id="paBack2" type="button">Back to the games</button></div>';
      document.getElementById('paFb').innerHTML = html;
      document.getElementById('paAgain').addEventListener('click', wire);
      document.getElementById('paBack2').addEventListener('click', function(){
        board.hidden = true; pressTile(''); });
      paintRank();
    }
    render();
  }

  /* ---------------- entry points ---------------- */
  function startQueue(ids, title){
    queue = ids.map(PA.itemById).filter(Boolean);
    qi = 0; session = {ok:0, n:0, xp:0};
    runQueue(title);
  }
  function startExam(){
    mode = 'exam';
    var nx = PA.nextRank();
    var all = PA.pool(null).filter(function(it){ return it.game !== 'sprint'; });
    var ids = PA.shuffle(all).slice(0, CFG.rankup.size).map(function(it){ return it.id; });
    pressTile('');
    startQueue(ids, 'Rank-up board &middot; ' + (nx ? nx.name : ''));
  }
  function start(game){
    mode = game; pressTile(game);
    if(game === 'sprint') return sprint();
    if(game === 'wire') return wire();
    if(game === 'daily') return startQueue(PA.daily(), 'Daily 5');
    var p = PA.pool(game);
    if(!p.length){ return; }
    var ids = PA.shuffle(p.slice()).slice(0,5).map(function(it){ return it.id; });
    startQueue(ids, game === 'pert' ? 'Perturbation Lab' : "What It Doesn't Show");
  }

  paintRank(); paintTiles();
  var note = document.getElementById('paStorage');
  if(note) note.hidden = false;
})();
</script>
"""


# ------------------------------------------------------------- progress js ---
# Mapa je zaroven diagnostika i odmena: kresli se ze SKUTECNYCH souradnic
# pathway/model.json, takze je to tentyz obrazek, ktery Atlas uz pouziva.
# Otevrene otazky se kresli srafovane a nikdy nedosahnou plne mastery.

PROGRESS_JS = """
<script>
(function(){
  var D = PA.boot('pa-data'); if(!D) return;
  var S = PA.state(), CFG = D.cfg, MAP = D.map;
  var fall = document.getElementById('paFallback'); if(fall) fall.hidden = true;
  var snap = 'now', sel = null, snapM = {};

  function esc(s){ return String(s==null?'':s); }
  function lvl(id){
    if(snap === 'now') return PA.mastery(id);
    return snapM[id] || 0;
  }
  /* Sirku i zkraceny popisek spocital build (fit_labels) z toho, kolik ma uzel
     na mape opravdu mista -- tady uz se jen cte, aby staticka a zivá mapa
     kreslily pixel po pixelu totez. */
  function mapLabel(n){ return n.dlab || n.label; }
  function boxW(n){ return n.dw || 78; }

  /* ---------------- map ---------------- */
  function clip(a, b, w, h){
    var dx = b.x-a.x, dy = b.y-a.y, hw = w/2+4, hh = h/2+4;
    if(!dx && !dy) return {x:a.x, y:a.y};
    var sx = dx ? hw/Math.abs(dx) : 1e9, sy = dy ? hh/Math.abs(dy) : 1e9;
    var s = Math.min(sx, sy);
    return {x: a.x + dx*s, y: a.y + dy*s};
  }
  function drawMap(){
    var svg = document.getElementById('paMap'); if(!svg) return;
    var BH = 34, s = '', i, id, n;
    s += '<defs><pattern id="paHatch" width="7" height="7" patternTransform="rotate(45)" ' +
         'patternUnits="userSpaceOnUse"><line x1="0" y1="0" x2="0" y2="7" stroke="currentColor" ' +
         'stroke-width="2.2" opacity=".26"/></pattern></defs>';
    for(i=0;i<MAP.bands.length;i++){
      var b = MAP.bands[i], c = MAP.comps[b.compartment] || {short:'', name:''};
      if(i % 2 === 0) s += '<rect class="pa-band" x="60" y="' + b.y + '" width="1400" height="' + b.h + '"/>';
      s += '<line x1="60" y1="' + b.y + '" x2="1460" y2="' + b.y + '" stroke="var(--line)"/>';
      var cy = b.y + b.h/2;
      s += '<text class="pa-bandlab" x="92" y="' + cy + '" text-anchor="middle" ' +
           'transform="rotate(-90 92 ' + cy + ')">' + esc(c.short) + '</text>';
      s += '<text class="pa-bandsub" x="112" y="' + cy + '" text-anchor="middle" ' +
           'transform="rotate(-90 112 ' + cy + ')">' + esc(c.name) + '</text>';
    }
    for(i=0;i<MAP.rest.length;i++)
      s += '<circle class="pa-rest" cx="' + MAP.rest[i][0] + '" cy="' + MAP.rest[i][1] + '" r="4.5"/>';

    /* open loop, drawn as a ghost edge that never resolves */
    s += '<path class="pa-openedge" d="M 860 1148 C 1430 1120 1440 300 1120 186"/>';
    s += '<text class="pa-opentag" x="1398" y="720" text-anchor="middle" ' +
         'transform="rotate(-90 1398 720)">open loop &middot; autophagy &rarr; amino-acid pool</text>';

    for(i=0;i<MAP.edges.length;i++){
      var ed = MAP.edges[i], A = D.nodes[ed.s], B = D.nodes[ed.t];
      if(!A || !B) continue;
      var on = (lvl(ed.s) >= CFG.mastery.masteredFrom && lvl(ed.t) >= CFG.mastery.masteredFrom) ? 1 : 0;
      var pa = clip(A, B, boxW(A), BH), pb = clip(B, A, boxW(B), BH);
      s += '<line class="pa-mede" data-on="' + on + '" data-ind="' + (ed.dir === 'indirect' ? 1 : 0) +
           '" x1="' + pa.x + '" y1="' + pa.y + '" x2="' + pb.x + '" y2="' + pb.y + '"/>';
      var ang = Math.atan2(pb.y-pa.y, pb.x-pa.x), cc = Math.cos(ang), ss = Math.sin(ang);
      if(ed.eff === 'inhibits'){
        s += '<line class="pa-mede" data-on="' + on + '" x1="' + (pb.x-8*ss) + '" y1="' + (pb.y+8*cc) +
             '" x2="' + (pb.x+8*ss) + '" y2="' + (pb.y-8*cc) + '"/>';
      } else {
        s += '<polygon class="pa-mehead" data-on="' + on + '" points="' + pb.x + ',' + pb.y + ' ' +
             (pb.x-13*cc-5.6*ss) + ',' + (pb.y-13*ss+5.6*cc) + ' ' +
             (pb.x-13*cc+5.6*ss) + ',' + (pb.y-13*ss-5.6*cc) + '"/>';
      }
    }
    /* the one localisation the Atlas keeps open */
    s += '<g class="pa-open"><rect x="1237" y="673" width="140" height="34"/>' +
         '<text x="1307" y="690">Golgi ?</text></g>';

    for(id in D.nodes){
      n = D.nodes[id];
      var v = lvl(id), w = boxW(n), m = v >= 4 ? 4 : (v >= 3 ? 3 : (v >= 2 ? 2 : (v >= 1 ? 1 : 0)));
      s += '<g class="pa-mn" data-m="' + m + '" data-id="' + esc(id) + '" tabindex="0" role="button">';
      if(v >= CFG.mastery.goldFrom)
        s += '<rect class="pa-gold" x="' + (n.x-w/2-5) + '" y="' + (n.y-BH/2-5) + '" width="' + (w+10) +
             '" height="' + (BH+10) + '"/>';
      s += '<rect x="' + (n.x-w/2) + '" y="' + (n.y-BH/2) + '" width="' + w + '" height="' + BH + '"/>' +
           '<text x="' + n.x + '" y="' + (n.y+1) + '">' + esc(mapLabel(n)) + '</text></g>';
    }
    svg.innerHTML = s;
    svg.querySelectorAll('.pa-mn').forEach(function(g){
      function pick(){ sel = g.getAttribute('data-id'); paintNode(); }
      g.addEventListener('click', pick);
      g.addEventListener('keydown', function(ev){
        if(ev.key === 'Enter' || ev.key === ' '){ ev.preventDefault(); pick(); }
      });
    });
    paintStats();
  }

  function paintStats(){
    var el = document.getElementById('paStats'); if(!el) return;
    var core = 0, tot = 0, mast = 0, gold = 0, learn = 0, id, v;
    for(id in D.nodes){
      tot++; if(D.nodes[id].pool === 'core') core++;
      v = lvl(id);
      if(v >= CFG.mastery.goldFrom) gold++;
      if(v >= CFG.mastery.masteredFrom) mast++;
      else if(v >= 1) learn++;
    }
    el.innerHTML = tot + ' Academy nodes of ' + D.counts.atlas + ' in the Atlas &middot; <b>' + mast +
      '</b> mastered (<b>' + gold + '</b> gold) &middot; <b>' + learn + '</b> learning &middot; <b>' +
      (tot-mast-learn) + '</b> untouched &middot; <b>2</b> open';
  }

  function paintNode(){
    var el = document.getElementById('paNodePanel'); if(!el) return;
    if(!sel){ el.innerHTML = '<div class="pa-col"><p class="pa-note">' +
      esc(CFG.copy.progressLede) + '</p></div>'; return; }
    var n = D.nodes[sel], v = lvl(sel), pips = '', i;
    for(i=0;i<CFG.mastery.max;i++)
      pips += '<i class="' + (i < v ? (v >= CFG.mastery.goldFrom ? 'on gold' : 'on') : '') + '"></i>';
    var next = v >= CFG.mastery.goldFrom
      ? 'You can predict what happens when this node is removed. Keep it fresh &mdash; mastery decays.'
      : (v >= CFG.mastery.masteredFrom
         ? 'Predict a perturbation involving this node in the Perturbation Lab to reach gold.'
         : (v > 0 ? 'Wire it correctly and answer a question about it to raise it.'
                  : 'Untouched. It shows up in Daily 5 once you reach the lesson that covers it.'));
    el.innerHTML =
      '<div class="pa-col"><p class="pa-q" style="font-size:18px;margin:0 0 2px">' + esc(n.label) + '</p>' +
      '<p class="pa-sub">mastery ' + v + ' / ' + CFG.mastery.max + ' &middot; ' + esc(n.comp) +
      ' &middot; ' + (n.pool === 'core' ? 'core' : 'guided route') + '</p>' +
      '<div class="pa-pips">' + pips + '</div></div>' +
      '<div class="pa-col"><p class="pa-sub">What moves it</p><p class="pa-note">' + next + '</p>' +
      (n.url ? '<p class="pa-note"><a href="' + esc(n.url) + '">Lesson: ' +
        esc(n.lesson.replace(/-/g, ' ')) + ' &rarr;</a></p>' : '') + '</div>';
  }

  /* ---------------- badges ---------------- */
  var RING = 'M40.89 7.57 A26 26 0 1 1 23.11 7.57';
  var GLYPH = {
   predictor: '<g class="pa-bglyph"><path d="M12 37 H24" stroke-dasharray="4 5"/>' +
     '<path d="M27 37 H38"/><path d="M34 33 l4 4 -4 4"/><circle class="pa-solid" cx="47" cy="37" r="4"/></g>',
   architect: '<g class="pa-bglyph"><path d="M17 47 L29 34"/><path d="M28 39 l1 -5 5 1"/>' +
     '<path d="M35 34 L47 47"/><path d="M43 49 l7 -4"/><circle class="pa-solid" cx="14" cy="49" r="3.6"/>' +
     '<circle class="pa-solid" cx="32" cy="32" r="3.6"/></g>',
   calibrated: '<g class="pa-bglyph"><path d="M15 47 A17 17 0 0 1 49 47"/><path d="M32 47 L43 36"/>' +
     '<circle class="pa-solid" cx="32" cy="47" r="3.2"/></g>',
   core: '<g class="pa-bglyph"><path d="M19 31 H27"/><path d="M37 31 H45"/><path d="M19 45 H27"/>' +
     '<path d="M37 45 H45"/><circle class="pa-solid" cx="15" cy="31" r="3.4"/>' +
     '<circle class="pa-solid" cx="32" cy="31" r="3.4"/><circle class="pa-solid" cx="49" cy="31" r="3.4"/>' +
     '<circle class="pa-solid" cx="15" cy="45" r="3.4"/><circle class="pa-solid" cx="32" cy="45" r="3.4"/>' +
     '<circle class="pa-solid" cx="49" cy="45" r="3.4"/></g>',
   limits: '<g class="pa-bglyph"><path d="M14 39 H27"/><path d="M27 39 L44 29"/><path d="M27 39 L44 49"/>' +
     '<path d="M40 28 l4 1 -1 4"/><circle class="pa-solid" cx="43" cy="49" r="4.4"/></g>',
   methods: '<g class="pa-bglyph"><path d="M20 26 H44 V50 H20 Z"/><path d="M25 33 H39"/>' +
     '<path d="M25 39 H35"/><path d="M25 45 H33" stroke-width="4"/><circle cx="41" cy="45" r="4.6"/></g>',
   smalln: '<g class="pa-bglyph"><path d="M17 29 V47"/><path d="M13 29 H21"/><path d="M13 47 H21"/>' +
     '<path d="M32 32 V50"/><path d="M28 32 H36"/><path d="M28 50 H36"/><path d="M47 27 V45"/>' +
     '<path d="M43 27 H51"/><path d="M43 45 H51"/><circle class="pa-solid" cx="17" cy="38" r="2.6"/>' +
     '<circle class="pa-solid" cx="32" cy="41" r="2.6"/><circle class="pa-solid" cx="47" cy="36" r="2.6"/></g>',
   unknown: '<g class="pa-bglyph"><clipPath id="paUnk"><circle cx="32" cy="38" r="12.5"/></clipPath>' +
     '<g clip-path="url(#paUnk)" stroke-width="2.4"><path d="M16 44 L28 26"/><path d="M22 48 L36 28"/>' +
     '<path d="M29 50 L44 30"/><path d="M37 52 L50 34"/></g><circle cx="32" cy="38" r="12.5"/></g>',
   sources: '<g class="pa-bglyph"><path d="M22 26 H16 V50 H22"/><path d="M42 26 H48 V50 H42"/>' +
     '<path d="M26 43 H38"/><circle class="pa-solid" cx="32" cy="34" r="4.2"/></g>',
   falsifier: '<g class="pa-bglyph"><circle cx="21" cy="38" r="8.5"/>' +
     '<circle cx="44" cy="38" r="8.5" stroke-dasharray="3.5 4.5"/><path d="M35 47 L53 29" stroke-width="3.4"/></g>'
  };
  function badgeSvg(id, size, state, pct, tiers, tier){
    var p = state === 'earned' ? 100 : (state === 'progress' ? (pct||0) : 0);
    var seal = state === 'earned'
      ? '<circle class="pa-bseal" cx="32" cy="15" r="9"/>'
      : '<circle class="pa-bseal-h" cx="32" cy="15" r="8"/>';
    var pips = '', i;
    if(tiers > 1){
      var gap = 7, x0 = 32 - gap*(tiers-1)/2;
      for(i=0;i<tiers;i++)
        pips += '<circle class="pa-pip' + ((state === 'earned' && i < (tier||1)) ? ' on' : '') +
                '" cx="' + (x0+i*gap) + '" cy="68" r="2.4"/>';
    }
    return '<svg width="' + size + '" height="' + Math.round(size*74/64) + '" viewBox="0 0 64 74" ' +
      'aria-hidden="true"><path class="pa-bring-track" d="' + RING + '" stroke-width="4.4" ' +
      'stroke-linecap="round" pathLength="100"/>' +
      (p > 0 ? '<path class="pa-bring-fill" d="' + RING + '" stroke-width="4.4" stroke-linecap="round" ' +
        'pathLength="100" stroke-dasharray="' + p + ' 100"/>' : '') +
      seal + (GLYPH[id]||'') + pips + '</svg>';
  }
  function roman(n){ return ['','I','II','III'][n] || String(n); }
  function paintBadges(){
    var shelf = document.getElementById('paShelf'), list = document.getElementById('paCrit');
    if(!shelf) return;
    var html = '', crit = '', i, b, p, state, sub;
    for(i=0;i<CFG.badges.length;i++){
      b = CFG.badges[i];
      if(b.phase === 'A'){
        p = PA.badgeProgress(b);
        state = p.tier ? 'earned' : (p.pct > 0 ? 'progress' : 'locked');
        sub = p.tier ? (b.tiers.length > 1 ? 'Tier ' + roman(p.tier) : 'Earned')
                     : (p.gate ? p.gate : (b.metric === 'brier'
                        ? (p.value ? p.value.toFixed(2) + ' &rarr; ' + b.tiers[0] : 'no data yet')
                        : p.value + ' / ' + p.next));
      } else {
        p = {tier:0, pct:0}; state = 'locked'; sub = 'phase B';
      }
      html += '<div class="pa-badge" data-state="' + state + '">' +
              badgeSvg(b.id, 76, state, p.pct, b.tiers.length, p.tier) +
              '<div class="pa-bn">' + esc(b.name) + '</div><div class="pa-bs">' + sub + '</div></div>';
      crit += '<li><span class="pa-cn">' + esc(b.name) + '</span>' +
              '<span class="pa-cc">' + esc(b.criterion) + '</span>' +
              '<span class="pa-cv">' + (b.phase === 'A' ? sub : 'phase B') + '</span></li>';
    }
    shelf.innerHTML = html;
    if(list) list.innerHTML = crit;
  }

  /* ---------------- calibration ---------------- */
  function paintCal(){
    var el = document.getElementById('paCal'); if(!el) return;
    var br = PA.brier();
    if(S.rank < CFG.confidence.showScoreFromRank){
      el.innerHTML = '<p class="pa-note">Your calibration is being recorded from the first question, ' +
        'but the score only starts showing at rank ' + CFG.confidence.showScoreFromRank +
        ' &mdash; below about 50 judgements the number says more about luck than about you.</p>';
      return;
    }
    if(!br){ el.innerHTML = '<p class="pa-note">Answer a few more questions with a confidence level ' +
      'and the score appears here.</p>'; return; }
    el.innerHTML = '<p class="pa-q" style="font-size:17px;margin:0 0 6px">Brier ' + br.v.toFixed(3) +
      ' <span class="pa-sub" style="margin-left:10px">over your last ' + br.n + ' judgements</span></p>' +
      '<p class="pa-note">Random guessing scores 0.25. &ldquo;Always 80% sure and right 80% of the time&rdquo; ' +
      'scores 0.16. A good expert sits near 0.10. Lower is better, and being wrong while certain is what ' +
      'moves it most.</p>';
  }

  /* ---------------- tools ---------------- */
  function wireTools(){
    var ex = document.getElementById('paExport');
    if(ex) ex.addEventListener('click', function(){
      var blob = new Blob([PA.exportBlob()], {type:'application/json'});
      var a = document.createElement('a');
      a.href = URL.createObjectURL(blob);
      a.download = 'mtor-atlas-practice.json';
      document.body.appendChild(a); a.click(); document.body.removeChild(a);
      setTimeout(function(){ URL.revokeObjectURL(a.href); }, 2000);
    });
    var imp = document.getElementById('paImport'), file = document.getElementById('paFile');
    if(imp && file){
      imp.addEventListener('click', function(){ file.click(); });
      file.addEventListener('change', function(){
        var f = file.files && file.files[0]; if(!f) return;
        var rd = new FileReader();
        rd.onload = function(){
          var err = PA.importBlob(String(rd.result));
          document.getElementById('paToolMsg').textContent =
            err ? err : 'Progress restored from that file.';
          if(!err){ S = PA.state(); redraw(); }
        };
        rd.readAsText(f);
      });
    }
    var rs = document.getElementById('paReset');
    if(rs) rs.addEventListener('click', function(){
      if(!window.confirm('Erase all practice progress in this browser? Export first if you want to keep it.')) return;
      PA.reset(); S = PA.state(); redraw();
      document.getElementById('paToolMsg').textContent = 'Progress cleared.';
    });
    document.querySelectorAll('#paSnap button').forEach(function(b){
      b.addEventListener('click', function(){
        snap = b.getAttribute('data-snap');
        document.querySelectorAll('#paSnap button').forEach(function(x){
          x.setAttribute('aria-pressed', String(x === b)); });
        snapM = snap === 'now' ? {} : PA.snapshotBack(30);
        drawMap(); paintNode();
      });
    });
  }

  function redraw(){ drawMap(); paintNode(); paintBadges(); paintCal(); paintHead(); }
  function paintHead(){
    var el = document.getElementById('paRank2'); if(!el) return;
    var r = PA.rankDef(S.rank);
    el.innerHTML = '<span class="pa-rk">Rank ' + r.n + '</span> <b>' + esc(r.name) + '</b> &middot; ' +
      S.xp + ' Insight &middot; ' + S.met.answered + ' judgements';
  }

  wireTools(); redraw();
})();
</script>
"""


# ------------------------------------------------------------- fallbacky ---
# Bez JS musi stranka zustat uzitecna. Ne "zapni si JavaScript", ale skutecna
# cvicebnice: otazky, moznosti, odpoved a vysvetleni v <details>. Tohle je
# stejny kontrakt jako u kvizu a cviceni Faze 2 -- a pravidlo ve
# verify_practice.py hlida, ze tady fallback opravdu je.

def fallback_sheet(bank, n_quiz=6, n_lim=3, n_sp=4):
    items = bank["items"]
    def take(game, n, key=None):
        got, seen_lesson = [], set()
        for it in items:
            if it["game"] != game:
                continue
            if key and it["lesson"] in seen_lesson:
                continue
            seen_lesson.add(it["lesson"])
            got.append(it)
            if len(got) >= n:
                break
        return got

    out = ['<div class="pa-fallback" id="paFallback">',
           '<h2>Practice questions</h2>',
           '<p class="pa-note">%s</p>' % e(bank["cfg"]["copy"]["noJs"])]
    for it in take("quiz", n_quiz, key=1) + take("limits", n_lim, key=1) + take("sprint", n_sp):
        opts = "".join('<li>%s</li>' % o for o in it["options"])
        out.append('<details><summary>%s</summary>'
                   '<ol class="pa-note" type="A">%s</ol>'
                   '<p class="pa-ans"><b>Answer: %s.</b> %s</p></details>'
                   % (it["prompt"], opts, "ABCDEFGH"[it["answer"]], it.get("explain") or ""))
    out.append("</div>")
    return "".join(out)


def wire_fallback(bank, n=2):
    """Wire the Pathway bez JS: cesta vypsana jako text, se znamenky a s tim,
    ktery krok je neprimy -- tedy presne to, co se ve hre skladá."""
    out = ['<div class="pa-fallback">', "<h2>Routes to rebuild</h2>",
           '<p class="pa-note">In the game these arrive as loose parts to be put back '
           'in order. Here they are written out, with the answer.</p>']
    seen = set()
    for p in bank["wire"]:
        if p["diff"] != 2 or p["route"] in seen:
            continue
        seen.add(p["route"])
        steps = " ".join(
            "%s %s" % (e(bank["nodes"][s["s"]]["label"]),
                       "&rarr;" if s["eff"] == "activates" else "&#8867;")
            for s in p["steps"])
        last = e(bank["nodes"][p["steps"][-1]["t"]]["label"])
        ind = [s for s in p["steps"] if s["dir"] == "indirect"]
        out.append('<details><summary>%s</summary><p class="pa-ans"><b>%s %s</b>%s</p></details>'
                   % (e(p["name"] or p["route"]), steps, last,
                      (" &mdash; %d of these steps is indirect: it runs through a step this "
                       "route does not draw." % len(ind)) if ind else ""))
        if len(seen) >= n:
            break
    out.append("</div>")
    return "".join(out)


CHAR_W = 8.6      # sirka znaku pri 15px DM Sans, zmereno na vygenerovane strance
BOX_PAD = 26
BOX_MIN = 68
BOX_MAX = 190
ROW_TOL = 20      # co je "stejna rada"
GUTTER = 10       # mezera mezi dvema sousednimi boxy


def fit_labels(meta):
    """Kazdemu uzlu spocita sirku boxu a popisek, ktery se do ni vejde.

    Bez tohohle se v hustych radach (uzly 79 jednotek od sebe) boxy prekryvaji
    -- coz na mape vypada jako chyba dat, i kdyz jsou souradnice v poradku.
    """
    ids = sorted(meta)
    for nid in ids:
        m = meta[nid]
        room = BOX_MAX
        for oid in ids:
            if oid == nid:
                continue
            o = meta[oid]
            if abs(o["y"] - m["y"]) > ROW_TOL:
                continue
            d = abs(o["x"] - m["x"])
            if d:
                room = min(room, d - GUTTER)
        want = len(m["label"]) * CHAR_W + BOX_PAD
        w = max(BOX_MIN, min(want, room))
        if w >= want:
            lab = m["label"]
        else:
            fit = int((w - BOX_PAD) / CHAR_W)
            lab = m["label"][:max(3, fit - 1)].rstrip() + "\u2026"
        m["dlab"] = lab
        m["dw"] = round(w, 1)
    return meta


def static_map(bank):
    """Mapa bez JS: stejne souradnice, vsechny uzly ve stavu untouched.
    JS ji pak jen prekresli podle mastery. Bez tohohle by /academy/progress/
    bez JS byla prazdna stranka -- a mapa je pritom obsah, ne skore."""
    m, mp = bank["nodes"], bank["map"]
    BH = 34
    s = ['<defs><pattern id="paHatch" width="7" height="7" patternTransform="rotate(45)" '
         'patternUnits="userSpaceOnUse"><line x1="0" y1="0" x2="0" y2="7" stroke="currentColor" '
         'stroke-width="2.2" opacity=".26"/></pattern></defs>']
    for i, b in enumerate(mp["bands"]):
        c = mp["comps"].get(b["compartment"], {"short": "", "name": ""})
        if i % 2 == 0:
            s.append('<rect class="pa-band" x="60" y="%s" width="1400" height="%s"/>' % (b["y"], b["h"]))
        s.append('<line x1="60" y1="%s" x2="1460" y2="%s" stroke="var(--line)"/>' % (b["y"], b["y"]))
        cy = b["y"] + b["h"] / 2
        s.append('<text class="pa-bandlab" x="92" y="%s" text-anchor="middle" '
                 'transform="rotate(-90 92 %s)">%s</text>' % (cy, cy, e(c["short"])))
        s.append('<text class="pa-bandsub" x="112" y="%s" text-anchor="middle" '
                 'transform="rotate(-90 112 %s)">%s</text>' % (cy, cy, e(c["name"])))
    for x, y in mp["rest"]:
        s.append('<circle class="pa-rest" cx="%s" cy="%s" r="4.5"/>' % (x, y))
    s.append('<path class="pa-openedge" d="M 860 1148 C 1430 1120 1440 300 1120 186"/>')
    s.append('<text class="pa-opentag" x="1398" y="720" text-anchor="middle" '
             'transform="rotate(-90 1398 720)">open loop &middot; autophagy &rarr; amino-acid pool</text>')
    for ed in mp["edges"]:
        a, b2 = m.get(ed["s"]), m.get(ed["t"])
        if not a or not b2:
            continue
        s.append('<line class="pa-mede" data-on="0" data-ind="%d" x1="%s" y1="%s" x2="%s" y2="%s"/>'
                 % (1 if ed["dir"] == "indirect" else 0, a["x"], a["y"], b2["x"], b2["y"]))
    s.append('<g class="pa-open"><rect x="1237" y="673" width="140" height="34"/>'
             '<text x="1307" y="690">Golgi ?</text></g>')
    for nid, n in sorted(m.items()):
        lab = n.get("dlab") or n["label"]
        w = n.get("dw") or 78
        s.append('<g class="pa-mn" data-m="0" data-id="%s"><rect x="%s" y="%s" width="%s" height="%s"/>'
                 '<text x="%s" y="%s">%s</text></g>'
                 % (e(nid), n["x"] - w / 2, n["y"] - BH / 2, w, BH, n["x"], n["y"] + 1, e(lab)))
    return "".join(s)


def badge_table(cfg):
    """Kriteria odznaku v HTML, nezavisle na JS: co se po tobe chce, je videt
    dopredu. Zamceny odznak s otaznikem by byl loterie, ne cil."""
    rows = []
    for b in cfg["badges"]:
        rows.append('<li><span class="pa-cn">%s</span><span class="pa-cc">%s</span>'
                    '<span class="pa-cv">%s</span></li>'
                    % (e(b["name"]), e(b["criterion"]),
                       "phase B" if b["phase"] != "A" else "&mdash;"))
    return '<ul class="pa-crit" id="paCrit">%s</ul>' % "".join(rows)


# ----------------------------------------------------------------- stranky ---

def payload(bank):
    """Banka se zapece do stranky jako JSON v <script type="application/json">.
    Stejny vzorec jako ac-rcdata u Research Challenges: zadny fetch, stranka je
    jeden soubor a funguje i offline."""
    slim = {k: bank[k] for k in ("v", "cfg", "nodes", "items", "models", "wire", "map", "counts")}
    txt = json.dumps(slim, ensure_ascii=False, separators=(",", ":"))
    # </script> uvnitr dat by ukoncilo blok drive, nez ma -- stejna past jako
    # v build_academy.py u rc_lab_data().
    txt = txt.replace("</", "<\\/")
    return '<script type="application/json" id="pa-data">%s</script>' % txt


def practice_page(bank):
    cfg = bank["cfg"]
    url = SITE + "/academy/practice/"
    body = ['<div class="ac-hero"><p class="ac-eyebrow">mTOR Academy &middot; Practice</p>'
            '<h1>Practice Arena</h1>'
            '<p class="ac-lede">%s</p></div>' % e(cfg["copy"]["hubLede"])]

    body.append('<div class="pa-rankbar pa-tint" id="paRank">'
                '<div><p class="pa-rk">Rank 1</p><p class="pa-rkname">Curious</p></div>'
                '<span class="pa-xp"><b>0</b> Insight</span>'
                '<span class="pa-meter"><i style="width:0%"></i></span>'
                '<span class="pa-to">Progress is kept in this browser</span></div>')

    # Dlazdice se bez JS vykresli jako popis her (ne tlacitka) -- porad rikaji,
    # co Practice Arena je a co v ni na sebe navazuje.
    tiles = []
    for g in cfg["games"]:
        tiles.append('<div class="pa-tile"><span class="pa-skill">%s</span><h3>%s</h3><p>%s</p></div>'
                     % (e(g["skill"]), e(g["name"]), e(g["blurb"])))
    body.append('<div class="pa-tiles" id="paTiles">%s</div>' % "".join(tiles))
    body.append('<div class="pa-board" id="paBoard" hidden></div>')

    body.append('<p class="pa-note" id="paStorage" hidden>%s '
                '<a href="%s/academy/progress/">Your pathway and badges &rarr;</a></p>'
                % (e(cfg["copy"]["storageNote"]), SITE))

    body.append('<h2>How the points work</h2>'
                '<p class="pa-note">Every question asks how sure you are <em>before</em> the answer '
                'appears. Being right while sure is worth the most; being right while unsure is worth '
                'less; being <strong>wrong while sure</strong> is worth nothing at all. There are no '
                'points for opening a page, no daily-login bonus and no streak to lose &mdash; the only '
                'thing that earns anything here is a judgement that could have been wrong.</p>'
                '<p class="pa-note">%s</p>' % e(cfg["copy"]["openNote"]))

    body.append(fallback_sheet(bank))
    body.append(wire_fallback(bank))

    ld = {"@context": "https://schema.org", "@type": "LearningResource",
          "name": "mTOR Practice Arena", "url": url, "inLanguage": "en",
          "learningResourceType": "Quiz",
          "educationalLevel": "Secondary and undergraduate",
          "description": "Practice games built on the Open mTOR Atlas pathway model: predict "
                         "perturbations, rebuild routes, and name what a result does not show.",
          "isPartOf": dict(DATASET_REF),
          "license": "https://creativecommons.org/licenses/by/4.0/"}
    bc = breadcrumb_ld([("Oliver's mTOR Atlas", SITE + "/"), ("Academy", SITE + "/academy/"),
                        ("Practice", None)])
    crumb = ('<a href="%s/">Oliver\'s mTOR Atlas</a> &middot; <a href="%s/academy/">Academy</a> '
             '&middot; Practice' % (SITE, SITE))
    from build_academy import ACADEMY_CSS
    return url, shell("Practice Arena | mTOR Academy",
                      "Short games built on the Atlas's own pathway model: predict what a "
                      "perturbation does, rebuild a signalling route, and say what a result does "
                      "not show. Points reward calibration, not speed.",
                      url, [ld, bc], "".join(body), crumb, active_tab="learn",
                      extra_css=ACADEMY_CSS + PRACTICE_CSS,
                      extra_body=payload(bank) + ENGINE_JS + PRACTICE_JS,
                      level_switch=False)


def progress_page(bank):
    cfg = bank["cfg"]
    url = SITE + "/academy/progress/"
    body = ['<div class="ac-hero"><p class="ac-eyebrow">mTOR Academy &middot; Progress</p>'
            '<h1>Your pathway</h1>'
            '<p class="ac-lede">%s</p></div>' % e(cfg["copy"]["progressLede"])]

    body.append('<p class="pa-note" id="paRank2"><span class="pa-rk">Rank 1</span> '
                '<b>Curious</b></p>')

    body.append('<div class="pa-mapframe pa-tint">'
                '<div class="pa-mapbar"><span class="pa-stats" id="paStats">'
                '%d Academy nodes of %d in the Atlas</span>'
                '<div class="pa-seg" id="paSnap" role="group" aria-label="Snapshot">'
                '<button type="button" data-snap="now" aria-pressed="true">Now</button>'
                '<button type="button" data-snap="then" aria-pressed="false">A month ago</button>'
                '</div></div>'
                '<div class="pa-mapwrap"><svg class="pa-map" id="paMap" viewBox="60 50 1400 1370" '
                'role="img" aria-label="Pathway map coloured by what you have mastered">%s</svg></div>'
                '<div class="pa-legend">'
                '<span class="pa-lg"><span class="pa-sw s0"></span>Untouched</span>'
                '<span class="pa-lg"><span class="pa-sw s1"></span>Learning</span>'
                '<span class="pa-lg"><span class="pa-sw s3"></span>Mastered</span>'
                '<span class="pa-lg"><span class="pa-sw s4"></span>Can predict it</span>'
                '<span class="pa-lg"><span class="pa-sw sopen"></span>Open question &mdash; never fills</span>'
                '</div>'
                '<div class="pa-nodepanel" id="paNodePanel"><div class="pa-col">'
                '<p class="pa-note">%s</p></div></div></div>'
                % (len(bank["nodes"]), bank["counts"]["atlas"], static_map(bank),
                   e(cfg["copy"]["progressLede"])))

    body.append('<h2>Calibration</h2><div id="paCal"><p class="pa-note">Every answer you give with a '
                'confidence level feeds one number: how well your certainty matches your accuracy. '
                'It is the one habit here that transfers to reading real papers.</p></div>')

    body.append('<h2>Badges</h2>'
                '<p class="pa-note">Ten of them, and no more. The map already shows what you know, so '
                'these reward what a map cannot show: prediction, calibration, and naming the limits '
                'of a result. Nothing here is awarded for showing up.</p>'
                '<div class="pa-shelf" id="paShelf"></div>')
    body.append(badge_table(cfg))

    body.append('<h2>Your data</h2>'
                '<p class="pa-note">%s</p>'
                '<div class="pa-tools">'
                '<button id="paExport" type="button">Export progress</button>'
                '<button id="paImport" type="button">Import a file</button>'
                '<button id="paReset" type="button">Clear progress</button>'
                '<input type="file" id="paFile" accept="application/json" class="pa-hidden">'
                '</div><p class="pa-note" id="paToolMsg"></p>' % e(cfg["copy"]["storageNote"]))

    ld = {"@context": "https://schema.org", "@type": "WebPage",
          "name": "Your pathway | mTOR Academy", "url": url, "inLanguage": "en",
          "description": "A map of the mTOR pathway coloured by what you have practised, with the "
                         "Academy's ten badges and their criteria.",
          "isPartOf": dict(DATASET_REF)}
    bc = breadcrumb_ld([("Oliver's mTOR Atlas", SITE + "/"), ("Academy", SITE + "/academy/"),
                        ("Progress", None)])
    crumb = ('<a href="%s/">Oliver\'s mTOR Atlas</a> &middot; <a href="%s/academy/">Academy</a> '
             '&middot; Progress' % (SITE, SITE))
    from build_academy import ACADEMY_CSS
    return url, shell("Your pathway | mTOR Academy",
                      "The mTOR pathway map coloured by what you have practised: grey nodes are "
                      "untested, gold ones you can predict, and open questions never fill in.",
                      url, [ld, bc], "".join(body), crumb, active_tab="learn",
                      extra_css=ACADEMY_CSS + PRACTICE_CSS,
                      extra_body=payload(bank) + ENGINE_JS + PROGRESS_JS,
                      robots="index, follow")


# ------------------------------------------------------------------- main ---

def build(verbose=True):
    cfg, les, pw = load()
    bank = build_bank(cfg, les, pw)
    urls = []
    for fn, sub in ((practice_page, "practice"), (progress_page, "progress")):
        url, page = fn(bank)
        write(os.path.join(ACADEMY_DIR, sub, "index.html"), page)
        urls.append((url, "0.8"))
    if verbose:
        c = bank["counts"]
        print("  Practice Arena: %d polozek, %d wire puzzlu, %d uzlu (core %d + route %d) z %d v modelu"
              % (c["items"], c["wire"], len(bank["nodes"]), c["core"], c["route"], c["atlas"]))
    return urls, bank


def main():
    build()


if __name__ == "__main__":
    main()
