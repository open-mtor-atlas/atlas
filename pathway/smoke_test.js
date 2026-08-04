/* =========================================================================
   smoke_test.js — headless test for the Pathway & Mechanism module.

   WHY THIS EXISTS
   The explorer is the most interactive thing in the Atlas and it lives in a
   file that nothing else tests. A broken selector or a typo in a template
   would previously only be discovered by a human clicking around after
   deploy. This boots the real module against the real model.json in jsdom
   and asserts the things that would actually break:

     * every node and interaction in the model renders
     * every interaction's marker, effect class and directness class exist
     * clicking an arrow produces an inspector with mechanism, confidence
       and at least one citation
     * every guided route can be walked end to end and every step answers
       all six questions with non-empty text
     * the level switch changes the words and not the graph
     * no console errors along the way

   Run:  node pathway/smoke_test.js        (needs jsdom; see NODE_PATH below)
   ========================================================================= */
const fs = require("fs");
const path = require("path");
const { JSDOM } = require(process.env.JSDOM_PATH || "jsdom");

const ROOT = path.join(__dirname, "..");
const model = JSON.parse(fs.readFileSync(path.join(ROOT, "pathway", "model.json"), "utf8"));
const contextsDoc = JSON.parse(fs.readFileSync(path.join(ROOT, "pathway", "contexts.json"), "utf8"));
const src = fs.readFileSync(path.join(ROOT, "pathway", "pathway.js"), "utf8");

let fails = 0, checks = 0;
function ok(cond, msg) {
  checks++;
  if (!cond) { fails++; console.log("  ✗ " + msg); }
}

const dom = new JSDOM("<!doctype html><html><body><div id=host></div></body></html>",
  { pretendToBeVisual: true, runScripts: "outside-only" });
const w = dom.window;

// jsdom has no layout: give the canvas a size so camera maths is exercised
Object.defineProperty(w.HTMLElement.prototype, "clientWidth", { get() { return 1000; } });
Object.defineProperty(w.HTMLElement.prototype, "clientHeight", { get() { return 700; } });
w.HTMLElement.prototype.getBoundingClientRect = function () {
  return { left: 0, top: 0, width: 1000, height: 700, right: 1000, bottom: 700 };
};
w.HTMLElement.prototype.setPointerCapture = function () {};
w.HTMLElement.prototype.releasePointerCapture = function () {};
w.performance = w.performance || { now: () => Date.now() };
w.requestAnimationFrame = (fn) => setTimeout(() => fn(w.performance.now()), 0);
w.cancelAnimationFrame = (id) => clearTimeout(id);
w.CSS = { escape: (s) => String(s).replace(/["\\]/g, "\\$&") };
// boot() derives the contexts.json URL from modelUrl by substring replace,
// so the stub must be URL-aware to actually exercise that path.
w.fetch = (url) => Promise.resolve({
  ok: true,
  json: () => Promise.resolve(String(url).indexOf("contexts.json") >= 0 ? contextsDoc : model)
});
w.matchMedia = () => ({ matches: false, addListener() {}, removeListener() {} });
w.scrollTo = () => {};

const errors = [];
w.console = { log() {}, warn() {}, error(...a) { errors.push(a.join(" ")); } };

// Atlas globals the module talks to. Minimal honest stubs.
w.studyBySid = (sid) => ({ sid, title: "Stub title for " + sid, authors: "Author A; Author B",
                           year: 2020, tier: "D" });
w.tierMeta = (t) => ({ letter: t, color: "#000" });
w.filterStudiesByTitle = () => {};
w.entityByName = () => true;
w.selectEntity = () => {};
w.showView = () => {};

w.eval(src);


/* realClick reproduces what a real mouse does, which the old test did not:
   pointerdown lands on the SVG shape, then setPointerCapture retargets every
   later pointer event to the capturing element, so pointerup arrives with
   target === the canvas <div>. Forcing ev.target on pointerup (as this test
   used to) bypassed exactly the code path that was broken in production. */
function fire(w, canvas, type, target, x, y) {
  const e = new w.MouseEvent(type, { bubbles: true });
  Object.defineProperty(e, "target", { value: target });
  Object.defineProperty(e, "clientX", { value: x == null ? 500 : x });
  Object.defineProperty(e, "clientY", { value: y == null ? 350 : y });
  Object.defineProperty(e, "pointerId", { value: 1 });
  canvas.dispatchEvent(e);
  return e;
}
/* realClick reproduces the full browser sequence for a real activation:
   pointerdown -> pointerup -> click. Two details matter and both were got
   wrong before:
     * pointerup may be RETARGETED to the capturing element by pointer
       capture, so it is dispatched here with target === canvas;
     * `click` is the event that actually means "the user activated this",
       and it arrives with the correct target.
   Selection is asserted through this path only. Dispatching a lone synthetic
   pointerup with a forced target — as this test used to — exercised a code
   path the platform never produces. */
function realClick(w, canvas, shape, x, y) {
  fire(w, canvas, "pointerdown", shape, x, y);
  fire(w, canvas, "pointerup", canvas, x, y);
  fire(w, canvas, "click", shape, x, y);
}
/* A pan: press, move well past the threshold, release, and the click the
   browser still emits. Must NOT select. */
function realDrag(w, canvas, shape, x1, y1, x2, y2) {
  fire(w, canvas, "pointerdown", shape, x1, y1);
  fire(w, canvas, "pointermove", canvas, x2, y2);
  fire(w, canvas, "pointerup", canvas, x2, y2);
  fire(w, canvas, "click", canvas, x2, y2);
}

const host = w.document.getElementById("host");

w.PathwayApp.boot(host, "pathway/model.json").then(async () => {
  const D = w.document;
  /* NB: host contains TWO svgs - the overview diagram and the canvas. An
     earlier version of this test did host.querySelector("svg") and silently
     asserted against the overview, which made the camera checks meaningless.
     Always scope to #pwCanvas. */
  const svg = D.querySelector("#pwCanvas svg");
  const ovSvg = D.querySelector(".pw-ov-svg");

  console.log("— render —");
  ok(!!svg, "canvas SVG built");
  ok(!!ovSvg && ovSvg !== svg, "overview SVG is a separate element from the canvas");
  ok((svg.getAttribute("viewBox") || "").split(" ").length === 4, "canvas has a 4-part viewBox");
  ok(D.querySelectorAll(".pw-n").length === model.nodes.length,
    `all ${model.nodes.length} nodes rendered (got ${D.querySelectorAll(".pw-n").length})`);
  model.interactions.forEach((e) => {
    const p = D.getElementById("pwe-" + e.id);
    ok(!!p, `interaction ${e.id} rendered`);
    if (!p) return;
    ok(p.classList.contains("f-" + e.effect), `${e.id} carries effect class`);
    ok(p.classList.contains("d-" + e.directness), `${e.id} carries directness class`);
    ok(p.classList.contains("m-" + e.confidence.mechanistic), `${e.id} carries confidence class`);
    ok(/marker-end="url\(#pw/.test(p.outerHTML), `${e.id} has a terminus marker`);
    const dAttr = p.getAttribute("d") || "";
    ok(/^M[-\d.]+,[-\d.]+ C/.test(dAttr) && !/NaN|Infinity/.test(dAttr), `${e.id} path geometry is finite`);
  });
  // every marker referenced must be defined
  const defined = new Set([...D.querySelectorAll("marker")].map((m) => m.id));
  const used = new Set([...D.querySelectorAll("[marker-end]")]
    .map((p) => (p.getAttribute("marker-end").match(/#([\w-]+)/) || [])[1]));
  [...used].forEach((u) => ok(defined.has(u), `marker #${u} is defined`));

  console.log("— overview —");
  ok(/investment committee/.test(host.innerHTML), "overview lede present");
  ok(D.querySelectorAll(".pw-ov-act").length === 3, "three primary actions");
  ok(/parallel and independent/.test(host.innerHTML),
    "overview states the inputs are parallel (guards against re-introducing a false serial cascade)");

  /* Nothing may sit outside the overview viewBox. jsdom cannot lay out, but
     rect x/width are literal attributes, so overflow IS checkable — and it
     had happened: 4 columns starting at x=34 in a 940-wide viewBox put the
     fourth box's right edge at 974, clipping "is anything wrong?" live. */
  const ovVB = (ovSvg.getAttribute("viewBox") || "0 0 0 0").split(" ").map(Number);
  [...ovSvg.querySelectorAll("rect")].forEach((rc) => {
    const x = parseFloat(rc.getAttribute("x")), wd = parseFloat(rc.getAttribute("width"));
    const y = parseFloat(rc.getAttribute("y")), ht = parseFloat(rc.getAttribute("height"));
    ok(x >= ovVB[0] - 0.5 && x + wd <= ovVB[0] + ovVB[2] + 0.5,
      `overview rect at x=${x} w=${wd} fits the ${ovVB[2]}-wide viewBox`);
    ok(y >= ovVB[1] - 0.5 && y + ht <= ovVB[1] + ovVB[3] + 0.5,
      `overview rect at y=${y} h=${ht} fits the ${ovVB[3]}-tall viewBox`);
  });

  console.log("— inspector —");
  let inspected = 0;
  model.interactions.forEach((e) => {
    D.getElementById("pwe-" + e.id); // exists, checked above
    const hit = D.querySelector(`.pw-hitline[data-eid="${e.id}"]`);
    ok(!!hit, `${e.id} has a hit target`);
  });
  // drive the real click path on a representative sample
  ["RAG-MTORC1", "RHEB-MTORC1", "MTORC1-RCC", "RAPA-MTORC2", "S6K1-IRS1"].forEach((id) => {
    const hit = D.querySelector(`.pw-hitline[data-eid="${id}"]`);
    if (!hit) return;
    realClick(w, D.getElementById("pwCanvas"), hit);
    const insp = D.getElementById("pwInsp").innerHTML;
    inspected++;
    ok(/Mechanism/.test(insp), `${id}: inspector shows mechanism`);
    ok(/Confidence — three separate things/.test(insp), `${id}: inspector separates the three confidences`);
    ok(/Supporting evidence/.test(insp), `${id}: inspector cites evidence`);
    ok(/reviewed \d{4}-\d{2}-\d{2}/.test(insp), `${id}: inspector shows review date`);
  });
  ok(inspected === 5, "all sampled arrows were clickable");

  // the load-bearing pedagogical claim
  const hitRag = D.querySelector('.pw-hitline[data-eid="RAG-MTORC1"]');
  realClick(w, D.getElementById("pwCanvas"), hitRag);
  ok(/recruits/.test(D.getElementById("pwInsp").innerHTML),
    "RAG-MTORC1 is described as recruitment, not activation");
  ok(!/allosterically activates/.test(D.getElementById("pwInsp").innerHTML),
    "RAG-MTORC1 is not described as activation");

  console.log("— learning levels —");
  const nodeG = D.querySelector('.pw-n[data-nid="mTORC1"]');
  realClick(w, D.getElementById("pwCanvas"), nodeG.querySelector(".nb") || nodeG);
  const texts = {};
  ["beginner", "student", "research"].forEach((lv) => {
    D.querySelector(`#pwLevel button[data-lv="${lv}"]`).dispatchEvent(new w.MouseEvent("click", { bubbles: true }));
    texts[lv] = D.getElementById("pwInsp").textContent;
  });
  ok(texts.beginner !== texts.student && texts.student !== texts.research,
    "level switch changes the explanation text");

  // Declared simplifications must be surfaced. Principle 1 of the redesign is
  // "never let a simplification become a misconception"; a compartment that
  // compresses real cell biology has to say so on every node in it.
  model.compartments.filter((c) => c.sensing_note).forEach((c) => {
    const n = model.nodes.find((x) => x.compartment === c.id);
    if (!n) return;
    const g = D.querySelector(`.pw-n[data-nid="${w.CSS.escape(n.id)}"]`);
    realClick(w, D.getElementById("pwCanvas"), g.querySelector(".nb") || g);
    ok(/Declared simplification/.test(D.getElementById("pwInsp").innerHTML),
      `compartment ${c.id} declares its simplification on its nodes`);
  });
  ok(D.querySelectorAll(".pw-n").length === model.nodes.length,
    "level switch does NOT rebuild the graph");

  console.log("— guided routes —");
  w.PathwayApp.setMode("guided");
  model.routes.forEach((r) => {
    D.querySelector(`.pw-routebtn[data-r="${r.id}"]`).dispatchEvent(new w.MouseEvent("click", { bubbles: true }));
    const start = D.getElementById("pwStart");
    ok(!!start, `route ${r.id}: has an intro with a start button`);
    if (!start) return;
    start.dispatchEvent(new w.MouseEvent("click", { bubbles: true }));
    const total = (r.steps && r.steps.length) ? r.steps.length : r.spine.length;
    ok(total >= 5, `route ${r.id}: has at least 5 steps (${total})`);
    for (let i = 0; i < total; i++) {
      const dds = [...D.querySelectorAll("#pwStep .pw-q dd")];
      ok(dds.length === 5, `route ${r.id} step ${i + 1}: five answered questions`);
      dds.forEach((dd, k) => ok(dd.textContent.trim().length > 12,
        `route ${r.id} step ${i + 1}: answer ${k + 1} is substantive`));
      const hd = D.querySelector("#pwStep .pw-step-hd h4");
      ok(hd && hd.textContent.trim().length > 12, `route ${r.id} step ${i + 1}: has a headline`);
      ok(/Step \d+ \/ \d+ · /.test(D.querySelector("#pwStep .pw-step-n").textContent),
        `route ${r.id} step ${i + 1}: states position and compartment`);
      const next = D.getElementById("pwNext");
      if (i < total - 1) next.dispatchEvent(new w.MouseEvent("click", { bubbles: true }));
    }
  });

  // Camera must reach its destination even when requestAnimationFrame never
  // fires. It does not fire in a hidden tab, which is exactly how this was
  // found: a route step in a backgrounded tab left the camera at frame 0.
  // Regression: the Scenario Lab card used to reuse .pw-step-n, so once that
  // panel had rendered, an unscoped lookup returned "Phase 2 — in build"
  // instead of the live step. Visit it FIRST, then assert the route step
  // still reads correctly both scoped and unscoped.
  /* The bug this guards: pointer capture retargets pointerup to the canvas
     div, so reading ev.target there found no shape and clicking a molecule or
     an arrow silently did nothing on the live site. */
  console.log("— click survives pointer capture retargeting —");
  const canvasEl = D.getElementById("pwCanvas");
  inspectDefaultCheck: {
    D.querySelector('#pwView button[data-vw="pathway"]').dispatchEvent(new w.MouseEvent("click", { bubbles: true }));
    realClick(w, canvasEl, D.querySelector('.pw-hitline[data-eid="TSC-RHEB"]'));
    const t = D.getElementById("pwInsp").textContent;
    ok(/acts as a GAP on/.test(t), "clicking an arrow populates the inspector despite capture retargeting");
    ok(!/Click any molecule or any arrow/.test(t), "inspector is no longer showing its empty state");
  }
  realClick(w, canvasEl, D.querySelector('.pw-n[data-nid="Rheb"]').querySelector(".nb"));
  ok(/Rheb/.test(D.getElementById("pwInsp").textContent) && /Inputs \(/.test(D.getElementById("pwInsp").innerHTML),
    "clicking a molecule populates the inspector despite capture retargeting");
  // A pan must NOT select whatever was under the initial press.
  realClick(w, canvasEl, D.querySelector('.pw-n[data-nid="Rheb"]').querySelector(".nb"));
  const beforeDrag = D.getElementById("pwInsp").textContent;
  realDrag(w, canvasEl, D.querySelector('.pw-n[data-nid="mTORC1"]').querySelector(".nb"), 400, 300, 480, 340);
  ok(D.getElementById("pwInsp").textContent === beforeDrag,
    "a pan gesture does not select whatever was under the initial press");
  // and a normal click still works immediately after a pan
  realClick(w, canvasEl, D.querySelector('.pw-n[data-nid="mTORC1"]').querySelector(".nb"));
  ok(/mTORC1/.test(D.querySelector("#pwInsp h4").textContent),
    "a click right after a pan still selects");
  // keyboard activation must reach the same code path
  const kn = D.querySelector('.pw-n[data-nid="AMPK"]');
  const kev = new w.KeyboardEvent("keydown", { key: "Enter", bubbles: true });
  Object.defineProperty(kev, "target", { value: kn });
  canvasEl.dispatchEvent(kev);
  ok(/AMPK/.test(D.querySelector("#pwInsp h4").textContent),
    "keyboard Enter on a molecule selects it");
  D.querySelector('#pwView button[data-vw="mechanism"]').dispatchEvent(new w.MouseEvent("click", { bubbles: true }));

  console.log("— panel class isolation —");
  w.PathwayApp.setMode("scenarios");
  ok(D.querySelectorAll("#pwScen .pw-step-n").length === 0,
    "Scenario Lab does not borrow the guided-route step badge class");
  w.PathwayApp.setMode("guided");
  D.querySelector('.pw-routebtn[data-r="aa"]').dispatchEvent(new w.MouseEvent("click", { bubbles: true }));
  D.getElementById("pwStart").dispatchEvent(new w.MouseEvent("click", { bubbles: true }));
  ok(D.querySelectorAll(".pw-step-n").length === 1,
    "exactly one .pw-step-n exists in the document while a route step is open");
  ok(/Step \d+ \/ \d+ · /.test(D.querySelector(".pw-step-n").textContent),
    "the step badge names its position and compartment even after the Scenario Lab has rendered");

  console.log("— camera robustness —");
  const rafBackup = w.requestAnimationFrame;
  w.requestAnimationFrame = () => 0;                 // simulate a hidden tab
  w.PathwayApp.setMode("guided");
  D.querySelector('.pw-routebtn[data-r="aa"]').dispatchEvent(new w.MouseEvent("click", { bubbles: true }));
  D.getElementById("pwStart").dispatchEvent(new w.MouseEvent("click", { bubbles: true }));
  const vbStart = svg.getAttribute("viewBox");
  D.getElementById("pwNext").dispatchEvent(new w.MouseEvent("click", { bubbles: true }));
  await new Promise((r) => setTimeout(r, 700));
  const vbAfter = svg.getAttribute("viewBox");
  ok(vbAfter !== vbStart, "camera still reaches its target with requestAnimationFrame dead");
  ok(!/NaN|Infinity/.test(vbAfter), "camera target is finite");
  w.requestAnimationFrame = rafBackup;

  console.log("— abstraction axis: mechanism vs pathway —");
  w.PathwayApp.setMode("explorer");
  const COMPRESSED = { "signal-relay": 1, "functional-consequence": 1, "clinical-outcome": 1, "association": 1 };
  const isMech = (e) => !COMPRESSED[e.type];
  const vis = () => model.interactions.filter((e) => !D.getElementById("pwe-" + e.id).classList.contains("dim"));
  const mechShown = vis();
  ok(mechShown.length > 0 && mechShown.every(isMech),
    `explorer opens in Mechanism view: molecular events only (${mechShown.length}/${model.interactions.length})`);
  ok(mechShown.length < model.interactions.length, "Mechanism view is a genuine subset");
  ok(/Mechanism view/.test(D.getElementById("pwHintBox").innerHTML),
    "the canvas states which abstraction level is shown");
  D.querySelector('#pwView button[data-vw="pathway"]').dispatchEvent(new w.MouseEvent("click", { bubbles: true }));
  ok(vis().length === model.interactions.length, "Pathway view adds the compressed links and outcomes");
  ok(/Pathway view/.test(D.getElementById("pwHintBox").innerHTML), "hint follows the view");

  console.log("— temporal dynamics —");
  const TIME_ORDER = ["constitutive", "seconds", "minutes", "hours", "days", "chronic"];
  ["seconds", "minutes", "hours", "chronic"].forEach((tm) => {
    D.querySelector(`#pwTime button[data-tm="${tm}"]`).dispatchEvent(new w.MouseEvent("click", { bubbles: true }));
    const shown = vis();
    ok(shown.length > 0, `time window "${tm}" shows something`);
    ok(shown.every((e) => e.timescale === "constitutive"
        || TIME_ORDER.indexOf(e.timescale) <= TIME_ORDER.indexOf(tm)),
      `time window "${tm}" is cumulative and excludes slower steps`);
    ok(/cumulative up to/.test(D.getElementById("pwHintBox").innerHTML),
      `time window "${tm}" is announced on the canvas`);
  });
  // the window must actually grow
  const counts = ["seconds", "minutes", "hours", "chronic"].map((tm) => {
    D.querySelector(`#pwTime button[data-tm="${tm}"]`).dispatchEvent(new w.MouseEvent("click", { bubbles: true }));
    return vis().length;
  });
  ok(counts[0] < counts[counts.length - 1], `the network unfolds over time (${counts.join(" → ")})`);
  ok(counts.every((c, i) => i === 0 || c >= counts[i - 1]), "each time window is a superset of the previous");
  D.querySelector('#pwTime button[data-tm="all"]').dispatchEvent(new w.MouseEvent("click", { bubbles: true }));

  console.log("— feedback loops —");
  ok((model.loops || []).length >= 4, `model names ${(model.loops || []).length} feedback loops`);
  model.loops.forEach((lp) => {
    ok(["negative", "positive"].includes(lp.sign), `${lp.id} has a sign`);
    ok((lp.sign_caveat || "").length > 20, `${lp.id} ships its sign caveat (parity is not strength)`);
    ok(lp.interactions.every((eid) => model.interactions.some((e) => e.id === eid)),
      `${lp.id} references only real interactions`);
    // a loop must close: every node is both a source and a target within the loop
    const srcs = new Set(), tgts = new Set();
    lp.interactions.forEach((eid) => {
      const e = model.interactions.find((x) => x.id === eid);
      srcs.add(e.source); tgts.add(e.target);
    });
    ok([...srcs].every((n) => tgts.has(n)) && [...tgts].every((n) => srcs.has(n)),
      `${lp.id} is a closed cycle`);
  });
  ok((model.open_loops || []).length >= 1,
    "loops the literature describes but this map cannot close are declared, not omitted");
  D.getElementById("pwLoops").dispatchEvent(new w.MouseEvent("click", { bubbles: true }));
  const loopShown = vis();
  ok(loopShown.length > 0 && loopShown.every((e) => (e.loops || []).length),
    `feedback filter shows only interactions inside a loop (${loopShown.length})`);
  ok(/feedback loops only/i.test(D.getElementById("pwHintBox").innerHTML), "feedback mode is announced");
  const li = D.getElementById("pwInsp").innerHTML;
  ok(/feedback loops/.test(li) && /set point|set-point/.test(li),
    "the loop panel explains that a loop has a set point rather than a direction");
  ok(/cannot close/.test(li), "the loop panel lists the loops this map cannot close");
  D.getElementById("pwLoops").dispatchEvent(new w.MouseEvent("click", { bubbles: true }));
  D.querySelector('#pwView button[data-vw="pathway"]').dispatchEvent(new w.MouseEvent("click", { bubbles: true }));

  console.log("— filters —");
  // filters compose with the detail set rather than fighting it
  D.querySelector('#pwView button[data-vw="pathway"]').dispatchEvent(new w.MouseEvent("click", { bubbles: true }));
  D.querySelector('#pwEvid2 button[data-ev="human"]').dispatchEvent(new w.MouseEvent("click", { bubbles: true }));
  const humanShown = model.interactions.filter((e) => !D.getElementById("pwe-" + e.id).classList.contains("dim"));
  ok(humanShown.length > 0 && humanShown.every((e) => e.confidence.human_relevance === "established"),
    `human-relevance filter shows only human-relevant steps (${humanShown.length})`);
  D.querySelector('#pwEvid2 button[data-ev="contested"]').dispatchEvent(new w.MouseEvent("click", { bubbles: true }));
  const contested = model.interactions.filter((e) => !D.getElementById("pwe-" + e.id).classList.contains("dim"));
  ok(contested.length > 0 && contested.every((e) => e.confidence.consensus === "contested"),
    `contested filter works (${contested.length})`);
  D.getElementById("pwReset").dispatchEvent(new w.MouseEvent("click", { bubbles: true }));
  const afterReset = model.interactions.filter((e) => !D.getElementById("pwe-" + e.id).classList.contains("dim"));
  ok(afterReset.every(isMech) && afterReset.length === model.interactions.filter(isMech).length,
    "reset clears filters and returns to the Mechanism view");
  ok(D.querySelector('#pwView button[data-vw="mechanism"]').getAttribute("aria-pressed") === "true"
     && D.querySelector('#pwTime button[data-tm="all"]').getAttribute("aria-pressed") === "true"
     && D.getElementById("pwLoops").getAttribute("aria-pressed") === "false",
    "reset leaves every control agreeing with what is drawn");

  console.log("— context overlay (Fed / Fasting / Exercise) —");
  ok(!!D.getElementById("pwCtxBar"), "context chip bar renders");
  const ctxIds = contextsDoc.contexts.map((c) => c.id);
  ["all", "fed", "fasting", "exercise", "cancer", "aging", "muscle", "immune", "neuron"].forEach((id) => {
    ok(ctxIds.includes(id), `contexts.json defines "${id}"`);
    ok(!!D.querySelector(`.pw-ctx-chip[data-ctx="${id}"]`), `chip for "${id}" renders`);
  });
  const stubIds = contextsDoc.contexts.filter((c) => c.stub).map((c) => c.id);
  ok(stubIds.length === 5, `five contexts are marked stub (${stubIds.join(", ")})`);
  stubIds.forEach((id) => {
    ok(D.querySelector(`.pw-ctx-chip[data-ctx="${id}"]`).classList.contains("stub"),
      `${id} chip carries the stub/"planned" marker`);
  });

  // every id a context references must be a real node/interaction -- guards
  // contexts.json against drifting from model.json after either changes
  const ctxEdgeIds = new Set(model.interactions.map((e) => e.id));
  const ctxNodeIds = new Set(model.nodes.map((n) => n.id));
  contextsDoc.contexts.forEach((c) => {
    Object.keys(c.edges || {}).forEach((eid) =>
      ok(ctxEdgeIds.has(eid), `context "${c.id}": edge id ${eid} exists in model.json`));
    Object.keys(c.nodes || {}).forEach((nid) =>
      ok(ctxNodeIds.has(nid), `context "${c.id}": node id ${nid} exists in model.json`));
    Object.entries(c.edges || {}).forEach(([eid, st]) =>
      ok(["active", "suppressed", "unclear"].includes(st),
        `context "${c.id}": edge ${eid} has a valid state (${st})`));
  });

  // selecting a context is a weighting, never a re-layout
  const xyBeforeCtx = new Map(model.nodes.map((n) => [n.id, `${n.x},${n.y}`]));
  D.querySelector('.pw-ctx-chip[data-ctx="fed"]').dispatchEvent(new w.MouseEvent("click", { bubbles: true }));
  ok(model.nodes.every((n) => xyBeforeCtx.get(n.id) === `${n.x},${n.y}`),
    "selecting a context never mutates node coordinates -- weighting only, never a re-layout");
  ok(D.querySelector('.pw-ctx-chip[data-ctx="fed"]').getAttribute("aria-pressed") === "true",
    "Fed chip becomes pressed on click");
  ok(D.querySelector('.pw-ctx-chip[data-ctx="all"]').getAttribute("aria-pressed") === "false",
    "All chip un-presses when Fed is selected");
  ok(/Fed/.test(D.getElementById("pwCtxBrief").textContent), "context brief shows the Fed narrative");

  const fedNodeIds = Object.keys(contextsDoc.contexts.find((c) => c.id === "fed").nodes);
  let ctxBadgeCount = 0;
  fedNodeIds.forEach((nid) => {
    const g = D.querySelector(`.pw-n[data-nid="${w.CSS.escape(nid)}"]`);
    const b = g && g.querySelector(".pw-ctxb");
    if (b && b.textContent) ctxBadgeCount++;
  });
  ok(ctxBadgeCount === fedNodeIds.length,
    `every Fed-annotated node carries a context badge (${ctxBadgeCount}/${fedNodeIds.length})`);

  // MTORC2-AKT is deliberately unannotated for Fed and is a mechanistic
  // (non-compressed) edge, so under Mechanism view it would normally NOT be
  // dimmed -- only the context "na" rule dims it.
  const naEdge = D.getElementById("pwe-MTORC2-AKT");
  ok(naEdge && naEdge.classList.contains("dim"),
    "Fed context dims an unannotated edge (MTORC2-AKT) rather than guessing its state");

  // RAG-MTORC1 is annotated "active" for Fed and is mechanistic -> must stay visible
  const activeEdge = D.getElementById("pwe-RAG-MTORC1");
  ok(activeEdge && !activeEdge.classList.contains("dim"), "Fed-active edge RAG-MTORC1 stays visible");
  const activeUnderlay = D.querySelector('.pw-ctxu[data-eid="RAG-MTORC1"]');
  ok(activeUnderlay && parseFloat(activeUnderlay.style.opacity) > 0,
    "Fed-active edge RAG-MTORC1 shows a context underlay");

  // stub contexts must NEVER filter or dim the diagram -- only the brief changes
  const baselineDim = model.interactions.filter((e) =>
    D.getElementById("pwe-" + e.id).classList.contains("dim")).length;
  D.querySelector('.pw-ctx-chip[data-ctx="cancer"]').dispatchEvent(new w.MouseEvent("click", { bubbles: true }));
  const cancerDim = model.interactions.filter((e) =>
    D.getElementById("pwe-" + e.id).classList.contains("dim")).length;
  ok(/not yet curated/i.test(D.getElementById("pwCtxBrief").textContent),
    "stub context (Cancer) brief says it is not yet curated");
  D.querySelector('.pw-ctx-chip[data-ctx="all"]').dispatchEvent(new w.MouseEvent("click", { bubbles: true }));
  const allDim = model.interactions.filter((e) =>
    D.getElementById("pwe-" + e.id).classList.contains("dim")).length;
  ok(cancerDim === allDim,
    `a stub context dims exactly as much as no context at all (fed ${baselineDim}, cancer ${cancerDim}, all ${allDim})`);

  // Reset view must also clear the context back to All
  D.querySelector('.pw-ctx-chip[data-ctx="fasting"]').dispatchEvent(new w.MouseEvent("click", { bubbles: true }));
  D.getElementById("pwReset").dispatchEvent(new w.MouseEvent("click", { bubbles: true }));
  ok(D.querySelector('.pw-ctx-chip[data-ctx="all"]').getAttribute("aria-pressed") === "true",
    "Reset view returns the context filter to All");

  console.log("— search —");
  D.getElementById("pwFind").value = "Rheb";
  D.getElementById("pwFind").dispatchEvent(new w.Event("input", { bubbles: true }));
  ok(!D.querySelector('.pw-n[data-nid="Rheb"]').classList.contains("dim"), "search reveals its hit");

  console.log("— accessibility —");
  ok([...D.querySelectorAll(".pw-n")].every((g) => g.getAttribute("tabindex") === "0"),
    "every node is keyboard reachable");
  ok([...D.querySelectorAll(".pw-n")].every((g) => (g.getAttribute("aria-label") || "").length > 3),
    "every node has an aria-label naming its compartment");
  ok(!!D.querySelector('[role="status"][aria-live]'), "live region for announcements exists");
  ok([...D.querySelectorAll(".pw-mode")].every((b) => b.hasAttribute("aria-selected")),
    "mode tabs expose selection state");

  /* jsdom has no layout engine, so touch-target size cannot be measured here.
     What CAN be checked is that the rules exist — this was added after a live
     check found 14 toolbar controls at 38px while the spec claimed 44px.
     A source assertion is shallow, but it is not nothing, and it stops the
     rule being deleted silently. */
  console.log("— touch targets (source assertion) —");
  const css = fs.readFileSync(path.join(ROOT, "pathway", "pathway.css"), "utf8");
  const mobileBlock = (css.match(/@media \(max-width:900px\)\{[\s\S]*?\n\}/) || [""])[0];
  ok(mobileBlock.length > 200, "mobile media block found");
  ok(/\.pw-btn[^{]*\{[^}]*(min-)?height:44px/.test(mobileBlock),
    "toolbar buttons are raised to 44px on touch viewports");
  ok(/\.pw-ctx-chip[^{]*\{[^}]*(min-)?height:44px/.test(mobileBlock),
    "context chips are raised to 44px on touch viewports");
  ok(/\.pw-seg button[^{]*\{[^}]*(min-)?height:44px/.test(mobileBlock),
    "segmented controls are raised to 44px on touch viewports");
  ok(/\.pw-zoom button[^{]*\{[^}]*width:44px/.test(mobileBlock),
    "zoom buttons are raised to 44px on touch viewports");
  ok(/\.pw-insp\{[^}]*position:fixed/.test(mobileBlock),
    "inspector becomes a fixed bottom sheet on mobile");
  ok(/@media \(prefers-reduced-motion:reduce\)/.test(css),
    "reduced-motion block present");

  console.log("— review pass: context, node evidence, roles, tiers, legend —");
  // 1. the consensus-model caveat is standing, not a footnote
  const cav = D.querySelector(".pw-caveat");
  ok(!!cav, "standing context-dependence notice is present");
  ok(/consensus model, not a list of verified facts/.test(cav.textContent),
    "the notice says the map is a consensus model rather than verified fact");
  ok(/cell types|tissue/.test(cav.textContent) && /dose/.test(cav.textContent),
    "the notice names the axes of context dependence");
  // edge-level context notes exist and render
  const withCtx = model.interactions.filter((e) => (e.context_note || "").length > 20);
  ok(withCtx.length >= 8, `${withCtx.length} interactions carry an explicit context note`);
  const ampk = model.interactions.find((e) => e.id === "AMPK-TSC");
  ok(/cell-type dependent/.test(ampk.context_note) && /TSC2-null/.test(ampk.context_note),
    "the reviewer's own example (AMPK→TSC2) states that this arm is not universally dominant");
  realClick(w, canvasEl, D.querySelector('.pw-hitline[data-eid="AMPK-TSC"]'));
  ok(/Context dependence/.test(D.getElementById("pwInsp").innerHTML),
    "context dependence is shown on the interaction, not only in the banner");

  // 2. node-level evidence strength
  model.nodes.forEach((n) => {
    const ev = n.evidence || {};
    ok(typeof ev.studies_in_corpus === "number", `${n.id}: has a study count`);
    ok(/not in the literature/.test(ev.caveat || ""),
      `${n.id}: the count is labelled as corpus-only, not a literature count`);
  });
  const nodeCounts = model.nodes.map((n) => n.evidence.studies_in_corpus);
  ok(Math.max(...nodeCounts) > Math.min(...nodeCounts) * 3,
    `node support genuinely varies (${Math.min(...nodeCounts)}–${Math.max(...nodeCounts)} studies)`);
  const weights = new Set([...D.querySelectorAll(".pw-n")].map((g) =>
    ["ev-hi", "ev-mid", "ev-lo", "ev-min"].find((c) => g.classList.contains(c))));
  ok(weights.size >= 3, `nodes carry at least 3 distinct visual weights (${[...weights].join(",")})`);
  ok([...D.querySelectorAll(".pw-n")].every((g) => /studies in this corpus/.test(g.getAttribute("aria-label"))),
    "study count is in the aria-label, so border weight is never the only channel");
  realClick(w, canvasEl, D.querySelector('.pw-n[data-nid="mTORC1"]').querySelector(".nb"));
  const ni = D.getElementById("pwInsp").innerHTML;
  ok(/studies in this corpus/.test(ni) && /earliest paper cited here/.test(ni),
    "node inspector shows study count and earliest cited year, precisely labelled");
  ok(!/>\s*Year of discovery/i.test(ni) && /not the year of discovery/i.test(ni),
    "it labels the year as 'earliest paper cited here' and explicitly disclaims a discovery year");

  // 7. context-dependent roles
  const roled = model.nodes.filter((n) => (n.context_roles || []).length);
  ok(roled.length >= 12, `${roled.length} molecules carry context-dependent roles`);
  ok(/Context-dependent roles/.test(ni), "the roles section renders for mTORC1");
  const akt = model.nodes.find((n) => n.id === "Akt/PKB");
  ok(akt.context_roles.length >= 3 && akt.context_roles.some((r) => /FOXO/.test(r[1])),
    "Akt lists roles beyond this map, including FOXO, as the reviewer asked");

  // 9. tiers are a study type, not a grade
  realClick(w, canvasEl, D.querySelector('.pw-hitline[data-eid="EVE-RCC"]'));
  const ti = D.getElementById("pwInsp").innerHTML;
  ok(/human trial or cohort|systematic review/.test(ti),
    "a tier letter is rendered together with what that tier MEANS");
  ok(/kind of study, not its quality/.test(ti), "the panel states tiers are not a quality score");

  // 6. legend separates effect from mechanism
  const leg = D.querySelector(".pw-legend").innerHTML;
  ok(/Net effect/.test(leg) && /Mechanistic type/.test(leg),
    "legend presents effect and mechanistic type as two separate axes");
  ["phosphorylation", "translocation", "stabilization", "degradation"].forEach((t) => {
    ok(new RegExp(t).test(leg), `legend lists the "${t}" mechanism the reviewer asked for`);
  });
  ok(/Phosphorylates<\/em> is a mechanism|phosphorylation\s*can just as easily activate|can just as easily activate/.test(leg),
    "legend explains that phosphorylation is a mechanism, not an effect");
  ok(/more curated evidence behind that molecule/.test(leg),
    "legend explains what node border weight means");

  console.log("— organelle build-out (review pass 2) —");
  // Lysosome centrality is a MEASURED claim, not decoration.
  const lyso = model.compartments.find((c) => c.id === "lyso");
  ok(lyso.direct_regulators_total > 0, "lysosome carries a direct-regulator census");
  const directIn = model.interactions.filter((e) => e.target === "mTORC1" && e.directness === "direct");
  ok(lyso.direct_regulators_total === directIn.length,
    `census matches the model (${lyso.direct_regulators_total} direct inputs to mTORC1)`);
  ok(lyso.direct_regulators_here === directIn.filter((e) => e.compartment === "lyso").length,
    "count of direct regulators at the lysosome is computed, not asserted");
  ok(lyso.direct_regulators_elsewhere.every((x) => x.type === "complex-assembly"),
    "the only direct input to mTORC1 outside the lysosome is complex assembly — "
    + "so every direct REGULATOR of activity is lysosomal");
  ok(/switched on/.test(D.querySelector("#pwCanvas svg").innerHTML),
    "the canvas states on the lysosomal band where mTORC1 is switched on");
  model.compartments.filter((c) => c.interaction_count).forEach((c) => {
    ok(typeof c.interaction_share === "number", `${c.id}: has an interaction share`);
  });

  // Mitochondria: bidirectional, and the ROS loop must be POSITIVE.
  ["MITODYS-MTORC1", "MTORC1-OXPHOS", "MTORC1-ROS", "ROS-MTORC1", "MTORC2-MAM", "MTORC1-PGC1A"]
    .forEach((id) => {
      const e = model.interactions.find((x) => x.id === id);
      ok(!!e, `${id} exists`);
      if (e) ok(e.evidence.supporting.length > 0, `${id} cites at least one study`);
    });
  const posLoops = (model.loops || []).filter((l) => l.sign === "positive");
  ok(posLoops.length >= 1,
    "at least one POSITIVE feedback loop is now detected — positive loops amplify rather "
    + "than stabilise, which is a different biological claim from every loop being negative");
  ok(posLoops.some((l) => l.nodes.some((n) => /Reactive oxygen/.test(n))),
    "the ROS <-> mTORC1 loop is the positive one");

  // Nucleus: the arms the reviewer named.
  ["HIF-1α", "FOXO1/3", "PGC-1α / YY1", "TFEB", "SREBP1 / SREBP2"].forEach((n) => {
    ok(model.nodes.some((x) => x.id === n && x.compartment === "nucleus"),
      `${n} is present in the nucleus band`);
  });

  // The TFEB loop must now CLOSE, and must no longer be declared open.
  const tfebLoop = (model.loops || []).find((l) => l.nodes.includes("TFEB"));
  ok(!!tfebLoop, "the TFEB -> lysosomal biogenesis -> lysosome -> mTORC1 loop now closes");
  ok(!(model.open_loops || []).some((o) => /TFEB/.test(o.name)),
    "and it is no longer listed as a loop this map cannot close");

  // Golgi: declared as a gap, never asserted as an edge.
  ok((model.open_localisations || []).some((o) => /Golgi/.test(o.name)),
    "Golgi is declared as an unrepresented localisation");
  ok(!model.interactions.some((e) => /Golgi/i.test(e.source) || /Golgi/i.test(e.target)),
    "no Golgi interaction is asserted, because no corpus study supports one");
  D.getElementById("pwLoops").dispatchEvent(new w.MouseEvent("click", { bubbles: true }));
  ok(/Golgi/.test(D.getElementById("pwInsp").innerHTML),
    "the panel tells the reader that Golgi is missing for want of a paper");
  D.getElementById("pwLoops").dispatchEvent(new w.MouseEvent("click", { bubbles: true }));

  // Numbers about the model must be COMPUTED from it. The default inspector
  // hard-coded "51 of the 100" and silently lied once the model grew to 111.
  console.log("— no hard-coded model counts —");
  w.PathwayApp.setMode("explorer");
  const dtxt = D.getElementById("pwInsp").textContent;
  const mechN = model.interactions.filter(isMech).length;
  const restN = model.interactions.length - mechN;
  ok(dtxt.includes(String(mechN)) && dtxt.includes(String(model.interactions.length)),
    `default panel quotes live counts (${mechN} of ${model.interactions.length})`);
  ok(dtxt.includes(String(restN)), `and the withheld count (${restN}) is computed too`);
  const stale = dtxt.match(/\b(51|49|100)\b/g) || [];
  ok(!stale.length || (mechN === 51 || restN === 49 || model.interactions.length === 100),
    "no stale hard-coded count survives in the default panel");
  // Band labels are pinned to the viewport, so panning cannot clip them.
  ok(D.querySelectorAll("#pwCanvas .pw-bandg").length === model.compartments.length,
    "every band label is in a translatable group");
  const before = D.querySelector("#pwCanvas .pw-bandg").getAttribute("transform");
  D.getElementById("pwOut").dispatchEvent(new w.MouseEvent("click", { bubbles: true }));
  ok(D.querySelector("#pwCanvas .pw-bandg").getAttribute("transform") !== before,
    "band labels reposition when the camera moves, instead of scrolling off");
  ok(!/1 steps/.test(D.querySelector("#pwCanvas svg").textContent),
    "band label counts are pluralised correctly");
  D.getElementById("pwReset").dispatchEvent(new w.MouseEvent("click", { bubbles: true }));

  console.log("— console —");
  ok(errors.length === 0, "no console errors (" + errors.slice(0, 3).join(" | ") + ")");

  console.log("\n" + (fails ? "FAILED" : "PASSED") + `  ${checks - fails}/${checks} checks`);
  process.exit(fails ? 1 : 0);
}).catch((e) => {
  console.log("BOOT FAILED:", e && e.stack || e);
  process.exit(1);
});
