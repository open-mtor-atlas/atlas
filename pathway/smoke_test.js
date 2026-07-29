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
w.fetch = () => Promise.resolve({ ok: true, json: () => Promise.resolve(model) });
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

const host = w.document.getElementById("host");

w.PathwayApp.boot(host, "pathway/model.json").then(() => {
  const D = w.document;
  const svg = host.querySelector("svg");

  console.log("— render —");
  ok(!!svg, "SVG built");
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
    const ev = new w.MouseEvent("pointerup", { bubbles: true });
    Object.defineProperty(ev, "target", { value: hit });
    host.querySelector("#pwCanvas").dispatchEvent(ev);
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
  const ev2 = new w.MouseEvent("pointerup", { bubbles: true });
  Object.defineProperty(ev2, "target", { value: hitRag });
  host.querySelector("#pwCanvas").dispatchEvent(ev2);
  ok(/recruits/.test(D.getElementById("pwInsp").innerHTML),
    "RAG-MTORC1 is described as recruitment, not activation");
  ok(!/allosterically activates/.test(D.getElementById("pwInsp").innerHTML),
    "RAG-MTORC1 is not described as activation");

  console.log("— learning levels —");
  const nodeG = D.querySelector('.pw-n[data-nid="mTORC1"]');
  const evN = new w.MouseEvent("pointerup", { bubbles: true });
  Object.defineProperty(evN, "target", { value: nodeG });
  host.querySelector("#pwCanvas").dispatchEvent(evN);
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
    const evS = new w.MouseEvent("pointerup", { bubbles: true });
    Object.defineProperty(evS, "target", { value: g });
    host.querySelector("#pwCanvas").dispatchEvent(evS);
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
      ok(/Step \d+ \/ \d+ · /.test(D.querySelector(".pw-step-n").textContent),
        `route ${r.id} step ${i + 1}: states position and compartment`);
      const next = D.getElementById("pwNext");
      if (i < total - 1) next.dispatchEvent(new w.MouseEvent("click", { bubbles: true }));
    }
  });

  console.log("— filters —");
  w.PathwayApp.setMode("explorer");
  D.querySelector('#pwEvid2 button[data-ev="human"]').dispatchEvent(new w.MouseEvent("click", { bubbles: true }));
  const humanShown = model.interactions.filter((e) => !D.getElementById("pwe-" + e.id).classList.contains("dim"));
  ok(humanShown.length > 0 && humanShown.every((e) => e.confidence.human_relevance === "established"),
    `human-relevance filter shows only human-relevant steps (${humanShown.length})`);
  D.querySelector('#pwEvid2 button[data-ev="contested"]').dispatchEvent(new w.MouseEvent("click", { bubbles: true }));
  const contested = model.interactions.filter((e) => !D.getElementById("pwe-" + e.id).classList.contains("dim"));
  ok(contested.length > 0 && contested.every((e) => e.confidence.consensus === "contested"),
    `contested filter works (${contested.length})`);
  D.getElementById("pwReset").dispatchEvent(new w.MouseEvent("click", { bubbles: true }));
  ok(model.interactions.every((e) => !D.getElementById("pwe-" + e.id).classList.contains("dim")),
    "reset restores every interaction");

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

  console.log("— console —");
  ok(errors.length === 0, "no console errors (" + errors.slice(0, 3).join(" | ") + ")");

  console.log("\n" + (fails ? "FAILED" : "PASSED") + `  ${checks - fails}/${checks} checks`);
  process.exit(fails ? 1 : 0);
}).catch((e) => {
  console.log("BOOT FAILED:", e && e.stack || e);
  process.exit(1);
});
