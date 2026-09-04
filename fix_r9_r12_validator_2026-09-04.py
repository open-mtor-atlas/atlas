#!/usr/bin/env python3
"""
fix_r9_r12_validator_2026-09-04.py

14 of the validator's 17 WARNs are false positives, from two distinct causes.
They are fixed separately, because they are separate bugs.

R12 -- unscoped absence claims
------------------------------
The Atlas's correction logs deliberately QUOTE the superseded wording:

    CORRECTION LOG (2026-08-30): this block previously read 'supported ONLY by
    tier-D mechanistic studies and links to ZERO aging/longevity outcomes'.

R12 matches the quoted ONLY and ZERO and reports them as live claims. The audit
trail is the one place those words are supposed to appear. R8 already solves
this exact problem at line ~317 with a look-back for "previously read|CORRECTION
LOG|already false"; R9 and R12 simply never got it. This patch lifts that check
into a shared in_correction_log() helper, widens the marker list to cover the
newer log formats (SCOPE, WITHDRAWN CLAIM, WORDING CORRECTION, previously
cited), and calls it from R8 and R12.

Clears: H1 x2, H4, H9. Keeps H10, which is a genuine unscoped absence claim in
live text ("Missing: no study tests whether BLOCKING senescence suppression...")
and should be fixed in Airtable rather than silenced.

R9 -- numbers without a study code
----------------------------------
Two bugs here, neither of them about correction logs.

1. The rule's comment says a numeral needs a "nearby study code"; the code
   requires it in the SAME sentence. In a passage like "QUANTIFIED: BIT2016,
   HIGH-DOSE ARM ... males +60% (p=0.02); females NO survival benefit (p=0.261)"
   the code is attached once and then carried by the following clauses, which is
   normal scientific prose. Widened to a window covering the sentence plus ~400
   preceding characters, which is what "nearby" meant.

2. Sentence splitting breaks on abbreviations. "8 mg/kg/day i.p. x 90 days"
   splits after "i.p.", orphaning the numbers from the BIT2016 that introduced
   them. Common abbreviations (i.p., e.g., i.e., vs., approx., etc., cf., Fig.)
   are protected before splitting.

Clears: H3 x2, H5 x2 (the two CORRECTION sentences and the BOLERO-2/RADIANT-3
sentence), H6, H8. Keeps H9's ITP figure, which genuinely has no study code
anywhere near it -- that one is flagged in its own text as a SOURCING GAP and
needs the ITP publication entered in the corpus.

Expected result: 17 WARN -> 6, all six substantive.

Run from the repo root:

    py fix_r9_r12_validator_2026-09-04.py --dry-run
    py fix_r9_r12_validator_2026-09-04.py
    py validate_claims.py

Standard library only. Idempotent.
"""
import os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
VC = os.path.join(HERE, "validate_claims.py")
DRY = "--dry-run" in sys.argv

HELPER = '''
# ---------------------------------------------------------------------------
# Correction-log awareness (added 2026-09-04).
#
# This Atlas logs its own corrections in place, quoting the wording it replaced:
#   "CORRECTION LOG (2026-08-30): this block previously read '... ZERO ...'"
# A rule that greps for the superseded phrasing will therefore fire on the audit
# trail itself. R8 had a private look-back for this; R9 and R12 did not, which
# produced 14 of 17 WARNs on a correct build. Shared here so the next rule that
# needs it does not have to reinvent it.
CORRECTION_MARKER = re.compile(
    r"CORRECTION LOG|WORDING CORRECTION|BENEFIT-SIDE CORRECTION|CORRECTION \\(|"
    r"WITHDRAWN CLAIM|SCOPE \\(|previously read|previously cited|"
    r"previously carried|previously asserted|already false",
    re.I)


# A correction log quotes the wording it replaced, in single quotes:
#   CORRECTION LOG (...): this block previously read '... ZERO ...'.
# Suppression is therefore scoped to the QUOTED SPAN, not to a distance from the
# marker. A distance window is wrong: H10's live claim "Missing: no study tests
# whether BLOCKING senescence suppression..." sits 665 characters after its
# WITHDRAWN CLAIM marker and a 700-char look-back silenced it, which is exactly
# the kind of false negative that makes a validator worse than none.
# The opening quote must not be a possessive apostrophe: in "rapamycin's
# mammalian lifespan extension ... previously read 'No study tests whether...'"
# a naive pairing joins the apostrophe in "rapamycin's" to the real opening
# quote and swallows the whole correction, so nothing gets suppressed.
_QUOTED = re.compile(r"(?<![A-Za-z])'[^']{10,400}'(?![A-Za-z])")


def in_correction_log(text, pos, back=350):
    """True if pos falls inside a quotation that a correction marker introduces,
    i.e. the match is superseded wording being logged, not a live claim."""
    for q in _QUOTED.finditer(text):
        if q.start() < pos < q.end():
            if CORRECTION_MARKER.search(text[max(0, q.start() - back):q.start()]):
                return True
    return False


# Abbreviations that must not end a sentence when splitting prose. Without this,
# "8 mg/kg/day i.p. x 90 days" splits after "i.p." and orphans the figures from
# the study code that introduced them.
_ABBREV = re.compile(r"\\b(i\\.p|i\\.v|e\\.g|i\\.e|vs|cf|approx|etc|Fig|no|ca)\\.",
                     re.I)


def split_sentences(text):
    """Sentence split that survives common scientific abbreviations. Returns
    (sentence, start_offset) pairs so callers can look at surrounding context."""
    guarded = _ABBREV.sub(lambda m: m.group(0).replace(".", "\\x00"), text)
    out, pos = [], 0
    for part in re.split(r"(?<=[.!?])\\s+", guarded):
        out.append((part.replace("\\x00", "."), pos))
        pos += len(part) + 1
    return out

'''

OLD_R8 = '''                pre = basis[max(0, m.start() - 200):m.start()]
                if re.search(r"previously read|CORRECTION LOG|already false", pre, re.I):
                    continue'''
NEW_R8 = '''                if in_correction_log(basis, m.start()):
                    continue'''

OLD_R9 = '''        # R9 -- every numeral in a gap's basis needs a nearby study code.
        for sent in re.split(r"(?<=[.!?])\\s+", basis):
            if NUMERAL.search(sent) and not CODE.search(sent):
                add(findings, "WARN", "R9 number-without-code", "gap:%s.basis" % gid, sent,
                    "Sentence carries a number with no study code in the same sentence.",
                    "Attach the supporting study code next to the figure.")'''

NEW_R9 = '''        # R9 -- every numeral in a gap's basis needs a NEARBY study code.
        # "Nearby" is deliberately not "in the same sentence": a code is
        # normally attached once and then carried by the clauses that follow
        # ("QUANTIFIED: BIT2016 ... males +60% ... females p=0.261"). Requiring
        # it per sentence flagged ordinary prose. The window is the sentence
        # plus the preceding 400 characters of the same basis.
        for sent, off in split_sentences(basis):
            if not NUMERAL.search(sent):
                continue
            window = basis[max(0, off - 400):off + len(sent)]
            if CODE.search(window):
                continue
            if in_correction_log(basis, off):
                continue
            add(findings, "WARN", "R9 number-without-code", "gap:%s.basis" % gid, sent,
                "Figure with no study code anywhere near it: nothing in this "
                "sentence or the preceding context says which study it comes from.",
                "Attach the supporting study code next to the figure.")'''

OLD_R12 = '''        for m in list(ABSENCE_WORD.finditer(basis)) + list(ABSENCE_PHRASE.finditer(basis)):
            window = basis[max(0, m.start() - 120):m.end() + 120]
            if not SCOPE_PHRASE.search(window):'''

NEW_R12 = '''        for m in list(ABSENCE_WORD.finditer(basis)) + list(ABSENCE_PHRASE.finditer(basis)):
            window = basis[max(0, m.start() - 120):m.end() + 120]
            # A superseded absolute quoted inside a correction log is the audit
            # trail, not a live claim.
            if in_correction_log(basis, m.start()):
                continue
            if not SCOPE_PHRASE.search(window):'''


def main():
    if not os.path.exists(VC):
        sys.exit("ABORT: validate_claims.py not found -- run from the repo root.")
    src = open(VC, encoding="utf-8").read()
    before = len(src)
    changed = []

    if "def in_correction_log(" not in src:
        anchor = "\ndef load_atlas_gaps("
        if anchor not in src:
            sys.exit("ABORT: anchor load_atlas_gaps() not found; patch by hand.")
        src = src.replace(anchor, "\n" + HELPER.strip("\n") + "\n\n" + anchor.lstrip("\n"), 1)
        changed.append("added in_correction_log() + split_sentences() helpers")

    for label, old, new in (("R8 uses shared helper", OLD_R8, NEW_R8),
                            ("R9 nearby-code window + abbreviation-safe split", OLD_R9, NEW_R9),
                            ("R12 skips correction logs", OLD_R12, NEW_R12)):
        if new.strip().splitlines()[0] in src and old not in src:
            continue  # already applied
        if old not in src:
            sys.exit("ABORT: could not find the block for %r.\n"
                     "       validate_claims.py has changed; patch by hand." % label)
        src = src.replace(old, new, 1)
        changed.append(label)

    if not changed:
        print("validate_claims.py: already patched, nothing to do")
        return
    for c in changed:
        print("   - " + c)

    try:
        compile(src, VC, "exec")
    except SyntaxError as e:
        sys.exit("ABORT: patched validate_claims.py does not compile: %s" % e)
    for need in ("def in_correction_log(", "def split_sentences(", "CORRECTION_MARKER"):
        if need not in src:
            sys.exit("ABORT: patch incomplete, %s missing" % need)

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
