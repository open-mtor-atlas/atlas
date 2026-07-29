#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
build_pathway_model.py — Pathway & Mechanism redesign, Fáze 1.

PROČ TOHLE EXISTUJE
-------------------
Do dneška měl Atlas DVĚ nezávislé reprezentace téže dráhy:

  1. MAP_NODES / MAP_CORE_EDGES / MAP_PERIPH_EDGES  (ruční x/y, "Entity Map")
  2. ATLAS_EDGES / ATLAS_ROUTES                     (kurátorované hrany + 7 tras)

Nikdo je nedržel v synchronu. Entity Map kreslila 42 core hran, Mechanism
Explorer 100 — a část "hran" v Entity Map nebyla biologie vůbec, jen
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
    podpůrné i konfliktní studie, a — nově — DVĚ oddělené jistoty:
    mechanistickou důvěru a lidskou relevanci. Tier studie není totéž
    co důvěra v mechanismus (nález F4 externí recenze).
  * Layout se POČÍTÁ (kompartmentové pásy + barycentrické řazení), ne ladí
    ručně. Staré route.bows / route.ctrl byly ruční konstanty s komentářem
    "regenerate them if you move a node" — to je dluh, ne architektura.

VSTUP   index.html  (ATLAS_EDGES, ATLAS_ROUTES — migrace stávající kurace)
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
CURATOR = "Open mTOR Atlas curation team"
REVIEW_DATE = "2026-07-29"

# ---------------------------------------------------------------------------
# 1. Kompartmenty — prostorová osnova.
#
# Pořadí = pořadí pásů shora dolů. `physical: false` znamená "tohle NENÍ
# místo v buňce" — vstupy a fenotypy dostanou jiný vizuální jazyk, aby
# nikdo nezískal dojem, že "Longevity" je organela.
# ---------------------------------------------------------------------------
COMPARTMENTS = [
    {
        "id": "input", "name": "Inputs", "short": "IN", "physical": False,
        "blurb": "Nutrients, hormones, stresses and drugs — the information the cell is trying to read. Not a cellular location.",
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
        "blurb": "The decision platform. mTORC1 is only switched on here, because this is the only place it meets Rheb. Everything about nutrient sensing is really about getting mTORC1 to this membrane.",
        # Deklarované zjednodušení. Zamlčené zjednodušení je přesně to, co
        # tenhle redesign zakazuje — takže se řekne nahlas i tam, kde je
        # pedagogicky správné.
        "sensing_note": "Simplified on purpose: this band means 'the endomembrane surface where mTORC1 is switched on'. Rheb is not exclusively lysosomal — a large fraction sits on the ER and Golgi, and which pool activates mTORC1 is still argued. Rheb is drawn here because the lysosome is where it meets mTORC1, which is the fact the pathway logic turns on. The ER, Golgi and peroxisome are not drawn as separate bands.",
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
        "blurb": "Cell-, tissue- and organism-level consequences. Not a cellular location — and the evidence here is a different kind of evidence from the molecular steps above.",
    },
]

# ---------------------------------------------------------------------------
# 2. Uzly — kompartment, třída, a role ve třech úrovních.
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
                "Binds Sestrin2 with ~20 µM Kd — within the range over which intracellular leucine actually fluctuates, which is the main argument that Sestrin2 is a physiological sensor rather than a binder."),
    "Arginine": ("input", "nut", "A second amino acid the cell counts.",
                 "Sensed twice: by cytosolic CASTOR1 and by the lysosomal transporter SLC38A9.",
                 "Two-sensor architecture lets the cell distinguish cytosolic from lysosomal arginine pools; the functional division of labour is still argued."),
    "Glutamine": ("input", "nut", "Abundant amino acid with a disputed route in.",
                  "Activates mTORC1 in some settings without the Rag GTPases (Arf1-dependent route).",
                  "Rag-independent glutamine signalling via Arf1 is reported but not universally reproduced; treat the route as unsettled."),
    "S-adenosylmethionine (SAM)": ("input", "nut", "Reports how much methyl-donor the cell has.",
                                   "Methionine-derived metabolite read by SAMTOR — the cell's methionine proxy.",
                                   "SAM binds SAMTOR (Kd ~7 µM); links one-carbon metabolism to mTORC1 independently of the leucine and arginine arms."),
    "Growth hormone / IGF-1 axis": ("input", "hormone", "The 'there is food and it is safe to grow' hormone signal.",
                                    "Endocrine input acting through receptor tyrosine kinases, IRS proteins and PI3K.",
                                    "Compressed here into one node; the axis spans GH→hepatic IGF-1→IGF1R/InsR→IRS→PI3K, and dwarf-mouse longevity phenotypes sit on it."),
    "Energy & cellular stress": ("input", "stress", "Running out of fuel.",
                                 "Rising AMP:ATP ratio and other stresses that activate AMPK.",
                                 "AMP and ADP binding to the AMPK γ-subunit plus LKB1-dependent T172 phosphorylation; also covers glucose withdrawal sensed via aldolase/lysosomal AXIN–LKB1."),
    "Hypoxia": ("input", "stress", "Not enough oxygen.",
                "Low O₂ suppresses mTORC1 partly through transcriptional induction of REDD1.",
                "REDD1 (DDIT4) induction is HIF-1-dependent; hypoxia also acts faster via AMPK and via direct effects on translation, so REDD1 is one arm not the whole story."),
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

    # ---- plasma membrane --------------------------------------------------
    "PI3K": ("pm", "protein", "Makes the membrane signal that pulls Akt in.",
             "Class I PI3K phosphorylates PIP2 to PIP3 at the plasma membrane.",
             "p110/p85 heterodimer; PIK3CA is one of the most frequently mutated oncogenes in human cancer. Its output is a lipid, not a phosphoprotein — which is why PTEN reverses it."),
    "PTEN": ("pm", "protein", "Erases the signal PI3K writes.",
             "Lipid phosphatase that converts PIP3 back to PIP2.",
             "PTEN does not inhibit the PI3K enzyme; it degrades PI3K's product. Haploinsufficient tumour suppressor with dose-dependent phenotypes."),
    "IRS-1 / IRS-2": ("pm", "protein", "The adaptor that connects the insulin receptor to PI3K.",
                      "Scaffold recruiting PI3K to activated insulin/IGF-1 receptors.",
                      "Serine phosphorylation by S6K1 (and others) triggers IRS-1 degradation — the molecular basis of the best-characterised mTORC1 feedback loop and of rapalog-associated insulin resistance."),
    "Akt/PKB": ("pm", "protein", "The main 'grow' relay from growth factors.",
                "AGC kinase requiring PIP3 recruitment plus two phosphorylations to be fully active.",
                "T308 by PDK1 and S473 by mTORC2. Recruitment and activation are separate events — a distinction the older Atlas diagram blurred."),
    "mTORC2": ("pm", "complex", "mTOR's second, less famous complex.",
               "mTOR–Rictor–SIN1–mLST8; phosphorylates Akt, SGK1 and PKC.",
               "Largely plasma-membrane associated and PI3K-responsive via the SIN1 PH domain; acutely rapamycin-insensitive, which is the cleanest way to separate mTORC1 from mTORC2 biology experimentally."),

    # ---- cytosol ----------------------------------------------------------
    "Sestrin2": ("cytosol", "protein", "A leucine detector that works as a brake.",
                 "Leucine-binding negative regulator: without leucine it holds GATOR2 inactive.",
                 "Sestrin2 is a *negative* regulator. Leucine binding releases GATOR2 — the pathway is switched on by removing a brake. Also stress-inducible via p53, so it sits at a stress/nutrient junction."),
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
             "αβγ heterotrimer. Two independent arms onto mTORC1 plus a direct activating arm onto ULK1 — the reason energy stress switches growth off and recycling on in one move."),
    "LKB1 (STK11)": ("cytosol", "protein", "The kinase that arms AMPK.",
                     "Constitutive upstream kinase phosphorylating AMPK T172.",
                     "Tumour suppressor mutated in Peutz–Jeghers syndrome and in lung adenocarcinoma; also the reason some cells cannot mount an AMPK response at all."),
    "ULK1": ("cytosol", "protein", "The switch that starts self-digestion.",
             "Autophagy-initiating kinase, inhibited by mTORC1 and activated by AMPK.",
             "mTORC1 phosphorylates S757 to block the AMPK–ULK1 interaction; ULK1 also feeds back to phosphorylate and dampen AMPK, making this a closed loop rather than a switch."),
    "S6K1": ("cytosol", "protein", "mTORC1's best-known output kinase.",
             "Ribosomal protein S6 kinase; the standard readout of mTORC1 activity.",
             "T389 phosphorylation by mTORC1 is rapamycin-sensitive, which is why S6K1 became the field's default assay — and why the field long over-read rapamycin as a complete mTORC1 inhibitor."),
    "4E-BP1": ("cytosol", "protein", "A cap on protein-making that mTORC1 removes.",
               "Translational repressor released from eIF4E upon multi-site phosphorylation.",
               "Only partially rapamycin-sensitive. This single fact explains the rapalog/Torin discrepancy and drove the whole ATP-competitive inhibitor programme."),
    "eIF4E": ("cytosol", "protein", "The clamp that starts reading mRNA.",
              "Cap-binding translation initiation factor.",
              "Rate-limiting for cap-dependent initiation; a proto-oncogene in its own right when overexpressed."),
    "PDCD4": ("cytosol", "protein", "Another brake on protein-making.",
              "Inhibits eIF4A; degraded after S6K1 phosphorylation.",
              "S6K1 phosphorylates S67, creating a βTRCP degron — an mTORC1 output that works by destroying a repressor rather than activating an enzyme."),
    "PRAS40": ("cytosol", "protein", "A plug in mTORC1's substrate slot.",
               "Raptor-binding inhibitor displaced by Akt phosphorylation.",
               "AKT1S1. Competes with substrate for the Raptor TOS-motif site; its displacement is a substrate-access mechanism, not a change in kinase catalytic rate."),
    "Grb10": ("cytosol", "protein", "A brake mTORC1 puts on its own upstream signal.",
              "mTORC1 substrate that inhibits insulin/IGF-1 receptor signalling.",
              "Stabilised by mTORC1 phosphorylation; one of two arms (with S6K1→IRS-1) of negative feedback onto PI3K, and an imprinted gene with growth phenotypes."),
    "DEPTOR": ("cytosol", "protein", "An in-built damper on both complexes.",
               "mTOR-binding inhibitor of mTORC1 and mTORC2.",
               "Overexpressed in a subset of multiple myeloma where its loss is required for viability — an inhibitor that behaves as an oncogenic dependency."),
    "FKBP12": ("cytosol", "protein", "The protein rapamycin must borrow.",
               "Prolyl isomerase that forms the drug-receptor complex with rapamycin.",
               "FKBP1A. Rapamycin has essentially no activity against mTOR without it, which is why FKBP12 expression sets rapalog sensitivity."),
    "ERK / RSK (MAPK)": ("cytosol", "protein", "A second growth pathway that presses the same brake.",
                         "ERK and RSK phosphorylate TSC2 to inhibit it, and are activated when mTORC1 is blocked.",
                         "ERK S664 and RSK S1798 on TSC2. mTORC1 inhibition relieves feedback and activates MAPK PI3K-dependently — the basis for combined mTOR/MEK strategies."),
    "REDD1 (DDIT4)": ("cytosol", "protein", "A stress-made brake amplifier.",
                      "Hypoxia-induced protein that promotes TSC-dependent mTORC1 inhibition.",
                      "Proposed to release TSC2 from 14-3-3 sequestration; short half-life makes it a transient rather than a maintained signal."),
    "mTOR": ("cytosol", "protein", "The kinase at the centre of everything.",
             "Serine/threonine kinase, catalytic subunit of both mTORC1 and mTORC2.",
             "PIKK-family kinase. The same catalytic subunit in two complexes with different partners, locations, substrates and drug sensitivities — the complex, not the kinase, is the unit of biology."),
    "Raptor": ("cytosol", "protein", "The part that makes mTOR into mTORC1.",
               "Substrate-presenting subunit defining mTORC1 and its lysosomal targeting.",
               "Recognises TOS motifs; the AMPK phosphorylation site and the Rag-binding surface both sit here, so Raptor is where location and inhibition converge."),
    "Rictor": ("cytosol", "protein", "The part that makes mTOR into mTORC2.",
               "Defining subunit of mTORC2.",
               "Confers acute rapamycin insensitivity and, with SIN1, the substrate specificity for Akt S473."),
    "SIN1 / MAPKAP1": ("cytosol", "protein", "mTORC2's growth-factor antenna.",
                       "mTORC2 subunit whose PH domain makes the complex PI3K-responsive.",
                       "MAPKAP1. The PH domain inhibits mTORC2 until PIP3 relieves it — the cleanest mechanism for how growth factors reach mTORC2."),
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
               "DEPDC5 loss causes focal epilepsy — a human phenotype that establishes GATOR1's physiological relevance beyond cell lines."),
    "KICSTOR": ("lyso", "complex", "The dock GATOR1 needs.",
                "KPTN–ITFG2–C12orf66–SZT2; tethers GATOR1 to the lysosome.",
                "Loss uncouples mTORC1 from nutrient status; SZT2 mutations cause a human epileptic encephalopathy."),
    "Rag GTPases": ("lyso", "protein", "The taxi that brings mTORC1 to the lysosome.",
                    "RagA/B–RagC/D heterodimers; nucleotide state determines mTORC1 recruitment.",
                    "Note the inversion: RagA/B is active when GTP-loaded, RagC/D when GDP-loaded. The Rags control mTORC1 *location*, not its catalytic activity."),
    "Ragulator": ("lyso", "complex", "The bolt holding the taxi to the membrane.",
                  "LAMTOR1–5 complex tethering the Rags to the lysosomal surface.",
                  "Also reported as a RagA/B GEF, though the GEF assignment is less secure than the tethering role; LAMTOR1 lipidation anchors the whole assembly."),
    "v-ATPase": ("lyso", "complex", "The pump the sensing machinery is built on.",
                 "Lysosomal proton pump physically and functionally coupled to Ragulator.",
                 "Required for amino-acid signalling; inhibitor experiments cannot fully separate the signalling role from loss of lysosomal acidification."),
    "SLC38A9": ("lyso", "protein", "A lysosomal arginine sensor and exporter.",
                "Transceptor: arginine-regulated component of the Rag–Ragulator machinery that also effluxes leucine.",
                "Its cytosolic N-terminus binds Rag–Ragulator arginine-dependently; the transport and signalling functions are separable and both matter."),
    "FLCN / FNIP1/2": ("lyso", "complex", "The switch that decides which substrates mTORC1 gets.",
                       "GAP for RagC/D; required for mTORC1 to phosphorylate TFEB.",
                       "Folliculin is a *positive* regulator of the RagC/D arm despite being a tumour suppressor in Birt–Hogg–Dubé — the substrate-selective mTORC1 pathway explains the apparent contradiction."),
    "Rheb": ("lyso", "protein", "The one thing that actually switches mTORC1 on.",
             "Small GTPase; GTP-loaded Rheb allosterically activates mTORC1.",
             "Realigns the mTOR active site; the convergence point of the entire growth-factor arm and the reason localisation alone is not activation. Note a declared simplification in this map: Rheb is farnesylated and distributes across the endomembrane system, with a substantial ER and Golgi pool, and which pool supplies the activating Rheb is still debated. It is drawn on the lysosomal band because that is where it meets mTORC1."),
    "mTORC1": ("lyso", "complex", "The growth decision itself.",
               "mTOR–Raptor–mLST8 (+PRAS40, DEPTOR); switched on only at the lysosome.",
               "Coincidence detector: nutrients supply location via the Rags, growth factors supply activation via Rheb. Neither alone is sufficient — the single most important idea in the pathway."),
    "Lysosome": ("lyso", "organelle", "The place where the decision is made.",
                 "Signalling platform as well as degradative organelle.",
                 "Amino-acid sensing, Rheb access, TFEB regulation and autophagosome fusion all happen on or in this one organelle."),

    # ---- nucleus ----------------------------------------------------------
    "TFEB": ("nucleus", "protein", "The master switch for recycling genes.",
             "Transcription factor for lysosomal and autophagy genes; excluded from the nucleus when phosphorylated by mTORC1.",
             "Phosphorylated on S211 in a Rag- and FLCN-dependent, substrate-selective manner; this is the clearest case where mTORC1 substrate choice — not overall activity — is the regulated variable."),
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
                           "In mice, mTORC2 disruption is a major contributor (LAM2012); in humans the relative contributions of mTORC2 loss, S6K1–IRS-1 feedback and direct β-cell effects are unresolved."),
    "Cellular senescence": ("outcome", "phenotype", "Cells that stop dividing but do not die.",
                            "Stable proliferative arrest with an inflammatory secretory programme, supported by mTORC1.",
                            "mTORC1 drives the SASP translationally; rapamycin suppresses SASP without reversing arrest, so 'senescence' and 'SASP' must not be conflated."),
    "Tumor growth": ("outcome", "phenotype", "Cancer growing.",
                     "Proliferation and mass increase supported by mTORC1 signalling.",
                     "Genotype-dependent: mTORC1 activation is a strong dependency in TSC- and PI3K-pathway-mutant contexts and much weaker elsewhere."),
    "Renal cell carcinoma (RCC)": ("outcome", "disease", "A kidney cancer treated with these drugs.",
                                   "Cancer where rapalogs are licensed and mTOR-pathway lesions are common.",
                                   "Temsirolimus (ARCC) and everolimus (RECORD-1) both improved outcomes; exceptional responders have been traced to TSC1 loss."),
    "Breast cancer": ("outcome", "disease", "A cancer where a rapalog is used with hormone therapy.",
                      "Hormone-receptor-positive disease where everolimus is added to exemestane.",
                      "BOLERO-2: progression-free survival benefit, no clear overall-survival benefit, meaningful toxicity — a resistance-delaying rather than curative effect."),
    "Pancreatic neuroendocrine tumor": ("outcome", "disease", "A rare pancreatic tumour type.",
                                               "Everolimus-licensed indication.",
                                               "RADIANT-3 showed progression-free survival benefit; mTOR-pathway mutations are recurrent in this histology."),
    "Tuberous sclerosis complex": ("outcome", "disease", "A genetic disease of the pathway's own brake.",
                                   "TSC1/TSC2 loss causing benign tumours in multiple organs.",
                                   "The cleanest human demonstration that mTORC1 hyperactivation drives disease, and the setting where rapalogs work best — including on subependymal giant-cell astrocytoma."),
    "Lymphangioleiomyomatosis": ("outcome", "disease", "A rare progressive lung disease.",
                                 "TSC-related proliferative lung disease treated with sirolimus.",
                                 "MILES tested sirolimus and stabilised FEV1; EXIST-2 tested everolimus against renal angiomyolipoma, not the lung disease — a distinction routinely blurred."),
    "Prostate cancer": ("outcome", "disease", "A cancer where mTORC2 matters unusually much.",
                        "PTEN-loss-driven disease with an mTORC2 requirement in mouse models.",
                        "Rictor deletion blocks PTEN-null prostate tumorigenesis in mice; rapalog monotherapy has not translated, consistent with an mTORC2-dependent mechanism."),
    "Immune function": ("outcome", "phenotype", "How well the immune system works.",
                        "mTOR inhibition reshapes rather than simply suppresses immunity.",
                        "Rapalogs are immunosuppressants at transplant doses, yet low-dose everolimus improved influenza vaccine responses in the elderly (Mannick 2014/2018) — dose and schedule determine the direction."),
    "Actin cytoskeleton": ("outcome", "process", "The cell's internal scaffolding.",
                           "mTORC2-dependent actin organisation and cell shape control.",
                           "The original TORC2 phenotype in yeast; in mammals mediated through PKCα and Rho GTPases and largely rapamycin-insensitive acutely."),
}

# ---------------------------------------------------------------------------
# 3. Kurace hran.
#
# type  — mechanistický děj:
#   binding | recruitment | localisation | translocation | scaffolding
#   | phosphorylation | dephosphorylation | gap-activity | gef-activity
#   | complex-assembly | complex-disassembly | allosteric-activation
#   | allosteric-inhibition | competitive-inhibition | transcriptional
#   | transport | signal-relay | functional-consequence | clinical-outcome
#   | association
# comp  — kde se to děje (id kompartmentu)
# ts    — seconds | minutes | hours | days | chronic | constitutive
# dir   — direct | indirect | unresolved
# mc    — mechanistická důvěra: high | medium | low
# hr    — lidská relevance: established | plausible | untested
# cons  — established | emerging | contested
#
# POZOR: "sign" (activates/inhibits/required-for) se PŘEBÍRÁ ze stávajících
# dat — byl externě recenzován a nebyl v něm nalezen ani jeden chybný znak.
# Tady se doplňuje jen to, co dosud chybělo.
# ---------------------------------------------------------------------------
CUR = {
 "LEU-SESN2":        ("binding","cytosol","seconds","direct","high","plausible","established"),
 "SESN2-GATOR2":     ("binding","cytosol","seconds","direct","high","plausible","established"),
 "ARG-CASTOR1":      ("binding","cytosol","seconds","direct","high","plausible","established"),
 "CASTOR1-GATOR2":   ("binding","cytosol","seconds","direct","high","plausible","established"),
 "GATOR2-GATOR1":    ("binding","lyso","seconds","direct","medium","plausible","emerging"),
 "KICSTOR-GATOR1":   ("recruitment","lyso","constitutive","direct","high","established","established"),
 "GATOR1-RAG":       ("gap-activity","lyso","seconds","direct","high","established","established"),
 "SAM-SAMTOR":       ("binding","cytosol","seconds","direct","high","plausible","emerging"),
 "SAMTOR-GATOR1":    ("binding","lyso","seconds","direct","medium","plausible","emerging"),
 "RAGULATOR-RAG":    ("scaffolding","lyso","constitutive","direct","high","established","established"),
 "VATPASE-RAGULATOR":("binding","lyso","constitutive","direct","medium","plausible","emerging"),
 "SLC38A9-RAG":      ("binding","lyso","seconds","direct","high","plausible","established"),
 "FLCN-RAG":         ("gap-activity","lyso","seconds","direct","high","established","established"),
 "RAG-MTORC1":       ("recruitment","lyso","minutes","direct","high","established","established"),
 "LYSO-MTORC1":      ("localisation","lyso","minutes","direct","high","established","established"),
 "LEU-LARS":         ("binding","cytosol","seconds","unresolved","low","untested","contested"),
 "LARS-RAG":         ("gap-activity","lyso","seconds","unresolved","low","untested","contested"),
 "GLN-RAG":          ("signal-relay","lyso","minutes","indirect","low","untested","contested"),
 "IGF1-PI3K":        ("signal-relay","pm","seconds","indirect","high","established","established"),
 "PI3K-AKT":         ("recruitment","pm","seconds","indirect","high","established","established"),
 "MTORC2-AKT":       ("phosphorylation","pm","seconds","direct","high","established","established"),
 "AKT-TSC":          ("phosphorylation","cytosol","seconds","direct","high","established","established"),
 "TBC1D7-TSC":       ("complex-assembly","cytosol","constitutive","direct","high","established","established"),
 "TSC-RHEB":         ("gap-activity","lyso","seconds","direct","high","established","established"),
 "RHEB-MTORC1":      ("allosteric-activation","lyso","seconds","direct","high","established","established"),
 "AKT-PRAS40":       ("phosphorylation","cytosol","seconds","direct","high","established","established"),
 "PRAS40-MTORC1":    ("competitive-inhibition","lyso","seconds","direct","high","plausible","established"),
 "AMPK-TSC":         ("phosphorylation","cytosol","minutes","direct","high","established","established"),
 "AMPK-MTORC1":      ("phosphorylation","lyso","minutes","direct","high","established","established"),
 "MTORC1-GRB10":     ("phosphorylation","cytosol","minutes","direct","high","plausible","established"),
 "GRB10-IGF1":       ("signal-relay","pm","hours","indirect","medium","plausible","established"),
 "MTORC1-S6K1":      ("phosphorylation","cytosol","minutes","direct","high","established","established"),
 "MTORC1-4EBP1":     ("phosphorylation","cytosol","minutes","direct","high","established","established"),
 "MTORC1-ULK1":      ("phosphorylation","cytosol","minutes","direct","high","established","established"),
 "ULK1-AUTOPHAGY":   ("functional-consequence","autophagy","minutes","direct","high","established","established"),
 "RAPA-FKBP12":      ("binding","cytosol","seconds","direct","high","established","established"),
 "FKBP12-MTORC1":    ("allosteric-inhibition","lyso","minutes","direct","high","established","established"),
 "RAPTOR-MTORC1":    ("complex-assembly","cytosol","constitutive","direct","high","established","established"),
 "RICTOR-MTORC2":    ("complex-assembly","cytosol","constitutive","direct","high","established","established"),
 "RAPA-MTORC2":      ("complex-disassembly","cytosol","chronic","indirect","low","plausible","contested"),
 "MTORC2-INSULINRES":("functional-consequence","outcome","chronic","indirect","medium","plausible","emerging"),
 "RAPA-LONGEVITY":   ("clinical-outcome","outcome","chronic","indirect","medium","untested","established"),
 "MTORC1-LONGEVITY": ("functional-consequence","outcome","chronic","indirect","medium","untested","established"),
 "4EBP1-EIF4E":      ("competitive-inhibition","cytosol","seconds","direct","high","established","established"),
 "EIF4E-TRANSL":     ("functional-consequence","cytosol","minutes","direct","high","established","established"),
 "S6K1-PDCD4":       ("phosphorylation","cytosol","minutes","direct","high","plausible","established"),
 "PDCD4-TRANSL":     ("functional-consequence","cytosol","minutes","direct","high","plausible","established"),
 "TRANSL-MUSCLE":    ("functional-consequence","outcome","days","indirect","high","established","established"),
 "MTORC1-TFEB":      ("phosphorylation","lyso","minutes","direct","high","established","established"),
 "TFEB-AUTOPHAGY":   ("transcriptional","nucleus","hours","direct","high","established","established"),
 "MTORC1-SREBP":     ("signal-relay","cytosol","hours","indirect","medium","plausible","emerging"),
 "SREBP-LIPID":      ("transcriptional","nucleus","hours","direct","high","established","established"),
 "MTORC1-MITO":      ("signal-relay","mito","hours","indirect","medium","plausible","emerging"),
 "4EBP1-MITO":       ("functional-consequence","mito","hours","indirect","medium","untested","emerging"),
 "MTORC1-NUCL":      ("signal-relay","cytosol","hours","indirect","high","plausible","established"),
 "S6K1-NUCL":        ("phosphorylation","cytosol","minutes","direct","high","plausible","established"),
 "4EBP1-LONGEVITY":  ("functional-consequence","outcome","chronic","indirect","medium","untested","emerging"),
 "S6K1-LONGEVITY":   ("functional-consequence","outcome","chronic","indirect","medium","untested","emerging"),
 "MTORC1-SENESCENCE":("functional-consequence","outcome","days","indirect","medium","plausible","emerging"),
 "STRESS-AMPK":      ("allosteric-activation","cytosol","seconds","direct","high","established","established"),
 "LKB1-AMPK":        ("phosphorylation","cytosol","seconds","direct","high","established","established"),
 "METFORMIN-AMPK":   ("signal-relay","cytosol","minutes","indirect","low","plausible","contested"),
 "AMPK-ULK1":        ("phosphorylation","cytosol","minutes","direct","high","established","established"),
 "ULK1-AMPK":        ("phosphorylation","cytosol","minutes","direct","high","plausible","established"),
 "HYPOXIA-REDD1":    ("transcriptional","nucleus","hours","indirect","high","established","established"),
 "REDD1-TSC":        ("binding","cytosol","hours","direct","medium","plausible","emerging"),
 "STRESS-TSC":       ("translocation","lyso","minutes","direct","medium","plausible","emerging"),
 "ISR-SALR":         ("transcriptional","nucleus","hours","indirect","medium","untested","emerging"),
 "SALR-MTORC1":      ("signal-relay","cytosol","hours","unresolved","low","untested","emerging"),
 "AMPK-MITOPHAGY":   ("functional-consequence","mito","hours","indirect","medium","plausible","emerging"),
 "MTOR-MTORC2":      ("complex-assembly","cytosol","constitutive","direct","high","established","established"),
 "SIN1-MTORC2":      ("complex-assembly","cytosol","constitutive","direct","high","established","established"),
 "MLST8-MTORC2":     ("complex-assembly","cytosol","constitutive","direct","high","plausible","established"),
 "PI3K-MTORC2":      ("signal-relay","pm","seconds","indirect","medium","plausible","emerging"),
 "PTEN-PI3K":        ("dephosphorylation","pm","seconds","direct","high","established","established"),
 "MTORC2-SGK1":      ("phosphorylation","cytosol","minutes","direct","high","established","established"),
 "MTORC2-ACTIN":     ("functional-consequence","cytosol","minutes","indirect","high","plausible","established"),
 "MTORC2-LIPID":     ("functional-consequence","outcome","chronic","indirect","medium","plausible","emerging"),
 "MTORC2-PROSTATE":  ("functional-consequence","outcome","chronic","indirect","medium","plausible","emerging"),
 "DEPTOR-MTOR":      ("binding","cytosol","constitutive","direct","high","plausible","established"),
 "TSC-MTORC1":       ("signal-relay","lyso","seconds","indirect","high","established","established"),
 "MTORC1-TUMOR":     ("functional-consequence","outcome","chronic","indirect","high","established","established"),
 "EVE-MTORC1":       ("allosteric-inhibition","lyso","hours","indirect","high","established","established"),
 "TEM-MTORC1":       ("allosteric-inhibition","lyso","hours","indirect","high","established","established"),
 "EVE-RCC":          ("clinical-outcome","outcome","chronic","indirect","high","established","established"),
 "TEM-RCC":          ("clinical-outcome","outcome","chronic","indirect","high","established","established"),
 "EVE-PNET":         ("clinical-outcome","outcome","chronic","indirect","high","established","established"),
 "EVE-BREAST":       ("clinical-outcome","outcome","chronic","indirect","high","established","established"),
 "EVE-TSC":          ("clinical-outcome","outcome","chronic","indirect","high","established","established"),
 "EVE-LAM":          ("clinical-outcome","outcome","chronic","indirect","medium","established","established"),
 "EVE-IMMUNE":       ("clinical-outcome","outcome","chronic","indirect","medium","established","contested"),
 "MTORC1-PROSTATE":  ("functional-consequence","outcome","chronic","indirect","medium","plausible","emerging"),
 "S6K1-IRS1":        ("phosphorylation","cytosol","hours","direct","high","established","established"),
 "IRS1-PI3K":        ("recruitment","pm","seconds","direct","high","established","established"),
 "ERK-TSC":          ("phosphorylation","cytosol","minutes","direct","high","plausible","established"),
 "MTORC1-MAPK":      ("signal-relay","cytosol","hours","indirect","high","established","established"),
 "METFORMIN-MTORC1": ("signal-relay","cytosol","hours","indirect","low","plausible","contested"),
 "SESN2-AGING":      ("functional-consequence","outcome","chronic","indirect","medium","untested","emerging"),
 "RAPA-LAM":         ("clinical-outcome","outcome","chronic","indirect","high","established","established"),
 "MTORC1-RCC":       ("association","outcome","chronic","unresolved","low","established","emerging"),
}

# Poznámky, které stará data neuměla vyjádřit a které jsou pedagogicky
# nosné — proč je zde znak takový, jaký je.
TEACH = {
 "RAG-MTORC1": "Recruitment, not activation. The Rags decide *where* mTORC1 is; they do not switch the kinase on. This is why amino acids alone cannot drive growth.",
 "RHEB-MTORC1": "This is the actual on-switch. Everything the growth-factor arm does converges here.",
 "PI3K-AKT": "Indirect on purpose: PI3K makes PIP3, and PIP3 recruits Akt. Recruitment then enables two separate phosphorylations. Three distinct events often drawn as one arrow.",
 "PTEN-PI3K": "PTEN does not touch the PI3K protein. It removes PI3K's product. Drawn as an inhibition arrow for readability — the mechanism is enzymatic reversal.",
 "TSC-MTORC1": "A deliberate shortcut edge: TSC never touches mTORC1. It acts on Rheb. Shown so the overview reads cleanly; switch to Research level to see the two-step version.",
 "FKBP12-MTORC1": "Partial, not complete. The FKBP12–rapamycin complex occludes the substrate channel, so S6K1 phosphorylation collapses while 4E-BP1 phosphorylation persists. This one fact created the entire ATP-competitive inhibitor field.",
 "FLCN-RAG": "Positive regulator of the RagC/D arm, despite being a tumour suppressor. It licenses mTORC1 to phosphorylate TFEB specifically — substrate choice, not overall activity.",
 "S6K1-IRS1": "The pathway's most clinically consequential feedback loop: blocking mTORC1 releases IRS-1, reactivating PI3K/Akt. Half of why rapalog monotherapy underperforms.",
 "MTORC1-MAPK": "The second feedback arm. mTORC1 inhibition activates ERK PI3K-dependently, which is the rationale for combined mTOR/MEK strategies.",
 "MTORC1-4EBP1": "The sign is on 4E-BP1's repressor function: mTORC1 phosphorylates it, which stops it repressing eIF4E. Phosphorylation is not the same as inhibition — here it happens to be.",
 "GATOR2-GATOR1": "Everyone agrees this inhibition happens; nobody has fully resolved how. Kept visible as an honest hole in a canonical pathway.",
 "ULK1-AMPK": "Closes the loop. ULK1 dampens the very kinase that activated it, so 'AMPK switches on autophagy' is a loop, not an arrow.",
 "MTORC1-RCC": "Association, not demonstrated causation. Renal cancers often carry lesions that leave mTORC1 active; that is why the tissue responds to rapalogs, not proof that mTORC1 initiates the disease.",
 "LYSO-MTORC1": "A requirement, not a signal. The lysosome contributes a location.",
 "STRESS-TSC": "Regulation by relocation: energy stress moves the TSC complex to the lysosome, where Rheb is. Location is a form of control the pathway uses repeatedly.",
}


# ---------------------------------------------------------------------------
# 4. Ručně napsané kroky tras.
#
# Motor tras umí každý krok složit z kurátorovaných polí (mechanism,
# teaching_note, confidence, boundary) — takže všech 7 tras funguje hned a
# nic si nevymýšlí. Ruční verze je ale lepší: umí říct, JAKÝ PROBLÉM buňka
# řeší, a navázat krok na krok. Tady je `aa` napsaná ručně jako etalon
# kvality, na který se dopisují ostatní (Fáze 2).
#
# Každý krok odpovídá na šest otázek. Když některou vynecháš, doplní se
# automaticky z modelu — nikdy nezůstane prázdná.
# ---------------------------------------------------------------------------
ROUTE_STEPS = {
 "aa": [
  {"interaction": "LEU-SESN2",
   "what": "Leucine binds Sestrin2 — and switches a brake off.",
   "why": "Sestrin2 carries a pocket that fits leucine with roughly 20 µM affinity. That number is the whole argument: it sits inside the range over which leucine inside a real cell actually rises and falls, so Sestrin2 changes state when leucine changes, rather than being permanently full or permanently empty.",
   "changed": "Leucine-loaded Sestrin2 can no longer hold onto GATOR2. Nothing has been switched on yet — something has been let go of.",
   "consequence": "GATOR2 is now free. Watch what it does with that freedom: it does not activate anything either. It inhibits the next brake.",
   "certainty": "The binding is structurally resolved and the affinity measured in vitro. What is not established is whether the same 20 µM setpoint holds in tissues with different leucine transport — so this is high mechanistic confidence with unproven human physiological calibration.",
   "matters": "This is where the pathway's logic starts being counter-intuitive. The cell does not detect food and then send a 'grow' signal. It detects food and stops sending a 'do not grow' signal. Almost every nutrient input works this way, and it is the reason the pathway is so hard to read off a diagram of arrows."},
  {"interaction": "SESN2-GATOR2",
   "what": "GATOR2 is released — the first brake comes off.",
   "why": "Sestrin2 and GATOR2 are mutually exclusive binding partners: leucine-bound Sestrin2 lets go, and free GATOR2 becomes able to act on GATOR1.",
   "changed": "GATOR2 goes from sequestered to available. Its availability, not its abundance, is what the cell regulates.",
   "consequence": "Available GATOR2 now inhibits GATOR1. Count the negatives as you go — you are two into a chain of them.",
   "certainty": "Mechanistically solid and reproduced. Structures of the GATOR2 cage and its sensor-binding surfaces exist; the cited corpus evidence here is cell-line biochemistry, so human relevance is plausible rather than demonstrated.",
   "matters": "Regulation by sequestration rather than by synthesis is fast and cheap — no transcription, no translation, no degradation. It lets the cell respond to a meal in seconds instead of hours. Evolution reaches for this trick whenever speed matters."},
  {"interaction": "GATOR2-GATOR1",
   "what": "GATOR2 shuts down GATOR1 — the second brake comes off.",
   "why": "GATOR1 is the machine that switches the Rag GTPases off. GATOR2 inhibits it. So inhibiting GATOR1 means the Rags stop being switched off.",
   "changed": "GATOR1's GAP activity toward RagA/B falls. Two negatives have now cancelled: leucine present → Sestrin2 inhibited → GATOR2 free → GATOR1 inhibited.",
   "consequence": "The Rag GTPases can finally load GTP and stay loaded. That is the state that does something.",
   "certainty": "Everyone agrees the inhibition happens; nobody has fully resolved how it happens catalytically. This step is graded emerging consensus with medium mechanistic confidence — an honest hole in the middle of a canonical pathway.",
   "matters": "Worth pausing on: this is a textbook step that a textbook will draw as a confident arrow, and the mechanism behind it is genuinely unresolved. A map that hides that is more comfortable and less useful."},
  {"interaction": "GATOR1-RAG",
   "what": "With GATOR1 suppressed, the Rag GTPases stay loaded with GTP.",
   "why": "GATOR1 is a GAP — it forces RagA/B to hydrolyse GTP to GDP. Remove the GAP and RagA/B accumulates in the GTP state, which is its active conformation.",
   "changed": "RagA/B flips from GDP-loaded to GTP-loaded. Note the inversion in this heterodimer: RagA/B is active with GTP, but its partner RagC/D is active with GDP.",
   "consequence": "GTP-loaded RagA/B can now grip Raptor. That grip is what brings mTORC1 in.",
   "certainty": "The GAP activity is directly demonstrated biochemistry, and human genetics supports its physiological importance — DEPDC5 mutations cause focal epilepsy. The cited corpus evidence is cell-line work, so human relevance is graded plausible.",
   "matters": "Nucleotide state is the pathway's memory. A GTPase holds its answer until something actively changes it, which lets a signal that arrived seconds ago still be true now."},
  {"interaction": "RAGULATOR-RAG",
   "what": "Ragulator holds the Rags on the lysosomal membrane.",
   "why": "The Rags are not free-floating. Ragulator is lipid-anchored to the lysosome and clamps the Rag heterodimer to that surface, so everything the Rags do, they do at one specific place.",
   "changed": "Nothing about the Rags' activity changes here. What is fixed is their address.",
   "consequence": "Because the Rags are on the lysosome, whatever they recruit arrives on the lysosome too.",
   "certainty": "The tethering role is well established. Ragulator has also been reported as a GEF for RagA/B; that assignment is less secure than the tethering function, and the model records the tethering claim rather than the GEF claim.",
   "matters": "This is the step that makes the rest of the pathway make sense. Signalling here is not chemistry in free solution — it is a set of mechanisms for putting particular molecules in particular places. Location is the regulated variable."},
  {"interaction": "RAG-MTORC1",
   "what": "The Rags recruit mTORC1 to the lysosome. They do not switch it on.",
   "why": "GTP-loaded RagA/B binds Raptor directly, dragging the whole mTORC1 complex out of the cytosol and onto the lysosomal surface.",
   "changed": "mTORC1's location changes, and only its location. Its kinase activity at this moment is essentially unchanged. Recruitment is not activation — these are two different claims and this map draws them differently on purpose.",
   "consequence": "mTORC1 is now in the one place where it can meet Rheb. Meeting Rheb is the event that actually switches it on.",
   "certainty": "Directly demonstrated and reproduced across labs; the corpus evidence is cell-line biochemistry, so human relevance is graded plausible rather than established.",
   "matters": "If you take one thing from this route, take this: amino acids alone cannot make a cell grow. Starve a cell of growth factors, flood it with leucine, and mTORC1 will sit on the lysosome doing nothing. The nutrient arm answers 'are the parts available?' — it does not answer 'am I allowed to build?'"},
  {"interaction": "RHEB-MTORC1",
   "what": "Rheb switches mTORC1 on — and only growth factors control Rheb.",
   "why": "GTP-loaded Rheb binds mTORC1 and physically realigns its active site into a catalytically competent conformation. This is an allosteric activation, a different kind of event from everything upstream in this route.",
   "changed": "mTORC1 becomes an active kinase. Now, and only now, S6K1 and 4E-BP1 start getting phosphorylated.",
   "consequence": "The cell builds. And because Rheb is controlled by the TSC complex, which is controlled by Akt, AMPK and ERK, the growth-factor and energy arms all converge on this single step.",
   "certainty": "Structurally resolved and mechanistically secure. Cited evidence is mammalian cell work, so human relevance is graded plausible.",
   "matters": "This is coincidence detection, and it is the answer to why the pathway is built the way it is. Two independent conditions — nutrients supplying location, growth factors supplying activation — must both be satisfied at the same place and the same time. A cell that grew on either signal alone would build without materials or build when told not to. The lysosome is where the cell checks both answers against each other."},
 ],
}


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
    old_edges = read_atlas_array(html, "ATLAS_EDGES")
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
        })
        by_comp.setdefault(comp, []).append(name)

    # ---- hrany -----------------------------------------------------------
    interactions = []
    for e in old_edges:
        cur = CUR.get(e["id"])
        if not cur:
            problems.append("edge not curated: %s" % e["id"])
            cur = ("signal-relay", "cytosol", "minutes", "unresolved", "low", "untested", "emerging")
        typ, comp, ts, direct, mc, hr, cons = cur
        bad = [s for s in e["st"] if s not in known_sids]
        if bad:
            problems.append("edge %s cites unknown SID(s) %s" % (e["id"], bad))

        # --- lidská relevance se NEUVÁDÍ, ODVOZUJE SE ----------------------
        # Nález F4 externí recenze: pravidlo pro sílu tvrzení bylo napsáno
        # jinak, než bylo použito. Řešení není opravit jednotlivé případy,
        # ale odebrat kurátorovi možnost tvrdit víc, než evidence unese.
        # Kurátor smí lidskou relevanci jen SNÍŽIT (např. "untested" u
        # myších lifespan dat), nikdy zvýšit nad to, co dovolují citace.
        tiers_here = {sid_tier.get(s, "?") for s in e["st"]}
        human_sp = "human" in e["sp"].lower()
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
            "teaching_note": TEACH.get(e["id"], ""),
            "boundary": e.get("ctx", ""),
            "note": e.get("note", ""),
            "evidence": {
                "kind": e["dir"],
                "tiers": e["tiers"],
                "best_tier": e["tier"],
                "supporting": e["st"],
                "conflicting": [],
            },
            "confidence": {
                "mechanistic": mc,
                "human_relevance": hr,
                "consensus": cons,
            },
            "review": {"reviewer": CURATOR, "reviewed": REVIEW_DATE, "updated": REVIEW_DATE},
        })

    coords, bands, height = layout(by_comp, interactions, comp_order)
    for n in nodes:
        n.update(coords.get(n["id"], {"x": 700, "y": 400}))

    # ---- trasy: migrace 7 stávajících ------------------------------------
    routes = []
    for r in old_routes:
        routes.append({
            "id": r["id"], "name": r["name"], "summary": r["sub"],
            "story": r["story"],
            "interactions": r["edges"],
            "spine": r.get("steps", []),
            "steps": ROUTE_STEPS.get(r["id"], []),
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
            "counts": {"nodes": len(nodes), "interactions": len(interactions), "routes": len(routes)},
            "vocab": {
                "type": sorted({i["type"] for i in interactions}),
                "effect": sorted({i["effect"] for i in interactions}),
                "timescale": ["seconds", "minutes", "hours", "days", "chronic", "constitutive"],
                "directness": ["direct", "indirect", "unresolved"],
                "mechanistic": ["high", "medium", "low"],
                "human_relevance": ["established", "plausible", "untested"],
                "consensus": ["established", "emerging", "contested"],
            },
        },
        "compartments": COMPARTMENTS,
        "bands": bands,
        "nodes": nodes,
        "interactions": interactions,
        "routes": routes,
    }

    os.makedirs(OUT_DIR, exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
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
