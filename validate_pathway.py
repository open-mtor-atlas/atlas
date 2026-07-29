#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
validate_pathway.py — vědecká a strukturní branka pro pathway/model.json.

PROČ TOHLE EXISTUJE
-------------------
Model dráhy je teď jediný zdroj pravdy a edituje se jako kód. Aby to byla
výhoda a ne riziko, musí každou změnu chytit validátor DŘÍV, než se nasadí.
Externí recenze (F4) našla přesně ten druh chyby, kterou tenhle skript
zachytí strojově: pravidlo pro tier bylo definováno jinak, než bylo použito.

CO KONTROLUJE
  1. Slovníky   — každý type/effect/timescale/directness/confidence z povolené sady.
  2. Referenční integrita — každý source/target existuje jako uzel;
     každý uzel má kompartment, který existuje; každá trasa odkazuje na
     existující interakce.
  3. Citace     — každý SID existuje v korpusu; každá interakce má >=1 studii.
  4. Kalibrace  — tvrzení nesmí být silnější než evidence:
       * human_relevance = "established" vyžaduje aspoň jednu studii tier A/B
         NEBO species obsahující human.
       * mechanistic = "high" nesmí stát na jediné correlative studii.
       * consensus = "established" se nesmí kombinovat s mechanistic = "low".
       * directness = "direct" u typu signal-relay je protimluv.
       * clinical-outcome / association nesmí být directness = "direct".
  5. Pedagogika — každý uzel má text ve všech třech úrovních; žádný z nich
     není prázdný ani duplikát jiné úrovně.
  6. Neizolovanost — žádný uzel bez hrany (tichý zbytek po editaci).

POUŽITÍ
    py validate_pathway.py            # report
    py validate_pathway.py --strict   # nenulový exit při ERROR (pro deploy)
"""

import json
import os
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))

TYPES = {
    "binding", "recruitment", "localisation", "translocation", "scaffolding",
    "phosphorylation", "dephosphorylation", "gap-activity", "gef-activity",
    "complex-assembly", "complex-disassembly", "allosteric-activation",
    "allosteric-inhibition", "competitive-inhibition", "transcriptional",
    "transport", "signal-relay", "functional-consequence", "clinical-outcome",
    "association",
}
EFFECTS = {"activates", "inhibits", "required-for", "recruits", "binds", "context-dependent"}
TIMESCALES = {"seconds", "minutes", "hours", "days", "chronic", "constitutive"}
DIRECTNESS = {"direct", "indirect", "unresolved"}
MECH = {"high", "medium", "low"}
HUMREL = {"established", "plausible", "untested"}
CONSENSUS = {"established", "emerging", "contested"}


def main():
    strict = "--strict" in sys.argv
    m = json.load(open(os.path.join(ROOT, "pathway", "model.json"), encoding="utf-8"))
    studies = json.load(open(os.path.join(ROOT, "atlas_data", "studies_baked.json"), encoding="utf-8"))
    sid_tier = {s.get("sid"): (s.get("tier") or "").strip().upper()[:1] for s in studies}

    errors, warnings = [], []
    E = errors.append
    W = warnings.append

    comps = {c["id"] for c in m["compartments"]}
    nodes = {n["id"]: n for n in m["nodes"]}

    # --- 1+5+6 uzly -------------------------------------------------------
    used = set()
    for i in m["interactions"]:
        used.add(i["source"]); used.add(i["target"])
    for nid, n in nodes.items():
        if n["compartment"] not in comps:
            E("node %s: unknown compartment %r" % (nid, n["compartment"]))
        ex = n.get("explain", {})
        for lvl in ("beginner", "student", "research"):
            if not (ex.get(lvl) or "").strip():
                E("node %s: missing %s explanation" % (nid, lvl))
        if ex.get("beginner") == ex.get("student") or ex.get("student") == ex.get("research"):
            W("node %s: two learning levels are identical — the level switch does nothing here" % nid)
        if nid not in used:
            W("node %s: no interactions — orphan in the graph" % nid)

    # --- 2+3+4 interakce --------------------------------------------------
    seen = set()
    for i in m["interactions"]:
        iid = i["id"]
        if iid in seen:
            E("duplicate interaction id %s" % iid)
        seen.add(iid)
        if i["source"] not in nodes:
            E("%s: source %r is not a node" % (iid, i["source"]))
        if i["target"] not in nodes:
            E("%s: target %r is not a node" % (iid, i["target"]))
        if i["type"] not in TYPES:
            E("%s: unknown type %r" % (iid, i["type"]))
        if i["effect"] not in EFFECTS:
            E("%s: unknown effect %r" % (iid, i["effect"]))
        if i["timescale"] not in TIMESCALES:
            E("%s: unknown timescale %r" % (iid, i["timescale"]))
        if i["directness"] not in DIRECTNESS:
            E("%s: unknown directness %r" % (iid, i["directness"]))
        if i["compartment"] not in comps:
            E("%s: unknown compartment %r" % (iid, i["compartment"]))

        c = i.get("confidence", {})
        if c.get("mechanistic") not in MECH:
            E("%s: bad mechanistic confidence %r" % (iid, c.get("mechanistic")))
        if c.get("human_relevance") not in HUMREL:
            E("%s: bad human_relevance %r" % (iid, c.get("human_relevance")))
        if c.get("consensus") not in CONSENSUS:
            E("%s: bad consensus %r" % (iid, c.get("consensus")))

        ev = i.get("evidence", {})
        sup = ev.get("supporting") or []
        if not sup:
            E("%s: no supporting study — every interaction must be citable" % iid)
        for sid in sup + (ev.get("conflicting") or []):
            if sid not in sid_tier:
                E("%s: cites SID %s which is not in the corpus" % (iid, sid))
        tiers = {sid_tier.get(s, "?") for s in sup}
        sp = " ".join(i.get("species", [])).lower()

        # kalibrace
        if c.get("human_relevance") == "established" and not (tiers & {"A", "B"}) and "human" not in sp:
            E("%s: human_relevance=established but no tier A/B study and no human model "
              "(this is exactly finding F4 — do not let clinical language rest on cell-line data)" % iid)
        if c.get("mechanistic") == "high" and ev.get("kind") == "Correlative":
            E("%s: mechanistic=high on correlative evidence" % iid)
        if c.get("mechanistic") == "high" and len(sup) == 1 and tiers <= {"D"}:
            W("%s: mechanistic=high rests on a single tier-D study" % iid)
        if c.get("consensus") == "established" and c.get("mechanistic") == "low":
            E("%s: consensus=established with mechanistic=low is a contradiction" % iid)
        if i["type"] == "signal-relay" and i["directness"] == "direct":
            E("%s: signal-relay cannot be direct — a relay is by definition multi-step" % iid)
        if i["type"] in ("clinical-outcome", "association") and i["directness"] == "direct":
            E("%s: %s must not be marked direct" % (iid, i["type"]))
        if i["type"] == "association" and c.get("mechanistic") != "low":
            W("%s: association with mechanistic confidence above low" % iid)
        if not (i.get("mechanism") or "").strip():
            E("%s: empty mechanism text" % iid)
        if c.get("consensus") == "contested" and not (i.get("boundary") or "").strip():
            W("%s: contested but no boundary conditions stated" % iid)

    # --- trasy ------------------------------------------------------------
    for r in m.get("routes", []):
        for ref in r.get("interactions", []) + r.get("spine", []):
            if ref not in seen:
                E("route %s: references unknown interaction %s" % (r["id"], ref))
        for st in r.get("steps", []):
            if st.get("interaction") not in seen:
                E("route %s: step references unknown interaction %s" % (r["id"], st.get("interaction")))
            for k in ("what", "why", "changed", "consequence", "certainty", "matters"):
                if not (st.get(k) or "").strip():
                    E("route %s step %s: missing %s" % (r["id"], st.get("interaction"), k))

    print("pathway/model.json — %d nodes, %d interactions, %d routes"
          % (len(m["nodes"]), len(m["interactions"]), len(m.get("routes", []))))
    print("ERRORS   %d" % len(errors))
    for e in errors:
        print("  ✗", e)
    print("WARNINGS %d" % len(warnings))
    for w in warnings:
        print("  !", w)
    if errors and strict:
        print("\nABORT: model is not deployable.")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
