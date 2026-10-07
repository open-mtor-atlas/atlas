#!/usr/bin/env python3
"""
sync_lab_lineage.py -- Airtable Lab_Lineage -> atlas_data/lab_lineage_baked.json

Rodokmen laboratoří (kdo koho vyškolil, PhD / postdok, co si žák odnesl do
vlastní laboratoře). Čte ho stránka /field/lineage/ ve V2 (Atlas_v2 ->
scripts/sync_data.py ho kopíruje z origin/main). Pravidla tabulky jsou
v projektovém dokumentu claude/lab-lineage-2026-10-07.md.

Co se peče:
  * jen záznamy se zaškrtnutým Published (= ověřeno dvěma zdroji),
  * jen veřejná pole: interní Notes a Own_Lab_Note se NEPEČOU,
  * výstup je seřazený a bez časového razítka, takže beze změny v Airtable
    vznikne bajtově stejný soubor a commit nic nehlásí.

Pojistky:
  * Dry run je default; zápis jen s --write.
  * Publikovaný záznam bez mentora nebo žáka se přeskočí a vypíše.
  * Když by výsledek měl méně než polovinu hran minulého souboru, zápis se
    zastaví (spíš výpadek API nebo filtru než skutečné mazání).
  * Zápis je atomický (temp + fsync + os.replace + kontrola zpětným čtením).

    set AIRTABLE_TOKEN=patXXXXXXXX
    py sync_lab_lineage.py            # dry run
    py sync_lab_lineage.py --write
    py sync_lab_lineage.py --from-dump dump.json --write   # bez sítě, z MCP výpisu
"""
import json
import os
import re
import sys
import urllib.parse
import urllib.request

BASE = "appt2U6ObDHUcRlrj"
TABLE = "tblhrA9yNOC08RDB9"
ROOT = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(ROOT, "atlas_data", "lab_lineage_baked.json")

F = {
    "id": "fldQHMvi2pTzwNSB6",
    "mentor": "fldNEug9vJpgA9pcm",
    "trainee": "fldkaGDwBqv6nf8v3",
    "mentor_key": "fldB3xdPWIj6nOR4L",
    "trainee_key": "fldHxixIMaSRRjPTH",
    "role": "fldX8KNOznLwlrIzE",
    "period": "fld3SmxU0UVvhVnbn",
    "work": "fldGGd9kYvvoG2THa",
    "own_lab": "fldmk2bblaf6xDWpB",
    "branch": "fldAq9CcxfxKSK1Nl",
    "focus": "fldCEnYaNTCSCcMdO",
    "focus_beginner": "fld22zbqGszx90d0b",
    "pmids": "fld0WhAFaGCS8DKPd",
    "urls": "fld0aHstyzB9rdGXg",
    "verification": "fldoG86vDb0mwHuAF",
}
F_PUBLISHED = "fldwr0dSQRnh6NGKO"

INVISIBLE = re.compile("[​-‏‪-‮⁠-⁤﻿­]")


def clean(v):
    if isinstance(v, dict):           # MCP vrací select jako objekt
        v = v.get("name")
    if v is None:
        return ""
    s = INVISIBLE.sub("", str(v)).replace(" ", " ")
    return re.sub(r"[ \t]+", " ", s).strip()


def api():
    token = os.environ.get("AIRTABLE_TOKEN")
    if not token:
        sys.exit('AIRTABLE_TOKEN is not set.  PowerShell: $env:AIRTABLE_TOKEN = "patXXXX"')
    out, offset = [], None
    fields = list(F.values()) + [F_PUBLISHED]
    while True:
        p = {"returnFieldsByFieldId": "true", "pageSize": "100", "fields[]": fields}
        if offset:
            p["offset"] = offset
        url = "https://api.airtable.com/v0/%s/%s?%s" % (BASE, TABLE, urllib.parse.urlencode(p, doseq=True))
        req = urllib.request.Request(url, headers={"Authorization": "Bearer " + token})
        with urllib.request.urlopen(req, timeout=60) as r:
            data = json.load(r)
        out.extend({"id": x["id"], "f": x.get("fields", {})} for x in data.get("records", []))
        offset = data.get("offset")
        if not offset:
            return out


def from_dump(path):
    d = json.load(open(path, encoding="utf-8"))
    recs = d["records"] if isinstance(d, dict) else d
    return [{"id": x["id"], "f": x.get("cellValuesByFieldId") or x.get("fields") or {}} for x in recs]


def pmid_list(s):
    """'28355222 (2017)\\n27549339' -> [{'pmid': '28355222', 'year': '2017'}, ...]"""
    out, seen = [], set()
    for line in re.split(r"[\n;,]+", s):
        m = re.search(r"\b(\d{6,9})\b(?:\D*?((?:19|20)\d\d))?", line)
        if m and m.group(1) not in seen:
            seen.add(m.group(1))
            out.append({"pmid": m.group(1), "year": m.group(2) or ""})
    return out


def url_list(s):
    return [u for u in re.findall(r"https?://[^\s<>\"]+", s)]


def bake(recs):
    edges, skipped = [], []
    for r in recs:
        f = r["f"]
        if not f.get(F_PUBLISHED):
            continue
        e = {k: clean(f.get(fid)) for k, fid in F.items()}
        if not e["mentor"] or not e["trainee"]:
            skipped.append(e["id"] or r["id"])
            continue
        e["pmids"] = pmid_list(e["pmids"])
        e["urls"] = url_list(e["urls"])
        e["kind"] = "staff" if e["role"] == "Research scientist" else "trainee"
        edges.append({k: v for k, v in e.items() if v not in ("", [])})
    edges.sort(key=lambda e: (e["id"].lower(), e["trainee"].lower()))
    return edges, skipped


def write_atomic(path, text):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(text)
        fh.flush()
        os.fsync(fh.fileno())
    os.replace(tmp, path)
    if open(path, encoding="utf-8").read() != text:
        sys.exit("ABORTED: %s nesouhlasí po zápisu" % path)


def main():
    write = "--write" in sys.argv
    if "--from-dump" in sys.argv:
        recs = from_dump(sys.argv[sys.argv.index("--from-dump") + 1])
    else:
        print("Reading Airtable Lab_Lineage...")
        recs = api()
    edges, skipped = bake(recs)
    print("  %d records, %d published edges" % (len(recs), len(edges)))
    for s in skipped:
        print("  ! skipped (published, but no mentor or trainee name): %s" % s)

    old = []
    if os.path.exists(OUT):
        try:
            old = json.load(open(OUT, encoding="utf-8")).get("edges", [])
        except Exception:
            old = []
    o, n = {e["id"] for e in old}, {e["id"] for e in edges}
    for k in sorted(n - o):
        print("  + %s" % k)
    for k in sorted(o - n):
        print("  - %s" % k)
    if old and len(edges) < len(old) / 2:
        sys.exit("ABORTED: %d edges now vs %d before - looks like an API or filter failure, not a real change."
                 % (len(edges), len(old)))

    text = json.dumps({"source": "Airtable Lab_Lineage, Published records only",
                       "note": "Editorial reconstruction of training links (PhD, postdoc). "
                               "Each published link is backed by a PubMed co-authorship at the mentor's "
                               "institution and an independent page naming the mentor.",
                       "edges": edges}, ensure_ascii=False, indent=1) + "\n"
    if not write:
        print("  dry run - nothing written (use --write)")
        return 0
    if os.path.exists(OUT) and open(OUT, encoding="utf-8").read() == text:
        print("  unchanged: %s" % os.path.relpath(OUT, ROOT))
        return 0
    write_atomic(OUT, text)
    print("  wrote %s" % os.path.relpath(OUT, ROOT))
    return 0


if __name__ == "__main__":
    sys.exit(main())
