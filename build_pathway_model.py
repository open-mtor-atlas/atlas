#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
build_pathway_model.py – Pathway & Mechanism redesign, Fáze 1.

PROČ TOHLE EXISTUJE
-------------------
Do dneška měl Atlas DVĚ nezávislé reprezentace téže dráhy:

  1. MAP_NODES / MAP_CORE_EDGES / MAP_PERIPH_EDGES  (ruční x/y, "Entity Map")
  2. ATLAS_EDGES / ATLAS_ROUTES                     (kurátorované hrany + 7 tras)

Nikdo je nedržel v synchronu. Entity Map kreslila 42 core hran, Mechanism
Explorer 100 – a část "hran" v Entity Map nebyla biologie vůbec, jen
co-citace ("linked via shared-study evidence"), nakreslená stejným vizuálním
jazykem jako mechanismus. To je přesně ten typ tiché nepřesnosti, kterou
recenzent najde.

Tenhle skript zavádí JEDEN zdroj pravdy: pathway/model.json.

  * Uzly mají kompartment, třídu a vysvětlení ve třech úrovních.
  * Hrany mají mechanistický TYP (fosforylace / rekrutace / vazba / GAP …)
    ODDĚLENĚ od funkčního ZNAKU (aktivuje / inhibuje / je nutné pro).
    To je vědecky podstatný rozdíl, který stará data neuměla vyjádřit:
    Rag GTPázy mTORC1 *rekrutují*, ale neaktivují ho. Rheb ho aktivuje.
  * Hrany mají directness, timescale, species, model, boundary conditions,
    podpůrné i konfliktní studie, a – nově – DVĚ oddělené jistoty:
    mechanistickou důvěru a lidskou relevanci. Tier studie není totéž
    co důvěra v mechanismus (nález F4 externí recenze).
  * Layout se POČÍTÁ (kompartmentové pásy + barycentrické řazení), ne ladí
    ručně. Staré route.bows / route.ctrl byly ruční konstanty s komentářem
    "regenerate them if you move a node" – to je dluh, ne architektura.

VSTUP   atlas_data/relations_baked.json (hrany; zdroj Airtable Relations, od 2026-09-30)
        index.html  (ATLAS_ROUTES)
        atlas_data/studies_baked.json (validace SID)
VÝSTUP  pathway/model.json

Spouštěj vždy přes:  py build_pathway_model.py
Validuj vždy přes:   py validate_pathway.py --strict
"""

import json
import os
import re
import sys
import datetime

ROOT = os.path.dirname(os.path.abspath(__file__))
OUT_DIR = os.path.join(ROOT, "pathway")
OUT = os.path.join(OUT_DIR, "model.json")

MODEL_VERSION = "2.0.0"
CURATOR = "Oliver's mTOR Atlas curation team"
REVIEW_DATE = "2026-07-29"

# ---------------------------------------------------------------------------
# 1. Kompartmenty – prostorová osnova.
#
# Pořadí = pořadí pásů shora dolů. `physical: false` znamená "tohle NENÍ
# místo v buňce" – vstupy a fenotypy dostanou jiný vizuální jazyk, aby
# nikdo nezískal dojem, že "Longevity" je organela.
# ---------------------------------------------------------------------------
# A11 (audit 2026-10-07): "human" v poli species nestačí. Lidské buňky,
# linie, organoidy nebo xenografty jsou lidský MATERIÁL, ne pozorování
# v člověku. Za lidský model se počítá jen položka species, která obsahuje
# "human"/"patient"/"participant" a NEOBSAHUJE kvalifikátor buněk/materiálu.
# Smíšené práce ("human; mouse") projdou, protože aspoň jedna položka je
# in-human. Viz test v _selftest_in_human() níže.
_IN_VITRO_QUALIFIERS = ("cell", "line", "organoid", "in vitro", "ipsc",
                        "xenograft", "tissue explant", "lysate", "recombinant")
_HUMAN_WORDS = ("human", "patient", "participant", "volunteer", "adult")

def in_human_species(sp):
    """True jen když aspoň jedna položka species popisuje člověka samotného."""
    import re as _re
    for tok in _re.split(r"[;,/]| and ", (sp or "").lower()):
        tok = tok.strip()
        if not tok:
            continue
        if any(w in tok for w in _HUMAN_WORDS) and not any(q in tok for q in _IN_VITRO_QUALIFIERS):
            return True
    return False

def _selftest_in_human():
    assert not in_human_species("human cells")
    assert not in_human_species("human cell lines; mouse")
    assert not in_human_species("human iPSC-derived neurons")
    assert in_human_species("human")
    assert in_human_species("human; mouse")
    assert in_human_species("patients, mouse")
    assert not in_human_species("mouse")
_selftest_in_human()


COMPARTMENTS = [
    {
        "id": "input", "name": "Inputs", "short": "IN", "physical": False,
        "blurb": "Nutrients, hormones, stresses and drugs – the information the cell is trying to read. Not a cellular location.",
        "sensing_note": "Amino acids are shown here as inputs, but they are sensed *inside* the cell: leucine by cytosolic Sestrin2, arginine by cytosolic CASTOR1 and by lysosomal SLC38A9, SAM by cytosolic SAMTOR.",
    },
    {
        "id": "pm", "name": "Plasma membrane", "short": "PM", "physical": True,
        "blurb": "Where receptors meet the outside world and where PIP3 is made. Akt has to come here to be switched on.",
    },
    {
        "id": "cytosol", "name": "Cytosol", "short": "CYT", "physical": True,
        "blurb": "The mixing bowl. Most sensors, kinases and brakes live here and diffuse until they are recruited somewhere specific.",
    },
    {
        "id": "lyso", "name": "Lysosomal surface", "short": "LYS", "physical": True,
        "blurb": "The decision platform. In the amino-acid route this is where mTORC1 is switched on, because this is where it meets Rheb. Much of nutrient sensing is about getting mTORC1 to this membrane; other membranes and the nucleus also host mTOR activity (see the open localisations).",
        # Deklarované zjednodušení. Zamlčené zjednodušení je přesně to, co
        # tenhle redesign zakazuje – takže se řekne nahlas i tam, kde je
        # pedagogicky správné.
        "sensing_note": "Simplified on purpose: this band means 'the endomembrane surface where mTORC1 is switched on'. Rheb is not exclusively lysosomal – a large fraction sits on the ER and Golgi, and which pool activates mTORC1 is still argued. Rheb is drawn here because the lysosome is where it meets mTORC1, which is the fact the pathway logic turns on. The ER, Golgi and peroxisome are not drawn as separate bands.",
    },
    {
        "id": "nucleus", "name": "Nucleus", "short": "NUC", "physical": True,
        "blurb": "Where the slow, transcriptional arm of the pathway acts. Hours, not seconds.",
    },
    {
        "id": "mito", "name": "Mitochondrion", "short": "MITO", "physical": True,
        "blurb": "Both a target of mTORC1 (biogenesis) and a source of the energy signal that AMPK reads.",
    },
    {
        "id": "autophagy", "name": "Autophagy machinery", "short": "AUT", "physical": True,
        "blurb": "The recycling plant mTORC1 keeps switched off while nutrients last.",
    },
    {
        "id": "outcome", "name": "Biological outcomes", "short": "OUT", "physical": False,
        "blurb": "Cell-, tissue- and organism-level consequences. Not a cellular location – and the evidence here is a different kind of evidence from the molecular steps above.",
    },
]

# ---------------------------------------------------------------------------
# 2. Uzly – kompartment, třída, a role ve třech úrovních.
#
# `cls`:  nut | hormone | stress | drug | protein | complex | organelle
#         | process | phenotype | disease
# Klíč je Entity_Name ze stávajícího korpusu, aby zůstaly funkční odkazy
# do Entity Map a na prerenderované /gene/… stránky.
# ---------------------------------------------------------------------------
NODES = {
    # ---- inputs -----------------------------------------------------------
    "Leucine": ("input", "nut", "The amino acid the cell watches most closely.",
                "Essential BCAA; its cytosolic concentration is read by Sestrin2 and (contested) by LARS.",
                "Binds Sestrin2 with ~20 µM Kd – within the range over which intracellular leucine actually fluctuates, which is the main argument that Sestrin2 is a physiological sensor rather than a binder."),
    "Arginine": ("input", "nut", "A second amino acid the cell counts.",
                 "Sensed twice: by cytosolic CASTOR1 and by the lysosomal transporter SLC38A9.",
                 "Two-sensor architecture lets the cell distinguish cytosolic from lysosomal arginine pools; the functional division of labour is still argued."),
    "Glutamine": ("input", "nut", "Abundant amino acid with a disputed route in.",
                  "Activates mTORC1 in some settings without the Rag GTPases (Arf1-dependent route).",
                  "Rag-independent glutamine signalling via Arf1 is reported but not universally reproduced; treat the route as unsettled."),
    "S-adenosylmethionine (SAM)": ("input", "nut", "Reports how much methyl-donor the cell has.",
                                   "Methionine-derived metabolite read by SAMTOR – the cell's methionine proxy.",
                                   "SAM binds SAMTOR (Kd ~7 µM); links one-carbon metabolism to mTORC1 independently of the leucine and arginine arms."),
    "Growth hormone / IGF-1 axis": ("input", "hormone", "The 'there is food and it is safe to grow' hormone signal.",
                                    "Endocrine input acting through receptor tyrosine kinases, IRS proteins and PI3K.",
                                    "Compressed here into one node; the axis spans GH→hepatic IGF-1→IGF1R/InsR→IRS→PI3K, and dwarf-mouse longevity phenotypes sit on it."),
    "Energy & cellular stress": ("input", "stress", "Running out of fuel.",
                                 "Rising AMP:ATP ratio and other stresses that activate AMPK.",
                                 "AMP and ADP binding to the AMPK γ-subunit plus LKB1-dependent T172 phosphorylation; also covers glucose withdrawal sensed via aldolase/lysosomal AXIN–LKB1."),
    "Hypoxia": ("input", "stress", "Not enough oxygen.",
                "Low O₂ suppresses mTORC1 partly through transcriptional induction of REDD1.",
                "REDD1 (DDIT4) induction by hypoxia is HIF-1-dependent in the wider literature, but the corpus paper for this arm (BRU2004) does not establish the HIF step, so the map draws hypoxia to REDD1 directly. Hypoxia also acts faster via AMPK and via direct effects on translation, so REDD1 is one arm, not the whole story."),
    "Rapamycin": ("input", "drug", "The drug that made this pathway famous.",
                  "Allosteric mTORC1 inhibitor that works only as a complex with FKBP12.",
                  "Sirolimus. Not an active-site inhibitor: the FKBP12–rapamycin complex binds the FRB domain and partially occludes substrate access, which is why 4E-BP1 phosphorylation is only incompletely blocked."),
    "Everolimus": ("input", "drug", "A rapamycin derivative used in clinic.",
                   "Rapalog licensed in several cancers and in tuberous sclerosis complex.",
                   "RAD001. Same FKBP12-dependent allosteric mechanism as rapamycin, better oral pharmacokinetics; the clinical evidence base here is trial evidence, not mechanism."),
    "Temsirolimus": ("input", "drug", "Another clinical rapamycin derivative.",
                     "Intravenous rapalog, first mTOR inhibitor approved for advanced renal cell carcinoma.",
                     "CCI-779; a prodrug converted to sirolimus. Its RCC approval rests on the ARCC trial."),
    "Metformin": ("input", "drug", "A diabetes drug that quietens mTORC1 indirectly.",
                  "Lowers mTORC1 activity; the mechanism is genuinely unsettled.",
                  "Complex I inhibition→AMPK, AMPK-independent Rag inhibition, lysosomal PEN2–ATP6AP1 sensing and gut-microbiome effects have all been proposed; clinical doses may not reach the concentrations used in vitro."),
    "Integrated stress response": ("input", "stress", "The cell's alarm for damaged protein-making.",
                                   "eIF2α-kinase-driven translational reprogramming that intersects mTORC1.",
                                   "ATF4 is the shared node: mTORC1 drives ATF4 translation, and ISR activation drives ATF4 independently, so the two systems are cross-wired rather than serial."),


    # ---- second- and third-generation mTOR inhibitors --------------------
    # Potřebné pro trasu "Cancer hijacks mTOR – and then escapes the drug":
    # bez nich končí příběh u rapalogu a čtenář nedozví, co s tím pole udělalo.
    "ATP-competitive mTOR inhibitors": ("input", "drug", "Drugs that block mTOR's engine instead of getting in its way.",
        "Torin1, AZD8055 and relatives occupy the mTOR active site directly, inhibiting both complexes.",
        "Designed as a research answer to rapamycin's incompleteness, then developed clinically. Because they compete with ATP at the catalytic site they do not need FKBP12, they suppress 4E-BP1 phosphorylation that rapalogs leave standing, and they hit mTORC2 as well – which is both their advantage and their toxicity problem."),
    "Bi-steric mTORC1-selective inhibitors": ("input", "drug", "A newer design: deep inhibition of one complex only.",
        "Bivalent compounds (e.g. RMC-5552) engaging both an FKBP12-dependent site and the active site, giving deeper mTORC1 inhibition with selectivity over mTORC2.",
        "The attempt to have it both ways: the depth of an active-site inhibitor with the mTORC1 selectivity of a rapalog, so that 4E-BP1 is actually suppressed without incurring the mTORC2-dependent metabolic toxicity. RMC-5552 has completed a phase 1 trial in advanced solid tumours (SCH2025): a safety and pharmacodynamic result, not an efficacy verdict."),
    "Resistance exercise / mechanical load": ("input", "stress", "Lifting something heavy.",
        "Mechanical loading of skeletal muscle, the physiological stimulus for hypertrophy, acting through mTORC1.",
        "One of the very few places in this map where the causal chain has been interrupted in living humans: rapamycin blocks the contraction-induced rise in muscle protein synthesis (DRU2009). The upstream route is only partly IGF-1-dependent – mechanical load reaches mTORC1 through mechanisms that do not require circulating growth factor, which is why loading and hormone signalling are not interchangeable."),
    "Fasting / caloric restriction": ("input", "stress", "Not eating, for a while.",
        "Reduced nutrient and energy availability, the intervention that most reliably lowers mTORC1 signalling in vivo.",
        "Distinguish the two axes deliberately: total calories and macronutrient composition are not the same lever (SOL2014 found the RATIO mattered more than the intake for cardiometabolic outcome and lifespan in mice). Two-year caloric restriction is tolerable in non-obese humans (ROM2016) but that trial measured safety, not lifespan – no human longevity data exists for this or any other mTOR-lowering intervention."),
    # ---- plasma membrane --------------------------------------------------
    "PI3K": ("pm", "protein", "Makes the membrane signal that pulls Akt in.",
             "Class I PI3K phosphorylates PIP2 to PIP3 at the plasma membrane.",
             "p110/p85 heterodimer; PIK3CA is one of the most frequently mutated oncogenes in human cancer. Its output is a lipid, not a phosphoprotein – which is why PTEN reverses it."),
    "PTEN": ("pm", "protein", "Erases the signal PI3K writes.",
             "Lipid phosphatase that converts PIP3 back to PIP2.",
             "PTEN does not inhibit the PI3K enzyme; it dephosphorylates PI3K's product, PIP3. Haploinsufficient tumour suppressor with dose-dependent phenotypes."),
    "IRS-1 / IRS-2": ("pm", "protein", "The adaptor that connects the insulin receptor to PI3K.",
                      "Scaffold recruiting PI3K to activated insulin/IGF-1 receptors.",
                      "Serine phosphorylation by S6K1 (and others) triggers IRS-1 degradation – the molecular basis of the best-characterised mTORC1 feedback loop. Note the direction: the loop degrades IRS-1 when mTORC1 is ACTIVE, so it is a mechanism of insulin resistance under nutrient excess. Inhibiting mTORC1 releases it and raises Akt signalling instead."),
    "Akt/PKB": ("pm", "protein", "The main 'grow' relay from growth factors.",
                "AGC kinase requiring PIP3 recruitment plus two phosphorylations to be fully active.",
                "T308 by PDK1 and S473 by mTORC2. Recruitment and activation are separate events – a distinction the older Atlas diagram blurred."),
    "mTORC2": ("pm", "complex", "mTOR's second, less famous complex.",
               "mTOR–Rictor–SIN1–mLST8; phosphorylates Akt, SGK1 and PKC.",
               "Largely plasma-membrane associated and PI3K-responsive via the SIN1 PH domain; acutely rapamycin-insensitive, which is the cleanest way to separate mTORC1 from mTORC2 biology experimentally."),

    # ---- cytosol ----------------------------------------------------------
    "Sestrin2": ("cytosol", "protein", "A leucine detector that works as a brake.",
                 "Leucine-binding negative regulator: without leucine it holds GATOR2 inactive.",
                 "Sestrin2 is a *negative* regulator. Leucine binding releases GATOR2 – the pathway is switched on by removing a brake. Also stress-inducible via p53, so it sits at a stress/nutrient junction."),
    "CASTOR1": ("cytosol", "protein", "An arginine detector that works as a brake.",
                "Arginine-binding inhibitor of GATOR2.",
                "Homodimer (or heterodimer with CASTOR2); arginine binding dissociates it from GATOR2. Same double-negative logic as Sestrin2."),
    "SAMTOR": ("cytosol", "protein", "A methionine detector.",
               "SAM-binding protein that regulates GATOR1 via KICSTOR.",
               "SAM binding dissociates SAMTOR from GATOR1–KICSTOR, relieving GATOR1 activity. Wires one-carbon metabolism into nutrient sensing."),
    "LARS (leucyl-tRNA synthetase)": ("cytosol", "protein", "A contested second leucine detector.",
                                      "Proposed leucine sensor acting as a GAP for RagD.",
                                      "The moonlighting-GAP model has not reproduced cleanly across labs and competes with the Sestrin2 model; shown here as contested rather than omitted."),
    "TSC1/TSC2": ("cytosol", "complex", "The pathway's master brake.",
                  "TSC1–TSC2–TBC1D7 complex; a GAP that switches Rheb off.",
                  "Integrates Akt, AMPK, ERK/RSK, GSK3 and REDD1 inputs. Regulation is substantially about lysosomal recruitment, not only phosphorylation-driven activity change."),
    "TBC1D7": ("cytosol", "protein", "The third, easily forgotten subunit of the brake.",
               "Obligate TSC complex subunit needed for complex stability.",
               "Loss produces a mild megalencephaly phenotype far weaker than TSC1/TSC2 loss, so it is a stabiliser rather than a catalytic component."),
    "AMPK": ("cytosol", "complex", "The low-fuel sensor.",
             "Energy-stress kinase that both activates TSC2 and directly inhibits Raptor.",
             "αβγ heterotrimer. Two independent arms onto mTORC1 plus a direct arm onto ULK1, classically read as activating; whether AMPK activates or restrains ULK1 under energy stress is now disputed (see AMPK-ULK1)."),
    "LKB1 (STK11)": ("cytosol", "protein", "The kinase that arms AMPK.",
                     "Constitutive upstream kinase phosphorylating AMPK T172.",
                     "Tumour suppressor mutated in Peutz–Jeghers syndrome and in lung adenocarcinoma; also the reason some cells cannot mount an AMPK response at all."),
    "ULK1": ("cytosol", "protein", "The switch that starts self-digestion.",
             "Autophagy-initiating kinase, inhibited by mTORC1 and activated by AMPK.",
             "mTORC1 phosphorylates S757 to block the AMPK–ULK1 interaction; ULK1 also feeds back to phosphorylate and dampen AMPK, making this a closed loop rather than a switch."),
    "S6K1": ("cytosol", "protein", "mTORC1's best-known output kinase.",
             "Ribosomal protein S6 kinase; the standard readout of mTORC1 activity.",
             "T389 phosphorylation by mTORC1 is rapamycin-sensitive, which is why S6K1 became the field's default assay – and why the field long over-read rapamycin as a complete mTORC1 inhibitor."),
    "4E-BP1": ("cytosol", "protein", "A cap on protein-making that mTORC1 removes.",
               "Translational repressor released from eIF4E upon multi-site phosphorylation.",
               "Only partially rapamycin-sensitive. This goes a long way to explain the rapalog/Torin discrepancy and was a main motivation for ATP-competitive inhibitors."),
    "eIF4E": ("cytosol", "protein", "The clamp that starts reading mRNA.",
              "Cap-binding translation initiation factor.",
              "Rate-limiting for cap-dependent initiation; a proto-oncogene in its own right when overexpressed."),
    "PDCD4": ("cytosol", "protein", "Another brake on protein-making.",
              "Inhibits eIF4A; degraded after S6K1 phosphorylation.",
              "S6K1 phosphorylates S67, creating a βTRCP degron – an mTORC1 output that works by destroying a repressor rather than activating an enzyme."),
    "PRAS40": ("cytosol", "protein", "A plug in mTORC1's substrate slot.",
               "Raptor-binding inhibitor displaced by Akt phosphorylation.",
               "AKT1S1. Competes with substrate for the Raptor TOS-motif site; its displacement is a substrate-access mechanism, not a change in kinase catalytic rate."),
    "Grb10": ("cytosol", "protein", "A brake mTORC1 puts on its own upstream signal.",
              "mTORC1 substrate that inhibits insulin/IGF-1 receptor signalling.",
              "Stabilised by mTORC1 phosphorylation; one of two arms (with S6K1→IRS-1) of negative feedback onto PI3K, and an imprinted gene with growth phenotypes."),
    "DEPTOR": ("cytosol", "protein", "An in-built damper on both complexes.",
               "mTOR-binding inhibitor of mTORC1 and mTORC2.",
               "Overexpressed in a subset of multiple myeloma, and those cells need it: knockdown kills them (PET2009). An inhibitor of the pathway that the tumour is nonetheless addicted to."),
    "FKBP12": ("cytosol", "protein", "The protein rapamycin must borrow.",
               "Prolyl isomerase that forms the drug-receptor complex with rapamycin.",
               "FKBP1A. Rapamycin has essentially no activity against mTOR without it, which is why FKBP12 expression sets rapalog sensitivity."),
    "ERK / RSK (MAPK)": ("cytosol", "protein", "A second growth pathway that presses the same brake.",
                         "ERK and RSK phosphorylate TSC2 to inhibit it, and are activated when mTORC1 is blocked.",
                         "ERK S664 and RSK S1798 on TSC2. mTORC1 inhibition relieves feedback and activates MAPK PI3K-dependently – the basis for combined mTOR/MEK strategies."),
    "REDD1 (DDIT4)": ("cytosol", "protein", "A stress-made brake amplifier.",
                      "Hypoxia-induced protein that promotes TSC-dependent mTORC1 inhibition.",
                      "Proposed to release TSC2 from 14-3-3 sequestration; short half-life makes it a transient rather than a maintained signal."),
    "mTOR": ("cytosol", "protein", "The kinase at the centre of everything.",
             "Serine/threonine kinase, catalytic subunit of both mTORC1 and mTORC2.",
             "PIKK-family kinase. The same catalytic subunit in two complexes with different partners, locations, substrates and drug sensitivities – the complex, not the kinase, is the unit of biology."),
    "Raptor": ("cytosol", "protein", "The part that makes mTOR into mTORC1.",
               "Substrate-presenting subunit defining mTORC1 and its lysosomal targeting.",
               "Recognises TOS motifs; the AMPK phosphorylation site and the Rag-binding surface both sit here, so Raptor is where location and inhibition converge."),
    "Rictor": ("cytosol", "protein", "The part that makes mTOR into mTORC2.",
               "Defining subunit of mTORC2.",
               "Confers acute rapamycin insensitivity and, with SIN1, the substrate specificity for Akt S473."),
    "SIN1 / MAPKAP1": ("cytosol", "protein", "mTORC2's growth-factor antenna.",
                       "mTORC2 subunit whose PH domain makes the complex PI3K-responsive.",
                       "MAPKAP1. The PH domain inhibits mTORC2 until PIP3 relieves it – the cleanest mechanism for how growth factors reach mTORC2."),
    "mLST8": ("cytosol", "protein", "A shared subunit that matters more to mTORC2.",
              "GβL; present in both complexes but essential only for mTORC2 in vivo.",
              "Knockout phenocopies Rictor rather than Raptor loss, which is the standard genetic argument that mLST8 is an mTORC2-essential component."),
    "SGK1": ("cytosol", "protein", "Another kinase mTORC2 switches on.",
             "AGC kinase phosphorylated by mTORC2; controls ion transport and survival.",
             "Shares substrate motifs with Akt (e.g. NDRG1, used as the standard mTORC2 readout because it is Akt-independent)."),
    "Spalt-related (Salr)": ("cytosol", "protein", "A fly-only relay in this map.",
                             "Drosophila transcription factor linking the ISR to TOR suppression.",
                             "No established mammalian orthologue in this role; kept visible so the fly-derived longevity evidence is not silently generalised."),

    # ---- lysosomal surface ------------------------------------------------
    "GATOR2": ("lyso", "complex", "A brake on the brake.",
               "Pentameric complex (WDR24, WDR59, MIOS, SEH1L, SEC13) inhibiting GATOR1.",
               "Structures (Valenstein 2022) resolved the cage-like architecture and the Sestrin2/CASTOR1 binding surfaces; how it inhibits GATOR1 catalytically is still argued."),
    "GATOR1": ("lyso", "complex", "The switch-off machine for the Rags.",
               "DEPDC5–NPRL2–NPRL3; GAP for RagA/B.",
               "DEPDC5 loss causes focal epilepsy – a human phenotype that establishes GATOR1's physiological relevance beyond cell lines."),
    "KICSTOR": ("lyso", "complex", "The dock GATOR1 needs.",
                "KPTN–ITFG2–C12orf66–SZT2; tethers GATOR1 to the lysosome.",
                "Loss uncouples mTORC1 from nutrient status; SZT2 mutations cause a human epileptic encephalopathy."),
    "Rag GTPases": ("lyso", "protein", "The taxi that brings mTORC1 to the lysosome.",
                    "RagA/B–RagC/D heterodimers; nucleotide state determines mTORC1 recruitment.",
                    "Note the inversion: RagA/B is active when GTP-loaded, RagC/D when GDP-loaded. The Rags control mTORC1 *location*, not its catalytic activity."),
    "Ragulator": ("lyso", "complex", "The bolt holding the taxi to the membrane.",
                  "LAMTOR1–5 complex tethering the Rags to the lysosomal surface.",
                  "First reported as a RagA/B GEF (BAR2012); later work places its exchange activity on RagC, with SLC38A9 loading RagA with GTP. The tethering role is the better-established one; LAMTOR1 lipidation anchors the whole assembly."),
    "v-ATPase": ("lyso", "complex", "The pump the sensing machinery is built on.",
                 "Lysosomal proton pump physically and functionally coupled to Ragulator.",
                 "Required for amino-acid signalling; inhibitor experiments cannot fully separate the signalling role from loss of lysosomal acidification."),
    "SLC38A9": ("lyso", "protein", "A lysosomal arginine sensor and exporter.",
                "Transceptor: arginine-regulated component of the Rag–Ragulator machinery that also effluxes leucine.",
                "Its cytosolic N-terminus binds Rag–Ragulator arginine-dependently; the transport and signalling functions are separable and both matter."),
    "FLCN / FNIP1/2": ("lyso", "complex", "The switch that decides which substrates mTORC1 gets.",
                       "GAP for RagC/D; required for mTORC1 to phosphorylate TFEB.",
                       "Folliculin is a *positive* regulator of the RagC/D arm despite being a tumour suppressor in Birt–Hogg–Dubé – the substrate-selective mTORC1 pathway explains the apparent contradiction."),
    "Rheb": ("lyso", "protein", "The switch that turns mTORC1 on once the Rags have brought it to the lysosome.",
             "Small GTPase; GTP-loaded Rheb allosterically activates mTORC1.",
             "Realigns the mTOR active site; the convergence point of the entire growth-factor arm and the reason localisation alone is not activation. Note a declared simplification in this map: Rheb is farnesylated and distributes across the endomembrane system, with a substantial ER and Golgi pool, and which pool supplies the activating Rheb is still debated. It is drawn on the lysosomal band because that is where it meets mTORC1."),
    "mTORC1": ("lyso", "complex", "The growth decision itself.",
               "mTOR–Raptor–mLST8 (+PRAS40, DEPTOR); in the amino-acid route it is switched on at the lysosome.",
               "Coincidence detector: nutrients supply location via the Rags, growth factors supply activation via Rheb. Neither alone is sufficient – the central idea of the amino-acid route."),
    "Lysosome": ("lyso", "organelle", "The place where the decision is made.",
                 "Signalling platform as well as degradative organelle.",
                 "Amino-acid sensing, Rheb access, TFEB regulation and autophagosome fusion all happen on or in this one organelle."),


    # ---- organelle build-out (review pass 2, 2026-07-29) -----------------
    # Recenzent: mTORC1 je především lysosomální signální systém, a mapa má
    # slabě propojené mitochondrie a jádro. Všechny hrany níž jsou citované
    # z korpusu; kde citace není, hrana NENÍ (viz OPEN_LOCALISATIONS).
    "Lysosomal biogenesis": ("lyso", "process", "Making more recycling plants.",
                             "TFEB-driven expansion of the lysosomal compartment.",
                             "The return arm of the lysosome-to-nucleus circuit (SET2012): mTORC1 phosphorylation keeps TFEB out of the nucleus, and when it is released TFEB expands the very organelle on which mTORC1 is regulated. This closes a genuine homeostatic loop that a linear diagram cannot show."),
    "Mitochondrial dysfunction": ("mito", "stress", "Power plants in trouble.",
                                  "Loss of mitochondrial function, relayed to mTORC1 by AMPK and the HRI stress pathway.",
                                  "Genome-wide CRISPR screens (CON2021) show the relay is multitiered rather than single-channel: AMPK carries the energetic signal and heme-regulated inhibitor (HRI) carries a mitochondrial stress signal through the integrated stress response. mTORC1 therefore reads mitochondrial state through at least two independent routes."),
    "Oxidative phosphorylation": ("mito", "process", "Burning fuel for energy.",
                                  "Mitochondrial respiratory capacity, supported by mTORC1.",
                                  "Controlled through a YY1–PGC-1α transcriptional programme (CUN2007) and 4E-BP-dependent translation of respiratory components (MOR2013). Adipose Raptor knockout RAISES respiration (POL2008), which runs against this direction and is carried here as conflicting evidence, not as genetic confirmation."),
    "Reactive oxygen species": ("mito", "stress", "Chemical damage from burning fuel.",
                                "ROS generated by mitochondrial activity, both a consequence and a driver of mTOR signalling.",
                                "Bidirectional and therefore a loop, not an arrow: unleashing mTORC1 by deleting TSC1 floods haematopoietic stem cells with ROS and exhausts them, rescued by an antioxidant (CHE2008); conversely oxidative stress activates a redox-sensitive PI3K–Akt–mTORC1–eIF4A cascade (JIN2026). Which direction dominates depends on cell type and how sustained the oxidative load is."),
    "MAM (ER–mitochondria contacts)": ("mito", "organelle", "Where two organelles touch and talk.",
                                       "Mitochondria-associated ER membranes: a signalling platform distinct from the lysosome.",
                                       "mTORC2–Akt signalling localises here and regulates mitochondrial physiology (BET2013). Concrete evidence that mTOR signalling is not exclusively a lysosomal-surface phenomenon – the point that matters when the pathway is taught as though the lysosome were the only platform."),
    "PGC-1α / YY1": ("nucleus", "protein", "The switch that builds power plants.",
                     "Transcriptional complex through which mTORC1 drives mitochondrial gene expression.",
                     "mTOR interacts with YY1 and is required for YY1–PGC-1α function; rapamycin lowers mitochondrial gene expression and oxygen consumption (CUN2007). One of the clearest cases of mTORC1 acting through transcription rather than translation."),
    "HIF-1α": ("nucleus", "protein", "The low-oxygen alarm that also drives growth.",
               "Hypoxia-responsive transcription factor whose output is mTORC1-dependent.",
               "mTOR inhibition reverses Akt-driven prostate neoplasia partly through HIF-1-dependent pathways (MAJ2004). Note the arm this map does NOT contain: hypoxia → HIF-1α → REDD1 is real biology, but the corpus paper for the hypoxia arm (BRU2004) demonstrates REDD1 and TSC1/2 without establishing the HIF step, so that edge is not drawn."),
    "FOXO1/3": ("nucleus", "protein", "The stress-resistance programme mTOR switches off.",
                "Transcription factors excluded from the nucleus by Akt, opposing much of the mTORC1 programme.",
                "mTORC2 is required for signalling to Akt–FOXO but not to S6K1 (GUE2006), which is the genetic evidence that this arm belongs to mTORC2 rather than mTORC1. In C. elegans, TOR and rapamycin extend lifespan through SKN-1/Nrf and DAF-16/FoxO (ROB2012) – invertebrate evidence, not human."),

    # ---- nucleus ----------------------------------------------------------
    "TFEB": ("nucleus", "protein", "The master switch for recycling genes.",
             "Transcription factor for lysosomal and autophagy genes; excluded from the nucleus when phosphorylated by mTORC1.",
             "Phosphorylated on S211 in a Rag- and FLCN-dependent, substrate-selective manner; this is the clearest case where mTORC1 substrate choice – not overall activity – is the regulated variable."),
    "SREBP1 / SREBP2": ("nucleus", "protein", "The switch for making fat.",
                        "Transcription factors for lipogenic genes, activated downstream of mTORC1.",
                        "Regulated via S6K1 and Lipin-1 nuclear exclusion; the link is indirect and partly cell-type specific."),

    # ---- mitochondria / autophagy ----------------------------------------
    "Mitochondrial biogenesis": ("mito", "process", "Building more power plants.",
                                 "mTORC1-supported increase in mitochondrial mass and respiratory capacity.",
                                 "Mediated partly through 4E-BP-dependent translation of TFAM and complex components; effect sizes vary strongly with cell type."),
    "Mitophagy": ("mito", "process", "Recycling worn-out power plants.",
                  "Selective autophagy of mitochondria, promoted by AMPK.",
                  "ULK1-dependent and partly PINK1/Parkin-dependent; measured in vivo mostly with reporter mice, so quantitative claims are model-bound."),
    "Autophagy": ("autophagy", "process", "The cell eating its own worn-out parts.",
                  "Bulk degradative recycling, held off by mTORC1 and switched on by AMPK.",
                  "Regulated at initiation (ULK1), at transcription (TFEB) and at fusion; most 'autophagy is required' claims rest on flux measurements that are hard to do in tissue."),

    # ---- outcomes ---------------------------------------------------------
    "Protein synthesis": ("outcome", "process", "Making new proteins.",
                          "Cap-dependent translation, the most direct mTORC1 output.",
                          "Controlled through 4E-BP/eIF4E and S6K1/PDCD4/eIF4A arms; ribosome-profiling shows the response is transcript-selective, not uniform."),
    "Lipid synthesis": ("outcome", "process", "Making fat and membrane.",
                        "SREBP-driven lipogenesis downstream of both complexes.",
                        "mTORC1 acts via SREBP; mTORC2 contributes independently in liver, which is why hepatic Rictor loss and hepatic Raptor loss give different lipid phenotypes."),
    "Nucleotide synthesis": ("outcome", "process", "Making DNA and RNA building blocks.",
                             "Purine and pyrimidine synthesis supported by mTORC1.",
                             "S6K1 phosphorylates CAD for pyrimidines; ATF4–MTHFD2 supports purines. A growth output that is often forgotten next to translation."),
    "Muscle growth": ("outcome", "phenotype", "Muscles getting bigger.",
                      "Load- and nutrient-driven skeletal muscle hypertrophy requiring mTORC1.",
                      "Raptor-null muscle is dystrophic and rapamycin blocks overload hypertrophy; but constitutive mTORC1 activation alone is not sufficient for healthy hypertrophy."),
    "Longevity": ("outcome", "phenotype", "Living longer.",
                  "Lifespan extension by mTOR inhibition, seen across several species.",
                  "Robust in yeast, worms, flies and mice (ITP, multiple sites); no human lifespan data exist. Effect is sex- and strain-dependent and separable from healthspan."),
    "Insulin resistance": ("outcome", "phenotype", "The body responding less well to insulin.",
                           "Metabolic side effect of chronic mTOR inhibition.",
                           "Under chronic mTOR inhibition, mouse data point to mTORC2 disruption as a major contributor (LAM2012) – not to the S6K1–IRS-1 loop, which the drug relieves rather than engages. In humans the relative contributions of mTORC2 loss and direct β-cell effects are unresolved."),
    "Cellular senescence": ("outcome", "phenotype", "Cells that stop dividing but do not die.",
                            "Stable proliferative arrest with an inflammatory secretory programme, supported by mTORC1.",
                            "mTORC1 drives the SASP translationally; rapamycin suppresses SASP without reversing arrest, so 'senescence' and 'SASP' must not be conflated."),
    "Senescence-associated secretory phenotype (SASP)": ("outcome", "phenotype", "The inflammatory signals that senescent cells pump out.",
                            "Inflammatory secretory programme of senescent cells, supported translationally by mTORC1.",
                            "Drawn as its own node because the evidence is about the secretome, not about becoming senescent: LAB2015 shows mTORC1 promoting IL1A translation in cells that are already arrested, and rapamycin suppressing the secretome while the arrest stays."),
    "Age-related pathology": ("outcome", "phenotype", "Getting ill and frail with age - not the same thing as how long you live.",
                            "Tissue- and organ-level ageing phenotypes, graded separately from survival.",
                            "Kept separate from Longevity on purpose. LEE2010 measured fat accumulation and muscle and cardiac pathology in flies lacking Sestrin, with no lifespan measurement; healthspan and lifespan are separable endpoints and this Atlas grades them separately."),
    "Renal angiomyolipoma": ("outcome", "phenotype", "A benign kidney growth that is common in tuberous sclerosis.",
                            "TSC-associated benign renal tumour; the measured endpoint of EXIST-2.",
                            "Exists as its own node because EXIST-2 measured renal angiomyolipoma response (42% vs 0% on placebo) in patients with TSC or sporadic LAM. Lung disease was not the endpoint, so an arrow drawn at LAM would claim more than the trial showed."),
    "Tumor growth": ("outcome", "phenotype", "Cancer growing.",
                     "Proliferation and mass increase supported by mTORC1 signalling.",
                     "Genotype-dependent: mTORC1 activation is a strong dependency in TSC- and PI3K-pathway-mutant contexts and much weaker elsewhere."),
    "Renal cell carcinoma (RCC)": ("outcome", "disease", "A kidney cancer treated with these drugs.",
                                   "Cancer where rapalogs are licensed and mTOR-pathway lesions are common.",
                                   "Temsirolimus (ARCC) and everolimus (RECORD-1) both improved outcomes; exceptional responders have been traced to TSC1 loss."),
    "Breast cancer": ("outcome", "disease", "A cancer where a rapalog is used with hormone therapy.",
                      "Hormone-receptor-positive disease where everolimus is added to exemestane.",
                      "BOLERO-2: progression-free survival benefit, no clear overall-survival benefit, meaningful toxicity – a resistance-delaying rather than curative effect."),
    "Pancreatic neuroendocrine tumor": ("outcome", "disease", "A rare pancreatic tumour type.",
                                               "Everolimus-licensed indication.",
                                               "RADIANT-3 showed progression-free survival benefit; mTOR-pathway mutations are recurrent in this histology."),
    "Tuberous sclerosis complex": ("outcome", "disease", "A genetic disease of the pathway's own brake.",
                                   "TSC1/TSC2 loss causing benign tumours in multiple organs.",
                                   "The cleanest human demonstration that mTORC1 hyperactivation drives disease, and the setting where rapalogs work best – including on subependymal giant-cell astrocytoma."),
    "Lymphangioleiomyomatosis": ("outcome", "disease", "A rare progressive lung disease.",
                                 "TSC-related proliferative lung disease treated with sirolimus.",
                                 "MILES tested sirolimus and stabilised FEV1; EXIST-2 tested everolimus against renal angiomyolipoma, not the lung disease – a distinction routinely blurred."),
    "Prostate cancer": ("outcome", "disease", "A cancer where mTORC2 matters unusually much.",
                        "PTEN-loss-driven disease with an mTORC2 requirement in mouse models.",
                        "Rictor deletion blocks PTEN-null prostate tumorigenesis in mice; rapalog monotherapy has not translated, consistent with an mTORC2-dependent mechanism."),
    "Immune function": ("outcome", "phenotype", "How well the immune system works.",
                        "mTOR inhibition reshapes rather than simply suppresses immunity.",
                        "Rapalogs are immunosuppressants at transplant doses, yet low-dose everolimus improved influenza vaccine responses in the elderly (Mannick 2014/2018) – dose and schedule determine the direction."),
    "Actin cytoskeleton": ("outcome", "process", "The cell's internal scaffolding.",
                           "mTORC2-dependent actin organisation and cell shape control.",
                           "The original TORC2 phenotype in yeast; in mammals mediated through PKCα and Rho GTPases and largely rapamycin-insensitive acutely."),

    # ---- added 2026-08-06: entity-browser audit found this node missing
    # from every graph in the Atlas despite having a real, well-cited
    # mechanistic link into the existing model (LV2026). See EXTRA_EDGES
    # below for the two interactions that connect it in.
    "cGAS-STING pathway": ("cytosol", "complex",
        "An immune alarm system that goes off when it detects DNA where it shouldn't be – floating loose in the cell, not tucked inside the nucleus.",
        "Innate-immune DNA-sensing pathway (cGAS binds cytosolic DNA, signals through STING) driving an inflammatory secretory programme; normally kept in check by lysosomal mTORC1 signalling.",
        "cGAS binds cytosolic double-stranded DNA and synthesises cGAMP, which activates STING to drive type-I-interferon and NF-κB-dependent inflammatory gene expression. In aged mouse macrophages, decline of the Ragulator subunit Lamtor5 impairs mTORC1 signalling, and this loss of restraint is sufficient to trigger cGAS-mediated paracrine inflammatory senescence; restoring Lamtor5 reverses the phenotype (LV2026). Single mouse study – human relevance of the Lamtor5–cGAS/STING link is untested."),
}

# ---------------------------------------------------------------------------
# 3. Kurace hran.
#
# type  – mechanistický děj:
#   binding | recruitment | localisation | translocation | scaffolding
#   | phosphorylation | dephosphorylation | gap-activity | gef-activity
#   | complex-assembly | complex-disassembly | allosteric-activation
#   | allosteric-inhibition | competitive-inhibition | transcriptional
#   | transport | signal-relay | functional-consequence | clinical-outcome
#   | association
# comp  – kde se to děje (id kompartmentu)
# ts    – seconds | minutes | hours | days | chronic | constitutive
# dir   – direct | indirect | unresolved
# mc    – mechanistická důvěra: high | medium | low
# hr    – lidská relevance: established | plausible | untested
# cons  – established | emerging | contested
#
# POZOR: "sign" (activates/inhibits/required-for) se PŘEBÍRÁ ze stávajících
# dat – byl externě recenzován a nebyl v něm nalezen ani jeden chybný znak.
# Tady se doplňuje jen to, co dosud chybělo.
# ---------------------------------------------------------------------------
# CUR -- ZRUŠENO 2026-09-30. Hrany žijí jen v Airtable Relations
# (pole: Interaction_Type, Compartment, Timescale, Causal_Directness, Mechanistic_Confidence, Human_Relevance_Claim, Consensus). Čte se přes relations_bake.py -> atlas_data/relations_baked.json.

# Poznámky, které stará data neuměla vyjádřit a které jsou pedagogicky
# nosné – proč je zde znak takový, jaký je.
# TEACH -- ZRUŠENO 2026-09-30. Hrany žijí jen v Airtable Relations
# (pole: Teaching_Note). Čte se přes relations_bake.py -> atlas_data/relations_baked.json.

# Beginner-register paraphrase of `mechanism`, one level down from the
# curated research-register text above. Added for the site-wide
# Beginner/Student/Research reading-level switch (2026-08-04).
# Student and Research levels keep reading the curated `mechanism` field
# unchanged -- only Beginner gets separately authored text here.
# MECH_BEGINNER -- ZRUŠENO 2026-09-30. Hrany žijí jen v Airtable Relations
# (pole: Mechanism_Beginner). Čte se přes relations_bake.py -> atlas_data/relations_baked.json.


# ---------------------------------------------------------------------------
# 4. Ručně napsané kroky tras.
#
# Motor tras umí každý krok složit z kurátorovaných polí (mechanism,
# teaching_note, confidence, boundary) – takže všech 7 tras funguje hned a
# nic si nevymýšlí. Ruční verze je ale lepší: umí říct, JAKÝ PROBLÉM buňka
# řeší, a navázat krok na krok. Tady je `aa` napsaná ručně jako etalon
# kvality, na který se dopisují ostatní (Fáze 2).
#
# Každý krok odpovídá na šest otázek. Když některou vynecháš, doplní se
# automaticky z modelu – nikdy nezůstane prázdná.
# ---------------------------------------------------------------------------
ROUTE_STEPS = {
# ---- rapa: why doesn't rapamycin switch mTOR off completely? -----------
 "rapa": [
  {"interaction": "RAPA-FKBP12",
   "what": "Rapamycin binds FKBP12 – and on its own, does nothing to mTOR.",
   "why": "Rapamycin is not an mTOR inhibitor in the way that word is normally used. It has essentially no activity against mTOR by itself. It first binds a small abundant prolyl isomerase, FKBP12, and the drug-protein pair becomes the actual inhibitor.",
   "changed": "A new molecular surface exists that did not exist before: the FKBP12–rapamycin composite. Neither half has that surface alone.",
   "consequence": "Because the inhibitor is a complex, how much inhibition a cell experiences depends on how much FKBP12 that cell expresses – not only on drug concentration.",
   "certainty": "Structurally resolved and mechanistically secure. Cited evidence is cell-line and structural work, so human relevance is graded plausible rather than established.",
   "matters": "This is the first clue that rapamycin will behave oddly. A drug that must borrow a host protein to work is a drug whose potency varies with the host. It also explains why FKBP12 expression is a determinant of rapalog sensitivity – a fact with no analogue in ordinary ATP-competitive inhibitors."},
  {"interaction": "FKBP12-MTORC1",
   "what": "The complex binds the FRB domain and partially blocks the substrate channel.",
   "why": "It does not enter the active site. It docks on a domain adjacent to it and gets in the way of substrates arriving. That is a different kind of inhibition from occupying the catalytic pocket – it is steric obstruction, and obstruction can be partial.",
   "changed": "mTORC1 remains a catalytically intact kinase. What changes is which substrates can still reach it.",
   "consequence": "Substrates that need deep, sustained access lose out. Substrates that need less access carry on. The pathway does not switch off – it becomes selectively deaf.",
   "certainty": "Structurally resolved, high mechanistic confidence. The clinical consequences are supported by trial evidence; this mechanism is not human data.",
   "matters": "Here is the answer to the route's question, and almost the whole field missed it for a decade. Because rapamycin obstructs rather than occupies, S6K1 phosphorylation collapses while 4E-BP1 phosphorylation largely survives. Every experiment that used S6K1 as 'the mTORC1 readout' therefore over-reported how much rapamycin inhibits mTORC1."},
  {"interaction": "MTORC1-ULK1",
   "what": "One output rapamycin does release: mTORC1 stops holding ULK1 down.",
   "why": "mTORC1 phosphorylates ULK1 on S757, which blocks ULK1 from being activated by AMPK. Inhibit mTORC1 and that block lifts.",
   "changed": "ULK1 becomes available to AMPK. Autophagy initiation is no longer suppressed.",
   "consequence": "The block on autophagy initiation is lifted. How much recycling actually follows is a separate question, and the answer is less than the textbook suggests.",
   "certainty": "Direct biochemistry, replicated across labs; mechanistic confidence high, evidence from mammalian cells.",
   "matters": "Here the route has to correct a story it would be easy to tell. THO2009 – the paper this route names as its breakthrough – found autophagy among the mTORC1 outputs that rapamycin leaves largely intact, and ATP-competitive inhibitors induce it far more completely. So rapamycin is partial on BOTH arms, and what it does is not turn 'mTORC1 activity' down by a fixed amount but reshape which outputs stay on. That reshaping is why rapamycin can extend lifespan in mice while being a mediocre anti-proliferative in many tumours – and why 'rapamycin induces autophagy' needs the dose, the cell type and the readout attached before it is true."},
  {"interaction": "ULK1-AUTOPHAGY",
   "what": "ULK1 initiates autophagy.",
   "why": "Freed and phosphorylated by AMPK, ULK1 nucleates the machinery that builds an autophagosome.",
   "changed": "Bulk degradative recycling begins: damaged proteins and organelles are captured and delivered to lysosomes.",
   "consequence": "The cell buys time and materials. Most of the healthspan claims made for rapamycin route through this step.",
   "certainty": "Mechanistically solid. But autophagic FLUX is genuinely hard to measure in tissue rather than cells, so quantitative in vivo claims about how much autophagy a given rapamycin dose produces are weaker than they sound.",
   "matters": "This is where the rapamycin story usually stops being told carefully. 'Rapamycin induces autophagy therefore it extends lifespan' skips the part where nobody has cleanly shown autophagy is the required mediator in a mammal."},
  {"interaction": "RAPA-MTORC2",
   "what": "Given long enough, rapamycin also disturbs mTORC2 – sometimes.",
   "why": "Chronic exposure can interfere with mTORC2 assembly in some cell types. This is not the acute, direct inhibition seen with mTORC1; it is a slower, indirect effect on complex integrity.",
   "changed": "In susceptible cells, mTORC2 output falls. In others, it does not.",
   "consequence": "The clean textbook statement 'rapamycin inhibits mTORC1 but not mTORC2' is true acutely and unreliable chronically – which matters enormously, because patients take rapalogs chronically.",
   "certainty": "Contested, low mechanistic confidence, a single supporting study in this corpus. Cell type and duration both change the answer. This is drawn as a dashed line with an amber halo for exactly that reason.",
   "matters": "A route that taught only the tidy version would be teaching a fact with a hidden expiry date. The honest position is that acute and chronic rapamycin are different drugs pharmacologically, and most of what people 'know' about rapamycin comes from acute experiments."},
  {"interaction": "MTORC2-INSULINRES",
   "what": "Losing mTORC2 is one route to insulin resistance.",
   "why": "mTORC2 phosphorylates Akt on S473. Reduce that and insulin signalling degrades, which in mice produces measurable glucose intolerance.",
   "changed": "Whole-body glucose handling worsens – an organism-level consequence, not a cellular one.",
   "consequence": "In mice this is a leading mechanistic explanation for rapamycin-induced glucose intolerance. Whether it explains the dysglycaemia seen in patients on rapalogs is not settled.",
   "certainty": "Mouse data (A – animal), medium mechanistic confidence. In humans the relative contributions of mTORC2 loss, S6K1–IRS-1 feedback and direct beta-cell effects are unresolved – so attributing the clinical side effect to this one mechanism overstates what is known.",
   "matters": "mTORC2 disruption is one plausible contributor to the metabolic side effects of rapalogs, and in mice it is a well-supported one. Its share in people is unresolved, alongside S6K1–IRS-1 feedback and direct beta-cell effects. Either way, 'selective mTORC1 inhibitor' describes acute treatment, and stretching it to chronic therapy is imprecise."},
  {"interaction": "RAPA-LONGEVITY",
   "what": "And still, rapamycin extends lifespan in mice.",
   "why": "Reproducibly, across genetically heterogeneous strains, at multiple independent sites, including when started late in life.",
   "changed": "Median and maximum lifespan increase. This is one of the most robust pharmacological longevity results in mammals.",
   "consequence": "Everything upstream in this route – partial inhibition, asymmetric outputs, possible mTORC2 disruption, insulin resistance – is the mechanism this outcome sits on. The outcome is solid; the causal chain is not.",
   "certainty": "Strong for mice: replicated, multi-site (A – animal). For humans: there is no lifespan data of any kind. Human relevance is graded untested, and that grade is not pessimism, it is arithmetic.",
   "matters": "The question this route asked was why rapamycin does not switch mTOR off completely. The answer may be why it works at all. A complete mTOR shutdown is lethal; partial, asymmetric inhibition that suppresses growth signalling while permitting recycling may be exactly the therapeutic window – achieved by accident, through a drug that obstructs rather than occupies."},
 ],

 # ---- gf: how does a cell learn that it is allowed to grow? -------------
 "gf": [
  {"interaction": "IGF1-PI3K",
   "what": "A hormone arrives and PI3K is switched on at the membrane.",
   "why": "IGF-1 binds its receptor, the receptor autophosphorylates, IRS adaptors dock, and PI3K is recruited to the membrane. This map draws it as one arrow, but it is at least four events.",
   "changed": "PI3K starts converting PIP2 into PIP3 – the cell writes a lipid message into its own membrane.",
   "consequence": "That lipid becomes a docking site. Whatever can read PIP3 will now be pulled to the membrane.",
   "certainty": "Mechanistically secure and drawn as a long dash precisely because it is compressed. Cited evidence is cell-line work, so human relevance is plausible, not established.",
   "matters": "The cell's answer to 'am I allowed to grow?' does not arrive as a molecule entering the cytosol. It arrives as a change in membrane chemistry. That is why this arm is reversed by a phosphatase rather than switched off by degradation."},
  {"interaction": "PI3K-AKT",
   "what": "PIP3 recruits Akt to the membrane – and recruitment is not activation.",
   "why": "Akt has a domain that binds PIP3. Arriving at the membrane puts it where two kinases can reach it, but arriving is not the same as being switched on. PDK1 phosphorylates T308 in the activation loop, the step central to switching Akt on. mTORC2 phosphorylates S473, which raises activity further and changes which substrates Akt reaches.",
   "changed": "Akt's location changes first. Its activity rises with T308 phosphorylation; S473 adds to it, and how much S473 matters depends on the substrate.",
   "consequence": "Some Akt outputs depend on mTORC2 more than others. In mice lacking rictor or mLST8, insulin signalling to FOXO3 was lost while signalling to TSC2 and GSK3-beta was kept (GUE2006). Losing mTORC2 therefore weakens part of Akt's output rather than switching Akt off, and the branch through TSC2 toward mTORC1 largely keeps working. mTOR still sits on both sides of this pathway, but the upstream dependency is partial.",
   "certainty": "High mechanistic confidence, well replicated; cell-line and knockout-mouse evidence (GUE2006, JAC2006).",
   "matters": "The same distinction as in the nutrient arm, appearing again: getting a protein to a place is a different act from switching it on. A diagram with one arrow from PI3K to Akt hides three events and a partial, substrate-dependent reliance on the other mTOR complex."},
  {"interaction": "AKT-TSC",
   "what": "Akt phosphorylates the TSC complex and takes the brake off.",
   "why": "TSC1/TSC2 is the pathway's master brake. Akt phosphorylation inhibits it – partly by changing its activity, substantially by moving it away from where its target sits.",
   "changed": "The brake stops being applied. Nothing has been pushed yet; something has stopped being held back.",
   "consequence": "Whatever the brake was suppressing is now free to act. That target is Rheb.",
   "certainty": "This is one of the two papers the route's Journey header names as its breakthrough (INO2002). High mechanistic confidence; cell-line evidence, so human relevance plausible – though TSC loss in people is the one place this pathway's causality is established.",
   "matters": "Double-negative logic again, exactly as in the nutrient arm. Growth signals in this pathway overwhelmingly work by removing inhibition rather than adding stimulation. Once you see that pattern you stop being surprised by it."},
  {"interaction": "TSC-RHEB",
   "what": "Released from Akt's inhibition, TSC would switch Rheb off – so inhibiting TSC leaves Rheb loaded.",
   "why": "TSC2 is a GAP: it forces Rheb to hydrolyse GTP to GDP. With TSC inhibited, Rheb accumulates in its GTP state.",
   "changed": "Rheb flips from GDP-loaded to GTP-loaded. This is the moment the growth-factor signal becomes a switch position.",
   "consequence": "GTP-Rheb can now do what nothing upstream in this route has done: switch the kinase on rather than merely position it.",
   "certainty": "The second breakthrough paper (INOK2003), with GAR2003 independently. High mechanistic confidence; cell-line evidence.",
   "matters": "Note how far the signal has travelled and how little has been 'activated': a hormone bound a receptor, a lipid was made, a kinase was recruited, a brake was released, and a GTPase changed nucleotide. Four negations and a nucleotide swap. That is what a signalling pathway actually is."},
  {"interaction": "RHEB-MTORC1",
   "what": "GTP-Rheb binds mTORC1 and switches the kinase on.",
   "why": "Rheb realigns the mTOR active site into a catalytically competent conformation. This is an allosteric activation – structurally different from everything upstream.",
   "changed": "mTORC1 becomes an active kinase, and its substrates are now phosphorylated efficiently.",
   "consequence": "The cell begins to build. And because this step happens at the lysosome, it can only happen if the nutrient arm has already delivered mTORC1 there.",
   "certainty": "Structurally resolved, high mechanistic confidence, cell-line evidence.",
   "matters": "This is the convergence point of the whole map. The nutrient arm answers 'are the parts available' by controlling location; this arm answers 'am I allowed' by controlling Rheb. Both must be satisfied at the same membrane at the same time – and this step is where the AND gate is evaluated."},
  {"interaction": "MTORC1-S6K1",
   "what": "Active mTORC1 phosphorylates S6K1.",
   "why": "S6K1 carries a TOS motif recognised by Raptor, which presents it to the kinase. T389 phosphorylation activates it.",
   "changed": "S6K1 becomes an active kinase with its own substrates.",
   "consequence": "Two things follow, and they point in opposite directions. S6K1 promotes translation – and it also starts dismantling the signal that created it.",
   "certainty": "High mechanistic confidence, replicated, and this is the classical rapamycin-sensitive readout. Cell-line evidence.",
   "matters": "S6K1's rapamycin sensitivity is why it became the field's default assay for 'mTORC1 activity' – and why the field systematically overestimated how completely rapamycin inhibits mTORC1 for years. The convenience of a readout shaped what people believed."},
  {"interaction": "S6K1-IRS1",
   "what": "S6K1 phosphorylates IRS-1 and marks it for destruction.",
   "why": "Serine phosphorylation of IRS-1 creates a degradation signal. The adaptor that connected the receptor to PI3K is removed.",
   "changed": "IRS-1 protein levels fall. The input arm of this very route is dismantled.",
   "consequence": "PI3K recruitment drops, Akt activity falls, and the growth signal decays – even though the hormone is still present.",
   "certainty": "High mechanistic confidence, multiple supporting studies. Cell-line evidence, so human relevance graded plausible, though the clinical consequence is well documented.",
   "matters": "This is negative feedback, and one of the best-characterised and most clinically important loops in the pathway (Grb10 and the MAPK reroute are parallel ones). Block mTORC1 with a rapalog and you also block this loop – so IRS-1 survives, PI3K/Akt reactivate, and the tumour you were treating gets a growth signal back. A large part of why rapalog monotherapy underperforms is visible in this single arrow. Note which way round the loop runs: it is mTORC1 ACTIVITY that destroys IRS-1, so the loop is a mechanism of insulin resistance under nutrient excess – the drug relieves it."},
  {"interaction": "IRS1-PI3K",
   "what": "IRS-1 recruits PI3K – closing the loop back to step one.",
   "why": "IRS-1 is the scaffold that brings PI3K to the activated receptor. Its abundance sets how much signal gets through.",
   "changed": "The route returns to where it started. This is not a chain; it is a cycle with a set point.",
   "consequence": "The steady state of growth-factor signalling is determined by the balance between the forward arm and this feedback arm – not by the hormone concentration alone.",
   "certainty": "High mechanistic confidence; cell-line evidence.",
   "matters": "The question was how a cell learns it is allowed to grow. The answer turns out to be that it never simply learns – it continuously negotiates. The pathway measures its own output and turns its own input down. Any drug that interrupts the loop changes the negotiation, which is why mTOR inhibitors have effects nobody predicted from the linear diagram."},
 ],

 # ---- energy: how does a cell decide it cannot afford to grow? ----------
 "energy": [
  {"interaction": "STRESS-AMPK",
   "what": "Falling energy charge activates AMPK directly.",
   "why": "AMP and ADP bind the AMPK gamma subunit, which both activates the kinase allosterically and protects its activating phosphorylation from being removed. The cell is not reading 'low ATP' – it is reading the RATIO.",
   "changed": "AMPK becomes active within seconds of the energy charge dropping.",
   "consequence": "A kinase is now running whose entire job is to stop expensive processes and start cheap ones.",
   "certainty": "High mechanistic confidence, well replicated; cell-line evidence, so human relevance plausible.",
   "matters": "Reading a ratio rather than an absolute is what makes this a sensor rather than a thermometer. A cell with genuinely low but stable ATP is not in trouble; a cell whose ATP is falling is. The ratio distinguishes them."},
  {"interaction": "AMPK-TSC",
   "what": "AMPK phosphorylates and activates the TSC complex.",
   "why": "Where Akt phosphorylation inhibited TSC, AMPK phosphorylation at different sites activates it. The same brake, driven in the opposite direction by a different kinase.",
   "changed": "TSC GAP activity rises. Rheb starts being switched off.",
   "consequence": "The growth-factor signal is overridden. A cell that was told to grow can now refuse.",
   "certainty": "High mechanistic confidence, though on a single M – molecular – study in this corpus – the validator flags it, and it is fair to note that the corpus here is thinner than the literature.",
   "matters": "Two opposing inputs converge on one protein, and TSC becomes the place where 'permitted' and 'affordable' are reconciled. Integration in this pathway is not a special mechanism; it is several kinases writing to the same substrate."},
  {"interaction": "TSC-RHEB",
   "what": "Activated TSC drives Rheb back to its GDP state.",
   "why": "Same GAP reaction as in the growth-factor route, running the other way because TSC is now active rather than inhibited.",
   "changed": "GTP-Rheb falls. The mTORC1 on-switch is being withdrawn.",
   "consequence": "mTORC1 activity declines even if nutrients are plentiful and hormones are still signalling.",
   "certainty": "High mechanistic confidence; cell-line evidence.",
   "matters": "Energy status wins. Of the four inputs on the overview diagram, this is the one that can veto the others – which makes biological sense, because a cell that builds without fuel destroys itself."},
  {"interaction": "RHEB-MTORC1",
   "what": "With Rheb off, mTORC1 goes quiet.",
   "why": "No GTP-Rheb, no allosteric activation, no active kinase – regardless of where mTORC1 is sitting.",
   "changed": "mTORC1 stops phosphorylating its substrates. Building stops.",
   "consequence": "But stopping growth is only half of what an energy-starved cell needs. It also needs to generate resources.",
   "certainty": "Structurally resolved; high mechanistic confidence.",
   "matters": "This is the same step the growth-factor route ended on, reached from the opposite direction. Seeing one node arrived at by two different arms is how the map teaches convergence – and why 'mTORC1 activity' is never explained by a single upstream signal."},
  {"interaction": "AMPK-ULK1",
   "what": "In parallel, AMPK phosphorylates ULK1 and switches recycling on.",
   "why": "AMPK acts on ULK1 directly, at sites distinct from the inhibitory site mTORC1 uses. And with mTORC1 now quiet, the mTORC1 block on ULK1 has lifted too.",
   "changed": "Autophagy initiation is both released and actively driven – two independent pushes in the same direction.",
   "consequence": "The cell starts digesting its own components to regenerate substrates.",
   "certainty": "Direct biochemistry, replicated for the phosphorylation itself; the net sign is contested. Park, Lee and Kim (Nat Commun 2023, PMID 37225695) report that under glucose starvation and mitochondrial energy stress AMPK restrains ULK1 activation while protecting the ULK1 machinery.",
   "matters": "This is the elegant part of energy sensing, in its classic reading. One kinase performs both halves of the switch: it stops the expensive programme and starts the recovery programme, simultaneously, without needing a second sensor. Note also that ULK1 phosphorylates AMPK back – so this is a loop with a set point, not a one-way command."},
  {"interaction": "AMPK-MITOPHAGY",
   "what": "Selectively, damaged mitochondria are recycled.",
   "why": "AMPK promotes mitophagy, the targeted autophagy of mitochondria – which is both a quality-control mechanism and a way to reclaim material.",
   "changed": "Dysfunctional mitochondria are cleared rather than left to leak.",
   "consequence": "Over longer timescales this shapes mitochondrial quality, and it is one of the arms through which energy stress is proposed to influence ageing.",
   "certainty": "Medium mechanistic confidence, indirect, and measured largely with reporter mice – so quantitative claims are model-bound. Mouse evidence, human relevance plausible at best.",
   "matters": "The route began with a question about affordability and ends with quality control. That is not a digression: a cell short of energy is usually a cell with failing mitochondria, so the same signal that stops growth is the right signal to trigger repair of the cause. Energy sensing is not a thermostat – it is a diagnostic."},
 ],

# ---- mtorc2: why does one kinase need two complexes? -------------------
 "mtorc2": [
  {"interaction": "RICTOR-MTORC2",
   "what": "Rictor binds mTOR and defines a second complex.",
   "why": "The same catalytic subunit, a different partner. Rictor takes the place Raptor occupies in mTORC1, and the resulting complex has different substrates, a different location and – decisively – different drug sensitivity.",
   "changed": "There are now two mTOR complexes in the cell, not one kinase with two moods.",
   "consequence": "Because Rictor confers rapamycin insensitivity, this complex was invisible for a decade to anyone using rapamycin as their probe.",
   "certainty": "This is the route's breakthrough paper (SAR2004). High mechanistic confidence, biochemistry and complex purification in mammalian cells.",
   "matters": "The answer to the route's question starts here. Evolution did not need two kinases because the catalytic domain is not what specifies a signalling job – the partner is. Substrate choice, location and regulation all come from the accessory subunit, so one kinase gene can serve two pathways."},
  {"interaction": "SIN1-MTORC2",
   "what": "SIN1 joins, and brings a growth-factor antenna with it.",
   "why": "SIN1 is required for complex integrity and for Akt S473 kinase activity. Its PH domain inhibits mTORC2 until PIP3 relieves that inhibition.",
   "changed": "mTORC2 becomes assembled, competent, and responsive to membrane lipid state.",
   "consequence": "The complex now has a way to know whether growth factors are present – through the same PIP3 signal Akt uses.",
   "certainty": "High mechanistic confidence, multiple studies including structural work.",
   "matters": "A subunit doubling as a sensor is an economical piece of design: the same lipid that recruits the substrate also licenses the kinase. It also means PI3K sits upstream of both arms, which is why PI3K inhibition has broader consequences than mTOR inhibition."},
  {"interaction": "PI3K-MTORC2",
   "what": "PIP3 relieves the SIN1 brake and mTORC2 becomes active.",
   "why": "Growth-factor-generated PIP3 engages the SIN1 PH domain, releasing its autoinhibition of the complex.",
   "changed": "mTORC2 activity rises in response to growth factors – on a seconds timescale.",
   "consequence": "Both mTOR complexes are now downstream of PI3K, but they read it differently: mTORC1 through Akt→TSC→Rheb, mTORC2 through this direct lipid relief.",
   "certainty": "Medium mechanistic confidence, emerging consensus, one supporting study in this corpus. Drawn as a long dash because it is a compressed relay, not a single event.",
   "matters": "This is the cleanest available answer to how growth factors reach mTORC2, and it is weaker evidence than the equivalent step in the mTORC1 arm. Worth noticing: the two complexes are not equally well understood, and the map shows that asymmetry rather than smoothing it over."},
  {"interaction": "MTORC2-AKT",
   "what": "mTORC2 phosphorylates Akt on S473.",
   "why": "This is mTORC2's signature reaction. Akt needs both T308 from PDK1 and S473 from mTORC2 for full activity against many substrates.",
   "changed": "Akt becomes fully active – and Akt is what activates mTORC1's upstream arm.",
   "consequence": "Through Akt, mTORC2 is one of the inputs that licenses mTORC1. That is not a simple hierarchy, though: both complexes read PI3K, each has substrates the other never touches, and mTORC1's own S6K1 to IRS-1 feedback runs back into the signalling that feeds mTORC2. Upstream here names a route, not a rank.",
   "certainty": "High mechanistic confidence, multiple studies, and the genetic dissection in mice is the strongest evidence in this route: Rictor or mLST8 loss abolishes signalling to Akt while sparing S6K1.",
   "matters": "Here is the structural reason the two-complex question matters clinically. Rapamycin hits mTORC1 but not mTORC2 acutely, so it leaves the Akt-activating arm intact – one more reason blocking mTORC1 does not simply shut the pathway down."},
  {"interaction": "MTORC2-INSULINRES",
   "what": "Disrupting mTORC2 degrades whole-body glucose handling.",
   "why": "Less S473 phosphorylation means weaker insulin signalling, which in mice produces measurable glucose intolerance.",
   "changed": "An organism-level metabolic phenotype appears, from a change in one complex.",
   "consequence": "This is the leading explanation for the dysglycaemia patients experience on chronic rapalogs.",
   "certainty": "Mouse data (A – animal), medium mechanistic confidence. In humans the relative contributions of mTORC2 loss, S6K1–IRS-1 feedback and direct beta-cell effects are unresolved.",
   "matters": "A complex that was invisible because the standard drug did not hit it turns out to explain that drug's most common serious side effect. That is a strong argument for the Atlas's central habit: knowing which arm a claim rests on, and on which species."},
  {"interaction": "RAPA-MTORC2",
   "what": "And chronic rapamycin may reach mTORC2 after all.",
   "why": "Prolonged exposure can interfere with mTORC2 assembly in some cell types – slowly, indirectly, and not universally.",
   "changed": "The clean separation that made mTORC2 discoverable becomes unreliable over time.",
   "consequence": "The textbook line 'rapamycin inhibits mTORC1 but not mTORC2' is a statement about acute treatment being applied to chronic therapy.",
   "certainty": "Contested, low mechanistic confidence, a single supporting study. Cell type and duration both change the answer – which is why this arrow is dashed with an amber halo.",
   "matters": "The route closes on an irony worth sitting with. Rapamycin insensitivity is the property that revealed mTORC2 existed; that same property may not hold under the conditions in which the drug is actually used. The tool that made the discovery possible may not describe the therapy."},
 ],

 # ---- out: what does a cell actually do when mTORC1 fires? --------------
 "out": [
  {"interaction": "MTORC1-4EBP1",
   "what": "mTORC1 phosphorylates 4E-BP1 and releases a brake on translation.",
   "why": "4E-BP1 sits on eIF4E and prevents it from starting translation. Multi-site phosphorylation by mTORC1 makes 4E-BP1 let go.",
   "changed": "eIF4E becomes available. Note the direction: a phosphate was ADDED, and the effect is to STOP an inhibitor – phosphorylation is a mechanism, not a sign.",
   "consequence": "Cap-dependent translation initiation can begin.",
   "certainty": "High mechanistic confidence, well replicated; cell-line evidence.",
   "matters": "This one substrate carries more consequence than any other in the pathway, because it is only PARTLY rapamycin-sensitive. That single property explains the rapalog/Torin discrepancy and motivated the entire second-generation inhibitor programme."},
  {"interaction": "4EBP1-EIF4E",
   "what": "Free of 4E-BP1, eIF4E can bind eIF4G.",
   "why": "4E-BP1 and eIF4G compete for the same surface on eIF4E. Removing one lets the other bind – competitive inhibition, not enzymatic.",
   "changed": "The initiation complex can assemble on capped mRNA.",
   "consequence": "Ribosomes begin loading. The cell starts making protein.",
   "certainty": "High mechanistic confidence, structurally understood; cell-line evidence.",
   "matters": "Competition is a distinct mechanism from catalysis, and it behaves differently: it is concentration-sensitive and instantly reversible. That is why 4E-BP:eIF4E stoichiometry matters as much as mTORC1 activity, and why tissues with different 4E-BP levels respond differently to the same drug."},
  {"interaction": "EIF4E-TRANSL",
   "what": "Translation increases – but not uniformly.",
   "why": "Ribosome profiling showed mTORC1 does not raise all translation equally. It selectively promotes a specific class of transcripts.",
   "changed": "The composition of what the cell is making changes, not just the amount.",
   "consequence": "Which proteins increase determines which phenotype follows – and those transcripts are enriched for growth and invasion programmes.",
   "certainty": "This is the route's breakthrough paper (HSI2012). High mechanistic confidence; cancer cell lines, so human relevance plausible.",
   "matters": "'mTORC1 increases protein synthesis' is the summary that hides the actual biology. The regulated variable is transcript CHOICE. Anyone reasoning about mTOR from the summary will predict the wrong consequences, because a uniform increase and a selective one have different phenotypes."},
  {"interaction": "TRANSL-MUSCLE",
   "what": "In muscle, that translation supports hypertrophy.",
   "why": "Load-driven growth requires mTORC1: Raptor-null muscle is dystrophic, and rapamycin blocks overload-induced hypertrophy.",
   "changed": "Muscle fibres grow – over days, not minutes.",
   "consequence": "The step just before this one has been tested in people; this one has not.",
   "certainty": "Mouse genetics and pharmacology (BOD2001) and cultured myotubes (ROM2001); human relevance plausible. The human study in this area, DRU2009, measured protein synthesis 1–2 h after one bout of exercise, not muscle growth, so it supports the previous step rather than this arrow.",
   "matters": "Worth pausing on, because the human evidence sits one step upstream of where it is usually quoted. A human intervention shows mTORC1 is needed for the acute rise in protein synthesis; that more synthesis becomes more muscle over weeks is shown in mice. It also carries a caveat: mTORC1 activation is NECESSARY for healthy hypertrophy but not sufficient – constitutive activation alone does not build good muscle."},
  {"interaction": "MTORC1-ULK1",
   "what": "At the same time, mTORC1 is holding recycling down.",
   "why": "Phosphorylation of ULK1 on S757 blocks the AMPK–ULK1 interaction, preventing autophagy initiation.",
   "changed": "Autophagy is suppressed while building proceeds.",
   "consequence": "The two arms move in opposite directions: when mTORC1 is active, building goes up and autophagy initiation goes down.",
   "certainty": "High mechanistic confidence, replicated; cell-line evidence.",
   "matters": "This is the answer to what mTORC1 firing actually DOES, stated properly: it is not one action but a coordinated shift that pushes building up and recycling down at the same time. Cells usually run both programmes to some degree; mTORC1 sets the balance between them rather than choosing one. Any account that lists only the build side has described half a switch."},
  {"interaction": "ULK1-AUTOPHAGY",
   "what": "Release mTORC1 and autophagy resumes.",
   "why": "Unblocked ULK1 nucleates autophagosome formation, and TFEB – released from mTORC1 phosphorylation – transcribes the genes to sustain it.",
   "changed": "The cell shifts from building to recycling, at both the initiation and the transcriptional level.",
   "consequence": "Materials are regenerated. Over longer timescales this arm is where most healthspan claims for mTOR inhibition are made.",
   "certainty": "High mechanistic confidence for initiation. Autophagic flux in tissue is genuinely hard to measure, so in vivo quantitative claims are weaker than the mechanism.",
   "matters": "Two independent control points – a kinase switch in minutes and a transcriptional programme in hours – on the same process. That is how the pathway gets both a fast response and a sustained one out of a single input."},
  {"interaction": "S6K1-LONGEVITY",
   "what": "And deleting one output extends lifespan – in female mice.",
   "why": "S6K1-null mice live longer and resist age-related pathology, which is the cleanest genetic evidence that a specific mTORC1 output influences lifespan.",
   "changed": "Median lifespan increases, along with metabolic protection.",
   "consequence": "It suggests the longevity effect of mTOR inhibition can be traced to particular outputs rather than to 'less mTOR' in general.",
   "certainty": "Mouse genetics (A – animal), medium mechanistic confidence, human relevance untested. And the effect is SEX-SPECIFIC – reported in females – a qualification routinely dropped when this result is cited.",
   "matters": "The route asked what a cell does when mTORC1 fires. The honest ending is that we can trace it from a kinase to a phosphosite to a translational programme to a phenotype in one sex of one species – and that no step of that chain has been demonstrated in a human. The map is strongest at the top and weakest exactly where people most want to use it."},
 ],

 # ---- clin: does any of this actually help a patient? -------------------
 "clin": [
  {"interaction": "TSC-MTORC1",
   "what": "Lose the TSC brake and mTORC1 runs unopposed.",
   "why": "TSC does not directly inhibit mTORC1. Its canonical target is Rheb, whose GTP state controls mTORC1 activation. This arrow is a deliberate two-step compression, drawn as one link so the clinical story reads cleanly.",
   "changed": "Without TSC, Rheb stays GTP-loaded and mTORC1 stays on even when no growth factor says it should. Note what this does not mean: TSC2-null cells still need amino acids and still respond to energy stress, so the input that has been lost is the growth-factor one, not every input.",
   "consequence": "Growth signalling becomes constitutive rather than conditional.",
   "certainty": "High mechanistic confidence, and this is the one place in the whole map where human genetics establishes causality: TSC1/TSC2 loss causes disease in people.",
   "matters": "Every other arm of this pathway is inferred from cells and mice. This one is inferred from patients. That difference is why tuberous sclerosis is the setting where mTOR inhibitors work best – the drug is aimed at the actual cause."},
  {"interaction": "MTORC1-TUMOR",
   "what": "Constitutive mTORC1 supports tumour growth.",
   "why": "Sustained translation of growth and invasion programmes, plus suppressed autophagy, plus the biosynthetic outputs – mTORC1 supplies much of what a proliferating cell needs.",
   "changed": "Proliferation and mass increase.",
   "consequence": "That makes mTORC1 a drug target. It does not make it the target in every tumour.",
   "certainty": "High mechanistic confidence but INDIRECT, and strongly genotype-dependent: a strong dependency in TSC- and PI3K-pathway-mutant contexts, much weaker elsewhere.",
   "matters": "The gap between 'mTORC1 supports tumour growth' and 'inhibiting mTORC1 treats this tumour' is where most of the clinical disappointment of the last twenty years lives. Dependency is contextual; the arrow is not."},
  {"interaction": "EVE-MTORC1",
   "what": "Everolimus inhibits mTORC1 – partially, and via FKBP12.",
   "why": "Same allosteric mechanism as rapamycin, with better oral pharmacokinetics. It obstructs the substrate channel rather than occupying the active site.",
   "changed": "S6K1 signalling collapses; 4E-BP1 phosphorylation substantially persists.",
   "consequence": "The drug delivers partial, asymmetric inhibition to a tumour that may depend on the arm it does not fully block.",
   "certainty": "High confidence, and unusually for this map, supported by H – human trial – evidence across several indications.",
   "matters": "Carry the rapamycin route's lesson into the clinic. The incomplete inhibition that is a curiosity in a cell-biology paper is a therapeutic ceiling in a patient – and it is the reason bi-steric and ATP-competitive inhibitors reached trials."},
  {"interaction": "EVE-TSC",
   "what": "In tuberous sclerosis, it works.",
   "why": "The disease is caused by loss of the brake this drug substitutes for. Mechanism and treatment are matched.",
   "changed": "Tumours shrink, including subependymal giant-cell astrocytoma and renal angiomyolipoma.",
   "consequence": "This is the pathway's clearest mechanism-to-benefit case.",
   "certainty": "H – trial evidence in humans; human relevance established. Note the honest scope: these are benign tumours and the benefit is control, not cure – treatment interruption is followed by regrowth.",
   "matters": "The best result in the whole map comes from the one disease where the causal lesion is known and the drug addresses it directly. That is the template, and the rest of oncology has struggled to reproduce it precisely because the causal lesion is usually not so clean."},
  {"interaction": "MTORC1-RCC",
   "what": "In renal cancer the link is association, not demonstrated causation.",
   "why": "Renal cancers frequently carry lesions that leave mTORC1 active. That is a correlation between genotype and pathway state, not evidence that mTORC1 activation initiates the disease.",
   "changed": "Nothing mechanistically. This arrow records a statistical relationship.",
   "consequence": "It explains why the tissue responds to rapalogs at all, and why an exceptional responder could be traced to TSC1 loss.",
   "certainty": "Typed as ASSOCIATION, directness unresolved, mechanistic confidence low – the lowest-graded link on the route, deliberately. Drawn dotted and thin.",
   "matters": "This step exists to be read sceptically. It sits between two well-evidenced clinical steps, and if it were drawn like them a reader would infer a causal chain that the evidence does not support. Grading it honestly is what stops the route from over-claiming."},
  {"interaction": "TEM-RCC",
   "what": "Temsirolimus improved survival in advanced renal cell carcinoma.",
   "why": "A randomised trial in poor-prognosis patients – the result that produced the first mTOR inhibitor approval in oncology.",
   "changed": "Overall survival improved versus interferon alfa.",
   "consequence": "mTOR moved from a laboratory pathway to a licensed drug target.",
   "certainty": "H – a randomised controlled trial; human relevance established. This is trial evidence: it establishes that the drug changed an outcome, NOT that the mechanism drawn upstream is the reason.",
   "matters": "The distinction in that last sentence is the whole point of the route. A positive trial validates a treatment, not a diagram. Everything above this step remains inferred from cells and mice even after the drug is approved."},
  {"interaction": "RAPA-LAM",
   "what": "In lymphangioleiomyomatosis, sirolimus stabilised lung function.",
   "why": "LAM involves TSC-pathway lesions, so the same mechanistic logic as tuberous sclerosis applies to a progressive lung disease.",
   "changed": "FEV1 decline stabilised during treatment in the MILES trial.",
   "consequence": "A rare, previously untreatable progressive disease acquired a therapy derived from pathway biology.",
   "certainty": "H – a human trial; human relevance established. Precision matters here: MILES tested SIROLIMUS in the lung disease. EXIST-2 tested everolimus against renal angiomyolipoma, not the lung disease – a distinction routinely blurred, and an external review of this Atlas caught us blurring it.",
   "matters": "Arguably the strongest answer to the route's question. Not a cancer, not a lifespan claim – a specific progressive disease where understanding the pathway produced a treatment that changed the disease course. It is also the example most people have never heard of."},
  {"interaction": "EVE-IMMUNE",
   "what": "And in older adults, low-dose everolimus improved vaccine responses.",
   "why": "The same drug class used as an immunosuppressant at transplant doses improved influenza vaccine responses when given intermittently at low dose.",
   "changed": "Immune function improved rather than degraded – the opposite direction from the drug's classical use.",
   "consequence": "It suggests dose and schedule, not the target, determine whether mTOR inhibition suppresses or rejuvenates immunity.",
   "certainty": "H – human trials – but typed CONTESTED with medium confidence, because the direction of effect depends on dose and schedule and the finding has not been uniformly replicated at scale.",
   "matters": "The route ends where the field currently is. Forty years of mechanism produced clear wins in rare diseases with known causal lesions, partial wins in cancer limited by feedback and incomplete inhibition, and a genuinely open question about whether intermittent low-dose inhibition can improve ageing physiology in people. No human lifespan data exists. That is not a disappointing ending – it is the accurate one, and it is where the next set of trials is aimed."},
 ],

 "exercise": [
  {"interaction": "LOAD-MTORC1",
   "what": "You lift something heavy, and mTORC1 activity rises in the muscle.",
   "why": "Mechanical loading raises mTORC1 signalling in skeletal muscle. Rapamycin given to human volunteers before resistance exercise BLOCKS the contraction-induced rise in muscle protein synthesis – so mTORC1 signalling is needed for the acute response, not merely present during it. Rapamycin also blunted ERK1/2 in the same volunteers, so the block is not attributable to mTORC1 alone.",
   "changed": "A physical force has become a molecular signal. The muscle has committed to building.",
   "consequence": "Everything downstream is the pathway you already know, running on a stimulus that is not a hormone.",
   "certainty": "The strongest evidence in this entire section: a human interventional study (DRU2009, H – human), supported by rodent genetics and pharmacology (BOD2001). Human relevance ESTABLISHED, not plausible.",
   "matters": "Pause on what kind of evidence this is. Almost every other step in this Atlas says 'we showed this in cells and infer it in people'. Here someone gave a drug to humans, removed the pathway, and the response disappeared. That is an interruption experiment in a person, and it is worth far more than any amount of correlative human data."},
  {"interaction": "IGF1-PI3K",
   "what": "Part of the signal does travel the familiar growth-factor route.",
   "why": "IGF-1 acting through its receptor and PI3K produces myotube hypertrophy (ROM2001). Mechanical load itself is different: in mouse muscle it activated mTOR signalling independently of PI3K and Akt (Hornberger 2004, outside this corpus), so this is the hormonal contribution, not the mechanical one.",
   "changed": "PIP3 accumulates in the membrane.",
   "consequence": "Akt can be recruited, exactly as in the growth-factor route.",
   "certainty": "High mechanistic confidence, but compressed and drawn as a long dash. Cell and myotube evidence (ROM2001, CAN2002).",
   "matters": "Only PART of the signal goes this way, and that qualifier matters. Load reaches mTORC1 partly independently of circulating IGF-1, which is why you cannot substitute a growth-factor injection for the mechanical stimulus. The mechanosensor upstream of this has not been identified – the honest gap in an otherwise well-evidenced route."},
  {"interaction": "PI3K-AKT",
   "what": "PIP3 recruits Akt to the membrane.",
   "why": "Akt binds PIP3 and is then phosphorylated by PDK1 and mTORC2. Recruitment is not activation; both phosphorylations are required.",
   "changed": "Akt becomes active at the membrane.",
   "consequence": "The brake downstream can now be released.",
   "certainty": "High mechanistic confidence; cell-line evidence, human relevance plausible.",
   "matters": "The same recruitment-versus-activation distinction that runs through the whole map. In a muscle context it also means mTORC2 function is quietly required for a hypertrophy response – a dependency invisible in most exercise-physiology accounts."},
  {"interaction": "AKT-TSC",
   "what": "Akt inhibits the TSC complex.",
   "why": "Phosphorylation of TSC2 inhibits the complex and moves it away from Rheb.",
   "changed": "The master brake comes off.",
   "consequence": "Rheb stops being switched off.",
   "certainty": "High mechanistic confidence; cell-line evidence.",
   "matters": "Double-negative logic again: the growth signal in muscle works by removing inhibition, not by adding stimulation. This is why the pathway can respond within an hour of a training set – there is nothing to synthesise, only something to stop doing."},
  {"interaction": "TSC-RHEB",
   "what": "Rheb accumulates in its GTP-loaded state.",
   "why": "TSC2 is the GAP that forces Rheb to hydrolyse GTP. Inhibited GAP, loaded Rheb.",
   "changed": "The mTORC1 on-switch moves into position.",
   "consequence": "mTORC1 can be activated wherever the two meet.",
   "certainty": "High mechanistic confidence; cell-line evidence.",
   "matters": "Nutrient state still gates this, through location. A trained muscle in a fasted state does not build – which is the mechanistic basis for the entire field of post-exercise nutrition, visible here as the AND gate the nutrient route describes."},
  {"interaction": "RHEB-MTORC1",
   "what": "mTORC1 is switched on.",
   "why": "GTP-Rheb allosterically activates the kinase.",
   "changed": "mTORC1 begins phosphorylating its substrates.",
   "consequence": "The translational machinery is released.",
   "certainty": "Structurally resolved, high mechanistic confidence; cell-line evidence.",
   "matters": "Convergence point again, reached from a third direction – nutrients, hormones, and now mechanical load all terminate here. That is the strongest argument for why this one node is worth understanding properly: everything that decides whether a cell grows has to come through it."},
  {"interaction": "MTORC1-4EBP1",
   "what": "mTORC1 phosphorylates 4E-BP1 and releases the cap on translation.",
   "why": "Multi-site phosphorylation makes 4E-BP1 let go of eIF4E.",
   "changed": "eIF4E is free. A phosphate was added and an inhibitor stopped inhibiting.",
   "consequence": "Cap-dependent initiation can proceed.",
   "certainty": "High mechanistic confidence; cell-line evidence.",
   "matters": "This is the arm rapamycin only partly blocks – and yet in DRU2009 rapamycin abolished the rise in human muscle protein synthesis after a single bout of resistance exercise, measured 1–2 h afterwards. Read the endpoint carefully: that is acute protein synthesis, not muscle gained, and rapamycin also blunted ERK1/2 in the same volunteers, so the block is not cleanly attributable to this step alone. Even so, partial inhibition was enough to abolish a whole-body acute response, which suggests little reserve in it."},
  {"interaction": "4EBP1-EIF4E",
   "what": "eIF4E binds eIF4G and the initiation complex assembles.",
   "why": "4E-BP1 and eIF4G compete for the same surface. Remove one and the other binds.",
   "changed": "Ribosomes begin loading onto capped mRNA.",
   "consequence": "Protein synthesis rises.",
   "certainty": "High mechanistic confidence, structurally understood.",
   "matters": "Competition rather than catalysis, so the response is stoichiometric and immediately reversible. Muscle expresses its own balance of 4E-BP isoforms, which is one reason the same training stimulus produces different responses in different people and different fibre types."},
  {"interaction": "EIF4E-TRANSL",
   "what": "Muscle protein synthesis increases.",
   "why": "Cap-dependent initiation rises, selectively favouring a particular class of transcripts rather than everything equally.",
   "changed": "The rate and the COMPOSITION of protein synthesis both change.",
   "consequence": "Given repeated stimuli and adequate substrate, net protein accretion follows.",
   "certainty": "High mechanistic confidence; and this is the exact readout DRU2009 measured in humans and found rapamycin-sensitive.",
   "matters": "This is where the human experiment intersects the molecular chain, and it is the reason this route can claim more than the others. The measured variable in the person is the same variable the cell biology predicts."},
  {"interaction": "TRANSL-MUSCLE",
   "what": "Over days and repeated sessions, the muscle grows.",
   "why": "Repeated bouts of elevated synthesis, exceeding breakdown, produce hypertrophy. Raptor-null muscle is dystrophic; rapamycin blocks overload-induced growth.",
   "changed": "Fibre cross-sectional area increases.",
   "consequence": "The adaptation that the training was for.",
   "certainty": "Mouse genetics and pharmacology (BOD2001) and cultured myotubes; human relevance plausible. The human study in this route (DRU2009) measured the acute protein-synthesis step, not growth. Timescale: days – this is the slowest step in the route by two orders of magnitude.",
   "matters": "One honest limit to end on. mTORC1 activation is NECESSARY for healthy hypertrophy but not SUFFICIENT: constitutively activating mTORC1 in muscle does not produce good muscle, it produces inflammation and dysfunction. The signal has to be intermittent. That is a general lesson about this pathway – it is a switch that is meant to be thrown, not held."},
 ],

 "fasting": [
  {"interaction": "CR-MTORC1",
   "what": "You stop eating. mTORC1 signalling falls.",
   "why": "Two arms detect it at once: the amino-acid sensors stop reporting sufficiency, and AMPK detects the falling energy charge. Neither alone accounts for the drop.",
   "changed": "mTORC1 output declines across all of its substrates.",
   "consequence": "Everything mTORC1 was suppressing is now released – and that release runs on a slower clock than the suppression did.",
   "certainty": "High mechanistic confidence for the direction. Evidence spans mouse, rhesus and one human safety trial (ROM2016), so human relevance is graded plausible.",
   "matters": "Set the BY TIME control to seconds and look at the canvas before reading on. Almost nothing downstream has happened yet. That is the point of this route: fasting is not a state the cell enters, it is a sequence the cell runs, and the interesting part is the ordering."},
  {"interaction": "STRESS-AMPK",
   "what": "Within seconds: AMPK activates.",
   "why": "AMP and ADP bind the AMPK gamma subunit directly, activating it allosterically and protecting its activating phosphorylation. No transcription, no translation, no new protein.",
   "changed": "An active kinase exists that did not exist a moment ago.",
   "consequence": "The fastest arm of the response is now running.",
   "certainty": "High mechanistic confidence, direct biochemistry; cell-line evidence.",
   "matters": "Allosteric activation is the fastest control mechanism a cell has, and the pathway spends it on the energy sensor. That is a priority statement: running out of fuel is the emergency that cannot wait for gene expression."},
  {"interaction": "AMPK-TSC",
   "what": "Within minutes: AMPK activates the TSC brake.",
   "why": "Phosphorylation at sites distinct from Akt's – same substrate, opposite direction.",
   "changed": "TSC GAP activity rises and Rheb starts being switched off.",
   "consequence": "The mTORC1 on-switch is withdrawn.",
   "certainty": "High mechanistic confidence, though on a single M – molecular – study in this corpus.",
   "matters": "Notice the timescale step you just took: seconds to minutes. AMPK activation and AMPK's effect on mTORC1 are not simultaneous, and treating them as one event is what makes fasting look like a switch rather than a cascade."},
  {"interaction": "RHEB-MTORC1",
   "what": "mTORC1 goes quiet.",
   "why": "No GTP-Rheb, no allosteric activation – regardless of where mTORC1 is sitting.",
   "changed": "The kinase stops phosphorylating substrates. Building stops.",
   "consequence": "The brakes mTORC1 was applying to recycling now come off, one substrate at a time.",
   "certainty": "Structurally resolved, high mechanistic confidence.",
   "matters": "Stopping is the easy half. Everything from here is the cell constructing a recovery programme, and each subsequent step is slower than the last – which is why short and long fasts are not the same intervention on a different scale, but different interventions."},
  {"interaction": "MTORC1-ULK1",
   "what": "Minutes: the block on autophagy initiation lifts.",
   "why": "mTORC1 had been phosphorylating ULK1 on S757, preventing AMPK from activating it. With mTORC1 quiet, that block is gone.",
   "changed": "ULK1 becomes available.",
   "consequence": "Availability is not activity. Something still has to switch it on.",
   "certainty": "High mechanistic confidence, replicated; cell-line evidence.",
   "matters": "Release and activation as separate events, on the same protein, from two different kinases. On this arm the cell has built something close to an AND gate: ULK1-driven initiation needs mTORC1 down AND AMPK up, which stops recycling from firing on a brief dip in either signal. 'Close to', not exactly: autophagy has inputs this map does not draw, so treat the gate as the logic of these two arrows rather than as the whole control of autophagy."},
  {"interaction": "AMPK-ULK1",
   "what": "And AMPK provides the activating push.",
   "why": "AMPK phosphorylates ULK1 at activating sites – the second half of the gate.",
   "changed": "ULK1 is now both released and driven.",
   "consequence": "Autophagy initiation begins in earnest.",
   "certainty": "Direct biochemistry for the phosphorylation; the net sign is contested (Park, Lee and Kim, Nat Commun 2023, PMID 37225695: under energy stress AMPK can restrain ULK1 while protecting it).",
   "matters": "In the classic reading, one kinase performing both halves of a switch – stopping the expensive programme and starting the recovery programme – is the economy of this design. And ULK1 phosphorylates AMPK back, so the steady state is a set point rather than a command."},
  {"interaction": "ULK1-AUTOPHAGY",
   "what": "Autophagy runs. The cell begins digesting its own components.",
   "why": "ULK1 nucleates the machinery that captures cargo and delivers it to lysosomes.",
   "changed": "Damaged proteins and organelles are broken down; amino acids are regenerated.",
   "consequence": "The cell buys both time and materials – and the materials feed the very sensors that started this.",
   "certainty": "High mechanistic confidence for initiation. Autophagic FLUX in tissue is genuinely hard to measure, so quantitative in vivo claims are weaker than the mechanism.",
   "matters": "This closes a loop the Atlas cannot yet draw: autophagy-derived amino acids re-enter the sensing machinery, so a fasting cell is partly feeding itself. It is declared as an open loop in the model, because no curated edge carries that final step."},
  {"interaction": "MTORC1-TFEB",
   "what": "Also in minutes: TFEB is released from the nucleus's doorstep.",
   "why": "mTORC1 had been phosphorylating TFEB on S211, trapping it in the cytosol via 14-3-3. Quiet mTORC1 means TFEB is free to enter the nucleus.",
   "changed": "A transcription factor changes compartment – the slow arm has been armed.",
   "consequence": "Gene expression is about to change, which takes hours rather than minutes.",
   "certainty": "High mechanistic confidence, and substrate-selective: it depends on FLCN/RagC status, so mTORC1 can be active on S6K1 while TFEB escapes.",
   "matters": "The timescale changes character here. Everything before this was post-translational and reversible in minutes. From here the cell is rewriting which proteins exist, and that cannot be undone quickly. Switch BY TIME to hours and watch the rest of the route appear."},
  {"interaction": "TFEB-AUTOPHAGY",
   "what": "Hours: TFEB transcribes the autophagy programme.",
   "why": "Nuclear TFEB switches on autophagy and lysosomal genes as one coordinated module.",
   "changed": "The cell now has MORE autophagy machinery, not just active machinery.",
   "consequence": "The response becomes sustainable rather than a burst.",
   "certainty": "High mechanistic confidence; cell-line evidence, human relevance plausible.",
   "matters": "This is the difference between a short fast and a long one, and it is a difference in kind. The first hour reallocates existing machinery. Later hours build more of it. Any claim that a 16-hour and a 48-hour fast do 'the same thing more' is ignoring this step."},
  {"interaction": "TFEB-LYSOBIO",
   "what": "The lysosomal compartment itself expands.",
   "why": "The same TFEB programme drives lysosomal biogenesis – more lysosomes, not just more autophagosomes.",
   "changed": "The organelle on which mTORC1 is regulated is being rebuilt.",
   "consequence": "The cell is remodelling the platform that controls the signal that started all of this.",
   "certainty": "High mechanistic confidence; and SET2012 established the lysosome-to-nucleus circuit this arm belongs to.",
   "matters": "This closes a real feedback loop, and the model detects it as one: TFEB to lysosomal biogenesis to lysosome to mTORC1 to TFEB. Fasting does not just lower mTORC1 signalling – it changes the machine that does the signalling. That is why refeeding after a long fast is not simply the reverse of fasting."},
  {"interaction": "AMPK-MITOPHAGY",
   "what": "Over hours: damaged mitochondria are selectively cleared.",
   "why": "AMPK promotes mitophagy, the targeted autophagy of mitochondria.",
   "changed": "Mitochondrial quality improves rather than merely mitochondrial number falling.",
   "consequence": "This is one of the arms through which fasting is proposed to influence ageing.",
   "certainty": "Medium mechanistic confidence, indirect, measured largely with reporter mice – so quantitative claims are model-bound. Human relevance plausible at best.",
   "matters": "Quality control rather than accounting. A fasting cell is usually a cell with strained mitochondria, so the same signal that stopped growth is the right trigger for repairing the cause. Note the grade drop: from here the evidence weakens as the claims get more interesting."},
  {"interaction": "CR-LONGEVITY",
   "what": "And over a lifetime, restricted animals live longer.",
   "why": "Caloric restriction improved health and survival in rhesus monkeys, and macronutrient composition altered lifespan in mice.",
   "changed": "Median and in some studies maximum lifespan increase.",
   "consequence": "The molecular sequence you just walked is the leading mechanistic account of why.",
   "certainty": "Medium mechanistic confidence, INDIRECT, rhesus and mouse. Human relevance UNTESTED – there is no human lifespan data. The two large rhesus studies famously disagreed depending on the control diet, and in SOL2014, cutting calories by diluting the food did not extend lifespan in freely fed mice, while a lower protein-to-carbohydrate ratio did. Which variable carries the effect is not settled.",
   "matters": "The route asked what happens and in what order. It can answer that with reasonable confidence for the first few hours in a cell, and it cannot answer it at all for a human lifetime. The gap between those two ends of the same arrow is the single most important thing to carry away from this section – and the reason the Atlas grades human relevance separately from mechanism."},
 ],
 "open": [
  {"interaction": "LEU-LARS",
   "what": "Two labs proposed two different leucine sensors, and the field has not fully closed the question.",
   "why": "Sestrin2 binds leucine with an affinity in the range over which intracellular leucine actually fluctuates. LARS, a leucyl-tRNA synthetase, was independently proposed to moonlight as a leucine sensor acting on the Rag GTPases. Both could operate in the same cell; their relative contribution has not been measured side by side, the two proposals have not been reconciled, and which one dominates may depend on the cell type.",
   "changed": "Nothing in the cell. What changes is how much weight you should put on either arrow.",
   "consequence": "This map draws both, and marks LARS as contested with a dashed line and an amber halo.",
   "certainty": "Contested consensus, LOW mechanistic confidence, human relevance untested. The LARS model has not reproduced cleanly across labs.",
   "matters": "Start here because it is the cleanest example of the general problem. A pathway diagram that showed only the winning model would be more comfortable and less true; one that showed both without marking which is disputed would be worse still. The honest option is the one that costs a dashed line and an explanation."},
  {"interaction": "LARS-RAG",
   "what": "The proposed mechanism – LARS acting as a GAP for RagD – is the weakest link in the amino-acid arm.",
   "why": "A moonlighting GAP function for a tRNA synthetase is an unusual claim, and the reproduction record is mixed.",
   "changed": "Nothing. This is an unresolved mechanism, not an event.",
   "consequence": "If it is wrong, the amino-acid arm is simpler than this map suggests. If it is right, there is a second sensing route nobody has integrated.",
   "certainty": "Contested, low mechanistic confidence, untested in humans – and the validator flags that no boundary conditions are stated for it, which is itself a curation gap this route is happy to expose.",
   "matters": "Notice that the Atlas is admitting a hole in its own curation here rather than hiding it. A validator warning left visible is more useful than a warning silenced."},
  {"interaction": "GLN-MTORC1-ARF1",
   "what": "Glutamine may reach mTORC1 without the Rag GTPases at all.",
   "why": "A Rag-independent, Arf1-dependent route has been reported. If real, it means the lysosomal recruitment story is not the only way in.",
   "changed": "Potentially the architecture of the whole nutrient arm.",
   "consequence": "The map draws it dotted and thin, because the claim is large and the reproduction is not uniform.",
   "certainty": "Contested, low mechanistic confidence, human relevance untested.",
   "matters": "This one matters disproportionately because of what it would overturn. Most contested edges are details; this is a contested claim about whether the central mechanism is complete. Weight of a claim and strength of its evidence are independent, and this step has high weight with low evidence."},
  {"interaction": "GATOR2-GATOR1",
   "what": "A step everyone draws confidently has a mechanism nobody has resolved.",
   "why": "That GATOR2 inhibits GATOR1 is not in doubt – it is in every textbook figure. HOW it does so catalytically is still argued, even after the GATOR2 structure was determined.",
   "changed": "Nothing. This is a hole in the middle of a canonical pathway.",
   "consequence": "Every account of amino-acid sensing passes through a step whose mechanism is an open question.",
   "certainty": "Consensus graded EMERGING with medium mechanistic confidence – deliberately not established, despite how confidently the step is usually drawn.",
   "matters": "This is the most instructive step in the route. It is not contested, not obscure, and not weakly evidenced – it is simply unresolved, in a place where the diagram looks finished. Textbook confidence and mechanistic understanding are different things, and a map that grades them the same teaches the wrong lesson."},
  {"interaction": "METFORMIN-AMPK",
   "what": "The most-prescribed drug that touches this pathway has a contested mechanism.",
   "why": "Complex I inhibition raising AMP, AMPK-independent Rag inhibition, lysosomal PEN2–ATP6AP1 sensing and gut-microbiome effects have all been proposed. HOW2017 showed the mTORC1 effect is dose-dependent and mechanistically plural.",
   "changed": "Nothing mechanistically. What changes is how confidently anyone can say why metformin works.",
   "consequence": "Claims that metformin acts 'via AMPK' are shorthand for an unsettled question.",
   "certainty": "Contested, LOW mechanistic confidence. And the boundary condition is decisive: concentrations used in cell culture routinely exceed plasma levels achieved at clinical doses.",
   "matters": "Dose is the whole argument, and it is the most commonly ignored variable in translating cell biology. A mechanism demonstrated at 5 mM in a dish may be irrelevant at 20 uM in a patient. Any in vitro mechanism claim should come with the concentration attached."},
  {"interaction": "METFORMIN-MTORC1",
   "what": "So the downstream link inherits the uncertainty.",
   "why": "If the route from metformin to AMPK is unsettled, the route from metformin to mTORC1 cannot be firmer than its weakest segment.",
   "changed": "Nothing. This is uncertainty propagating along a chain.",
   "consequence": "Metformin's mTOR-lowering effect is real and reproducible; its mechanism is not settled, and the two facts are often conflated.",
   "certainty": "Contested, low mechanistic confidence, indirect. Cited across mammalian cells and mice.",
   "matters": "Uncertainty compounds along a path, and no pathway diagram shows that. If a route has three steps at medium confidence, the endpoint is not medium confidence. The Atlas grades each step but cannot yet grade a PATH – a genuine limitation of this design, worth naming."},
  {"interaction": "RAPA-MTORC2",
   "what": "Whether chronic rapamycin hits mTORC2 rests on two studies in this corpus: cell lines (SAR2006) and mouse liver (LAM2012). No study here tests it directly in people.",
   "why": "Prolonged exposure was reported to disrupt mTORC2 assembly in some cell types. It is not the acute, direct inhibition seen with mTORC1, and it is not universal.",
   "changed": "Nothing acutely. Over weeks, possibly a great deal.",
   "consequence": "The textbook claim 'rapamycin inhibits mTORC1 but not mTORC2' is a statement about acute treatment being applied to chronic therapy.",
   "certainty": "Contested, LOW mechanistic confidence, one supporting study. Cell type and duration both change the answer.",
   "matters": "The clinical stakes are inverted relative to the evidence. This is one of the weakest-evidenced edges in the Atlas, and it may explain the most common serious side effect of the drug class. Low confidence does not mean low importance – which is exactly why the two are graded separately."},
  {"interaction": "MTORC1-RCC",
   "what": "An association presented in a chain of causal claims.",
   "why": "Renal cancers frequently carry lesions that leave mTORC1 active. That is a correlation between genotype and pathway state – not evidence that mTORC1 activation initiates the disease.",
   "changed": "Nothing mechanistically. This arrow records a statistical relationship.",
   "consequence": "It explains why the tissue responds to rapalogs, and why an exceptional responder was traceable to TSC1 loss. It does not establish causation.",
   "certainty": "Typed ASSOCIATION, directness UNRESOLVED, mechanistic confidence low – the lowest grade available, applied deliberately.",
   "matters": "Correlation sitting between two well-evidenced clinical steps is the most dangerous position on any pathway map, because the reader's eye carries causality across it. Typing it as an association and drawing it dotted is the only defence, and it only works if someone reads the grade."},
  {"interaction": "MTORC1-LONGEVITY",
   "what": "The pathway's most famous claim has no human evidence at all.",
   "why": "Lowering mTOR signalling extends lifespan in yeast, worms, flies and mice – reproducibly, multi-site, in genetically heterogeneous strains.",
   "changed": "In those organisms, median and sometimes maximum lifespan.",
   "consequence": "In humans: unknown. Not disputed, not negative – simply never measured.",
   "certainty": "Human relevance UNTESTED. That grade is arithmetic, not pessimism: no human lifespan trial of any mTOR-lowering intervention exists or could have completed.",
   "matters": "Thirteen interactions in this map carry human relevance untested, and every longevity edge is one of them. This is the single most important calibration in the Atlas, because it is the claim most likely to be repeated without its qualifier. Robust in four species is a strong result; it is not a human result."},
  {"interaction": "RAPA-LONGEVITY",
   "what": "The same gap, for the drug specifically.",
   "why": "Rapamycin extends mouse lifespan reproducibly, including when started late in life.",
   "changed": "Mouse lifespan. Effects are sex- and strain-dependent, and healthspan and lifespan do not always move together.",
   "consequence": "It is the strongest pharmacological longevity result in mammals and the basis for current human interest.",
   "certainty": "Mouse work (A – animal), medium mechanistic confidence, human relevance untested. LEE2024 systematically reviewed what human rapamycin data actually supports – and lifespan is not among it.",
   "matters": "There is a systematic review in this corpus specifically about human rapamycin data, and the honest summary of it is that the human evidence concerns safety and surrogate outcomes, not longevity. When a claim has a systematic review and the review does not support the popular version, the gap is not in the science – it is in the retelling."},
  {"interaction": "EVE-IMMUNE",
   "what": "A case where the direction of effect itself is contested.",
   "why": "The same drug class is an immunosuppressant at transplant doses, yet intermittent low-dose everolimus improved influenza vaccine responses in older adults.",
   "changed": "Immune function – in opposite directions depending on dose and schedule.",
   "consequence": "'mTOR inhibition suppresses immunity' and 'mTOR inhibition rejuvenates immunity' are both supported, under different regimens.",
   "certainty": "Human trials (H), and still typed CONTESTED with medium confidence – because dose and schedule change the sign of the effect and the finding has not been uniformly replicated at scale.",
   "matters": "Human trial evidence and contested status are not mutually exclusive, and this step exists to make that visible. Good human data can still leave a question open when the effect depends on a variable the trials sampled differently. Dose and schedule are not implementation details here; they are part of the claim."},
  {"interaction": "S6K1-LONGEVITY",
   "what": "And a result whose crucial qualifier is routinely dropped.",
   "why": "S6K1-null mice live longer and resist age-related pathology – in FEMALES. The effect is sex-specific.",
   "changed": "Median lifespan and metabolic protection, in one sex.",
   "consequence": "It is the cleanest genetic evidence that a specific mTORC1 output influences lifespan, and it is narrower than its usual citation.",
   "certainty": "Mouse genetics (A – animal), medium mechanistic confidence, human relevance untested – and an external review of this Atlas found the sex-specificity stated in two places and omitted in two others. We were making the error this step describes.",
   "matters": "End on that. The route has been about where the pathway stops being known, and the most common failure is not a missing experiment – it is a qualifier lost in transmission. Sex, strain, dose, duration, species: five words that turn a true claim into a false one when dropped, and no pathway diagram has room for them. Which is why this Atlas puts them in the grade instead."},
 ],
 "cancer": [
  {"interaction": "PTEN-PI3K",
   "what": "PTEN is lost, and nothing erases the growth signal any more.",
   "why": "PTEN is a lipid phosphatase: it converts PIP3 back to PIP2. It does not inhibit the PI3K enzyme – it destroys PI3K's product. Delete PTEN and the product accumulates even at normal PI3K activity.",
   "changed": "PIP3 builds up in the membrane. The signal is no longer being written faster than it is erased; it is simply not being erased.",
   "consequence": "Anything that reads PIP3 now spends far more of its time at the membrane, with no upstream hormone required.",
   "certainty": "Mouse evidence in this corpus (A – animal), with PTEN among the most frequently inactivated tumour suppressors in human cancer. Graded human-relevance plausible here because the cited studies are mouse, not because the human genetics is weak.",
   "matters": "The first thing to understand about mTOR in cancer is that the lesion is usually not in mTOR. It is in the machinery that decides whether mTOR should be receiving a signal. That distinction is why inhibiting mTOR treats a symptom of the genotype rather than its cause."},
  {"interaction": "PI3K-AKT",
   "what": "Accumulated PIP3 recruits Akt continuously.",
   "why": "Akt binds PIP3 and is then phosphorylated by PDK1 and mTORC2. With PIP3 chronically elevated, recruitment stops being an event and becomes closer to a standing condition.",
   "changed": "Akt occupies the membrane persistently, and Akt signalling runs high.",
   "consequence": "The growth-permission signal is now generated inside the cell rather than arriving from outside it.",
   "certainty": "High mechanistic confidence, cell-line evidence.",
   "matters": "This is what oncogenic means in signalling terms: not a stronger signal, but a signal that no longer requires its input. The cell has stopped asking the organism for permission and started granting it to itself."},
  {"interaction": "AKT-TSC",
   "what": "Akt inhibits the TSC complex, persistently now rather than in bursts.",
   "why": "Phosphorylation of TSC2 by Akt inhibits the complex and moves it away from where its target sits.",
   "changed": "The pathway's master brake is held off continuously rather than transiently.",
   "consequence": "Rheb stops being switched off.",
   "certainty": "High mechanistic confidence, cell-line evidence; and TSC loss in people establishes that removing this brake causes disease.",
   "matters": "Notice that the tumour is exploiting the pathway's own logic rather than breaking it. Every step from here on is the normal mechanism running correctly on a false input – which is precisely why the pathway is hard to drug selectively."},
  {"interaction": "TSC-RHEB",
   "what": "With TSC inhibited, Rheb stays GTP-loaded.",
   "why": "TSC2 is the GAP that forces Rheb to hydrolyse GTP. Inhibit the GAP and Rheb accumulates in its active state.",
   "changed": "The mTORC1 on-switch is held in the on position.",
   "consequence": "mTORC1 will now fire whenever it is at the lysosome – which, given adequate nutrients, is most of the time.",
   "certainty": "High mechanistic confidence, cell-line evidence.",
   "matters": "The AND gate from the nutrient and growth-factor routes has been half-defeated. Nutrient sensing still controls location, but the permission input is stuck at yes. A coincidence detector with one input jammed is no longer a detector."},
  {"interaction": "RHEB-MTORC1",
   "what": "mTORC1 is constitutively active.",
   "why": "GTP-Rheb allosterically activates mTORC1 whenever the two are co-located.",
   "changed": "The kinase runs without regard to whether the organism wants this cell to grow.",
   "consequence": "Its outputs run too: translation of growth and invasion programmes up, autophagy down.",
   "certainty": "Structurally resolved, high mechanistic confidence, cell-line evidence.",
   "matters": "This is the state the drug will be aimed at. Worth holding onto the fact that mTORC1 itself is entirely normal here – correct protein, correct regulation, wrong input. A drug that inhibits mTORC1 is therefore not correcting an error; it is imposing a second one in the opposite direction."},
  {"interaction": "MTORC1-TUMOR",
   "what": "The tumour grows on that output.",
   "why": "Sustained selective translation, suppressed autophagy, and the biosynthetic arms together supply much of what a proliferating cell needs.",
   "changed": "Proliferation and mass increase.",
   "consequence": "mTORC1 becomes a rational drug target for this genotype.",
   "certainty": "High mechanistic confidence but INDIRECT, and strongly genotype-dependent: a real dependency in TSC- and PI3K-pathway-mutant contexts, considerably weaker elsewhere.",
   "matters": "The gap between this arrow and a treatment is where most of the last twenty years of clinical disappointment lives. 'mTORC1 supports tumour growth' is a statement about biology; 'inhibiting mTORC1 treats this tumour' is a statement about dependency – and dependency is contextual in a way the arrow cannot show."},
  {"interaction": "EVE-MTORC1",
   "what": "Give everolimus. mTORC1 is inhibited – partially.",
   "why": "Like rapamycin, everolimus works as a complex with FKBP12 and obstructs the substrate channel rather than occupying the active site. Obstruction is partial by nature.",
   "changed": "S6K1 phosphorylation collapses. 4E-BP1 phosphorylation substantially persists – and 4E-BP1 controls the translation arm that matters most for proliferation.",
   "consequence": "The tumour loses one output and keeps a good part of the other, while the reader's assay says the drug is working.",
   "certainty": "High confidence with H – human trial – evidence across several indications, including BAS2012 in hormone-receptor-positive breast cancer.",
   "matters": "Two failures compound here. The drug is incomplete, and the standard readout is blind to the part it misses – because S6K1 is rapamycin-sensitive and became the field's default assay. For years the pathway looked more inhibited than it was, in the exact output that mattered."},
  {"interaction": "S6K1-IRS1",
   "what": "And inhibiting mTORC1 releases a brake the tumour had been living under.",
   "why": "Active S6K1 had been phosphorylating IRS-1 and marking it for degradation. Inhibit mTORC1, S6K1 goes quiet, and IRS-1 stops being destroyed.",
   "changed": "IRS-1 protein accumulates. The adaptor that couples receptors to PI3K comes back.",
   "consequence": "PI3K signalling recovers – driven by the drug, not despite it.",
   "certainty": "High mechanistic confidence, multiple supporting studies, cell-line evidence. ROD2011 additionally showed mTOR kinase inhibition produces biphasic Akt regulation through exactly this kind of feedback.",
   "matters": "This is the sentence that reframes the whole route. The drug does not merely fail to finish the job – it actively removes one of the tumour's own restraints. Any therapy that interrupts a negative feedback loop is partly self-defeating, and this loop was there all along in the growth-factor route."},
  {"interaction": "IRS1-PI3K",
   "what": "PI3K and Akt reactivate, which can give the tumour a way around the drug.",
   "why": "Restored IRS-1 recruits PI3K to receptors that are still present, regenerating PIP3 and reactivating Akt.",
   "changed": "The upstream arm recovers while mTORC1 remains partly inhibited – the worst of both worlds, since Akt has many targets besides mTORC1.",
   "consequence": "Where this happens it can blunt the drug's effect. It is one proposed reason why rapalogs have had modest effects in many solid tumours, though not the only one, and in some settings they did extend survival (temsirolimus in poor-prognosis kidney cancer, HUD2007).",
   "certainty": "High mechanistic confidence, cell-line evidence; ORE2006 showed the parallel arm in which mTOR inhibition raises receptor tyrosine kinase signalling directly.",
   "matters": "This escape route needs no mutation. It requires no new genetic event and no selection time – it is the pathway's normal homeostatic wiring responding to the drug. That is why this kind of adaptive resistance can appear quickly, as seen in patient tumours after RAD001 (ORE2006), and why some combination strategies target the loop rather than the kinase. Whether it decides clinical outcome in a given patient has not been shown."},
  {"interaction": "MTORC1-MAPK",
   "what": "There is a second escape, through MAPK.",
   "why": "mTORC1 inhibition activates ERK in a PI3K-dependent manner. CAR2008 traces it through the same S6K1–PI3K–Ras relay that carries the IRS-1 escape, so this is a second OUTPUT of one feedback circuit rather than a separate circuit.",
   "changed": "ERK activity rises, which additionally phosphorylates and inhibits TSC2, feeding back toward mTORC1.",
   "consequence": "The drug now faces two reroutes with a shared root. Because they share it, blocking PI3K upstream can close both – while blocking only the IRS-1 arm leaves the MAPK output open.",
   "certainty": "High mechanistic confidence. CAR2008 combines cell lines, a mouse prostate model and tumour biopsies from patients treated with RAD001, in which MAPK activation depended on the dosing schedule. This paper sat in the Atlas corpus with zero edges until an external review flagged that one of the pathway's most clinically important feedback arms was missing from the graph.",
   "matters": "Redundancy is the theme of this pathway and it cuts both ways. The same architecture that makes the cell robust makes the tumour robust. This is the mechanistic rationale for combining mTOR inhibition with MEK inhibition rather than escalating the mTOR dose."},
  {"interaction": "TORIN-MTORC1",
   "what": "So build a drug that occupies the site instead of obstructing it.",
   "why": "ATP-competitive inhibitors compete with ATP at the mTOR active site. They do not need FKBP12 and they suppress the 4E-BP1 phosphorylation that rapalogs leave standing.",
   "changed": "Inhibition becomes deep rather than partial – and extends to mTORC2, because both complexes share the same catalytic site.",
   "consequence": "The 4E-BP1 escape closes. The mTORC2 toxicity opens.",
   "certainty": "High mechanistic confidence from cell-line pharmacology (THO2009, FEL2009, CHR2009). Clinical development of this class has been limited by toxicity attributed to simultaneous mTORC2 inhibition.",
   "matters": "Selectivity in this pathway comes from accessory subunits, not from the catalytic site – so a drug aimed at the site inherits no selectivity. That is a structural fact rather than a design failure, and it sets up the problem the next generation had to solve."},
  {"interaction": "BISTERIC-MTORC1",
   "what": "The current attempt: deep inhibition of mTORC1 only.",
   "why": "A bivalent molecule engages both an FKBP12-dependent site and the active site, achieving the depth of an active-site inhibitor with selectivity for mTORC1 over mTORC2.",
   "changed": "In principle: 4E-BP1 actually suppressed, without the mTORC2-dependent metabolic toxicity.",
   "consequence": "RMC-5552 has completed a phase 1 trial in advanced solid tumours. Further clinical development has not been reported since (see the drug pipeline page).",
   "certainty": "One phase 1 trial (SCH2025, 2025). H – human – but phase 1 reports safety and pharmacodynamics, not efficacy. Consensus graded emerging, on a single study. Directness is indirect because, like rapalogs, the mechanism still requires FKBP12.",
   "matters": "This is the honest answer to the route's question, and it is not a failure story. A weakness identified in cell culture in 2009 became a molecular design constraint, then a compound, then a trial in 2025. The pathway was first drugged with a molecule discovered before anyone knew what it did, and it has taken this long to build one aimed at what we now know. Whether closing the 4E-BP1 escape improves survival is unanswered; a phase 1 trial is not designed to test it."},
 ],
 "aa": [
  {"interaction": "LEU-SESN2",
   "what": "Leucine binds Sestrin2 – and switches a brake off.",
   "why": "Sestrin2 carries a pocket that fits leucine with roughly 20 µM affinity. That number is the whole argument: it sits inside the range over which leucine inside a real cell actually rises and falls, so Sestrin2 changes state when leucine changes, rather than being permanently full or permanently empty.",
   "changed": "Leucine-loaded Sestrin2 can no longer hold onto GATOR2. Nothing has been switched on yet – something has been let go of.",
   "consequence": "GATOR2 is now free. Watch what it does with that freedom: it does not activate anything either. It inhibits the next brake.",
   "certainty": "The binding is structurally resolved and the affinity measured in vitro. What is not established is whether the same 20 µM setpoint holds in tissues with different leucine transport – so this is high mechanistic confidence with unproven human physiological calibration.",
   "matters": "This is where the pathway's logic starts being counter-intuitive. The cell does not detect food and then send a 'grow' signal. It detects food and stops sending a 'do not grow' signal. Most nutrient inputs drawn in this map work that way – count the double negatives yourself rather than taking the word 'almost every' on trust – and it is the reason the pathway is so hard to read off a diagram of arrows."},
  {"interaction": "SESN2-GATOR2",
   "what": "GATOR2 is released – the first brake comes off.",
   "why": "Without leucine, Sestrin2 binds GATOR2 and holds it in check. Leucine binding to Sestrin2 disrupts that interaction (WOL2015), so the two competing states are Sestrin2 bound to leucine and Sestrin2 bound to GATOR2. Released GATOR2 becomes able to act on GATOR1.",
   "changed": "GATOR2 goes from held by Sestrin2 to free. In this step the cell changes how much GATOR2 is free, not how much GATOR2 it makes.",
   "consequence": "Available GATOR2 now inhibits GATOR1. Count the negatives as you go – you are two into a chain of them.",
   "certainty": "Mechanistically solid and reproduced. Structures of the GATOR2 cage and its sensor-binding surfaces exist; the cited corpus evidence here is cell-line biochemistry, so human relevance is plausible rather than demonstrated.",
   "matters": "Regulation by sequestration rather than by synthesis is fast and cheap – no transcription, no translation, no degradation. It lets the cell respond to leucine within minutes rather than hours. Evolution reaches for this trick whenever speed matters."},
  {"interaction": "GATOR2-GATOR1",
   "what": "GATOR2 shuts down GATOR1 – the second brake comes off.",
   "why": "GATOR1 is the machine that switches the Rag GTPases off. GATOR2 inhibits it. So inhibiting GATOR1 means the Rags stop being switched off.",
   "changed": "GATOR1's GAP activity toward RagA/B falls. Two negatives have now cancelled: leucine present → Sestrin2 inhibited → GATOR2 free → GATOR1 inhibited.",
   "consequence": "The Rag GTPases can finally load GTP and stay loaded. That is the state that does something.",
   "certainty": "Everyone agrees the inhibition happens; nobody has fully resolved how it happens catalytically. This step is graded emerging consensus with medium mechanistic confidence – an honest hole in the middle of a canonical pathway.",
   "matters": "Worth pausing on: this is a textbook step that a textbook will draw as a confident arrow, and the mechanism behind it is genuinely unresolved. A map that hides that is more comfortable and less useful."},
  {"interaction": "GATOR1-RAG",
   "what": "With GATOR1 suppressed, the Rag GTPases stay loaded with GTP.",
   "why": "GATOR1 is a GAP – it forces RagA/B to hydrolyse GTP to GDP. Remove the GAP and RagA/B accumulates in the GTP state, which is its active conformation.",
   "changed": "RagA/B flips from GDP-loaded to GTP-loaded. Note the inversion in this heterodimer: RagA/B is active with GTP, but its partner RagC/D is active with GDP.",
   "consequence": "GTP-loaded RagA/B can now grip Raptor. That grip is what brings mTORC1 in.",
   "certainty": "The GAP activity is directly demonstrated biochemistry, and human genetics supports its physiological importance – DEPDC5 mutations cause focal epilepsy. The cited corpus evidence is cell-line work, so human relevance is graded plausible.",
   "matters": "Nucleotide state is the pathway's memory. A GTPase holds its answer until something actively changes it, which lets a signal that arrived seconds ago still be true now."},
  {"interaction": "RAGULATOR-RAG",
   "what": "Ragulator holds the Rags on the lysosomal membrane.",
   "why": "The Rags are not free-floating. Ragulator is lipid-anchored to the lysosome and clamps the Rag heterodimer to that surface, so everything the Rags do, they do at one specific place.",
   "changed": "Nothing about the Rags' activity changes here. What is fixed is their address.",
   "consequence": "Because the Rags are on the lysosome, whatever they recruit arrives on the lysosome too.",
   "certainty": "The tethering role is well established. Its GEF activity is a separate question. The original report (2012) assigned it to RagA/B; later biochemistry (SHE2018B) found an unusual GEF activity toward RagC instead, with SLC38A9 acting on RagA. That GEF role rests on fewer independent studies than the tethering function, and how much each activity matters in different nutrient states is open.",
   "matters": "This is the step that makes the rest of the pathway make sense. Signalling here is not chemistry in free solution – it is a set of mechanisms for putting particular molecules in particular places. Location is the regulated variable."},
  {"interaction": "RAG-MTORC1",
   "what": "The Rags recruit mTORC1 to the lysosome. They do not switch it on.",
   "why": "GTP-loaded RagA/B binds Raptor directly, dragging the whole mTORC1 complex out of the cytosol and onto the lysosomal surface.",
   "changed": "mTORC1's location changes, and only its location. Its kinase activity at this moment is essentially unchanged. Recruitment is not activation – these are two different claims and this map draws them differently on purpose.",
   "consequence": "mTORC1 is now at the surface where the Rheb pool that switches it on in this route is waiting. Meeting Rheb is the event that actually switches it on.",
   "certainty": "Directly demonstrated and reproduced across labs; the corpus evidence is cell-line biochemistry, so human relevance is graded plausible rather than established.",
   "matters": "If you take one thing from this route, take this: in the canonical model, amino acids on their own are not enough to drive growth. Starve a cell of growth factors, flood it with leucine, and mTORC1 is pulled to the lysosome but stays largely off, because without growth-factor input TSC keeps most Rheb in its GDP-bound state. The nutrient arm answers 'are the parts available?' – it does not answer 'am I allowed to build?'"},
  {"interaction": "RHEB-MTORC1",
   "what": "Rheb-GTP switches mTORC1 on. Nutrients act mainly through the Rags rather than on Rheb, though withdrawing amino acids also pulls TSC2 to the lysosome and switches Rheb off (DEM2014).",
   "why": "GTP-loaded Rheb binds mTORC1 and physically realigns its active site into a catalytically competent conformation. This is an allosteric activation, a different kind of event from everything upstream in this route.",
   "changed": "mTORC1 becomes an active kinase, and S6K1 and 4E-BP1 are now phosphorylated efficiently.",
   "consequence": "The cell builds. And because Rheb is controlled by the TSC complex, which integrates inputs from Akt, AMPK, ERK and other kinases, the growth-factor and energy arms all converge on this single step.",
   "certainty": "Structurally resolved and mechanistically secure. Cited evidence is mammalian cell work, so human relevance is graded plausible.",
   "matters": "This is coincidence detection, and it is the answer to why the pathway is built the way it is. Two independent conditions – nutrients supplying location, growth factors supplying activation – must both be satisfied at the same place and the same time. A cell that grew on either signal alone would build without materials or build when told not to. The lysosome is where the cell checks both answers against each other."},
 ],
}



# ---------------------------------------------------------------------------
# 3b. Kontextové poznámky doplněné nad rámec původního `ctx`.
#
# Nález recenze č. 1: mapa působí příliš definitivně. Jednotlivá hrana může
# být v jednom buněčném typu nosná a v jiném zanedbatelná. Tam, kde to platí
# silně, se to říká přímo na hraně – ne jen v globálním disclaimeru.
# ---------------------------------------------------------------------------
# CTX_EXTRA -- ZRUŠENO 2026-09-30. Hrany žijí jen v Airtable Relations
# (pole: Context_Dependence). Čte se přes relations_bake.py -> atlas_data/relations_baked.json.



# ---------------------------------------------------------------------------
# 3c. Kontextové role uzlů.
#
# Nález recenze č. 7: stejná molekula dělá v různých kontextech různé věci.
# Akt inhibuje TSC2, aktivuje mTORC1 nepřímo, řídí FOXO a metabolismus
# glukózy – a mapa dráhy z toho ukazuje jen část. Tady se říká nahlas, co
# molekula dělá i mimo tuhle mapu, aby si nikdo nemyslel, že vidí celou roli.
# ---------------------------------------------------------------------------
CONTEXT_ROLES = {
 "Akt/PKB": [
   ["In this map", "Inhibits the TSC complex and displaces PRAS40, so growth-factor signal reaches Rheb and then mTORC1."],
   ["Beyond this map", "Phosphorylates and excludes FOXO transcription factors from the nucleus, suppressing a stress-resistance and autophagy programme that partly opposes mTORC1's outputs."],
   ["Metabolism", "Drives glucose uptake via GLUT4 trafficking and inhibits GSK3 – effects largely independent of mTORC1."],
   ["Isoform caveat", "AKT1/2/3 are not interchangeable; AKT2 dominates in insulin-responsive metabolic tissue, so 'Akt' in a paper may not be the Akt in your tissue."],
 ],
 "AMPK": [
   ["In this map", "Two arms onto mTORC1 (activating TSC2, phosphorylating Raptor) plus a direct arm onto ULK1 whose net sign is disputed."],
   ["Beyond this map", "Switches on catabolism broadly – fatty-acid oxidation via ACC, mitochondrial biogenesis via PGC-1α – not only mTORC1 suppression."],
   ["Context", "Requires LKB1 (or CaMKK2) to be armed at all. LKB1-null cells cannot mount this response, which is why AMPK-dependence claims are cell-line specific."],
 ],
 "mTORC1": [
   ["In this map", "The coincidence detector: in the canonical route it is switched on at the lysosome when nutrient-supplied location and growth-factor-supplied Rheb activation coincide. mTOR activity is also measured in the cytosol, nucleus and near mitochondria (BOU2020, FER2024)."],
   ["Substrate selectivity", "Not a single on/off output. Rapamycin collapses S6K1 phosphorylation while sparing much of 4E-BP1, and TFEB phosphorylation depends on FLCN/RagC – so 'mTORC1 activity' depends on which substrate you measure."],
   ["Beyond this map", "Also regulates ribosome biogenesis, one-carbon metabolism via ATF4, and immune cell differentiation."],
 ],
 "mTORC2": [
   ["In this map", "Phosphorylates Akt S473 and SGK1; acutely rapamycin-insensitive, which is how it is separated from mTORC1 experimentally."],
   ["Beyond this map", "Controls actin organisation via PKCα (the original yeast TORC2 phenotype) and ion transport via SGK1."],
   ["Context", "Chronic rapamycin can disrupt mTORC2 assembly in some cell types but not others – a contested, time- and cell-type-dependent effect, not a general property."],
 ],
 "Sestrin2": [
   ["In this map", "Leucine sensor acting as a brake: leucine-free Sestrin2 holds GATOR2 inactive."],
   ["Beyond this map", "Stress-inducible via p53 and ATF4, so it also reports DNA damage and oxidative stress – it is a stress/nutrient junction, not a pure amino-acid sensor."],
   ["Contested", "Whether the ~20 uM leucine affinity measured in vitro is the operating setpoint in tissue is untested."],
 ],
 "FLCN / FNIP1/2": [
   ["In this map", "GAP for RagC/D; required for mTORC1 to phosphorylate TFEB."],
   ["Apparent paradox", "A tumour suppressor in Birt-Hogg-Dube that behaves as a POSITIVE regulator of one mTORC1 arm. Resolved by substrate selectivity: losing FLCN leaves mTORC1 active on S6K1 while TFEB escapes into the nucleus."],
 ],
 "S6K1": [
   ["In this map", "The canonical rapamycin-sensitive mTORC1 readout; degrades PDCD4 and IRS-1."],
   ["Feedback", "Its IRS-1 arm is a negative feedback loop onto PI3K, so inhibiting mTORC1 reactivates Akt – a large part of why rapalog monotherapy underperforms."],
   ["Context", "Its lifespan phenotype in mice is sex-specific (female), which is routinely dropped when the result is cited."],
 ],
 "4E-BP1": [
   ["In this map", "Translational repressor released by mTORC1 phosphorylation."],
   ["Why it matters disproportionately", "Only partially rapamycin-sensitive. That goes a long way to explain the rapalog/Torin discrepancy and was a main motivation for ATP-competitive inhibitors."],
   ["Context", "Redundant with 4E-BP2 in many tissues, so single-knockout phenotypes understate the arm."],
 ],
 "TFEB": [
   ["In this map", "Nuclear-excluded when phosphorylated by mTORC1; drives lysosomal and autophagy genes when free."],
   ["Loop", "Its output builds more lysosomes, which is where mTORC1 is regulated – a slow feedback arm this map cannot fully close because the lysosome-biogenesis-to-mTORC1 step is not curated here."],
 ],
 "ULK1": [
   ["In this map", "Autophagy initiator, inhibited by mTORC1 (S757) and activated by AMPK."],
   ["Loop", "Phosphorylates AMPK back, dampening its own activator – so 'AMPK switches on autophagy' is a loop with its own set point, not an arrow."],
 ],
 "TSC1/TSC2": [
   ["In this map", "The master brake: a GAP that switches Rheb off, integrating Akt, AMPK, ERK/RSK and REDD1 inputs."],
   ["Regulation by location", "Substantially controlled by recruitment to and release from the lysosomal surface, not only by changes in catalytic activity – a mode of control easy to miss in an arrow diagram."],
   ["Human relevance", "TSC1/TSC2 loss is the cleanest human demonstration that mTORC1 hyperactivation drives disease, and the setting where rapalogs work best."],
 ],
 "Rag GTPases": [
   ["In this map", "Control mTORC1's LOCATION, not its activity."],
   ["Nucleotide inversion", "RagA/B is active GTP-loaded; its partner RagC/D is active GDP-loaded. Reading both the same way inverts half the amino-acid arm."],
 ],
 "PI3K": [
   ["In this map", "Produces PIP3, which recruits Akt and relieves the SIN1 PH domain on mTORC2."],
   ["Beyond this map", "PIK3CA is among the most frequently mutated oncogenes in human cancer; its output is a lipid, so it is reversed by a phosphatase (PTEN) rather than switched off."],
 ],
 "Rheb": [
   ["In this map", "The activator of mTORC1: GTP-loaded Rheb switches on a kinase the Rags have already brought to the membrane. Neither Rheb nor the Rags is sufficient alone. Also the convergence point of the growth-factor arm."],
   ["Declared simplification", "Drawn on the lysosomal band because that is where it meets mTORC1, but a large Rheb pool sits on the ER and Golgi and which pool activates mTORC1 is argued."],
 ],
 "DEPTOR": [
   ["In this map", "Built-in inhibitor of both complexes."],
   ["Apparent paradox", "Overexpressed in a subset of multiple myeloma where cells depend on it – an inhibitor behaving as an oncogenic dependency."],
 ],
}



# ---------------------------------------------------------------------------
# 3d. Pojmenování zpětných smyček.
#
# Smyčky se hledají strojově (nemůže vzniknout rozpor se seznamem hran), ale
# jméno dostane smyčka podle CHARAKTERISTICKÉ hrany. Pravidla se vyhodnocují
# v tomhle pořadí, první vyhraje. Smyčka bez pravidla dostane jméno z cesty.
# ---------------------------------------------------------------------------
LOOP_RULES = [
 ("S6K1-IRS1",   "S6K1 → IRS-1 feedback",
  "One of the pathway's best-characterised and most clinically important feedback loops. mTORC1 drives S6K1, S6K1 degrades IRS-1, and PI3K signalling falls. Block mTORC1 and IRS-1 is spared, so Akt reactivates – a large part of the reason rapalog monotherapy underperforms."),
 ("MTORC1-GRB10", "mTORC1 → Grb10 feedback",
  "The second arm of negative feedback onto the receptor. mTORC1 phosphorylation stabilises Grb10, which damps insulin/IGF-1 receptor signalling."),
 ("MTORC1-MAPK",  "mTORC1 → MAPK feedback",
  "mTORC1 inhibition relieves feedback and activates ERK in a PI3K-dependent way. This is the rationale for combining mTOR with MEK inhibition rather than escalating mTOR inhibition alone."),
 ("ULK1-AMPK",    "AMPK ↔ ULK1 set-point",
  "ULK1 phosphorylates the very kinase that activated it. So 'AMPK switches on autophagy' is not an arrow but a loop with a set-point, and the steady state depends on the relative strength of both directions."),
 ("LYSOBIO-LYSOSOME", "TFEB → lysosome → mTORC1 set-point",
  "The slow loop: mTORC1 inhibition releases TFEB, TFEB builds more lysosomes, and the lysosomal surface is where mTORC1 is regulated. So inhibiting the pathway changes the machine that does the signalling, not only its output. The last step – how a larger lysosomal compartment feeds back on mTORC1 quantitatively – is the weakest link, and this Atlas does not curate a study for it."),
 ("ROS-MTORC1",   "mTORC1 ↔ ROS amplification",
  "The only positive loop in this map, and the weakest-evidenced one. mTORC1 unleashed by TSC1 deletion floods haematopoietic stem cells with ROS (CHE2008, mouse), and oxidative stress activates a PI3K–Akt–mTORC1 relay back (JIN2026, one cell line, multidrug-resistance context). Positive loops amplify rather than stabilise, which is how a transient insult could become a persistent state – but the two arms come from different systems and neither was measured in the other's setting, so read this as a circuit the map makes visible for testing, not as an established one."),
]



# Smyčky, které literatura popisuje, ale tahle mapa je NEUZAVŘE, protože jí
# chybí jeden krok. Recenzent jmenoval TFEB ↔ lysosome ↔ mTORC1 – a má pravdu,
# že tam smyčka je. Detekce cyklů ji nenajde, protože krok "více lysosomů →
# jiná regulace mTORC1" v korpusu nemáme. Mlčet o tom by znamenalo tvrdit,
# že smyčka neexistuje.
OPEN_LOOPS = [
 {"name": "mTORC1 → autophagy → nutrient supply → mTORC1",
  "missing_step": "autophagy → intracellular amino-acid pool",
  "why": "Autophagy regenerates amino acids, which feed the very sensors that control mTORC1. This is a real homeostatic loop and the Atlas holds both halves as separate arms, but no curated edge for autophagy-derived amino acids re-entering the sensing machinery."},
 # POZOR: smyčka TFEB → lysosomal biogenesis → mTORC1 tady BYLA jako otevřená.
 # Po zakurátorování SET2011/SET2012 se uzavřela (viz detekované loops), takže
 # se ze seznamu odebrala. Nechat ji tam by znamenalo, že model tvrdí, že
 # neumí uzavřít smyčku, kterou právě uzavřel – validátor to teď hlídá.
]





# ---------------------------------------------------------------------------
# 3e. Organelle build-out – nové hrany (review pass 2).
#
# Formát je záměrně stejný jako u migrovaných hran, aby prošly týmiž
# branami. KAŽDÁ má citaci z korpusu; hrana bez citace se nepřidává, i když
# by ji recenzent chtěl (viz Golgi v OPEN_LOCALISATIONS).
#
# ("id", src, tgt, effect, type, comp, ts, direct, mc, hr, cons,
#  evidence_kind, species, [sids], mechanism, teaching_note, boundary)
# ---------------------------------------------------------------------------
# ---- audit 2026-09-04: conflicting evidence is now carried, not discarded.
# evidence.conflicting was hardcoded to [] for all 119 interactions, which
# silently deleted the one thing this Atlas claims to model that others do not.
# Seeded from the two cases found by external audit; extend as they are found,
# or wire to a Conflicting_Studies field on the Relations table.
# CONFLICTING -- ZRUŠENO 2026-09-30. Hrany žijí jen v Airtable Relations
# (pole: Conflicting_Studies). Čte se přes relations_bake.py -> atlas_data/relations_baked.json.

# EXTRA_EDGES -- ZRUŠENO 2026-09-30. Hrany žijí jen v Airtable Relations
# (pole: celé záznamy (21 hran přeneseno 2026-09-30)). Čte se přes relations_bake.py -> atlas_data/relations_baked.json.



# Lokality aktivace mTOR, o kterých literatura mluví, ale KORPUS je neunese.
# Recenzent chtěl Golgi. GOB2016 je review o transportérech, které "označují
# místo" aktivace; BOU2020 (BRET biosenzor AIMTOR) měří mTOR aktivitu v
# cytosolu, na lysosomu, v jádře a u mitochondrií – Golgi mezi nimi NENÍ.
# Nakreslit Golgi hranu by znamenalo tvrdit něco, co citace nedokládá. Místo
# toho se to řekne nahlas jako chybějící citace, ne jako neexistující biologie.
OPEN_LOCALISATIONS = [
 {"name": "Golgi as an mTORC1 activation site",
  "status": "not represented – no curated paper",
  "why": "Proposed in the amino-acid-transporter literature (GOB2016 reviews the idea that intracellular transporters mark the site of activation), but no study in this corpus demonstrates mTORC1 activation at the Golgi. Adding the edge would assert more than the citations support. Closing this gap needs a primary paper in the corpus, at which point the edge appears automatically."},
 {"name": "Subcellular mTOR pools beyond the lysosome",
  "status": "partially represented",
  "why": "Live BRET biosensor imaging (BOU2020) reads mTOR activity separately in cytosol, on the lysosomal surface, in the nucleus and near mitochondria – so mTOR signalling is measurably not one pool. This map represents the peri-mitochondrial case concretely (mTORC2 at MAM, BET2013) and the nuclear case functionally (mTORC1 to YY1–PGC-1α), but it does not yet model the pools as separate entities with their own activity states."},
]



# ---------------------------------------------------------------------------
# 3f. Researcher's Journey – společná šablona pro VŠECHNY guided routes.
#
# Recenzent: Reactome a KEGG ukazují, CO víme. Guided Routes mají učit, JAK
# o mTOR přemýšlet – a to je místo, kde se Atlas skutečně odlišuje. Aby to
# nebyl jen jiný výřez dráhy, musí každá trasa odpovídat na JEDNU otázku a
# nést stejnou hlavičku:
#
#   question     – biologická otázka, na kterou trasa odpovídá
#   breakthrough – práce, která ji zlomila (nebo přiznaná syntéza)
#   evidence     – jaké experimenty odpověď unesou
#   unknowns     – co zůstává nevyřešené
#
# POZOR na tlak k fabulaci: některé trasy JEDNU zlomovou práci nemají.
# Kdyby schéma jednu vyžadovalo, někdo nakonec nominuje práci, která si to
# nezaslouží. Proto existuje legitimní varianta {"synthesis": [...]}, kterou
# validátor bere jako úplnou – stejná disciplína jako deklarovaná mezera
# u Golgi místo nakreslené hrany.
#
# Titul je OTÁZKA, ne území. "The mTORC2 branch" je výřez; "Why does one
# kinase need two complexes?" je otázka.
# ---------------------------------------------------------------------------
ROUTE_JOURNEY = {
 "exercise": {
  "title": "Why does lifting something heavy make a muscle bigger?",
  "question": "Muscle grows in response to mechanical load, not to a hormone injection. Somewhere a physical force has to become a molecular signal, and then a decision to build. Where does that conversion happen, and how do we know mTORC1 is required rather than merely present?",
  "breakthrough": {"sid": "DRU2009",
    "why": "Did the interruption experiment in people. Human volunteers were given rapamycin before resistance exercise, and the contraction-induced rise in muscle protein synthesis was blocked. Almost everything else in this Atlas is inferred from cells or mice; this placed mTORC1 causally inside a human physiological response. BOD2001 had established the pathway's necessity in rodent muscle, but necessity in a person is a different claim."},
  "evidence": "A human interventional study for the causal step, rodent genetics and myotube work for the upstream route. This is the only route in the section whose terminal claim carries human-relevance ESTABLISHED rather than plausible – worth noticing, because it is rare here and it is what an interruption experiment buys you.",
  "unknowns": "How mechanical force is actually transduced into mTORC1 activation is not settled: load reaches mTORC1 partly independently of IGF-1, and the mechanosensor has not been identified. Whether the same dependence holds in ageing muscle, where anabolic resistance appears, is untested. And mTORC1 activation is necessary but NOT sufficient – constitutive activation alone does not build healthy muscle.",
 },
 "fasting": {
  "title": "What happens, and in what order, when you stop eating?",
  "question": "Fasting is usually described as a state – fed or fasted. But a cell does not switch states; it runs a sequence, and the parts of that sequence operate on wildly different timescales. Which responses have happened after a few seconds, and which are still hours away?",
  "breakthrough": {"synthesis": ["EGA2010", "MAR2012", "SET2012", "GWI2008"],
    "why": "This is an order-of-events question, so no single paper answers it – the sequence had to be assembled from papers about different steps. GWI2008 and EGA2010 supplied the fast arm (AMPK to Raptor, AMPK to ULK1, seconds to minutes). MAR2012 supplied the mTORC1-to-TFEB step that gates the slow arm. SET2012 supplied the return leg, lysosome to nucleus and back. Read together they give a timeline; read separately none of them is about timing at all."},
  "evidence": "Direct biochemistry in cells for the ordering, and its timescale grading comes from the curated timescale field on each interaction rather than from any single time-course experiment. The organism-level end of the route rests on rhesus and mouse data (MAT2017, SOL2014) plus one human safety trial (ROM2016).",
  "unknowns": "The ORDER here is defensible; the CLOCK is not. This map holds six ordinal timescale buckets, not rate constants, so it can say what has happened by now but never how fast. Human fasting time-courses for these molecular events do not exist in this corpus. And SOL2014 raises the harder question of whether calories or macronutrient ratio is even the right variable.",
 },
 "open": {
  "title": "Where does this pathway stop being known?",
  "question": "Every pathway diagram looks equally confident everywhere. This one is not, and it records where. So: which parts of mTOR biology are contested between labs, which have a mechanism nobody has resolved, and which have never been tested in a human at all?",
  "breakthrough": {"synthesis": ["WOL2015", "SAX2015", "HOW2017", "SAR2006"],
    "why": "There is no breakthrough here by construction – this route is about the absence of one. The papers listed are instead the clearest examples of live disagreement: WOL2015 and SAX2015 established Sestrin2 as a leucine sensor, which competes with the LARS model that this map still carries as contested; HOW2017 showed metformin's mTORC1 inhibition is dose-dependent and mechanistically plural, undermining the tidy AMPK story; SAR2006 in cell lines and LAM2012 in mouse liver show that chronic rapamycin disrupts mTORC2, while how much that matters in people is still argued. Each is good work whose conclusion the field has not closed."},
  "evidence": "Deliberately the weakest evidence in the Atlas, and the grading is the point: 7 interactions are typed contested, 8 carry low mechanistic confidence, 13 have human relevance untested. Those counts are computed from the model, so this route cannot drift from the data it is complaining about.",
  "unknowns": "That is the entire route. But the meta-unknown is worth stating: gaps here are computed against THIS corpus, not against the literature. A gap may mean nobody has done the experiment, or it may mean the Atlas has not yet found the paper – and an external review already caught one case of the second kind. Treat every step as a hypothesis about the evidence, testable by finding the study that closes it.",
 },
 "cancer": {
  "title": "Why does a pathway we understand this well only half work as a drug target?",
  "question": "mTORC1 is one of the best-characterised growth pathways in biology, and there are licensed drugs that inhibit it. Yet outside a few genotypes the clinical results are modest: progression delayed, survival rarely extended. If the mechanism is right, why is the treatment only partly right?",
  "breakthrough": {"synthesis": ["ORE2006", "CAR2008", "ROD2011", "THO2009"],
    "why": "No single paper explains this, and the four that do are better read together because each found a different escape. ORE2006 showed mTOR inhibition raises receptor tyrosine kinase signalling; CAR2008 showed it activates MAPK PI3K-dependently; ROD2011 showed mTOR kinase inhibition produces biphasic Akt regulation through feedback. THO2009 supplied the fourth answer from the drug side – the inhibition was never complete to begin with. Together they say the pathway does not simply switch off when you inhibit it; it reroutes."},
  "evidence": "Cell-line pharmacology and biochemistry for the escape mechanisms; H – randomised trials – for the clinical outcomes; one phase 1 trial (SCH2025, 2025) for the newest drug class. Note the asymmetry that runs through this route: the mechanism is cell-line evidence, the disappointment is human evidence.",
  "unknowns": "Which tumours depend on mTOR remains largely unpredictable from genotype – the single largest open problem here. Whether closing the 4E-BP1 escape translates into survival benefit is exactly what the bi-steric trials are testing and is not yet answered. And why rapalogs delay progression without clearly extending overall survival in several indications has no accepted explanation, with the feedback arms as leading suspects.",
 },
 "aa": {
  "title": "How does a cell know it has enough raw material to grow?",
  "question": "A cell cannot start building unless the amino acids are actually present. But amino acids are small molecules with no receptor on the cell surface – so how does the cell measure something it cannot bind from outside?",
  "breakthrough": {"sid": "SAN2010",
    "why": "Reframed nutrient sensing from a chemistry problem into a GEOGRAPHY problem. The Rag–Ragulator complex does not switch mTORC1 on; it moves mTORC1 to the lysosomal surface. Everything about amino-acid sensing turned out to be about location, which is why the answer had eluded people looking for a classical receptor. SAN2008 had already shown the Rags carry the amino-acid signal; this paper said where."},
  "evidence": "Structural biology and genetic epistasis in human cell lines, plus imaging of mTORC1 translocation. Cell-line work throughout – this arm has no human genetic or clinical evidence in this corpus, which is why almost every step is graded human-relevance *plausible* rather than established.",
  "unknowns": "How GATOR2 actually inhibits GATOR1 catalytically is still unresolved. Whether Sestrin2's ~20 µM leucine affinity is the operating setpoint in real tissue is untested. And the LARS and glutamine arms remain contested – reproduced in some labs, not others.",
 },
 "gf": {
  "title": "How does a cell learn that it is allowed to grow?",
  "question": "Raw material is not permission. A cell in a tissue must not grow just because food is available – it has to be told by the organism that growth is wanted. How does a hormone signal at the cell surface reach a kinase on the lysosome?",
  "breakthrough": {"synthesis": ["INO2002", "INOK2003"],
    "why": "No single paper answers this one, and pretending otherwise would misrepresent the history. INO2002 showed Akt phosphorylates and inhibits TSC2 – the permission signal arriving. INOK2003, a year later, showed Rheb is the direct target of TSC2's GAP activity – the switch being thrown. The question needed both halves, and neither is complete alone."},
  "evidence": "Direct biochemistry and genetic epistasis in mammalian cells, with the TSC arm additionally supported by human disease genetics (tuberous sclerosis complex is the one place this pathway's causality is established in people).",
  "unknowns": "How much of TSC regulation is phosphorylation changing its activity versus relocation changing its access to Rheb. Which endomembrane pool of Rheb supplies the activating signal. And the relative strength of the two feedback arms (S6K1→IRS-1, mTORC1→Grb10) in any given tissue.",
 },
 "rapa": {
  "title": "Why doesn't rapamycin switch mTOR off completely?",
  "question": "Rapamycin was the drug that discovered this pathway, and for a decade it was treated as *the* mTOR inhibitor. But cells treated with rapamycin keep doing some of the things mTORC1 drives. Why does a drug that clearly hits mTOR fail to stop all of its outputs?",
  "breakthrough": {"sid": "THO2009",
    "why": "Built an ATP-competitive inhibitor and used it as a ruler. Comparing it against rapamycin exposed a whole class of rapamycin-RESISTANT mTORC1 outputs – most importantly 4E-BP1 phosphorylation, which rapamycin barely touches while collapsing S6K1. That single comparison explained a decade of confusing results and launched the second-generation inhibitor programme that reached trials by 2025."},
  "evidence": "Pharmacological comparison plus biochemistry in cell lines, with the structural basis (FKBP12–rapamycin occluding the substrate channel rather than the active site) resolved separately. The clinical consequence is supported by trial evidence; the mechanism is not human data.",
  "unknowns": "Whether chronic rapamycin genuinely disrupts mTORC2 is contested and appears to be cell-type and duration dependent. How much the 4E-BP escape matters in any particular tumour is unresolved, which is precisely the question bi-steric inhibitors are being trialled to answer.",
 },
 "out": {
  "title": "What does a cell actually do when mTORC1 fires?",
  "question": "'Promotes growth' is not a mechanism. If mTORC1 switching on has consequences, those consequences are specific molecules being made and specific processes being stopped. Which ones – and does mTORC1 turn everything up equally?",
  "breakthrough": {"sid": "HSI2012",
    "why": "Answered the second half, which almost everyone had assumed away. Ribosome profiling showed mTORC1 does not raise translation uniformly – it selectively promotes a specific class of transcripts. 'mTORC1 increases protein synthesis' turned out to be a summary that hides the actual biology, which is transcript choice."},
  "evidence": "Ribosome profiling and biochemistry in cancer cell lines for the selectivity; genetic knockouts in mice for the phenotypic arms (muscle, mitochondria, lipid). The output-to-phenotype steps are the weakest links in the route, and they are graded accordingly.",
  "unknowns": "How much of the mTOR-responsive phosphoproteome is functionally relevant rather than incidental. Which outputs matter for which phenotype – the map draws mTORC1 to muscle growth and to longevity, but these are not the same kind of claim and the second has no human evidence at all.",
 },
 "energy": {
  "title": "How does a cell decide it cannot afford to grow?",
  "question": "Building is expensive. A cell that starts a growth programme it cannot fuel will damage itself. So there must be a way for energy status to override a growth instruction that has already been given – and it has to work even when the usual brake is broken.",
  "breakthrough": {"sid": "GWI2008",
    "why": "Found the arm nobody expected: AMPK phosphorylates Raptor directly, inhibiting mTORC1 without going through the TSC complex at all. That explained why TSC2-null cells still shut down under energy stress, and it established that this pathway has redundant brakes rather than one master switch."},
  "evidence": "Direct biochemistry and genetic epistasis in mammalian cells, with the two AMPK arms separable using TSC-null lines. LKB1 dependence means cell lines lacking LKB1 cannot mount the response at all – a boundary condition that invalidates naive comparison across cell types.",
  "unknowns": "The relative weight of the TSC2 arm versus the Raptor arm in intact tissue is not resolved, and it is cell-type dependent. The metformin route is genuinely contested: several mechanisms are proposed, and the concentrations used in vitro often exceed what clinical dosing achieves.",
 },
 "mtorc2": {
  "title": "Why does one kinase need two complexes?",
  "question": "mTOR is a single protein, yet it does two jobs that respond to different signals, sit in different places, and have different drug sensitivities. Why did evolution not simply use two kinases – and how do you study one of two jobs when your only tool inhibits the other?",
  "breakthrough": {"sid": "SAR2004",
    "why": "Identified Rictor and, with it, a second mTOR complex that is raptor-independent and – decisively – rapamycin-insensitive. That last property is what made mTORC2 studiable at all: it gave the field a way to separate the two jobs experimentally, using the very drug that had previously hidden one of them."},
  "evidence": "Biochemistry and complex purification in mammalian cells, then genetic dissection in knockout mice (Rictor and mLST8 loss abolishes signalling to Akt and PKCα while sparing S6K1). The mouse genetics is the strongest evidence in this route.",
  "unknowns": "Whether prolonged rapamycin disrupts mTORC2 assembly is contested. The mTORC2-to-insulin-resistance link rests on mouse data, and in humans the relative contributions of mTORC2 loss, S6K1–IRS-1 feedback and direct β-cell effects are unresolved.",
 },
 "clin": {
  "title": "Does any of this actually help a patient?",
  "question": "Forty years of mechanism is not a treatment. If mTORC1 drives growth and we have drugs that inhibit it, where does that convert into benefit for a person – and where does it conspicuously fail to?",
  "breakthrough": {"synthesis": ["HUD2007", "MOT2008", "MCC2011", "LEE2024"],
    "why": "There is no breakthrough paper here and claiming one would be dishonest – clinical translation is not a discovery, it is an accumulation. HUD2007 brought the first mTOR inhibitor approval in renal cancer; MOT2008 established everolimus in the same disease; MCC2011 showed sirolimus stabilises lung function in LAM, the cleanest mechanism-to-benefit case in the pathway; LEE2024 is the systematic review that assembles what human rapamycin data actually supports.",
    },
  "evidence": "Randomised controlled trials and one systematic review – the only route in this section built primarily on human evidence (S and H – synthesis of human data and human studies). Note what that buys and what it does not: trials establish that the drug changes an outcome, not that the mechanism drawn upstream is the reason.",
  "unknowns": "Which tumours depend on mTOR remains largely unpredictable from genotype. There is no human lifespan data of any kind. And the pattern that rapalogs delay progression without clearly extending overall survival in several indications is unexplained – the feedback loops are the leading suspect.",
 },
}



# ---------------------------------------------------------------------------
# 3g. Nové trasy (Fáze 5+).
#
# Trasy migrované z ATLAS_ROUTES pokrývají mechanismus. Tahle je první
# postavená od začátku a odpovídá na otázku, kterou žádná z nich neřeší:
# proč dráha, kterou umíme popsat do detailu, dává v klinice jen částečné
# výsledky. Vede od genetické léze přes lék až k tomu, jak nádor uteče —
# a končí molekulou, která je v korpusu nejnovější evidencí (SCH2025, 2025).
#
# Formát: {"id", "territory", "story", "interactions", "spine"}. Journey a
# kroky se doplňují v ROUTE_JOURNEY / ROUTE_STEPS jako u ostatních, takže
# nová trasa prochází týmiž branami.
# ---------------------------------------------------------------------------
NEW_ROUTES = [
 {"id": "exercise",
  "territory": "Mechanical load → IGF-1/Akt → mTORC1 → translation → hypertrophy",
  "story": "The one route in this section whose final claim was tested by interrupting it in living people. Follow mechanical load to muscle growth, and notice where the evidence stops being inference.",
  "interactions": ["LOAD-MTORC1", "IGF1-PI3K", "PI3K-AKT", "AKT-TSC", "TSC-RHEB", "RHEB-MTORC1",
                   "MTORC1-S6K1", "MTORC1-4EBP1", "4EBP1-EIF4E", "EIF4E-TRANSL",
                   "S6K1-PDCD4", "PDCD4-TRANSL", "TRANSL-MUSCLE", "EVE-MTORC1"],
  "spine": ["LOAD-MTORC1", "IGF1-PI3K", "PI3K-AKT", "AKT-TSC", "TSC-RHEB", "RHEB-MTORC1",
            "MTORC1-4EBP1", "4EBP1-EIF4E", "EIF4E-TRANSL", "TRANSL-MUSCLE"]},

 {"id": "fasting",
  "territory": "Nutrient withdrawal → AMPK → mTORC1 off → autophagy → lysosomal renewal",
  "story": "Not a clock but an ORDER. Set the BY TIME control to seconds, then minutes, then hours, and watch which parts of the response have happened yet. The pathway does not switch state – it unfolds.",
  "interactions": ["CR-MTORC1", "LEU-SESN2", "SESN2-GATOR2", "STRESS-AMPK", "AMPK-TSC",
                   "TSC-RHEB", "RHEB-MTORC1", "AMPK-MTORC1", "MTORC1-ULK1", "AMPK-ULK1",
                   "ULK1-AUTOPHAGY", "ULK1-AMPK", "MTORC1-TFEB", "TFEB-AUTOPHAGY",
                   "TFEB-LYSOBIO", "LYSOBIO-LYSOSOME", "AMPK-MITOPHAGY", "CR-LONGEVITY"],
  "spine": ["CR-MTORC1", "STRESS-AMPK", "AMPK-TSC", "RHEB-MTORC1", "MTORC1-ULK1",
            "AMPK-ULK1", "ULK1-AUTOPHAGY", "MTORC1-TFEB", "TFEB-AUTOPHAGY",
            "TFEB-LYSOBIO", "AMPK-MITOPHAGY", "CR-LONGEVITY"]},

 {"id": "open",
  "territory": "The contested, the unresolved and the untested",
  "story": "Every other route shows you what the Atlas holds. This one walks the weakest links on purpose: the interactions this Atlas grades as contested, the ones carrying low mechanistic confidence, and the ones with no human evidence in this corpus. Read it as a guide to reading evidence, not as a confession – and read it as a statement about what has been curated here, not about what the field has done.",
  "interactions": ["LEU-SESN2", "LEU-LARS", "LARS-RAG", "GLN-MTORC1-ARF1", "GATOR2-GATOR1",
                   "METFORMIN-AMPK", "METFORMIN-MTORC1", "RAPA-MTORC2", "MTORC1-RCC",
                   "MTORC1-LONGEVITY", "RAPA-LONGEVITY", "EVE-IMMUNE", "SALR-MTORC1",
                   "ISR-SALR", "ROS-MTORC1", "S6K1-LONGEVITY"],
  "spine": ["LEU-LARS", "LARS-RAG", "GLN-MTORC1-ARF1", "GATOR2-GATOR1", "METFORMIN-AMPK",
            "METFORMIN-MTORC1", "RAPA-MTORC2", "MTORC1-RCC", "MTORC1-LONGEVITY",
            "RAPA-LONGEVITY", "EVE-IMMUNE", "S6K1-LONGEVITY"]},
 {"id": "cancer",
  "territory": "Oncogenic activation → rapalog → escape → next generation",
  "story": "Follow one tumour genotype from the lesion that creates it, through the drug that was aimed at it, to the two feedback arms that undo the drug, and on to the molecules designed against that failure. This is the route where mechanism meets the clinic and the clinic answers back.",
  "interactions": ["PTEN-PI3K", "PI3K-AKT", "AKT-TSC", "TSC-RHEB", "RHEB-MTORC1",
                   "MTORC1-S6K1", "MTORC1-4EBP1", "4EBP1-EIF4E", "EIF4E-TRANSL",
                   "MTORC1-TUMOR", "EVE-MTORC1", "EVE-BREAST", "MTORC1-PROSTATE",
                   "S6K1-IRS1", "IRS1-PI3K", "MTORC1-MAPK", "ERK-TSC",
                   "TORIN-MTORC1", "TORIN-MTORC2", "BISTERIC-MTORC1"],
  "spine": ["PTEN-PI3K", "PI3K-AKT", "AKT-TSC", "TSC-RHEB", "RHEB-MTORC1",
            "MTORC1-TUMOR", "EVE-MTORC1", "S6K1-IRS1", "IRS1-PI3K",
            "MTORC1-MAPK", "TORIN-MTORC1", "BISTERIC-MTORC1"]},
]


def read_atlas_array(html, name):
    i = html.find("const %s = [" % name)
    if i < 0:
        raise SystemExit("missing %s in index.html" % name)
    seg = html[i + len("const %s = " % name):]
    return json.loads(seg[:seg.find("];") + 1])


def layout(nodes_by_comp, edges, comp_order):
    """Kompartmentové pásy + barycentrické řazení.

    Nahrazuje ruční route.bows / route.ctrl. Deterministické: stejný vstup
    dá vždy stejné souřadnice, takže diff modelu je čitelný.
    """
    LANE_H = 132
    X0, XW = 90, 1420
    order = {c: list(nodes_by_comp.get(c, [])) for c in comp_order}
    adj = {}
    for e in edges:
        adj.setdefault(e["source"], []).append(e["target"])
        adj.setdefault(e["target"], []).append(e["source"])

    pos = {}
    for ci, c in enumerate(comp_order):
        for i, n in enumerate(order[c]):
            pos[n] = i

    for sweep in range(24):
        for c in comp_order:
            row = order[c]
            if len(row) < 2:
                continue
            bary = {}
            for n in row:
                nb = [pos[m] for m in adj.get(n, []) if m in pos and m not in row]
                bary[n] = sum(nb) / len(nb) if nb else pos[n]
            row.sort(key=lambda n: (bary[n], n))
            for i, n in enumerate(row):
                pos[n] = i

    coords = {}
    y = 74
    bands = []
    for c in comp_order:
        row = order[c]
        n = max(1, len(row))
        rows = 1 if n <= 8 else (2 if n <= 16 else 3)
        per = -(-n // rows)
        h = LANE_H if rows == 1 else LANE_H + (rows - 1) * 62
        for i, name in enumerate(row):
            r, k = divmod(i, per)
            cnt = min(per, n - r * per)
            step = XW / (cnt + 1)
            coords[name] = {
                "x": round(X0 + step * (k + 1), 1),
                "y": round(y + 34 + r * 62, 1),
            }
        bands.append({"compartment": c, "y": round(y, 1), "h": round(h, 1), "rows": rows})
        y += h
    return coords, bands, round(y + 24, 1)


def main():
    html = open(os.path.join(ROOT, "index.html"), encoding="utf-8").read()
    # Hrany: jediný zdroj pravdy je Airtable Relations (od 2026-09-30), sem
    # přicházejí přes relations_bake.py -> atlas_data/relations_baked.json.
    # Jen publikované (Published = true, Status != Rejected).
    import relations_bake
    old_edges = relations_bake.load(published_only=True)
    old_routes = read_atlas_array(html, "ATLAS_ROUTES")
    studies = json.load(open(os.path.join(ROOT, "atlas_data", "studies_baked.json"), encoding="utf-8"))
    known_sids = {s.get("sid") for s in studies}
    sid_tier = {s.get("sid"): (s.get("tier") or "").strip().upper()[:1] for s in studies}

    comp_order = [c["id"] for c in COMPARTMENTS]
    problems = []
    downgrades = []

    # ---- uzly ------------------------------------------------------------
    endpoints = set()
    for e in old_edges:
        endpoints.add(e["s"]); endpoints.add(e["t"])
    for name in endpoints:
        if name not in NODES:
            problems.append("node not curated: %s" % name)

    nodes = []
    by_comp = {}
    for name in sorted(endpoints):
        if name not in NODES:
            continue
        comp, cls, beg, stu, res = NODES[name]
        nodes.append({
            "id": name, "label": name, "cls": cls, "compartment": comp,
            "explain": {"beginner": beg, "student": stu, "research": res},
            "context_roles": CONTEXT_ROLES.get(name, []),
        })
        by_comp.setdefault(comp, []).append(name)

    # ---- hrany -----------------------------------------------------------
    interactions = []
    for e in old_edges:
        typ, comp, ts, direct, mc, hr, cons = (e["type"], e["comp"], e["ts"], e["directness"],
                                               e["mc"], e["hr"], e["cons"])
        bad = [s for s in e["st"] + e["cf"] if s not in known_sids]
        if bad:
            problems.append("edge %s cites unknown SID(s) %s" % (e["id"], bad))

        # --- lidská relevance se NEUVÁDÍ, ODVOZUJE SE ----------------------
        # Nález F4 externí recenze: pravidlo pro sílu tvrzení bylo napsáno
        # jinak, než bylo použito. Řešení není opravit jednotlivé případy,
        # ale odebrat kurátorovi možnost tvrdit víc, než evidence unese.
        # Kurátor smí lidskou relevanci jen SNÍŽIT (např. "untested" u
        # myších lifespan dat), nikdy zvýšit nad to, co dovolují citace.
        # Airtable pole Human_Relevance_Claim je proto NÁROK, ne výsledek.
        tiers_here = {sid_tier.get(s, "?") for s in e["st"]}
        human_sp = in_human_species(e["sp"])  # A11: lidské buňky nestačí
        ceiling = "established" if (tiers_here & {"A", "B"}) or human_sp else "plausible"
        rank = {"untested": 0, "plausible": 1, "established": 2}
        if rank[hr] > rank[ceiling]:
            downgrades.append("%s: human_relevance %s -> %s (cited tiers %s, species %r)"
                              % (e["id"], hr, ceiling, "".join(sorted(tiers_here)), e["sp"]))
            hr = ceiling
        interactions.append({
            "id": e["id"],
            "source": e["s"], "target": e["t"],
            "type": typ,
            "effect": e["sign"],
            "compartment": comp,
            "directness": direct,
            "timescale": ts,
            "species": [x.strip() for x in re.split(r"[;,]", e["sp"]) if x.strip()],
            "mechanism": e["mech"],
            "mechanism_beginner": e["mech_beginner"],
            "teaching_note": e["teach"],
            "boundary": e["ctx"],
            # Nález recenze č. 1: kontextová závislost patří na hranu, ne jen
            # do globálního disclaimeru.
            "context_note": e["context"],
            "note": e["note"],
            "evidence": {
                "kind": e["dir"],
                "tiers": e["tiers"],
                "best_tier": e["tier"],
                "supporting": e["st"],
                "conflicting": e["cf"],
            },
            "confidence": {
                "mechanistic": mc,
                "human_relevance": hr,
                "consensus": cons,
            },
            # 2026-10-03: no fallback date or reviewer any more. Until then every
            # edge claimed "reviewed 2026-07-29 by the curation team", including
            # edges created that day that nobody had reviewed (Status=Proposed,
            # Reviewed_By empty). Only Airtable Reviewed_On/Reviewed_By count.
            "review": {"reviewer": e.get("reviewed_by") or None,
                       "reviewed": e.get("reviewed_on") or None,
                       "updated": e.get("reviewed_on") or None,
                       "status": e.get("status") or "Proposed"},
            # 2026-10-09: "Checked by" = vedec mimo kuratorsky tym, jen se
            # souhlasem (Check_Consent v Airtable). None = nikdo zvenku.
            "checked": e.get("checked") or None,
        })

    ix = {i["id"]: i for i in interactions}

    # -----------------------------------------------------------------
    # Nález recenze č. 2: uzly vypadaly stejně důležitě.
    #
    # Síla důkazů u uzlu se NEKURÁTORUJE, ODVOZUJE se z citací hran, které se
    # ho dotýkají. Důležité: je to počet studií V TOMHLE KORPUSU, ne v
    # literatuře – Sestrin2 má ve světě stovky prací, tady jich má tolik,
    # kolik jich kurátor zařadil. Label to musí říkat, jinak je to lež.
    # Stejně tak "first cited" není rok objevu, ale nejstarší citovaná práce.
    # -----------------------------------------------------------------
    sid_year = {x.get("sid"): x.get("year") for x in studies}
    TIER_RANK = {"A": 0, "B": 1, "C": 2, "D": 3}
    for n in nodes:
        sids, types, effects = set(), set(), set()
        deg_in = deg_out = 0
        for i in interactions:
            if i["source"] != n["id"] and i["target"] != n["id"]:
                continue
            sids.update(i["evidence"]["supporting"])
            types.add(i["type"]); effects.add(i["effect"])
            if i["source"] == n["id"]:
                deg_out += 1
            else:
                deg_in += 1
        years = [sid_year.get(x) for x in sids]
        years = [int(y) for y in years if str(y).isdigit()]
        tiers = sorted({sid_tier.get(x, "D") for x in sids}, key=lambda t: TIER_RANK.get(t, 9))
        n["evidence"] = {
            "studies_in_corpus": len(sids),
            "best_tier": tiers[0] if tiers else None,
            "tiers": tiers,
            "first_cited_year": min(years) if years else None,
            "latest_cited_year": max(years) if years else None,
            "interactions_in": deg_in,
            "interactions_out": deg_out,
            "distinct_mechanisms": sorted(types),
            "caveat": "Counts studies in this curated corpus, not in the literature. "
                      "'First cited' is the earliest paper cited here, not the year of discovery.",
        }

    # -----------------------------------------------------------------
    # Nález recenze č. 4: zpětné vazby byly v datech, ale nikde nepojmenované.
    # Cykly se hledají strojově, aby nemohl vzniknout rozpor mezi seznamem
    # smyček a hranami, ze kterých se skládají.
    # -----------------------------------------------------------------
    adj = {}
    for i in interactions:
        adj.setdefault(i["source"], []).append((i["target"], i["id"]))
    raw = []

    def walk(start, node, path, eids, depth):
        if depth > 5:
            return
        for tgt, eid in adj.get(node, []):
            if tgt == start and len(path) >= 2:
                raw.append((path + [tgt], eids + [eid]))
            elif tgt not in path and tgt > start:
                walk(start, tgt, path + [tgt], eids + [eid], depth + 1)

    for nm in sorted(adj):
        walk(nm, nm, [nm], [], 0)
    # Graf obsahuje 10 cyklů, ale jen ~4 odlišné biologické mechanismy —
    # tentýž zpětnovazebný krok se objeví v několika delších cestách. Ukázat
    # deset smyček se čtyřmi stejnými jmény je šum. Z každého pojmenovaného
    # mechanismu se drží NEJKRATŠÍ cyklus (kanonická forma), nepojmenované
    # se deduplikují podle množiny uzlů.
    seen_cyc, loops, claimed = set(), [], set()
    for path, eids in sorted(raw, key=lambda x: (len(x[1]), x[1])):
        key = tuple(sorted(eids))
        if key in seen_cyc:
            continue
        seen_cyc.add(key)
        name, why, sig_hit = " → ".join(path), "", None
        for sig, nm, wy in LOOP_RULES:
            if sig in eids:
                name, why, sig_hit = nm, wy, sig
                break
        if sig_hit:
            if sig_hit in claimed:
                continue                      # už máme kratší verzi
            claimed.add(sig_hit)
        else:
            nk = frozenset(path[:-1])
            if nk in claimed:
                continue
            claimed.add(nk)
        signs = [ix[e]["effect"] for e in eids if e in ix]
        neg = sum(1 for x in signs if x == "inhibits")
        loops.append({
            "id": "loop%02d" % (len(loops) + 1),
            "nodes": path[:-1],
            "interactions": eids,
            "length": len(eids),
            # Parita inhibicí: nepárová = negativní (stabilizující) zpětná
            # vazba, párová = pozitivní (zesilující). Zjednodušení, které se
            # říká nahlas: "required-for" a "recruits" se počítají jako
            # neinhibiční, což je správně, ale parita neváží sílu ramen.
            "sign": "negative" if neg % 2 == 1 else "positive",
            "sign_caveat": "Sign is the parity of inhibitory steps around the loop. "
                           "It says which direction the loop pushes, not how strongly – "
                           "loop strength depends on the relative weight of each arm, "
                           "which is cell-type dependent.",
            "name": name,
            "why": why,
        })

    loop_of = {}
    for lp in loops:
        for eid in lp["interactions"]:
            loop_of.setdefault(eid, []).append(lp["id"])
    for i in interactions:
        i["loops"] = loop_of.get(i["id"], [])

    # Nález recenze: "lysosom by měl být centrální uzel". Místo vizuálního
    # zvýraznění se to spočítá: kolik interakcí se skutečně děje na které
    # membráně. Tvrzení pak nese číslo, ne dojem.
    from collections import Counter as _C
    comp_census = _C(i["compartment"] for i in interactions)
    for c in COMPARTMENTS:
        c["interaction_count"] = comp_census.get(c["id"], 0)
        c["interaction_share"] = round(100.0 * comp_census.get(c["id"], 0) / max(1, len(interactions)), 1)

    # Ostřejší tvrzení: ne "tady se děje nejvíc interakcí" (to vyhrává cytosol),
    # ale "tady se reguluje mTORC1". To je věcný obsah recenzentovy poznámky.
    mt = [i for i in interactions if "mTORC1" in (i["source"], i["target"])]
    mt_lyso = [i for i in mt if i["compartment"] == "lyso"]
    lyso = next(c for c in COMPARTMENTS if c["id"] == "lyso")
    lyso["mtorc1_interactions"] = len(mt)
    lyso["mtorc1_here"] = len(mt_lyso)
    lyso["mtorc1_share"] = round(100.0 * len(mt_lyso) / max(1, len(mt)), 1)

    # Nejostřejší pravdivá formulace: ne "většina interakcí", ale "každý PŘÍMÝ
    # regulátor aktivity mTORC1 působí tady". Výjimka je jen složení komplexu.
    direct_in = [i for i in interactions
                 if i["target"] == "mTORC1" and i["directness"] == "direct"]
    d_lyso = [i for i in direct_in if i["compartment"] == "lyso"]
    d_other = [i for i in direct_in if i["compartment"] != "lyso"]
    lyso["direct_regulators_total"] = len(direct_in)
    lyso["direct_regulators_here"] = len(d_lyso)
    lyso["direct_regulators_elsewhere"] = [
        {"id": i["id"], "type": i["type"], "compartment": i["compartment"]} for i in d_other]
    lyso["headline"] = ("%d of the %d direct inputs to mTORC1 act on this membrane. "
                        "The remainder %s complex assembly, which builds mTORC1 rather than "
                        "regulating it – so every direct regulator of mTORC1 activity in this "
                        "model acts at the lysosome."
                        % (len(d_lyso), len(direct_in),
                           "is" if len(d_other) == 1 else "are"))

    coords, bands, height = layout(by_comp, interactions, comp_order)
    for n in nodes:
        n.update(coords.get(n["id"], {"x": 700, "y": 400}))

    # ---- trasy: migrace 7 stávajících ------------------------------------
    routes = []
    for r in old_routes:
        j = ROUTE_JOURNEY.get(r["id"])
        if not j:
            problems.append("route %s has no Researcher's Journey header" % r["id"])
        routes.append({
            "id": r["id"],
            # Titul je otázka. Staré jméno zůstává jako podtitul, aby se
            # neztratila orientace v dráze.
            "name": (j or {}).get("title", r["name"]),
            "territory": r["name"],
            "journey": j or {},
            "summary": r["sub"],
            "story": r["story"],
            "interactions": r["edges"],
            "spine": r.get("steps", []),
            "steps": ROUTE_STEPS.get(r["id"], []),
        })
    # Nové trasy stejnou cestou jako migrované – jinak by šly obejít branky.
    for nr in NEW_ROUTES:
        j = ROUTE_JOURNEY.get(nr["id"])
        if not j:
            problems.append("new route %s has no Researcher's Journey header" % nr["id"])
        for eid in nr["interactions"] + nr["spine"]:
            if eid not in {e["id"] for e in interactions}:
                problems.append("new route %s references unknown interaction %s" % (nr["id"], eid))
        routes.append({
            "id": nr["id"],
            "name": (j or {}).get("title", nr["id"]),
            "territory": nr["territory"],
            "journey": j or {},
            "summary": nr["story"],
            "story": nr["story"],
            "interactions": nr["interactions"],
            "spine": nr["spine"],
            "steps": ROUTE_STEPS.get(nr["id"], []),
        })

    for rid, steps in ROUTE_STEPS.items():
        route = next((x for x in routes if x["id"] == rid), None)
        if not route:
            problems.append("ROUTE_STEPS for unknown route %s" % rid)
            continue
        for st in steps:
            if st["interaction"] not in {e["id"] for e in interactions}:
                problems.append("route %s step cites unknown interaction %s" % (rid, st["interaction"]))
            if st["interaction"] not in route["interactions"]:
                problems.append("route %s step %s is not in that route's interaction set"
                                % (rid, st["interaction"]))

    model = {
        "meta": {
            "version": MODEL_VERSION,
            "generated": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "curator": CURATOR,
            "license": "CC BY 4.0",
            "source_of_truth": "pathway/model.json (generated by build_pathway_model.py)",
            "canvas": {"w": 1600, "h": height},
            "counts": {"nodes": len(nodes), "interactions": len(interactions),
                       "routes": len(routes), "loops": len(loops)},
            "corpus_caveat": "Node study counts are counts within this curated corpus of "
                             "%d studies, not within the literature." % len(studies),
            "vocab": {
                "type": sorted({i["type"] for i in interactions}),
                "effect": sorted({i["effect"] for i in interactions}),
                "timescale": ["seconds", "minutes", "hours", "days", "chronic", "constitutive"],
                "directness": ["direct", "indirect", "unresolved"],
                "mechanistic": ["high", "medium", "low"],
                "human_relevance": ["established", "plausible", "untested"],
                "consensus": ["established", "emerging", "contested"],
                "loop_sign": ["negative", "positive"],
            },
        },
        "compartments": COMPARTMENTS,
        "bands": bands,
        "nodes": nodes,
        "interactions": interactions,
        "routes": routes,
        "loops": loops,
        "open_loops": OPEN_LOOPS,
        "open_localisations": OPEN_LOCALISATIONS,
    }

    os.makedirs(OUT_DIR, exist_ok=True)
    with open(OUT, "w", encoding="utf-8", newline="\n") as f:
        json.dump(model, f, ensure_ascii=False, indent=1)
        f.flush(); os.fsync(f.fileno())

    print("wrote %s" % OUT)
    print("  nodes        %d" % len(nodes))
    print("  interactions %d  (was %d)" % (len(interactions), len(old_edges)))
    print("  routes       %d" % len(routes))
    print("  canvas h     %s" % height)
    if downgrades:
        print("\nhuman_relevance auto-downgraded to match the cited evidence (%d):" % len(downgrades))
        for d in downgrades:
            print("  ↓", d)
    if problems:
        print("\nPROBLEMS (%d):" % len(problems))
        for p in problems:
            print("  -", p)
        return 1
    print("\nno problems")
    return 0


if __name__ == "__main__":
    sys.exit(main())
