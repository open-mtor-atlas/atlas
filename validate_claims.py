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



# ---------------------------------------------------------------- R8-R12
# Added 2026-08-30 after the external scientific audit. Root cause the audit
# named for the Category-1/2 findings it caught (H1 "ZERO", H7 Araki 2009,
# H8 Halloran 2012, 4EBP1-MITO/ZID2009): the pipeline verified a citation
# EXISTS, never that it supports the DIRECTION or SCOPE assigned to it, and
# an announced correction (Welcome page) was never re-asserted against the
# card it corrected. These five rules are static/regex heuristics, not full
# semantic checks -- they narrow where a human needs to look, same spirit
# as R1-R7 above.

ABSENCE_WORD = re.compile(r"\b(ZERO|ONLY|EVERY|NONE|ALL)\b")
ABSENCE_PHRASE = re.compile(r"\b(no study|not a single|not one)\b", re.I)
SCOPE_PHRASE = re.compile(r"in this (corpus|atlas|dataset|collection)", re.I)
NUMERAL = re.compile(r"\b\d+(\.\d+)?\s*%|\bp\s*[<=]\s*0\.\d+|\bHR\s*[\d.]+|\bn\s*=\s*\d+|"
                     r"\b\d+/\d+\b|\b\d+(\.\d+)?\s*(months?|weeks?|years?)\b", re.I)
CODE = re.compile(r"\b[A-Z]{2,6}\d{4}[A-Za-z]?\b")

# Genuinely unreachable: no caller, no reader. renderFullMap() was reduced to a
# handoff button on 2026-08-06 and renderMechanism() is never called.
# MAP_CORE_EDGES also carries three wrong signs (SAMTOR->GATOR2; AKT->PRAS40 as
# "activate"; 4E-BP1->Muscle as "activate"), so deleting it fixes biology too.
DEAD_LAYERS = ["MAP_NODES", "MAP_CORE_EDGES", "MAP_PERIPH_EDGES", "MAP_BANDS"]
DEAD_FUNCS = ["renderMechanism", "mxBuildSVG", "mxSetRoute"]

# NOT dead, despite never being rendered: build_pathway_model.py reads these out
# of index.html (read_atlas_array, called from main()) and they are the input
# from which pathway/model.json is generated. Deleting them breaks the build.
# Corrected 2026-09-04, after R11 was found advising exactly that deletion.
BUILD_INPUT_ARRAYS = ["ATLAS_EDGES", "ATLAS_ROUTES"]


def load_atlas_gaps(h):
    m = re.search(r"const ATLAS_GAPS = (\[.*?\]);", h, re.S)
    if not m:
        return []
    try:
        return json.loads(m.group(1))
    except Exception:
        return []


def check_gap_regression_rules(findings, h):
    gaps = load_atlas_gaps(h)

    # R8 -- absolute-claim regression: re-assert a specific claim class
    # against the live pathway model each run, per the audit's own example
    # ("assert no sensor -> aging edge would have failed the moment
    # SESN2-AGING was added, catching 1.3 automatically").
    try:
        model = json.load(open(os.path.join(HERE, "pathway", "model.json"), encoding="utf-8"))
        sensor_to_aging_edges = [e["id"] for e in model.get("interactions", [])
                                  if e.get("target", "").lower() in ("aging", "longevity")
                                  and any(s in e.get("source", "") for s in
                                          ("Sestrin", "SAMTOR", "CASTOR", "sensor"))]
    except Exception:
        sensor_to_aging_edges = None

    for g in gaps:
        gid = g.get("id", "?")
        basis = g.get("basis") or ""
        hyp = g.get("hyp") or ""
        blob = basis + " " + hyp

        # R8, concretely: an amino-acid-sensor gap asserting a ZERO/NONE-style
        # absence of any sensor->aging outcome, while the model already
        # carries such an edge, is a live regression.
        if sensor_to_aging_edges and gid == "H1":
            for m in re.finditer(r"\bZERO\b.{0,40}(aging|longevity)", basis, re.I):
                # Skip a match that is itself being quoted as the OLD, already-
                # corrected wording (e.g. inside a "CORRECTION LOG ... previously
                # read '...'" note) -- that is documentation of the fix, not a
                # live regression of it.
                pre = basis[max(0, m.start() - 200):m.start()]
                if re.search(r"previously read|CORRECTION LOG|already false", pre, re.I):
                    continue
                add(findings, "ERROR", "R8 absolute-claim-regression", "gap:%s" % gid, basis,
                    "H1 claims a ZERO sensor->aging/longevity link, but pathway/model.json "
                    "already carries %s. Re-run the correction." % ", ".join(sensor_to_aging_edges),
                    "Update Evidence_Basis to acknowledge the edge (see LEE2010/SESN2-AGING).")

        # R9 -- every numeral in a gap's basis needs a nearby study code.
        for sent in re.split(r"(?<=[.!?])\s+", basis):
            if NUMERAL.search(sent) and not CODE.search(sent):
                add(findings, "WARN", "R9 number-without-code", "gap:%s.basis" % gid, sent,
                    "Sentence carries a number with no study code in the same sentence.",
                    "Attach the supporting study code next to the figure.")

        # R10 -- codes mentioned in the prose should be in the gap's own
        # Supporting_Studies list (bidirectional citation integrity, the
        # achievable half -- the full corpus-wide reachability check needs
        # the Studies table cross-referenced and is left to a human pass).
        mentioned = set(CODE.findall(blob)) - {"NCT" + m for m in []}
        mentioned = {c for c in mentioned if not c.startswith("NCT")}
        listed = set(g.get("studies") or [])
        missing = mentioned - listed
        if missing:
            add(findings, "WARN", "R10 code-not-in-supporting-list", "gap:%s" % gid,
                ", ".join(sorted(missing)),
                "Study code(s) %s appear in the gap's text but not in its Supporting_Studies "
                "list." % ", ".join(sorted(missing)),
                "Add the code(s) to Supporting_Studies, or remove the in-text citation.")

        # R12 -- scope guard: an absence claim not scoped to "in this
        # corpus/Atlas" reads as a claim about the whole literature.
        for m in list(ABSENCE_WORD.finditer(basis)) + list(ABSENCE_PHRASE.finditer(basis)):
            window = basis[max(0, m.start() - 120):m.end() + 120]
            if not SCOPE_PHRASE.search(window):
                add(findings, "WARN", "R12 unscoped-absence-claim", "gap:%s.basis" % gid,
                    window,
                    "Absence/absolute word %r with no 'in this corpus/Atlas' scoping nearby." % m.group(0),
                    "Add 'in this corpus' (or similar) next to the claim, or drop the absolute word.")


def check_dead_layers(findings, h):
    # R11 -- dead render layer. WARN, not ERROR: the MAP_* arrays and the
    # renderMechanism()/mx*() helpers are unreachable (renderFullMap() became a
    # handoff button on 2026-08-06; the live explorer reads pathway/model.json),
    # but deleting ~900 lines is a separate reviewed change, not something to
    # fold into a content pass. Flip to ERROR once they are gone, so that a
    # reintroduction fails the build.
    #
    # ATLAS_EDGES / ATLAS_ROUTES are deliberately NOT in this list. They are also
    # never rendered, but build_pathway_model.py reads them out of index.html to
    # generate pathway/model.json, so they are build input, not dead weight.
    # Until 2026-09-04 this rule listed them and told the reader to delete them,
    # which would have broken the build.
    present = [name for name in DEAD_LAYERS + DEAD_FUNCS
               if re.search(r"\b" + re.escape(name) + r"\b", h)]
    if present:
        add(findings, "WARN", "R11 dead-pathway-layer", "index.html", ", ".join(present),
            "Unreachable render-layer constants/functions still shipped (never "
            "called, but machine-readable to crawlers): %s. MAP_CORE_EDGES also "
            "carries three wrong signs." % ", ".join(present),
            "Safe to delete: nothing reads these. Do NOT also remove ATLAS_EDGES "
            "or ATLAS_ROUTES -- build_pathway_model.py needs them.")

    # R11b -- the inverse guard. If a build-input array goes missing, the next
    # build_pathway_model.py run raises SystemExit("missing %s in index.html").
    # Catch it here, before the build, and say why.
    gone = [name for name in BUILD_INPUT_ARRAYS
            if not re.search(r"const\s+" + re.escape(name) + r"\s*=", h)]
    if gone:
        add(findings, "ERROR", "R11b build-input-array-missing", "index.html", ", ".join(gone),
            "%s is missing from index.html. build_pathway_model.py reads it via "
            "read_atlas_array() and will fail, and pathway/model.json cannot be "
            "regenerated." % ", ".join(gone),
            "Restore from git history. These arrays are unrendered but they are "
            "the source of truth for the pathway model.")


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


def check_academy(findings):
    """Academy prose (2026-08-30). Lekce jsou jedina rucne psana veda na webu,
    ktera NENI v index.html -- bez teto funkce by prosly branou nezkontrolovane.
    Stejne skenery jako vsude jinde: R5 (absolutni jazyk) nad kazdym kusem prozy
    a R3 (mechanisticka prace popsana jako klinicky dukaz) nad temi kusy, ktere
    zaroven mluvi klinickym jazykem. ERROR, ne WARN: v lekci je prehnana
    formulace horsi nez v poznamce -- uci se z ni."""
    p = os.path.join(HERE, "academy_data", "lessons.json")
    if not os.path.exists(p):
        return 0
    lessons = json.load(open(p, encoding="utf-8"))["lessons"]
    for l in lessons:
        blobs = [("coreIdea", x) for x in l.get("coreIdea") or []]
        blobs += [("uncertainty", l.get("uncertainty") or "")]
        blobs += [("subtitle", l.get("subtitle") or ""), ("question", l.get("question") or "")]
        for i, sec in enumerate(l.get("sections") or []):
            blobs += [("section%d" % i, x) for x in sec.get("body") or []]
            blobs += [("section%d.beginner" % i, x) for x in sec.get("bodyBeginner") or []]
        blobs += [("coreIdeaBeginner", x) for x in l.get("coreIdeaBeginner") or []]
        for j, t in enumerate(l.get("thinkQuestions") or []):
            blobs += [("think%d.prompt" % j, t.get("prompt") or ""),
                      ("think%d.hint" % j, t.get("hint") or ""),
                      ("think%d.reveal" % j, t.get("reveal") or "")]
        # Interaktivni cviceni (Faze 2, 2026-08-31). Stejny duvod jako u kvizu:
        # zpetna vazba k navrhu experimentu a "what this does not show" jsou
        # proza, kterou si student precte pozorneji nez hlavni text.
        for j, x in enumerate(l.get("exercises") or []):
            w2 = "ex%d.%s" % (j, x.get("kind"))
            for f in ("prompt", "explain", "why", "bothSupport", "differ",
                      "nextExperiment", "question", "wouldResolve"):
                blobs.append(("%s.%s" % (w2, f), x.get(f) or ""))
            for f in ("options", "shows", "doesNotShow", "limitations",
                      "whatWeKnow", "whatWeDont", "competing"):
                v = x.get(f)
                if isinstance(v, list):
                    blobs += [("%s.%s%d" % (w2, f, k), str(i)) for k, i in enumerate(v)]
            for sk, st in (x.get("states") or {}).items():
                blobs.append(("%s.state[%s]" % (w2, sk), st.get("note") or ""))
            for d in x.get("dimensions") or []:
                blobs += [("%s.%s.%s" % (w2, d.get("id"), o.get("label")), o.get("note") or "")
                          for o in d.get("options") or []]
            for side in ("a", "b"):
                if isinstance(x.get(side), dict):
                    blobs += [("%s.%s.perturbation" % (w2, side), x[side].get("perturbation") or ""),
                              ("%s.%s.readout" % (w2, side), x[side].get("readout") or "")]
            if isinstance(x.get("observe"), dict):
                blobs += [("%s.observe.method" % w2, x["observe"].get("method") or ""),
                          ("%s.observe.readout" % w2, x["observe"].get("readout") or "")]
        blobs += [("objective%d" % k, o)
                  for k, o in enumerate(l.get("learningObjectives") or [])]

        # Kviz (2026-08-30). Distraktory jsou taky proza a ctou se stejne jako
        # zbytek lekce -- kdyby prosly nezkontrolovane, absolutni formulace by
        # se do webu dostala prave tou vetou, kterou si student precte dvakrat.
        for j, q in enumerate(l.get("quiz") or []):
            blobs += [("quiz%d.prompt" % j, q.get("prompt") or ""),
                      ("quiz%d.explain" % j, q.get("explain") or "")]
            blobs += [("quiz%d.option%d" % (j, k), o)
                      for k, o in enumerate(q.get("options") or [])]
        for field, raw in blobs:
            if not raw:
                continue
            txt = html.unescape(re.sub(r"<[^>]+>", " ", raw))
            where = "academy:%s.%s" % (l["slug"], field)
            scan_absolute(findings, where, txt, sev="ERROR")
            # R3 se testuje na textu BEZ uvozovkovanych pasazi. Lekce o cteni
            # papiru cituje vetne tvary, pred kterymi varuje ("X is a
            # therapeutic target for Y") -- to je pouziti - zminka, ne tvrzeni,
            # a scanner ho jinak hlasi napored. R5 (absolutni jazyk) se naopak
            # scanuje na plnem textu: absolutni slovo je problem i v citaci.
            unquoted = re.sub(u"[\u2018\u201c'\"][^\u2019\u201d'\"]{0,400}"
                              u"[\u2019\u201d'\"]", " ", txt)
            if CLINICAL_LANG.search(unquoted):
                add(findings, "WARN", "R3 mechanistic-as-clinical", where, txt,
                    "Lesson prose uses clinical/human language -- check the claim is scoped "
                    "to the species and design of the studies the lesson actually cites.",
                    "Name the model system in the sentence, or move the claim to a "
                    "human-evidence lesson.")
    return len(lessons)



def check_challenges(findings):
    """Research Challenges (2026-09-01). Stejny duvod jako u lekci, jen ostrejsi:
    vyzva je psana jako rozhodovaci prostredi, takze skoro kazdy retezec v ni je
    komentar k volbe -- a komentar k volbe si student precte pozorneji nez hlavni
    text. Prehnana formulace v nem uci spatne cist evidenci, coz je presne to, co
    ma vyzva odnaucovat."""
    p = os.path.join(HERE, "academy_data", "challenges.json")
    if not os.path.exists(p):
        return 0
    chs = json.load(open(p, encoding="utf-8"))["challenges"]
    for c in chs:
        if c.get("status") != "published":
            continue
        blobs = [("subtitle", c.get("subtitle") or ""),
                 ("researchQuestion", c.get("researchQuestion") or "")]
        blobs += [("objective%d" % i, x) for i, x in enumerate(c.get("learningObjectives") or [])]
        blobs += [("know%d" % i, k.get("claim") or "")
                  for i, k in enumerate(c.get("whatWeKnow") or [])]
        blobs += [("uncertainty%d" % i, x) for i, x in enumerate(c.get("uncertainty") or [])]
        blobs += [("budget.note", (c.get("budget") or {}).get("note") or "")]
        md = c.get("model") or {}
        blobs.append(("model.caption", md.get("caption") or ""))
        for sk, st in (md.get("states") or {}).items():
            blobs.append(("model.state[%s]" % sk, st.get("note") or ""))
        for b in c.get("break") or []:
            blobs += [("break.%s.prompt" % b.get("id"), b.get("prompt") or ""),
                      ("break.%s.explain" % b.get("id"), b.get("explain") or "")]
            blobs += [("break.%s.option%d" % (b.get("id"), i), x)
                      for i, x in enumerate(b.get("options") or [])]
        h = c.get("hypotheses") or {}
        blobs.append(("hypotheses.prompt", h.get("prompt") or ""))
        for op in h.get("options") or []:
            blobs += [("hypothesis.%s.label" % op.get("id"), op.get("label") or ""),
                      ("hypothesis.%s.note" % op.get("id"), op.get("note") or "")]
        rv = c.get("revise") or {}
        blobs += [("revise.prompt", rv.get("prompt") or ""),
                  ("revise.note", rv.get("note") or "")]
        blobs += [("revise.feedback.%s" % k, v)
                  for k, v in (rv.get("feedback") or {}).items()]
        lab = c.get("lab") or {}
        blobs.append(("lab.budget.note", (lab.get("budget") or {}).get("note") or ""))
        blobs.append(("lab.startNote", lab.get("startNote") or ""))
        for g in lab.get("goals") or []:
            blobs += [("lab.goal.%s.q" % g.get("id"), g.get("question") or ""),
                      ("lab.goal.%s.note" % g.get("id"), g.get("note") or "")]
        for x in lab.get("nodes") or []:
            xw = "lab.%s" % x.get("id")
            for f in ("label", "addresses", "equipment", "opensNote", "informative"):
                blobs.append(("%s.%s" % (xw, f), x.get(f) or ""))
            for f in ("model", "perturbation", "readout", "control"):
                blobs.append(("%s.design.%s" % (xw, f), (x.get("design") or {}).get(f) or ""))
            blobs.append(("%s.evidence.basis" % xw,
                          (x.get("evidence") or {}).get("basis") or ""))
            blobs.append(("%s.result.caption" % xw, (x.get("result") or {}).get("caption") or ""))
            for f in ("conclude", "cannotConclude"):
                blobs += [("%s.%s%d" % (xw, f, i), v) for i, v in enumerate(x.get(f) or [])]
            for i, op in enumerate(x.get("interpret") or []):
                blobs += [("%s.interpret%d.label" % (xw, i), op.get("label") or ""),
                          ("%s.interpret%d.note" % (xw, i), op.get("note") or "")]
            ev = x.get("event") or {}
            for f in ("info", "prompt", "explain", "control"):
                blobs.append(("%s.event.%s" % (xw, f), ev.get(f) or ""))
            for i, op in enumerate(ev.get("options") or []):
                blobs += [("%s.event.option%d.label" % (xw, i), op.get("label") or ""),
                          ("%s.event.option%d.note" % (xw, i), op.get("note") or "")]
        for i, r in enumerate((lab.get("debrief") or {}).get("rules") or []):
            blobs.append(("lab.debrief.rule%d" % i, r.get("note") or ""))

        # Answer (2026-09-01). Jediny text, ktery student cte jako "takhle to
        # dneska je" -- prehnana formulace je tu nejdrazsi, protoze si ji odnese
        # jako zaver cele vyzvy.
        ans = c.get("answer") or {}
        blobs.append(("answer.short", ans.get("short") or ""))
        for i, row in enumerate(ans.get("observation") or []):
            blobs.append(("answer.observation%d" % i, row.get("text") or ""))
        for f in ("interpretation", "stillOpen"):
            blobs += [("answer.%s%d" % (f, i), v) for i, v in enumerate(ans.get(f) or [])]
        for k, v in (ans.get("hypothesisVerdicts") or {}).items():
            blobs.append(("answer.verdict.%s" % k, v or ""))

        cp = c.get("compare") or {}
        blobs += [("compare.whatTheyTested", cp.get("whatTheyTested") or ""),
                  ("compare.howToRead", cp.get("howToRead") or "")]
        for f in ("whatItAnswered", "whatItDidNot"):
            blobs += [("compare.%s%d" % (f, i), v) for i, v in enumerate(cp.get(f) or [])]
        for r in c.get("reflection") or []:
            blobs.append(("reflect.%s.prompt" % r.get("id"), r.get("prompt") or ""))
            blobs += [("reflect.%s.option%d" % (r.get("id"), i), v)
                      for i, v in enumerate(r.get("options") or [])]
        nq = c.get("nextQuestion") or {}
        blobs += [("next.text", nq.get("text") or ""), ("next.prompt", nq.get("prompt") or "")]
        for i, op in enumerate(nq.get("options") or []):
            blobs += [("next.option%d.label" % i, op.get("label") or ""),
                      ("next.option%d.note" % i, op.get("note") or "")]
        blobs += [("prereq%d.why" % i, pr.get("why") or "")
                  for i, pr in enumerate(c.get("prerequisites") or [])]

        for field, raw in blobs:
            if not raw:
                continue
            txt = html.unescape(re.sub(r"<[^>]+>", " ", raw))
            where = "challenge:%s.%s" % (c["slug"], field)
            scan_absolute(findings, where, txt, sev="ERROR")
            unquoted = re.sub(u"[\u2018\u201c'\"][^\u2019\u201d'\"]{0,400}"
                              u"[\u2019\u201d'\"]", " ", txt)
            if CLINICAL_LANG.search(unquoted):
                add(findings, "WARN", "R3 mechanistic-as-clinical", where, txt,
                    "Challenge prose uses clinical/human language -- check the claim is "
                    "scoped to the species and design of the studies it cites.",
                    "Name the model system in the sentence, or drop the clinical framing.")
    return len([c for c in chs if c.get("status") == "published"])


# ---------------------------------------------------------------- main

def main():
    findings = []
    n = check_studies(findings)
    check_index(findings)
    h = open(INDEX, encoding="utf-8").read()
    check_gap_regression_rules(findings, h)
    check_dead_layers(findings, h)
    n_les = check_academy(findings)
    n_ch = check_challenges(findings)

    errs = [f for f in findings if f["severity"] == "ERROR"]
    warns = [f for f in findings if f["severity"] == "WARN"]

    print("=" * 78)
    print("Atlas claim calibration -- %d studies, %d Academy lessons, "
          "%d research challenges scanned" % (n, n_les, n_ch))
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
