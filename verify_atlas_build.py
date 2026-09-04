#!/usr/bin/env python3
"""
verify_atlas_build.py -- post-build checks for the Open mTOR Atlas.

Run from the repo root after the build steps. Exit code 0 = all good,
1 = at least one check failed (do not commit), 2 = could not run.

    py verify_atlas_build.py
    py verify_atlas_build.py --no-sync    # relax checks that need a fresh Airtable sync

--no-sync
    Some checks depend on Airtable edits made on 2026-09-04 (dropping JIN2026
    from PDCD4-TRANSL, dropping ZHU2026 from LKB1-AMPK, the H4 scope fix, 15
    filled PMIDs). Those edits only reach index.html via sync_airtable.py, which
    needs AIRTABLE_TOKEN. With --no-sync those checks are reported as SKIPPED
    rather than failing, and the summary warns that the build is incomplete.

Standard library only.
"""
import json, os, re, sys

NO_SYNC = "--no-sync" in sys.argv
FAILS = []
SKIPS = []


def ok(m):    print("   OK      " + m)
def fail(m):  print("   FAIL    " + m); FAILS.append(m)
def skip(m):  print("   SKIP    " + m); SKIPS.append(m)
def warn(m):  print("   WARN    " + m)


def need(path):
    if not os.path.exists(path):
        print("Cannot run: %s not found. Run from the repo root." % path)
        sys.exit(2)
    return open(path, encoding="utf-8").read()


def main():
    html = need("index.html")
    need("pathway/model.json")
    model = json.loads(open("pathway/model.json", encoding="utf-8").read())
    ix = {i["id"]: i for i in model["interactions"]}

    print("\n-- 1. Superseded Open Questions text ------------------------------")
    forbidden = [
        "links to ZERO aging/longevity outcomes",
        "links to ZERO longevity / aging outcomes",
        "RADIANT-3 PFS 5% vs 2%",
        "Nrf2-KO fibroblasts WITHOUT activating autophagy",
        "ARA2009 mTOR drives memory-CD8 differentiation",
        "HAL2012 found chronic rapamycin modulates BOTH cognitive",
        "CALERIE (ROM2016): safety only, no significant differences",
    ]
    # The correction logs deliberately QUOTE the superseded wording ("this block
    # previously read ..."), so a bare substring test produces false positives on
    # the Atlas's own audit trail. An occurrence only counts as a live claim if
    # no correction marker sits near it.
    markers = ("CORRECTION", "WITHDRAWN", "previously read", "previously cited",
               "previously carried", "SCOPE (", "WORDING CORRECTION",
               "BENEFIT-SIDE CORRECTION", "DOSE QUALIFIER", "QUALIFIED (")
    live = []
    logged = 0
    for s in forbidden:
        for mm in re.finditer(re.escape(s), html):
            window = html[max(0, mm.start() - 700): mm.end() + 400]
            if any(k in window for k in markers):
                logged += 1
            else:
                live.append(s)
    if live:
        for s in sorted(set(live)):
            fail("old text present as a live claim in index.html: " + s)
    else:
        ok("no superseded string appears as a live claim "
           "(%d occurrence(s) found inside correction logs, which is correct)" % logged)

    print("\n-- 2. Expected corrections present --------------------------------")
    for label, needle, needs_sync in [
        ("H1 correction log", "CORRECTION LOG", False),
        ("SAX2026 / TRON in H8", "SAX2026", False),
        ("H10 withdrawn claim", "WITHDRAWN CLAIM", False),
        ("H4 corpus scope", "No study IN THIS CORPUS", True),
    ]:
        if needle in html:
            ok("%s present" % label)
        elif needs_sync and NO_SYNC:
            skip("%s missing - needs a fresh Airtable sync" % label)
        else:
            fail("%s missing (%r)" % (label, needle))

    print("\n-- 3. Prerender block vs ATLAS_GAPS -------------------------------")
    m = re.search(r"<!--PRERENDER:questionsView-->(.*?)<!--/PRERENDER:questionsView-->", html, re.S)
    if not m:
        fail("PRERENDER:questionsView markers not found")
    else:
        pre = m.group(1)
        gaps = json.loads(re.search(r"const ATLAS_GAPS = (\[.*?\]);", html, re.S).group(1))
        stale = [g["id"] for g in gaps if g["basis"][:60] not in pre]
        if stale:
            fail("prerender stale for: " + ", ".join(stale)
                 + "  (run fix_findings_and_prerender.py)")
        else:
            ok("prerender carries current text for all %d gap cards" % len(gaps))

    print("\n-- 4. Baked corpus counts -----------------------------------------")
    studies = json.loads(re.search(r"const ATLAS_STUDIES = (\[.*?\]);\n", html, re.S).group(1))
    total = len(studies)
    bad = []
    for sid in ("epStudyCount", "ipyStudyCount", "snapshotCount", "statTotal"):
        for mm in re.finditer(r'<span id="%s"[^>]*>([^<]*)</span>' % sid, html):
            if mm.group(1).strip() != str(total):
                bad.append("%s=%s" % (sid, mm.group(1).strip()))
    if bad:
        fail("baked counts stale against corpus of %d: %s" % (total, ", ".join(bad)))
    else:
        ok("all baked count spans read %d" % total)

    print("\n-- 5. Pathway model evidence --------------------------------------")

    def ev(eid, key):
        return (ix.get(eid, {}).get("evidence", {}) or {}).get(key)

    # These come from the code patch, so they hold with or without a sync.
    for eid, study in (("4EBP1-MITO", "ZID2009"), ("EVE-IMMUNE", "MAN2021")):
        got = ev(eid, "conflicting") or []
        if study in got:
            ok("%s carries %s as conflicting evidence" % (eid, study))
        else:
            fail("%s conflicting=%s, expected to contain %s "
                 "(run apply_audit_fixes_2026-09-04.py then build_pathway_model.py)"
                 % (eid, got, study))

    # These come from Airtable and need a sync.
    for eid, study in (("LKB1-AMPK", "ZHU2026"), ("PDCD4-TRANSL", "JIN2026")):
        got = ev(eid, "supporting") or []
        if study not in got:
            ok("%s no longer cites %s" % (eid, study))
        elif NO_SYNC:
            skip("%s still cites %s - needs a fresh Airtable sync" % (eid, study))
        else:
            fail("%s still cites %s" % (eid, study))

    n_conf = sum(1 for i in model["interactions"] if i["evidence"].get("conflicting"))
    if n_conf == 0:
        fail("no interaction carries conflicting evidence - the field is still dead")
    else:
        ok("%d of %d interactions carry conflicting evidence"
           % (n_conf, len(model["interactions"])))

    print("\n-- 6. model.json freshness ----------------------------------------")
    gen = model["meta"]["generated"][:10]
    upd = re.search(r'ATLAS_UPDATED = "([^"]*)"', html).group(1)[:10]
    if gen >= upd:
        ok("model.json (%s) is current with index.html (%s)" % (gen, upd))
    else:
        fail("model.json generated %s but index.html synced %s "
             "- rerun build_pathway_model.py" % (gen, upd))

    print("\n-- 7. PMID coverage -----------------------------------------------")
    nopmid = [s for s in studies
              if not (s.get("pmid") or "").strip()
              and (s.get("tier") or "") not in ("Preprint", "Registered trial")]
    if len(nopmid) <= 29:
        ok("%d graded studies without a PMID (was 43 before 2026-09-04)" % len(nopmid))
    elif NO_SYNC:
        skip("%d graded studies without a PMID - 15 were filled in Airtable, "
             "needs a sync" % len(nopmid))
    else:
        warn("%d graded studies without a PMID" % len(nopmid))

    print("\n" + "=" * 68)
    if FAILS:
        print("RESULT: %d check(s) FAILED. Do not commit." % len(FAILS))
        for f in FAILS:
            print("   - " + f)
        sys.exit(1)
    if SKIPS:
        print("RESULT: passed, but %d check(s) SKIPPED because there was no "
              "Airtable sync." % len(SKIPS))
        print("This build does NOT contain the 2026-09-04 Airtable edits.")
        print("Re-run with AIRTABLE_TOKEN set before committing.")
        sys.exit(0)
    print("RESULT: all checks passed.")
    sys.exit(0)


if __name__ == "__main__":
    main()
