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

# 2026-09-07 (SEO P0 Ukol 3b): ATLAS_STUDIES is no longer inlined here -- the
# homepage fetches it at runtime from atlas_data/studies_baked.json instead
# (795 KB removed from every page load; the file was already this repo's
# independent source of truth, byte-verified identical to the old inline
# copy before the switch). Two checks replace the old single one: (a) the
# async-fetch scaffolding itself wasn't corrupted/reverted -- `let
# ATLAS_STUDIES = []` plus a fetch() of the right file must both still be
# present; (b) the actual data file is intact and has a plausible record
# count, since that's the real integrity question now, not anything inside
# this HTML file.
if "let ATLAS_STUDIES = []" not in h and "let ATLAS_STUDIES=[]" not in h:
    problems.append("ATLAS_STUDIES no longer declared as `let ATLAS_STUDIES = []` "
                     "(async-fetch scaffolding missing or reverted)")
if "atlas_data/studies_baked.json" not in h:
    problems.append("no fetch() of atlas_data/studies_baked.json found -- "
                     "ATLAS_STUDIES would never get populated in a browser")
sbp = os.path.join(os.path.dirname(os.path.abspath(path)), "atlas_data", "studies_baked.json")
if not os.path.exists(sbp):
    problems.append("atlas_data/studies_baked.json missing -- the homepage's "
                     "runtime fetch would fail")
else:
    try:
        studies = json.load(open(sbp, encoding="utf-8"))
        if len(studies) < 50:
            problems.append("atlas_data/studies_baked.json parsed but only has %d "
                             "records (expected 200+)" % len(studies))
    except Exception as e:
        problems.append("atlas_data/studies_baked.json did not parse as JSON: %s" % e)

m2 = re.search(r"const ATLAS_EVENTS = (\[.*?\]);\n\nfunction goAuthor", h, re.S)
if not m2:
    problems.append("ATLAS_EVENTS block not found / not properly closed")
else:
    try:
        json.loads(m2.group(1))
    except Exception as e:
        problems.append("ATLAS_EVENTS did not parse as JSON: %s" % e)

# --- Checks below only apply to the real index.html, not to the deploy backup
# copy deploy.bat also runs this script against: they compare index.html to
# sibling build products, which the backup is not expected to match.
if os.path.basename(path) == "index.html":
    root = os.path.dirname(os.path.abspath(path))

    # 1. model.json must not be older than the data in index.html. A sync
    #    without a rebuild shipped a two-day-old pathway model on 2026-09-04:
    #    ATLAS_STUDIES was current while pathway/model.json was not, and the
    #    site showed evidence tiers derived from the older corpus.
    mp = os.path.join(root, "pathway", "model.json")
    mu = re.search(r'const ATLAS_UPDATED = "([^"]*)"', h)
    if os.path.exists(mp) and mu:
        try:
            gen = json.load(open(mp, encoding="utf-8"))["meta"]["generated"][:10]
            upd = mu.group(1)[:10]
            if gen < upd:
                problems.append(
                    "pathway/model.json generated %s but index.html synced %s "
                    "- run build_pathway_model.py" % (gen, upd))
        except Exception as e:
            problems.append("pathway/model.json unreadable: %s" % e)

    # 2. The baked count spans are what a crawler or a no-JS reader sees;
    #    JS overwrites them for everyone else, so they can be wrong for a long
    #    time without anyone noticing. stamp_updated.py stamps them - this is
    #    the assertion that the stamping actually ran.
    def _len_of(name):
        mm = re.search(r"const %s = (\[.*?\]);" % name, h, re.S)
        try:
            return len(json.loads(mm.group(1))) if mm else None
        except Exception:
            return None

    def _studies_baked_len():
        try:
            return len(json.load(open(sbp, encoding="utf-8")))
        except Exception:
            return None

    n_st = _studies_baked_len()
    expected = {"ipyStudyCount": n_st, "atlasStatStudies": n_st,
                "shStudyCount": n_st, "atlasStatEntities": _len_of("ATLAS_ENTITIES")}
    if os.path.exists(mp):
        try:
            _pm = json.load(open(mp, encoding="utf-8"))
            expected["shNodeCount"] = len(_pm["nodes"])
            expected["shEdgeCount"] = len(_pm["interactions"])
            expected["shRouteCount"] = len(_pm["routes"])
        except Exception:
            pass
    for sid, want in expected.items():
        if want is None:
            continue
        for mm in re.finditer(r'<span id="%s"[^>]*>([^<]*)</span>' % sid, h):
            got = mm.group(1).strip()
            if got != str(want):
                problems.append("baked count #%s reads %s, data says %d "
                                "- run stamp_updated.py" % (sid, got or "empty", want))

    # 3. Conflicting evidence must survive the ATLAS_EDGES -> model.json build.
    #    build_pathway_model.py hardcoded evidence.conflicting = [] for all 119
    #    interactions until 2026-09-04, silently discarding the one thing this
    #    Atlas claims to model that others do not. A count round-trip catches a
    #    regression without asserting any particular study.
    i = h.find("const ATLAS_EDGES = [")
    if i >= 0 and os.path.exists(mp):
        try:
            seg = h[i + len("const ATLAS_EDGES = "):]
            edges = json.loads(seg[:seg.find("];") + 1])
            n_cf = sum(1 for e in edges if e.get("cf"))
            _pm = json.load(open(mp, encoding="utf-8"))
            n_model = sum(1 for x in _pm["interactions"]
                          if (x.get("evidence") or {}).get("conflicting"))
            if n_cf and n_model < n_cf:
                problems.append(
                    "%d edge(s) carry conflicting studies in ATLAS_EDGES but only "
                    "%d survive into model.json - run build_pathway_model.py"
                    % (n_cf, n_model))
        except Exception as e:
            problems.append("could not round-trip conflicting evidence: %s" % e)

if problems:
    print("INDEX.HTML VERIFICATION FAILED (%s):" % path)
    for p in problems:
        print("  - " + p)
    sys.exit(1)
else:
    print("index.html verification OK (%s, %d bytes)" % (path, len(h.encode("utf-8"))))
    sys.exit(0)
