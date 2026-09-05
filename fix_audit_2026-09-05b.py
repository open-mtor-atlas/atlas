#!/usr/bin/env python3
"""
fix_audit_2026-09-05b.py

Fixes the findings of the 2026-09-05 audit round that live in code or content
files. The remaining finding (B1, stale ATLAS_GAPS) needs no patch -- it is a
missed sync_airtable.py run.

A1  CATEGORY 1 -- Academy routes SAMTOR through GATOR2
    academy_data/lessons.json + build_academy.py

    Lesson 06 (Nutrient Sensing) presents three sensors as one symmetry: "The
    arginine row is the same shape with CASTOR1 in place of Sestrin2, and the
    SAM row the same again with SAMTOR", and fig_aa_sensors() draws all three
    feeding a shared bus into GATOR2.

    SAMTOR does not act on GATOR2. Gu et al., Science 2017 (PMID 29123071,
    doi:10.1126/science.aao3265): SAMTOR "inhibits mTORC1 signaling by
    interacting with GATOR1, the GTPase activating protein for RagA/B", and SAM
    binds SAMTOR with a Kd of ~7 uM to disrupt the SAMTOR-GATOR1 complex.
    Sestrin2 and CASTOR1 bind GATOR2; SAMTOR binds GATOR1, one node further
    down, with a different number of inhibitory steps behind it.

    The Atlas's own pathway model already has this right -- SAMTOR-GATOR1,
    "Methionine-starved SAMTOR binds the GATOR1-KICSTOR complex" -- so the
    lesson contradicted the map it teaches. It is also the same error that was
    found in MAP_CORE_EDGES on 2026-08-30 and deleted with that array on
    2026-09-04; it survived here.

    The diagram is redrawn rather than relabelled: two rows into GATOR2, and a
    separate SAMTOR row entering GATOR1 directly. The asymmetry is the teaching
    point, not a blemish to hide.

B2  CATEGORY 2 -- static homepage hero carries hardcoded counts
    index.html + stamp_updated.py

    The SEO hero says "curates 356 peer-reviewed primary studies" against a
    corpus of 357, and states node/interaction/route counts as bare text. None
    of the four is in a span refresh_counts can stamp, so all four drift on
    every corpus change. This block exists specifically so that crawlers and AI
    readers see real content without JS, which is exactly where a wrong number
    travels furthest. The four figures are wrapped in spans and stamped, with
    the pathway numbers read from pathway/model.json.

C1  CATEGORY 3 -- glossary overstates Rheb
    generate.py

    "directly activates mTORC1 at the lysosomal membrane ... The final switch"
    asserts a compartment the Atlas itself records as unsettled (see
    open_localisations in pathway/model.json) and reads as more absolute than
    the evidence. Softened to match the model.

    Note: the mTORC2 glossary entry was also flagged during the audit for
    missing the chronic-dosing caveat. It is not missing -- the rendered snippet
    was truncated mid-sentence. No change made.

Run from the repo root, then rebuild:

    py fix_audit_2026-09-05b.py --dry-run
    py fix_audit_2026-09-05b.py
    py sync_airtable.py          # also picks up the stale gap text (finding B1)
    py build_academy.py
    py generate.py
    py verify_atlas_build.py
    py validate_claims.py

Idempotent. Standard library only.
"""
import json, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
DRY = "--dry-run" in sys.argv
changed_files = []


def rewrite(path, old, new, label):
    if not os.path.exists(path):
        sys.exit("ABORT: %s not found -- run from the repo root." % path)
    src = open(path, encoding="utf-8").read()
    if new in src:
        print("   - %s: already applied" % label)
        return False
    if src.count(old) != 1:
        sys.exit("ABORT: %s -- expected exactly 1 match, found %d. Patch by hand."
                 % (label, src.count(old)))
    src = src.replace(old, new, 1)
    if not DRY:
        tmp = path + ".tmp"
        open(tmp, "w", encoding="utf-8").write(src)
        if open(tmp, encoding="utf-8").read() != src:
            sys.exit("ABORT: read-back mismatch on %s" % path)
        os.replace(tmp, path)
    changed_files.append(path)
    print("   - %s: patched" % label)
    return True


# ---------------------------------------------------------------- A1 prose ---
L_OLD_1 = ("The answer that emerged is a set of dedicated binding proteins, one per "
           "nutrient, feeding into a shared relay.")
L_NEW_1 = ("The answer that emerged is a set of dedicated binding proteins, one per "
           "nutrient, feeding into the same relay \\u2014 though not all of them at the "
           "same point.")

L_OLD_2 = ("The arginine row is the same shape with CASTOR1 in place of Sestrin2, and "
           "the SAM row the same again with SAMTOR. Three chemically unrelated small "
           "molecules, three unrelated binding proteins, one shared relay.")
L_NEW_2 = ("The arginine row is the same shape with CASTOR1 in place of Sestrin2. The "
           "SAM row is <strong>not</strong> the same shape, and the difference is worth "
           "knowing: SAMTOR does not act on GATOR2 at all. When SAM is scarce, SAMTOR "
           "binds GATOR1 \\u2014 together with KICSTOR \\u2014 and helps it keep mTORC1 "
           "off; SAM binding to SAMTOR breaks that interaction. Methionine status "
           "therefore enters the same relay one node further down than leucine and "
           "arginine do, with one inhibitory step fewer behind it. Three chemically "
           "unrelated small molecules, three unrelated binding proteins, one relay "
           "entered at two different points.")

# --------------------------------------------------------------- A1 figure ---
F_OLD_MARK = 'rows = [("Leucine", "Sestrin2"), ("Arginine", "CASTOR1"),\n            ("S-adenosyl-methionine", "SAMTOR")]'

F_NEW_FUNC = '''rows = [("Leucine", "Sestrin2"), ("Arginine", "CASTOR1")]'''


def patch_figure():
    """Redraw fig_aa_sensors: SAMTOR enters GATOR1, not the GATOR2 bus."""
    path = os.path.join(HERE, "build_academy.py")
    src = open(path, encoding="utf-8").read()
    if "SAMTOR enters at GATOR1" in src:
        print("   - build_academy.py fig_aa_sensors: already applied")
        return False
    start = src.find("def fig_aa_sensors():")
    if start < 0:
        sys.exit("ABORT: fig_aa_sensors() not found in build_academy.py")
    end = src.find("\ndef ", start + 10)
    if end < 0:
        sys.exit("ABORT: could not find the end of fig_aa_sensors()")

    new_fn = '''def fig_aa_sensors():
    """Lekce 06. Dvojity zapor je cela pointa: senzor VAZE aminokyselinu a tim
    PRESTANE inhibovat. Kresli se proto jako retez kolmicek, ne sipek.

    SAMTOR enters at GATOR1, not at GATOR2 (opraveno 2026-09-05). Gu 2017:
    SAMTOR inhibuje mTORC1 vazbou na GATOR1/KICSTOR, ne na GATOR2 jako Sestrin2
    a CASTOR1. Drivejsi verze kreslila vsechny tri senzory do jedne sbernice do
    GATOR2, coz odporovalo i vlastnimu pathway modelu Atlasu (SAMTOR-GATOR1).
    Asymetrie je tady poucka, ne vada obrazku."""
    rows = [("Leucine", "Sestrin2"), ("Arginine", "CASTOR1")]
    g = []
    ys = []
    for i, (aa, sensor) in enumerate(rows):
        y = 14 + i * 46
        ys.append(y + 15)
        g.append('<rect class="ac-box" x="4" y="%d" width="150" height="30" rx="3"/>'
                 '<text class="ac-t" x="79" y="%d">%s</text>' % (y, y + 20, aa))
        g.append('<path class="ac-arrow ac-thin" d="M158 %d H186" marker-end="url(#acArrow)"/>'
                 % (y + 15))
        g.append('<rect class="ac-box" x="190" y="%d" width="118" height="30" rx="3"/>'
                 '<text class="ac-t" x="249" y="%d">%s</text>' % (y, y + 20, sensor))
        g.append('<path class="ac-inh" d="M312 %d H336"/>' % (y + 15))
    mid = (ys[0] + ys[1]) // 2
    # spolecna sbernice do GATOR2 -- jen leucin a arginin
    g.append('<path class="ac-inh" d="M336 %d V%d"/>' % (ys[0], ys[1]))
    g.append('<path class="ac-inh" d="M336 %d H354"/>' % mid)
    g.append('<rect class="ac-box" x="358" y="%d" width="112" height="46" rx="3"/>'
             '<text class="ac-t" x="414" y="%d">GATOR2</text>'
             '<text class="ac-t ac-sub" x="414" y="%d">bound = inhibited</text>'
             % (mid - 23, mid - 3, mid + 13))
    g.append('<path class="ac-inh" d="M474 %d H498"/><path class="ac-inh" d="M498 %d V%d"/>'
             % (mid, mid - 9, mid + 9))
    g.append('<rect class="ac-box" x="506" y="%d" width="112" height="46" rx="3"/>'
             '<text class="ac-t" x="562" y="%d">GATOR1</text>'
             '<text class="ac-t ac-sub" x="562" y="%d">GAP for RagA/B</text>'
             % (mid - 23, mid - 3, mid + 13))
    g.append('<path class="ac-inh" d="M622 %d H646"/><path class="ac-inh" d="M646 %d V%d"/>'
             % (mid, mid - 9, mid + 9))
    g.append('<rect class="ac-box ac-accent" x="654" y="%d" width="104" height="46" rx="3"/>'
             '<text class="ac-t" x="706" y="%d">Rag</text>'
             '<text class="ac-t ac-sub" x="706" y="%d">active state</text>'
             % (mid - 23, mid - 3, mid + 13))
    # SAM radek vstupuje o uzel niz -- primo na GATOR1
    sy = 14 + 2 * 46 + 15
    g.append('<rect class="ac-box" x="4" y="%d" width="150" height="30" rx="3"/>'
             '<text class="ac-t" x="79" y="%d">S-adenosyl-methionine</text>'
             % (sy - 15, sy + 5))
    g.append('<path class="ac-inh" d="M158 %d H186"/>' % sy)
    g.append('<rect class="ac-box" x="190" y="%d" width="118" height="30" rx="3"/>'
             '<text class="ac-t" x="249" y="%d">SAMTOR</text>' % (sy - 15, sy + 5))
    g.append('<path class="ac-arrow" d="M312 %d H562 V%d" marker-end="url(#acArrow)"/>'
             % (sy, mid + 27))
    g.append('<text class="ac-t ac-sub" x="330" y="%d">no SAM: SAMTOR helps GATOR1 '
             'keep mTORC1 off</text>' % (sy + 18))
    g.append('<text class="ac-t ac-sub" x="4" y="200">count the blunt ends: an amino acid '
             'present means one more inhibition released, not one more push. '
             'Methionine enters one node further down.</text>')
    return _svg("0 0 768 212", "".join(g),
                "Leucine binds Sestrin2 and arginine binds CASTOR1; each bound sensor "
                "stops inhibiting GATOR2, which inhibits GATOR1, the GAP that switches "
                "the Rag GTPases off. S-adenosylmethionine acts on a different node: "
                "without it SAMTOR binds GATOR1 and helps keep mTORC1 off, and SAM "
                "binding to SAMTOR breaks that interaction.")

'''
    src = src[:start] + new_fn + src[end + 1:]
    try:
        compile(src, path, "exec")
    except SyntaxError as e:
        sys.exit("ABORT: patched build_academy.py does not compile: %s" % e)
    if not DRY:
        tmp = path + ".tmp"
        open(tmp, "w", encoding="utf-8").write(src)
        os.replace(tmp, path)
    changed_files.append(path)
    print("   - build_academy.py fig_aa_sensors: redrawn")
    return True


# ------------------------------------------------------------------ B2 hero ---
H_OLD = ("curates 356 peer-reviewed primary studies")
H_NEW = ('curates <span id="shStudyCount">356</span> peer-reviewed primary studies')
H_OLD_2 = ("covers 88 molecular nodes and 119 evidence-linked\ninteractions across "
           "11 guided routes")
H_NEW_2 = ('covers <span id="shNodeCount">88</span> molecular nodes and '
           '<span id="shEdgeCount">119</span> evidence-linked\ninteractions across '
           '<span id="shRouteCount">11</span> guided routes')

S_OLD = '''        (r'(<span id="atlasStatEntities">)\\d+(</span>)', r"\\g<1>%d\\g<2>" % n_entities),
    ]'''
S_NEW = '''        (r'(<span id="atlasStatEntities">)\\d+(</span>)', r"\\g<1>%d\\g<2>" % n_entities),
        (r'(<span id="shStudyCount">)\\d+(</span>)', r"\\g<1>%d\\g<2>" % n_studies),
    ]
    # The static SEO hero (2026-09-05) states pathway figures as bare prose. It
    # exists so that crawlers and AI readers see real content without JS, which
    # is precisely where a stale number travels furthest -- it said 356 against a
    # corpus of 357 within a day of being written. Read from the model itself.
    try:
        _pm = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                          "pathway", "model.json"), encoding="utf-8"))
        subs += [
            (r'(<span id="shNodeCount">)\\d+(</span>)',
             r"\\g<1>%d\\g<2>" % len(_pm["nodes"])),
            (r'(<span id="shEdgeCount">)\\d+(</span>)',
             r"\\g<1>%d\\g<2>" % len(_pm["interactions"])),
            (r'(<span id="shRouteCount">)\\d+(</span>)',
             r"\\g<1>%d\\g<2>" % len(_pm["routes"])),
        ]
    except Exception as _e:
        print("  refresh_counts: pathway/model.json unreadable (%s) - hero pathway "
              "figures left alone" % _e)'''

# -------------------------------------------------------------- C1 glossary ---
G_OLD = ('"A small GTPase that directly activates mTORC1 at the lysosomal membrane once "\n'
         '     "TSC1/TSC2\'s inhibitory brake is released. The final switch mTORC1\'s upstream "\n'
         '     "signals converge on."')
G_NEW = ('"A small GTPase that directly activates mTORC1 once TSC1/TSC2\'s inhibitory "\n'
         '     "brake is released \\u2014 the step the growth-factor inputs converge on. "\n'
         '     "Which membrane the activating pool sits on is not settled; the Atlas "\n'
         '     "records that as an open question rather than asserting the lysosome."')


def main():
    print("A1  Academy: SAMTOR routed through GATOR2 (Category 1)")
    lp = os.path.join(HERE, "academy_data", "lessons.json")
    rewrite(lp, L_OLD_1, L_NEW_1.encode().decode("unicode_escape"), "lessons.json intro")
    rewrite(lp, L_OLD_2, L_NEW_2.encode().decode("unicode_escape"), "lessons.json SAM row")
    patch_figure()
    if not DRY and os.path.exists(lp):
        json.load(open(lp, encoding="utf-8"))          # must still be valid JSON
        print("   - lessons.json still parses")

    print("B2  Static hero: hardcoded counts (Category 2)")
    ip = os.path.join(HERE, "index.html")
    rewrite(ip, H_OLD, H_NEW, "index.html study count")
    rewrite(ip, H_OLD_2, H_NEW_2, "index.html pathway counts")
    sp = os.path.join(HERE, "stamp_updated.py")
    rewrite(sp, S_OLD, S_NEW, "stamp_updated.py refresh_counts")
    if not DRY:
        compile(open(sp, encoding="utf-8").read(), sp, "exec")
        print("   - stamp_updated.py compiles")

    print("C1  Glossary: Rheb overstated (Category 3)")
    gp = os.path.join(HERE, "generate.py")
    rewrite(gp, G_OLD, G_NEW.encode().decode("unicode_escape"), "generate.py Rheb entry")
    if not DRY:
        compile(open(gp, encoding="utf-8").read(), gp, "exec")
        print("   - generate.py compiles")

    print("\n%d file(s) %s" % (len(set(changed_files)),
                               "would change" if DRY else "changed"))
    if DRY:
        print("--dry-run: nothing written.")
    else:
        print("\nNow rebuild:  py sync_airtable.py && py build_academy.py && py generate.py")
        print("sync_airtable.py also fixes finding B1 (ATLAS_GAPS two days stale).")


if __name__ == "__main__":
    main()
