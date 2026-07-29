#!/usr/bin/env python3
"""
validate_claims.py -- scientific-calibration linter for Oliver's mTOR Atlas.

PROC TOHLE EXISTUJE
-------------------
Kazde tvrzeni v Atlasu ma byt formulovano tak silne, jak silny je dukaz za nim
-- ne silneji. Tenhle skript to kontroluje strojove, aby se prehnana formulace
nedostala na web pri pristim syncu z Airtable.

Neni to nahrada za redakcni usudek. Skript nezna vyznam vety; zna jen dvojici
(sila tvrzeni, design studie) a upozorni, kdyz spolu nesedi. Vysledek je
seznam k rozhodnuti, ne automaticka oprava.

    py validate_claims.py                 # zkontroluje vse, vypise nalezy
    py validate_claims.py --strict        # exit 1 pri ERROR (pro deploy gate)
    py validate_claims.py --json out.json # strojove citelny report

VSTUP   atlas_data/studies_baked.json, index.html (ATLAS_GAPS / ATLAS_RELATIONS
        / ATLAS_ENTITIES + rucne psana proza), atlas_data/entities_baked.json
VYSTUP  textovy report; s --strict navic navratovy kod

PRAVIDLA (viz RULES nize)
  R1  nekontrolovana / oteviena Phase I nebo single-arm studie popsana jako
      definitivni potvrzeni
  R2  observacni studie popsana jako dukaz kauzality
  R3  mechanisticka / in vitro / zvireci prace popsana jako klinicky dukaz
  R4  preprint / registered trial / narrative review s A-D tierem
  R5  absolutni jazyk kdekoli (proves / definitive / settles / avoids ...)
  R6  A-D tier prirazen praci, ktera stoji mimo hierarchii (konzistence
      Pyramid_Level <-> Evidence_Tier)
"""

import os, re, sys, json, html

HERE = os.path.dirname(os.path.abspath(__file__))
STUDIES = os.path.join(HERE, "atlas_data", "studies_baked.json")
INDEX = os.path.join(HERE, "index.html")

STRICT = "--strict" in sys.argv
JSON_OUT = None
if "--json" in sys.argv:
    i = sys.argv.index("--json")
    JSON_OUT = sys.argv[i + 1] if len(sys.argv) > i + 1 else "claim_validation.json"


# ---------------------------------------------------------------- vocabularies

# Absolutni jazyk. Klic = regex, hodnota = navrhovana nahrada.
ABSOLUTE = {
    r"\bprove[sd]?\b": "show / support",
    r"\bproven\b": "supported",
    r"\bproof\b": "evidence",
    r"\bdefinitiv(e|ely)\b": "landmark / strongest available",
    r"\bconclusiv(e|ely)\b": "consistent with",
    r"\bunequivocal(ly)?\b": "clear",
    r"\bbeyond doubt\b": "well supported",
    r"\bsettle[sd]?\b": "address / weigh in on",
    r"\bestablishes? (that|beyond)\b": "supports that",
    r"\bdirect (clinical )?confirmation\b": "evidence consistent with",
    r"\bempirically confirming\b": "consistent with",
    r"\bguarantee[sd]?\b": "makes likely",
}

# Slabsi, ale kontextove citliva slovesa -- flagujeme jen u slabych designu.
CAUSAL = {
    r"\bconfirm(s|ed|ing|ation)\b": "is consistent with",
    r"\bavoids?\b": "reduces / spares (with species + design scope)",
    r"\bcauses?\b": "drives / is associated with (scope the model)",
    r"\bdemonstrat(es|ed|ing)\b": "supports / shows",
}

# Vyrazy, ktere signalizuji klinicky/lidsky zaver.
CLINICAL_LANG = re.compile(
    r"\b(in patients|clinically|clinical (confirmation|evidence|benefit|proof)|"
    r"therapeutic target|treats? a human|in humans|human (proof|confirmation))\b", re.I)

# Design markery
UNCONTROLLED = re.compile(
    r"\b(phase\s*(1|i)\b|first-in-human|open-label|single-arm|dose[- ]escalation|"
    r"uncontrolled|no comparator)\b", re.I)
CONTROLLED = re.compile(r"\b(randomi[sz]ed|randomi[sz]ation|\bRCT\b|placebo|"
                        r"double-blind|controlled trial|phase\s*(3|iii)\b)", re.I)
OBSERVATIONAL = re.compile(
    r"\b(retrospective|prospective cohort|cohort study|observational|"
    r"case[- ]control|cross[- ]sectional|registry|epidemiolog)", re.I)

# DVE OSY, NEZAMENOVAT.
#   Pyramid_Level = TYP studie. Narrative Review / Preprint / Registered Trial
#                   stoji mimo pyramidu 1-5.
#   Evidence_Tier = SILA dukazu pro tvrzeni o lidskem zdravi. Tier D je z
#                   definice "mechanistic / in vitro / theoretical / narrative
#                   review", takze narativni prehled tier D dostava zamerne --
#                   je to nejslabsi stupen, ne chyba.
# Mimo A-D hierarchii proto stoji jen prace, ktere jeste neprosly recenzi nebo
# nemaji vysledky: preprinty a registrovane studie. Ty A-D tier dostat nesmi.
OUT_OF_HIERARCHY_PYRAMID = {"Preprint", "Registered Trial"}
AD_TIERS = ("A -", "B -", "C -", "D -")

# Slova, kde "cause" neni kauzalni sloveso.
NOT_CAUSAL_CONTEXT = re.compile(r"(all-cause|the cause|root cause|underlying cause|"
                                r"a cause of death|cause of)", re.I)
# Negace v okoli 70 znaku pred nalezem ruzi tvrzeni misto aby ho posilovala.
NEGATION = re.compile(r"\b(not|never|no|nor|without|lacking|absent|yet to|fails? to|"
                      r"cannot|can't|isn't|is not|does not|did not|unable to|"
                      r"rather than|instead of)\b", re.I)

# Kategorie, ktere NEJSOU lidsky dukaz.
NONHUMAN_TIERS = ("C -", "D -")


# ---------------------------------------------------------------- helpers

def add(findings, sev, rule, where, text, msg, fix=None):
    findings.append({
        "severity": sev, "rule": rule, "where": where,
        "excerpt": (text or "")[:300].replace("\n", " ").strip(),
        "message": msg, "suggested": fix,
    })


def negated(text, start):
    """True if the match at `start` sits inside a negation, e.g. 'not proven',
    'no OS benefit demonstrated', 'benefit not yet established'. Negated use of
    a strong word is the cautious use -- flagging it would push the Atlas
    toward hedging its own null results, which is the opposite of the goal."""
    pre = text[max(0, start - 70):start]
    post = text[start:start + 40]
    return bool(NEGATION.search(pre) or NEGATION.search(post))


def scan_absolute(findings, where, text, sev="ERROR"):
    if not text:
        return
    for pat, fix in ABSOLUTE.items():
        for m in re.finditer(pat, text, re.I):
            if negated(text, m.start()):
                continue
            add(findings, sev, "R5 absolute-language", where, text,
                "Absolute claim word %r -- stronger than any single study licenses." % m.group(0),
                "Replace with: %s" % fix)


# ---------------------------------------------------------------- rules

def check_studies(findings):
    d = json.load(open(STUDIES, encoding="utf-8"))
    for s in d:
        sid = s.get("sid")
        tier = (s.get("tier") or "")
        pyr = (s.get("pyramid") or "")
        model = (s.get("model") or "")
        peer = (s.get("peer") or "")
        blob = " ".join(filter(None, [s.get("finding"), s.get("ai_effect")]))
        where = "study:%s" % sid

        # R4 / R6 -- tier vs. publication category
        if pyr in OUT_OF_HIERARCHY_PYRAMID and tier.startswith(AD_TIERS):
            sev = "ERROR" if pyr in ("Preprint", "Registered Trial") else "WARN"
            add(findings, sev, "R4 tier-on-out-of-hierarchy", where, tier,
                "Pyramid_Level=%r sits outside the A-D hierarchy but Evidence_Tier=%r." % (pyr, tier),
                "Set Evidence_Tier to %r (or the matching out-of-hierarchy label)." % pyr)
        if peer.strip().lower() in ("no", "false") and tier.startswith(AD_TIERS):
            add(findings, "ERROR", "R4 tier-on-non-peer-reviewed", where, tier,
                "Peer_Reviewed=%r but graded %r. Preprints must not carry an A-D tier." % (peer, tier),
                "Set Evidence_Tier='Preprint'.")

        # R5 -- absolute language anywhere
        scan_absolute(findings, where, blob)

        # R7 -- Evidence_Tier must agree with Pyramid_Level.
        # Pridano 2026-07-29 po externim review. Tier a pyramida jsou dve osy,
        # ale nesmi si odporovat: DEN2026 mel tier "C - Animal" a zaroven
        # pyramid "5 - Mechanistic / In Vitro" v jednom zaznamu -- jedna z tech
        # dvou hodnot byla proste spatne, a nic to nezachytilo. LAM2012 byl
        # cely mysi in vivo experiment gradovany D/5. Tohle pravidlo obojí
        # chytne driv, nez to najde recenzent.
        exp_pyr = {"A": ("1",), "B": ("2", "3"), "C": ("4",), "D": ("5", "Narrative Review")}
        t0 = (tier or " ")[0]
        if t0 in exp_pyr and pyr:
            if not any(pyr.startswith(p) for p in exp_pyr[t0]):
                add(findings, "ERROR", "R7 tier-pyramid-disagreement", where,
                    "tier=%s / pyramid=%s" % (tier, pyr),
                    "Evidence_Tier %r implies Pyramid_Level %s, but the record says %r. "
                    "One of the two axes is wrong." % (tier, " or ".join(exp_pyr[t0]), pyr),
                    "Decide what claim the study supports: an organismal phenotype grades C/4, "
                    "a signalling mechanism grades D/5. See the Evidence_Tier field description.")

        # R1 -- uncontrolled trial + confirmation language
        design = model + " " + blob
        if UNCONTROLLED.search(design) and not CONTROLLED.search(design):
            marker = UNCONTROLLED.search(design).group(0)
            for pat, fix in CAUSAL.items():
                for m in re.finditer(pat, blob, re.I):
                    if negated(blob, m.start()):
                        continue
                    if NOT_CAUSAL_CONTEXT.search(blob[max(0, m.start() - 20):m.end() + 12]):
                        continue
                    add(findings, "ERROR", "R1 uncontrolled-as-confirmation", where, blob,
                        "Uncontrolled/single-arm design (%s) paired with %r." % (marker, m.group(0)),
                        "Use: %s; state 'no comparator arm' explicitly." % fix)

        # R2 -- observational described causally
        if OBSERVATIONAL.search(model + " " + pyr):
            extra = [(r"\bleads? to\b", "is associated with"),
                     (r"\bprevent(s|ed)\b", "was associated with lower rates of"),
                     (r"\bpinpoints?\b", "implicates")]
            for pat, fix in list(CAUSAL.items()) + extra:
                for m in re.finditer(pat, blob, re.I):
                    if negated(blob, m.start()):
                        continue
                    if NOT_CAUSAL_CONTEXT.search(blob[max(0, m.start() - 20):m.end() + 12]):
                        continue
                    add(findings, "ERROR", "R2 observational-as-causal", where, blob,
                        "Observational design paired with causal verb %r." % m.group(0),
                        "Use: %s; note residual confounding." % fix)
            if not re.search(r"(confound|observational|association|associated|"
                             r"causation cannot|not randomi|non-randomi|selection bias|"
                             r"retrospective|hypothesis-generating|n-of-1|single[- ]patient|"
                             r"case report|cannot be excluded)", blob, re.I):
                add(findings, "WARN", "R2 observational-missing-caveat", where, blob,
                    "Observational study with no confounding/association caveat in the text.",
                    "Add: 'observational; confounding by indication not excluded'.")

        # R3 -- non-human evidence described as clinical
        if tier.startswith(NONHUMAN_TIERS) and pyr not in ("2 - Human Clinical Trial",
                                                           "3 - Human Observational",
                                                           "1 - Systematic Review"):
            m = CLINICAL_LANG.search(blob)
            if m and not re.search(r"\bno human data|not (yet )?(tested|shown) in humans\b", blob, re.I):
                add(findings, "WARN", "R3 mechanistic-as-clinical", where, blob,
                    "Tier %s (%s) but the text uses clinical language %r." % (tier, pyr, m.group(0)),
                    "Scope to the model organism/system, or add 'no human data'.")

        # R3b -- animal/in-vitro claim with no species scope
        if tier.startswith(NONHUMAN_TIERS) and re.search(r"\bcauses?\b", blob, re.I):
            if not re.search(r"\b(mouse|mice|rat|monkey|macaque|yeast|worm|fly|"
                             r"drosophila|c\.? elegans|in vitro|cells?|cell line|"
                             r"in these cells|in this model)\b", blob, re.I):
                add(findings, "WARN", "R3b unscoped-causal-claim", where, blob,
                    "Causal verb in a non-human study with no species/system scope in the sentence.",
                    "Name the model explicitly ('in mice', 'in these cells').")
    return len(d)


def check_index(findings):
    h = open(INDEX, encoding="utf-8").read()

    # -- ATLAS_GAPS
    m = re.search(r"const ATLAS_GAPS = (\[.*?\]);", h, re.S)
    if m:
        for g in json.loads(m.group(1)):
            for k in ("basis", "hyp", "exp", "title"):
                scan_absolute(findings, "gap:%s.%s" % (g.get("id"), k), g.get(k))

    # -- ATLAS_RELATIONS
    m = re.search(r"const ATLAS_RELATIONS = (\[.*?\]);", h, re.S)
    if m:
        try:
            for r in json.loads(m.group(1)):
                for k in ("mech", "ctx", "note"):
                    scan_absolute(findings, "relation:%s.%s" % (r.get("id"), k), r.get(k))
        except Exception:
            pass

    # -- ATLAS_ENTITIES
    m = re.search(r"const ATLAS_ENTITIES = (\[.*?\]);", h, re.S)
    if m:
        try:
            for e in json.loads(m.group(1)):
                scan_absolute(findings, "entity:%s" % e.get("name"), e.get("desc"))
        except Exception:
            pass

    # -- hand-written prose (skip the baked data lines)
    for i, line in enumerate(h.split("\n"), 1):
        if len(line) > 4000:
            continue
        txt = re.sub(r"<[^>]+>", " ", line)
        txt = html.unescape(txt)
        if not txt.strip():
            continue
        scan_absolute(findings, "index.html:%d" % i, txt, sev="WARN")

    # -- R6: does the homepage still claim blanket A-D grading?
    plain = html.unescape(re.sub(r"<[^>]+>", " ", h))
    for bad in [r"grades every one by evidence tier",
                r"[Ee]very study receives an? (A-D |A–D )?evidence tier",
                r"evidence tier on every study"]:
        if re.search(bad, plain):
            add(findings, "ERROR", "R6 tier-scope-overclaim", "index.html", bad,
                "Copy claims every study is A-D graded, but preprints / narrative reviews / "
                "registered trials sit outside the hierarchy.",
                "Say 'every eligible peer-reviewed primary study'.")


# ---------------------------------------------------------------- main

def main():
    findings = []
    n = check_studies(findings)
    check_index(findings)

    errs = [f for f in findings if f["severity"] == "ERROR"]
    warns = [f for f in findings if f["severity"] == "WARN"]

    print("=" * 78)
    print("Atlas claim calibration -- %d studies scanned" % n)
    print("  %d ERROR   %d WARN" % (len(errs), len(warns)))
    print("=" * 78)
    for group, label in ((errs, "ERROR"), (warns, "WARN")):
        if not group:
            continue
        print("\n---- %s (%d) ----" % (label, len(group)))
        for f in group:
            print("\n[%s] %s" % (f["rule"], f["where"]))
            print("  %s" % f["message"])
            if f["excerpt"]:
                print("  text: %s" % f["excerpt"][:220])
            if f["suggested"]:
                print("  fix : %s" % f["suggested"])

    if JSON_OUT:
        json.dump(findings, open(JSON_OUT, "w", encoding="utf-8"),
                  ensure_ascii=False, indent=1)
        print("\nwrote %s" % JSON_OUT)

    if STRICT and errs:
        print("\nFAIL: %d error-level findings (--strict)." % len(errs))
        return 1
    print("\nOK." if not errs else "\n%d error-level findings." % len(errs))
    return 0


if __name__ == "__main__":
    sys.exit(main())
