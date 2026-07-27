# Sample Atlas output (Phase 1 MVP)

**Question:** *"I'm interested in transient activation of mTORC1 to promote muscle regeneration without suppressing autophagy. What is known, what remains uncertain, and which experiments would be most informative?"*

*Retrieval: local TF-IDF index over 250 studies (top-10). Synthesis: LLM strictly over the retrieved abstracts. Every claim carries a citation and an evidence tier (A > B > C > D).*

---

### 1. Answer
mTORC1 is **essential** for muscle growth and maintenance: its activation drives muscle protein synthesis and hypertrophy, while its loss leads to dystrophy [1, 2, 4]. But your exact goal — *transient* mTORC1 activation that promotes regeneration while *not suppressing autophagy* — is **not directly tested** in this corpus. On the contrary, the studies show that mTORC1 activation and autophagy suppression are mechanistically **coupled** through the amino-acid→Rag GTPase→mTORC1 pathway [3, 10]. Decoupling those two effects is the crux of the open problem.

### 2. Evidence
- **B – human evidence (strongest here):** Rapamycin (an mTORC1 inhibitor) given before exercise in humans **completely blocked** the resistance-exercise-induced rise in muscle protein synthesis [2, PMID:19188252]. → mTORC1 is causally required for the muscle's anabolic response in humans.
- **C – animal in vivo:** Muscle-specific deletion of raptor (an mTORC1 component), but not rictor (mTORC2), causes progressive dystrophy [1]. Akt/mTOR is necessary and sufficient for hypertrophy; rapamycin blocks hypertrophy without itself causing atrophy of controls [4, DOI:10.1038/ncb1101-1014].
- **D – mechanistic/in vitro:** Amino acids activate mTORC1 and *suppress autophagy* via the Rag GTPases [3, 10]; IGF-1 drives hypertrophy through Akt/mTOR [5].
- **Weakness:** the overwhelming majority of direct mechanistic data is C/D (animal / cell). The only direct human evidence is about *inhibition*, not controlled *activation*. This selection says little about **satellite cells and actual regeneration** (as opposed to hypertrophy).

### 3. Key Papers
- **Drummond MJ et al. (2009)** [PMID:19188252, tier B] — the only direct human evidence that mTORC1 is required for the muscle's anabolic response to loading.
- **Bentzinger CF et al. (2008)** [DOI:10.1016/j.cmet.2008.10.002, tier C] — mTORC1 (raptor), not mTORC2, is indispensable for muscle health.
- **Bodine SC et al. (2001)** [DOI:10.1038/ncb1101-1014, tier C] — Akt/mTOR is necessary and sufficient for hypertrophy; rapamycin blocks it without atrophy of controls.
- **Kim YM et al. (2012)** [PMID:22575674, tier D] — amino acids via Rag-mTORC1 simultaneously trigger growth and *suppress autophagy* → the mechanistic core of the conflict.
- **Bitto A et al. (2016)** [PMID:27549339, tier C] — *transient* rapamycin dosing captures the benefit even without continuous treatment → evidence that "transient" regimens make sense (albeit toward inhibition).

### 4. Knowledge Gaps (what we don't know — and why)
1. **No study in the corpus directly tests *pulsatile/transient activation* of mTORC1 on muscle regeneration while simultaneously measuring autophagic flux** (LC3-II/p62). We know about inhibition (rapamycin) and about sustained activation, not about a controlled pulse. *Why the gap:* tools for time-precise mTORC1 activation (as opposed to rapamycin inhibition) are rare.
2. **Conflicting goals:** mTORC1 drives hypertrophy (desirable) [4], but at the same time suppresses autophagy via ULK1 (undesirable for your goal) [3, 10]. Whether the two branches can be *decoupled* is unresolved in the corpus.
3. **Regeneration ≠ hypertrophy:** the data mostly address fiber size, not satellite cells and repair after injury.

**Testable hypotheses / proposed experiments:**
- **H1 (timing):** *Pulsatile* mTORC1 activation after muscle injury (e.g. a leucine pulse or transient Rheb activation) will improve satellite-cell-mediated regeneration while preserving basal autophagic flux **better than sustained activation**. → Experiment: mouse injury model (cardiotoxin), compare pulsatile vs continuous activation, measure centrally-nucleated fibers + LC3-II/p62 flux (± bafilomycin) + satellite-cell labeling (Pax7).
- **H2 (branch decoupling):** Activating the *downstream* protein-synthesis branch (S6K/4E-BP) while leaving **ULK1 in a dephosphorylated/active state** will allow growth without blocking autophagy. → Experiment: phospho-mimetic/resistant ULK1 mutants in myotubes, measure protein synthesis (puromycin/SUnSET) vs autophagic flux.

---

> **The point (why this is different from Elicit/Consensus):** section 4 does not re-tell what the studies say — it **names what is missing in your curated corpus, shows a contradiction, and proposes two concrete experiments**, all tied to evidence tiers. That is "What we don't know and why."
