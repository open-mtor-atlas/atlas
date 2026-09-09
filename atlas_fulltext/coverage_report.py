#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""coverage_report.py -- kolik korpusu Deep search doopravdy prohledava.

Cislo, ktere chybelo: chunk_index.json umi rict, kolik ma pasazi, ale ne
kolik studii Atlasu tim padem NEvidi. Bez teho se da 8% pokryti tvarit jako
hotova funkce. Spousti se na konci refresh_fulltext.bat.
"""
import json, os, csv

HERE = os.path.dirname(os.path.abspath(__file__))
IDX  = os.path.join(HERE, "chunk_index.json")
MAN  = os.path.join(HERE, "manifest.csv")
BAKED = os.path.join(HERE, "..", "atlas_data", "studies_baked.json")


def main():
    st = json.load(open(BAKED, encoding="utf-8"))
    st = st if isinstance(st, list) else st.get("studies", st)
    total = len(st)
    with_pmcid = sum(1 for s in st if s.get("pmcid"))

    if not os.path.exists(IDX):
        print("chunk_index.json neexistuje -- spust build_chunk_index.py"); return 1
    idx = json.load(open(IDX, encoding="utf-8"))
    sids = {c["sid"] for c in idx["chunks"]}
    size = os.path.getsize(IDX) / 1024.0 / 1024.0

    print("=== POKRYTI DEEP SEARCH ===")
    print("  studii v korpusu:        %d" % total)
    print("  z toho s PMCID:          %d" % with_pmcid)
    print("  s fulltextem v indexu:   %d  (%.0f %% korpusu, %.0f %% kandidatu)"
          % (len(sids), 100.0 * len(sids) / max(total, 1),
             100.0 * len(sids) / max(with_pmcid, 1)))
    print("  pasazi:                  %d" % len(idx["chunks"]))
    print("  velikost indexu:         %.1f MB  (stahuje se pri prvnim Deep search)" % size)

    if os.path.exists(MAN):
        rows = list(csv.DictReader(open(MAN, encoding="utf-8")))
        from collections import Counter
        c = Counter(r.get("status", "?") for r in rows)
        print("  manifest:                " + ", ".join("%s=%d" % kv for kv in sorted(c.items())))

    if size > 6:
        print("\n  ! Index presahl 6 MB. Jeden soubor uz je pro prvni nacteni moc --")
        print("    rozdelit po sekcich nebo prejit na postings list.")
    if len(sids) < with_pmcid * 0.5:
        print("\n  ! Pokryta je min nez polovina kandidatu. Vetsinou je duvod licence")
        print("    (jen CC bez ND se smi ulozit) -- zkontroluj status v manifest.csv.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
