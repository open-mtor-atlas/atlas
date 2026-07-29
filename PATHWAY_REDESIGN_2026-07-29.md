# Pathway & Mechanism — complete redesign

**Open mTOR Atlas · 29 July 2026 · Phase 1 shipped, Phases 2–4 specified**

Scope: the Pathway section of the Atlas, rebuilt from scratch rather than optimised.
Corpus at time of writing: 283 studies, 100 curated interactions, 75 molecules, 7 guided routes.

---

## 0. The question asked first

*If EMBL, the Broad and HHMI jointly built the definitive interactive mTOR explorer today, what would it be?*

Not a prettier diagram. Diagrams already exist, and better-funded ones (Reactome, KEGG, WikiPathways, STRING). Copying them means competing on completeness, which a one-person Atlas loses.

The answer we converged on: **the thing nobody has built is a pathway map where every single arrow tells you how much to trust it, and where the map teaches the *logic* of signalling rather than the inventory of proteins.**

Reactome has more reactions and no opinion about evidence quality. Textbook figures have narrative and no citations. Review articles have both and cannot be explored. The gap in the world is a map that is simultaneously:

1. **Explorable** — spatial, zoomable, filterable
2. **Graded** — every claim carries its own evidence and its own uncertainty, visibly
3. **Narrated** — teaches causal chains, not adjacency
4. **Honest about compression** — says out loud when one arrow is really five steps

That fourth point is the one everyone else omits, and it is where the Atlas can be genuinely best-in-class. It costs nothing but discipline.

### Then the comparison with what existed

| | Before | After |
|---|---|---|
| Sources of truth | **Two**, drifting: `MAP_NODES`/`MAP_CORE_EDGES` (42 hand-placed edges) and `ATLAS_EDGES`/`ATLAS_ROUTES` (100 curated edges) | **One**: `pathway/model.json`, generated and validated |
| "Edges" in the main map | Mixed real mechanism with **co-citation** ("linked via shared-study evidence") in the same visual language | Co-citation moved to the Entity Browser and labelled; mechanism edges only in the Explorer |
| Interaction semantics | 5 values: activates / inhibits / required-for / recruits / binds | **20 mechanistic types** (phosphorylation, recruitment, GAP activity, translocation, …) held **separately** from the functional sign |
| Spatial model | None. Boxes on a plane | 8 compartment bands, physical ones marked as such and non-physical ones marked as *not* |
| Layout | Hand-tuned `bows` / `ctrl` constants with the comment *"regenerate them if you move a node"* | Computed: compartment bands + barycentric crossing reduction, deterministic |
| Confidence | One number (study tier), used as if it were confidence in the biology | **Three separate axes**: mechanistic confidence, human relevance, field consensus |
| Uncertainty | `status: Proposed` on 93/100 edges — a field that carried no information | Consensus grading, directness grading, visible dash patterns, explicit boundary conditions |
| Route playback | A dot travelling a preset path, one paragraph of story per route | Step-through, camera framing, and **six answered questions per step** |
| Scenarios | None | Specified with a safety architecture; deliberately not shipped yet (§9) |
| Learning levels | None | Three, switching text only |
| Zoom / pan / search | None (a `min-width:940px` scroll box) | Full camera, search, focus mode, four filter axes |
| Payload | Inside a 1.5 MB `index.html` | Lazy module, fetched on first open |
| Tests | None | 1 150 assertions, mutation-verified |

---

## 1. Redesign philosophy

**Five principles, in priority order. When they conflict, the earlier one wins.**

**1. Never let a simplification become a misconception.** Simplifying is compulsory — the real pathway has thousands of edges. Simplifying *silently* is what makes a teaching resource harmful. Every compression in this map announces itself: `directness: indirect` renders as a long dash and the inspector says *"This arrow spans more than one molecular event. It is drawn as one line for readability, not because it is one step."*

**2. An arrow is not a verb.** The single biggest scientific upgrade here. "Rag GTPases → mTORC1" and "Rheb → mTORC1" were the same kind of arrow before. They are completely different claims: one is recruitment (changes location), the other is allosteric activation (changes catalytic state). A student who cannot tell them apart cannot understand coincidence detection, which *is* the pathway. So `type` and `effect` are separate fields, rendered separately, and validated separately.

**3. Evidence grading and confidence grading are different things.** A mechanism can be structurally resolved, reproduced in six labs, and completely untested in humans. The old model had one letter for both, and the external review (finding F4) caught the Atlas applying its own tier rule inconsistently as a direct result. Now: mechanistic confidence, human relevance, field consensus — three axes, shown side by side, with a sentence explaining why they differ.

**4. Location is a mechanism.** mTOR biology is not chemistry in free solution. It is a set of devices for putting one kinase on one membrane. A map that does not show compartments cannot teach that, and a reader who does not see it will forever wonder why amino acids "activate" mTORC1 without activating it. The compartment bands are the primary organising axis of the whole explorer.

**5. Teach the problem before the solution.** "A activates B" is a fact. "The cell has to avoid building when materials are missing *and* avoid building when the tissue has said don't — so it evolved a switch requiring two independent signals in the same place" is understanding. Every guided-route step therefore answers *why does the cell need this?*, not just *what happens?*

### One thing in the brief we did not follow

The brief specified this overview diagram:

```
Growth Factors ↓ Nutrients ↓ Energy ↓ Stress ↓ mTOR ↓ outputs
```

**We did not build that, because it teaches a chain that does not exist.** Those four inputs are *parallel and independent*: growth factors do not feed into nutrient sensing, and nutrient status does not gate the energy sensor. Drawn in series, a reader infers a causal cascade — and then has to unlearn it the moment they open the Explorer and find four separate arms converging.

Worse, the serial version hides the single most important idea in the pathway. mTORC1 is a **coincidence detector**: nutrients decide *where* it sits, growth factors decide *whether it is on*. That is only visible if the inputs are drawn as independent and converging.

The overview therefore keeps the brief's real requirement — *understand mTOR in fifteen seconds* — with four parallel inputs converging on one hub, outputs fanning out, and an explicit caption: *"The four inputs are drawn side by side because they are parallel and independent. A textbook that stacks them in a single chain is teaching a chain that does not exist."*

The smoke test asserts that sentence is present, so the correction cannot be silently reverted.

---

## 2. Information architecture

The old section was `Pathway → [Entity Map | Mechanism Explorer]`, where "Entity Map" contained *two* maps (a focused knowledge graph and a "Full Pathway Map"), and the full map mixed mechanism with co-citation.

New:

```
Pathway
├── Pathway & Mechanism          ← the redesigned section, lazy-loaded
│   ├── Overview          (landing; 15 seconds to the core idea)
│   ├── Mechanism Explorer (the whole network, spatially organised)
│   ├── Guided Routes     (narrated walkthroughs)
│   └── Scenario Lab      (Phase 2)
└── Entity Browser               ← what the old Entity Map was actually good at
```

**Why the Entity Browser survives but is renamed and demoted.** It does a real job the Explorer does not: browse the corpus *by entity* and reach the study list. But its "Full Pathway Map" drew shared-study co-citation links using the same visual grammar as mechanism arrows. That is the kind of quiet inaccuracy a reviewer finds. Fix: mechanism now lives exclusively in the Explorer, and the Entity Browser's map caption reads *"shared-study links only — for mechanism, see Pathway & Mechanism."* The inbound links from 100+ prerendered `/gene/…` pages keep working.

**Why Overview is the landing view.** Someone arriving at "Pathway" with no context previously got 75 boxes. Cognitive load before motivation. Now they get one paragraph, one diagram, and three doors.

---

## 3. Scientific architecture

### The model

`pathway/model.json` — single source of truth, generated by `build_pathway_model.py`, gated by `validate_pathway.py`.

```
compartments[]  id, name, physical: bool, blurb, sensing_note
bands[]         computed y/height per compartment
nodes[]         id, label, cls, compartment, x, y,
                explain: { beginner, student, research }
interactions[]  id, source, target,
                type,            ← mechanistic verb (20-value vocabulary)
                effect,          ← functional sign
                compartment,     ← WHERE it happens
                directness,      ← direct | indirect | unresolved
                timescale,       ← seconds…chronic | constitutive
                species[], mechanism, teaching_note, boundary,
                evidence: { kind, tiers[], best_tier, supporting[], conflicting[] },
                confidence: { mechanistic, human_relevance, consensus },
                review: { reviewer, reviewed, updated }
routes[]        id, name, summary, story, interactions[], spine[], steps[]
```

### The type vocabulary, and why each distinction is load-bearing

| Type | Distinguishes | Example that would otherwise be wrong |
|---|---|---|
| `recruitment` | moving vs switching on | Rags→mTORC1 **recruits**. Amino acids alone cannot drive growth. |
| `allosteric-activation` | the actual on-switch | Rheb→mTORC1. The only thing that switches the kinase on. |
| `localisation` | a requirement, not a signal | Lysosome→mTORC1 contributes a *place*. |
| `gap-activity` | catalysed nucleotide cycling | GATOR1→Rag, TSC→Rheb, FLCN→RagC/D |
| `dephosphorylation` | reversing a product, not inhibiting an enzyme | PTEN does not touch PI3K. It destroys PI3K's product. |
| `competitive-inhibition` | blocking substrate access | PRAS40 and 4E-BP1 both work this way; neither changes catalytic rate. |
| `allosteric-inhibition` | partial, site-specific block | FKBP12–rapamycin occludes the substrate channel — which is *why* 4E-BP1 escapes. |
| `translocation` | regulation by relocation | Energy stress moves TSC to the lysosome. |
| `signal-relay` | **multiple steps compressed** | Rendered with a `⋯` tag and forced to `directness: indirect` by the validator. |
| `association` | correlation, not causation | mTORC1↔RCC. Forced to low mechanistic confidence. |
| `clinical-outcome` | trial evidence, not mechanism | Every everolimus indication. Forbidden from being `direct`. |

### The three confidence axes

| Axis | Grades | Values |
|---|---|---|
| `mechanistic` | how well we understand *how* it works | high / medium / low |
| `human_relevance` | whether it has been shown to matter in humans | established / plausible / untested |
| `consensus` | whether the field agrees | established / emerging / contested |

**Human relevance is derived, not asserted.** This is the direct structural fix for review finding F4 (*"the evidence-tier rule is defined one way and applied another"*). Fixing the individual mis-graded edges would not have prevented recurrence. Instead the builder computes a ceiling from the citations:

```python
ceiling = "established" if (cited tiers ∩ {A,B}) or "human" in species else "plausible"
human_relevance = min(curator_value, ceiling)
```

The curator can only ever grade human relevance *down* (e.g. `untested` for mouse-only lifespan data). They cannot grade it up past what the papers support. **On first run this auto-downgraded 29 of 100 interactions** — including steps I had confidently marked `established` (Akt→TSC2, mTORC1→S6K1, S6K1→IRS-1) whose corpus evidence is tier-D mammalian cell work. I was making exactly the error the review had already flagged; the machine caught it in the first thirty seconds.

Distribution after correction: 25 established, 64 plausible, 11 untested. That is an honest picture of a corpus built mostly on cell biology.

### What was corrected in the biology

The 100 signs were externally reviewed with **no sign errors found**, so they were migrated unchanged. What is new:

- `PTEN-PI3K` reclassified `dephosphorylation` with an explicit note that PTEN does not inhibit the PI3K protein
- `RAG-MTORC1` reclassified `recruitment` / `required-for`, with a teaching note that this is the reason amino acids alone cannot drive growth
- `TSC-MTORC1` marked `signal-relay` + `indirect` — TSC never touches mTORC1, it acts on Rheb
- `GATOR2-GATOR1` graded `emerging` consensus with medium confidence: everyone agrees the inhibition happens, nobody has resolved how. An honest hole in the middle of a canonical pathway.
- `Ragulator-Rag` recorded as `scaffolding` rather than GEF activity, because the tethering role is better supported than the GEF assignment
- `MTORC1-RCC` typed `association`, forced to low mechanistic confidence and `unresolved` directness
- 14 interactions flagged by the validator as *"mechanistic=high rests on a single tier-D study"* — not errors, but a machine-generated **corpus gap list** for future curation

---

## 4. UX architecture

**Progressive disclosure via three orthogonal controls.** The old design had one dimension (which route). The new one separates concerns that were previously tangled:

| Control | Changes | Never changes |
|---|---|---|
| **Level** (beginner / student / research) | the *words* | the graph |
| **Filter** (effect, evidence, directness, contested) | which edges are *visible* | the words |
| **Focus mode** | the *neighbourhood* in view | anything else |

Keeping these independent is why the brief's instruction — *"switching levels should change explanations rather than rebuild the pathway"* — is enforceable. The smoke test asserts both halves: level switching changes the inspector text **and** leaves the node count identical.

**Selection model.** One selection, two kinds (node or interaction). Clicking an arrow inspects it and dims everything else; clicking a node lists its inputs and outputs as clickable rows. Escape clears. Every inspector row is a real button, so the whole graph is navigable without ever touching the canvas.

**Animation policy: every animation must teach.** Guided-route steps pulse the two participating molecules and run a flow dash along the interaction — communicating direction and participants. There are no decorative transitions. `prefers-reduced-motion` disables all of it, including camera easing, which then jumps instantly.

**Camera.** viewBox-driven, cubic-eased, 480 ms. Route steps frame the bounding box of the two nodes plus padding, so the reader keeps spatial context instead of teleporting. The step header always names the compartment — *"Step 6 / 7 · Lysosomal surface"* — so location is never lost.

---

## 5. Desktop architecture

Two-column stage: canvas (fluid, `min(72vh, 760px)`) + 330 px inspector, both scroll-independent. Toolbar above, collapsible legend below.

- Wheel zooms to cursor, drag pans, `+ − 0` on keyboard
- Mid-line mechanistic-verb tags (`GAP`, `MOVE`, `P`, `⋯`) fade in below viewBox width 1100 — visible when you are close enough to read them, absent when they would be noise
- The legend is a `<details>`, closed by default: available on demand, not consuming space by default

## 6. Mobile architecture

Designed as its own layout, not a squeeze.

- **Inspector becomes a bottom sheet** — fixed, 62 vh max, slide-up, grip + explicit close, `overscroll-behavior: contain`. Diagram and reading never compete for the same space, and the sheet is thumb-reachable.
- **Canvas 58 vh** with pinch-zoom (two-pointer distance tracking) and `touch-action: none` so the page never fights the diagram
- **Route buttons go full-width**; every control is ≥ 44 px tall by construction
- **Node labels grow** from 11.5 px to 13 px at ≤ 900 px — legibility at the size where it actually matters
- **Camera auto-framing** does the work a finger would otherwise have to: each route step frames itself, so a guided lesson is completable one-handed with nothing but *Next*

## 7. Accessibility

- Every node is `tabindex="0"`, `role="button"`, with an aria-label naming its class **and compartment** (*"Rheb, protein in Lysosomal surface"*)
- `role="status" aria-live="polite"` region announces mode changes, step changes with compartment, filter results and search counts — so camera movement, which a screen reader cannot perceive, is narrated
- **Colour never carries information alone.** Effect is colour **+ terminus shape** (arrow / bar / chevron / dot). Confidence is stroke weight **+ a written label**. Uncertainty is dash pattern **+ a glyph**. Deuteranopia loses nothing.
- Visible focus rings on canvas nodes (3.4 px stroke) and every control (3 px outline)
- Escape and arrow-key route navigation; all mode tabs expose `aria-selected`
- `prefers-reduced-motion` fully honoured
- Minimum touch target 44 × 44 px, enforced in CSS not by hope
- `<noscript>` points to the prerendered study and entity pages

Four of these are asserted in the smoke test, so they cannot silently regress.

## 8. Performance

| | Before | After |
|---|---|---|
| Explorer code path | inside 1.5 MB `index.html`, parsed on every visit | 40 KB JS + 12 KB CSS + 150 KB JSON, **fetched on first Pathway open** |
| Layout cost at runtime | hand-tuned constants, no computation | zero — coordinates precomputed at build time |
| Re-render on interaction | full `innerHTML` rebuild of canvas | **class toggles only**; SVG built once |
| Zoom / pan | not possible | `viewBox` attribute writes, no reflow, no re-render |
| Animation | `setTimeout` chain | `requestAnimationFrame`, single loop, cancellable |

The decisive choice is *build the SVG once, then only toggle classes*. Every filter, focus change, selection and route step is a `classList.toggle` over ~200 elements. That holds 60 fps on mid-range hardware, and it is why zoom stays smooth at 100 edges — and would at 500.

Deliberately avoided: no framework, no runtime layout engine, no D3. The 150 KB model is the largest asset and gzips to roughly 35 KB.

## 9. Scenario Laboratory — specified, deliberately not shipped

The Lab will offer fed, starvation, exercise, hypoxia, energy depletion, cancer, PTEN loss, PIK3CA mutation, TSC1 loss, TSC2 loss, high and low leucine, acute and chronic rapamycin, Torin, and metformin.

**Architecture: rule engine constrained by hand-curated expected outcomes.**

1. Each scenario declares perturbations (`{node: PTEN, state: loss}`)
2. A three-state qualitative propagation (**up / unchanged / down**) walks the interaction graph, respecting `effect` and skipping `association` and `clinical-outcome` edges
3. Each scenario also ships a **hand-curated, cited expected outcome** for its key readouts
4. **CI fails if the engine does not reproduce the curated outcome.** The engine is never the authority; the literature is.

**Why it is not in Phase 1, stated plainly:** a propagation engine over this graph will produce a confident answer for every condition, *including* the conditions governed by feedback loops the graph compresses into single arrows (S6K1→IRS-1, mTORC1→MAPK). Shipping that before it is constrained would make the Atlas *less* accurate while making it look more impressive. That trade is exactly backwards for this project. The Scenario tab currently says so, in those words, rather than showing a coming-soon placeholder.

**Hard limits, permanent:**

- **No numbers.** No predicted fold-changes, no simulated westerns, no dose-response curves. This graph cannot legitimately produce any of them.
- Direction and confidence only
- Every scenario labelled *educational modelling*, not *validated simulation*
- Feedback-loop-dominated scenarios (chronic rapamycin) show the loop explicitly and refuse to collapse it to a single arrow

## 10. Evidence system

The defining strength, and now structurally sound. Every interaction's inspector shows:

- **Mechanism** — curated prose
- **Why this distinction matters** — the teaching note, where one exists
- **Compressed** — automatic banner on every `indirect` edge
- **Boundary conditions** — where the claim stops holding
- **Three confidence meters**, with the standing explanation: *"A step can be mechanistically certain and still untested in humans. Study tier grades the papers; mechanism confidence grades the biology. They are not the same number."*
- **Supporting evidence** and **Conflicting evidence** as separate lists, each row clickable through to the study
- **Curation provenance** — interaction id, reviewer, review date

`conflicting[]` is empty today because the old model had no such field. It is now first-class, and populating it is the highest-value curation task in Phase 2 (see §15).

## 11. Scientific validation plan

Three gates, all machine-run:

**Gate 1 — `validate_pathway.py`** (blocks deploy on `--strict`). Vocabulary conformance; referential integrity; every interaction cites ≥ 1 corpus study; every node has all three levels and no two identical; orphan detection. Plus **calibration rules**, which are the interesting part:

| Rule | Rationale |
|---|---|
| `human_relevance: established` requires tier A/B or a human model | Finding F4, made unrepeatable |
| `mechanistic: high` forbidden on correlative evidence | Correlation is not mechanism |
| `consensus: established` + `mechanistic: low` rejected | Self-contradiction |
| `signal-relay` cannot be `direct` | A relay is multi-step by definition |
| `clinical-outcome` / `association` cannot be `direct` | Trial and epidemiological evidence are not mechanism |
| `contested` without boundary conditions → warning | If the field disagrees, say where |
| `mechanistic: high` on a single tier-D study → warning | Doubles as a corpus gap list (14 hits today) |

**Gate 2 — `pathway/smoke_test.js`**, 1 150 assertions in jsdom against the real model. Every node and interaction renders; every path is finite (no `NaN` geometry); every referenced marker is defined; every route walks end to end with all six questions substantively answered; filters return only what they claim; level switching changes words and not structure; four accessibility invariants; zero console errors.

**Mutation-verified.** Changing `RAG-MTORC1` from `recruitment` to `allosteric-activation` — the exact error this redesign exists to prevent — makes the suite fail. A test suite that has never failed has not been shown to work.

**Gate 3 — human review.** Every interaction carries `reviewer` and `reviewed`. Phase 3 adds a staleness report so a claim unreviewed for 12 months surfaces automatically.

The two automated gates are complementary and neither subsumes the other: the validator catches calibration and integrity, the smoke test catches rendering and pedagogy. The mutation above passes the validator and fails the smoke test.

## 12. Future extensibility

Nothing in `pathway.js` mentions mTOR. It reads compartments, nodes, interactions and routes. To add AMPK, MAPK, PI3K, Wnt, Notch or autophagy as first-class pathways:

1. Add nodes and interactions to the model, or a sibling model file
2. Extend `COMPARTMENTS` if a new location is needed
3. Nothing else

The layout engine, camera, inspector, evidence system, route engine and validator are pathway-agnostic. The type vocabulary is deliberately general cell-signalling grammar, not mTOR-specific.

**The one real coupling** is `studyBySid` / `filterStudiesByTitle` / `selectEntity` from the Atlas shell. All three are called through `typeof x === "function"` guards, so the module degrades rather than crashes if lifted into another site. Phase 4 formalises this as an injected adapter object.

## 13. Critical roadmap — Phase 1, shipped today

| # | Item | Status |
|---|---|---|
| C1 | Single source of truth; retire the drifting second representation | ✅ `pathway/model.json` |
| C2 | Separate mechanistic type from functional sign | ✅ 20 types × 6 effects |
| C3 | Separate the three confidence axes; derive human relevance from citations | ✅ 29 auto-downgrades on first run |
| C4 | Compartment-based spatial layout, computed not hand-tuned | ✅ 8 bands, barycentric ordering |
| C5 | Remove co-citation links from the mechanism visual language | ✅ moved to Entity Browser, relabelled |
| C6 | Zoom, pan, search, focus, four filter axes | ✅ |
| C7 | Overview landing with **correct** input topology | ✅ + test asserting the correction |
| C8 | Three learning levels changing text only | ✅ + test asserting the graph is unchanged |
| C9 | Evidence inspector with provenance and conflicting-evidence slot | ✅ |
| C10 | Guided routes: 6 questions per step, camera, progress, compartment | ✅ 7 routes, 6–8 steps each |
| C11 | Mobile bottom sheet, pinch, auto-framing, 44 px targets | ✅ |
| C12 | Accessibility: keyboard graph, live region, shape-not-colour | ✅ 4 invariants tested |
| C13 | Lazy-loaded module out of `index.html` | ✅ |
| C14 | Automated validation gates | ✅ validator + 1 150 assertions, mutation-verified |

## 14. High impact — Phase 2

| # | Item | Why it earns its place |
|---|---|---|
| H1 | **Hand-author the remaining 6 routes** to the `aa` standard, add *coincidence detection*, *feedback regulation*, *complete pathway* → 10 routes | Auto-assembled steps are honest but generic. The `aa` route is what the section should feel like; the others are not there yet. Biggest single quality gap. |
| H2 | **Populate `conflicting[]`** across the corpus | The field is built; empty. Showing supporting *and* conflicting evidence side by side is the most reviewer-visible strength available. |
| H3 | **Scenario Lab** per §9, with CI-enforced curated outcomes | The most-requested capability; must not ship before its safety net. |
| H4 | **Close the 14 single-tier-D-study gaps** the validator found | A machine-generated curation to-do list already exists. |
| H5 | **Prerender the Explorer** for AI crawlers | Memory records the site is empty to JS-less crawlers. The model is now clean structured data — one static page per interaction is nearly free. |
| H6 | **Retire `ATLAS_EDGES` / `ATLAS_ROUTES` / `MAP_*`** and the dead `mx*` functions | Kept one release deliberately, so both representations can be diffed. Removes ~60 KB and the last drift risk. |
| H7 | **Timescale as a visual axis** | `timescale` is curated but only shown in the inspector. Seconds-fast phosphorylation and hours-slow transcription look identical, which flattens real biology. |

## 15. Nice to have — Phase 3

- Deep-link URLs (`#/pathway/explorer?focus=Rheb&level=research`) — currently no shareable state
- Route bookmarking and resume
- Compartment collapse (fold the cytosol to 3 rows)
- Print / SVG export with a citation block, for teaching slides
- Review-staleness dashboard
- Side-by-side interaction comparison
- Species toggle (fly / mouse / human evidence only)
- `sensing_note` surfaced on the Inputs band — the fact that amino acids are sensed *inside* the cell deserves more than a tooltip

## 16. Future vision — Phase 4

- **Pathway framework**: AMPK, MAPK, PI3K, Wnt, Notch, autophagy as sibling models with cross-pathway edges
- **Structural layer**: PDB viewer on interactions with resolved structures — a genuine "how do we know" answer for `Structural` evidence
- **Community curation**: model in a public repo, biology changed by pull request with the validator as CI. Turns the Atlas from a publication into an instrument.
- **Model versioning with diffs**: *"what changed in our understanding of arginine sensing between 2024 and 2026"* — a question no other pathway resource can answer
- **Adapter formalisation** so the module drops into any site

---

## 17. The memorable feature

**Ask the map what it does not know.**

Every mechanism resource shows what is known. This one already stores, per interaction, its mechanistic confidence, human relevance, consensus state, boundary conditions and evidence tier. So it can invert:

> *Show me the shortest path from leucine to lifespan, and grade the weakest link in it.*

The answer is a chain where every step is graded, and the display names the weakest link explicitly. For leucine → longevity the weakest link is not exotic — it is the human-relevance step, because **no interaction in this corpus connecting mTORC1 to lifespan has human evidence at all** (11 of 100 interactions are graded `untested`, and every longevity edge is one of them).

That is not a visualisation trick. It is a claim about the state of a field, computed from graded primary literature, that a reader can verify by clicking through to the papers. Nobody leaves that unchanged. It is also the honest version of the argument the Atlas already wants to make, and it needs no new data — only Phase 2's route work plus a path query.

Deliberately *not* a memorable feature: 3D cells, particle animations, physics-based layouts. They impress on first load and teach nothing on the second.

---

## 18. Final self-review

### What a reviewer at *Nature Reviews MCB*, *Cell*, EMBL or CSHL would say — and the response

**"Your corpus is 77 % tier D. This is a cell-biology map dressed as a pathway authority."**
Correct, and now visible rather than implied: 64/100 interactions are `human_relevance: plausible`, 11 `untested`, only 25 `established`. The human-relevance filter lets a reader see the human-supported subgraph in one click, and it is small. This is the honest state of mTOR mechanism literature, not a defect in the map. *Not fixable — and should not be hidden.*

**"100 interactions is a fraction of the real pathway. Where is ATF4? SREBP's full arm? Lipin-1? The GATOR2 subunits individually? mTORC1's other substrates?"**
Fair and unfixed. This is a curated teaching map, not a reaction database; every edge earns inclusion by having a cited paper and a teaching purpose. But `Ragulator` as one node hides LAMTOR1–5, and `GATOR2` hides five subunits — a researcher will notice. Phase 4's structural layer plus subunit expansion is the answer. *Should be stated in the section's own about text, and currently is not.* Added to Phase 2.

**"Six of your seven guided routes are template-generated."**
True and the most visible weakness. They are honest — every sentence derives from a curated field, and the UI labels each step *"assembled from curated fields"* versus *"hand-authored"* — but generic. The `aa` route shows what the section is aiming at; H1 is the highest-priority follow-up for exactly this reason. *Partially addressed: the label at least does not let the reader mistake one for the other.*

**"`conflicting[]` is empty. You built the field and left it blank."**
Accurate. The old model had no such field so there was nothing to migrate. Empty-but-structured beats absent, and H2 fills it. But today the evidence system shows only one side, which for a section claiming honest uncertainty is a real shortfall.

**"Your compartments are simplified past the point of accuracy. Where is the ER? Rheb is substantially ER-localised. The Golgi? The peroxisome?"**
This was the sharpest criticism the review produced, and it was **fixed before shipping rather than deferred.** Rheb is placed on the lysosomal band because that is where it meets mTORC1 — the pedagogically load-bearing fact — but its farnesylation and its substantial ER/Golgi pool were not shown, and *which* pool supplies the activating Rheb is genuinely argued. An undeclared simplification is precisely what principle 1 forbids. Now: the lysosomal band carries a `sensing_note` stating that it means "the endomembrane surface where mTORC1 is switched on" and that the ER, Golgi and peroxisome are not drawn separately; Rheb's research-level text states its distribution and the open question; and the inspector renders any compartment's declared simplification as a **Declared simplification** banner on every node in that band. A smoke-test assertion now requires that every compartment with a `sensing_note` surfaces it, so a future band cannot compress cell biology silently.

**"Auto-downgrading human relevance is crude. A mechanism can be established in humans through genetics without a tier A/B paper in your corpus."**
Correct — DEPDC5 epilepsy establishes GATOR1's human relevance, and the rule grades it `plausible` because the corpus citations are cell lines. The rule is deliberately conservative: it under-claims rather than over-claims, and the alternative (curator assertion) is what failed. Right fix is not to loosen the rule but to add the human-genetics papers to the corpus, at which point the ceiling rises on its own. *Working as intended; documented here so it is not mistaken for a bug.*

**"You removed a feature (Full Pathway Map) users may have relied on."**
Deliberate. It drew co-citation and mechanism in the same visual language. The underlying capability survives in the Entity Browser with an honest caption. This is the clearest case in the redesign where an existing feature was worse than nothing.

**"Show me your test for the claim that colour is never the only channel."**
Not currently automated — it is enforced by CSS convention and review. The four accessibility invariants that *are* tested are keyboard reach, aria-labels, the live region and tab state. A contrast-and-channel audit belongs in Phase 2. *Conceded gap.*

### Iterations this review produced

1. First draft had one `confidence` number → split into three axes
2. Second draft let the curator assert human relevance → made it derived, catching 29 of my own errors
3. Third draft had the brief's serial input cascade → replaced with parallel convergence plus a test pinning the correction
4. Fourth draft shipped a Scenario Lab with a naive propagation engine → withdrawn to Phase 2 behind curated expected outcomes, because a confident wrong answer is worse than an absent feature
5. Fifth draft had a passing test suite with no evidence it could fail → added the mutation check
6. This review surfaced the undeclared Rheb/ER simplification → **fixed before shipping**: `sensing_note` on the lysosomal band, corrected Rheb research text, a *Declared simplification* banner in the inspector, and a test requiring every such band to surface it

### Would I recommend this to those institutions today?

The **architecture**, yes — the model, the three-axis evidence system, the derived calibration, the validation gates and the extensibility story are all publishable-grade, and the type/sign separation is a real contribution other pathway resources do not make.

The **content**, not yet. Six template routes and an empty conflicting-evidence field are the two things a careful reviewer will still find. Neither is architectural; both are curation, and both are Phase 2.

The right claim to make today is: *the framework is ready for review; the corpus needs one more pass.* Claiming more than that would be the exact failure mode this whole document is built to prevent.

---

## 19. Files

| File | Role |
|---|---|
| `pathway/model.json` | **Single source of truth.** 75 nodes, 100 interactions, 7 routes, 8 compartments |
| `build_pathway_model.py` | Generates the model; holds the curation tables and the derived-calibration rule |
| `validate_pathway.py` | Structural + scientific calibration gate. `--strict` blocks deploy |
| `pathway/pathway.js` | The module: overview, explorer, camera, inspector, route engine |
| `pathway/pathway.css` | Visual language; shape-and-weight encoding, mobile bottom sheet |
| `pathway/smoke_test.js` | 1 150 assertions in jsdom, mutation-verified |
| `_inject_pathway.py` | Idempotent wiring into `index.html` with write verification |
| `index.html.pre_pathway2` | Pre-redesign backup |

**Rebuild and verify:**

```bash
py build_pathway_model.py      # regenerate model.json
py validate_pathway.py --strict # scientific + structural gate
node pathway/smoke_test.js      # 1 150 rendering / pedagogy assertions
```
