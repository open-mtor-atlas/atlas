#!/usr/bin/env python3
"""
sync_relations.py -- regenerate the ATLAS_EDGES constant inside index.html from
the Airtable "Relations" table, and re-solve the arrow geometry for every route
in ATLAS_ROUTES so no arrow crosses an unrelated node box.

This is the Mechanism Explorer's half of the Tier-0 static bake, the sibling of
sync_airtable.py. Same rules apply: Airtable is the source of truth, no secret
ever ships inside index.html, and the file is written with fsync + verification
because this repo's OneDrive-synced folder has truncated large writes before.

    export AIRTABLE_TOKEN=patXXXX      # read-only PAT scoped to this base
    python3 sync_relations.py
    python3 sync_relations.py --layout-only      # skip Airtable, just re-solve geometry
    python3 sync_relations.py --confirmed-only   # publish only reviewer-signed edges

REVIEW GATE
  By default every edge that is not Rejected goes onto the page, including
  Proposed ones -- useful while the graph is being built out. Once a reviewer has
  worked through the backlog in the "Relations Review" Airtable interface, switch
  to --confirmed-only and the public page will carry only edges a human has
  actually signed off. Contested edges stay published in both modes: an edge the
  field genuinely disagrees about is a finding, not a defect.

WHAT IS AND IS NOT REGENERATED
  ATLAS_EDGES  -- fully regenerated from Airtable. Never hand-edit it.
  ATLAS_ROUTES -- hand-maintained in index.html (node coordinates, story text,
                  play order). This script only rewrites each route's "bows" and
                  "ctrl" layout hints. Move a node, re-run this, done.

CURATION RULE
  An edge with no linked study is a bug, not a shortcut. If a canonical textbook
  step has no supporting paper in the corpus, that absence belongs in
  Knowledge_Gaps, not in a drawn arrow. This script refuses to bake such edges
  and prints them so they can be fixed.

Standard library only.
"""
import os, sys, json, re, math, time, itertools, urllib.request, urllib.parse

BASE  = "appt2U6ObDHUcRlrj"
TOKEN = os.environ.get("AIRTABLE_TOKEN")
HTML  = os.path.join(os.path.dirname(os.path.abspath(__file__)), "index.html")

# Status values allowed onto the public page. See REVIEW GATE above.
PUBLISH_ALL       = {"Proposed", "Confirmed", "Contested"}
PUBLISH_REVIEWED  = {"Confirmed", "Contested"}
PUBLISH = PUBLISH_ALL          # reassigned in main() when --confirmed-only is passed

# Node geometry -- must stay in sync with mx.js (MX_NH, mxNodeW, mxAnchor).
NH   = 34
PAD  = 7          # clearance demanded around every other node box
SAMP = 235        # samples per curve when testing for collisions


# ---------------------------------------------------------------- Airtable ---
def api(table, params=None):
    out, offset = [], None
    while True:
        q = dict(params or {})
        if offset:
            q["offset"] = offset
        url = "https://api.airtable.com/v0/%s/%s" % (BASE, urllib.parse.quote(table))
        if q:
            url += "?" + urllib.parse.urlencode(q, doseq=True)
        req = urllib.request.Request(url, headers={"Authorization": "Bearer " + TOKEN})
        data = json.load(urllib.request.urlopen(req))
        out += data.get("records", [])
        offset = data.get("offset")
        if not offset:
            break
        time.sleep(0.25)
    return out


def g(f, k, d=""):
    v = f.get(k, d)
    return v if v is not None else d


TIER_RANK = {"A": 0, "B": 1, "C": 2, "D": 4}


def best_tier(tiers):
    """A > B > C > D. Preprints / registered trials rank with D."""
    ls = [(t or "D")[:1] for t in tiers] or ["D"]
    ls = [l if l in TIER_RANK else "D" for l in ls]
    return sorted(ls, key=lambda l: TIER_RANK[l])[0]


def build_edges():
    ent = {r["id"]: g(r["fields"], "Entity_Name") for r in api("Entities")}
    stu = {r["id"]: (g(r["fields"], "Study_ID"), g(r["fields"], "Evidence_Tier"))
           for r in api("Studies")}

    edges, skipped, orphan, unsigned = [], [], [], []
    for r in sorted(api("Relations"), key=lambda r: g(r["fields"], "Edge_ID")):
        f = r["fields"]
        eid = g(f, "Edge_ID")
        status = g(f, "Status", "Proposed")
        if status == "Confirmed" and not g(f, "Reviewed_By").strip():
            unsigned.append(eid)     # Confirmed without a name is not a review
        if status not in PUBLISH:
            skipped.append((eid, status))
            continue
        src = [ent.get(i) for i in f.get("Source", []) if ent.get(i)]
        tgt = [ent.get(i) for i in f.get("Target", []) if ent.get(i)]
        sids, tiers = [], []
        for i in f.get("Evidence_Studies", []):
            if i in stu:
                sids.append(stu[i][0])
                tiers.append(stu[i][1])
        if not sids:
            orphan.append(eid)          # no citation -> refuse to draw it
            continue
        if not src or not tgt:
            orphan.append(eid + " (missing Source/Target)")
            continue
        edges.append({
            "id": eid, "s": src[0], "t": tgt[0], "sign": g(f, "Sign", "activates"),
            "mech": g(f, "Mechanism"), "st": sids, "dir": g(f, "Directness"),
            "sp": g(f, "Context_Species"), "ctx": g(f, "Context_Note"),
            "status": status, "note": g(f, "Curator_Note"),
            "tier": best_tier(tiers),
            "tiers": sorted({(t or "D")[:1] for t in tiers},
                            key=lambda l: TIER_RANK.get(l, 4)),
        })
    if skipped:
        print("  skipped (not publishable): " + ", ".join("%s[%s]" % s for s in skipped))
    if orphan:
        print("  !! REFUSED -- edge with no linked study in the corpus: " + ", ".join(orphan))
        print("     Link a study, or record the missing evidence in Knowledge_Gaps.")
    if unsigned:
        print("  !  Confirmed but nobody signed it (Reviewed_By empty): " + ", ".join(unsigned))
    return edges


# ------------------------------------------------------------ edge geometry --
def node_w(label):
    return max(74, len(str(label)) * 7.6 + 26)


def anchor(n, ox, oy):
    w, h = node_w(n["l"]) / 2, NH / 2
    dx, dy = ox - n["x"], oy - n["y"]
    if dx == 0 and dy == 0:
        return (n["x"], n["y"])
    sx = float("inf") if dx == 0 else w / abs(dx)
    sy = float("inf") if dy == 0 else h / abs(dy)
    s = min(sx, sy)
    return (n["x"] + dx * s, n["y"] + dy * s)


def in_rect(n, p, pad=PAD):
    return (abs(p[0] - n["x"]) <= node_w(n["l"]) / 2 + pad and
            abs(p[1] - n["y"]) <= NH / 2 + pad)


def quad(a, c, b, t):
    u = 1 - t
    return (u * u * a[0] + 2 * u * t * c[0] + t * t * b[0],
            u * u * a[1] + 2 * u * t * c[1] + t * t * b[1])


def cubic(a, c1, c2, b, t):
    u = 1 - t
    return (u**3 * a[0] + 3 * u * u * t * c1[0] + 3 * u * t * t * c2[0] + t**3 * b[0],
            u**3 * a[1] + 3 * u * u * t * c1[1] + 3 * u * t * t * c2[1] + t**3 * b[1])


def default_ctrl(A, B, mult):
    """Same rule as mx.js: bow perpendicular to the chord, scaled by `mult`."""
    dx, dy = B["x"] - A["x"], B["y"] - A["y"]
    L = math.hypot(dx, dy) or 1
    bow = 0 if abs(dx) < 30 else min(58, L * 0.11)
    if dx < 0:
        bow = -bow
    bow *= mult
    return ((A["x"] + B["x"]) / 2 + (-dy / L) * bow,
            (A["y"] + B["y"]) / 2 + (dx / L) * bow)


def hits(route, e, pts, box):
    vbx, vby, W, H = box
    for p in pts:
        if p[0] < vbx + 2 or p[0] > vbx + W - 2 or p[1] < vby + 2 or p[1] > vby + H - 2:
            return True
        for n in route["nodes"]:
            if n["k"] in (e["s"], e["t"]):
                continue
            if in_rect(n, p):
                return True
    return False


MULTS = [1, -1, 1.4, -1.4, 1.9, -1.9, 2.5, -2.5, 3.2, -3.2, 0.5, -0.5, 0.15, -0.15]


def solve_route(route, edges_by_id):
    """Pick, per edge, the gentlest curve that touches no unrelated node box."""
    N = {n["k"]: n for n in route["nodes"]}
    box = [float(x) for x in route["vb"].split()]
    vbx, vby, W, H = box
    bows, ctrl, unsolved, oob = {}, {}, [], []

    for n in route["nodes"]:
        w = node_w(n["l"]) / 2
        if (n["x"] - w < vbx + 2 or n["x"] + w > vbx + W - 2 or
                n["y"] - NH / 2 < vby + 2 or n["y"] + NH / 2 > vby + H - 2):
            oob.append(n["k"])

    for eid in route["edges"]:
        e = edges_by_id.get(eid)
        if not e:
            unsolved.append(eid + " (not in ATLAS_EDGES)")
            continue
        A, B = N.get(e["s"]), N.get(e["t"])
        if not A or not B:
            unsolved.append(eid + " (endpoint not placed in this route)")
            continue

        done = False
        for m in MULTS:                                   # 1) try a simple arc
            c = default_ctrl(A, B, m)
            a, b = anchor(A, *c), anchor(B, *c)
            pts = [quad(a, c, b, t / SAMP) for t in range(3, SAMP - 2)]
            if not hits(route, e, pts, box):
                if m != 1:
                    bows[eid] = m
                done = True
                break
        if done:
            continue

        best = None                                       # 2) fall back to a detour
        gx = [vbx + 30, vbx + W * .12, vbx + W * .25, vbx + W * .4, vbx + W * .5,
              vbx + W * .6, vbx + W * .75, vbx + W * .88, vbx + W - 30]
        gy = [vby + 25, vby + H * .15, vby + H * .3, vby + H * .5, vby + H * .7,
              vby + H * .85, vby + H - 25]
        ux, uy = B["x"] - A["x"], B["y"] - A["y"]
        ul = math.hypot(ux, uy) or 1
        for c1 in itertools.product(gx, gy):
            p1 = (c1[0] - A["x"]) * ux / ul + (c1[1] - A["y"]) * uy / ul
            if not 0 <= p1 <= ul * 1.25:
                continue
            for c2 in itertools.product(gx, gy):
                p2 = (c2[0] - A["x"]) * ux / ul + (c2[1] - A["y"]) * uy / ul
                if not p1 < p2 <= ul * 1.25:              # keep controls in travel order
                    continue
                a, b = anchor(A, *c1), anchor(B, *c2)
                pts = [cubic(a, c1, c2, b, t / SAMP) for t in range(3, SAMP - 2)]
                if hits(route, e, pts, box):
                    continue
                ln = sum(math.dist(pts[i], pts[i + 1]) for i in range(len(pts) - 1))
                if ln / (math.dist(pts[0], pts[-1]) or 1) > 1.85:
                    continue                              # no absurd loops
                if best is None or ln < best[0]:
                    best = (ln, [list(c1), list(c2)])
        if best:
            ctrl[eid] = best[1]
        else:
            unsolved.append(eid)

    return bows, ctrl, unsolved, oob


# ------------------------------------------------------------------- rewrite --
def extract(h, name):
    m = re.search(r"const %s = (\[.*?\]);\n" % name, h, re.S)
    if not m:
        sys.exit("%s not found in index.html" % name)
    return json.loads(m.group(1)), m


def main():
    global PUBLISH
    layout_only = "--layout-only" in sys.argv
    if "--confirmed-only" in sys.argv:
        PUBLISH = PUBLISH_REVIEWED
    if not layout_only and not TOKEN:
        sys.exit("Set AIRTABLE_TOKEN (read-only PAT scoped to this base), "
                 "or pass --layout-only to just re-solve the geometry.")

    h = open(HTML, encoding="utf-8").read()
    old_edges, _ = extract(h, "ATLAS_EDGES")
    routes, _ = extract(h, "ATLAS_ROUTES")

    if layout_only:
        edges = old_edges
        print("ATLAS_EDGES: left untouched (--layout-only), %d edges" % len(edges))
    else:
        print("publishing statuses: %s" % ", ".join(sorted(PUBLISH)))
        edges = build_edges()
        print("ATLAS_EDGES: %d edges pulled from Airtable (was %d)" % (len(edges), len(old_edges)))
        if not edges:
            sys.exit("Refusing to write an empty ATLAS_EDGES. "
                     "With --confirmed-only this usually means nothing has been "
                     "reviewed yet -- run without the flag, or review some edges first.")
        if len(edges) < len(old_edges) * 0.5 and old_edges:
            print("  !  This would drop %d of %d edges off the page. Check that is intended."
                  % (len(old_edges) - len(edges), len(old_edges)))

    by_id = {e["id"]: e for e in edges}
    problems = []
    for r in routes:
        bows, ctrl, unsolved, oob = solve_route(r, by_id)
        r.pop("bows", None)
        r.pop("ctrl", None)
        if bows:
            r["bows"] = bows
        if ctrl:
            r["ctrl"] = ctrl
        print("  route %-6s %2d edges | %d bowed | %d detoured" %
              (r["id"], len(r["edges"]), len(bows), len(ctrl)))
        for u in unsolved:
            problems.append("route %s: could not route %s" % (r["id"], u))
        for n in oob:
            problems.append("route %s: node %s sticks out of the viewBox" % (r["id"], n))

    for p in problems:
        print("  !! " + p)

    h = re.sub(r"const ATLAS_EDGES = \[.*?\];\n",
               "const ATLAS_EDGES = " + json.dumps(edges, ensure_ascii=False) + ";\n",
               h, count=1, flags=re.S)
    h = re.sub(r"const ATLAS_ROUTES = \[.*?\];\n",
               "const ATLAS_ROUTES = " + json.dumps(routes, ensure_ascii=False) + ";\n",
               h, count=1, flags=re.S)

    blob = h.encode("utf-8")
    with open(HTML, "w", encoding="utf-8") as fh:
        fh.write(h)
        fh.flush()
        os.fsync(fh.fileno())
    back = open(HTML, "rb").read()
    if back != blob:
        sys.exit("WRITE VERIFICATION FAILED -- index.html was truncated. Do not commit.")
    print("index.html rewritten and verified (%d bytes)." % len(blob))
    if problems:
        sys.exit(1)


if __name__ == "__main__":
    main()
