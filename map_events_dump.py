#!/usr/bin/env python3
"""
map_events_dump.py -- convert a raw Airtable MCP list_records_for_table result
(the {records:[{id, cellValuesByFieldId:{fldXXXX: value}}], metadata} shape) for
the Events table into atlas_data/events_baked.json, the flat key shape
bake_from_mcp.py expects for the ATLAS_EVENTS constant in index.html.

Usage:
    python3 map_events_dump.py <path-to-raw-mcp-result.json or .txt>

The raw file is whatever list_records_for_table returned for the Events table
(tbl142mcSZeCMay7o in base appt2U6ObDHUcRlrj) -- either the direct tool result
(if small) saved to a file, or the auto-saved tool-results file the MCP wrapper
writes when a result is too large for context. Either way it's the same JSON
shape. Fetch with no fieldIds filter (or all fields) so every column below is
present.
"""
import sys, os, json, datetime

MAP = {
    'fld00aPAERi7S6vnq': 'name',
    'fld3PEpnlNAFut1WC': 'desc',
    'fld4AETssrVpT9L4O': 'mtor',
    'fldQ9D9XPnN6IhTXD': 'venue',
    'fldRh4PQTxRNcJYPB': 'series',
    'fldWWbAI9kOBm3YR7': 'country',
    'fldor5lmxHHkVnvvE': 'start',
    'fldrv79YdQ5wYi7CC': 'organizers',
    'fldtNurUE2HuyDjAD': 'city',
    'fldux5k83IcvZtAbn': 'speakers',
    'fldwiECQFBLe9Dqaf': 'url',
    'fldOlynNgRfTTgTwn': 'end',
}
AUTHORS_FIELD = 'fldKtmZPlTdpxiWYU'  # Linked_Authors, multipleRecordLinks

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "atlas_data", "events_baked.json")

MONTHS = ["", "Jan", "Feb", "Mar", "Apr", "May", "Jun",
          "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def unwrap(v):
    """singleSelect -> plain name string; other scalars pass through."""
    if isinstance(v, dict) and 'name' in v:
        return v['name']
    if isinstance(v, list):
        return ', '.join(unwrap(x) for x in v)
    return v if v is not None else ''


def unwrap_authors(v):
    """multipleRecordLinks -> list of linked record display names."""
    if not v:
        return []
    if isinstance(v, list):
        out = []
        for x in v:
            if isinstance(x, dict) and 'name' in x:
                out.append(x['name'])
            elif isinstance(x, str):
                out.append(x)
        return out
    return []


def fmt_date_range(start, end):
    """Build a human 'dates' string like existing entries, e.g.
    '24–27 Jun 2026', '2–3 Dec 2026', '25 Aug – 4 Sep 2026',
    '12 Dec 2026 – 3 Jan 2027'. Falls back to '' if dates unparseable."""
    def parse(d):
        try:
            return datetime.date.fromisoformat(d)
        except (TypeError, ValueError):
            return None

    s, e = parse(start), parse(end)
    if not s:
        return ''
    if not e or e == s:
        return "%d %s %d" % (s.day, MONTHS[s.month], s.year)
    if s.year == e.year and s.month == e.month:
        return "%d–%d %s %d" % (s.day, e.day, MONTHS[s.month], s.year)
    if s.year == e.year:
        return "%d %s – %d %s %d" % (s.day, MONTHS[s.month], e.day, MONTHS[e.month], s.year)
    return "%d %s %d – %d %s %d" % (s.day, MONTHS[s.month], s.year, e.day, MONTHS[e.month], e.year)


def main():
    if len(sys.argv) != 2:
        sys.exit("usage: python3 map_events_dump.py <raw-mcp-result-file>")
    d = json.load(open(sys.argv[1], encoding="utf-8"))
    records = d["records"]
    out = []
    for r in records:
        cv = r.get("cellValuesByFieldId", {})
        row = {}
        for fid, key in MAP.items():
            row[key] = unwrap(cv.get(fid, ""))
        row["authors"] = unwrap_authors(cv.get(AUTHORS_FIELD))
        row["dates"] = fmt_date_range(row.get("start"), row.get("end"))
        # key order matches the hand-authored entries already in index.html
        ordered = {k: row[k] for k in
                   ["name", "series", "start", "end", "dates", "city", "country",
                    "venue", "url", "desc", "mtor", "organizers", "speakers", "authors"]}
        out.append(ordered)
    # stable, chronological-ish order: by start date (blank dates sort last)
    out.sort(key=lambda e: e["start"] or "9999-99-99")
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False)
    print("wrote %d events to %s (source total: %s)" % (
        len(out), OUT, d.get("metadata", {}).get("totalRecordCount")))


if __name__ == "__main__":
    main()
