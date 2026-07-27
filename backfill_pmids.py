#!/usr/bin/env python3
"""
backfill_pmids.py — Fáze 6, krok 1

Doplní ke každé studii PMID a PMCID na základě jejího DOI.

Zdroje (v tomto pořadí):
  1. NCBI ID Converter API  — hromadně, 200 DOI na požadavek, pokrývá vše v PMC
  2. NCBI ESearch (PubMed)  — fallback pro studie, které nejsou v PMC
                               (starší a non-open-access práce)

Spuštění:
    python backfill_pmids.py

Výstupy:
    atlas_data/pmid_map.json        {doi: {"pmid": ..., "pmcid": ...}}
    atlas_data/pmid_map.csv         totéž pro import/kontrolu v Airtable
    atlas_data/pmid_report.md       přehled: kolik dohledáno, co chybí a proč
    atlas_data/studies_baked.json   doplněna pole "pmid" a "pmcid" (--no-patch vypne)

Nic se nemaže a nepřepisuje mimo uvedené soubory. Původní studies_baked.json
se před zápisem zálohuje jako studies_baked.json.bak
"""

import json
import csv
import re
import sys
import time
import shutil
import urllib.parse
import urllib.request
from pathlib import Path

# --- konfigurace -----------------------------------------------------------

ROOT = Path(__file__).resolve().parent
STUDIES = ROOT / "atlas_data" / "studies_baked.json"
OUT_JSON = ROOT / "atlas_data" / "pmid_map.json"
OUT_CSV = ROOT / "atlas_data" / "pmid_map.csv"
OUT_REPORT = ROOT / "atlas_data" / "pmid_report.md"

# NCBI chce identifikaci volajícího; při jejím uvedení platí vyšší rate limit
TOOL = "mtor-atlas"
EMAIL = "barton.petr@gmail.com"

IDCONV = "https://www.ncbi.nlm.nih.gov/pmc/utils/idconv/v1.0/"
ESEARCH = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"

BATCH = 200        # maximum, které ID Converter přijme
PAUSE = 0.4        # s mezi požadavky — NCBI limit je 3 req/s bez API klíče
TIMEOUT = 30

PATCH = "--no-patch" not in sys.argv


# --- pomocné ---------------------------------------------------------------

def get_json(url: str) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": f"{TOOL} ({EMAIL})"})
    with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
        return json.loads(r.read().decode("utf-8"))


def looks_like_doi(s: str) -> bool:
    return bool(re.match(r"^10\.\d{4,9}/", s.strip()))


# --- krok 1: hromadně přes ID Converter ------------------------------------

def via_idconv(dois):
    """Vrátí {doi: {'pmid':..,'pmcid':..}} pro to, co je v PMC."""
    found = {}
    for i in range(0, len(dois), BATCH):
        chunk = dois[i:i + BATCH]
        qs = urllib.parse.urlencode({
            "ids": ",".join(chunk),
            "format": "json",
            "tool": TOOL,
            "email": EMAIL,
        })
        print(f"  ID Converter: dávka {i//BATCH + 1} ({len(chunk)} DOI) ...", flush=True)
        try:
            data = get_json(f"{IDCONV}?{qs}")
        except Exception as e:
            print(f"    ! dávka selhala: {e}")
            continue

        for rec in data.get("records", []):
            doi = rec.get("requested-id") or rec.get("doi")
            if not doi or rec.get("status") == "error":
                continue
            pmid = rec.get("pmid")
            if pmid:
                found[doi] = {
                    "pmid": str(pmid),
                    "pmcid": rec.get("pmcid") or "",
                }
        time.sleep(PAUSE)
    return found


# --- krok 2: fallback přes PubMed ESearch -----------------------------------

def via_esearch(dois):
    """Po jednom — pro DOI, které nejsou v PMC, ale v PubMedu být můžou."""
    found = {}
    for n, doi in enumerate(dois, 1):
        qs = urllib.parse.urlencode({
            "db": "pubmed",
            "term": f"{doi}[DOI]",
            "retmode": "json",
            "tool": TOOL,
            "email": EMAIL,
        })
        try:
            data = get_json(f"{ESEARCH}?{qs}")
            ids = data.get("esearchresult", {}).get("idlist", [])
            if ids:
                found[doi] = {"pmid": ids[0], "pmcid": ""}
        except Exception as e:
            print(f"    ! {doi}: {e}")
        if n % 10 == 0:
            print(f"  ESearch: {n}/{len(dois)} ...", flush=True)
        time.sleep(PAUSE)
    return found


# --- main ------------------------------------------------------------------

def main():
    studies = json.loads(STUDIES.read_text(encoding="utf-8"))
    print(f"Načteno {len(studies)} studií z {STUDIES.name}\n")

    dois, skipped = [], []
    for s in studies:
        d = (s.get("doi") or "").strip()
        if looks_like_doi(d):
            dois.append(d)
        elif d:
            skipped.append((s.get("sid", "?"), d))
    dois = list(dict.fromkeys(dois))  # dedup, zachovává pořadí

    print(f"Platných DOI: {len(dois)}   nepoužitelných identifikátorů: {len(skipped)}\n")

    print("Krok 1/2 — NCBI ID Converter")
    mapping = via_idconv(dois)
    print(f"  → dohledáno {len(mapping)}\n")

    missing = [d for d in dois if d not in mapping]
    if missing:
        print(f"Krok 2/2 — PubMed ESearch pro {len(missing)} zbývajících")
        mapping.update(via_esearch(missing))
        print(f"  → celkem dohledáno {len(mapping)}\n")

    still_missing = [d for d in dois if d not in mapping]

    # --- zápis výstupů ---
    OUT_JSON.write_text(json.dumps(mapping, indent=2, ensure_ascii=False), encoding="utf-8")

    with OUT_CSV.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["sid", "doi", "pmid", "pmcid", "open_access"])
        for s in studies:
            d = (s.get("doi") or "").strip()
            m = mapping.get(d, {})
            w.writerow([
                s.get("sid", ""), d,
                m.get("pmid", ""), m.get("pmcid", ""),
                "yes" if m.get("pmcid") else "",
            ])

    n_pmc = sum(1 for v in mapping.values() if v.get("pmcid"))
    pct = 100 * len(mapping) / len(dois) if dois else 0

    report = [
        "# PMID backfill — report", "",
        f"- Studií celkem: **{len(studies)}**",
        f"- Platných DOI: **{len(dois)}**",
        f"- Dohledaných PMID: **{len(mapping)}** ({pct:.1f} %)",
        f"- Z toho s PMCID (tj. volně dostupný fulltext): **{n_pmc}**",
        f"- Nedohledáno: **{len(still_missing)}**", "",
    ]
    if skipped:
        report += ["## Identifikátory, které nejsou DOI", ""]
        report += [f"- `{sid}` → `{v}`" for sid, v in skipped] + [""]
    if still_missing:
        report += [
            "## DOI bez PMID", "",
            "Obvyklé důvody: preprint (bioRxiv/medRxiv), práce z časopisu "
            "neindexovaného v PubMedu, nebo příliš čerstvý záznam.", "",
        ]
        by_doi = {(s.get("doi") or "").strip(): s for s in studies}
        for d in still_missing:
            s = by_doi.get(d, {})
            report.append(f"- `{d}` — {s.get('sid','?')} · {s.get('year','?')} · {s.get('journal','?')}")
        report.append("")
    OUT_REPORT.write_text("\n".join(report), encoding="utf-8")

    # --- volitelný patch baked JSON ---
    if PATCH:
        shutil.copy2(STUDIES, STUDIES.with_suffix(".json.bak"))
        for s in studies:
            m = mapping.get((s.get("doi") or "").strip(), {})
            s["pmid"] = m.get("pmid", "")
            s["pmcid"] = m.get("pmcid", "")
        STUDIES.write_text(json.dumps(studies, indent=1, ensure_ascii=False), encoding="utf-8")
        print(f"studies_baked.json doplněn (záloha: {STUDIES.name}.bak)")

    print(f"\nHotovo. {len(mapping)}/{len(dois)} PMID ({pct:.1f} %), {n_pmc} s volným fulltextem.")
    print(f"Report: {OUT_REPORT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
