#!/usr/bin/env python3
"""build_lab_map.py - preguje Atlas Lab Map z atlas_data/author_bios_baked.json.

Zdroj: pole lab_name (format "Nazev laboratore, instituce (mesto, stat, zeme)"),
lab_url, highlights (pocet studii). Souradnice mest jsou v atlas_data/lab_geo.json;
nove mesto se zkusi dohledat pres Nominatim (potrebuje sit) a ulozi se do cache.
Vystup: "Claude outputs/atlas-lab-map.html" (sablona atlas_data/lab_map_template.html).

Exit kod 0 = mapa postavena (i s varovanim); 1 = chyba, ktera mapu znehodnoti.
Varovani: medailonek bez lab_name nebo bez parsovatelne lokace, mesto bez souradnic.
Pouziti: py build_lab_map.py [--strict]   (--strict: varovani konci kodem 2)
"""
import json, os, re, sys, time, urllib.parse, urllib.request
from datetime import date

ROOT = os.path.dirname(os.path.abspath(__file__))
BIOS = os.path.join(ROOT, "atlas_data", "author_bios_baked.json")
GEO = os.path.join(ROOT, "atlas_data", "lab_geo.json")
TPL = os.path.join(ROOT, "atlas_data", "lab_map_template.html")
OUT = os.path.join(ROOT, "Claude outputs", "atlas-lab-map.html")

NE = {"Massachusetts","New York","Connecticut","New Jersey","Maine","New Hampshire","Vermont",
      "Rhode Island","Pennsylvania","Maryland","Delaware","District of Columbia","Virginia"}
WEST = {"California","Washington","Oregon","Nevada","Alaska","Hawaii","Arizona","Utah",
        "Colorado","Idaho","Montana","Wyoming","New Mexico"}
EUROPE = {"Czech Republic","Switzerland","Italy","Spain","UK","Germany","France","Netherlands",
          "Ireland","Austria","Sweden","Belgium","Denmark","Norway","Finland","Poland","Portugal",
          "Greece","Hungary","Slovakia","Slovenia","Croatia","Serbia","Romania","Bulgaria",
          "Estonia","Latvia","Lithuania","Luxembourg","Iceland","Ukraine","Russia","Turkey"}
APAC = {"Kazakhstan","South Korea","Japan","Singapore","India","Taiwan","Australia","New Zealand",
        "Thailand","Malaysia","Indonesia","Vietnam","Philippines","Hong Kong","Pakistan",
        "Bangladesh","Saudi Arabia","Israel","Iran","United Arab Emirates","Egypt"}

def split_lab_name(ln):
    """'Lab, Inst (a, b, c)' -> ('Lab, Inst', 'a, b, c') podle POSLEDNI vyvazene zavorky."""
    ln = (ln or "").strip()
    if not ln.endswith(")"):
        return None
    depth = 0
    for i in range(len(ln) - 1, -1, -1):
        if ln[i] == ")": depth += 1
        elif ln[i] == "(":
            depth -= 1
            if depth == 0:
                lab, loc = ln[:i].strip(), ln[i + 1:-1].strip()
                return (lab, loc) if lab and loc else None
    return None

def country_of(loc):
    c = loc.split(",")[-1].strip()
    return "UK" if c == "United Kingdom" else c

def region_of(loc):
    parts = [p.strip() for p in loc.split(",")]
    country = country_of(loc)
    if country == "USA":
        st = parts[-2] if len(parts) >= 3 else ""
        return "US Northeast (Boston–NY)" if st in NE else "US West Coast" if st in WEST else "US Midwest & South"
    if country == "Canada":
        prov = parts[-2] if len(parts) >= 3 else ""
        if prov == "British Columbia" or prov == "Alberta": return "US West Coast"
        if parts[0] == "London": return "US Midwest & South"
        return "US Northeast (Boston–NY)"
    if country == "China": return "China"
    if country in EUROPE: return "Europe"
    if country in APAC: return "Asia-Pacific (other)"
    return "Other regions"

def geocode(loc, warn):
    q = ", ".join(p for p in (x.strip() for x in loc.replace("(", ",").replace(")", "").split(",")) if p)
    url = "https://nominatim.openstreetmap.org/search?format=json&limit=1&q=" + urllib.parse.quote(q)
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "open-mtor-atlas-lab-map/1.0 (mtor-atlas.org)"})
        with urllib.request.urlopen(req, timeout=15) as r:
            data = json.load(r)
        time.sleep(1.1)  # limit Nominatim: 1 dotaz/s
        if data:
            return [round(float(data[0]["lat"]), 4), round(float(data[0]["lon"]), 4)]
    except Exception as e:
        warn.append(f"geokodovani '{loc}' selhalo ({e.__class__.__name__}) - dopln souradnice do atlas_data/lab_geo.json")
        return None
    warn.append(f"Nominatim nenasel '{loc}' - dopln souradnice do atlas_data/lab_geo.json")
    return None

def main():
    strict = "--strict" in sys.argv
    bios = json.load(open(BIOS, encoding="utf8"))
    geo = json.load(open(GEO, encoding="utf8")) if os.path.exists(GEO) else {}
    warn, rows, geo_dirty = [], [], False
    for key, b in bios.items():
        parsed = split_lab_name(b.get("lab_name"))
        if not parsed:
            warn.append(f"{key} ({b.get('full','?')}): chybi lab_name, nebo nema lokaci v zavorce '(mesto, stat, zeme)'")
            continue
        lab, loc = parsed
        if loc not in geo:
            g = geocode(loc, warn)
            if g: geo[loc] = g; geo_dirty = True
        if loc not in geo:
            warn.append(f"{key}: mesto '{loc}' nema souradnice - autor je mimo mapu")
            continue
        rows.append([key, b.get("full", key), lab, loc, country_of(loc), region_of(loc),
                     len(b.get("highlights") or {}), b.get("lab_url") or "", geo[loc][0], geo[loc][1]])
    if not rows:
        print("CHYBA: zadny radek pro mapu"); return 1
    rows.sort(key=lambda r: (-r[6], r[1]))
    if geo_dirty:
        json.dump(geo, open(GEO, "w", encoding="utf8", newline=""), ensure_ascii=False, indent=1, sort_keys=True)
    tpl = open(TPL, encoding="utf8").read()
    assert "/*__ROWS__*/[]" in tpl and "/*__STAMP__*/" in tpl, "sablona nema znacky"
    html = tpl.replace("/*__ROWS__*/[]", json.dumps(rows, ensure_ascii=False, separators=(",", ":")), 1)
    html = html.replace("/*__STAMP__*/", "build " + date.today().isoformat(), 1)
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    tmp = OUT + ".tmp"
    with open(tmp, "w", encoding="utf8", newline="") as f:
        f.write(html); f.flush(); os.fsync(f.fileno())
    if open(tmp, encoding="utf8").read() != html:
        print("CHYBA: zapis vystupu se neshoduje (uriznuty soubor)"); return 1
    os.replace(tmp, OUT)
    cities = len({r[3] for r in rows}); countries = len({r[4] for r in rows})
    print(f"Lab map: {len(rows)}/{len(bios)} autoru, {cities} mest, {countries} zemi -> {os.path.relpath(OUT, ROOT)}")
    for w in warn: print("  VAROVANI:", w)
    return 2 if (warn and strict) else 0

if __name__ == "__main__":
    sys.exit(main())
