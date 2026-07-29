# External scientific review — Oliver's mTOR Atlas

**Reviewer stance:** adversarial pre-publication review. I went looking for reasons to reject.
**Date:** 29 July 2026 · corpus 275 studies, 93 mechanism edges, 109 entities, 7 pathway routes, 10 knowledge gaps.

**Verdict up front.** The pathway biology is, with the exceptions below, accurate and current — better than several published reviews I would compare it against. The serious problems are not in the biology; they are **three citation-support failures, one inverted entity definition, and an evidence-grading rule that is applied differently from how it is defined.** Two of these are load-bearing for the Atlas's flagship hypothesis (H2) and would be found by any reviewer who checked the sources.

Sixteen findings. Four I would call blocking.

---

## BLOCKING

### F1 — ARR2015 is cited for a lifespan claim the paper never measured

**Location** `atlas_data/studies_baked.json` → ARR2015 `finding` and `ai_effect`; edge `RAPA-LONGEVITY` (`st: ['HAR2009','ARR2015']`); H2 gap `basis`; propagated to `study/ARR2015/index.html`, `drug/rapamycin/`, `outcome/longevity/`.

**The Atlas says**
> "Intermittent rapamycin regimens **preserve lifespan benefit** while reducing glucose/immune side effects." (`finding`)
> "Intermittent regimens **retain the lifespan benefit** while mitigating side effects." (`ai_effect`)

**Why this is problematic** ARR2015 (Arriola Apelo & Lamming, *Aging Cell* 2015, PMID 26463117) contains **no survival endpoint whatsoever**. From the abstract stored in the Atlas's own record, the measured outcomes are: glucose tolerance, pyruvate tolerance, fasting glucose and insulin, beta-cell function, and immune parameters. Its own conclusion is narrower than the Atlas's: *"our results suggest that many of the negative side effects of rapamycin treatment can be mitigated through intermittent dosing or the use of rapamycin analogs."* Side effects mitigated — benefit preserved is not claimed and not tested.

This matters far beyond one record. "Intermittent dosing keeps the benefit and drops the harm" is the **entire premise of hypothesis H2**, the Atlas's highest-confidence gap (0.85). The Atlas's strongest-looking support for the "benefit" half of that sentence is a paper that did not measure benefit.

**Proposed correction** Rewrite the finding to what was measured. Move the benefit-preservation claim to **BIT2016** (Bitto 2016), already in the corpus and used in H3, which *did* measure post-treatment survival (+60% male life expectancy, p=0.02, with no female benefit). Remove ARR2015 from the `RAPA-LONGEVITY` edge, or re-scope that edge's citation set. Note in H2 that the decoupling premise rests on a mechanistic inference (mTORC1 inhibited, mTORC2 spared) plus BIT2016, not on a head-to-head lifespan comparison of dosing schedules — because that experiment has not been done.

**Confidence: High** — verified against the abstract in the Atlas's own database.

---

### F2 — The Sestrin2 entity inverts the sensor's sign and contradicts the Atlas's own edges

**Location** `ATLAS_ENTITIES` → "Sestrin2"; static page `gene/sestrin2/` if generated. Contradicts edges `LEU-SESN2` and `SESN2-GATOR2`.

**The Atlas says**
> "Direct intracellular leucine sensor; binds leucine and relays that signal to the Rag GTPases **to activate mTORC1**."

**Why this is problematic** Sestrin2 is a **negative** regulator. Leucine-free Sestrin2 binds and inhibits GATOR2; leucine binding *releases* GATOR2, which then inhibits GATOR1, which stops inactivating the Rags. Sestrin2 never "relays a signal to the Rag GTPases" — it acts two steps upstream, and its direct effect on the pathway is inhibitory. The entity description reads as though Sestrin2 were an activator.

The Atlas's own edges have this **right**: `LEU-SESN2` is signed *inhibits*, `SESN2-GATOR2` is signed *inhibits*, and the `aa` route story states the double-negative logic correctly. So the entity layer contradicts the edge layer on a mechanism the Atlas otherwise teaches well.

**Proposed correction**
> "Direct intracellular leucine sensor and a **negative** regulator of mTORC1. When leucine is scarce, Sestrin2 binds and inhibits GATOR2, so GATOR1 stays active and keeps mTORC1 off. Leucine binding releases GATOR2 — the pathway is switched on by removing a brake, not by adding a signal."

**Confidence: High**

---

### F3 — The FLCN entity states the opposite of the paper the Atlas cites for FLCN

**Location** `ATLAS_ENTITIES` → "FLCN / FNIP1/2"; `disease/` and `gene/` pages derived from it. The contradicted source, **NAP2020**, is cited on the Atlas's own `FLCN-RAG` edge.

**The Atlas says**
> "Mutations in FLCN cause Birt-Hogg-Dubé syndrome **with constitutive mTORC1 activation**."

**Why this is problematic** Napolitano et al., *Nature* 2020 — the paper the Atlas cites one layer down — shows the opposite for canonical signalling: in FLCN-deficient cells mTORC1 **still phosphorylates 4E-BP1 and S6K1 normally, but cannot phosphorylate TFEB**. BHD is driven by constitutive **TFEB/TFE3 nuclear translocation**, i.e. a *substrate-specific* failure, not blanket mTORC1 hyperactivation. Describing BHD as "constitutive mTORC1 activation" is the pre-2020 model and is contradicted by NAP2020.

This is the kind of error a reviewer working on lysosomal biology would catch immediately, and it is embarrassing precisely because the correct paper is already in the corpus.

**Proposed correction**
> "…acts as a GAP for RagC/D. Loss of FLCN causes Birt-Hogg-Dubé syndrome through a **substrate-specific** defect: canonical mTORC1 outputs (S6K1, 4E-BP1) are largely preserved, while TFEB/TFE3 escape phosphorylation and accumulate in the nucleus (NAP2020). BHD is therefore not simple mTORC1 hyperactivation."

Add the same nuance to the `FLCN-RAG` edge `mech`, which currently describes only the nucleotide-state logic and omits the selectivity that is NAP2020's actual finding (**F13**, folded in here).

**Confidence: High** — verified against the published abstract.

---

### F4 — The evidence-tier rule is defined one way and applied another

**Location** Airtable `Evidence_Tier` field description; About/methodology copy; 33 study records.

**The definition says** "C = animal in vivo; D = mechanistic / in vitro / theoretical / narrative review."

**What is actually applied** Tier appears to track *what kind of claim the study can support*, not the organism. Compare, all whole-organism *Drosophila* work:

| Study | Tier / Pyramid | What it measured |
|---|---|---|
| BJE2010, KAP2004, ZID2009, RAV2004 | **C / 4** | lifespan, degeneration — organismal phenotype |
| SAU2003, STO2003, GAR2003, INOK2003 | **D / 5** | signalling epistasis — mechanism |
| DEN2026 | **C / 5** | — internally contradictory |

Yeast splits the same way (KAE2005/POW2006 replicative lifespan → C; HEI1991/LOE2002/PAN2013 mechanism → D), as does *C. elegans*.

**Why this is problematic** The applied rule is actually the **better** one — evidence strength should track the claim, not the taxon — but it is nowhere written down, and the written definition contradicts it. An external reviewer comparing SAU2003 (D) with KAP2004 (C), both whole-fly studies, will conclude the grading is arbitrary. That undermines the Atlas's single largest value proposition.

Two records are wrong under **either** rule:

- **DEN2026** — tier "C - Animal" with pyramid "5 - Mechanistic / In Vitro" in the same record. One of the two is wrong.
- **LAM2012** — model "Mouse", graded **D / 5**. This is whole-animal metabolic phenotyping (glucose and insulin tolerance in living mice), not in vitro mechanism. Under the written rule it is C; under the applied claim-type rule it is also C, because its claim is an organismal phenotype. It is additionally the primary citation for the entire mTORC2/insulin-resistance argument, for H2, and for the `MTORC2-INSULINRES` edge — **which the Atlas grades C while grading its own key study D.**

**Proposed correction** (1) Rewrite the `Evidence_Tier` field description and the About copy to state the claim-type rule explicitly, with the fly example as the illustration. (2) Regrade LAM2012 to C / 4. (3) Resolve DEN2026 to C / 4 or D / 5. (4) Add a validator rule flagging tier/pyramid pairs that disagree.

**Confidence: High** on the inconsistency; **Medium** on exactly which way DEN2026 should resolve.

---

## SIGNIFICANT

### F5 — S6K1 lifespan sex-specificity is stated in two places and omitted in two others

**Location** SEL2009 `finding`; entity "S6K1"; edge `S6K1-LONGEVITY` ctx; gap H6.

| Location | Says |
|---|---|
| Edge `S6K1-LONGEVITY` ctx | "Female mice only in SEL2009 — not significant in males" ✓ |
| Gap H6 | "+19% median lifespan in FEMALES / no effect in males" ✓ |
| SEL2009 `finding` | "Deleting S6K1 … extended lifespan … in mice" ✗ |
| Entity "S6K1" | "its deletion extends mouse lifespan similarly to caloric restriction" ✗ |

**Why this is problematic** H6 is an entire knowledge gap devoted to the argument that sex dimorphism in mTOR-longevity responses is *pervasive and under-reported*. The Atlas then under-reports it in two of the four places it states this specific result. A reviewer will use this to argue the sex-dimorphism gap is asserted rather than applied.

**Proposed correction** Add "in female mice; the effect was not significant in males" to both the SEL2009 finding and the S6K1 entity. Consider a systematic pass: any study whose effect is sex-specific should carry it in the `finding`, since that is the field that propagates to the static pages.

**Confidence: High**

---

### F6 — The most clinically important feedback loop in the pathway is missing from the graph

**Location** `ATLAS_EDGES` (absent); `gf` route story; corpus.

**Why this is problematic** There is **no S6K1 → IRS-1 edge**. This is the canonical mTORC1 negative-feedback arm — the textbook explanation for why mTOR inhibition raises Akt signalling and for a large part of rapalog-associated insulin resistance. Harrington 2004 (*JCB*) and Shah 2004 (*Curr Biol*) are absent from the corpus. UMX2004 (Um 2004, *Nature*) **is** present — a paper substantially about exactly this feedback — but is used only for longevity.

The `gf` route story tells the reader:
> "That loop is why mTOR inhibitors paradoxically *raise* Akt activity in patients."

attributing the phenomenon **solely to Grb10**. Grb10 is real (HSU2011, YUX2011) but it is the second-discovered, lesser arm. Teaching it as the explanation is a substantive pedagogical error in the Atlas's most-viewed diagram.

Separately, **CAR2008** ("Inhibition of mTORC1 leads to MAPK pathway activation through a PI3K-dependent feedback loop") sits in the corpus with **zero edges** — a third feedback arm entirely invisible in the graph. And there is **no MAPK/ERK input to mTORC1 anywhere**: ERK/RSK → TSC2 (Ma 2005 *Cell*, Roux 2004 *PNAS*) is absent as both paper and edge, so the Atlas presents mTORC1 as receiving PI3K/Akt and AMPK inputs only.

**Proposed correction** Add papers Harrington 2004 and Shah 2004; add edges `S6K1-IRS1` (inhibits) and `IRS1-PI3K` (activates); add `MTORC1-MAPK` from the CAR2008 paper already held. Rewrite the `gf` story to present S6K1→IRS-1 as the principal loop with Grb10 and RTK rebound as parallel arms. Add Ma 2005 / Roux 2004 and an `ERK/RSK-TSC` edge, or log the MAPK input as an explicit Knowledge_Gap.

**Confidence: High**

---

### F7 — H1 is a gap in the corpus, not a gap in the literature

**Location** Gap H1, "Sensor-selective geroprotection without the metabolic penalty", confidence 0.75.

**The Atlas says**
> "Every amino-acid sensor (Sestrin2, CASTOR1, SAMTOR, v-ATPase) is supported ONLY by tier-D mechanistic studies and links to **ZERO aging/longevity outcomes**."

**Why this is problematic** That is true of the Atlas's corpus and false of the field. **Lee et al., *Science* 2010, "Sestrin as a feedback inhibitor of TOR that prevents age-related pathologies"** showed that loss of *Drosophila* Sestrin produces triglyceride accumulation, mitochondrial dysfunction, muscle degeneration and cardiac malfunction, all rescued by TOR inhibition or AMPK activation. That is precisely a sensor → aging-phenotype link. A 2022 *Nature* paper on Sestrin-mediated adaptation to low-leucine diets in *Drosophila* adds an organismal-physiology link. Neither is in the corpus; the corpus holds only the mechanistic Sestrin papers (WOL2015, SAX2015, CHA2014, PAR2014).

The deeper issue is methodological and applies to **all ten gaps**: `gap_finder.py` derives gaps by joining the entity graph to evidence tiers, so it can only ever detect *absences in this corpus*. A hand-curated 275-paper corpus will have many absences that are not knowledge gaps. Presenting the output as "what we don't know" without that caveat is the most attackable claim on the site.

**Proposed correction** Add Lee 2010 and regrade H1 — it may survive as a weaker gap (no *mammalian* sensor-selective geroprotection data) but not in its current form. Add a standing caveat to the gaps tab: *"Gaps are computed against this corpus, not against the literature. A gap here means the Atlas holds no linking study — which may mean none exists, or may mean the corpus is incomplete."* This one sentence converts the section's biggest liability into a statement of method.

**Confidence: High** on Lee 2010; **High** on the methodological point.

---

### F8 — A canonical pathway step is propped up by a tangential 2026 toxicology paper

**Location** Edges `LKB1-AMPK` and `AMPK-MITOPHAGY`; both cite **only ZHU2026**.

**Why this is problematic** LKB1 → AMPK is one of the most firmly established steps in metabolic signalling (Hawley 2003; Woods 2003; Shaw 2004 *PNAS*). None of those papers is in the corpus. The Atlas instead supports it with ZHU2026 — "LKB1/AMPK deficiency aggravates mitochondrial DNA leakage via mTOR-dependent mitophagy in **trichloroethylene-induced liver injury**." That paper is consistent with the step but was not designed to establish it, and a reviewer will read the citation as evidence the corpus was back-filled to satisfy the "no edge without a study" rule.

The Atlas's own Relations table documentation anticipates exactly this: *"A canonical textbook step with no supporting study in the corpus should be logged as a Knowledge_Gap instead, not invented here."* The rule was written and then not followed.

**Proposed correction** Add Shaw 2004 (and ideally Hawley 2003) and re-cite both edges. If they will not be added, mark the edges as corpus-incomplete rather than leaving ZHU2026 as the sole authority.

**Confidence: High**

---

### F9 — The metformin mechanism is presented as settled and is not

**Location** Edge `METFORMIN-AMPK` (cites ZHO2001); entity "Metformin".

**The Atlas says**
> "Metformin works **largely by** nudging the cell's energy balance so AMPK switches on." / "activates AMPK and indirectly inhibits mTORC1."

**Why this is problematic** This is the 2001 model. Foretz et al. (*JCI* 2010) showed metformin still suppresses hepatic gluconeogenesis in **AMPK-null and LKB1-null** hepatocytes; Madiraju et al. (*Nature* 2014) identified mitochondrial glycerophosphate dehydrogenase inhibition; Kalender et al. (*Cell Metab* 2010) showed metformin inhibits mTORC1 via the Rag GTPases **independently of AMPK**. "Works largely by AMPK" is contested at best. ZHO2001 supports *that metformin activates AMPK*, not *that this is how it works*.

**Proposed correction** "Metformin activates AMPK (ZHO2001) and inhibits mTORC1, but the relative contribution of AMPK-dependent and AMPK-independent routes remains disputed — metformin retains activity in AMPK- and LKB1-null hepatocytes." Add Foretz 2010 and Kalender 2010, or flag the edge Contested.

**Confidence: High** that the current framing is outdated.

---

### F10 — The everolimus→LAM edge overstates the trial it cites

**Location** Edge `EVE-LAM`, cites BIS2013 only.

**The Atlas says** Everolimus → Lymphangioleiomyomatosis: *"The same TSC biology drives sporadic LAM, and the same drug shrinks those lesions."*

**Why this is problematic** BIS2013 is EXIST-2, whose endpoint was **renal angiomyolipoma** response in patients who had TSC *or* sporadic LAM. It did not test everolimus against LAM lung disease. The Atlas's own record for BIS2013 says so: *"targeting kidney tumors (angiomyolipomas)."* Meanwhile the trial that *does* support treating LAM — MCC2011, the MILES trial, which stabilised FEV1 — used **sirolimus**, and is not linked to this edge at all.

As written, the edge implies a licensed everolimus indication in LAM that the cited evidence does not establish.

**Proposed correction** Either re-scope the edge to `EVE-ANGIOMYOLIPOMA` and add a separate `RAPA-LAM` edge citing MCC2011, or retitle the mechanism: *"EXIST-2 tested everolimus against renal angiomyolipoma in TSC and sporadic LAM; the lung disease itself was treated with sirolimus in MILES (MCC2011)."*

**Confidence: Medium-High**

---

### F11 — One edge is a category error

**Location** Edge `TUMOR-RCC`: "Tumor growth → *activates* → Renal cell carcinoma", directness "Correlative".

**Why this is problematic** RCC is an *instance* of tumour growth, not a downstream target of it. This is a taxonomic relation rendered as a causal one, in a graph whose value depends on every arrow meaning "regulates". It also inflates the apparent evidence density of the `clin` route.

**Proposed correction** Delete the edge, or replace it with what is presumably meant: `MTORC1-RCC` ("RCC frequently carries lesions leaving mTORC1 constitutively active"), citing IYE2012.

**Confidence: Medium-High**

---

## WORTH ADDRESSING

### F12 — H2's confidence (0.85) is hard to reconcile with PEARL

H2 proposes that intermittent or mTORC1-selective dosing captures longevity without insulin resistance. PEARL (MOE2025) tested **intermittent rapamycin, 5 vs 10 mg/week, in humans** — essentially H2's proposed regimen — and missed its primary endpoint. H2's basis mentions PEARL only as evidence that "no mTORC1-selective human aging readout exists." A human trial of the proposed intervention failing its primary endpoint should move a confidence estimate downward, or the basis should explain why it does not (wrong endpoint, wrong duration, wrong population). At 0.85 H2 is the Atlas's most confident gap. **Confidence: Medium** — confidence scores are editorial, but the asymmetry in how PEARL is used across H2 and H5 is real.

### F14 — The GATOR2→GATOR1 caveat is dated

The ctx reads *"the biochemical mechanism by which GATOR2 inhibits GATOR1 is still not fully resolved."* Valenstein et al. (*Nature* 2022) determined the GATOR2 structure and substantially advanced this; the paper is absent from the corpus. The caveat is not wrong — the step is still debated — but it is stated as of ~2017. **Confidence: Medium**

### F15 — The "Insulin resistance" entity asserts a single cause

*"Metabolic side effect of chronic mTORC2 inhibition."* In humans, rapalog dysglycaemia also involves S6K1→IRS-1 feedback (see F6) and direct beta-cell effects; the mTORC2 attribution rests on LAM2012, which is mouse. An outcome entity stating one mechanism as definitional is stronger than the evidence. Suggest: *"Metabolic side effect of chronic mTOR inhibition. In mice, mTORC2 disruption is a major contributor (LAM2012); in humans the relative contributions of mTORC2 loss, S6K1–IRS-1 feedback and direct beta-cell effects are not resolved."* **Confidence: Medium**

### F16 — "in patients" is not supported in the `gf` route story

*"That loop is why mTOR inhibitors paradoxically raise Akt activity **in patients**."* The supporting studies are ROD2011 (cancer cell lines) and ORE2006 (cells and xenografts). The rebound is well documented preclinically; "in patients" needs a human pharmacodynamic citation or should read "in cells and xenografts, and is the leading explanation for the Akt rebound seen clinically." **Confidence: Medium**

---

## What I checked and found correct

I am listing these because a review that reports only faults is not a review.

**The amino-acid sensing module is accurate and current.** GATOR1 as GAP for RagA/B; FLCN–FNIP as GAP for RagC/D; KICSTOR as the lysosomal dock; SLC38A9 correctly described as both an arginine sensor *and* a leucine effluxer (the Wyant 2017 refinement, which many reviews still omit); the v-ATPase "inside-out" model correctly flagged as requiring luminal accumulation. The LARS and glutamine routes are correctly marked **Contested** with the Rag-independence discrepancy named.

**`RAG-MTORC1` states the single most-blurred distinction in the field correctly:** *"This is a relocation, not an activation — the kinase is moved to where its activator waits."* Most reviews elide this. The `aa` route story reinforces it.

**The rapamycin module is unusually careful.** Two-part FKBP12 mechanism; partial 4E-BP1 blockade as the origin of the rapamycin-resistant output problem; `RAPA-MTORC2` marked Contested with an explicit time- and cell-type-dependence caveat. The `rapa` story ("the dashed arrow is the one everyone gets wrong") is correct.

**The p-S6K caveat on `MTORC1-S6K1`** — *"p-S6K is a proxy, not the phenotype. Many 'mTORC1 activity' claims rest on this single band"* — is a methodological warning most primary papers do not make.

**Caveats that are present and correct:** `4EBP1-LONGEVITY` (fly only, DR only); `S6K1-LONGEVITY` (female mice); `EVE-BREAST` (PFS not OS); `TEM-RCC` (poor-prognosis subgroup; combination arm no better); `EVE-TSC` ("lesions regrow — suppression, not cure"); `EVE-IMMUNE` (Contested, with MAN2021's non-replication named); `MTORC1-LONGEVITY` ("no human hard-endpoint evidence").

**Corpus coverage is genuinely strong.** Vézina 1975, Heitman 1991, Brown 1994 / Sabatini 1994/1995, the Rag series, the sensor series, TFEB series, cryo-EM structures (YAN2017, CHE2018, STU2018, SCA2020), the ITP papers, all six rapalog registration trials, and — creditably — the contrarian literature: **Neff 2013** ("limited effects on aging"), MAN2021's failed phase 3, PEARL's missed endpoint, Blagosklonny's hyperfunction theory, and the ITP null results. Including Neff 2013 is a real mark of good faith.

**The seven pathway routes are well constructed.** Node placement, the "spine" step-through, and the contrast the `clin` route draws against the `aa` route (B badges vs D badges, "not one of them ends in lifespan") is exactly the argument the Atlas should be making.

**Preprint and registered-trial handling is correct** — no A–D tier on any non-peer-reviewed record, verified across all 275.

**Signs on all 93 edges were checked individually.** Apart from the Sestrin2 *entity* text (F2) and the `TUMOR-RCC` category error (F11), I found **no sign errors** — including the ones that are easy to get backwards: `MTORC1-4EBP1` (inhibits), `GATOR2-GATOR1` (inhibits, double negative), `REDD1-TSC` (activates), `MTORC2-INSULINRES` (inhibits), `S6K1-LONGEVITY` (inhibits) vs `4EBP1-LONGEVITY` (activates).

---

## Priority

| # | Finding | Confidence | Blocking? |
|---|---|---|---|
| F1 | ARR2015 lifespan claim unsupported | High | **Yes** |
| F2 | Sestrin2 entity inverted | High | **Yes** |
| F3 | FLCN/BHD contradicts cited NAP2020 | High | **Yes** |
| F4 | Tier rule defined ≠ applied; LAM2012, DEN2026 | High | **Yes** |
| F5 | S6K1 sex-specificity inconsistent | High | Should fix |
| F6 | S6K1→IRS-1 feedback and MAPK input missing | High | Should fix |
| F7 | H1 is a corpus gap, not a knowledge gap | High | Should fix |
| F8 | LKB1→AMPK on a tangential citation | High | Should fix |
| F9 | Metformin mechanism outdated | High | Should fix |
| F10 | EVE-LAM overstates EXIST-2 | Med-High | Should fix |
| F11 | TUMOR-RCC category error | Med-High | Should fix |
| F12 | H2 confidence vs PEARL | Medium | Consider |
| F13 | FLCN edge omits substrate selectivity | Med-High | With F3 |
| F14 | GATOR2 caveat dated | Medium | Consider |
| F15 | Insulin-resistance entity single-cause | Medium | Consider |
| F16 | "in patients" unsupported | Medium | Consider |

**Papers to add:** Harrington 2004; Shah 2004; Shaw 2004 (and Hawley 2003); Lee 2010 *Science*; Ma 2005 / Roux 2004; Foretz 2010 and Kalender 2010; Valenstein 2022.

**What I did not find:** no sign errors in the edge set, no fabricated citations, no preprint carrying an A–D tier, and no instance of the pathway diagram contradicting the edge data it is drawn from.
