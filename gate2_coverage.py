#!/usr/bin/env python3
"""GATE 2 - pokryti korpusu (coverage gate).

Odpovida na otazku, kterou se denni kontrola nikdy neptá: "ktera vetev mTOR
literatury v Atlasu chybi cela?" Denni kontrola i zakladaci sada korpusu jsou
tematicke - berou, co prijde. Proto muze mit cely obor laborator s desitkami
praci a v Atlasu nebyt vubec (pripad Korolchuk, 2026-09-13).

Kontroluje tri veci proti atlas_data/studies_baked.json:

  1. VETVE   - kazda vetev z coverage_roster.json musi mit aspon N studii.
  2. KOTVY   - jmenovana zakladajici prace kazde vetve musi byt v korpusu
               (parovani podle PMID, fallback DOI, fallback Study_ID).
  3. LIDE    - jmena z rosteru, ktera v korpusu nemaji ani jednu studii.
  4. ZAZNAMY - autorske klice s >=2 studiemi, ktere nemaji zaznam
               v atlas_data/author_allowlist.json (tj. sync Authors je pozadu).
  5. MEDAILONKY - klice se statusem "Jeden clovek", ktere nemaji medailonek
               v atlas_data/author_bios_baked.json (pravidlo z 2026-09-13).
               Klice se statusem "Vice lidi" / "Chyba v datech" se preskakuji,
               u nich se medailonek stavet nesmi.

Neblokuje deploy. Je to mesicni kuratorska brana, ne technicka.

Pouziti:
    python gate2_coverage.py                 # report do konzole
    python gate2_coverage.py --json          # strojove citelny vystup
    python gate2_coverage.py --due-only      # mlci, dokud neni cas na revizi
    python gate2_coverage.py --strict        # exit 1, kdyz je nalez

Exit kody: 0 = bez nalezu (nebo neni --strict), 1 = nalez pri --strict,
2 = chyba vstupu.
"""

import argparse
import datetime as _dt
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
DEF_STUDIES = os.path.join(HERE, "atlas_data", "studies_baked.json")
DEF_ROSTER = os.path.join(HERE, "atlas_data", "coverage_roster.json")
DEF_BIOS = os.path.join(HERE, "atlas_data", "author_bios_baked.json")
DEF_ALLOW = os.path.join(HERE, "atlas_data", "author_allowlist.json")

SEARCH_FIELDS = ("title", "finding", "abstract", "ai_target", "ai_intervention",
                 "model", "journal")


def _load(path, what):
    if not os.path.exists(path):
        sys.stderr.write("GATE 2: chybi %s (%s)\n" % (what, path))
        sys.exit(2)
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def _haystack(study):
    return " \n ".join(str(study.get(f) or "") for f in SEARCH_FIELDS).lower()


def _kw_re(keyword):
    """Slovo jako cele slovo, ale tolerantne k pomlckam a zavorkam."""
    esc = re.escape(keyword.lower())
    esc = esc.replace(r"\ ", r"[\s\-]+")
    return re.compile(r"(?<![a-z0-9])" + esc + r"(?![a-z0-9])")


def _author_keys(authors_field):
    """Rozebere 'Kamada Y; Ohsumi Y et al.' na klice."""
    txt = re.sub(r"\bet\s+al\.?", "", authors_field or "")
    out = []
    for part in re.split(r"[;,]| and ", txt):
        part = part.strip().rstrip(".")
        if len(part) >= 3:
            out.append(part)
    return out


def run(studies, roster, bios, allow):
    findings = {"branches": [], "anchors": [], "people": [],
                "records": [], "bios": []}

    pmids = {str(s.get("pmid") or "").strip() for s in studies}
    pmids.discard("")
    dois = {str(s.get("doi") or "").strip().lower() for s in studies}
    dois.discard("")
    sids = {str(s.get("sid") or "").strip() for s in studies}
    hay = [(s, _haystack(s)) for s in studies]

    min_studies = int(roster.get("min_studies_per_branch", 1))

    for br in roster.get("branches", []):
        pats = [_kw_re(k) for k in br.get("keywords", [])]
        hits = [s["sid"] for s, h in hay if any(p.search(h) for p in pats)]
        if len(hits) < min_studies:
            findings["branches"].append({
                "id": br["id"], "label": br["label"],
                "count": len(hits), "required": min_studies,
            })
        for a in br.get("anchors", []):
            have = (str(a.get("pmid") or "") in pmids
                    or str(a.get("doi") or "").lower() in dois
                    or str(a.get("sid") or "") in sids)
            if not have:
                findings["anchors"].append({
                    "branch": br["id"], "cite": a.get("cite", ""),
                    "pmid": a.get("pmid", ""), "sid": a.get("sid", ""),
                    "why": a.get("why", ""),
                })

    corpus_keys = {}
    for s in studies:
        for k in _author_keys(s.get("authors", "")):
            corpus_keys.setdefault(k, []).append(s["sid"])

    lowered = {k.lower(): k for k in corpus_keys}
    for p in roster.get("people", []):
        key = p["key"]
        found = lowered.get(key.lower())
        if not found:
            surname = key.split()[0].lower()
            found = next((orig for low, orig in lowered.items()
                          if low.split()[0] == surname), None)
        if not found:
            findings["people"].append({
                "key": key, "label": p.get("label", key),
                "branch": p.get("branch", ""), "why": p.get("why", ""),
            })

    blocked = {"Vice lidi", "V\u00edce lid\u00ed", "Chyba v datech"}
    for key, hit_sids in sorted(corpus_keys.items()):
        uniq = sorted(set(hit_sids))
        rec = allow.get(key)
        if len(uniq) >= 2 and rec is None:
            findings["records"].append({"key": key, "studies": uniq})
            continue
        if rec is None:
            continue
        if str(rec.get("status", "")) in blocked:
            continue
        if key not in bios:
            findings["bios"].append({"key": key, "studies": uniq,
                                     "full": rec.get("full", "")})

    return findings


def due(roster):
    last = roster.get("last_reviewed")
    interval = int(roster.get("review_interval_days", 30))
    if not last:
        return True, None
    try:
        d = _dt.date.fromisoformat(last)
    except ValueError:
        return True, None
    days = (_dt.date.today() - d).days
    return days >= interval, days


def main():
    ap = argparse.ArgumentParser(description="GATE 2 - pokryti korpusu")
    ap.add_argument("--studies", default=DEF_STUDIES)
    ap.add_argument("--roster", default=DEF_ROSTER)
    ap.add_argument("--bios", default=DEF_BIOS)
    ap.add_argument("--allowlist", default=DEF_ALLOW)
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--due-only", action="store_true")
    ap.add_argument("--strict", action="store_true")
    args = ap.parse_args()

    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

    studies = _load(args.studies, "studies_baked.json")
    roster = _load(args.roster, "coverage_roster.json")
    bios = _load(args.bios, "author_bios_baked.json") if os.path.exists(args.bios) else {}
    allow = _load(args.allowlist, "author_allowlist.json") if os.path.exists(args.allowlist) else {}

    is_due, days = due(roster)
    if args.due_only and not is_due:
        print("GATE 2: revize neni na rade (naposledy %s, za %d dni)."
              % (roster.get("last_reviewed"), roster.get("review_interval_days", 30) - (days or 0)))
        return 0

    f = run(studies, roster, bios, allow)
    total = sum(len(v) for v in f.values())

    if args.json:
        print(json.dumps({"studies": len(studies), "due": is_due,
                          "days_since_review": days, "findings": f},
                         ensure_ascii=False, indent=2))
        return 1 if (total and args.strict) else 0

    print("GATE 2 - pokryti korpusu")
    print("studii v korpusu: %d | medailonku: %d | posledni revize: %s (%s dni)"
          % (len(studies), len(bios), roster.get("last_reviewed", "?"),
             "?" if days is None else days))
    print("-" * 72)

    if f["branches"]:
        print("\nPRAZDNE / PODVYZIVENE VETVE (%d):" % len(f["branches"]))
        for b in f["branches"]:
            print("  - %-28s %d studii (min %d)  %s"
                  % (b["id"], b["count"], b["required"], b["label"]))
    if f["anchors"]:
        print("\nCHYBEJICI ZAKLADAJICI PRACE (%d):" % len(f["anchors"]))
        for a in f["anchors"]:
            print("  - [%s] %s  PMID %s" % (a["branch"], a["cite"], a["pmid"]))
            if a["why"]:
                print("      %s" % a["why"])
    if f["people"]:
        print("\nLIDE Z ROSTERU BEZ JEDINE STUDIE (%d):" % len(f["people"]))
        for p in f["people"]:
            print("  - %-24s %-18s %s" % (p["key"], p["branch"], p["why"]))
    if f["records"]:
        print("\nV KORPUSU, ALE BEZ ZAZNAMU V AUTHORS (%d) - sync je pozadu:"
              % len(f["records"]))
        for b in sorted(f["records"], key=lambda x: -len(x["studies"])):
            print("  - %-24s %s" % (b["key"], ", ".join(b["studies"])))
    if f["bios"]:
        print("\nJEDNOZNACNI AUTORI BEZ MEDAILONKU (%d):" % len(f["bios"]))
        for b in f["bios"]:
            print("  - %-24s %-26s %s"
                  % (b["key"], b.get("full", ""), ", ".join(b["studies"])))

    if not total:
        print("\nBez nalezu.")
    else:
        print("\nCelkem nalezu: %d" % total)
        print("Latka pro zarazeni studie zustava: byla by tahle prace v Atlasu")
        print("i tehdy, kdyby o tom cloveku nikdo neuvazoval?")

    return 1 if (total and args.strict) else 0


if __name__ == "__main__":
    sys.exit(main())
