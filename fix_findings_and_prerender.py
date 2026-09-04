#!/usr/bin/env python3
"""
fix_findings_and_prerender.py -- two things sync_airtable.py cannot do.

1. ATLAS_FINDINGS is hardcoded in index.html (there is no Airtable table for it).
   Its first finding still carries the H1 "ZERO longevity / aging outcomes" claim
   that was corrected in Airtable on 2026-08-30. Patched here.

2. The <!--PRERENDER:questionsView--> block is a static copy of renderGaps()'s
   output, baked for crawlers, AI readers and no-JS clients. Nothing in the repo
   regenerates it, so after a sync the JS array is correct while the prerendered
   HTML still shows the old text. This rebuilds it from ATLAS_GAPS +
   ATLAS_FINDINGS, mirroring renderGaps() exactly at the 'student' register.

Run AFTER sync_airtable.py, BEFORE committing.

    py fix_findings_and_prerender.py            # writes index.html
    py fix_findings_and_prerender.py --dry-run  # prints what would change

Standard library only.
"""
import json, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
HTML = os.path.join(HERE, "index.html")
DRY = "--dry-run" in sys.argv

OLD_FINDING_P = (
    "Every amino-acid sensor and upstream regulator (Sestrin2, CASTOR1, SAMTOR, "
    "Rag GTPases, GATOR1/2, Ragulator, Rheb, PRAS40, AMPK) rests only on tier-D "
    "mechanistic evidence - and the sensors link to ZERO longevity / aging outcomes. "
    "The most drug-specific part of the pathway is phenotype-untested."
)
NEW_FINDING_P = (
    "Every amino-acid sensor and upstream regulator (Sestrin2, CASTOR1, SAMTOR, "
    "Rag GTPases, GATOR1/2, Ragulator, Rheb, PRAS40, AMPK) rests almost entirely on "
    "tier-D mechanistic evidence, and exactly one of them - Sestrin2 - links to an "
    "organismal ageing phenotype at all (LEE2010, Drosophila, tier C; carried as the "
    "SESN2-AGING edge). No mammalian lifespan and no human ageing endpoint exists for "
    "any sensor. The most drug-specific part of the pathway is very nearly phenotype-untested."
)

OLD_FINDING_B = (
    "The molecules that directly sense nutrients \u2014 Sestrin2, CASTOR1, SAMTOR, the Rag "
    "proteins and others \u2014 are only backed by lab/mechanism-level studies. Not one of "
    "them has been tested for whether blocking it actually changes lifespan or ageing. "
    "These are exactly the parts a drug could most precisely target, and nobody has "
    "checked yet."
)
NEW_FINDING_B = (
    "The molecules that directly sense nutrients \u2014 Sestrin2, CASTOR1, SAMTOR, the Rag "
    "proteins and others \u2014 are almost entirely backed by lab/mechanism-level studies. "
    "Only one, Sestrin2, has ever been linked to an ageing phenotype in a living animal, "
    "and that was in fruit flies. Nothing similar exists in a mammal, let alone a person. "
    "These are exactly the parts a drug could most precisely target, and they are barely tested."
)


def esc_js_str(s):
    """Read a JS double-quoted string out of the source the way json does."""
    return json.loads('"' + s.replace('"', '\\"') + '"') if False else s


def patch_findings(h):
    """ATLAS_FINDINGS is JS-object literal, not JSON, so patch by exact substring."""
    hits = 0
    for old, new in ((OLD_FINDING_P, NEW_FINDING_P), (OLD_FINDING_B, NEW_FINDING_B)):
        if old in h:
            h = h.replace(old, new, 1)
            hits += 1
        else:
            print("  ! ATLAS_FINDINGS: source string not found, skipping one replacement")
    print("ATLAS_FINDINGS: %d/2 strings replaced" % hits)
    return h


def read_gaps(h):
    m = re.search(r"const ATLAS_GAPS = (\[.*?\]);", h, re.S)
    if not m:
        sys.exit("ABORT: ATLAS_GAPS not found in index.html")
    return json.loads(m.group(1))


def read_findings(h):
    """ATLAS_FINDINGS uses unquoted keys, so pull the two fields with a regex."""
    m = re.search(r"const ATLAS_FINDINGS = \[(.*?)\];\n", h, re.S)
    if not m:
        sys.exit("ABORT: ATLAS_FINDINGS not found in index.html")
    out = []
    for block in re.finditer(r"\{h:(\".*?\"), p:(\".*?\"), p_beginner:(\".*?\")\}", m.group(1), re.S):
        out.append({
            "h": json.loads(block.group(1)),
            "p": json.loads(block.group(2)),
            "p_beginner": json.loads(block.group(3)),
        })
    if not out:
        sys.exit("ABORT: could not parse any ATLAS_FINDINGS entries")
    return out


def build_prerender(gaps, findings):
    """Mirror of renderGaps() at the default 'student' register (lv() -> fallback)."""
    find = "".join(
        '<div class="gf"><h4><span class="ep ep-interp">Interpretation</span>'
        + f["h"] + '</h4><p>' + f["p"] + '</p></div>'
        for f in findings
    )
    ordered = sorted(gaps, key=lambda g: int(re.sub(r"\D", "", g.get("id", "")) or 0))
    cards = []
    for g in ordered:
        chips = "".join(
            '<span class="study-chip" onclick="goStudy(\'%s\')">%s</span>' % (c, c)
            for c in g.get("studies", [])
        )
        cards.append(
            '<div class="gap-card"><div class="gc-head"><span class="gc-id">' + g["id"] + '</span>'
            + '<span class="gc-title">' + g["title"] + '</span><span class="gc-type">' + g["type"] + '</span>'
            + '<span class="gap-conf">confidence %.2f</span></div>' % float(g.get("conf") or 0)
            + '<div class="gc-body">'
            + '<div class="gc-row"><div class="gc-k"><span class="ep ep-fact">Established</span>'
              'Why it is a gap (evidence basis)</div><div class="gc-v">' + g["basis"] + '</div></div>'
            + '<div class="gc-row"><div class="gc-k"><span class="ep ep-hyp">Editorial hypothesis</span>'
              'What might be true</div><div class="gc-hyp">' + g["hyp"]
            + '<div class="gc-warn">Not established by anyone. This is a proposal generated by this '
              'Atlas &mdash; do not cite it as a finding.</div></div></div>'
            + '<div class="gc-row"><div class="gc-k"><span class="ep ep-hyp">Editorial hypothesis</span>'
              'Proposed experiment &mdash; not yet run</div><div class="gc-v">' + g["exp"] + '</div></div>'
            + '<div class="gc-row"><div class="gc-k">Supporting studies</div>'
              '<div class="gc-studies">' + chips + '</div></div>'
            + '</div></div>'
        )
    return (
        '<div class="atlas-section-head"><div class="ase-eyebrow">Oliver\'s mTOR Atlas &middot; '
        '<b>Open Questions</b></div><h2 class="ase-title">Where the evidence runs out.</h2></div>'
        '<div class="oq-intro"><h3>What we don&rsquo;t know &mdash; and why</h3>'
        '<p><b>How to read these, and how not to.</b> Gaps here are computed against <em>this corpus</em>, '
        'not against the literature. A gap means the Atlas holds no linking study &mdash; which may mean '
        'none exists, or may mean the corpus is incomplete. That distinction is not cosmetic: gap H1 '
        'originally claimed the amino-acid sensors link to zero ageing outcomes, and an external review '
        'found a 2010 <i>Science</i> paper that did exactly that. It has since been added and the gap '
        'narrowed. Treat every gap below as a hypothesis about the evidence, testable by finding the '
        'paper that closes it.</p>'
        '<p>A pathway map shows what is known. This section is the opposite: gaps surfaced automatically '
        'by joining the Atlas&rsquo;s entity graph to each study&rsquo;s evidence tier (A&gt;B&gt;C&gt;D). '
        'Two structural findings, then ' + str(len(ordered)) + ' testable hypotheses &mdash; each anchored '
        'to the studies that define the gap. Click any study code to open it.</p>'
        '<div class="ep-legend">'
        '<p class="ttl">Every block below is labelled by what kind of claim it is</p>'
        '<p class="item"><span class="ep ep-fact">Established</span> What the corpus actually contains: '
        'published, peer-reviewed results and the tier structure over them. Checkable against the cited '
        'studies.</p>'
        '<p class="item"><span class="ep ep-interp">Interpretation</span> A reading of what those results '
        'mean together. The underlying findings are solid; the joining-up is a judgement, and other '
        'readings are possible.</p>'
        '<p class="item"><span class="ep ep-hyp">Editorial hypothesis</span> Not established by anyone. '
        'A proposal generated by this Atlas about what might be true and how it could be tested. '
        '<b>Nothing carrying this label has been demonstrated.</b> Do not cite it as a finding. The '
        'confidence number on each card is the curator&rsquo;s subjective prior that the hypothesis is '
        'worth testing &mdash; not a probability that it is true, and not a statistic.</p>'
        '</div></div>'
        '<div class="gap-finding">' + find + '</div>'
        + "".join(cards)
    )


def main():
    h = open(HTML, encoding="utf-8").read()
    before = len(h)

    h = patch_findings(h)

    gaps = read_gaps(h)
    findings = read_findings(h)
    block = build_prerender(gaps, findings)

    open_tag, close_tag = "<!--PRERENDER:questionsView-->", "<!--/PRERENDER:questionsView-->"
    pat = re.compile(re.escape(open_tag) + ".*?" + re.escape(close_tag), re.S)
    if not pat.search(h):
        sys.exit("ABORT: PRERENDER:questionsView markers not found -- nothing written.")
    h = pat.sub(lambda m: open_tag + block + close_tag, h, count=1)
    print("PRERENDER:questionsView: rebuilt (%d gaps, %d findings, %d chars)"
          % (len(gaps), len(findings), len(block)))

    # Sanity gates before touching the file.
    # The Atlas's own correction logs QUOTE the superseded wording ("this block
    # previously read ..."), so a bare substring test fires on the audit trail
    # itself. An occurrence only counts as a live claim when no correction
    # marker sits near it. Fixed 2026-09-04 after this gate produced four false
    # positives on a correct build.
    markers = ("CORRECTION", "WITHDRAWN", "previously read", "previously cited",
               "previously carried", "SCOPE (", "WORDING CORRECTION",
               "BENEFIT-SIDE CORRECTION", "DOSE QUALIFIER", "QUALIFIED (")
    live, logged = [], 0
    for bad in ("links to ZERO aging/longevity outcomes",
                "links to ZERO longevity / aging outcomes",
                "RADIANT-3 PFS 5% vs 2%",
                "Nrf2-KO fibroblasts WITHOUT activating autophagy",
                "ARA2009 mTOR drives memory-CD8 differentiation"):
        start = 0
        while True:
            i = h.find(bad, start)
            if i < 0:
                break
            start = i + len(bad)
            window = h[max(0, i - 700): start + 400]
            if any(k in window for k in markers):
                logged += 1
            else:
                live.append(bad)
    if live:
        sys.exit("ABORT: corrected-away string present as a LIVE claim in "
                 "index.html: %r\n"
                 "       Did you run sync_airtable.py first?" % live[0])
    if logged:
        print("sanity: %d superseded string(s) found, all inside correction "
              "logs - correct" % logged)
    if not h.rstrip().endswith("</html>"):
        sys.exit("ABORT: output does not end in </html>")

    print("size: %d -> %d bytes" % (before, len(h)))
    if DRY:
        print("--dry-run: nothing written.")
        return
    tmp = HTML + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(h)
    if open(tmp, encoding="utf-8").read() != h:
        sys.exit("ABORT: verification read-back mismatch, index.html untouched.")
    os.replace(tmp, HTML)
    print("index.html rewritten and verified.")


if __name__ == "__main__":
    main()
