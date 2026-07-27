#!/usr/bin/env python3
"""
pull_ai_facts.py -- export the Phase-4 quantitative extraction from Airtable to a
local file so gap_finder / reports can use it. Pulls only studies with
AI_FullText_Extracted = true.

    export AIRTABLE_TOKEN=patXXXX      # read scope is enough
    python3 atlas_gaps/pull_ai_facts.py     # -> atlas_gaps/ai_facts.jsonl

Standard library only.
"""
import os, sys, json, urllib.request, urllib.parse

HERE = os.path.dirname(os.path.abspath(__file__))
OUT  = os.path.join(HERE, "ai_facts.jsonl")
BASE, TABLE = "appt2U6ObDHUcRlrj", "Studies"
TOK = os.environ.get("AIRTABLE_TOKEN")
FIELDS = ["Study_ID", "Evidence_Tier", "AI_Intervention", "AI_Target",
          "AI_Dose", "AI_SampleSize", "AI_EffectSize", "AI_Limitations"]

def main():
    if not TOK:
        sys.exit("Set AIRTABLE_TOKEN.")
    params = [("filterByFormula", "AI_FullText_Extracted=1"), ("pageSize", "100")]
    for f in FIELDS:
        params.append(("fields[]", f))
    rows, offset = [], None
    while True:
        p = list(params) + ([("offset", offset)] if offset else [])
        url = f"https://api.airtable.com/v0/{BASE}/{urllib.parse.quote(TABLE)}?" + urllib.parse.urlencode(p)
        req = urllib.request.Request(url, headers={"Authorization": f"Bearer {TOK}"})
        data = json.load(urllib.request.urlopen(req))
        rows += data.get("records", [])
        offset = data.get("offset")
        if not offset:
            break
    with open(OUT, "w", encoding="utf-8") as fh:
        for r in rows:
            f = r["fields"]
            fh.write(json.dumps({k: f.get(k, "") for k in FIELDS}, ensure_ascii=False) + "\n")
    print(f"wrote {len(rows)} deep-extracted studies -> {OUT}")

if __name__ == "__main__":
    main()
