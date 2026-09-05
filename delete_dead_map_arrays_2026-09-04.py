#!/usr/bin/env python3
"""
delete_dead_map_arrays_2026-09-04.py

R11 flags seven dead names and says "nothing reads these". That is true for
three of them and NOT true for MAP_NODES, so this script deletes only what it
has verified as unreferenced, and reports the rest instead of guessing.

Deleted (zero readers; only other mention is inside a comment):
  MAP_CORE_EDGES    - also carries three WRONG SIGNS, which is the real reason
                      to remove it rather than leave it for crawlers:
                        SAMTOR -> GATOR2 (SAMTOR binds GATOR1/KICSTOR, not GATOR2)
                        AKT -> PRAS40 as "activate" (Akt phosphorylation inactivates PRAS40)
                        4E-BP1 -> Muscle as "activate" (4E-BP1 represses translation)
  MAP_PERIPH_EDGES  - no reference anywhere outside its own definition
  MAP_BANDS         - definition plus one comment mention

NOT deleted, deliberately:
  MAP_NODES         - read by mapNodeById() and by focusSelectedNode(), and
                      focusSelectedNode() is reachable: attachFullMap() calls it
                      and onTabShown() calls attachFullMap(). In practice the
                      path stops early because renderFullMap() no longer emits
                      an <svg>, and line 6577 even guards on
                      "typeof MAP_NODES === 'undefined'" - but "probably
                      unreachable" is not the standard for deleting a symbol
                      that live code names. It holds layout coordinates, not
                      biology, so leaving it costs nothing.
  renderMechanism, mxBuildSVG, mxSetRoute
                    - mxSetRoute and mxBuildSVG are still called from
                      renderMechanism()'s body, so they must be removed together
                      with it, in one reviewed pass over ~250 lines of function
                      bodies. Out of scope for an array deletion.

After running this, R11 will still fire on the four remaining names. That is
correct: they are still there.

Run from the repo root:

    py delete_dead_map_arrays_2026-09-04.py --dry-run
    py delete_dead_map_arrays_2026-09-04.py
    py validate_claims.py

Standard library only. Idempotent. Refuses to delete anything it can still find
a reader for.
"""
import os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
HTML = os.path.join(HERE, "index.html")
DRY = "--dry-run" in sys.argv

TARGETS = ["MAP_CORE_EDGES", "MAP_PERIPH_EDGES", "MAP_BANDS"]
KEEP = ["MAP_NODES"]


def find_array(src, name):
    """Locate 'const NAME = [ ... ];' and return (start, end) of the whole
    statement. Bracket-counted rather than regex-matched, because the arrays
    contain nested brackets and quoted strings."""
    m = re.search(r"const\s+" + re.escape(name) + r"\s*=\s*\[", src)
    if not m:
        return None
    i = src.index("[", m.start())
    depth, j, in_str, esc = 0, i, None, False
    while j < len(src):
        c = src[j]
        if in_str:
            if esc:
                esc = False
            elif c == "\\":
                esc = True
            elif c == in_str:
                in_str = None
        elif c in "\"'`":
            in_str = c
        elif c == "[":
            depth += 1
        elif c == "]":
            depth -= 1
            if depth == 0:
                k = j + 1
                while k < len(src) and src[k] in " \t\r\n":
                    k += 1
                if k < len(src) and src[k] == ";":
                    k += 1
                while k < len(src) and src[k] in " \t":
                    k += 1
                if k < len(src) and src[k] == "\n":
                    k += 1
                return (m.start(), k)
        j += 1
    return None


def readers(src, name, span):
    """Every mention of name outside its own definition and outside comments."""
    out = []
    for m in re.finditer(r"\b" + re.escape(name) + r"\b", src):
        if span and span[0] <= m.start() < span[1]:
            continue
        line_start = src.rfind("\n", 0, m.start()) + 1
        line = src[line_start:src.find("\n", m.start())]
        stripped = line.strip()
        if stripped.startswith(("//", "*", "/*")) or "--" in stripped[:80]:
            continue
        out.append((src.count("\n", 0, m.start()) + 1, stripped[:100]))
    return out


def main():
    if not os.path.exists(HTML):
        sys.exit("ABORT: index.html not found -- run from the repo root.")
    src = open(HTML, encoding="utf-8").read()
    before = len(src)

    for name in KEEP:
        span = find_array(src, name)
        r = readers(src, name, span)
        if r:
            print("keeping %s (%d live reference(s)):" % (name, len(r)))
            for ln, txt in r[:3]:
                print("   line %d: %s" % (ln, txt))

    removed = []
    for name in TARGETS:
        span = find_array(src, name)
        if not span:
            print("%s: already gone" % name)
            continue
        r = readers(src, name, span)
        if r:
            print("REFUSING to delete %s -- found %d reader(s):" % (name, len(r)))
            for ln, txt in r:
                print("   line %d: %s" % (ln, txt))
            sys.exit("ABORT: %s is referenced; nothing written." % name)
        n_lines = src.count("\n", span[0], span[1])
        src = src[:span[0]] + src[span[1]:]
        removed.append((name, n_lines))

    if not removed:
        print("nothing to do")
        return
    for name, n in removed:
        print("   - deleted %s (%d lines)" % (name, n))

    # gates
    if not src.rstrip().endswith("</html>"):
        sys.exit("ABORT: output does not end in </html>")
    for name in ("ATLAS_EDGES", "ATLAS_ROUTES", "ATLAS_STUDIES", "ATLAS_GAPS", "MAP_NODES"):
        if not re.search(r"const\s+" + name + r"\s*=", src):
            sys.exit("ABORT: %s disappeared -- refusing to write." % name)
    for marker in ("<!--PRERENDER:questionsView-->", "<!--/PRERENDER:questionsView-->"):
        if marker not in src:
            sys.exit("ABORT: %s missing -- refusing to write." % marker)

    print("size: %d -> %d bytes (-%d)" % (before, len(src), before - len(src)))
    if DRY:
        print("--dry-run: nothing written.")
        return
    tmp = HTML + ".tmp"
    open(tmp, "w", encoding="utf-8").write(src)
    if open(tmp, encoding="utf-8").read() != src:
        sys.exit("ABORT: read-back mismatch, index.html untouched.")
    os.replace(tmp, HTML)
    print("index.html rewritten and verified.")


if __name__ == "__main__":
    main()
