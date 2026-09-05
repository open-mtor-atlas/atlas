#!/usr/bin/env python3
"""
consolidate_verifiers_2026-09-05.py

Folds the three checks worth keeping out of verify_atlas_build.py into the two
gates deploy.bat already runs, and deletes the rest.

Why
---
verify_atlas_build.py was written on 2026-09-04 without noticing that deploy.bat
already had a verification stage. It ended up a second pipeline beside the first
-- which is the exact class of problem the audits kept finding in the Atlas
itself (two pathway layers, two count sources, out/ beside the repo root).

Comparing the three, by check:

  ALREADY COVERED, dropped
    </html> present, ATLAS_STUDIES/ATLAS_EVENTS parse   -> verify_index_html.py
    PRERENDER markers exist and are non-trivial         -> verify_prerender.py
    every ATLAS_GAPS id appears in the prerender        -> verify_prerender.py

  WORTH KEEPING, moved
    1. prerender carries the current gap TEXT, not just the ids
       -> verify_prerender.py. Its existing check matches ids, so a block whose
          H1..H10 headings are right but whose bodies are two days old passes.
          That is not hypothetical: on 2026-09-05 the live prerender and
          ATLAS_GAPS agreed on ids while H4, H5, H9 and H10 carried superseded
          text, and nothing caught it.
    2. model.json is not older than index.html's ATLAS_UPDATED
       -> verify_index_html.py. Catches a sync without a rebuild, which shipped
          a two-day-old pathway model on 2026-09-04.
    3. baked count spans agree with the data they summarise
       -> verify_index_html.py. stamp_updated.py now stamps them, so this is the
          assertion that the stamping actually ran.

  DROPPED as one-off acceptance tests
    "superseded Open Questions text absent", "expected corrections present",
    "4EBP1-MITO carries ZID2009" -- these assert the specific content of the
    2026-09 audit. They pass forever and rot into noise; the durable versions
    are validate_claims.py's R8/R12 (absolute-claim regression) and R13 (a study
    on the supporting side that contradicts the edge). The one genuinely general
    part -- that conflicting evidence survives the ATLAS_EDGES -> model.json
    build -- is kept as a round-trip count.
    "PMID coverage <= 29" is dropped outright: the threshold was the number that
    happened to be true the day it was written.

Run from the repo root:

    py consolidate_verifiers_2026-09-05.py --dry-run
    py consolidate_verifiers_2026-09-05.py
    py verify_index_html.py index.html
    py verify_prerender.py

Idempotent. Standard library only.
"""
import os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
DRY = "--dry-run" in sys.argv

# ---------------------------------------------------------- verify_prerender ---
P_ANCHOR = """    emiss = [e["name"] for e in arr("ATLAS_EVENTS")"""

P_NEW = '''    # Text, ne jen ID. Puvodni kontrola porovnava seznam id -- blok, ktery ma
    # spravne nadpisy H1..H10, ale dva dny stary obsah, ji projde. Presne to se
    # stalo 5. 9. 2026: prerender a ATLAS_GAPS se shodovaly na id, zatimco H4,
    # H5, H9 a H10 nesly prekonany text, a nic to nezachytilo. Porovnava se
    # zacatek Evidence_Basis, protoze ten se pri kazde vecne oprave meni.
    stale = []
    for g in arr("ATLAS_GAPS"):
        head = (g.get("basis") or "")[:60]
        if head and head not in qbody:
            stale.append(g.get("id"))
    if stale:
        print("CHYBA: %d hypotez ma v prerenderu ZASTARALY text (id sedi, obsah ne): %s"
              % (len(stale), stale))
        print("       spust: node prerender_tabs.js  (nebo fix_findings_and_prerender.py)")
        ok = False

    emiss = [e["name"] for e in arr("ATLAS_EVENTS")'''

# --------------------------------------------------------- verify_index_html ---
I_ANCHOR = """if problems:
    print("INDEX.HTML VERIFICATION FAILED (%s):" % path)"""

I_NEW = '''# --- Checks below only apply to the real index.html, not to the deploy backup
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
        mm = re.search(r"const %s = (\\[.*?\\]);" % name, h, re.S)
        try:
            return len(json.loads(mm.group(1))) if mm else None
        except Exception:
            return None

    n_st = _len_of("ATLAS_STUDIES")
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
    print("INDEX.HTML VERIFICATION FAILED (%s):" % path)'''


def patch(path, old, new, label):
    if not os.path.exists(path):
        sys.exit("ABORT: %s not found -- run from the repo root." % path)
    src = open(path, encoding="utf-8").read()
    if new.strip().splitlines()[0] in src:
        print("   - %s: already applied" % label)
        return
    if src.count(old) != 1:
        sys.exit("ABORT: %s -- expected 1 anchor, found %d. Patch by hand."
                 % (label, src.count(old)))
    src = src.replace(old, new, 1)
    try:
        compile(src, path, "exec")
    except SyntaxError as e:
        sys.exit("ABORT: patched %s does not compile: %s" % (label, e))
    if not DRY:
        tmp = path + ".tmp"
        open(tmp, "w", encoding="utf-8").write(src)
        os.replace(tmp, path)
    print("   - %s: patched" % label)


def main():
    print("Folding the durable checks into the existing gates")
    patch(os.path.join(HERE, "verify_prerender.py"), P_ANCHOR, P_NEW,
          "verify_prerender.py (gap text, not just ids)")
    patch(os.path.join(HERE, "verify_index_html.py"), I_ANCHOR, I_NEW,
          "verify_index_html.py (model freshness, baked counts, cf round-trip)")

    ip = os.path.join(HERE, "verify_index_html.py")
    src = open(ip, encoding="utf-8").read()
    if "import sys, os, re, json" not in src and "import json" not in src:
        sys.exit("ABORT: verify_index_html.py does not import json -- patch by hand.")

    dead = os.path.join(HERE, "verify_atlas_build.py")
    if os.path.exists(dead):
        print("Removing the duplicate")
        print("   - verify_atlas_build.py: superseded, deleting")
        if not DRY:
            os.remove(dead)
    else:
        print("   - verify_atlas_build.py: already gone")

    if DRY:
        print("\n--dry-run: nothing written.")
    else:
        print("\nRun both gates now:")
        print("   py verify_index_html.py index.html")
        print("   py verify_prerender.py")
        print("\ndeploy.bat already calls both. verify_atlas_build.py was never")
        print("wired into it, so nothing else needs changing.")


if __name__ == "__main__":
    main()
