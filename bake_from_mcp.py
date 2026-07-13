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
import os, json, re, datetime, time

HERE = os.path.dirname(os.path.abspath(__file__))
HTML = os.path.join(HERE, "index.html")
STUDIES_JSON = os.path.join(HERE, "atlas_data", "studies_baked.json")
GAPS_JSON = os.path.join(HERE, "atlas_data", "gaps_baked.json")
EVENTS_JSON = os.path.join(HERE, "atlas_data", "events_baked.json")


def write_verified(path, content, expect_suffix="</html>", attempts=5):
    """Write `content` to `path` atomically (temp file + fsync + os.replace),
    then re-read the published file and verify it matches byte-for-byte and
    ends with `expect_suffix`. Retries on failure since this repo lives in a
    OneDrive-synced folder where large writes have repeatedly been silently
    truncated mid-file, by more than one write path (plain file I/O, editor
    saves) -- a single fsync'd write is not sufficient. Raises RuntimeError if
    all attempts fail, rather than leaving a truncated file for git to commit."""
    expected_len = len(content.encode("utf-8"))
    last_err = None
    for attempt in range(1, attempts + 1):
        tmp = path + ".tmp%d" % os.getpid()
        try:
            with open(tmp, "w", encoding="utf-8") as f:
                f.write(content)
                f.flush()
                os.fsync(f.fileno())
            with open(tmp, encoding="utf-8") as f:
                check = f.read()
            if len(check.encode("utf-8")) != expected_len or not check.rstrip().endswith(expect_suffix):
                raise RuntimeError(
                    "pre-publish verification failed for %s (attempt %d): wrote %d bytes, read back %d, tail=%r"
                    % (path, attempt, expected_len, len(check.encode("utf-8")), check[-80:])
                )
            os.replace(tmp, path)
            with open(path, encoding="utf-8") as f:
                final = f.read()
            if len(final.encode("utf-8")) != expected_len or not final.rstrip().endswith(expect_suffix):
                raise RuntimeError(
                    "post-publish verification failed for %s (attempt %d): expected %d bytes, found %d, tail=%r"
                    % (path, attempt, expected_len, len(final.encode("utf-8")), final[-80:])
                )
            return
        except Exception as e:
            last_err = e
            print("  write_verified: attempt %d/%d failed: %s" % (attempt, attempts, e))
            time.sleep(2)
    raise RuntimeError("write_verified: all %d attempts failed for %s: %s" % (attempts, path, last_err))


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
        # string must not be able to truncate the match early.
        new_h, c4 = re.subn(
            r"const ATLAS_EVENTS = \[.*?\];\n\nfunction goAuthor",
            lambda m: js + "\n\nfunction goAuthor",
            h, count=1, flags=re.S,
        )
        if c4:
            if new_h != h:
                changed = True
            h = new_h
            print("ATLAS_EVENTS: updated (%d records)" % len(events))
        else:
            print("ATLAS_EVENTS: NOT FOUND in index.html (pattern mismatch)")
    else:
        print("ATLAS_EVENTS: no events_baked.json, leaving untouched")

    ts = datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
    h, c3 = re.subn(r'const ATLAS_UPDATED = "[^"]*";', 'const ATLAS_UPDATED = "' + ts + '";', h, count=1)
    if c3:
        changed = True

    write_verified(HTML, h, expect_suffix="</html>")
    print("index.html rewritten and verified (last updated " + ts + ", content_changed=%s)." % changed)

    size = os.path.getsize(HTML)
    print("index.html size after write:", size, "bytes")


if __name__ == "__main__":
    main()
