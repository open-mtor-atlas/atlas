#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
verify_practice.py -- brana pro Practice Arenu (build_practice.py).

Stejna logika jako verify_academy.py: kontroluje se to, co se v teto vrstve
uz jednou POKAZILO nebo co by tise lhalo studentovi. Neni to unit test
generatoru, je to seznam invariantu, ktere musi platit o VYSTUPU.

PRAVIDLA
  P1  Kazdy uzel, na ktery se polozka odkazuje, existuje v pathway/model.json
      a lezi v pokryti lekci (core nebo guided route). Polozka mimo pokryti by
      studentovi ukazala hranu, o ktere web nikde neuci.
  P2  Kazda sprint polozka o znamenku odpovida skutecne interakci v modelu
      -- vcetne smeru a efektu. Vymyslena hrana je horsi nez chybejici hra.
  P3  Kazdy krok wire puzzlu je skutecna interakce; retez na sebe navazuje;
      rozptylovac (hard) na ceste NElezi.
  P4  Kazda pert polozka ma existujici model, existujici stav a neprazdny
      readout; moznosti se daji sestavit (model ma aspon dva ruzne readouty).
  P5  Kazdy odznak ma metriku, kterou engine skutecne pocita, neprazdne tiers
      a viditelne kriterium. Odznak bez merene metriky by nesel nikdy ziskat.
  P6  Prahy hodnosti rostou (XP i pocet zvladnutych uzlu) a faze A konci
      hodnosti 3 -- vys se ve fazi A nelze dostat, takze to nesmi byt slibeno.
  P7  Parita bez JS: obe stranky obsahuji staticky ekvivalent (cvicebnice s
      odpovedmi, staticka mapa, kriteria odznaku) -- ne "zapni si JavaScript".
  P8  Zapecena data neobsahuji ukoncovaci </script> a daji se naparsovat.
  P9  Otevrene otazky se nedaji "vyresit": zadna polozka netvrdi nic o hrane,
      kterou model vede jako open_loop.

    py verify_practice.py          # 0 = cisto, 1 = nalezy
"""

import os
import re
import sys
import json

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

PROBLEMS = []


def bad(where, msg):
    PROBLEMS.append("%s: %s" % (where, msg))


def main():
    import build_practice as BPR

    cfg, les, pw = BPR.load()
    bank = BPR.build_bank(cfg, les, pw)
    nodes = bank["nodes"]
    inter = {i["id"]: i for i in pw["interactions"]}
    pw_ids = {n["id"] for n in pw["nodes"]}

    # ---- P1 / P2 -----------------------------------------------------------
    for it in bank["items"]:
        w = "item %s" % it["id"]
        for nid in it.get("nodes") or []:
            if nid not in pw_ids:
                bad(w, "uzel %r neexistuje v model.json" % nid)
            elif nid not in nodes:
                bad(w, "uzel %r je mimo pokryti lekci (core/route)" % nid)
        if it["game"] == "sprint" and it["id"].startswith("sp:"):
            eid = it["id"][3:]
            i2 = inter.get(eid)
            if not i2:
                bad(w, "interakce %r neexistuje" % eid)
            else:
                want = "activates" if it["answer"] == 0 else "inhibits"
                if i2["effect"] != want:
                    bad(w, "efekt neodpovida modelu (%s vs %s)" % (want, i2["effect"]))
                if [i2["source"], i2["target"]] != it["nodes"]:
                    bad(w, "smer hrany neodpovida modelu")
        if it["options"] and not (0 <= it["answer"] < len(it["options"])):
            if it["game"] != "pert":
                bad(w, "index spravne odpovedi je mimo rozsah")

    # ---- P3 ----------------------------------------------------------------
    for p in bank["wire"]:
        w = "wire %s" % p["id"]
        seq = p["seq"]
        if len(seq) < 2:
            bad(w, "cesta kratsi nez dva uzly")
        for k, st in enumerate(p["steps"]):
            key = None
            for eid, i2 in inter.items():
                if i2["source"] == st["s"] and i2["target"] == st["t"] and i2["effect"] == st["eff"]:
                    key = eid
                    break
            if not key:
                bad(w, "krok %d (%s -> %s, %s) neni v modelu" % (k, st["s"], st["t"], st["eff"]))
            if seq[k] != st["s"] or seq[k + 1] != st["t"]:
                bad(w, "krok %d nenavazuje na poradi uzlu" % k)
        if p.get("distractor"):
            if p["distractor"] in seq:
                bad(w, "rozptylovac lezi na ceste -- past by mela spravnou odpoved")
            if p["distractor"] not in nodes:
                bad(w, "rozptylovac je mimo pokryti")

    # ---- P4 ----------------------------------------------------------------
    models = {m["id"]: m for m in bank["models"]}
    for it in bank["items"]:
        if it["game"] != "pert":
            continue
        w = "pert %s" % it["id"]
        M = models.get(it["model"])
        if not M:
            bad(w, "model %r chybi v payloadu" % it["model"])
            continue
        st = M["states"].get(it["state"])
        if not st:
            bad(w, "stav %r neni v modelu" % it["state"])
        elif not st.get("readout"):
            bad(w, "stav nema readout, nedá se z nej udelat predikce")
        if len(M["readouts"]) < 2:
            bad(w, "model ma jen jeden readout -- otazka by nemela rozptylovac")
        for col in M["layout"]:
            for nid in col:
                if nid not in pw_ids:
                    bad(w, "uzel schematu %r neni v modelu" % nid)

    # ---- P5 ----------------------------------------------------------------
    engine = open(os.path.join(HERE, "build_practice.py"), encoding="utf-8").read()
    engine_js = engine.split("ENGINE_JS = ")[1] if "ENGINE_JS = " in engine else ""
    for b in cfg["badges"]:
        w = "badge %s" % b["id"]
        if not b.get("tiers"):
            bad(w, "zadne tiers")
        if not b.get("criterion"):
            bad(w, "chybi viditelne kriterium")
        m = b["metric"]
        known = (("S.met." + m) in engine_js) or (("'" + m + "'") in engine_js)
        if b["phase"] == "A" and not known:
            bad(w, "metrika %r se nikde v enginu nepocita -- odznak by byl nezískatelny" % m)

    # ---- P6 ----------------------------------------------------------------
    last_xp, last_nodes = -1, -1
    for r in cfg["ranks"]:
        w = "rank %s" % r["id"]
        if r["xp"] <= last_xp and r["n"] > 1:
            bad(w, "prah XP neroste")
        if r["masteredNodes"] < last_nodes:
            bad(w, "pocet zvladnutych uzlu klesa")
        last_xp, last_nodes = r["xp"], r["masteredNodes"]
    phase_a = [r for r in cfg["ranks"] if r["phase"] == "A"]
    if not phase_a or max(r["n"] for r in phase_a) != 3:
        bad("ranks", "faze A musi koncit hodnosti 3")

    # ---- P7 / P8 / P9 ------------------------------------------------------
    for sub, must in (("practice", ['id="paFallback"', "<details>", 'id="pa-data"',
                                    "Answer:", 'id="paTiles"']),
                      ("progress", ['id="paMap"', 'class="pa-mn"', 'id="paCrit"',
                                    'id="pa-data"', "pa-open"])):
        fp = os.path.join(HERE, "academy", sub, "index.html")
        if not os.path.exists(fp):
            bad("page %s" % sub, "stranka neexistuje -- spust build_practice.py")
            continue
        html = open(fp, encoding="utf-8").read()
        for token in must:
            if token not in html:
                bad("page %s" % sub, "chybi %r (parita bez JS nebo zapecena data)" % token)
        m = re.search(r'<script type="application/json" id="pa-data">(.*?)</script>', html, re.S)
        if not m:
            bad("page %s" % sub, "payload pa-data nenalezen")
        else:
            try:
                json.loads(m.group(1).replace("<\\/", "</"))
            except Exception as exc:
                bad("page %s" % sub, "payload se neda naparsovat: %s" % exc)
        if re.search(r'noscript', html, re.I) and "Answer:" not in html and sub == "practice":
            bad("page %s" % sub, "fallback je jen vyzva k zapnuti JS")

    open_edges = set()
    for ol in pw.get("open_loops") or []:
        for eid in ol.get("interactions") or []:
            open_edges.add(eid)
    for it in bank["items"]:
        if it["id"].startswith("sp:") and it["id"][3:] in open_edges:
            bad("item %s" % it["id"], "polozka tvrdi neco o hrane, kterou model vede jako otevrenou")

    # ---- vysledek ----------------------------------------------------------
    c = bank["counts"]
    print("Practice Arena: %d polozek, %d wire puzzlu, %d uzlu (core %d, route %d) z %d"
          % (c["items"], c["wire"], len(nodes), c["core"], c["route"], c["atlas"]))
    if PROBLEMS:
        print("\nNALEZY (%d):" % len(PROBLEMS))
        for p in PROBLEMS:
            print("  ! " + p)
        return 1
    print("Cisto -- vsech devet pravidel prosslo.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
