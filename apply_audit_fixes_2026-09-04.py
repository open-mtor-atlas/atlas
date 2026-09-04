#!/usr/bin/env python3
"""
apply_audit_fixes_2026-09-04.py

The parts of the 2026-09-04 audit that live in code rather than in Airtable.
Everything else from that audit was written directly into the Airtable base on
2026-09-04 and arrives via sync_airtable.py / build_pathway_model.py.

Run from the repo root, AFTER sync_airtable.py and BEFORE build_pathway_model.py:

    py sync_airtable.py
    py apply_audit_fixes_2026-09-04.py --dry-run
    py apply_audit_fixes_2026-09-04.py
    py build_pathway_model.py
    py fix_findings_and_prerender.py
    py validate_claims.py

What it does
------------

A. build_pathway_model.py — support conflicting evidence (audit 2.1)
   evidence.conflicting is currently hardcoded to [] in BOTH interaction
   builders, so all 119 interactions ship with an empty conflicting list. That
   is the field the Atlas's whole "we model contradiction as data" claim rests
   on. This wires it to a CONFLICTING dict and seeds the two known cases:
     - EVE-IMMUNE: MAN2021 is the negative phase 3 trial (no reduction in
       clinically symptomatic respiratory illness, 26% vs 25%, OR 1.07, p=0.65)
       yet sits in supporting on an "activates" edge.
     - 4EBP1-MITO: ZID2009 reports the opposite direction in fly under DR.
   Adding a Conflicting_Studies field to the Relations table is the proper
   long-term fix; this makes the model able to carry it either way.

B. build_pathway_model.py — consensus vs boundary contradictions (audit 3.1)
   Six edges are marked consensus "established" while their own boundary text
   says "single-study edge in this corpus" or equivalent. An edge cannot be
   both. Downgraded to "emerging", which is what one supporting study supports.
   LEU-SESN2 and MTORC1-MAPK are deliberately NOT touched: LEU-SESN2 has three
   supporting studies and its boundary hedges the 20 uM setpoint rather than the
   step; MTORC1-MAPK's boundary is about corpus depth, not about doubt.

C. build_pathway_model.py — MTORC1-MITO / MTORC1-OXPHOS near-duplication (3.2)
   Two edges assert mTORC1 -> mitochondrial output from overlapping citations
   (CUN2007 + MOR2013) at different tiers and different consensus, so a reader
   gets a different evidence strength depending on which arrow they click. This
   does not merge them (that is a curator decision) but cross-references them in
   both boundary texts so the overlap is visible.

D. index.html — stale baked count fallbacks (audit 2.2)
   renderWelcome() sets these spans from ATLAS_STUDIES.length at runtime, so a
   JS reader sees the right number. The baked fallbacks are what crawlers, AI
   readers and no-JS clients see, and epStudyCount still reads 352 against a
   355-study corpus. Refreshed from ATLAS_STUDIES.

Standard library only. Idempotent: running twice is a no-op.
"""
import os, re, sys, json

HERE = os.path.dirname(os.path.abspath(__file__))
BUILD = os.path.join(HERE, "build_pathway_model.py")
HTML = os.path.join(HERE, "index.html")
DRY = "--dry-run" in sys.argv

# Edges whose boundary text contradicts a consensus of "established".
DOWNGRADE = {
    "ERK-TSC": "Single-study edge; Roux 2004's parallel RSK arm is not held.",
    "HYPOXIA-REDD1": "Single-study edge in this corpus.",
    "MTORC2-SGK1": "Single-study edge in this corpus.",
    "S6K1-PDCD4": "Single-study edge in this corpus.",
}

CONFLICTING_SEED = """
# ---- audit 2026-09-04: conflicting evidence is now carried, not discarded.
# evidence.conflicting was hardcoded to [] for all 119 interactions, which
# silently deleted the one thing this Atlas claims to model that others do not.
# Seeded from the two cases found by external audit; extend as they are found,
# or wire to a Conflicting_Studies field on the Relations table.
CONFLICTING = {
    # MAN2021 is the negative phase 3 (no reduction in clinically symptomatic
    # respiratory illness: 26% vs 25%, OR 1.07, p=0.65) on an "activates" edge.
    "EVE-IMMUNE": ["MAN2021"],
    # ZID2009: 4E-BP ENHANCES mitochondrial activity in fly under dietary
    # restriction - opposite direction to this edge's mammalian-cell sign.
    "4EBP1-MITO": ["ZID2009"],
}
"""


def patch_build(src):
    changed = []

    # --- A. conflicting ---------------------------------------------------
    if "CONFLICTING = {" not in src:
        anchor = "EXTRA_EDGES = ["
        if anchor not in src:
            sys.exit("ABORT: EXTRA_EDGES anchor not found in build_pathway_model.py")
        src = src.replace(anchor, CONFLICTING_SEED.strip() + "\n\n" + anchor, 1)
        changed.append("added CONFLICTING dict")

    n = src.count('"conflicting": [],')
    if n:
        src = src.replace('"conflicting": [],',
                          '"conflicting": CONFLICTING.get(e["id"], []),', 1)
        src = src.replace('"conflicting": []',
                          '"conflicting": CONFLICTING.get(eid, [])', 1)
        changed.append("wired conflicting in %d builder(s)" % n)

    # --- B. consensus downgrades -----------------------------------------
    for eid in DOWNGRADE:
        pat = re.compile(r'(^ "%s":\s*\([^\n]*?),"established"\)' % re.escape(eid), re.M)
        new, k = pat.subn(r'\1,"emerging")', src)
        if k:
            src = new
            changed.append("consensus established->emerging: %s" % eid)

    # --- C. MITO / OXPHOS cross-reference ---------------------------------
    marker = "OVERLAP (audit 2026-09-04)"
    if marker not in src:
        old = ('"MTORC1-OXPHOS", "mTORC1", "Oxidative phosphorylation", '
               '"activates", "signal-relay"')
        if old in src:
            src = src.replace(
                "Effect size varies strongly by tissue; the transcriptional and "
                "translational arms have not been cleanly separated in vivo.",
                "Effect size varies strongly by tissue; the transcriptional and "
                "translational arms have not been cleanly separated in vivo. "
                + marker + ": this edge and MTORC1-MITO assert overlapping "
                "biology from overlapping citations (CUN2007, MOR2013) at "
                "different tiers and different consensus levels. Read them "
                "together; they are not independent support.", 1)
            changed.append("cross-referenced MTORC1-OXPHOS with MTORC1-MITO")

    return src, changed


def patch_html(src):
    changed = []
    m = re.search(r"const ATLAS_STUDIES = (\[.*?\]);\n", src, re.S)
    if not m:
        sys.exit("ABORT: ATLAS_STUDIES not found in index.html")
    total = len(json.loads(m.group(1)))

    for sid in ("statTotal", "statHuman", "statOther", "snapshotCount",
                "ipyStudyCount", "epStudyCount"):
        if sid in ("statHuman", "statOther"):
            continue  # derived from pyramid levels, left to renderWelcome()
        pat = re.compile(r'(<span id="%s"[^>]*>)([^<]*)(</span>)' % sid)
        def sub(mm):
            if mm.group(2).strip() == str(total):
                return mm.group(0)
            changed.append("%s: %s -> %d" % (sid, mm.group(2).strip(), total))
            return mm.group(1) + str(total) + mm.group(3)
        src = pat.sub(sub, src)

    src, ech = patch_atlas_edges(src)
    changed.extend(ech)
    return src, changed, total


# ---------------------------------------------------------------------------
# E. ATLAS_EDGES is the pathway source of truth (corrected 2026-09-04)
#
# build_pathway_model.py reads ATLAS_EDGES and ATLAS_ROUTES out of index.html
# (read_atlas_array, called from main()). sync_airtable.py does NOT sync the
# Relations table - it only writes ATLAS_STUDIES, ATLAS_ENTITIES and ATLAS_GAPS.
# So the Airtable Relations table is a documentation and review store; the array
# below is what actually reaches pathway/model.json and the site.
#
# Corrections written into Airtable Relations on 2026-09-04 therefore have to be
# applied here as well, or they never ship. Each carries its reason.
EDGE_FIXES = {
    # JIN2026 (PMID 42468714) is a glucosamine / redox / P-glycoprotein paper.
    # It never mentions PDCD4, so it cannot support "PDCD4 blocks eIF4A".
    # DOR2006 is the S6K1-mediated PDCD4 degradation paper, which supports the
    # S6K1-PDCD4 edge rather than this one. The biology here is textbook and
    # correct; the sourcing is what is wrong, so the edge is flagged rather than
    # deleted. Add Yang 2003 or Suzuki 2008 to close it.
    "PDCD4-TRANSL": {
        "st": ["DOR2006"],
        "ctx": ("SOURCING FLAG (2026-09-04): the mechanism stated here is correct and "
                "canonical, but no study currently in this corpus demonstrates it. "
                "JIN2026 was removed - it does not mention PDCD4. Treat as an unsourced "
                "canonical step until Yang 2003 or Suzuki 2008 is added."),
    },
    # ZHU2026 is a liver toxicology study that touches this axis in passing.
    # best_tier is the max over supporting studies, so attaching it silently
    # promoted a canonical mechanistic step from D to C.
    "LKB1-AMPK": {
        "st": ["SHW2004"],
        "sp": "mammalian cells",
        "ctx": ("Canonical step, established in LKB1-null cells and in vitro kinase "
                "assays (SHW2004). Graded D because that is what the supporting "
                "evidence is: cell and in vitro biochemistry, not an organismal "
                "phenotype. ZHU2026 removed 2026-09-04 - it is a liver toxicology "
                "study and was inflating this edge to tier C."),
    },
    # AMPK reads the AMP(ADP)/ATP ratio via the gamma subunit, not ATP directly.
    "STRESS-AMPK": {
        "mech": ("AMPK does not read ATP directly - it reads the ratio of AMP and ADP "
                 "to ATP. As ATP is consumed, AMP and ADP accumulate and bind the "
                 "gamma subunit, which is the actual switch: it activates AMPK "
                 "allosterically and protects the activating Thr172 phosphate from "
                 "removal. AMPK is the cell's low-fuel sensor, and mTORC1 is one of "
                 "the first things it shuts off."),
    },
    # The BIT2016 dose qualifier already corrected in Knowledge_Gaps H3 and H6,
    # never carried across to the pathway layer.
    "RAPA-LONGEVITY": {
        "ctx": ("Mouse only. No human lifespan or healthspan endpoint exists; EVERLAST "
                "has no results yet. BIT2016 shows a non-continuous schedule can still "
                "extend post-treatment life expectancy, but the result is dose- and "
                "route-specific: in the 8 mg/kg/day intraperitoneal arm males gained "
                "+60% post-treatment life expectancy (p=0.02) while females showed no "
                "survival benefit (p=0.261) and a shift toward aggressive haematopoietic "
                "cancers (16/16 vs 6/12, p=0.002); in the same paper's 126 ppm dietary "
                "arm survival rose significantly in BOTH sexes, with a Cox model finding "
                "no evidence that sex modified the treatment effect (p=0.904). Cite the "
                "arm, not just the paper."),
    },
}


def patch_atlas_edges(src):
    changed = []
    i = src.find("const ATLAS_EDGES = [")
    if i < 0:
        sys.exit("ABORT: ATLAS_EDGES not found in index.html. It is the input to "
                 "build_pathway_model.py and must not be deleted.")
    head = "const ATLAS_EDGES = "
    seg = src[i + len(head):]
    end = seg.find("];") + 1
    raw = seg[:end]
    edges = json.loads(raw)

    dirty = False
    for e in edges:
        fix = EDGE_FIXES.get(e.get("id"))
        if not fix:
            continue
        for k, v in fix.items():
            if e.get(k) != v:
                e[k] = v
                dirty = True
                changed.append("ATLAS_EDGES %s.%s updated" % (e["id"], k))

    if not dirty:
        return src, changed

    new = json.dumps(edges, ensure_ascii=False, separators=(",", ":"))
    src = src[:i + len(head)] + new + src[i + len(head) + end:]
    return src, changed


def main():
    for p in (BUILD, HTML):
        if not os.path.exists(p):
            sys.exit("ABORT: %s not found - run from the repo root." % p)

    b = open(BUILD, encoding="utf-8").read()
    nb, bch = patch_build(b)
    print("build_pathway_model.py:")
    for c in bch:
        print("   -", c)
    if not bch:
        print("   - already patched, nothing to do")

    h = open(HTML, encoding="utf-8").read()
    nh, hch, total = patch_html(h)
    print("index.html (corpus = %d studies):" % total)
    for c in hch:
        print("   -", c)
    if not hch:
        print("   - baked counts already current")

    # gates
    if "CONFLICTING.get(" not in nb:
        sys.exit("ABORT: conflicting wiring missing after patch")
    if not nh.rstrip().endswith("</html>"):
        sys.exit("ABORT: index.html no longer ends in </html>")
    try:
        compile(nb, BUILD, "exec")
    except SyntaxError as e:
        sys.exit("ABORT: patched build_pathway_model.py does not compile: %s" % e)

    if DRY:
        print("\n--dry-run: nothing written.")
        return
    for path, content in ((BUILD, nb), (HTML, nh)):
        tmp = path + ".tmp"
        open(tmp, "w", encoding="utf-8").write(content)
        if open(tmp, encoding="utf-8").read() != content:
            sys.exit("ABORT: read-back mismatch on %s" % path)
        os.replace(tmp, path)
    print("\nWritten and verified.")


if __name__ == "__main__":
    main()
