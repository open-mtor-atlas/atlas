/* PREVZATO z produkcniho index.html skriptem scripts/sync_lineage.py.
   NEEDITOVAT — oprava patri do produkce a pak sem pres npm run sync. */

    (function(){
/* ============================================================
   Oliver's mTOR Atlas — Lineage component (standalone)
   Field shape mirrors ATLAS_STUDIES plus a `lineage` block.
   relation: ENABLES | EXTENDS | CONVERGES | CONTRADICTS | OPENS
   type:     FOUNDATIONAL | TOOL | MECHANISM | LIFESPAN |
             TRANSLATION | REVERSAL | NULL | OPEN
   Every PMID below verified against PubMed.
   ============================================================ */

const BRANCHES = [
  { id:"A", name:"Chemistry & target", note:"The trunk: a molecule becomes a probe" },
  { id:"B", name:"Complex architecture", note:"mTORC1 vs mTORC2" },
  { id:"C", name:"Upstream sensing", note:"Energy, growth factors, amino acids" },
  { id:"D", name:"Downstream output", note:"Translation and autophagy" },
  { id:"E", name:"Ageing & lifespan", note:"Yeast → worm → fly → mouse → ?" },
  { id:"F", name:"Clinic", note:"Oncology, immunity, longevity" }
];

const LINEAGE = [{ pmid:"1102508", year:1975, label:"Rapamycin isolated", authors:"Vézina, Kudelski & Sehgal",
    journal:"J Antibiot", doi:"10.7164/antibiotics.28.721", species:"Microbial", tier:"D",
    title:"Rapamycin (AY-22,989), a new antifungal antibiotic. I. Taxonomy of the producing streptomycete and isolation of the active principle.",
    lineage:{ branch:"A", type:"TOOL", thickness:5, parents:[],
      unlocked:"A soil bacterium from Rapa Nui yields a molecule with an unusually clean effect on cell growth. Nobody yet knows what it binds.", unlocked_beginner:"A soil microbe from Easter Island makes a molecule that clearly slows cell growth — but nobody yet knows what it latches onto inside the cell.", still_open:null }},

  { pmid:"1715094", year:1991, label:"TOR1/TOR2 in yeast", authors:"Heitman, Movva & Hall",
    journal:"Science", doi:"10.1126/science.1715094", species:"Yeast", tier:"D",
    title:"Targets for cell cycle arrest by the immunosuppressant rapamycin in yeast.",
    lineage:{ branch:"A", type:"FOUNDATIONAL", thickness:5, parents:[{pmid:"1102508", relation:"ENABLES"}],
      unlocked:"Resistance mutations name the target: TOR1 and TOR2. The field's true origin — a drug converted into a genetic handle.", unlocked_beginner:"Yeast that had become resistant to the drug pointed straight at its target genes, TOR1 and TOR2 — turning a drug into a genetic tool, and starting the whole field.",
      still_open:"The paper frames rapamycin as an immunosuppressant that blocks T-cell activation. That framing survives eighteen years, until it is inverted (Araki, 2009).", still_open_beginner:"At the time, this drug was seen purely as an immune-suppressing tool — nobody suspected it could also do the opposite under different conditions. That assumption got overturned nearly two decades later." }},

  { pmid:"7518356", year:1994, label:"RAFT1 — mammalian TOR", authors:"Sabatini et al.",
    journal:"Cell", doi:"10.1016/0092-8674(94)90570-3", species:"Mammalian cells", tier:"D",
    title:"RAFT1: a mammalian protein that binds to FKBP12 in a rapamycin-dependent fashion and is homologous to yeast TORs.",
    lineage:{ branch:"A", type:"FOUNDATIONAL", thickness:5, parents:[{pmid:"1715094", relation:"EXTENDS"}],
      unlocked:"The yeast gene has a mammalian counterpart. mTOR exists, and the entire yeast literature becomes relevant to human biology.", unlocked_beginner:"The same gene turns out to exist in humans too — meaning everything learned in yeast could now apply to human biology.", still_open:null }},

  { pmid:"8008069", year:1994, label:"FRAP — parallel find", authors:"Brown, Albers … Schreiber",
    journal:"Nature", doi:"10.1038/369756a0", species:"Mammalian cells", tier:"D",
    title:"A mammalian protein targeted by G1-arresting rapamycin-receptor complex.",
    lineage:{ branch:"A", type:"FOUNDATIONAL", thickness:3, parents:[{pmid:"1715094", relation:"EXTENDS"}],
      unlocked:"Two labs isolate the same protein within weeks by different routes. Parallel discovery signals a ripe question — worth showing, not collapsing into one node.", unlocked_beginner:"A second lab finds the very same protein within weeks, using a different method — a sign this was a question the whole field was closing in on at once.", still_open:null }},

  { pmid:"12150925", year:2002, label:"Raptor", authors:"Kim, Sarbassov … Sabatini",
    journal:"Cell", doi:"10.1016/s0092-8674(02)00808-5", species:"Mammalian cells", tier:"D",
    title:"mTOR interacts with raptor to form a nutrient-sensitive complex that signals to the cell growth machinery.",
    lineage:{ branch:"B", type:"MECHANISM", thickness:5, parents:[{pmid:"7518356", relation:"ENABLES"}],
      unlocked:"mTOR is not a lone kinase but the core of a complex. Raptor is the scaffold that lets mTORC1 reach its substrates.", unlocked_beginner:"mTOR isn't a lone enzyme — it works as part of a larger complex, and Raptor is the scaffold piece that lets it reach the right targets.", still_open:null }},

  { pmid:"12150926", year:2002, label:"Raptor — parallel find", authors:"Hara, Maruki … Yonezawa",
    journal:"Cell", doi:"10.1016/s0092-8674(02)00833-4", species:"Mammalian cells", tier:"D",
    title:"Raptor, a binding partner of target of rapamycin (TOR), mediates TOR action.",
    lineage:{ branch:"B", type:"MECHANISM", thickness:2, parents:[{pmid:"7518356", relation:"ENABLES"}],
      unlocked:"The same complex, back to back in the same issue of Cell, plus C. elegans genetics tying raptor to TOR function in a whole animal.", unlocked_beginner:"Another lab publishes the same discovery side by side, plus evidence in a living worm that this scaffold protein matters for a whole animal, not just cells in a dish.", still_open:null }},

  { pmid:"12408816", year:2002, label:"TORC1 vs TORC2 in yeast", authors:"Loewith … Hall",
    journal:"Mol Cell", doi:"10.1016/s1097-2765(02)00636-6", species:"Yeast", tier:"D",
    title:"Two TOR complexes, only one of which is rapamycin sensitive, have distinct roles in cell growth control.",
    lineage:{ branch:"B", type:"FOUNDATIONAL", thickness:5, parents:[{pmid:"1715094", relation:"EXTENDS"}],
      unlocked:"Yeast reveals the architecture before mammals do: two complexes, and rapamycin only touches one of them. This predicts mTORC2 two years early.", unlocked_beginner:"Yeast reveals the bigger picture two years before mammals do: there are actually two separate TOR complexes, and the drug only blocks one of them.", still_open:null }},

  { pmid:"15268862", year:2004, label:"Rictor / mTORC2", authors:"Sarbassov … Sabatini",
    journal:"Curr Biol", doi:"10.1016/j.cub.2004.06.054", species:"Mammalian cells", tier:"D",
    title:"Rictor, a novel binding partner of mTOR, defines a rapamycin-insensitive and raptor-independent pathway that regulates the cytoskeleton.",
    lineage:{ branch:"B", type:"MECHANISM", thickness:5,
      parents:[{pmid:"12408816", relation:"CONVERGES"},{pmid:"12150925", relation:"CONVERGES"}],
      unlocked:"Two lineages meet: yeast genetics said a second complex should exist, mammalian biochemistry finds it. A convergence node — the shape a citation graph cannot show you.", unlocked_beginner:"Two separate lines of research — yeast genetics and human biochemistry — arrive at the same answer at the same time: the second complex, mTORC2, really exists.", still_open:null }},

  { pmid:"15718470", year:2005, label:"mTORC2 phosphorylates Akt", authors:"Sarbassov, Guertin, Ali & Sabatini",
    journal:"Science", doi:"10.1126/science.1106148", species:"Mammalian cells", tier:"D",
    title:"Phosphorylation and regulation of Akt/PKB by the rictor-mTOR complex.",
    lineage:{ branch:"B", type:"MECHANISM", thickness:5, parents:[{pmid:"15268862", relation:"ENABLES"}],
      unlocked:"mTORC2 is the missing S473 kinase for Akt. The pathway closes on itself, and mTORC2 becomes a metabolic node you cannot casually switch off.", unlocked_beginner:"mTORC2 turns out to be the missing piece that fully switches on Akt, a major growth signal — tying the two mTOR complexes into one system that can't easily be split apart.",
      still_open:"The origin of the selectivity problem: chronic rapalog dosing eventually reaches mTORC2, which is where the insulin resistance and hyperlipidaemia seen in the clinic come from.", still_open_beginner:"This is also where a long-term downside starts: give the drug for a long time and it eventually reaches this second complex too, causing the blood-sugar and cholesterol side effects seen in patients." }},

  { pmid:"12869586", year:2003, label:"TSC2 is a GAP for Rheb", authors:"Inoki, Li, Xu & Guan",
    journal:"Genes Dev", doi:"10.1101/gad.1110003", species:"Mammalian cells", tier:"D",
    title:"Rheb GTPase is a direct target of TSC2 GAP activity and regulates mTOR signaling.",
    lineage:{ branch:"C", type:"MECHANISM", thickness:5, parents:[{pmid:"7518356", relation:"ENABLES"}],
      unlocked:"The growth-factor input is wired: Akt relieves TSC1/TSC2, TSC2 stops shutting off Rheb, Rheb turns on mTORC1. A disease gene becomes a pathway component.", unlocked_beginner:"The final piece connecting growth-factor signals to mTOR clicks into place: Akt turns off a brake (TSC), which then releases the gas pedal (Rheb) that switches mTOR on.", still_open:null }},

  { pmid:"14651849", year:2003, label:"AMPK phosphorylates TSC2", authors:"Inoki, Zhu & Guan",
    journal:"Cell", doi:"10.1016/s0092-8674(03)00929-2", species:"Mammalian cells", tier:"D",
    title:"TSC2 mediates cellular energy response to control cell growth and survival.",
    lineage:{ branch:"C", type:"MECHANISM", thickness:4, parents:[{pmid:"12869586", relation:"EXTENDS"}],
      unlocked:"Energy status enters the pathway. Low ATP → AMPK → TSC2 → mTORC1 off. The mechanistic bridge to caloric restriction and, later, to metformin.", unlocked_beginner:"The cell's low-energy alarm (AMPK) is now wired into the same brake: when energy runs low, AMPK reinforces the brake on mTOR — the mechanistic link to calorie restriction, and later to the diabetes drug metformin.", still_open:null }},

  { pmid:"18497260", year:2008, label:"Rags sense amino acids", authors:"Sancak … Bar-Peled, Sabatini",
    journal:"Science", doi:"10.1126/science.1157535", species:"Mammalian cells", tier:"D",
    title:"The Rag GTPases bind raptor and mediate amino acid signaling to mTORC1.",
    lineage:{ branch:"C", type:"MECHANISM", thickness:5, parents:[{pmid:"12150925", relation:"ENABLES"}],
      unlocked:"Amino acids act through a separate input that works by moving mTORC1, not by activating it directly. Location becomes a mechanism.", unlocked_beginner:"Amino acids turn out to switch mTOR on in an unusual way — not by directly activating it, but by moving it to a different spot inside the cell where it can then be turned on.", still_open:null }},

  { pmid:"20381137", year:2010, label:"mTORC1 on the lysosome", authors:"Sancak, Bar-Peled, Zoncu … Sabatini",
    journal:"Cell", doi:"10.1016/j.cell.2010.02.024", species:"Mammalian cells", tier:"D",
    title:"Ragulator-Rag complex targets mTORC1 to the lysosomal surface and is necessary for its activation by amino acids.",
    lineage:{ branch:"C", type:"MECHANISM", thickness:5, parents:[{pmid:"18497260", relation:"EXTENDS"}],
      unlocked:"The lysosome — long treated as the cell's rubbish bin — turns out to be the platform where growth is decided.", unlocked_beginner:"The lysosome — long thought of as just the cell's trash bin — turns out to be the platform where the decision to grow gets made.", still_open:null }},

  { pmid:"22053050", year:2011, label:"v-ATPase: inside-out", authors:"Zoncu, Bar-Peled, Efeyan … Sabatini",
    journal:"Science", doi:"10.1126/science.1207056", species:"Mammalian cells", tier:"D",
    title:"mTORC1 senses lysosomal amino acids through an inside-out mechanism that requires the vacuolar H(+)-ATPase.",
    lineage:{ branch:"C", type:"MECHANISM", thickness:3, parents:[{pmid:"20381137", relation:"EXTENDS"}],
      unlocked:"The signal starts inside the lysosomal lumen and is read outwards. Counter-intuitive, and it relocates where 'nutrient status' physically lives.", unlocked_beginner:"The nutrient signal starts from inside the lysosome and gets read from the outside — a surprising, inside-out way for a cell to sense its surroundings.", still_open:null }},

  { pmid:"23723238", year:2013, label:"GATOR1 / GATOR2", authors:"Bar-Peled, Chantranupong … Sabatini",
    journal:"Science", doi:"10.1126/science.1232044", species:"Mammalian cells", tier:"D",
    title:"A Tumor suppressor complex with GAP activity for the Rag GTPases that signal amino acid sufficiency to mTORC1.",
    lineage:{ branch:"C", type:"MECHANISM", thickness:4, parents:[{pmid:"18497260", relation:"EXTENDS"}],
      unlocked:"The negative arm of amino-acid sensing — and it is mutated in human cancers. Also the handle that makes the leucine sensor findable.", unlocked_beginner:"A whole new set of brake-and-release proteins for amino-acid sensing is found — some of which are mutated in human cancers, and one that later leads researchers to the actual leucine sensor.", still_open:null }},

  { pmid:"26449471", year:2015, label:"Sestrin2: leucine sensor", authors:"Wolfson, Chantranupong … Sabatini",
    journal:"Science", doi:"10.1126/science.aab2674", species:"Mammalian cells", tier:"D",
    title:"Sestrin2 is a leucine sensor for the mTORC1 pathway.",
    lineage:{ branch:"C", type:"MECHANISM", thickness:4, parents:[{pmid:"23723238", relation:"ENABLES"}],
      unlocked:"A twenty-year question closes: a protein binds leucine directly, with a Kd matching the concentration at which leucine half-maximally activates mTORC1. The cell has a leucine receptor.", unlocked_beginner:"A twenty-year mystery is solved: a protein is found that grabs onto leucine directly, at just the concentration where leucine is known to switch mTOR on. The cell really does have a dedicated leucine detector.", still_open:null }},

  { pmid:"19211835", year:2009, label:"mTORC1 → ULK1: autophagy", authors:"Hosokawa … Mizushima",
    journal:"Mol Biol Cell", doi:"10.1091/mbc.e08-12-1248", species:"Mammalian cells", tier:"D",
    title:"Nutrient-dependent mTORC1 association with the ULK1-Atg13-FIP200 complex required for autophagy.",
    lineage:{ branch:"D", type:"MECHANISM", thickness:5, parents:[{pmid:"12150925", relation:"ENABLES"}],
      unlocked:"The direct molecular link from nutrient status to self-digestion — the wire connecting mTOR to nearly every longevity mechanism people care about.", unlocked_beginner:"The direct wiring between “nutrients are available” and “stop the cell's self-cleanup process” is found — the same wire connects mTOR to nearly every process linked to ageing that people care about.",
      still_open:"Nutrient input is dynamic, but this is measured as an on/off state. Whether the timing of mTORC1 release, rather than its average level, sets autophagic flux is unsettled.", still_open_beginner:"This was measured as a simple on/off state. Whether the timing of the signal — not just its average strength — matters for how much cleanup happens is still unresolved." }},

  { pmid:"22552098", year:2012, label:"4E-BPs and TOP mRNAs", authors:"Thoreen, Chantranupong … Sabatini",
    journal:"Nature", doi:"10.1038/nature11083", species:"Mouse cells", tier:"D",
    title:"A unifying model for mTORC1-mediated regulation of mRNA translation.",
    lineage:{ branch:"D", type:"REVERSAL", thickness:4, parents:[{pmid:"12150925", relation:"ENABLES"}],
      unlocked:"Ribosome profiling under a full mTOR inhibitor shows the translational program is almost entirely TOP-motif mRNAs, controlled by the 4E-BPs. Earlier models built on 5'UTR complexity find no support.", unlocked_beginner:"Blocking mTOR completely and checking exactly which genes stop being read shows the effect runs almost entirely through one protein family (4E-BPs) — overturning an earlier, more complicated model.",
      still_open:"Rapamycin only partially inhibits 4E-BP phosphorylation — so twenty years of rapamycin data were reading a partial inhibitor as if it were complete.", still_open_beginner:"The standard drug (rapamycin) only partly blocks that same protein family — meaning two decades of studies using rapamycin were seeing a partial effect and treating it as if it were the complete picture." }},

  { pmid:"22343943", year:2012, label:"mTORC1 → TFEB", authors:"Settembre, Zoncu … Sabatini, Ballabio",
    journal:"EMBO J", doi:"10.1038/emboj.2012.32", species:"Mammalian cells", tier:"D",
    title:"A lysosome-to-nucleus signalling mechanism senses and regulates the lysosome via mTOR and TFEB.",
    lineage:{ branch:"D", type:"MECHANISM", thickness:4,
      parents:[{pmid:"20381137", relation:"CONVERGES"},{pmid:"19211835", relation:"EXTENDS"}],
      unlocked:"The sensing branch and the autophagy branch fuse: mTORC1 sits on the lysosome and phosphorylates the transcription factor that builds more lysosomes.", unlocked_beginner:"Two separate parts of the story merge into one: mTOR, sitting on the lysosome, directly controls the master switch (TFEB) that builds more lysosomes and turns on cleanup.",
      still_open:"TFEB shuttles in and out of the nucleus — an inherently time-dependent readout, and a natural place to test whether pulse frequency carries information.", still_open_beginner:"This master switch moves in and out of the cell's nucleus over time — a natural place to ask whether the rhythm of the signal, not just its level, carries meaningful information." }},

  { pmid:"14668850", year:2003, label:"Lifespan+ in C. elegans", authors:"Vellai … Müller",
    journal:"Nature", doi:"10.1038/426620a", species:"C. elegans", tier:"C",
    title:"Genetics: influence of TOR kinase on lifespan in C. elegans.",
    lineage:{ branch:"E", type:"LIFESPAN", thickness:5, parents:[{pmid:"1715094", relation:"EXTENDS"}],
      unlocked:"The first time TOR is tied to how long an animal lives. The pathway stops being about cell size and starts being about ageing.", unlocked_beginner:"For the first time, this pathway is linked to how long an animal lives — turning it from a story about cell size into a story about ageing.", still_open:null }},

  { pmid:"15186745", year:2004, label:"Lifespan+ in Drosophila", authors:"Kapahi, Zid … Benzer",
    journal:"Curr Biol", doi:"10.1016/j.cub.2004.03.059", species:"Drosophila", tier:"C",
    title:"Regulation of lifespan in Drosophila by modulation of genes in the TOR signaling pathway.",
    lineage:{ branch:"E", type:"LIFESPAN", thickness:4, parents:[{pmid:"14668850", relation:"EXTENDS"}],
      unlocked:"Replication in a second organism — and the effect depends on nutritional state, the first strong hint that TOR is the mechanism behind dietary restriction.", unlocked_beginner:"The same lifespan effect shows up in a second species, and it depends on how much food the animal gets — the first strong clue that this pathway is the actual mechanism behind the benefits of calorie restriction.", still_open:null }},

  { pmid:"16293764", year:2005, label:"Restriction acts via TOR", authors:"Kaeberlein … Kennedy",
    journal:"Science", doi:"10.1126/science.1115535", species:"Yeast", tier:"C",
    title:"Regulation of yeast replicative life span by TOR and Sch9 in response to nutrients.",
    lineage:{ branch:"E", type:"LIFESPAN", thickness:4, parents:[{pmid:"1715094", relation:"EXTENDS"}],
      unlocked:"Deleting TOR1 adds nothing on top of caloric restriction — they are the same road. Restriction stops being a mystery and becomes a pathway.", unlocked_beginner:"Removing the TOR gene and restricting calories turn out to do the exact same thing — they don't add up, because they're really the same intervention.", still_open:null }},

  { pmid:"19587680", year:2009, label:"Mouse lifespan +14%", authors:"Harrison, Strong … Miller",
    journal:"Nature", doi:"10.1038/nature08221", species:"Mouse", tier:"C",
    title:"Rapamycin fed late in life extends lifespan in genetically heterogeneous mice.",
    lineage:{ branch:"E", type:"LIFESPAN", thickness:5,
      parents:[{pmid:"14668850", relation:"EXTENDS"},{pmid:"15186745", relation:"EXTENDS"},{pmid:"16293764", relation:"EXTENDS"}],
      unlocked:"A drug started at 600 days — roughly a 60-year-old human — extends life in a mammal: about 14% in females and 9% in males, replicated at three independent sites in genetically heterogeneous mice. The heaviest node in the tree.", unlocked_beginner:"A drug given to mice as old as a 60-year-old human still extends their lives — about 14% in females, 9% in males — and three independent labs get the same result. The single biggest result in this whole field.",
      still_open:"It is a mouse. Seventeen years on, no human trial has tested a lifespan or healthspan endpoint. Everything above this node on the human side is inference.", still_open_beginner:"This is still a mouse result. Even years later, no human trial has directly tested whether the drug extends human lifespan or healthspan — everything built on top of this finding, on the human side, is inference." }},

  { pmid:"17538086", year:2007, label:"Temsirolimus, phase 3", authors:"Hudes … Motzer",
    journal:"N Engl J Med", doi:"10.1056/NEJMoa066838", species:"Human", tier:"B",
    title:"Temsirolimus, interferon alfa, or both for advanced renal-cell carcinoma.",
    lineage:{ branch:"F", type:"TRANSLATION", thickness:4, parents:[{pmid:"7518356", relation:"ENABLES"}],
      unlocked:"The first hard human outcome for an mTOR inhibitor: median overall survival 10.9 months versus 7.3 on interferon. Also the first clean human safety picture — rash, oedema, hyperglycaemia, hyperlipidaemia.", unlocked_beginner:"The first solid evidence in actual patients: a related drug helps people with advanced kidney cancer live longer, and doctors get their first clear picture of its side effects (rash, swelling, high blood sugar, high cholesterol).",
      still_open:"An oncology endpoint in sick patients says almost nothing about dosing a healthy person for decades.", still_open_beginner:"This trial was in very sick cancer patients — it says almost nothing about what happens if a healthy person takes the drug for decades." }},

  { pmid:"19543266", year:2009, label:"Rapamycin boosts memory", authors:"Araki … Ahmed",
    journal:"Nature", doi:"10.1038/nature08155", species:"Mouse & primate", tier:"C",
    title:"mTOR regulates memory CD8 T-cell differentiation.",
    lineage:{ branch:"F", type:"REVERSAL", thickness:5,
      parents:[{pmid:"1715094", relation:"CONTRADICTS"},{pmid:"12150925", relation:"ENABLES"}],
      unlocked:"The drug filed for eighteen years as an immunosuppressant makes memory T cells better — in quantity and in quality, in mice and in macaques. The field's assumption inverts.", unlocked_beginner:"A drug that had been used for 18 years purely to suppress the immune system turns out to also make immune memory cells work better — flipping the field's assumption about what it does.",
      still_open:"Immunosuppression and immune enhancement depend on dose and timing. Nobody has mapped where that boundary sits in humans.", still_open_beginner:"Whether the drug suppresses or boosts immunity seems to depend on dose and timing — but nobody has mapped out exactly where that line sits in people." }},

  { pmid:"22149876", year:2011, label:"Everolimus, BOLERO-2", authors:"Baselga … Hortobagyi",
    journal:"N Engl J Med", doi:"10.1056/NEJMoa1109653", species:"Human", tier:"B",
    title:"Everolimus in postmenopausal hormone-receptor-positive advanced breast cancer.",
    lineage:{ branch:"F", type:"TRANSLATION", thickness:3, parents:[{pmid:"17538086", relation:"EXTENDS"}],
      unlocked:"Progression-free survival roughly doubles when everolimus is added to endocrine therapy. mTOR inhibition becomes standard oncology care, and its side-effect profile gets characterised in thousands of people.", unlocked_beginner:"Adding this drug to standard hormone therapy roughly doubles how long advanced breast cancer stays under control — the drug becomes a normal part of cancer treatment, and doctors learn its side effects in thousands of patients.", still_open:null }},

  { pmid:"25540326", year:2014, label:"RAD001 in older adults", authors:"Mannick … Klickstein",
    journal:"Sci Transl Med", doi:"10.1126/scitranslmed.3009892", species:"Human", tier:"B",
    title:"mTOR inhibition improves immune function in the elderly.",
    lineage:{ branch:"F", type:"TRANSLATION", thickness:5,
      parents:[{pmid:"19543266", relation:"EXTENDS"},{pmid:"19587680", relation:"EXTENDS"}],
      unlocked:"The first time the ageing branch touches a human. Low-dose everolimus raises influenza-vaccine response by about 20% in older adults and lowers PD-1 on T cells.", unlocked_beginner:"For the first time, the “ageing” side of this research reaches an actual human: a low dose of the drug improves older adults' response to a flu vaccine by about 20% and reduces a marker of immune exhaustion.",
      still_open:"The endpoint is a surrogate — antibody titre, not health, not lifespan.", still_open_beginner:"The measurement here is a stand-in (antibody levels), not an actual health outcome and not lifespan." }},

  { pmid:"29997249", year:2018, label:"Phase 2a: fewer infections", authors:"Mannick … Klickstein",
    journal:"Sci Transl Med", doi:"10.1126/scitranslmed.aaq1564", species:"Human", tier:"B",
    title:"TORC1 inhibition enhances immune function and reduces infections in the elderly.",
    lineage:{ branch:"F", type:"TRANSLATION", thickness:4, parents:[{pmid:"25540326", relation:"EXTENDS"}],
      unlocked:"264 older adults, six weeks of low-dose TORC1 inhibition, and a significant drop in infections reported over the following year. The strongest human signal the field has produced.", unlocked_beginner:"264 older adults took a low dose for six weeks, and over the following year they reported significantly fewer infections — the strongest positive human signal this field has produced so far.",
      still_open:"Phase 2a, self-reported infections. Closer to health than a titre — but still not ageing.", still_open_beginner:"This was an early-phase trial, and infections were self-reported by participants — closer to a real health outcome than the vaccine study, but still not the same as measuring ageing itself." }},

  { pmid:"33977284", year:2021, label:"Phase 3 misses endpoint", authors:"Mannick … Shergill",
    journal:"Lancet Healthy Longev", doi:"10.1016/S2666-7568(21)00062-3", species:"Human", tier:"B",
    title:"Targeting the biology of ageing with mTOR inhibitors to improve immune function in older adults: phase 2b and phase 3 randomised trials.",
    lineage:{ branch:"F", type:"NULL", thickness:5, parents:[{pmid:"29997249", relation:"CONTRADICTS"}],
      unlocked:"1,024 participants. RTB101 did not reduce clinically symptomatic respiratory illness — 26% versus 25%, p=0.65. The antiviral genes still switched on; the clinical outcome did not move.", unlocked_beginner:"In a trial of over 1,000 people, the drug switched on the right antiviral genes just like before — but it did not actually reduce how many people got sick with respiratory illness (26% vs. 25%, essentially no difference).",
      still_open:"The biomarker moved and the patient did not. This is the node most databases would quietly omit, and the reason the Atlas records failures at the same weight as successes.", still_open_beginner:"The lab measurement improved, but the patients didn't feel it. Most databases would quietly leave a result like this out — this atlas keeps failures visible on purpose, next to the successes." }},

  { pmid:"27279227", year:2016, label:"RapaLink-1", authors:"Rodrik-Outmezguine … Rosen, Shokat",
    journal:"Nature", doi:"10.1038/nature17963", species:"Cells & mouse", tier:"C",
    title:"Overcoming mTOR resistance mutations with a new-generation mTOR inhibitor.",
    lineage:{ branch:"F", type:"TOOL", thickness:5,
      parents:[{pmid:"15718470", relation:"ENABLES"},{pmid:"17538086", relation:"CONTRADICTS"}],
      unlocked:"Linking the rapamycin pocket to the kinase pocket in a single molecule defeats resistance mutations that beat both earlier generations — and it is the chemistry that makes true mTORC1 selectivity thinkable. Direct ancestor of the bi-steric inhibitors now in human trials.", unlocked_beginner:"Chemists link two separate drug parts into a single molecule that gets around the resistance mutations that beat both earlier generations of the drug — the chemistry that first makes a much more selective mTOR-blocker seem possible, and the direct ancestor of the newer drugs now in human trials.",
      still_open:"Selectivity in cells is not selectivity in a person dosed for years.", still_open_beginner:"Being selective in a lab dish is not the same as staying selective inside a person taking the drug for years." }},

  /* ---- Open questions: buds, not findings. No PMID. ---- */
  { pmid:"OQ-SELECTIVITY", year:2026, label:"mTORC1-only, in humans?", authors:null, species:"Open question", tier:null,
    lineage:{ branch:"B", type:"OPEN", thickness:1,
      parents:[{pmid:"15718470", relation:"OPENS"},{pmid:"27279227", relation:"OPENS"}], unlocked:null,
      still_open:"Bi-steric inhibitors spare mTORC2 acutely. Whether that holds under chronic human dosing — and whether sparing mTORC2 removes the metabolic toxicity — is still open; the Phase 1 signal (SCH2025) is consistent with it but was uncontrolled.", still_open_beginner:"The newest drugs seem to spare the second mTOR complex, at least in short lab tests. Whether that holds up when people take the drug for years — and whether sparing that complex actually removes the blood-sugar side effect — is still an open question. Early human data is encouraging but the trial had no comparison group, so it isn't proof yet." }},

  { pmid:"OQ-FREQUENCY", year:2026, label:"Frequency, not level?", authors:null, species:"Open question", tier:null,
    lineage:{ branch:"D", type:"OPEN", thickness:1,
      parents:[{pmid:"22552098", relation:"OPENS"},{pmid:"19211835", relation:"OPENS"},{pmid:"22343943", relation:"OPENS"}], unlocked:null,
      still_open:"Every mechanism on this branch was measured at steady state. If mTORC1 oscillates with feeding, growth-factor bursts and the cell cycle, then two cells with identical average activity could have opposite fates. Almost nothing in the literature is designed to detect that.", still_open_beginner:"Every measurement so far has looked at the average, steady level of mTOR activity. But if activity actually rises and falls in pulses — with meals, growth signals, or the cell cycle — then two cells with the exact same average could be behaving completely differently. Almost no study has been designed to catch that." }},

  { pmid:"OQ-CHRONO", year:2026, label:"Does timing matter?", authors:null, species:"Open question", tier:null,
    lineage:{ branch:"F", type:"OPEN", thickness:1,
      parents:[{pmid:"33977284", relation:"OPENS"},{pmid:"27279227", relation:"OPENS"}], unlocked:null,
      still_open:"Every human trial so far dosed on a fixed schedule chosen for convenience. If mTORC1 is phase-dependent, dose timing is an untested variable sitting inside every null result — including the one directly below this bud.", still_open_beginner:"Every human trial so far picked a dosing schedule for convenience, not because of biology. If mTOR activity naturally rises and falls throughout the day, then when you take the drug — not just how much — might matter, and that's never been properly tested, including in the trial that failed just above this point." }},

  { pmid:"OQ-HUMAN", year:2026, label:"Human healthspan?", authors:null, species:"Open question", tier:null,
    lineage:{ branch:"E", type:"OPEN", thickness:1,
      parents:[{pmid:"19587680", relation:"OPENS"},{pmid:"33977284", relation:"OPENS"}], unlocked:null,
      still_open:"Untested — not disputed, not emerging. No completed trial has used a human ageing endpoint. This is the question the Atlas exists to keep visible.", still_open_beginner:"Nobody has ever run a human trial that measured ageing itself as the outcome. It's not that the idea failed — it just hasn't been tested yet. That untested gap is the whole reason this atlas exists." }}
];

/* ---------- layout ----------
   Glyphs sit on their exact year, on the centre line of their column.
   Only the label cards are packed apart and tethered back, so the time
   axis is never distorted to make room for text.                        */
const Y0 = 1974, Y1 = 2027;
const PX_PER_YEAR = 27;
const TOP = 104, LEFT = 84, LANE_W = 292, RIGHT_PAD = 150;
const W = LEFT + BRANCHES.length * LANE_W + RIGHT_PAD;
const H = TOP + (Y1 - Y0) * PX_PER_YEAR + 40;

const yOf = y => TOP + (y - Y0) * PX_PER_YEAR;
const laneX = b => LEFT + LANE_W / 2 + BRANCHES.findIndex(x => x.id === b) * LANE_W;

const byId = new Map(LINEAGE.map(d => [d.pmid, d]));
const pos = new Map(), card = new Map();
const CARD_H = 24, CARD_GAP = 28;

BRANCHES.forEach(br => {
  const nodes = LINEAGE.filter(d => d.lineage.branch === br.id).sort((a, b) => a.year - b.year);
  let prev = -Infinity;
  nodes.forEach(d => {
    const y = yOf(d.year);
    pos.set(d.pmid, { x: laneX(br.id), y });
    const cy = Math.max(y, prev + CARD_GAP);
    card.set(d.pmid, cy);
    prev = cy;
  });
});

/* ---------- derived stats ---------- */
const findings   = LINEAGE.filter(d => d.lineage.type !== "OPEN");
const humanNodes = findings.filter(d => d.tier === "B");
const openNodes  = LINEAGE.filter(d => d.lineage.type === "OPEN");
const reversals  = findings.filter(d => d.lineage.type === "REVERSAL" || d.lineage.type === "NULL");
const ageingEndpoints = humanNodes.filter(d => /lifespan|healthspan/i.test(d.lineage.unlocked || "")).length;
const span = Math.max(...findings.map(d => d.year)) - Math.min(...findings.map(d => d.year));

document.getElementById("lineageStats").innerHTML = [
  [findings.length, "landmark studies"],
  [span + " yrs", "soil sample to clinic"],
  [humanNodes.length, "H — human studies"],
  [ageingEndpoints, "human ageing endpoints", true],
  [reversals.length, "reversals & nulls"],
  [openNodes.length, "questions still open"]
].map(([n, l, warn]) =>
  `<div class="stat"><span class="n${warn ? " warn" : ""}">${n}</span><span class="l">${l}</span></div>`
).join("");

/* ---------- svg ---------- */
const NS = "http://www.w3.org/2000/svg";
const svg = document.getElementById("lineageTree");
svg.setAttribute("viewBox", `0 0 ${W} ${H}`);
svg.setAttribute("width", W);
svg.setAttribute("height", H);

const el = (tag, attrs = {}, text) => {
  const n = document.createElementNS(NS, tag);
  for (const k in attrs) n.setAttribute(k, attrs[k]);
  if (text != null) n.textContent = text;
  return n;
};

for (let y = 1975; y <= 2025; y += 5) {
  svg.appendChild(el("line", { class:"yr-rule", x1:LEFT - 10, x2:W - 30, y1:yOf(y), y2:yOf(y) }));
  svg.appendChild(el("text", { class:"yr", x:LEFT - 22, y:yOf(y) + 4, "text-anchor":"end" }, y));
}
svg.appendChild(el("text", { class:"yr", x:LEFT - 22, y:yOf(2026) + 4, "text-anchor":"end" }, "now"));

BRANCHES.forEach(br => {
  const x = laneX(br.id);
  svg.appendChild(el("line", { class:"lane-rule", x1:x, x2:x, y1:TOP - 34, y2:H - 30 }));
  const t = el("text", { class:"lane-head", x:x, y:44, "text-anchor":"middle" });
  t.appendChild(el("tspan", { class:"idx" }, br.id + " · "));
  t.appendChild(el("tspan", {}, br.name));
  svg.appendChild(t);
  svg.appendChild(el("text", { class:"lane-note", x:x, y:64, "text-anchor":"middle" }, br.note));
});

/* signature: the translation gap */
const gapTop = yOf(2009), gapBot = yOf(2026), gapW = 244;
const gx = laneX("E") - gapW / 2;
svg.appendChild(el("rect", { class:"gap-band", x:gx, y:gapTop, width:gapW, height:gapBot - gapTop, rx:1 }));
const rot = (cls, dx, txt) => {
  const px = gx + dx, py = gapTop + 120;
  svg.appendChild(el("text", { class:cls, x:px, y:py, transform:`rotate(-90 ${px} ${py})`, "text-anchor":"start" }, txt));
};
rot("gap-lbl", 17, "The translation gap");
rot("gap-sub", 35, "17 years since the mouse result. No completed human trial has shown a lifespan or healthspan benefit.");

/* edges */
const edgeEls = [];
LINEAGE.forEach(child => {
  child.lineage.parents.forEach(p => {
    const a = pos.get(p.pmid), b = pos.get(child.pmid);
    if (!a || !b) return;
    const dy = (b.y - a.y) * 0.42;
    const parent = byId.get(p.pmid);
    const path = el("path", {
      class: "edge " + p.relation.toLowerCase(),
      d: `M ${a.x} ${a.y} C ${a.x} ${a.y + dy}, ${b.x} ${b.y - dy}, ${b.x} ${b.y}`,
      "stroke-width": p.relation === "OPENS" ? 1.4 : 1 + (parent ? parent.lineage.thickness : 1) * 0.4
    });
    path.dataset.from = p.pmid;
    path.dataset.to = child.pmid;
    svg.appendChild(path);
    edgeEls.push(path);
  });
});

/* nodes */
const glyph = (type, x, y) => {
  switch (type) {
    case "TOOL":         return el("rect",    { class:"glyph", x:x-7, y:y-7, width:14, height:14, rx:1 });
    case "LIFESPAN":     return el("polygon", { class:"glyph", points:`${x},${y-9} ${x+8},${y+6} ${x-8},${y+6}` });
    case "TRANSLATION":
    case "NULL":         return el("polygon", { class:"glyph", points:`${x},${y-9} ${x+8},${y} ${x},${y+9} ${x-8},${y}` });
    case "FOUNDATIONAL": return el("circle",  { class:"glyph", cx:x, cy:y, r:9 });
    case "OPEN":         return el("circle",  { class:"glyph bud-pulse", cx:x, cy:y, r:9 });
    default:             return el("circle",  { class:"glyph", cx:x, cy:y, r:6.5 });
  }
};

const PAD = 11, GAP_GLYPH = 17;
const nodeEls = new Map();

LINEAGE.forEach(d => {
  const { x, y } = pos.get(d.pmid);
  const cy = card.get(d.pmid);
  const t = d.lineage.type;
  const isOpen = t === "OPEN";
  const cls = ["node"];
  if (isOpen) cls.push("bud");
  else {
    cls.push("t-" + d.tier.toLowerCase());
    if (t === "NULL") cls.push("nul");
    else if (t === "REVERSAL") cls.push("rev");
  }

  const g = el("g", { class:cls.join(" "), tabindex:"0", role:"button",
                      "aria-label":`${isOpen ? "Open question" : d.year}. ${d.label}` });

  const yrTxt = isOpen ? "open" : String(d.year);
  const cardW = PAD + yrTxt.length * 6.1 + 9 + d.label.length * 6.7 + PAD;
  const cx = x + GAP_GLYPH;

  if (Math.abs(cy - y) > 1)
    g.appendChild(el("path", { class:"tether", d:`M ${x + 7} ${y} L ${cx - 4} ${cy}` }));

  g.appendChild(el("rect", { class:"card", x:cx, y:cy - CARD_H/2, width:cardW, height:CARD_H, rx:1 }));
  g.appendChild(el("text", { class:"card-yr", x:cx + PAD, y:cy + 4 }, yrTxt));
  g.appendChild(el("text", { class:"lbl", x:cx + PAD + yrTxt.length * 6.1 + 9, y:cy + 4.5 }, d.label));

  g.appendChild(glyph(t, x, y));
  g.appendChild(el("circle", { class:"hit", cx:x, cy:y, r:15 }));

  g.addEventListener("click", () => select(d.pmid));
  g.addEventListener("keydown", e => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); select(d.pmid); }});
  g.addEventListener("mouseenter", () => highlight(d.pmid));
  g.addEventListener("mouseleave", () => { if (!selected) clearHighlight(); else highlight(selected); });

  svg.appendChild(g);
  nodeEls.set(d.pmid, g);
});

/* --- highlight / select --- */
let selected = null;

function neighbours(pmid){
  const s = new Set([pmid]);
  edgeEls.forEach(e => {
    if (e.dataset.to === pmid) s.add(e.dataset.from);
    if (e.dataset.from === pmid) s.add(e.dataset.to);
  });
  return s;
}
function highlight(pmid){
  const keep = neighbours(pmid);
  nodeEls.forEach((g, id) => g.classList.toggle("dim", !keep.has(id)));
  edgeEls.forEach(e => {
    const on = e.dataset.to === pmid || e.dataset.from === pmid;
    e.classList.toggle("lit", on);
    e.classList.toggle("dim", !on);
  });
}
function clearHighlight(){
  nodeEls.forEach(g => g.classList.remove("dim"));
  edgeEls.forEach(e => e.classList.remove("lit","dim"));
}

const REL_COPY = {
  ENABLES:"enabled by", EXTENDS:"extends", CONVERGES:"converges from",
  CONTRADICTS:"overturns", OPENS:"grows out of"
};
/* keys are the stored internal ids, values are the display codes -- see tierMeta */
const TIER_NAME = { A:"S — synthesis of human data", B:"H — human study", C:"A — animal model", D:"M — molecular" };
const panel = document.getElementById("lineagePanel");

function select(pmid){
  selected = pmid;
  nodeEls.forEach(g => g.classList.remove("sel"));
  nodeEls.get(pmid).classList.add("sel");
  highlight(pmid);
  panel.innerHTML = render(byId.get(pmid));
  panel.querySelectorAll("[data-goto]").forEach(a =>
    a.addEventListener("click", () => select(a.dataset.goto)));
  if (window.innerWidth <= 1000) panel.scrollIntoView({ behavior:"smooth", block:"start" });
}

function render(d){
  const L = d.lineage;
  const isOpen = L.type === "OPEN";
  const kids = LINEAGE.filter(k => k.lineage.parents.some(p => p.pmid === d.pmid));
  /* Beginner-register unlocked/still_open text added 2026-08-04 for the
     site-wide reading-level switch; Student and Research keep reading the
     curated fields above unchanged. */
  const LVL = (typeof window !== 'undefined' && window.ATLAS_LEVEL) || 'student';
  const lv = (beginnerText, fallbackText) => (LVL==='beginner' && beginnerText) ? beginnerText : fallbackText;

  let h = isOpen
    ? `<span class="badge tier q">open question</span>`
    : `<span class="badge tier ${d.tier.toLowerCase()}">${TIER_NAME[d.tier]}</span>`;
  h += `<span class="badge">${L.type.toLowerCase()}</span>`;
  h += `<span class="badge">branch ${L.branch}</span>`;
  h += `<h2>${d.label}</h2>`;
  if (!isOpen) h += `<p class="cite">${d.authors} · ${d.journal} · ${d.year}<br>${d.species}<br>${d.title}</p>`;

  if (L.unlocked)   h += `<h3>What it unlocked</h3><p>${lv(L.unlocked_beginner, L.unlocked)}</p>`;
  if (L.still_open) h += `<h3>${isOpen ? "The question" : "What stayed open"}</h3><p class="open-note">${lv(L.still_open_beginner, L.still_open)}</p>`;

  if (L.parents.length){
    h += `<h3>Grew from</h3>` + L.parents.map(p => {
      const par = byId.get(p.pmid);
      return `<p class="rel" data-goto="${p.pmid}"><span class="r ${p.relation.toLowerCase()}">${REL_COPY[p.relation]}</span>${par.label} · ${par.year}</p>`;
    }).join("");
  }
  if (kids.length){
    h += `<h3>Led to</h3>` + kids.map(k => {
      const rel = k.lineage.parents.find(p => p.pmid === d.pmid).relation;
      return `<p class="rel" data-goto="${k.pmid}"><span class="r ${rel.toLowerCase()}">${REL_COPY[rel]}</span>${k.label}${k.lineage.type === "OPEN" ? "" : " · " + k.year}</p>`;
    }).join("");
  }
  if (!isOpen){
    h += `<div class="links">
      <a href="https://pubmed.ncbi.nlm.nih.gov/${d.pmid}/" target="_blank" rel="noopener">PMID ${d.pmid}</a> ·
      <a href="https://doi.org/${d.doi}" target="_blank" rel="noopener">DOI</a>
    </div>`;
  }
  return h;
}

/* Site-wide level switch: if a lineage node is already selected when the
   Beginner/Student/Research control changes, re-render its panel in place
   instead of waiting for the next click. */
document.addEventListener('atlas-level-change', function(){
  if (typeof selected !== 'undefined' && selected && byId.has(selected)) {
    panel.innerHTML = render(byId.get(selected));
    panel.querySelectorAll('[data-goto]').forEach(a =>
      a.addEventListener('click', () => select(a.dataset.goto)));
  }
});

/* ---------- controls ---------- */
const controls = document.getElementById("lineageControls");
const active = new Set(BRANCHES.map(b => b.id));
let humanOnly = false;

BRANCHES.forEach(br => {
  const b = document.createElement("button");
  b.className = "chip"; b.setAttribute("aria-pressed","true");
  b.textContent = br.id + " · " + br.name;
  b.addEventListener("click", () => {
    active.has(br.id) ? active.delete(br.id) : active.add(br.id);
    b.setAttribute("aria-pressed", String(active.has(br.id)));
    applyFilters();
  });
  controls.appendChild(b);
});
const hb = document.createElement("button");
hb.className = "chip solo"; hb.setAttribute("aria-pressed","false");
hb.textContent = "Show human studies (H) only";
hb.addEventListener("click", () => {
  humanOnly = !humanOnly;
  hb.setAttribute("aria-pressed", String(humanOnly));
  applyFilters();
});
controls.appendChild(hb);

function applyFilters(){
  const visible = new Set();
  LINEAGE.forEach(d => {
    const ok = active.has(d.lineage.branch) &&
               (!humanOnly || d.tier === "B" || d.lineage.type === "OPEN");
    if (ok) visible.add(d.pmid);
    nodeEls.get(d.pmid).classList.toggle("dim", !ok);
  });
  edgeEls.forEach(e =>
    e.classList.toggle("dim", !(visible.has(e.dataset.from) && visible.has(e.dataset.to))));
  selected = null;
  nodeEls.forEach(g => g.classList.remove("sel"));
}

/* ---------- legend (derived from the data, so it cannot drift) ---------- */
const tiersUsed = [...new Set(findings.map(d => d.tier))].sort();
document.getElementById("lineageLegend").innerHTML =
  tiersUsed.map(t => `<div><span class="sw" style="background:var(--tier-${t.toLowerCase()})"></span>${TIER_NAME[t]}</div>`).join("") +
  `<div><svg width="18" height="18" viewBox="0 0 18 18"><circle cx="9" cy="9" r="8" fill="none" stroke="var(--danger)" stroke-width="2"></circle></svg>Reversal or null result</div>
   <div><svg width="18" height="18" viewBox="0 0 18 18"><circle cx="9" cy="9" r="7" fill="none" stroke="var(--teal)" stroke-width="1.5" stroke-dasharray="3 3"></circle></svg>Open question</div>
   <div><svg width="34" height="8" viewBox="0 0 34 8"><path d="M0 4H34" stroke="rgba(0,0,0,0.34)" stroke-width="2"></path></svg>Enables / extends</div>
   <div><svg width="34" height="8" viewBox="0 0 34 8"><path d="M0 4H34" stroke="var(--danger)" stroke-width="2" stroke-dasharray="6 4"></path></svg>Overturns</div>`;

/* ---------- zoom / fit-to-frame, wheel zoom, drag-to-pan ---------- */
const canvasEl = document.getElementById("lineageCanvas");
const laneHeaderEl = document.getElementById("lineageLaneHeader");
let baseScale = 1, zoomMult = 1;
const ZMIN = 0.3, ZMAX = 4;
function renderLaneHeader(s){
  if (!laneHeaderEl) return;
  const fs = Math.max(9, Math.min(16, 11 * s));
  const itemW = Math.max(0, LANE_W * s - 8);
  const showNote = itemW > 90;
  const headerH = Math.max(84 * s, showNote ? 42 : 26);
  laneHeaderEl.style.height = headerH + "px";
  laneHeaderEl.style.marginBottom = (-headerH) + "px";
  laneHeaderEl.style.width = (W * s) + "px";
  laneHeaderEl.innerHTML = BRANCHES.map(br => {
    const x = laneX(br.id) * s;
    return '<div class="lhs-item" style="left:' + x + 'px;width:' + itemW + 'px;font-size:' + fs + 'px;">'
      + '<span class="idx">' + br.id + ' &middot; </span><span class="nm">' + br.name + '</span>'
      + (showNote ? '<span class="nt">' + br.note + '</span>' : '')
      + '</div>';
  }).join("");
}
function applyZoom(){
  const s = baseScale * zoomMult;
  svg.style.width = (W * s) + "px";
  svg.style.height = (H * s) + "px";
  renderLaneHeader(s);
}
function computeFit(){
  const cw = canvasEl ? canvasEl.clientWidth - 36 : W;
  const ch = canvasEl ? canvasEl.clientHeight - 36 : H;
  baseScale = (cw > 0 && ch > 0) ? Math.min(cw / W, ch / H, 1) : 1;
  applyZoom();
  if (canvasEl){ canvasEl.scrollLeft = 0; canvasEl.scrollTop = 0; }
}
function zoomBy(factor, cx, cy){
  const oldScale = baseScale * zoomMult;
  const newMult = Math.min(ZMAX, Math.max(ZMIN, zoomMult * factor));
  if (newMult === zoomMult) return;
  let contentX, contentY, ox, oy;
  if (canvasEl){
    const rect = canvasEl.getBoundingClientRect();
    ox = (cx != null ? cx - rect.left : canvasEl.clientWidth / 2);
    oy = (cy != null ? cy - rect.top : canvasEl.clientHeight / 2);
    contentX = canvasEl.scrollLeft + ox;
    contentY = canvasEl.scrollTop + oy;
  }
  zoomMult = newMult;
  applyZoom();
  if (canvasEl){
    const ratio = (baseScale * zoomMult) / oldScale;
    canvasEl.scrollLeft = contentX * ratio - ox;
    canvasEl.scrollTop = contentY * ratio - oy;
  }
}
function zoomFit(){
  zoomMult = 1;
  computeFit();
}
computeFit();
let _fitResizeT = null;
window.addEventListener("resize", () => {
  clearTimeout(_fitResizeT);
  _fitResizeT = setTimeout(computeFit, 150);
});
const _zIn = document.getElementById("lineageZoomIn");
const _zOut = document.getElementById("lineageZoomOut");
const _zFit = document.getElementById("lineageZoomFit");
if (_zIn) _zIn.addEventListener("click", () => zoomBy(1.25));
if (_zOut) _zOut.addEventListener("click", () => zoomBy(0.8));
if (_zFit) _zFit.addEventListener("click", zoomFit);
/* expose the timeline zoom API so the Phase 3 pinch handler can drive it */
window.__lineageZoomBy = zoomBy;
window.__lineageZoomFit = zoomFit;
window.__lineageComputeFit = computeFit;

/* mouse-wheel zoom, centred on the cursor */
if (canvasEl){
  canvasEl.addEventListener("wheel", (e) => {
    e.preventDefault();
    const factor = e.deltaY < 0 ? 1.12 : 1/1.12;
    zoomBy(factor, e.clientX, e.clientY);
  }, { passive: false });

  /* click-and-drag panning */
  let dragging = false, dsx = 0, dsy = 0, dsl = 0, dst = 0;
  canvasEl.addEventListener("mousedown", (e) => {
    if (e.button !== 0) return;
    dragging = true;
    dsx = e.clientX; dsy = e.clientY;
    dsl = canvasEl.scrollLeft; dst = canvasEl.scrollTop;
    canvasEl.classList.add("dragging");
    e.preventDefault();
  });
  window.addEventListener("mousemove", (e) => {
    if (!dragging) return;
    canvasEl.scrollLeft = dsl - (e.clientX - dsx);
    canvasEl.scrollTop = dst - (e.clientY - dsy);
  });
  window.addEventListener("mouseup", () => {
    if (!dragging) return;
    dragging = false;
    canvasEl.classList.remove("dragging");
  });
}
    })();
    