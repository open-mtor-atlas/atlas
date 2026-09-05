#!/usr/bin/env python3
"""
add_r13_validator_2026-09-05.py

Adds R13: a study cited as SUPPORTING an edge whose direction it does not
support. This is the failure mode that cost the most time in the 2026-08-30 and
2026-09-04 audits, and none of R1-R12 could see it:

  * ZID2009 was listed as supporting 4EBP1-MITO (sign "inhibits") while its own
    title reads "...by ENHANCING mitochondrial activity in Drosophila".
  * MAN2021 sat in supporting on EVE-IMMUNE (sign "activates") although it is
    the phase 3 null trial, filed in the corpus as Negative_result.

Neither could be caught by checking that the citation exists and is on-topic,
which is all the pipeline did. R13 checks the DIRECTION.

Two signals, deliberately narrow
--------------------------------
R13a  A study whose corpus category is Negative_result is cited as supporting a
      directional edge (activates / inhibits). A null result can legitimately sit
      on the supporting side when a different arm of the same publication
      supports the edge, but it should then also appear in Conflicting_Studies.

R13b  The study TITLE contains an opposite-direction verb immediately before the
      edge's TARGET entity: an "increases/enhances/promotes" verb on an
      "inhibits" edge, or a "reduces/impairs/abolishes" verb on an "activates"
      edge. Titles are terse and assertive, so they carry far less noise than
      abstracts or curated findings.

Tuning, and why it is this narrow
---------------------------------
A first pass matched direction words anywhere in the title and produced 11 hits
on 100 edges, nearly all noise: "tumor suppressor" in three titles, "promotes
protein translation" on an edge about S6K1 and PDCD4, "enhancing insulin
sensitivity" on an edge about S6K1 and IRS-1. Requiring the verb to sit within
two words of the target entity, and dropping generic nouns from the target
tokens, removed all of them.

"inhibit" and "suppress" were then dropped from the negative verb list: they
describe the intervention far more often than the outcome, and matched
"mTOR INHIBITION improves immune function" as if it contradicted an activating
edge. Losing them costs little, because an inhibitory finding on an activating
edge almost always also says "reduced" or "impaired".

Result on the corpus of 2026-09-05: one hit, and it is real. Re-running the
scan with ZID2009 and MAN2021 restored to the supporting side catches both.

WARN, not ERROR: both signals are heuristics about prose, and a study can
legitimately sit on both sides of one edge when different arms point different
ways. R13 asks a question; it does not assert an error.

Run from the repo root:

    py add_r13_validator_2026-09-05.py --dry-run
    py add_r13_validator_2026-09-05.py
    py validate_claims.py

Standard library only. Idempotent.
"""
import os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
VC = os.path.join(HERE, "validate_claims.py")
DRY = "--dry-run" in sys.argv

HELPERS = '''
# --- R13 support: does a cited study actually back the edge's direction? -----
# Generic nouns are stripped from the target name before matching, or "growth"
# and "function" would pair with any verb in any title.
R13_STOP = {"function", "growth", "signaling", "signalling", "response",
            "activity", "cells", "cell", "human", "mouse", "factor",
            "pathway", "complex", "protein", "synthesis", "disease"}
R13_UP = r"enhanc\\w*|increas\\w*|promot\\w*|elevat\\w*|upregulat\\w*|augment\\w*"
# "inhibit" and "suppress" are deliberately absent: they describe the
# intervention more often than the outcome ("mTOR inhibition improves ...").
R13_DOWN = r"reduc\\w*|decreas\\w*|impair\\w*|abolish\\w*|blunt\\w*"


def r13_target_tokens(name):
    return [w for w in re.findall(r"[A-Za-z][A-Za-z0-9-]{4,}", name or "")
            if w.lower() not in R13_STOP]


def r13_title_contradicts(title, sign, target):
    """Opposite-direction verb within two words of the target entity."""
    opp = R13_UP if sign == "inhibits" else R13_DOWN
    for t in r13_target_tokens(target):
        m = re.search(r"(?:%s)\\W+(?:\\w+\\W+){0,2}%s" % (opp, re.escape(t)),
                      title or "", re.I)
        if m:
            return m.group(0)
    return None

'''

RULE = r'''

def load_atlas_edges(h):
    i = h.find("const ATLAS_EDGES = [")
    if i < 0:
        return []
    head = "const ATLAS_EDGES = "
    seg = h[i + len(head):]
    return json.loads(seg[:seg.find("];") + 1])


def load_atlas_studies(h):
    m = re.search(r"const ATLAS_STUDIES = (\[.*?\]);\n", h, re.S)
    return json.loads(m.group(1)) if m else []


def check_edge_direction(findings, h):
    """R13 -- a study on the SUPPORTING side that does not support the direction.
    See add_r13_validator_2026-09-05.py for why the match is this narrow."""
    edges = load_atlas_edges(h)
    by_sid = {s.get("sid"): s for s in load_atlas_studies(h) if s.get("sid")}
    for e in edges:
        sign = e.get("sign")
        if sign not in ("activates", "inhibits"):
            continue
        conflicting = set(e.get("cf") or [])
        for sid in e.get("st") or []:
            if sid in conflicting:
                continue          # already declared as cutting both ways
            s = by_sid.get(sid)
            if not s:
                continue
            where = "edge:%s" % e.get("id")
            if s.get("category") == "Negative_result":
                add(findings, "WARN", "R13 null-result-as-support", where, sid,
                    "%s is filed as Negative_result but is cited as SUPPORTING "
                    "%s (sign: %s)." % (sid, e.get("id"), sign),
                    "If one arm supports the edge and another contradicts it, add "
                    "%s to Conflicting_Studies as well." % sid)
            hit = r13_title_contradicts(s.get("title"), sign, e.get("t"))
            if hit:
                add(findings, "WARN", "R13 title-contradicts-sign", where, sid,
                    "%s supports %s (sign: %s) but its title says %r about the "
                    "target." % (sid, e.get("id"), sign, hit),
                    "Check the direction. If the study points the other way, move it "
                    "to Conflicting_Studies or scope the edge by species/context.")
'''


def main():
    if not os.path.exists(VC):
        sys.exit("ABORT: validate_claims.py not found -- run from the repo root.")
    src = open(VC, encoding="utf-8").read()
    before = len(src)

    if "R13 null-result-as-support" in src:
        print("validate_claims.py: R13 already present, nothing to do")
        return

    anchor = "\ndef load_atlas_gaps("
    if anchor not in src:
        sys.exit("ABORT: anchor load_atlas_gaps() not found; patch by hand.")
    src = src.replace(anchor, "\n" + HELPERS.strip("\n") + "\n\n" + anchor.lstrip("\n"), 1)
    print("   - added R13 helpers")

    anchor2 = "\ndef main():"
    if anchor2 not in src:
        sys.exit("ABORT: main() not found; patch by hand.")
    src = src.replace(anchor2, "\n" + RULE.strip("\n") + "\n\n" + anchor2.lstrip("\n"), 1)
    print("   - added check_edge_direction()")

    call_anchor = "    check_dead_layers(findings, h)"
    if call_anchor not in src:
        sys.exit("ABORT: could not find the check_dead_layers call site; patch by hand.")
    src = src.replace(call_anchor,
                      call_anchor + "\n    check_edge_direction(findings, h)", 1)
    print("   - wired R13 into main()")

    try:
        compile(src, VC, "exec")
    except SyntaxError as e:
        sys.exit("ABORT: patched validate_claims.py does not compile: %s" % e)

    print("size: %d -> %d bytes" % (before, len(src)))
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
