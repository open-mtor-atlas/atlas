# Phase 4 — Quantified gaps (full-text evidence)

*Date: 2026-07-08. The Phase-3 gaps were structural ("this link rests only on tier-D"). With full-text extraction (`AI_Dose / AI_SampleSize / AI_EffectSize / AI_Limitations`) for ~46 experimental studies, the same gaps now read in real numbers. Source: Airtable `AI_*` fields (regenerate with `pull_ai_facts.py`).*

---

## H2 — mTORC1-selective (mTORC2-sparing) dosing: now shown in mice, still untested for human longevity
The intermittent-dosing idea is no longer a hypothesis in animals — it's demonstrated, with the exact readout H2 predicted:

- **ARR2015 (Arriola-Apelo):** 2 mg/kg rapamycin **daily** impaired glucose tolerance (**+71% glucose AUC**, up to +116% blood glucose) **and** inhibited *both* mTORC1 (S6) and mTORC2 (AKT-Ser473). **Weekly** or every-5-days dosing caused **no glucose impairment** and inhibited **mTORC1 only.** → direct in-vivo decoupling of the benefit (mTORC1) from the harm (mTORC2), exactly H2's premise.
- **Dose-response (MIL2014):** 4.7 / 14 / 42 ppm; the top dose gave **+23% median lifespan (males, p<0.0001)** and **+26% (females, p<0.0001)**; lower doses extended females only.
- **The human test that should close it used the wrong endpoint:** PEARL (MOE2025) did compare **5 vs 10 mg/week**, but its primary endpoint was visceral fat (missed), with **no mTORC2/insulin-selective longevity readout.**

**Sharpened gap:** the mouse mechanism is proven; a human trial with an mTORC1-selective, mTORC2-sparing *aging* endpoint still does not exist.

## H3 — Transient dosing works — but the benefit was male-specific and carried a female harm signal
- **BIT2016 (transient, 8 mg/kg i.p. × 90 days):** **males +60% post-treatment life expectancy (p=0.02)**, +16% overall (p=0.03); **females: no survival benefit (p=0.26)** and **more aggressive hematopoietic cancers (16/16 vs 6/12 controls, p=0.002).**

**Sharpened gap:** "transient dosing captures the benefit" holds — but sex-specifically, and with a female cancer signal that any muscle-sparing / pulsed-dosing design (H3) must now control for.

## H6 (NEW) — Sex dimorphism is pervasive and sometimes direction-flipping
The extracted effect sizes make this unavoidable — it emerged straight from the numbers:

- **S6K1-KO (SEL2009):** +19% median lifespan in **females**, **no effect in males** (p<0.001 vs p>0.05).
- **Rapamycin:** all doses extend females, only the top two extend males (MIL2014); +38% F vs +28% M life-expectancy (HAR2009); +16% F vs +11% M (FOK2014); +22% F vs +11% M median (WUX2013 mTOR hypomorph).
- **Bitto:** benefit in males, **harm in females.**
- **Acarbose (HAR2014):** **+22% males vs +5% females** — the *opposite* skew.

**New testable gap:** sex changes not just the magnitude but sometimes the *direction* of the response (rapamycin favors females, acarbose favors males). No mechanistic explanation and no sex-stratified human aging data. → Experiment: sex-stratified dosing + PK study (females reach higher rapamycin blood levels, MIL2014) separating pharmacokinetic from pharmacodynamic sex effects.

## H5 — The human-endpoint desert, now with the exact failures
Every completed human trial with an aging/healthspan **primary** endpoint missed it or was safety-only:

- **PEARL (MOE2025):** primary (visceral fat) **NOT met**; secondary bone-density **OR 0.24 (95% CI 0.06–0.93, p=0.04)**.
- **RTB101 phase 3 (MAN2021):** symptomatic-RTI primary **NOT met** (biomarker moved, clinical outcome didn't).
- **Resveratrol (POU2013):** **fully negative** — no change in insulin sensitivity, energy expenditure, or biomarkers.
- **CALERIE 2-yr CR (ROM2016):** **safety only**, between-group differences not significant.

The human **wins** are all disease indications (BOLERO-2 PFS; RADIANT-3 PFS 5% vs 2% responses; exceptional responders IYE2012/WAG2014) or surrogate biomarkers (topical rapamycin, epidermal p16 reduced, p=0.008).

**Sharpened gap:** not "few human trials" but "**zero** completed human trials show a hard aging/longevity endpoint" — the positives are cancer/TSC/LAM indications. This is the strongest single argument for H5's surrogate-biomarker strategy.

## H4 — Autophagy: sufficiency shown, necessity still open
- **Atg5 overexpression (PYO2013):** **+17% median lifespan (p<0.001)**, +15% maximum (900 vs 781 days) — autophagy is *sufficient*.
- Necessity (rapamycin × autophagy-KO mammal) remains untested. H4 stands unchanged.

---

## What changed vs Phase 3
Phase 3 said *where* the corpus was thin. Phase 4 says *by how much*: dose-response curves (4.7→42 ppm), decoupled mTORC1/mTORC2 readouts, exact failed-endpoint statistics, and a pervasive sex effect that now merits its own hypothesis (H6). These numbers are what make the hypotheses concrete enough to design an experiment around — the level a Sabatini-lab mentor would expect.

*Regenerate the underlying facts: `python3 atlas_gaps/pull_ai_facts.py` → `ai_facts.jsonl`.*
