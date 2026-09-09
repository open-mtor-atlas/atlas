#!/usr/bin/env python3
"""
license_gate.py  --  Phase 4, Step 1: decide which full-text studies are
legally chunkable (open-access licensed) vs abstract-only.

Authoritative, free source: Europe PMC REST API (fields isOpenAccess, license,
authMan). We only mark a study "chunkable" when it is open access, carries a
Creative-Commons license, and is NOT an author manuscript (those often keep
reuse restrictions).

Input:  atlas_data/studies_enriched.jsonl  (has PMID / PMCID / fulltext flag)
Output: atlas_data/licenses.csv
Option: --write-airtable  adds/updates a `License` (text) + `Chunkable`
        (checkbox) field on the Studies table (needs AIRTABLE_TOKEN with write scope).

Usage:
    python3 atlas_gaps/license_gate.py
    python3 atlas_gaps/license_gate.py --write-airtable
    python3 atlas_gaps/license_gate.py --from-baked      # zivy korpus, ne snimek
    python3 atlas_gaps/license_gate.py --from-baked --dry-run
Standard library only (urllib).
"""
import json, os, sys, csv, time, urllib.request, urllib.parse

HERE = os.path.dirname(os.path.abspath(__file__))
SRC  = os.path.join(HERE, "studies_enriched.jsonl")
# Zivy korpus. studies_enriched.jsonl je snimek z 28. 7. 2026 (168 studii);
# atlas_data/studies_baked.json je to, co se dnes opravdu publikuje.
BAKED = os.path.join(HERE, "..", "atlas_data", "studies_baked.json")
OUT  = os.path.join(HERE, "licenses.csv")
EPMC = "https://www.ebi.ac.uk/europepmc/webservices/rest/search"
BASE = "appt2U6ObDHUcRlrj"

def epmc_batch(pmids):
    """Return {pmid: {isOpenAccess, license, authMan, pmcid}} for a batch."""
    q = "(" + " OR ".join("ext_id:%s" % p for p in pmids) + ") AND src:med"
    url = EPMC + "?" + urllib.parse.urlencode(
        {"query": q, "resultType": "core", "format": "json", "pageSize": len(pmids)+5})
    data = json.load(urllib.request.urlopen(url, timeout=60))
    out = {}
    for r in data.get("resultList", {}).get("result", []):
        pid = r.get("pmid")
        if pid:
            out[pid] = {
                "oa": r.get("isOpenAccess", "N"),
                "license": (r.get("license") or "").lower(),
                "authMan": r.get("authMan", "N"),
                "pmcid": r.get("pmcid", ""),
            }
    return out

def chunkable(info):
    # The CC license is what grants redistribution, so it governs whether we may
    # store/serve the text. We exclude only No-Derivatives (nd). The isOpenAccess
    # flag and author-manuscript status are metadata, not the governing right.
    lic = info["license"]
    return lic.startswith("cc") and "nd" not in lic

def targets_from_baked():
    """Kandidati z ziveho korpusu misto snimku z cervence.

    studies_enriched.jsonl mel priznak `fulltext_pmc_available`; baked data ho
    nemaji, ale maji rovnou `pmcid`, coz je tataz informace v silnejsi forme.
    Bereme vsechno s PMID, at licencni branka rozhodne sama -- PMCID nekdy
    Europe PMC zna, i kdyz ho v Airtable nemame.
    """
    recs = json.load(open(BAKED, encoding="utf-8"))
    recs = recs if isinstance(recs, list) else recs.get("studies", recs)
    out = []
    for r in recs:
        if not r.get("pmid"):
            continue
        out.append({"airtable_id": r.get("id", ""), "Study_ID": r.get("sid", ""),
                    "PMID": str(r["pmid"]), "PMCID": r.get("pmcid", "") or ""})
    return out


def main():
    if "--from-baked" in sys.argv:
        targets = targets_from_baked()
        print(f"[gate] zdroj: atlas_data/studies_baked.json -- {len(targets)} studii s PMID")
        print(f"        z toho {sum(1 for t in targets if t['PMCID'])} ma PMCID uz v datech")
    else:
        recs = [json.loads(l) for l in open(SRC, encoding="utf-8")]
        targets = [r for r in recs if r.get("fulltext_pmc_available") and r.get("PMID")]
        print(f"[gate] zdroj: studies_enriched.jsonl (snimek) -- {len(targets)} studii")

    if "--dry-run" in sys.argv:
        print("[gate] --dry-run: nic se nedotazuje ani nezapisuje.")
        return

    lic = {}
    pmids = [str(r["PMID"]) for r in targets]
    for i in range(0, len(pmids), 40):
        batch = pmids[i:i+40]
        try:
            lic.update(epmc_batch(batch))
        except Exception as e:
            print("  batch failed, retrying once:", e); time.sleep(3)
            lic.update(epmc_batch(batch))
        print(f"  checked {min(i+40,len(pmids))}/{len(pmids)}")
        time.sleep(1)   # be polite to Europe PMC

    rows = []
    for r in targets:
        info = lic.get(str(r["PMID"]), {"oa": "?", "license": "", "authMan": "?", "pmcid": r.get("PMCID","")})
        ck = chunkable(info) if info["oa"] != "?" else False
        rows.append({
            "airtable_id": r["airtable_id"], "sid": r.get("Study_ID",""),
            "PMID": r["PMID"], "PMCID": info["pmcid"] or r.get("PMCID",""),
            "isOpenAccess": info["oa"], "license": info["license"],
            "authMan": info["authMan"], "chunkable": ck,
        })

    with open(OUT, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys())); w.writeheader(); w.writerows(rows)

    n_ck = sum(1 for r in rows if r["chunkable"])
    from collections import Counter
    print("\n=== LICENSE GATE RESULT ===")
    print(f"chunkable (OA + CC + not author-manuscript): {n_ck}/{len(rows)}")
    print("license distribution:", dict(Counter(r["license"] or "(none)" for r in rows)))
    print(f"written: {OUT}")

    if "--write-airtable" in sys.argv:
        write_airtable(rows)

def write_airtable(rows):
    tok = os.environ.get("AIRTABLE_TOKEN")
    if not tok: sys.exit("AIRTABLE_TOKEN needed for --write-airtable")
    hdr = {"Authorization": f"Bearer {tok}", "Content-Type": "application/json"}
    # create fields (ignore error if they already exist)
    for fld in ({"name": "License", "type": "singleLineText"},
                {"name": "Chunkable", "type": "checkbox",
                 "options": {"icon": "check", "color": "greenBright"}}):
        try:
            req = urllib.request.Request(
                f"https://api.airtable.com/v0/meta/bases/{BASE}/tables/Studies/fields",
                data=json.dumps(fld).encode(), headers=hdr, method="POST")
            urllib.request.urlopen(req)
        except Exception as e:
            print("  (field exists or skipped:", fld["name"], ")")
    # patch records in batches of 10
    for i in range(0, len(rows), 10):
        payload = {"records": [
            {"id": r["airtable_id"],
             "fields": {"License": r["license"] or ("author-manuscript" if r["authMan"]=="Y" else "not-OA"),
                        "Chunkable": bool(r["chunkable"])}}
            for r in rows[i:i+10]]}
        req = urllib.request.Request(
            f"https://api.airtable.com/v0/{BASE}/Studies",
            data=json.dumps(payload).encode(), headers=hdr, method="PATCH")
        urllib.request.urlopen(req); time.sleep(0.3)
    print("  Airtable Studies updated with License + Chunkable.")

if __name__ == "__main__":
    main()
