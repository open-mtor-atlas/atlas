# Phase 3 — Knowledge Gaps & Testable Hypotheses

*Date: 2026-07-08. This is the Atlas differentiator: not "what we know" but "what we don't know — and why," derived by joining the curated 66-node entity graph to per-study evidence tiers (A > B > C > D). Reproducible via `gap_finder.py`.*

---

## How these gaps were found (method, not vibes)

`gap_finder.py` joins each entity in the Airtable **Entities** table to the evidence tier of every study it links to, then flags three structural patterns:

1. **Evidence deserts** — entities supported only by weak (tier C/D) studies.
2. **Mechanism→outcome disconnects** — well-characterized molecular nodes that link to *no* aging/disease outcome.
3. **Human-endpoint deserts** — outcomes whose evidence is almost entirely non-human.

The numbers below come straight from that join, so every claim is auditable against the corpus.

---

## The four data-level findings

**Finding A — The entire nutrient-sensing layer is tier-D only.** Every amino-acid sensor and upstream regulator is supported *exclusively* by mechanistic/in-vitro (tier D) work: Sestrin2, CASTOR1, SAMTOR, v-ATPase (each n=1, all D); Rag GTPases, Ragulator, GATOR1, GATOR2, Rheb, PRAS40, AMPK, PI3K, Raptor, Rictor, mLST8, FKBP12, Akt, ULK1, TFEB. Not one has a single tier-A/B/C study.

**Finding B — The sensors are disconnected from every phenotype.** Of the amino-acid sensors, **zero** link to the Longevity outcome, and (except Ragulator, 1) zero link to *any* outcome, disease, or process node. The most molecularly detailed, most pharmacologically *specific* part of the pathway has never been tested for an organismal effect.

**Finding C — Longevity rests on animals.** Of 32 Longevity-linked studies: 20 tier-C (animal), 7 tier-D, 3 tier-B, 1 tier-A, 1 registered trial. The four non-animal entries (metformin epidemiology BAN2014; PEARL safety MOE2025; systematic review LEE2024; safety RCT KRA2018) are **safety/immune/observational — none has a lifespan or healthspan primary endpoint.** There is effectively no completed human geroprotection trial with a hard aging endpoint; the one that could provide it (EVERLAST, NCT05835999) has no results yet.

**Finding D — Named contradictions/tensions in the corpus.**
- *Benefit vs harm:* rapamycin extends lifespan (many tier-C) yet chronic dosing causes insulin resistance via mTORC2 disruption (LAM2012), and one study finds it "extends lifespan but has limited effects on aging" (Neff/ZPg). Benefit and harm come from *different complexes*.
- *Longevity vs muscle:* mTORC1 is **required** for muscle — raptor-KO dystrophy (Bentzinger), rapamycin blocks human muscle protein synthesis (DRU2009), Akt/mTOR is necessary+sufficient for hypertrophy (ROM2001/Bodine) — yet mTOR inhibition is the leading longevity lever. Unresolved.
- *Hype vs data:* resveratrol, marketed as a CR-mimetic, failed in the ITP mouse trial (MIL2011) and in a human RCT (POU2013).

---

## Five testable hypotheses (each tied to the gap that generates it)

### H1 — Sensor-selective geroprotection without the metabolic penalty
**Gap:** Findings A+B. The sensors are druggable-specific but phenotype-untested.
**Hypothesis:** Selectively dialing down mTORC1 through *one* sensor arm — e.g. mimicking methionine restriction via the SAMTOR→GATOR1 axis, or leucine restriction via Sestrin2 — reproduces rapamycin's healthspan benefit **while sparing mTORC2**, and therefore without the insulin resistance seen with rapamycin.
**Experiment:** In mice, compare (i) SAMTOR gain-of-function / dietary methionine restriction, (ii) rapamycin, (iii) control. Endpoints: healthspan/lifespan, glucose tolerance, and mTORC2 activity (Akt-Ser473). Prediction: arm (i) matches (ii) on healthspan but not on glucose impairment.
**Anchored in:** GU2017 (SAMTOR), SAX2015 (Sestrin2), LAM2012 (mTORC2→insulin resistance).

### H2 — mTORC1-selective (mTORC2-sparing) dosing captures longevity without insulin resistance
**Gap:** Finding D (benefit/harm split by complex); no in-vivo mTORC1-selective aging test exists.
**Hypothesis:** An intervention that suppresses the mTORC1/4E-BP arm while leaving mTORC2 intact — e.g. intermittent/low-dose rapamycin, or a 4E-BP-biased regimen — yields the lifespan benefit without glucose intolerance.
**Experiment:** Mouse lifespan under continuous vs intermittent vs low-dose rapamycin; endpoints lifespan + insulin sensitivity + mTORC2 (Akt-Ser473). This mirrors the human EVERLAST daily-vs-weekly design.
**Anchored in:** LAM2012, KEN2016 (alternative regimens mitigate glucose/immune effects), THO2009 (Torin1 reveals rapamycin-resistant 4E-BP arm), NCT05835999 (EVERLAST).

### H3 — Muscle-sparing, pulsed mTORC1 inhibition
**Gap:** Finding D (longevity vs muscle contradiction).
**Hypothesis:** Time-restricted / pulsed mTORC1 inhibition (drug trough permitting post-exercise anabolic windows) preserves muscle mass while still capturing the longevity benefit, because muscle protein synthesis needs only intermittent mTORC1 activity whereas the geroprotective effect tolerates transient dosing.
**Experiment:** Mouse, continuous vs pulsed rapamycin timed around resistance loading; endpoints lifespan + muscle mass/fiber CSA + autophagic flux (LC3-II/p62). Prediction: pulsed arm preserves muscle at similar healthspan.
**Anchored in:** DRU2009 (rapamycin blocks human MPS), ROM2001 (IGF-1→Akt/mTOR hypertrophy), MOE2025 (PEARL: intermittent rapamycin, lean-tissue signal), BIT2016 (transient dosing captures benefit).

### H4 — Is autophagy actually *required* for the mammalian lifespan benefit?
**Gap:** Autophagy is assumed to mediate longevity but shown directly only in fly/worm (BJE2010, MEL2003) and by Atg5-overexpression in mouse (PYO2013). No study tests whether *blocking* autophagy abolishes rapamycin's mammalian lifespan extension.
**Hypothesis:** Autophagy is necessary — rapamycin will **fail** to extend lifespan in autophagy-deficient (e.g. inducible Atg7-KO) mice.
**Experiment:** Rapamycin × inducible tissue-wide autophagy-KO mouse lifespan study, with wild-type rapamycin arm as positive control.
**Anchored in:** BJE2010, MEL2003 (autophagy required in invertebrates), PYO2013 (Atg5 sufficient in mouse).

### H5 — A sensor/autophagy biomarker panel as a surrogate endpoint for human trials
**Gap:** Finding C (no human hard-endpoint trial; lifespan endpoints are impractically long in humans).
**Hypothesis:** A pathway-activity panel (SAMTOR/GATOR axis readout + LC3-II/p62 autophagic flux + mTORC1 vs mTORC2 substrate phosphorylation) tracks the interventions that extend lifespan in animals and can serve as a validated surrogate, enabling short human geroprotection trials.
**Experiment:** Back-test the panel across the animal longevity studies in this corpus (does it separate lifespan-extending from null interventions?), then validate prospectively against EVERLAST's daily-vs-weekly arms.
**Anchored in:** MOE2025 (PEARL biomarkers), LEE2024 (systematic review of human parameters), NCT05835999 (EVERLAST).

---

## Why this is the differentiator
Elicit/Consensus/PaperQA will tell you what the studies *say*. This layer tells you, with receipts from your own evidence-graded corpus, **where the corpus is thin, where it contradicts itself, and which specific experiment would move the needle** — the "what we don't know and why" that no general tool packages. The five hypotheses above are exactly the kind of proposal to put in front of a Sabatini-lab mentor: each names an untested edge in the graph and the experiment that would fill it.

*Reproduce: `python3 gap_finder.py` (needs `studies_enriched.jsonl` in the same folder).*
