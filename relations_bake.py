#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
relations_bake.py -- JEDINÉ místo, kde se tvar hrany dráhy skládá z Airtable.

PROČ TOHLE EXISTUJE (2026-09-30)
--------------------------------
Hrana dráhy dřív žila na čtyřech místech najednou:

  1. Airtable Relations          (znak, mechanismus, studie, druh důkazu...)
  2. index.html ATLAS_EDGES      (ručně držená kopie; sync_relations.py do ní
                                  jen doplňoval, nikdy nepřidal ani neubral hranu)
  3. build_pathway_model.py      (tabulky CUR, TEACH, MECH_BEGINNER, CTX_EXTRA,
                                  CONFLICTING a 21 celých hran v EXTRA_EDGES)
  4. pathway/model.json          (výsledek 2 + 3)

Každá oprava tedy musela jít na správné místo a rozcházelo se to: hrana
MALONYLCOA-MTORC1 přidaná do Airtable 28. 9. se do mapy nedostala nikdy,
21 hran z EXTRA_EDGES v Airtable vůbec nebylo a tři hrany mířily v Airtable
na jiný cílový uzel než na webu.

Od 30. 9. 2026 je Airtable Relations JEDINÝ zdroj pravdy pro všechno, co
o hraně tvrdíme. Tenhle modul převádí záznamy Relations na normalizovaný
seznam hran a zapisuje ho do atlas_data/relations_baked.json. Všechno ostatní
(build_pathway_model.py, build_evidence_audit.py, build_timing_page.py,
ATLAS_EDGES v index.html) čte už jen tenhle soubor.

Dvě vstupní cesty, jeden převod:
  * REST (sync_relations.py, Petrův stroj s AIRTABLE_TOKEN)
  * MCP dump (map_relations_dump.py, sandbox bez sítě na api.airtable.com)

Obě dávají TÝŽ výsledek; liší se jen tvar buněk (REST vrací u linků holá
record ID a u selectů řetězec, MCP vrací {id, name}).

Co se tu NEVYMÝŠLÍ: evidenční tier hrany se počítá z citovaných studií,
odvozené boundary tagy z Time_Dependence / počtu studií / Status. Ruční
hodnoty těchhle věcí v Airtable se ignorují.
"""
import json
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
BAKED = os.path.join(HERE, "atlas_data", "relations_baked.json")
STUDIES = os.path.join(HERE, "atlas_data", "studies_baked.json")

BASE = "appt2U6ObDHUcRlrj"
T_RELATIONS = "tblT4hOU9HrTFe4Ik"
T_STUDIES = "tblbQIQtzn2vWaV6d"
T_ENTITIES = "tblhFpLHVy1odzcbv"

# Pole se adresují ID, ne jménem: přejmenování sloupce v Airtable nesmí
# potichu rozbít převod.
F = {
    "edge_id":   "fldXL4UK8ARBfNhEo",
    "source":    "fldkpAb1jcKLba0uR",
    "target":    "fldz1ab8fJDc2MAqx",
    "sign":      "fldI3qyVK5idZkwOw",
    "mech":      "fldqkYGZVr7N8c9sj",
    "studies":   "fldhbXPw6k6BhARQD",
    "conflicting": "fld7lBBqegd5dSjA3",
    "kind":      "fldsJH6jZRrj31gqp",   # druh důkazu (Structural / Direct biochemical...)
    "sp":        "fldxRTNv88mvmNsaE",
    "boundary":  "fldXVdsFzV2y9m4oT",   # Context_Note -> model.json boundary
    "status":    "fldEO9HwufC5nEXKo",
    "timedep":   "fldGpT7vpSzRvrAA8",
    "tags":      "fldLJyDmWlnAi6TV5",
    "published": "fldc38iwmHIARHyNo",
    "type":      "fldn84PstRXkiFFd1",
    "comp":      "fldXp0K80cZUAd3iE",
    "ts":        "fldheZYMXL95dMQIm",
    "directness": "fldsamUcrvYSvfkJw",  # povaha kroku: direct/indirect/unresolved
    "mc":        "fldJv6ezYPTqiE4r0",
    "hr":        "fldHpaCR20vNHrcCB",
    "cons":      "fld0QSllMvZcbRnPX",
    "mech_beginner": "fldqOPP7WUpCx3e0e",
    "teach":     "fldYlNHSb3xfZPxiu",
    "context":   "fld4TySqAVit0px4E",   # Context_Dependence -> model.json context_note
    "note":      "fld7EsGhaQpq2wsL3",   # Public_Note (Curator_Note je interní, sem nejde)
    "reviewed_by": "fldEtYjqttqLnyMOo",
    "reviewed_on": "fldPmuUDe0FMVqucp",
}
F_STUDY_SID = "fldnmqtOHZ0luHRiI"
F_ENTITY_NAME = "fldh3zgrLDjLi1szC"

# Uzel mapy se jmenuje podle entity, na kterou hrana v Airtable ukazuje.
# Výjimky jsou jen tam, kde uzel mapy záměrně nese jiný (širší nebo
# přesnější) popisek než záznam v Entities. Uzly samotné (kompartment,
# vysvětlení) kurátoruje build_pathway_model.py -> NODES.
ENTITY_TO_NODE = {
    "Caloric restriction": "Fasting / caloric restriction",
    "FoxO": "FOXO1/3",
}

REQUIRED_FOR_PUBLISHED = ["source", "target", "sign", "mech", "type", "comp", "ts",
                          "directness", "mc", "hr", "cons"]

# Odvozené boundary tagy (dřív sync_relations.py, Bod 7.2).
DERIVED_TAGS = {"time-dependent", "reversible-on-withdrawal", "single-study", "direction-contested"}
TIMEDEP_TAG = {
    "Chronic only": "time-dependent",
    "Acute only": "time-dependent",
    "Diverges with time": "time-dependent",
    "Reversible on withdrawal": "reversible-on-withdrawal",
}
TIER_ORDER = "ABCD"


def _name(v):
    """Select / link / text -> text. MCP dává {name}, REST holý řetězec."""
    if isinstance(v, dict):
        return (v.get("name") or "").strip()
    return (v or "").strip() if isinstance(v, str) else v


def _links(v, lookup):
    out = []
    for x in v or []:
        if isinstance(x, dict):
            out.append((x.get("name") or lookup.get(x.get("id"), "")).strip())
        else:
            out.append((lookup.get(x) or "").strip())
    return [x for x in out if x]


def _multi(v):
    return sorted({_name(x) for x in (v or []) if _name(x)})


def study_tiers():
    studies = json.load(open(STUDIES, encoding="utf-8"))
    return {s.get("sid"): (s.get("tier") or "").strip().upper()[:1] for s in studies}


def normalize(records, sid_by_rec=None, entity_by_rec=None):
    """Airtable záznamy (REST nebo MCP) -> (edges, problems).

    Hrana je v seznamu vždy, i nepublikovaná; `published` rozhoduje, co se
    dostane do mapy. Problémy se vrací, ne tiskne -- rozhoduje volající."""
    sid_by_rec = sid_by_rec or {}
    entity_by_rec = entity_by_rec or {}
    tiers_of = study_tiers()
    edges, problems, seen = [], [], set()
    for r in records:
        f = r.get("cellValuesByFieldId") or r.get("fields") or {}
        g = lambda k: f.get(F[k])
        eid = _name(g("edge_id"))
        if not eid:
            problems.append("record %s has no Edge_ID" % r.get("id"))
            continue
        if eid in seen:
            problems.append("duplicate Edge_ID %s" % eid)
            continue
        seen.add(eid)
        src = _links(g("source"), entity_by_rec)
        tgt = _links(g("target"), entity_by_rec)
        # Pořadí citací je kurátorské (klíčová práce první) -- drží se pořadí
        # linků z Airtable, jen bez duplicit.
        st = list(dict.fromkeys(_links(g("studies"), sid_by_rec)))
        cf = list(dict.fromkeys(_links(g("conflicting"), sid_by_rec)))
        letters = sorted({tiers_of.get(s) for s in st if tiers_of.get(s) in TIER_ORDER})
        status = _name(g("status")) or "Proposed"
        timedep = _name(g("timedep")) or "Not tested"
        e = {
            "id": eid,
            "s": ENTITY_TO_NODE.get(src[0], src[0]) if len(src) == 1 else None,
            "t": ENTITY_TO_NODE.get(tgt[0], tgt[0]) if len(tgt) == 1 else None,
            "sign": _name(g("sign")),
            "mech": _name(g("mech")) or "",
            "st": st,
            "cf": cf,
            "dir": _name(g("kind")) or "",
            "sp": _name(g("sp")) or "",
            "ctx": _name(g("boundary")) or "",
            "status": status,
            "note": _name(g("note")) or "",
            "tier": letters[0] if letters else None,
            "tiers": letters,
            "timedep": timedep,
            "published": bool(g("published")) and status != "Rejected",
            "type": _name(g("type")),
            "comp": _name(g("comp")),
            "ts": _name(g("ts")),
            "directness": _name(g("directness")),
            "mc": _name(g("mc")),
            "hr": _name(g("hr")),
            "cons": _name(g("cons")),
            "mech_beginner": _name(g("mech_beginner")) or "",
            "teach": _name(g("teach")) or "",
            "context": _name(g("context")) or "",
            "reviewed_by": _name(g("reviewed_by")) or "",
            "reviewed_on": _name(g("reviewed_on")) or "",
        }
        derived = set()
        if TIMEDEP_TAG.get(timedep):
            derived.add(TIMEDEP_TAG[timedep])
        if len(st) == 1:
            derived.add("single-study")
        if status == "Contested":
            derived.add("direction-contested")
        e["tags"] = sorted((set(_multi(g("tags"))) - DERIVED_TAGS) | derived)

        if len(src) != 1 or len(tgt) != 1:
            problems.append("%s: needs exactly one Source and one Target (has %d/%d)"
                            % (eid, len(src), len(tgt)))
        if e["published"]:
            missing = [k for k in REQUIRED_FOR_PUBLISHED if not e.get(k if k not in ("source", "target") else k[0])]
            if missing:
                problems.append("%s: published but missing %s" % (eid, ", ".join(missing)))
            if not st:
                problems.append("%s: published with no Evidence_Studies (rule: no edge without a study)" % eid)
            unknown = [s for s in st + cf if s not in tiers_of]
            if unknown:
                problems.append("%s: cites SID(s) not in studies_baked.json: %s" % (eid, unknown))
        edges.append(e)
    return edges, problems


def order_like_previous(edges):
    """Pořadí hran ovlivňuje výpočet layoutu. Drží se proto pořadí z minulé
    verze relations_baked.json; nové hrany se přidávají na konec podle ID."""
    prev = []
    model = os.path.join(HERE, "pathway", "model.json")
    if os.path.exists(BAKED):
        prev = [e["id"] for e in json.load(open(BAKED, encoding="utf-8")).get("edges", [])]
    elif os.path.exists(model):
        # První bake (2026-09-30): pořadí převezmi z dosavadního modelu.
        prev = [i["id"] for i in json.load(open(model, encoding="utf-8")).get("interactions", [])]
    pos = {k: i for i, k in enumerate(prev)}
    return sorted(edges, key=lambda e: (pos.get(e["id"], len(pos)), e["id"]))


def write(edges, source):
    import datetime
    doc = {
        "_about": "Pathway edges baked from Airtable Relations (single source of truth since "
                  "2026-09-30). Generated by relations_bake.py via %s. Do not edit by hand." % source,
        "generated": datetime.datetime.utcnow().replace(microsecond=0).isoformat() + "Z",
        "edges": order_like_previous(edges),
    }
    tmp = BAKED + ".tmp"
    with open(tmp, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(doc, fh, ensure_ascii=False, indent=1)
        fh.write("\n")
    json.load(open(tmp, encoding="utf-8"))          # read-back
    os.replace(tmp, BAKED)
    return doc


def load(published_only=True):
    """Hrany pro všechny čtenáře. Default: jen publikované."""
    if not os.path.exists(BAKED):
        raise SystemExit("atlas_data/relations_baked.json chybí. Spusť: py sync_relations.py --write")
    edges = json.load(open(BAKED, encoding="utf-8"))["edges"]
    return [e for e in edges if e.get("published")] if published_only else edges


ATLAS_EDGE_KEYS = ["id", "s", "t", "sign", "mech", "st", "dir", "sp", "ctx", "status",
                   "note", "tier", "tiers", "timedep", "tags", "cf"]


def atlas_edges():
    """Tvar ATLAS_EDGES (V1 SPA, build_evidence_audit, build_timing_page).
    Odvozený, publikované hrany; prázdné cf se vynechá jako dřív."""
    out = []
    for e in load():
        row = {k: e.get(k) for k in ATLAS_EDGE_KEYS}
        if not row["cf"]:
            row.pop("cf")
        if not row["tags"]:
            row.pop("tags")
        out.append(row)
    return out


def write_atlas_edges_into_index(html_path):
    """Přepíše const ATLAS_EDGES v index.html celým odvozeným polem.
    Atomicky, s kontrolou konce souboru -- index.html je velký a most na
    OneDrive už zápisy uřízl (viz build-deploy-pipeline pasti)."""
    src = open(html_path, encoding="utf-8", newline="").read()
    head = "const ATLAS_EDGES = "
    i = src.find(head + "[")
    if i < 0:
        raise SystemExit("ABORT: const ATLAS_EDGES not found in index.html")
    lo = i + len(head)
    _, used = json.JSONDecoder().raw_decode(src[lo:])
    hi = lo + used
    new = json.dumps(atlas_edges(), ensure_ascii=False, separators=(",", ":"))
    out = src[:lo] + new + src[hi:]
    if not out.rstrip().endswith("</html>"):
        raise SystemExit("ABORT: output does not end in </html>; index.html untouched.")
    tmp = html_path + ".tmp"
    with open(tmp, "w", encoding="utf-8", newline="") as fh:
        fh.write(out)
        fh.flush()
        os.fsync(fh.fileno())
    if open(tmp, encoding="utf-8", newline="").read() != out:
        raise SystemExit("ABORT: read-back mismatch; index.html untouched.")
    os.replace(tmp, html_path)
    return src[lo:hi] != new
