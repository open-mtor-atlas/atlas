#!/usr/bin/env python3
"""
map_entities_dump.py -- convert a raw Airtable MCP list_records_for_table result
for the Entities table into atlas_data/entities_baked.json, the flat key shape
bake_from_mcp.py expects (matching what ATLAS_ENTITIES in index.html holds).

Usage:
    python3 map_entities_dump.py <raw-mcp-result.json> [--strict]

WHY THIS FILE EXISTS (2026-09-02)
---------------------------------
entities_baked.json had been stale since 2026-08-17: 120 entities baked while
Airtable held 146. Nothing in the pipeline refreshed it -- sync_airtable.py only
knew Studies + Knowledge_Gaps, bake_from_mcp.py only *consumed*
entities_baked.json, and the map_*_dump.py family had scripts for Studies and
Events but never one for Entities. So every bake re-stamped the same 120 into
the crawler-visible counts and the Entity Browser. This closes that hole on the
MCP path; sync_airtable.py::fetch_entities() closes it on the token path.

CARRY-FORWARD (default on; --strict disables)
---------------------------------------------
Description_Beginner is hand-authored, register-rewritten text. If a dump omits
it for a record that already has one baked, the value is carried forward from
the existing entities_baked.json rather than blanked -- the same pattern
sync_airtable.py::existing_gap_beginner_fields() uses for ATLAS_GAPS. Same for
Description, so a deliberately partial dump (e.g. one hand-assembled from a
paged MCP read that omitted the description columns) cannot silently wipe 120
curated descriptions.

Pass --strict when the dump is genuinely complete and an empty field in Airtable
really should clear the baked value. Always read the "carried forward" counts it
prints: a full dump that reports a large carry count means the dump was
incomplete, not that the data was fine.
"""
import sys, os, json, time

MAP = {
    'fldh3zgrLDjLi1szC': 'name',
    'fldSoUgZxKTYhJcyX': 'type',
    'fldY3eEGQf6xh3QmZ': 'desc',
    'flduckIR0kzKzAlkD': 'synonyms',
    'fldXAPRr4EpWg5nln': 'studies',
    'fldJuq0IWDdSSlbMS': 'desc_beginner',
}
# The exact key set (and order) ATLAS_ENTITIES rows carry. Asserted on output so
# a shape drift is a hard failure here, not a silent blank in the browser.
KEYS = ['id', 'name', 'type', 'desc', 'synonyms', 'studies', 'desc_beginner']
CARRYABLE = ('desc', 'desc_beginner')

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "atlas_data", "entities_baked.json")


def unwrap(v):
    """singleSelect -> its name; linked records -> list of primary-field names."""
    if isinstance(v, dict) and 'name' in v:
        return v['name']
    if isinstance(v, list):
        return [x['name'] if isinstance(x, dict) and 'name' in x else x for x in v]
    return v if v is not None else ''


def write_verified(path, content):
    """Atomic write + byte-length verification. This folder is OneDrive-synced
    and large writes here have repeatedly been truncated in silence."""
    expected = len(content.encode("utf-8"))
    for attempt in range(1, 6):
        tmp = "%s.tmp%d" % (path, os.getpid())
        try:
            with open(tmp, "w", encoding="utf-8") as f:
                f.write(content)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp, path)
            with open(path, encoding="utf-8") as f:
                if len(f.read().encode("utf-8")) != expected:
                    raise RuntimeError("write verification failed")
            return True
        except Exception as e:
            print("  attempt %d/5 failed: %s" % (attempt, e))
            time.sleep(1)
    return False


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    strict = "--strict" in sys.argv[1:]
    if len(args) != 1:
        sys.exit("usage: python3 map_entities_dump.py <raw-mcp-result-file> [--strict]")

    d = json.load(open(args[0], encoding="utf-8"))
    records = d.get("records", d if isinstance(d, list) else [])

    prev = {}
    if os.path.exists(OUT):
        prev = {e["id"]: e for e in json.load(open(OUT, encoding="utf-8"))}

    rows, carried = [], {k: 0 for k in CARRYABLE}
    for r in records:
        cells = r.get("cellValuesByFieldId", r.get("fields", {}))
        row = {"id": r["id"], "name": "", "type": "", "desc": "",
               "synonyms": "", "studies": [], "desc_beginner": ""}
        for fid, key in MAP.items():
            if fid in cells:
                row[key] = unwrap(cells[fid])
        if not strict:
            old = prev.get(row["id"])
            if old:
                for key in CARRYABLE:
                    if not row[key] and old.get(key):
                        row[key] = old[key]
                        carried[key] += 1
        if not row["name"]:
            sys.exit("ABORT: record %s has no Entity_Name -- refusing to bake a "
                     "nameless entity." % row["id"])
        rows.append({k: row[k] for k in KEYS})

    if not rows:
        sys.exit("ABORT: dump contained no records -- nothing written.")

    shapes = {tuple(sorted(r.keys())) for r in rows}
    if len(shapes) != 1 or sorted(KEYS) != sorted(shapes.pop()):
        sys.exit("ABORT: key shape drift -- expected %s" % KEYS)

    dupes = {r["id"] for r in rows if sum(1 for x in rows if x["id"] == r["id"]) > 1}
    if dupes:
        sys.exit("ABORT: duplicate record ids in dump: %s" % sorted(dupes))

    # Airtable/MCP default order == record-id order, which is what the existing
    # baked file uses. Keep it: the Entity Browser does its own sorting, and a
    # reorder here would churn the whole 700KB index.html diff for nothing.
    rows.sort(key=lambda r: r["id"])

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    if not write_verified(OUT, json.dumps(rows, ensure_ascii=False)):
        sys.exit("ABORT: could not write entities_baked.json")

    print("entities_baked.json: %d entities (was %d)" % (len(rows), len(prev)))
    print("  carried forward: desc=%d, desc_beginner=%d%s"
          % (carried["desc"], carried["desc_beginner"],
             "  [--strict: carry-forward disabled]" if strict else ""))
    missing_b = sum(1 for r in rows if not r["desc_beginner"])
    no_studies = sum(1 for r in rows if not r["studies"])
    print("  without Description_Beginner: %d (page falls back to desc)" % missing_b)
    print("  without linked studies: %d" % no_studies)


if __name__ == "__main__":
    main()
