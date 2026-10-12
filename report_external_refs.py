# -*- coding: utf-8 -*-
"""Prace citovane v prose Atlasu, ktere nejsou studie korpusu.

Doplnkovy pruchod auditem 2026-10-10, bod 7. Nalez: v prose Atlasu je
61 PMID, 47 z nich neni studie korpusu, a 6 z tech 47 sedi uvnitr karet
hran nebo entit -- tedy uvnitr tvrzeni o draze.

Atlas je v tom cestny, vetsinu oznacuje "outside this corpus". Problem je
jinde: PMID napsany do prozy nema evidence kod, nikdy nevstoupi do
supporting/conflicting a je neviditelny pro API, pro MCP server i pro
Contradiction Engine. Devet nalezu faze 8 auditu je tentyz defekt --
prace, kterou pole `boundary` nebo `changed_since_written` uz jmenuje,
nikdy nepromovana do korpusu.

`external_refs` v API (Atlas_v2/src/lib/api.ts) je citaci zviditelnuje.
Tenhle skript je druha polovina: frontu k zarazeni. Spoustet po
sync_airtable.py; nic nemeni, jen vypisuje.

Pouziti:
    python report_external_refs.py           # lidsky citelny vypis
    python report_external_refs.py --csv     # CSV na stdout
    python report_external_refs.py --strict  # exit 1, kdyz je neco v karte hrany
"""
import csv
import io
import json
import os
import re
import sys
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "atlas_data")
PMID_RE = re.compile(r"\bPMID[:\s]*([0-9]{7,9})\b", re.I)

# Pole, ktera cte ctenar jako tvrzeni o draze. Citace, ktera sedi tady a
# neni v korpusu, je prioritni -- nese ji claim, ne komentar k otazce.
CLAIM_SURFACES = ("relation", "entity", "node")


def load(name):
    with io.open(os.path.join(DATA, name), encoding="utf-8") as fh:
        return json.load(fh)


def scan():
    studies = load("studies_baked.json")
    corpus = {str(s.get("pmid") or "").strip() for s in studies if s.get("pmid")}
    by_sid = {s["sid"]: s for s in studies}

    hits = defaultdict(set)   # pmid -> {"surface:id.field", ...}

    def take(text, where):
        for m in PMID_RE.finditer(str(text or "")):
            hits[m.group(1)].add(where)

    model_path = os.path.join(HERE, "pathway", "model.json")
    with io.open(model_path, encoding="utf-8") as fh:
        model = json.load(fh)
    for i in model.get("interactions", []):
        for f in ("mechanism", "mechanism_beginner", "boundary",
                  "context_note", "note", "teaching_note"):
            take(i.get(f), "relation:%s.%s" % (i["id"], f))
    for n in model.get("nodes", []):
        for f, v in (n.get("explain") or {}).items():
            take(v, "node:%s.%s" % (n["id"], f))
        take(n.get("note"), "node:%s.note" % n["id"])

    for e in load("entities_baked.json"):
        for f in ("desc", "desc_beginner"):
            take(e.get(f), "entity:%s.%s" % (e["name"], f))

    for g in load("gaps_baked.json"):
        gid = g.get("slug") or g.get("id")
        for f, v in g.items():
            if isinstance(v, str):
                take(v, "question:%s.%s" % (gid, f))

    rows = []
    for pmid, wheres in hits.items():
        if pmid in corpus:
            continue
        surfaces = sorted(wheres)
        in_claim = any(w.split(":")[0] in CLAIM_SURFACES for w in surfaces)
        rows.append({
            "pmid": pmid,
            "in_claim_card": "yes" if in_claim else "no",
            "cited_in": "; ".join(surfaces),
            "url": "https://pubmed.ncbi.nlm.nih.gov/%s/" % pmid,
        })
    rows.sort(key=lambda r: (r["in_claim_card"] != "yes", r["pmid"]))
    return rows, len(hits), len(corpus), by_sid


def main():
    rows, total, n_corpus, _ = scan()
    if "--csv" in sys.argv:
        w = csv.DictWriter(sys.stdout, fieldnames=["pmid", "in_claim_card", "cited_in", "url"])
        w.writeheader()
        for r in rows:
            w.writerow(r)
        return 0

    in_claim = [r for r in rows if r["in_claim_card"] == "yes"]
    print("PMID citovanych v prose Atlasu : %d" % total)
    print("z toho studie korpusu          : %d" % (total - len(rows)))
    print("mimo korpus                    : %d" % len(rows))
    print("z toho v karte hrany/entity    : %d  <-- prioritni" % len(in_claim))
    print()
    if in_claim:
        print("--- v karte hrany nebo entity (nese to claim, ne komentar) ---")
        for r in in_claim:
            print("  PMID %-10s %s" % (r["pmid"], r["cited_in"]))
        print()
    rest = [r for r in rows if r["in_claim_card"] != "yes"]
    if rest:
        print("--- na kartach otazek (%d) ---" % len(rest))
        for r in rest:
            print("  PMID %-10s %s" % (r["pmid"], r["cited_in"][:110]))
    print()
    print("Co s tim: bud praci zaradit do korpusu (pak dostane evidence kod a")
    print("muze vstoupit do supporting/conflicting), nebo nechat jako citaci")
    print("v prose. Druha volba je legitimni, ale vedome -- API ji vydava jako")
    print("external_refs s in_corpus: false, takze konzument vi, ze za ni")
    print("nestoji nic z aparatu Atlasu.")
    if "--strict" in sys.argv and in_claim:
        print()
        print("FAIL: %d citaci mimo korpus sedi v karte hrany nebo entity (--strict)." % len(in_claim))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
