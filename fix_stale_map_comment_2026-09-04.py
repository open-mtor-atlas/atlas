#!/usr/bin/env python3
"""
fix_stale_map_comment_2026-09-04.py

After delete_dead_map_arrays_2026-09-04.py removed MAP_CORE_EDGES,
MAP_PERIPH_EDGES and MAP_BANDS, the explanatory comment above renderFullMap()
still named them. Two problems with leaving it: the comment is now factually
wrong about what the file contains, and R11 greps for those names anywhere in
index.html, so it kept reporting deleted arrays as still shipped.

Rewrites the comment to describe what is actually there, including why the node
coordinate table was kept while the edge and band tables were not.

Run from the repo root, after delete_dead_map_arrays_2026-09-04.py:

    py fix_stale_map_comment_2026-09-04.py
    py validate_claims.py

Idempotent. Standard library only.
"""
import os, sys

HTML = os.path.join(os.path.dirname(os.path.abspath(__file__)), "index.html")

OLD = """/* renderFullMap() used to draw its own hand-tuned SVG from MAP_NODES/
   MAP_CORE_EDGES/MAP_BANDS -- a second, independently-maintained copy of
   the pathway that drifted out of sync with pathway/model.json (41 of 111
   corpus entities had no node here at all, incl. cGAS-STING pathway and
   FoxO). Per build_pathway_model.py's own stated goal of one source of
   truth, this pane now delegates to the Pathway & Mechanism explorer --
   the one place that actually renders from model.json -- instead of
   maintaining a second renderer. See pathway/pathway.js: PathwayApp.focusNode(). */"""

NEW = """/* renderFullMap() used to draw its own hand-tuned SVG from a second,
   independently-maintained copy of the pathway that drifted out of sync with
   pathway/model.json (41 of 111 corpus entities had no node here at all, incl.
   cGAS-STING pathway and FoxO), and whose edge table carried three wrong signs.
   Per build_pathway_model.py's own stated goal of one source of truth, this
   pane now delegates to the Pathway & Mechanism explorer -- the one place that
   actually renders from model.json -- instead of maintaining a second renderer.
   Those edge and band arrays were deleted on 2026-09-04; the node coordinate
   table is retained because focusSelectedNode() still names it.
   See pathway/pathway.js: PathwayApp.focusNode(). */"""


def main():
    if not os.path.exists(HTML):
        sys.exit("ABORT: index.html not found -- run from the repo root.")
    h = open(HTML, encoding="utf-8").read()
    if NEW in h:
        print("comment already current, nothing to do")
        return
    n = h.count(OLD)
    if n != 1:
        sys.exit("ABORT: expected exactly 1 copy of the old comment, found %d.\n"
                 "       Edit it by hand." % n)
    h = h.replace(OLD, NEW, 1)
    if not h.rstrip().endswith("</html>"):
        sys.exit("ABORT: output does not end in </html>")
    tmp = HTML + ".tmp"
    open(tmp, "w", encoding="utf-8").write(h)
    if open(tmp, encoding="utf-8").read() != h:
        sys.exit("ABORT: read-back mismatch, index.html untouched.")
    os.replace(tmp, HTML)
    print("comment rewritten; R11 should no longer list MAP_CORE_EDGES or MAP_BANDS")


if __name__ == "__main__":
    main()
