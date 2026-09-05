#!/usr/bin/env python3
"""
sync_relations.py -- Airtable Relations -> ATLAS_EDGES in index.html

Closes the gap that made every edge correction a two-step manual job.
sync_airtable.py writes ATLAS_STUDIES, ATLAS_ENTITIES and ATLAS_GAPS but has
never touched the Relations table, so edits made there reached nothing:
build_pathway_model.py reads ATLAS_EDGES out of index.html, and that array was
maintained by hand. Corrections written to Airtable on 2026-08-30 and
2026-09-04 had to be re-applied to index.html separately, and twice they were
missed until the verifier caught them.

    set AIRTABLE_TOKEN=patXXXXXXXX
    py sync_relations.py                 # dry run: prints a per-field diff
    py sync_relations.py --write         # applies it
    py sync_relations.py --write --include-note   # see WARNING below

DESIGN: conservative on purpose
-------------------------------
This script rewrites hand-maintained prose, so it refuses more than it does.

  * Dry run by default. --write is required to touch anything.
  * Never adds or removes edges. ATLAS_EDGES entries with no Airtable row, and
    Airtable rows with no ATLAS_EDGES entry, are reported and left alone. Adding
    an edge changes the pathway model and is a curator decision.
  * Never blanks a populated field. If Airtable is empty and index.html has
    text, the text stays. Airtable is incomplete in places and a blind sync
    would silently delete curated content.
  * Writes a timestamped backup of index.html before any change.
  * Recomputes tier/tiers from the synced study list, so evidence grading cannot
    drift out of step with the citations it is derived from.

WARNING about "note"
--------------------
ATLAS_EDGES.note maps to Curator_Note, which is ALSO where audit rationale gets
written ("ZHU2026 removed 2026-09-04 - it is a liver toxicology study..."). That
text is internal review commentary, not site copy, and note[] is rendered to
readers. So note is NOT synced unless you pass --include-note. If you do, read
the diff first. The cleaner long-term fix is a separate Airtable field for
public-facing edge notes, leaving Curator_Note internal.

Fields are addressed by field ID, not name, so renaming a column in Airtable
cannot silently break the mapping.
"""
import datetime, json, os, re, sys, urllib.parse, urllib.request

BASE = "appt2U6ObDHUcRlrj"
T_RELATIONS = "tblT4hOU9HrTFe4Ik"
T_STUDIES = "tblbQIQtzn2vWaV6d"

F = {
    "edge_id":     "fldXL4UK8ARBfNhEo",
    "sign":        "fldI3qyVK5idZkwOw",
    "mech":        "fldqkYGZVr7N8c9sj",
    "studies":     "fldhbXPw6k6BhARQD",
    "conflicting": "fld7lBBqegd5dSjA3",
    "dir":         "fldsJH6jZRrj31gqp",
    "sp":          "fldxRTNv88mvmNsaE",
    "ctx":         "fldXVdsFzV2y9m4oT",
    "status":      "fldEO9HwufC5nEXKo",
    "note":        "fldND70SWZKmHA9kn",
}
F_STUDY_SID = "fldnmqtOHZ0luHRiI"
F_STUDY_TIER = "fld4mOmLgEYFA4mYE"

# ATLAS_EDGES key <- Airtable field. Order is the diff display order.
SCALAR = [("sign", "sign"), ("mech", "mech"), ("dir", "dir"),
          ("sp", "sp"), ("ctx", "ctx"), ("status", "status")]
LINKED = [("st", "studies"), ("cf", "conflicting")]

HERE = os.path.dirname(os.path.abspath(__file__))
HTML = os.path.join(HERE, "index.html")
WRITE = "--write" in sys.argv
INCLUDE_NOTE = "--include-note" in sys.argv


def api(table, params=None):
    token = os.environ.get("AIRTABLE_TOKEN")
    if not token:
        sys.exit('AIRTABLE_TOKEN is not set.  PowerShell: $env:AIRTABLE_TOKEN = "patXXXX"')
    out, offset = [], None
    while True:
        p = dict(params or {})
        p["returnFieldsByFieldId"] = "true"
        p["pageSize"] = "100"
        if offset:
            p["offset"] = offset
        url = "https://api.airtable.com/v0/%s/%s?%s" % (BASE, table, urllib.parse.urlencode(p, doseq=True))
        req = urllib.request.Request(url, headers={"Authorization": "Bearer " + token})
        with urllib.request.urlopen(req, timeout=60) as r:
            data = json.load(r)
        out.extend(data.get("records", []))
        offset = data.get("offset")
        if not offset:
            return out


def tier_letter(s):
    m = re.match(r"\s*([A-D])\b", s or "")
    return m.group(1) if m else None


def load_edges(src):
    i = src.find("const ATLAS_EDGES = [")
    if i < 0:
        sys.exit("ABORT: ATLAS_EDGES not found in index.html.")
    head = "const ATLAS_EDGES = "
    seg = src[i + len(head):]
    end = seg.find("];") + 1
    return json.loads(seg[:end]), i + len(head), i + len(head) + end


def main():
    print("Reading Airtable...")
    studies = api(T_STUDIES, {"fields[]": [F_STUDY_SID, F_STUDY_TIER]})
    sid = {r["id"]: (r["fields"].get(F_STUDY_SID) or "").strip() for r in studies}
    tier_of = {r["id"]: tier_letter(r["fields"].get(F_STUDY_TIER)) for r in studies}
    tier_by_sid = {sid[k]: v for k, v in tier_of.items() if sid.get(k) and v}
    rels = api(T_RELATIONS, {"fields[]": list(F.values())})
    print("  %d studies, %d relations" % (len(studies), len(rels)))

    at = {}
    for r in rels:
        f = r["fields"]
        eid = (f.get(F["edge_id"]) or "").strip()
        if eid:
            at[eid] = f

    src = open(HTML, encoding="utf-8").read()
    edges, lo, hi = load_edges(src)
    local = {e["id"]: e for e in edges}

    only_local = sorted(set(local) - set(at))
    only_air = sorted(set(at) - set(local))
    if only_local:
        print("\n%d edge(s) in index.html with no Airtable row (left untouched):" % len(only_local))
        print("   " + ", ".join(only_local))
    if only_air:
        print("\n%d Airtable row(s) with no edge in index.html (NOT added - curator decision):"
              % len(only_air))
        print("   " + ", ".join(only_air))

    changes, kept = [], 0
    for eid, e in local.items():
        f = at.get(eid)
        if not f:
            continue
        new = {}

        for key, fk in SCALAR:
            v = f.get(F[fk])
            v = v.strip() if isinstance(v, str) else v
            if not v:
                if e.get(key):
                    kept += 1
                continue
            if v != e.get(key):
                new[key] = v

        for key, fk in LINKED:
            ids = f.get(F[fk]) or []
            v = sorted({sid[i] for i in ids if sid.get(i)})
            if not v:
                if e.get(key):
                    kept += 1
                continue
            if v != sorted(e.get(key) or []):
                new[key] = v

        if INCLUDE_NOTE:
            v = (f.get(F["note"]) or "").strip()
            if v and v != e.get("note"):
                new["note"] = v

        if new:
            changes.append((eid, new, e))

    # tier/tiers are DERIVED from the cited studies and must never be hand-held.
    # Recomputed for every edge from its (possibly just-synced) st, not only for
    # edges Airtable touched: removing a study from ATLAS_EDGES by hand on
    # 2026-09-04 left LKB1-AMPK claiming tier C on the strength of a citation it
    # no longer had. build_pathway_model.py recomputes independently, so
    # model.json was right and only this array was stale -- which is exactly the
    # kind of drift nobody notices.
    for eid, e in local.items():
        pend = dict(next((n for i, n, _ in changes if i == eid), {}))
        sids = pend.get("st", e.get("st") or [])
        letters = sorted({t for t in (tier_by_sid.get(c) for c in sids) if t})
        if not letters:
            continue
        fix = {}
        if letters != sorted(e.get("tiers") or []):
            fix["tiers"] = letters
        if min(letters) != e.get("tier"):
            fix["tier"] = min(letters)
        if fix:
            hit = next((c for c in changes if c[0] == eid), None)
            if hit:
                hit[1].update(fix)
            else:
                changes.append((eid, fix, e))

    if not changes:
        print("\nNothing to change: ATLAS_EDGES already matches Airtable.")
        if kept:
            print("(%d field(s) left as-is because Airtable was empty.)" % kept)
        return

    print("\n%d edge(s) would change:\n" % len(changes))
    for eid, new, e in changes:
        print("  " + eid)
        for k, v in new.items():
            old = e.get(k)
            if isinstance(v, list):
                print("    %-6s %s -> %s" % (k, old, v))
            else:
                o = (str(old) or "")[:70].replace("\n", " ")
                n = str(v)[:70].replace("\n", " ")
                print("    %-6s %r" % (k, o))
                print("    %-6s %r" % ("", n))
        print()
    if kept:
        print("%d field(s) left as-is because Airtable was empty (never blanked).\n" % kept)

    if not WRITE:
        print("Dry run. Re-run with --write to apply.")
        if not INCLUDE_NOTE:
            print("note/Curator_Note not synced; see the docstring before using --include-note.")
        return

    for eid, new, e in changes:
        e.update(new)

    stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    backup = HTML + ".bak-" + stamp
    open(backup, "w", encoding="utf-8").write(src)
    print("backup: %s" % os.path.basename(backup))

    out = src[:lo] + json.dumps(edges, ensure_ascii=False, separators=(",", ":")) + src[hi:]
    if not out.rstrip().endswith("</html>"):
        sys.exit("ABORT: output does not end in </html>; index.html untouched.")
    if len(load_edges(out)[0]) != len(edges):
        sys.exit("ABORT: edge count changed; index.html untouched.")
    tmp = HTML + ".tmp"
    open(tmp, "w", encoding="utf-8").write(out)
    if open(tmp, encoding="utf-8").read() != out:
        sys.exit("ABORT: read-back mismatch; index.html untouched.")
    os.replace(tmp, HTML)
    print("index.html updated. Now run: py build_pathway_model.py")


if __name__ == "__main__":
    main()
