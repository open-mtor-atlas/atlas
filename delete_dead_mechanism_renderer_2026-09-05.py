#!/usr/bin/env python3
"""
delete_dead_mechanism_renderer_2026-09-05.py

Finishes R11. delete_dead_map_arrays_2026-09-04.py removed the three unreferenced
MAP_* data arrays; this removes the dead renderer that used to consume them.

Deletes 18 top-level function declarations, ~13 kB:

  renderMechanism        the retired Pathway 1.0 view. Never called: its only
                         remaining mentions are inside two block comments.
  mx* (14 functions)     mxBuildSVG, mxPaint, mxSetRoute, mxSelect, mxPlayRoute,
                         mxPanelDefault, mxPanelEdge, mxNodeOpen, mxNodeW,
                         mxAnchor, mxMarkers, mxEsc, mxCurRoute, mxEdgeById.
                         Reachable only from renderMechanism or from each other.
  edgeLine, drawCoreEdge, drawPeriphEdge
                         the old hand-tuned SVG edge painters, orphaned when the
                         MAP_CORE_EDGES / MAP_PERIPH_EDGES arrays went.

NOT deleted, and why
--------------------
  MAP_NODES, mapNodeById, prepNode
        Still reachable. mapNodeById and prepNode are called from live layout
        code, and focusSelectedNode() names MAP_NODES on a path that starts at
        onTabShown(). The path stops early in practice because renderFullMap()
        no longer emits an <svg>, but "probably unreachable" is not the standard
        for deleting a symbol live code references. MAP_NODES holds layout
        coordinates, not biology, so leaving it costs nothing.
  ATLAS_EDGES, ATLAS_ROUTES
        Never rendered, but build_pathway_model.py reads them out of index.html.
        Deleting them breaks the build. R11 said otherwise until 2026-09-04.

How the dead set was established
--------------------------------
A hand-rolled brace matcher was tried first and was wrong: it reported mxEsc as
63,000 characters, having run past a regex literal containing braces. JavaScript
cannot be reliably carved up with bracket counting, so the ranges here come from
an esprima parse of the real AST, cross-checked against a textual scan. Both
methods returned the same 18 names.

Deletion is verified by re-parsing the modified script with Node before anything
is written. If it does not parse, nothing is touched.

    py delete_dead_mechanism_renderer_2026-09-05.py --dry-run
    py delete_dead_mechanism_renderer_2026-09-05.py
    py validate_claims.py

Requires: esprima (pip install esprima) and node on PATH.
"""
import json, os, re, subprocess, sys, tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
HTML = os.path.join(HERE, "index.html")
DRY = "--dry-run" in sys.argv

SEED = {"renderMechanism", "edgeLine", "drawCoreEdge", "drawPeriphEdge"}
KEEP = {"MAP_NODES", "mapNodeById", "prepNode", "ATLAS_EDGES", "ATLAS_ROUTES",
        "renderFullMap", "focusSelectedNode", "attachFullMap"}


def biggest_script(h):
    best = None
    for m in re.finditer(r"<script(?![^>]*\bsrc=)[^>]*>(.*?)</script>", h, re.S):
        if best is None or len(m.group(1)) > len(best.group(1)):
            best = m
    if best is None:
        sys.exit("ABORT: no inline <script> found in index.html.")
    return best.start(1), best.group(1)


def collect(tree, off):
    funcs, ids = {}, []

    def walk(n):
        if isinstance(n, list):
            for x in n:
                walk(x)
            return
        if not hasattr(n, "type"):
            return
        if n.type == "Identifier" and getattr(n, "range", None):
            ids.append((n.name, off + n.range[0]))
        for k in dir(n):
            if k.startswith("_") or k in ("type", "range", "name"):
                continue
            try:
                v = getattr(n, k)
            except Exception:
                continue
            if isinstance(v, list) or hasattr(v, "type"):
                walk(v)

    for node in tree.body:
        if node.type == "FunctionDeclaration":
            funcs[node.id.name] = (off + node.range[0], off + node.range[1])
    walk(tree.body)
    return funcs, ids


def main():
    try:
        import esprima
    except ImportError:
        sys.exit("ABORT: esprima not installed.  py -m pip install esprima")
    if subprocess.call(["node", "--version"], stdout=subprocess.DEVNULL,
                       stderr=subprocess.DEVNULL) != 0:
        sys.exit("ABORT: node not found on PATH; needed to verify the result parses.")
    if not os.path.exists(HTML):
        sys.exit("ABORT: index.html not found -- run from the repo root.")

    h = open(HTML, encoding="utf-8").read()
    before = len(h)
    off, src = biggest_script(h)
    tree = esprima.parseScript(src, {"range": True, "tolerant": True})
    funcs, ids = collect(tree, off)

    dead = {n for n in funcs if n.startswith("mx")} | (SEED & set(funcs))
    dead -= KEEP
    if not dead:
        print("nothing to do: the dead renderer is already gone")
        return

    def inside(pos, names):
        return any(funcs[x][0] <= pos < funcs[x][1] for x in names)

    changed = True
    while changed:
        changed = False
        for n in sorted(dead):
            ext = [p for (nm, p) in ids if nm == n
                   and not (funcs[n][0] <= p < funcs[n][1])
                   and not inside(p, dead)]
            if ext:
                dead.discard(n)
                changed = True
                print("   keeping %s: still referenced at line %d"
                      % (n, h.count("\n", 0, ext[0]) + 1))
                break

    if not dead:
        print("ABORT: reachability analysis left nothing safe to delete.")
        return

    total = sum(funcs[n][1] - funcs[n][0] for n in dead)
    print("deleting %d function(s), %d bytes:" % (len(dead), total))
    for n in sorted(dead):
        print("   %-18s %6d" % (n, funcs[n][1] - funcs[n][0]))

    # The retirement comment still named renderMechanism(), so R11 -- which greps
    # for the symbol anywhere in the file -- kept reporting a function that no
    # longer exists. Reworded rather than deleted: the note about WHY the old
    # renderers went is worth keeping.
    STALE = ("/* renderGraph()/renderFullMap() retired 2026-08-06 -- Entity Browser "
             "detail pane now owns the mechanism link + related-entities chips; "
             "deprecated by Pathway 2.0 \u2014 see build_pathway_model.py: "
             "renderMechanism(); */")
    FRESH = ("/* renderGraph()/renderFullMap() retired 2026-08-06 -- Entity Browser "
             "detail pane now owns the mechanism link + related-entities chips. The "
             "Pathway 1.0 renderer and its mx* helpers were deleted on 2026-09-05; "
             "the live explorer is pathway/pathway.js reading pathway/model.json. */")
    h = h.replace(STALE, FRESH, 1)

    out = h
    for n in sorted(dead, key=lambda x: -funcs[x][0]):     # back to front
        a, b = funcs[n]
        while b < len(out) and out[b] in " \t":
            b += 1
        if b < len(out) and out[b] == "\n":
            b += 1
        out = out[:a] + out[b:]

    # gates
    if not out.rstrip().endswith("</html>"):
        sys.exit("ABORT: output does not end in </html>; nothing written.")
    for n in sorted(KEEP):
        if n in ("MAP_NODES", "ATLAS_EDGES", "ATLAS_ROUTES"):
            if not re.search(r"const\s+" + n + r"\s*=", out):
                sys.exit("ABORT: %s disappeared; nothing written." % n)
        elif ("function %s(" % n) not in out.replace(" (", "("):
            sys.exit("ABORT: %s disappeared; nothing written." % n)

    # the decisive check: does the modified script still parse?
    off2, src2 = biggest_script(out)
    with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False,
                                     encoding="utf-8") as f:
        f.write(src2)
        tmp_js = f.name
    try:
        r = subprocess.run(["node", "--check", tmp_js],
                           capture_output=True, text=True)
        if r.returncode != 0:
            sys.exit("ABORT: modified script does not parse; nothing written.\n"
                     + r.stderr[:600])
        print("node --check: script parses")
    finally:
        os.unlink(tmp_js)

    print("size: %d -> %d bytes (-%d)" % (before, len(out), before - len(out)))
    if DRY:
        print("--dry-run: nothing written.")
        return
    tmp = HTML + ".tmp"
    open(tmp, "w", encoding="utf-8").write(out)
    if open(tmp, encoding="utf-8").read() != out:
        sys.exit("ABORT: read-back mismatch; index.html untouched.")
    os.replace(tmp, HTML)
    print("index.html rewritten and verified.")


if __name__ == "__main__":
    main()
