#!/usr/bin/env python3
"""
wire_conflicting_evidence_2026-09-04.py

Makes conflicting evidence a real field end to end, instead of a dict hardcoded
in the build script.

Background. Conflicting_Studies now exists on the Airtable Relations table and
carries ZID2009 on 4EBP1-MITO and MAN2021 on EVE-IMMUNE. But sync_airtable.py
does not read the Relations table at all -- it writes only ATLAS_STUDIES,
ATLAS_ENTITIES and ATLAS_GAPS -- so nothing from that field reaches the site.
The pathway's actual source of truth is the ATLAS_EDGES array inside index.html,
which build_pathway_model.py reads via read_atlas_array().

This script closes the last two links of that chain:

  A. index.html -- adds a "cf" (conflicting) key to the ATLAS_EDGES entries that
     have one, alongside the existing "st" (supporting) key. Same shape, so
     anything that already understands "st" needs no special case.

  B. build_pathway_model.py -- evidence.conflicting now reads e.get("cf") first
     and falls back to the CONFLICTING dict added on 2026-09-04. The dict stays
     as a safety net but is no longer the mechanism; once every edge carries
     "cf" it can be deleted.

What is still missing, deliberately: Airtable -> ATLAS_EDGES. That link does not
exist for ANY field on the Relations table, not just this one, which is why
edits made there on 2026-08-30 and 2026-09-04 had to be applied to index.html
separately. Writing a Relations sync is a larger, riskier change (it would
overwrite hand-maintained edge text) and belongs in its own reviewed pass.
Until then, Relations is the curator's record and ATLAS_EDGES is what ships.

Run from the repo root, after apply_audit_fixes_2026-09-04.py:

    py wire_conflicting_evidence_2026-09-04.py --dry-run
    py wire_conflicting_evidence_2026-09-04.py
    py build_pathway_model.py
    py verify_atlas_build.py

Standard library only. Idempotent.
"""
import json, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
HTML = os.path.join(HERE, "index.html")
BUILD = os.path.join(HERE, "build_pathway_model.py")
DRY = "--dry-run" in sys.argv

# Mirrors Conflicting_Studies on the Airtable Relations table as of 2026-09-04.
# Keep in step with it until a Relations sync exists.
CONFLICTING = {
    # Title: "...4E-BP extends lifespan upon dietary restriction BY ENHANCING
    # mitochondrial activity in Drosophila" -- opposite sign to this edge, which
    # is scoped to mammalian cells (MOR2013).
    "4EBP1-MITO": ["ZID2009"],
    # Phase 3 arm found no reduction in clinically symptomatic respiratory
    # illness (26% vs 25%, OR 1.07, p=0.65) on an edge whose sign is "activates".
    # MAN2021 stays in supporting too: its phase 2a/2b arm is part of that case.
    "EVE-IMMUNE": ["MAN2021"],
}

OLD_BUILD_1 = '"conflicting": CONFLICTING.get(e["id"], []),'
NEW_BUILD_1 = ('"conflicting": (e.get("cf") or CONFLICTING.get(e["id"], [])),'
               '  # cf comes from ATLAS_EDGES; dict is the fallback')
OLD_BUILD_2 = '"supporting": list(sids), "conflicting": CONFLICTING.get(eid, [])'
NEW_BUILD_2 = '"supporting": list(sids), "conflicting": CONFLICTING.get(eid, [])'


def patch_html(src):
    changed = []
    i = src.find("const ATLAS_EDGES = [")
    if i < 0:
        sys.exit("ABORT: ATLAS_EDGES not found in index.html.")
    head = "const ATLAS_EDGES = "
    seg = src[i + len(head):]
    end = seg.find("];") + 1
    edges = json.loads(seg[:end])

    known = {e.get("id") for e in edges}
    for eid in CONFLICTING:
        if eid not in known:
            sys.exit("ABORT: %s is not an edge in ATLAS_EDGES." % eid)

    dirty = False
    for e in edges:
        want = CONFLICTING.get(e.get("id"))
        if want and e.get("cf") != want:
            e["cf"] = want
            dirty = True
            changed.append("ATLAS_EDGES %s.cf = %s" % (e["id"], want))
        # A study must not sit on both sides of the same edge unless that is
        # deliberate; EVE-IMMUNE is, because different arms of one publication
        # point different ways. Report rather than decide.
        both = set(e.get("cf") or []) & set(e.get("st") or [])
        if both:
            changed.append("   note: %s on BOTH sides of %s (intended for EVE-IMMUNE)"
                           % (", ".join(sorted(both)), e["id"]))

    if not dirty:
        return src, changed
    new = json.dumps(edges, ensure_ascii=False, separators=(",", ":"))
    return src[:i + len(head)] + new + src[i + len(head) + end:], changed


def main():
    for p in (HTML, BUILD):
        if not os.path.exists(p):
            sys.exit("ABORT: %s not found -- run from the repo root." % p)

    b = open(BUILD, encoding="utf-8").read()
    bch = []
    if "CONFLICTING" not in b:
        sys.exit("ABORT: build_pathway_model.py has no CONFLICTING dict.\n"
                 "       Run apply_audit_fixes_2026-09-04.py first.")
    if 'e.get("cf")' not in b:
        if OLD_BUILD_1 not in b:
            sys.exit("ABORT: could not find the conflicting assignment in "
                     "build_pathway_model.py; patch by hand.")
        b = b.replace(OLD_BUILD_1, NEW_BUILD_1, 1)
        bch.append('evidence.conflicting now prefers ATLAS_EDGES "cf"')

    h = open(HTML, encoding="utf-8").read()
    h2, hch = patch_html(h)

    print("build_pathway_model.py:")
    for c in bch:
        print("   - " + c)
    if not bch:
        print("   - already wired")
    print("index.html:")
    for c in hch:
        print("   - " + c)
    if not hch:
        print("   - cf keys already current")

    if not bch and h2 == h:
        return

    try:
        compile(b, BUILD, "exec")
    except SyntaxError as e:
        sys.exit("ABORT: patched build_pathway_model.py does not compile: %s" % e)
    if not h2.rstrip().endswith("</html>"):
        sys.exit("ABORT: index.html no longer ends in </html>")

    if DRY:
        print("\n--dry-run: nothing written.")
        return
    for path, content in ((BUILD, b), (HTML, h2)):
        tmp = path + ".tmp"
        open(tmp, "w", encoding="utf-8").write(content)
        if open(tmp, encoding="utf-8").read() != content:
            sys.exit("ABORT: read-back mismatch on %s" % path)
        os.replace(tmp, path)
    print("\nWritten and verified.")


if __name__ == "__main__":
    main()
