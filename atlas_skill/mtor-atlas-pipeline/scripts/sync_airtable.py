#!/usr/bin/env python3
"""
sync_airtable.py  --  regenerate the ATLAS_STUDIES and ATLAS_GAPS constants
inside index.html straight from the Airtable base. This is the "static bake"
(Tier 0) sync: no secret ever ships in the page.

Usage:
    export AIRTABLE_TOKEN=patXXXXXXXXXXXXXX      # a READ-only personal access token, scoped to this base
    python3 sync_airtable.py                     # rewrites index.html in place

Only needs the Python standard library (urllib) - no pip installs.
"""
import os, json, re, sys, urllib.request, urllib.parse, time

BASE   = "appt2U6ObDHUcRlrj"                 # mTOR Studies base
TOKEN  = os.environ.get("AIRTABLE_TOKEN")
HTML   = "index.html"

def api(table, params=None):
    """Fetch all records from a table (handles pagination)."""
    out, offset = [], None
    while True:
        q = dict(params or {})
        if offset: q["offset"] = offset
        url = f"https://api.airtable.com/v0/{BASE}/{urllib.parse.quote(table)}"
        if q: url += "?" + urllib.parse.urlencode(q, doseq=True)
        req = urllib.request.Request(url, headers={"Authorization": f"Bearer {TOKEN}"})
        data = json.load(urllib.request.urlopen(req))
        out += data.get("records", [])
        offset = data.get("offset")
        if not offset: break
        time.sleep(0.25)                      # stay under Airtable's 5 req/s limit
    return out

def studies_js():
    rows = api("Studies")
    def g(f, k, d=""):
        v = f.get(k, d)
        return v if v is not None else d
    arr = []
    for r in rows:
        f = r["fields"]
        arr.append({
            "id": r["id"],
            "sid": g(f, "Study_ID"),
            "title": g(f, "Title"),
            "authors": g(f, "Authors"),
            "year": g(f, "Year", None),
            "journal": g(f, "Journal"),
            "category": g(f, "Category"),
            "model": g(f, "Model"),
            "finding": g(f, "Key_Finding"),
            "tier": g(f, "Evidence_Tier"),
            "pyramid": g(f, "Pyramid_Level"),
            "peer": g(f, "Peer_Reviewed"),
            "doi": g(f, "DOI"),
            "abstract": g(f, "Abstract (PubMed)"),
            # the AI_ extraction fields (Phase 2) - available for future UI use:
            "ai_intervention": g(f, "AI_Intervention"),
            "ai_target": g(f, "AI_Target"),
            "ai_species": g(f, "AI_Species"),
            "ai_effect": g(f, "AI_Effect"),
        })
    return "const ATLAS_STUDIES = " + json.dumps(arr, ensure_ascii=False) + ";"

def gaps_js():
    try:
        rows = api("Knowledge_Gaps")
    except Exception as e:
        print("  (Knowledge_Gaps table not found, leaving ATLAS_GAPS untouched)", e)
        return None
    arr = []
    for r in sorted(rows, key=lambda r: r["fields"].get("Gap_ID", "")):
        f = r["fields"]
        codes = re.findall(r"[A-Z]{2,}[0-9]{4}|NCT[0-9]+", f.get("Supporting_Studies", "") or "")
        arr.append({
            "id": f.get("Gap_ID", ""),
            "type": f.get("Type", ""),
            "title": f.get("Title", ""),
            "basis": f.get("Evidence_Basis", ""),
            "hyp": f.get("Hypothesis", ""),
            "exp": f.get("Proposed_Experiment", ""),
            "studies": codes,
            "conf": f.get("Confidence", 0),
        })
    return "const ATLAS_GAPS = " + json.dumps(arr, ensure_ascii=False) + ";"

def main():
    if not TOKEN:
        sys.exit("Set AIRTABLE_TOKEN (a read-only personal access token scoped to this base).")
    h = open(HTML, encoding="utf-8").read()

    sjs = studies_js()
    n1 = re.subn(r"const ATLAS_STUDIES = \[.*?\];", sjs, h, count=1, flags=re.S)
    h, c1 = n1
    print(f"ATLAS_STUDIES: {'updated' if c1 else 'NOT FOUND'} ({sjs.count(chr(123))} records)")

    gjs = gaps_js()
    if gjs:
        h, c2 = re.subn(r"const ATLAS_GAPS = \[.*?\n\];", gjs, h, count=1, flags=re.S)
        # also handle the single-line form produced by a previous run of this script
        if not c2:
            h, c2 = re.subn(r"const ATLAS_GAPS = \[.*?\];", gjs, h, count=1, flags=re.S)
        print(f"ATLAS_GAPS: {'updated' if c2 else 'NOT FOUND'}")

    with open(HTML, "w", encoding="utf-8") as f:
        f.write(h); f.flush(); os.fsync(f.fileno())
    print("index.html rewritten. Commit & deploy to publish.")

if __name__ == "__main__":
    main()
