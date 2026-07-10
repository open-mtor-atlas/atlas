#!/usr/bin/env python3
"""
bake_from_mcp.py -- rewrite the ATLAS_STUDIES / ATLAS_GAPS / ATLAS_EVENTS constants
in index.html from local JSON dumps (atlas_data/studies_baked.json,
atlas_data/gaps_baked.json, atlas_data/events_baked.json).

Why this exists instead of sync_airtable.py: this sandbox's network policy blocks
direct HTTPS calls to api.airtable.com (only a curated allowlist of hosts like
github.com/pypi.org/npmjs.org is reachable). The already-authorized Airtable MCP
connector can still read the base, so the scheduled task fetches records via MCP
tool calls, dumps them to the small JSON files below, and this script does the
same regex-patch + timestamp-stamp job sync_airtable.py does -- just sourced
locally instead of hitting the API itself. No AIRTABLE_TOKEN needed.

Either JSON file may be absent -- that constant is simply left untouched.

    python3 bake_from_mcp.py
"""
import os, json, re, datetime

HERE = os.path.dirname(os.path.abspath(__file__))
HTML = os.path.join(HERE, "index.html")
STUDIES_JSON = os.path.join(HERE, "atlas_data", "studies_baked.json")
GAPS_JSON = os.path.join(HERE, "atlas_data", "gaps_baked.json")
EVENTS_JSON = os.path.join(HERE, "atlas_data", "events_baked.json")


def main():
    h = open(HTML, encoding="utf-8").read()
    changed = False

    if os.path.exists(STUDIES_JSON):
        studies = json.load(open(STUDIES_JSON, encoding="utf-8"))
        js = "const ATLAS_STUDIES = " + json.dumps(studies, ensure_ascii=False) + ";"
        # IMPORTANT: pass a lambda, not the raw string, as the replacement. re.sub
        # treats a plain string replacement as a template and decodes backslash
        # escapes like \n into real control characters, corrupting embedded JSON
        # newlines. A callable replacement is used verbatim -- no escape processing.
        # ANCHOR to the known next declaration (not a bare non-greedy \];) so a
        # literal "];" inside some study's abstract/finding text can't truncate
        # the match early and strand the rest of the old array as orphaned text.
        new_h, c1 = re.subn(
            r"const ATLAS_STUDIES = \[.*?\];\n\nconst ATLAS_ENTITIES",
            lambda m: js + "\n\nconst ATLAS_ENTITIES",
            h, count=1, flags=re.S,
        )
        if c1:
            if new_h != h:
                changed = True
            h = new_h
            print("ATLAS_STUDIES: updated (%d records)" % len(studies))
        else:
            print("ATLAS_STUDIES: NOT FOUND in index.html (pattern mismatch)")
    else:
        print("ATLAS_STUDIES: no studies_baked.json, leaving untouched")

    if os.path.exists(GAPS_JSON):
        gaps = json.load(open(GAPS_JSON, encoding="utf-8"))
        js = "const ATLAS_GAPS = " + json.dumps(gaps, ensure_ascii=False) + ";"
        new_h, c2 = re.subn(
            r"const ATLAS_GAPS = \[.*?\];\n(?=const ATLAS_FINDINGS)",
            lambda m: js + "\n",
            h, count=1, flags=re.S,
        )
        if c2:
            if new_h != h:
                changed = True
            h = new_h
            print("ATLAS_GAPS: updated (%d records)" % len(gaps))
        else:
            print("ATLAS_GAPS: NOT FOUND in index.html (pattern mismatch)")
    else:
        print("ATLAS_GAPS: no gaps_baked.json, leaving untouched")

    if os.path.exists(EVENTS_JSON):
        events = json.load(open(EVENTS_JSON, encoding="utf-8"))
        js = "const ATLAS_EVENTS = " + json.dumps(events, ensure_ascii=False) + ";"
        # ANCHOR to the known next declaration (the goAuthor() function that
        # immediately follows in the page's <script>), same defensive reasoning
        # as ATLAS_STUDIES above -- a literal "];" inside a desc/mtor/speakers
        # string