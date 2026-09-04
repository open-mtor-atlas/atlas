#!/usr/bin/env python3
"""
fix_r11_validator_2026-09-04.py

R11 currently tells you to delete ATLAS_EDGES and ATLAS_ROUTES. Doing so would
break the build: build_pathway_model.py reads both out of index.html via
read_atlas_array() in its main(). They are dead as RENDER code -- renderMechanism()
is never called and the live explorer reads pathway/model.json -- but they are the
INPUT to the model build. The rule's own comment states the render fact and draws
the wrong conclusion from it.

This patch:

  A. Removes ATLAS_EDGES and ATLAS_ROUTES from DEAD_LAYERS. What remains
     (MAP_NODES, MAP_CORE_EDGES, MAP_PERIPH_EDGES, MAP_BANDS, renderMechanism,
     mxBuildSVG, mxSetRoute) really is unreachable and safe to delete. Note that
     MAP_CORE_EDGES additionally contains three wrong signs (SAMTOR -> GATOR2,
     AKT -> PRAS40 = activate, 4E-BP1 -> Muscle = activate), so removing it is a
     correctness improvement as well as a cleanup.

  B. Adds the inverse check. If ATLAS_EDGES or ATLAS_ROUTES ever goes MISSING
     from index.html, that is an ERROR, because the next build_pathway_model.py
     run will fail. The rule now protects the build input instead of advising
     its deletion.

  C. Rewrites the comment and the fix hint so the next reader is not told the
     same wrong thing.

Run from the repo root:

    py fix_r11_validator_2026-09-04.py --dry-run
    py fix_r11_validator_2026-09-04.py
    py validate_claims.py

Standard library only. Idempotent.
"""
import os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
VC = os.path.join(HERE, "validate_claims.py")
DRY = "--dry-run" in sys.argv

OLD_DEAD = '''DEAD_LAYERS = ["MAP_NODES", "MAP_CORE_EDGES", "MAP_PERIPH_EDGES", "MAP_BANDS",
               "ATLAS_EDGES", "ATLAS_ROUTES"]
DEAD_FUNCS = ["renderMechanism", "mxBuildSVG", "mxSetRoute"]'''

NEW_DEAD = '''# Genuinely unreachable: no caller, no reader. renderFullMap() was reduced to a
# handoff button on 2026-08-06 and renderMechanism() is never called.
# MAP_CORE_EDGES also carries three wrong signs (SAMTOR->GATOR2; AKT->PRAS40 as
# "activate"; 4E-BP1->Muscle as "activate"), so deleting it fixes biology too.
DEAD_LAYERS = ["MAP_NODES", "MAP_CORE_EDGES", "MAP_PERIPH_EDGES", "MAP_BANDS"]
DEAD_FUNCS = ["renderMechanism", "mxBuildSVG", "mxSetRoute"]

# NOT dead, despite never being rendered: build_pathway_model.py reads these out
# of index.html (read_atlas_array, called from main()) and they are the input
# from which pathway/model.json is generated. Deleting them breaks the build.
# Corrected 2026-09-04, after R11 was found advising exactly that deletion.
BUILD_INPUT_ARRAYS = ["ATLAS_EDGES", "ATLAS_ROUTES"]'''

OLD_R11 = '''    # R11 -- single pathway layer. WARN, not ERROR: the legacy ATLAS_EDGES /
    # MAP_* arrays and renderMechanism()/mx*() helpers are known-dead (never
    # called; the live explorer reads pathway/model.json) and were flagged
    # for deletion by the 2026-07-29 review, but deleting ~1,100 lines from
    # this file is deliberately left as a separate, reviewed change rather
    # than folded into a content-correction pass. Flip to ERROR once they
    # are actually removed, so a reintroduction fails the build.
    present = [name for name in DEAD_LAYERS + DEAD_FUNCS
               if re.search(r"\\b" + re.escape(name) + r"\\b", h)]
    if present:
        add(findings, "WARN", "R11 dead-pathway-layer", "index.html", ", ".join(present),
            "Legacy pathway constants/functions still shipped (unrendered, but "
            "machine-readable to crawlers): %s." % ", ".join(present),
            "Delete per the 2026-07-29 review note; see pathway-model-single-source.")'''

NEW_R11 = '''    # R11 -- dead render layer. WARN, not ERROR: the MAP_* arrays and the
    # renderMechanism()/mx*() helpers are unreachable (renderFullMap() became a
    # handoff button on 2026-08-06; the live explorer reads pathway/model.json),
    # but deleting ~900 lines is a separate reviewed change, not something to
    # fold into a content pass. Flip to ERROR once they are gone, so that a
    # reintroduction fails the build.
    #
    # ATLAS_EDGES / ATLAS_ROUTES are deliberately NOT in this list. They are also
    # never rendered, but build_pathway_model.py reads them out of index.html to
    # generate pathway/model.json, so they are build input, not dead weight.
    # Until 2026-09-04 this rule listed them and told the reader to delete them,
    # which would have broken the build.
    present = [name for name in DEAD_LAYERS + DEAD_FUNCS
               if re.search(r"\\b" + re.escape(name) + r"\\b", h)]
    if present:
        add(findings, "WARN", "R11 dead-pathway-layer", "index.html", ", ".join(present),
            "Unreachable render-layer constants/functions still shipped (never "
            "called, but machine-readable to crawlers): %s. MAP_CORE_EDGES also "
            "carries three wrong signs." % ", ".join(present),
            "Safe to delete: nothing reads these. Do NOT also remove ATLAS_EDGES "
            "or ATLAS_ROUTES -- build_pathway_model.py needs them.")

    # R11b -- the inverse guard. If a build-input array goes missing, the next
    # build_pathway_model.py run raises SystemExit("missing %s in index.html").
    # Catch it here, before the build, and say why.
    gone = [name for name in BUILD_INPUT_ARRAYS
            if not re.search(r"const\\s+" + re.escape(name) + r"\\s*=", h)]
    if gone:
        add(findings, "ERROR", "R11b build-input-array-missing", "index.html", ", ".join(gone),
            "%s is missing from index.html. build_pathway_model.py reads it via "
            "read_atlas_array() and will fail, and pathway/model.json cannot be "
            "regenerated." % ", ".join(gone),
            "Restore from git history. These arrays are unrendered but they are "
            "the source of truth for the pathway model.")'''


def main():
    if not os.path.exists(VC):
        sys.exit("ABORT: validate_claims.py not found -- run from the repo root.")
    src = open(VC, encoding="utf-8").read()
    original = src
    changed = []

    if "BUILD_INPUT_ARRAYS" not in src:
        if OLD_DEAD not in src:
            sys.exit("ABORT: DEAD_LAYERS block does not match the expected text.\n"
                     "       validate_claims.py has changed; patch by hand.")
        src = src.replace(OLD_DEAD, NEW_DEAD, 1)
        changed.append("DEAD_LAYERS: removed ATLAS_EDGES, ATLAS_ROUTES; added BUILD_INPUT_ARRAYS")

    if "R11b build-input-array-missing" not in src:
        if OLD_R11 not in src:
            sys.exit("ABORT: R11 block does not match the expected text.\n"
                     "       validate_claims.py has changed; patch by hand.")
        src = src.replace(OLD_R11, NEW_R11, 1)
        changed.append("R11: rewritten; added R11b inverse guard (ERROR)")

    if not changed:
        print("validate_claims.py: already patched, nothing to do")
        return

    for c in changed:
        print("   - " + c)

    # gates
    try:
        compile(src, VC, "exec")
    except SyntaxError as e:
        sys.exit("ABORT: patched validate_claims.py does not compile: %s" % e)
    if re.search(r'DEAD_LAYERS = \[[^]]*ATLAS_EDGES', src, re.S):
        sys.exit("ABORT: ATLAS_EDGES still in DEAD_LAYERS after patch")
    if "BUILD_INPUT_ARRAYS = " not in src or "R11b" not in src:
        sys.exit("ABORT: patch incomplete")

    print("size: %d -> %d bytes" % (len(original), len(src)))
    if DRY:
        print("--dry-run: nothing written.")
        return
    tmp = VC + ".tmp"
    open(tmp, "w", encoding="utf-8").write(src)
    if open(tmp, encoding="utf-8").read() != src:
        sys.exit("ABORT: read-back mismatch, validate_claims.py untouched.")
    os.replace(tmp, VC)
    print("validate_claims.py rewritten and verified.")


if __name__ == "__main__":
    main()
