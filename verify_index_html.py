#!/usr/bin/env python3
"""Verify index.html looks complete and non-truncated. Used by deploy.bat as a
safety gate before committing/pushing -- exits non-zero (and prints why) if the
file doesn't end with </html> or its embedded ATLAS_STUDIES/ATLAS_EVENTS JSON
doesn't parse. This exists because this repo's OneDrive-synced folder has
repeatedly truncated large writes to index.html mid-file (2026-07-13 incident:
commit 11fc84f went live missing its closing </script></body></html> and the
site broke), and deploy.bat had no way to catch that before pushing.

Usage: python verify_index_html.py [path-to-index.html]  (defaults to ./index.html)
Exit 0 = looks good. Exit 1 = looks corrupted, do not commit/push.
"""
import sys, os, re, json

path = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(os.path.abspath(__file__)), "index.html")

h = open(path, encoding="utf-8").read()
problems = []

if not h.rstrip().endswith("</html>"):
    problems.append("file does not end with </html> (tail: %r)" % h[-100:])

m = re.search(r"const ATLAS_STUDIES = (\[.*?\]);\n\nconst ATLAS_ENTITIES", h, re.S)
if not m:
    problems.append("ATLAS_STUDIES block not found / not properly closed")
else:
    try:
        studies = json.loads(m.group(1))
        if len(studies) < 50:
            problems.append("ATLAS_STUDIES parsed but only has %d records (expected 200+)" % len(studies))
    except Exception as e:
        problems.append("ATLAS_STUDIES did not parse as JSON: %s" % e)

m2 = re.search(r"const ATLAS_EVENTS = (\[.*?\]);\n\nfunction goAuthor", h, re.S)
if not m2:
    problems.append("ATLAS_EVENTS block not found / not properly closed")
else:
    try:
        json.loads(m2.group(1))
    except Exception as e:
        problems.append("ATLAS_EVENTS did not parse as JSON: %s" % e)

if problems:
    print("INDEX.HTML VERIFICATION FAILED (%s):" % path)
    for p in problems:
        print("  - " + p)
    sys.exit(1)
else:
    print("index.html verification OK (%s, %d bytes)" % (path, len(h.encode("utf-8"))))
    sys.exit(0)
