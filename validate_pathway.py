#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
validate_pathway.py – vědecká a strukturní branka pro pathway/model.json.

PROČ TOHLE EXISTUJE
-------------------
Model dráhy je teď jediný zdroj pravdy a edituje se jako kód. Aby to byla
výhoda a ne riziko, musí každou změnu chytit validátor DŘÍV, než se nasadí.
Externí recenze (F4) našla přesně ten druh chyby, kterou tenhle skript
zachytí strojově: pravidlo pro tier bylo definováno jinak, než bylo použito.

CO KONTROLUJE
  1. Slovníky   – každý type/effect/timescale/directness/confidence z povolené sady.
  2. Referenční integrita – každý source/target existuje jako uzel;
     každý uzel má kompartment, který existuje; každá trasa odkazuje na
     existující interakce.
  3. Citace     – každý SID existuje v korpusu; každá interakce má >=1 studii.
  4. Kalibrace  – tvrzení nesmí být silnější než evidence:
       * human_relevance = "established" vyžaduje aspoň jednu studii s ULOŽENÝM
         tierem A/B (zobrazuje se jako S = přehled lidských dat, H = lidská
         studie) NEBO species s položkou popisující člověka samotného
         (in_human_species: "human cells" / linie / organoidy NESTAČÍ, A11).
       * mechanistic = "high" nesmí stát na jediné correlative studii.
       * consensus = "established" se nesmí kombinovat s mechanistic = "low".
       * directness = "direct" u typu signal-relay je protimluv.
       * clinical-outcome / association nesmí být directness = "direct".
  5. Pedagogika – každý uzel má text ve všech třech úrovních; žádný z nich
     není prázdný ani duplikát jiné úrovně.
  6. Neizolovanost – žádný uzel bez hrany (tichý zbytek po editaci).

POUŽITÍ
    py validate_pathway.py            # report
    py validate_pathway.py --strict   # nenulový exit při ERROR (pro deploy)
"""

import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))

TYPES = {
    "binding", "recruitment", "localisation", "translocation", "scaffolding",
    "phosphorylation", "dephosphorylation", "gap-activity", "gef-activity",
    "complex-assembly", "complex-disassembly", "allosteric-activation",
    "allosteric-inhibition", "competitive-inhibition", "transcriptional",
    "transport", "signal-relay", "functional-consequence", "clinical-outcome",
    "association",
    # Nález recenze č. 6: "stabilizuje" a "degraduje" jsou jiná biologická
    # tvrzení než "fosforyluje" – fosforylace je tady prostředek, ne děj.
    "stabilization", "degradation",
}
EFFECTS = {"activates", "inhibits", "required-for", "recruits", "binds", "context-dependent",
           # 2026-09-29 audit: a tested-and-null relationship must be drawable, otherwise
           # the map reads more positive than the corpus (Airtable Relations.Sign already has it).
           "no-effect"}
TIMESCALES = {"seconds", "minutes", "hours", "days", "chronic", "constitutive"}
DIRECTNESS = {"direct", "indirect", "unresolved"}
MECH = {"high", "medium", "low"}
HUMREL = {"established", "plausible", "untested"}
CONSENSUS = {"established", "emerging", "contested"}


# A11 (audit 2026-10-07): "human" v poli species nestačí. Lidské buňky,
# linie, organoidy nebo xenografty jsou lidský MATERIÁL, ne pozorování
# v člověku. Za lidský model se počítá jen položka species, která obsahuje
# "human"/"patient"/"participant" a NEOBSAHUJE kvalifikátor buněk/materiálu.
# Smíšené práce ("human; mouse") projdou, protože aspoň jedna položka je
# in-human. Viz test v _selftest_in_human() níže.
_IN_VITRO_QUALIFIERS = ("cell", "line", "organoid", "in vitro", "ipsc",
                        "xenograft", "tissue explant", "lysate", "recombinant",
                        "derived", "extract", "homogenate")
# N05 (audit 2026-10-10): jmeno zivocisneho druhu v tokenu polozku
# diskvalifikuje. Bez toho vracelo in_human_species("adult mice") True,
# protoze "adult" stalo v _HUMAN_WORDS samo za sebe -- jedna falesna
# pozitivita (lidske bunky) byla vymenena za jinou (dospela mys).
_ANIMAL_WORDS = ("mouse", "mice", "murine", "rat", "zebrafish",
                 "fly", "flies", "drosophila", "worm", "elegans", "yeast",
                 "monkey", "macaque", "rhesus", "marmoset", "dog", "canine",
                 "beagle", "pig", "porcine", "rabbit", "hamster", "killifish",
                 "chicken", "bovine", "sheep", "naked mole")
_HUMAN_WORDS = ("human", "patient", "participant", "volunteer", "adult")

def in_human_species(sp):
    """True jen kdyz aspon jedna polozka species popisuje cloveka samotneho."""
    import re as _re
    for tok in _re.split(r"[;,/]| and ", (sp or "").lower()):
        tok = tok.strip()
        if not tok:
            continue
        if any(w in tok for w in _HUMAN_WORDS) \
           and not any(q in tok for q in _IN_VITRO_QUALIFIERS) \
           and not any(a in tok for a in _ANIMAL_WORDS):
            return True
    return False

def _selftest_in_human():
    # Lidsky material, ne pozorovani v clovece:
    assert not in_human_species("human cells")
    assert not in_human_species("human cell lines; mouse")
    assert not in_human_species("human iPSC-derived neurons")
    assert not in_human_species("human liver extract")        # N05
    assert not in_human_species("human-derived neurons")      # N05
    # Zvire s vekovym pridavkem -- regrese N05:
    assert not in_human_species("adult mice")                 # N05
    assert not in_human_species("adult zebrafish")            # N05
    assert not in_human_species("mouse")
    # Pozorovani v clovece:
    assert in_human_species("human")
    assert in_human_species("human; mouse")
    assert in_human_species("patients, mouse")
    assert in_human_species("older adults")
    # VEDOME ROZHODNUTI: vzorek odebrany zivemu pacientovi se POCITA za
    # lidskou evidenci -- ORE2006 (parove nadorove biopsie) a CAR2008
    # (biopsie 10 pacientu) maji lidskou experimentalni slozku, kterou
    # audit 2026-10-10 vyslovne nechce smazat kodem studie.
    assert in_human_species("patient tumour biopsies")
    # ZBYVAJICI DIRA, vedome nezalepena seznamem slov: nazev bunecneho typu
    # bez slova "cell" projde dal ("primary human myoblasts", "human
    # hepatocytes"). Spravna oprava je strukturovane pole species +
    # experimental_material + oznaceni in-human slozky, ne delsi seznam.
_selftest_in_human()


# R-OUTCOME (2026-10-10, pruchod vsech hran po auditu 2026-10-07):
# studie citovana jako PODPORA hrany na vystup (delka zivota, rust svalu,
# rust nadoru, patologie stari) musi ten vystup sama merit. Opakovana chyba:
# studie podpira sousedni krok nebo meri neco jineho -- IYE2012 (mechyr u RCC),
# DRU2009 (synteza bilkovin 1-2 h, ne rust svalu), UMX2004 (obezita, ne delka
# zivota), OKI2021. Test je jazykovy (nazev + nalez + extrahovany efekt +
# abstrakt studie): chyti studii, ktera vystup vubec nezminuje. Smer
# vysledku nepozna -- studie s opacnym vysledkem (SOL2014) patri do
# Conflicting_Studies a hlida ji kurator, ne tohle pravidlo.
OUTCOME_MEASURES = {
    "Longevity": r"lifespan|life span|life-span|longevity|survival|mortality",
    "Muscle growth": (r"hypertroph|muscle mass|muscle size|muscle growth|fib(?:er|re) size|"
                      r"cross-sectional|lean mass|atroph|myotube (?:size|diameter)|muscle weight"),
    "Tumor growth": r"tumou?r|cancer|carcinoma|leuka?emia|lymphoma|xenograft|oncogen|neoplas",
    "Age-related pathology": r"age-related|aging|ageing|patholog|degenerat",
}
# Vyjimka jen s pisemnym duvodem: {("EDGE-ID", "SID"): "proc studie vystup meri, i kdyz to text nerika"}.
OUTCOME_EXEMPT = {}

def _study_text(s):
    return " ".join(str(s.get(k) or "") for k in ("title", "finding", "ai_effect", "abstract"))

def main():
    strict = "--strict" in sys.argv
    m = json.load(open(os.path.join(ROOT, "pathway", "model.json"), encoding="utf-8"))
    studies = json.load(open(os.path.join(ROOT, "atlas_data", "studies_baked.json"), encoding="utf-8"))
    sid_tier = {s.get("sid"): (s.get("tier") or "").strip().upper()[:1] for s in studies}
    sid_rec = {s.get("sid"): s for s in studies}

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
            W("node %s: two learning levels are identical – the level switch does nothing here" % nid)
        if nid not in used:
            W("node %s: no interactions – orphan in the graph" % nid)

    # --- 2+3+4 interakce --------------------------------------------------
    seen = set()
    ix = {i["id"]: i for i in m["interactions"]}
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
            E("%s: no supporting study – every interaction must be citable" % iid)
        for sid in sup + (ev.get("conflicting") or []):
            if sid not in sid_tier:
                E("%s: cites SID %s which is not in the corpus" % (iid, sid))
        tiers = {sid_tier.get(s, "?") for s in sup}
        sp = "; ".join(i.get("species", [])).lower()

        # kalibrace
        if c.get("human_relevance") == "established" and not (tiers & {"A", "B"}) and not in_human_species(sp):
            E("%s: human_relevance=established but no human-level study (stored tier "
              "A/B, displayed S/H) and no human model "
              "(this is exactly finding F4 – do not let clinical language rest on cell-line data)" % iid)
        if c.get("mechanistic") == "high" and ev.get("kind") == "Correlative":
            E("%s: mechanistic=high on correlative evidence" % iid)
        if c.get("mechanistic") == "high" and len(sup) == 1 and tiers <= {"D"}:
            W("%s: mechanistic=high rests on a single molecular study "
              "(stored tier D, displayed M)" % iid)
        if c.get("consensus") == "established" and c.get("mechanistic") == "low":
            E("%s: consensus=established with mechanistic=low is a contradiction" % iid)
        if i["type"] == "signal-relay" and i["directness"] == "direct":
            E("%s: signal-relay cannot be direct – a relay is by definition multi-step" % iid)
        if i["type"] in ("clinical-outcome", "association") and i["directness"] == "direct":
            E("%s: %s must not be marked direct" % (iid, i["type"]))
        if i["type"] == "association" and c.get("mechanistic") != "low":
            W("%s: association with mechanistic confidence above low" % iid)
        if not (i.get("mechanism") or "").strip():
            E("%s: empty mechanism text" % iid)
        pat = OUTCOME_MEASURES.get(i.get("target"))
        if pat:
            for sid in sup:
                if (iid, sid) in OUTCOME_EXEMPT or sid not in sid_rec:
                    continue
                if not re.search(pat, _study_text(sid_rec[sid]), re.I):
                    E("%s: R-OUTCOME supporting study %s never mentions the outcome '%s' "
                      "(title/finding/effect/abstract) - it probably supports a neighbouring "
                      "step; move it there, or add a reasoned entry to OUTCOME_EXEMPT"
                      % (iid, sid, i.get("target")))
        if c.get("consensus") == "contested" and not (i.get("boundary") or "").strip():
            W("%s: contested but no boundary conditions stated" % iid)

    # --- uzly: odvozená síla důkazů (nález č. 2) --------------------------
    for nid, n in nodes.items():
        ev = n.get("evidence")
        if not ev:
            E("node %s: missing derived evidence block" % nid); continue
        if ev.get("studies_in_corpus", 0) == 0 and (ev.get("interactions_in", 0) + ev.get("interactions_out", 0)):
            W("node %s: has interactions but no cited studies behind any of them" % nid)
        if not (ev.get("caveat") or "").strip():
            E("node %s: evidence block must carry the corpus caveat – a bare study "
              "count reads as a literature count and would be misleading" % nid)
        for lvl in ("beginner", "student", "research"):
            pass
    # --- smyčky (nález č. 4) ----------------------------------------------
    loop_ids = set()
    for lp in m.get("loops", []):
        if lp["id"] in loop_ids:
            E("duplicate loop id %s" % lp["id"])
        loop_ids.add(lp["id"])
        if lp.get("sign") not in ("negative", "positive"):
            E("loop %s: bad sign %r" % (lp["id"], lp.get("sign")))
        if not (lp.get("sign_caveat") or "").strip():
            E("loop %s: sign must ship with its caveat – parity says direction, not strength" % lp["id"])
        for eid in lp["interactions"]:
            if eid not in seen:
                E("loop %s references unknown interaction %s" % (lp["id"], eid))
        # a cycle must actually close
        chain = [ix[e] for e in lp["interactions"] if e in ix]
        if len(chain) == len(lp["interactions"]):
            starts = [c["source"] for c in chain]
            if sorted(starts) != sorted(lp["nodes"]):
                W("loop %s: node list does not match the interaction sources" % lp["id"])
    for lp in m.get("open_loops", []):
        for k in ("name", "missing_step", "why"):
            if not (lp.get(k) or "").strip():
                E("open loop %r: missing %s" % (lp.get("name"), k))
        # Otevřená smyčka nesmí být ve skutečnosti uzavřená. Když se dokurátoruje
        # chybějící krok, deklarace se musí odebrat – jinak model tvrdí, že neumí
        # uzavřít smyčku, kterou už uzavřel. Přesně tohle se stalo u TFEB.
        words = {w.strip().lower() for w in re.split(r"[^A-Za-z0-9α-ω/\-]+", lp.get("name", "")) if len(w.strip()) > 3}
        for det in m.get("loops", []):
            dwords = {w.strip().lower() for nm in det["nodes"]
                      for w in re.split(r"[^A-Za-z0-9α-ω/\-]+", nm) if len(w.strip()) > 3}
            if words and len(words & dwords) >= max(2, len(words) - 1):
                E("open loop %r looks closed: detected loop %s covers %s. Remove the "
                  "declaration once the missing step is curated."
                  % (lp.get("name"), det["id"], sorted(words & dwords)))
    for lp in m.get("open_localisations", []):
        for k in ("name", "status", "why"):
            if not (lp.get(k) or "").strip():
                E("open localisation %r: missing %s" % (lp.get("name"), k))

    # --- trasy ------------------------------------------------------------
    # --- Researcher's Journey: společná hlavička každé trasy ---------------
    #
    # Reactome ukazuje, co víme. Guided Routes mají učit, JAK o mTOR myslet —
    # a to vyžaduje, aby každá trasa odpovídala na jednu otázku, ne aby
    # ukazovala jiný výřez. Bez branky se hlavička u sedmé trasy tiše vynechá
    # a nikdo si toho půl roku nevšimne.
    for r in m.get("routes", []):
        j = r.get("journey") or {}
        if not j:
            E("route %s: missing the Researcher's Journey header" % r["id"])
            continue
        # Titul musí být OTÁZKA, jinak je to zase jen území.
        if not (r.get("name") or "").strip().endswith("?"):
            E("route %s: title %r is not a question. A route answers one question; "
              "a title without a question mark is a territory."
              % (r["id"], r.get("name")))
        for k in ("question", "evidence", "unknowns"):
            if len((j.get(k) or "").strip()) < 40:
                E("route %s: journey.%s is missing or too short to be an answer" % (r["id"], k))
        b = j.get("breakthrough") or {}
        if not (b.get("why") or "").strip():
            E("route %s: breakthrough needs a WHY – naming a paper without saying what it "
              "broke open teaches nothing" % r["id"])
        # Legitimní ústupová cesta. Některé trasy jednu zlomovou práci nemají a
        # vyžadovat ji by tlačilo k nominaci práce, která si to nezaslouží.
        # "synthesis" je proto plnohodnotná varianta, ne chybějící hodnota.
        if b.get("sid"):
            if b["sid"] not in sid_tier:
                E("route %s: breakthrough cites %s, which is not in the corpus" % (r["id"], b["sid"]))
            if b.get("synthesis"):
                E("route %s: breakthrough declares both a single paper and a synthesis" % r["id"])
        elif b.get("synthesis"):
            syn = b["synthesis"]
            if len(syn) < 2:
                E("route %s: a synthesis needs at least two papers, otherwise name the one" % r["id"])
            for sid in syn:
                if sid not in sid_tier:
                    E("route %s: synthesis cites %s, which is not in the corpus" % (r["id"], sid))
        else:
            E("route %s: breakthrough must name a paper OR declare a synthesis. If no single "
              "study broke this open, say so explicitly – do not nominate one that did not."
              % r["id"])

    for r in m.get("routes", []):
        for ref in r.get("interactions", []) + r.get("spine", []):
            if ref not in seen:
                E("route %s: references unknown interaction %s" % (r["id"], ref))
        # Každá trasa musí být DOPSANÁ. Šest ze sedmi tras dlouho běželo na
        # automaticky složených krocích – byly poctivé, ale generické, a
        # recenzent by si toho všiml dřív než chybějícího tématu. Bez branky
        # se osmá trasa nasadí zas jako šablona.
        if len(r.get("steps", [])) != len(r.get("spine", [])):
            E("route %s: %d of %d steps authored. A route running on assembled "
              "template text is the failure mode this section keeps returning to."
              % (r["id"], len(r.get("steps", [])), len(r.get("spine", []))))
        for k, st in enumerate(r.get("steps", [])):
            if st.get("interaction") != (r.get("spine") or [None] * (k + 1))[k]:
                E("route %s step %d: authored step is out of order with the spine "
                  "(%r vs %r) – the narrative would not match the camera"
                  % (r["id"], k + 1, st.get("interaction"),
                     (r.get("spine") or [None] * (k + 1))[k]))
            if len((st.get("matters") or "")) < 80:
                E("route %s step %s: 'why scientists care' is under 80 characters. "
                  "That field is the payload; a stub there means the step teaches "
                  "adjacency instead of understanding."
                  % (r["id"], st.get("interaction")))
        for st in r.get("steps", []):
            if st.get("interaction") not in seen:
                E("route %s: step references unknown interaction %s" % (r["id"], st.get("interaction")))
            for k in ("what", "why", "changed", "consequence", "certainty", "matters"):
                if not (st.get(k) or "").strip():
                    E("route %s step %s: missing %s" % (r["id"], st.get("interaction"), k))

    print("pathway/model.json – %d nodes, %d interactions, %d routes"
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
