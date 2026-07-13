#!/usr/bin/env python3
"""
map_studies_dump.py -- convert a raw Airtable MCP list_records_for_table result
(the {records:[{id, cellValuesByFieldId:{fldXXXX: value}}], metadata} shape) for
the Studies table into atlas_data/studies_baked.json, the flat key shape
bake_from_mcp.py expects (matching the field mapping sync_airtable.py uses).

Usage:
    python3 map_studies_dump.py <path-to-raw-mcp-result.json or .txt>

The raw file is whatever list_records_for_table returned -- either the direct
tool result (if small) saved to a file, or the auto-saved tool-results file the
MCP wrapper writes when a result is too large for context (>~600KB). Either way
it's the same JSON shape.
"""
import sys, os, json

MAP = {
    'fldnmqtOHZ0luHRiI': 'sid',
    'fld6QJ2apz6exanv3': 'title',
    'fld789JOK2CZfOFMF': 'authors',
    'fldr4Y3f7UBDjgf9m': 'year',
    'fldeaAeolBZJ3clDq': 'journal',
    'fldrA91CoCz55saM1': 'category',
    'fldVv6X2fO2isC57l': 'model',
    'fldGuPFKa9vjthWRW': 'finding',
    'fld4mOmLgEYFA4mYE': 'tier',
    'fldlsktpNFL3Dt5tj': 'pyramid',
    'fldgxdypgVYKM0l1e': 'peer',
    'fldpLul0CsatnyUuo': 'doi',
    'fldJLD0FAgqKVp6tZ': 'abstract',
    'fldDlRPeV8PbKxh7y': 'ai_intervention',
    'fldm6p7U6VWzSTcEY': 'ai_target',
    'fld9TFn1dlFKdEZD0': 'ai_species',
    'fldtDNasqhy7uT3dw': 'ai_effect',
}

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "atlas_data", "studies_baked.json")


def unwrap(v):
    if isinstance(v, dict) and 'name' in v:
        return v['name']
    if isinstance(v, list):
        return ', '.join(unwrap(x) for x in v)
    return v if v is not None else ''


def main():
    if len(sys.argv) != 2:
        sys.exit("usage: python3 map_studies_dump.py <raw-mcp-result-file>")
    d = json.load(open(sys.argv[1], encoding="utf-8"))
    records = d["records"]
    out = []
    for r in records:
        row = {"id": r["id"]}
        cv = r.get("cellValuesByFieldId", {})
        for fid, key in MAP.items():
            row[key] = unwrap(cv.get(fid, ""))
        out.append(row)
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    content = json.dumps(out, ensure_ascii=False)
    expected_len = len(content.encode("utf-8"))
    last_err = None
    for attempt in range(1, 6):
        tmp = OUT + ".tmp%d" % os.getpid()
        try:
            with open(tmp, "w", encoding="utf-8") as f:
                f.write(content)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp, OUT)
            with open(OUT, encoding="utf-8") as f:
                final = f.read()
            if len(final.encode("utf-8")) != expected_len:
                raise RuntimeError("write verification failed: expected %d bytes, found %d" % (
                    expected_len, len(final.encode("utf-8"))))
            last_err = None
            break
        except Exception as e:
            last_err = e
            print("  attempt %d/5 failed: %s" % (attempt, e))
    if last_err is not None:
        sys.exit("ABORT: %s write verification failed after retries: %s -- do not proceed to bake/deploy" % (OUT, last_err))
    print("wrote %d studies to %s (source total: %s)" % (
        len(out), OUT, d.get("metadata", {}).get("totalRecordCount")))


if __name__ == "__main__":
    main()
