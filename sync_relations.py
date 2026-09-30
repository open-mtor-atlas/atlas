#!/usr/bin/env python3
"""
sync_relations.py -- Airtable Relations -> atlas_data/relations_baked.json (+ ATLAS_EDGES)

OD 2026-09-30: AIRTABLE JE JEDINÝ ZDROJ PRAVDY PRO HRANY DRÁHY.
Dřívější verze byla záměrně konzervativní -- nikdy nepřidala ani neubrala
hranu, nikdy nevyprázdnila pole a poznámky nechávala ručně v index.html.
Právě tím ale vznikaly dvě pravdy: hrana přidaná v Airtable se do mapy
nedostala (MALONYLCOA-MTORC1), hrany přidané v kódu nebyly v Airtable
(21 z EXTRA_EDGES) a cíl tří hran se lišil. Teď to platí obráceně:

  * Co je v Relations se zaškrtnutým Published (a Status != Rejected),
    to je v mapě, v pathway/model.json a v API. Nic jiného.
  * Každé pole hrany (typ, kompartment, časová škála, jistoty, beginner text,
    teaching note, kontext, veřejná poznámka) se čte z Airtable. Tabulky
    CUR / TEACH / MECH_BEGINNER / CTX_EXTRA / CONFLICTING / EXTRA_EDGES
    v build_pathway_model.py byly zrušeny.
  * Prázdné pole v Airtable = prázdné pole na webu.

Pojistky, které zůstaly:
  * Dry run je default; zápis jen s --write.
  * Publikovaná hrana bez studie, bez povinného pole nebo s neznámým SID
    zápis zastaví (radši starý stav než rozbitá mapa).
  * Diff proti minulému relations_baked.json se vypíše před zápisem.
  * index.html se přepisuje atomicky s kontrolou konce souboru.

    set AIRTABLE_TOKEN=patXXXXXXXX
    py sync_relations.py            # dry run
    py sync_relations.py --write

Bez sítě (sandbox): map_relations_dump.py nad MCP dumpem dělá totéž.
"""
import json
import os
import sys
import urllib.parse
import urllib.request

import relations_bake as rb

WRITE = "--write" in sys.argv


def api(table, fields):
    token = os.environ.get("AIRTABLE_TOKEN")
    if not token:
        sys.exit('AIRTABLE_TOKEN is not set.  PowerShell: $env:AIRTABLE_TOKEN = "patXXXX"')
    out, offset = [], None
    while True:
        p = {"returnFieldsByFieldId": "true", "pageSize": "100", "fields[]": fields}
        if offset:
            p["offset"] = offset
        url = "https://api.airtable.com/v0/%s/%s?%s" % (rb.BASE, table, urllib.parse.urlencode(p, doseq=True))
        req = urllib.request.Request(url, headers={"Authorization": "Bearer " + token})
        with urllib.request.urlopen(req, timeout=60) as r:
            data = json.load(r)
        out.extend(data.get("records", []))
        offset = data.get("offset")
        if not offset:
            return out


def diff(old, new):
    o = {e["id"]: e for e in old}
    n = {e["id"]: e for e in new}
    for k in sorted(set(n) - set(o)):
        print("  + %s%s" % (k, "" if n[k]["published"] else "  (not published)"))
    for k in sorted(set(o) - set(n)):
        print("  - %s" % k)
    for k in sorted(set(o) & set(n)):
        ch = [f for f in n[k] if n[k].get(f) != o[k].get(f)]
        if ch:
            print("  ~ %s: %s" % (k, ", ".join(ch)))


def main():
    print("Reading Airtable...")
    studies = api(rb.T_STUDIES, [rb.F_STUDY_SID])
    ents = api(rb.T_ENTITIES, [rb.F_ENTITY_NAME])
    rels = api(rb.T_RELATIONS, list(rb.F.values()))
    sid = {r["id"]: (r["fields"].get(rb.F_STUDY_SID) or "").strip() for r in studies}
    ent = {r["id"]: (r["fields"].get(rb.F_ENTITY_NAME) or "").strip() for r in ents}
    print("  %d studies, %d entities, %d relations" % (len(studies), len(ents), len(rels)))

    edges, problems = rb.normalize(rels, sid, ent)
    for p in problems:
        print("  PROBLEM: " + p)
    if any("published" in p for p in problems):
        sys.exit("ABORT: a published edge is incomplete; fix it in Airtable, nothing was written.")

    old = rb.load(published_only=False) if os.path.exists(rb.BAKED) else []
    print("\nChanges against atlas_data/relations_baked.json:")
    diff(old, edges)

    if not WRITE:
        print("\nDry run. Re-run with --write to apply.")
        return
    rb.write(edges, "Airtable REST (sync_relations.py)")
    changed = rb.write_atlas_edges_into_index(os.path.join(rb.HERE, "index.html"))
    print("\nrelations_baked.json written (%d edges, %d published); ATLAS_EDGES %s."
          % (len(edges), sum(e["published"] for e in edges), "updated" if changed else "unchanged"))
    print("Now run: py build_pathway_model.py")


if __name__ == "__main__":
    main()
