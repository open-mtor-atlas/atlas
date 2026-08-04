/* =========================================================================
   pathway.js — Pathway & Mechanism 2.0
   Lazy-loaded module. Reads pathway/model.json, which is the single source
   of truth for pathway biology (built by build_pathway_model.py, gated by
   validate_pathway.py).

   WHY THIS IS A SEPARATE FILE
   The previous explorer lived inside a 1.5 MB index.html together with
   hand-tuned layout constants and a second, independent copy of the same
   pathway (MAP_NODES / MAP_CORE_EDGES). Two consequences: the two copies
   drifted, and every explorer change risked the whole page. This module
   owns the section, is fetched only when the Pathway tab is first opened,
   and derives every pixel from the model.

   WHAT IT DELIBERATELY DOES NOT DO
   It never invents biology. Every sentence shown to the user is either a
   curated field from model.json or a template assembled from curated
   fields, and templates state their own limits ("multiple steps compressed"
   rather than pretending a relay is one event).
   ========================================================================= */
(function () {
  "use strict";

  var M = null;                          // the model
  var el = {};                           // cached DOM
  var S = {                              // UI state
    mode: "overview",
    level: "student",
    detail: "core",
    sel: null, selKind: null,
    focus: null, hops: 1,
    /* detail: "core" | "full".
       The explorer must not open as a hairball. Principle 1 of the redesign
       is "never overwhelm beginners", and 100 interactions at fit-all zoom
       does exactly that. "Core" is a PRINCIPLED subset, not a hand-picked
       one: single molecular events we understand mechanistically
       (directness === direct AND mechanistic === high) — 51 of 100. The
       label says so, so the reader knows what is being withheld and why. */
    /* Reviewer point 8: the old Core/Full toggle graded CONFIDENCE, which is
       not the same axis as ABSTRACTION. "Who talks to whom" and "how it works
       molecularly" are different questions and now have their own control.
       The confidence rule did not disappear — it moved to the evidence
       filters as "Well understood". */
    view: "mechanism",          // mechanism | pathway
    /* Reviewer point 3: the network is not a circuit. Cumulative time window,
       so the map unfolds instead of arriving all at once. */
    timeMax: "all",             // seconds | minutes | hours | days | chronic | all
    loopsOnly: false, highlightLoop: null,
    filters: { effect: null, evidence: null, physOnly: false },
    routeId: null, step: -1,
    cam: null, camTarget: null, anim: null, snap: null
  };

  var NH = 30, LANE = 13;
  var LEVELS = ["beginner", "student", "research"];

  /* ---- helpers --------------------------------------------------------- */
  function esc(s) {
    return String(s == null ? "" : s).replace(/&/g, "&amp;").replace(/</g, "&lt;")
      .replace(/>/g, "&gt;").replace(/"/g, "&quot;");
  }
  function $(id) { return document.getElementById(id); }
  function nodeById(id) { return M.nodeIx[id]; }
  function edgeById(id) { return M.edgeIx[id]; }
  function nw(label) { return Math.max(76, String(label).length * 7.4 + 24); }
  function reduced() {
    return window.matchMedia && window.matchMedia("(prefers-reduced-motion:reduce)").matches;
  }
  function say(msg) { if (el.sr) el.sr.textContent = msg; }

  /* Mechanistic verb phrases. The whole point of the redesign: an arrow is
     not a verb. "Recruits" and "activates" are different claims, and the
     reader must be told which one they are looking at. */
  var VERB = {
    "binding": "binds",
    "recruitment": "recruits",
    "localisation": "provides the location required by",
    "translocation": "relocates",
    "scaffolding": "tethers",
    "phosphorylation": "phosphorylates",
    "dephosphorylation": "reverses the lipid signal read by",
    "gap-activity": "acts as a GAP on",
    "gef-activity": "acts as a GEF on",
    "complex-assembly": "assembles into",
    "complex-disassembly": "disassembles",
    "allosteric-activation": "allosterically activates",
    "allosteric-inhibition": "allosterically inhibits",
    "competitive-inhibition": "competitively blocks",
    "transcriptional": "transcriptionally controls",
    "transport": "transports",
    "signal-relay": "relays a signal to",
    "functional-consequence": "changes",
    "clinical-outcome": "changes, in clinical trials,",
    "association": "is statistically associated with",
    "stabilization": "stabilises",
    "degradation": "triggers the degradation of"
  };
  var TYPE_TAG = {
    "phosphorylation": "P", "dephosphorylation": "−P", "gap-activity": "GAP",
    "gef-activity": "GEF", "recruitment": "MOVE", "translocation": "MOVE",
    "localisation": "LOC", "scaffolding": "HOLD", "binding": "BIND",
    "complex-assembly": "ASM", "complex-disassembly": "DIS",
    "allosteric-activation": "ALLO", "allosteric-inhibition": "ALLO",
    "competitive-inhibition": "COMP", "transcriptional": "TXN",
    "transport": "TRANS", "signal-relay": "⋯", "functional-consequence": "→",
    "clinical-outcome": "TRIAL", "association": "?",
    "stabilization": "STAB", "degradation": "DEGR"
  };
  var MARK = {
    "activates": "pwArrowA", "inhibits": "pwBar", "required-for": "pwChev",
    "recruits": "pwChev", "binds": "pwDot", "context-dependent": "pwQ"
  };
  /* Reviewer point 9: a bare letter reads as a grade. The Atlas already has
     descriptive labels site-wide (TIER_LABELS); the pathway panel just never
     showed them. Never render a tier letter without its meaning next to it. */
  var TIER_MEANING = {
    A: "systematic review / meta-analysis",
    B: "human trial or cohort",
    C: "animal or invertebrate model",
    D: "mechanistic — cell culture, structure or review",
    PP: "preprint, not yet peer-reviewed",
    RT: "registered trial, results pending"
  };
  var CONF_W = { high: 100, medium: 62, low: 28 };
  var CONF_C = { high: "g", medium: "a", low: "r" };
  var HR_W = { established: 100, plausible: 55, untested: 18 };
  var HR_C = { established: "g", plausible: "a", untested: "r" };

  /* ==== 1. OVERVIEW ====================================================
     The brief asked for a vertical cascade:
         Growth factors -> Nutrients -> Energy -> Stress -> mTOR
     That diagram would teach a misconception. Those four are PARALLEL,
     independent inputs converging on one hub; growth factors do not feed
     into nutrient sensing. Drawing them in series implies a causal chain
     that does not exist and would have to be unlearned in the Explorer.
     So the overview keeps the promise (understand mTOR in 15 seconds)
     with the correct topology: four inputs converge, one hub decides,
     outputs fan out — and it names the coincidence rule explicitly,
     because that rule IS the logic of the pathway.
     ==================================================================== */
  var OV_IN = [
    ["Growth factors", "is it safe to grow?", "gf"],
    ["Nutrients", "are the parts available?", "aa"],
    ["Energy", "can we afford it?", "energy"],
    ["Stress", "is anything wrong?", "energy"]
  ];
  var OV_OUT = [
    ["Protein synthesis", "build"], ["Lipid + nucleotide synthesis", "build"],
    ["Cell growth", "build"], ["Autophagy", "recycle — switched OFF"]
  ];

  function renderOverview() {
    /* 4 columns of colW plus 3 gaps = 940, and they start at x=34, so the
       canvas must be 34*2 wider than the content or the last column is
       clipped. It was: the fourth input box ended at x=974 in a 940-wide
       viewBox and "is anything wrong?" was cut off on the live page. */
    var colW = 214, gap = 28, pad = 34;
    var W = pad * 2 + colW * 4 + gap * 3, y0 = 96, hubY = 300, outY = 470;
    var s = '<svg class="pw-ov-svg" viewBox="0 0 ' + W + ' 600" role="img" aria-label="' +
      'How mTOR works: four independent inputs converge on mTORC1, which decides between building and recycling">';
    s += '<text class="ov-cap" x="' + (W / 2) + '" y="26" text-anchor="middle">FOUR INDEPENDENT QUESTIONS · ASKED AT THE SAME TIME</text>';
    OV_IN.forEach(function (o, i) {
      var x = pad + i * (colW + gap), cx = x + colW / 2;
      s += '<g class="ov-in ov-hit" data-route="' + o[2] + '" tabindex="0" role="button" aria-label="' + esc(o[0]) + ' — open guided route">'
        + '<rect class="ov-box" x="' + x + '" y="' + y0 + '" width="' + colW + '" height="58"/>'
        + '<text x="' + cx + '" y="' + (y0 + 24) + '" text-anchor="middle">' + esc(o[0]) + '</text>'
        + '<text class="ov-cap" x="' + cx + '" y="' + (y0 + 43) + '" text-anchor="middle">' + esc(o[1]) + '</text></g>';
      s += '<path class="ov-arm" d="M' + cx + ',' + (y0 + 58) + ' C' + cx + ',' + (y0 + 110)
        + ' ' + (W / 2) + ',' + (hubY - 66) + ' ' + (W / 2) + ',' + (hubY - 26) + '" marker-end="url(#ovA)"/>';
    });
    s += '<g class="ov-hub"><rect class="ov-box" x="' + (W / 2 - 132) + '" y="' + (hubY - 22)
      + '" width="264" height="70"/><text x="' + (W / 2) + '" y="' + (hubY + 15)
      + '" text-anchor="middle">mTORC1</text></g>';
    s += '<text class="ov-cap" x="' + (W / 2) + '" y="' + (hubY + 68)
      + '" text-anchor="middle">SWITCHES ON ONLY IF THE ANSWERS AGREE</text>';
    OV_OUT.forEach(function (o, i) {
      var x = pad + i * (colW + gap), cx = x + colW / 2;
      s += '<path class="ov-arm" d="M' + (W / 2) + ',' + (hubY + 78) + ' C' + (W / 2) + ',' + (outY - 40)
        + ' ' + cx + ',' + (outY - 46) + ' ' + cx + ',' + outY + '" marker-end="url(#ovA)"/>';
      s += '<g class="ov-out"><rect class="ov-box" x="' + x + '" y="' + outY + '" width="' + colW + '" height="56"/>'
        + '<text x="' + cx + '" y="' + (outY + 24) + '" text-anchor="middle" font-size="11.5">' + esc(o[0]) + '</text>'
        + '<text class="ov-cap" x="' + cx + '" y="' + (outY + 42) + '" text-anchor="middle">' + esc(o[1]) + '</text></g>';
    });
    s += '<defs><marker id="ovA" markerUnits="userSpaceOnUse" markerWidth="11" markerHeight="11" viewBox="0 0 10 10" '
      + 'refX="9" refY="5" orient="auto"><path d="M0.5,1 L9.5,5 L0.5,9 Z" fill="currentColor" opacity=".55"/></marker></defs>';
    s += "</svg>";

    var n = M.meta.counts;
    el.ov.innerHTML =
      '<p class="pw-ov-lede">mTOR is the cell\'s <b>investment committee</b>. It does not sense one thing — '
      + 'it collects four independent reports about the outside world and only authorises building when they agree.</p>'
      + '<p class="pw-ov-sub">Growth factors say whether growing is <em>permitted</em>. Nutrients say whether the raw materials '
      + '<em>exist</em>. Energy says whether the cell can <em>afford</em> the work. Stress says whether anything is <em>wrong</em>. '
      + 'When the answers agree, mTORC1 switches on and the cell builds. When they do not, mTORC1 goes quiet and the cell '
      + 'starts recycling itself instead. Everything else on this page is the machinery that makes that one decision.</p>'
      + s
      + '<p class="pw-ov-note"><b>Read the shape, not just the words.</b> The four inputs are drawn side by side because they '
      + 'are <em>parallel and independent</em> — growth factors do not feed into nutrient sensing. A textbook that stacks them '
      + 'in a single chain is teaching a chain that does not exist. Inside the cell the independence is physical: nutrients '
      + 'control <em>where</em> mTORC1 sits, growth factors control <em>whether it is switched on</em>. Neither alone is enough. '
      + 'That is called coincidence detection, and it is the single most important idea in this pathway.</p>'
      + '<div class="pw-ov-acts">'
      + '<button class="pw-ov-act" data-go="explorer"><b>Explore the network →</b><span>All ' + n.interactions
      + ' curated steps in ' + M.compartments.length + ' cellular compartments. Zoom, search, filter by evidence.</span></button>'
      + '<button class="pw-ov-act" data-go="guided"><b>Follow a guided route →</b><span>' + n.routes
      + ' narrated walkthroughs. Each one answers what happened, why, what changed, and how certain we are.</span></button>'
      + '<button class="pw-ov-act" data-go="scenarios"><b>Experiment with scenarios →</b><span>Starvation, PTEN loss, '
      + 'rapamycin. Qualitative, clearly labelled as educational modelling.</span></button>'
      + "</div>";
    el.ov.querySelectorAll("[data-go]").forEach(function (b) {
      b.addEventListener("click", function () { setMode(b.dataset.go); });
    });
    el.ov.querySelectorAll("[data-route]").forEach(function (g) {
      function open() { S.routeId = g.dataset.route; setMode("guided"); }
      g.addEventListener("click", open);
      g.addEventListener("keydown", function (e) {
        if (e.key === "Enter" || e.key === " ") { e.preventDefault(); open(); }
      });
    });
  }

  /* ==== 2. EXPLORER — geometry ========================================= */
  function anchor(n, tx, ty) {
    var w = nw(n.label) / 2, h = NH / 2, dx = tx - n.x, dy = ty - n.y;
    if (!dx && !dy) return { x: n.x, y: n.y };
    var sx = dx === 0 ? Infinity : w / Math.abs(dx);
    var sy = dy === 0 ? Infinity : h / Math.abs(dy);
    var k = Math.min(sx, sy);
    return { x: n.x + dx * k, y: n.y + dy * k };
  }

  function geom(e) {
    var A = nodeById(e.source), B = nodeById(e.target);
    if (!A || !B) return null;
    var lane = (e._lane || 0) * LANE;
    var sameBand = Math.abs(A.y - B.y) < 4;
    var c1, c2, a, b;
    if (sameBand) {
      // arc out of the band so a within-compartment edge never runs under boxes
      var up = A.x <= B.x ? -1 : 1, rise = 44 + Math.abs(lane);
      c1 = { x: A.x + (B.x - A.x) * 0.25, y: A.y + up * rise };
      c2 = { x: A.x + (B.x - A.x) * 0.75, y: B.y + up * rise };
    } else {
      var mid = (A.y + B.y) / 2;
      c1 = { x: A.x + lane, y: mid };
      c2 = { x: B.x - lane, y: mid };
    }
    a = anchor(A, c1.x, c1.y); b = anchor(B, c2.x, c2.y);
    var d = "M" + a.x.toFixed(1) + "," + a.y.toFixed(1) + " C" + c1.x.toFixed(1) + "," + c1.y.toFixed(1)
      + " " + c2.x.toFixed(1) + "," + c2.y.toFixed(1) + " " + b.x.toFixed(1) + "," + b.y.toFixed(1);
    var m = { x: (a.x + 3 * c1.x + 3 * c2.x + b.x) / 8, y: (a.y + 3 * c1.y + 3 * c2.y + b.y) / 8 };
    return { d: d, mid: m, a: a, b: b };
  }

  function assignLanes() {
    var buckets = {};
    M.interactions.forEach(function (e) {
      var k = e.source + "|" + nodeById(e.target).compartment;
      (buckets[k] = buckets[k] || []).push(e);
    });
    Object.keys(buckets).forEach(function (k) {
      var g = buckets[k];
      g.forEach(function (e, i) { e._lane = g.length === 1 ? 0 : (i - (g.length - 1) / 2) * 2; });
    });
  }

  function defs() {
    var d = '<defs>'
      + '<pattern id="pwHatch" width="7" height="7" patternTransform="rotate(45)" patternUnits="userSpaceOnUse">'
      + '<line x1="0" y1="0" x2="0" y2="7" stroke="currentColor" stroke-width="1" opacity=".07"/></pattern>';
    var head = 'markerUnits="userSpaceOnUse" markerWidth="13" markerHeight="13" viewBox="0 0 10 10" orient="auto"';
    /* Markers use currentColor, and every f-* class sets BOTH stroke and color.
       `context-stroke` would be tidier but is not universally supported; a
       marker inheriting `color` from its referencing path is. */
    d += '<marker id="pwArrowA" ' + head + ' refX="9" refY="5"><path d="M0.5,1 L9.5,5 L0.5,9 Z" fill="currentColor"/></marker>';
    d += '<marker id="pwBar" ' + head + ' refX="5" refY="5"><path d="M5,0.6 L5,9.4" stroke="currentColor" stroke-width="2.8" fill="none"/></marker>';
    d += '<marker id="pwChev" ' + head + ' refX="8" refY="5"><path d="M1,1 L8,5 L1,9" stroke="currentColor" stroke-width="1.9" fill="none"/></marker>';
    d += '<marker id="pwDot" ' + head + ' refX="5" refY="5"><circle cx="5" cy="5" r="3.4" fill="currentColor"/></marker>';
    d += '<marker id="pwQ" ' + head + ' refX="5" refY="5"><circle cx="5" cy="5" r="3.6" fill="none" stroke="currentColor" stroke-width="1.6"/></marker>';
    return d + "</defs>";
  }

  function buildSVG() {
    var W = M.meta.canvas.w, H = M.meta.canvas.h;
    var s = '<svg viewBox="0 0 ' + W + " " + H + '" preserveAspectRatio="xMidYMid meet" role="application" '
      + 'aria-label="mTOR mechanism network, arranged by cellular compartment">' + defs();

    // bands
    s += '<g class="pw-bands" aria-hidden="true">';
    M.bands.forEach(function (b, i) {
      var c = M.compIx[b.compartment];
      s += '<rect class="' + (c.physical ? "pw-band-phys" : "pw-band-hatch") + '" x="0" y="' + b.y
        + '" width="' + W + '" height="' + b.h + '"/>';
      s += '<line class="' + (c.physical && i > 0 ? "pw-membrane" : "pw-bandline") + '" x1="0" y1="' + b.y
        + '" x2="' + W + '" y2="' + b.y + '"/>';
      /* Band labels carry their share of curated interactions. The reviewer
         asked for the lysosome to be "central"; the honest way to say that is
         with the number, not with decoration. */
      // BUG 3: "1 steps". Counts get singular/plural like anything else.
      var nsteps = c.interaction_count;
      var lab = c.name + (nsteps ? "  ·  " + nsteps + (nsteps === 1 ? " step" : " steps") : "");
      s += '<g class="pw-bandg">'
        + '<text class="pw-bandlab" x="16" y="' + (b.y + 16) + '">' + esc(lab) + "</text>";
      if (c.id === "lyso") {
        s += '<text class="pw-bandhead" x="' + (16 + lab.length * 7.4) + '" y="' + (b.y + 16)
          + '">' + esc("— where mTORC1 is switched on: " + c.direct_regulators_here + "/"
            + c.direct_regulators_total + " of its direct inputs") + "</text>";
      }
      s += "</g>";
      if (!c.physical) {
        s += '<text class="pw-bandwarn" x="' + (16 + c.name.length * 8.2) + '" y="' + (b.y + 16)
          + '">— NOT A CELLULAR LOCATION</text>';
      }
    });
    s += "</g>";

    // interactions
    var hits = "", lines = "", tags = "";
    M.interactions.forEach(function (e) {
      var g = geom(e); if (!g) return;
      e._g = g;
      var cls = "pw-e f-" + e.effect + " d-" + e.directness + " m-" + e.confidence.mechanistic;
      if (e.confidence.consensus === "contested") {
        lines += '<path class="pw-contest" data-eid="' + esc(e.id) + '" d="' + g.d + '"/>';
      }
      lines += '<path id="pwe-' + esc(e.id) + '" class="' + cls + '" data-eid="' + esc(e.id) + '" d="' + g.d
        + '" marker-end="url(#' + (MARK[e.effect] || "pwArrowA") + ')"/>';
      hits += '<path class="pw-hitline" data-eid="' + esc(e.id) + '" d="' + g.d + '"><title>'
        + esc(sentence(e)) + "</title></path>";
      var tag = TYPE_TAG[e.type] || "";
      if (tag) {
        var tw = tag.length * 6 + 8;
        tags += '<g class="pw-tagg" data-eid="' + esc(e.id) + '">'
          + '<rect class="pw-tagbg" x="' + (g.mid.x - tw / 2).toFixed(1) + '" y="' + (g.mid.y - 7).toFixed(1)
          + '" width="' + tw + '" height="14"/>'
          + '<text class="pw-tag" x="' + g.mid.x.toFixed(1) + '" y="' + (g.mid.y + 0.5).toFixed(1) + '">'
          + esc(tag) + "</text></g>";
      }
    });
    s += '<g class="pw-edges">' + lines + tags + hits + "</g>";

    // nodes
    s += '<g class="pw-nodes">';
    M.nodes.forEach(function (n) {
      var w = nw(n.label), x = n.x - w / 2, y = n.y - NH / 2;
      /* Reviewer point 2: every node looked equally important, and they are not.
         Border weight now reflects how much curated evidence sits behind the
         molecule. Weight is a HINT ONLY — the exact count is in the inspector
         and in the aria-label, so this never becomes the sole channel. */
      var ne = n.evidence || {}, sc = ne.studies_in_corpus || 0;
      var wclass = sc >= 20 ? "ev-hi" : sc >= 8 ? "ev-mid" : sc >= 3 ? "ev-lo" : "ev-min";
      s += '<g class="pw-n c-' + esc(n.cls) + " " + wclass + '" data-nid="' + esc(n.id) + '" tabindex="0" role="button" '
        + 'aria-label="' + esc(n.label + ", " + n.cls + " in " + M.compIx[n.compartment].name
          + ", " + sc + " studies in this corpus, strongest evidence "
          + (TIER_MEANING[ne.best_tier] || "not recorded")) + '">'
        + '<rect class="nb" x="' + x.toFixed(1) + '" y="' + y.toFixed(1) + '" width="' + w.toFixed(1)
        + '" height="' + NH + '"/>';
      if (n.cls === "complex") {
        s += '<rect class="nb2" x="' + (x + 3.2).toFixed(1) + '" y="' + (y + 3.2).toFixed(1)
          + '" width="' + (w - 6.4).toFixed(1) + '" height="' + (NH - 6.4) + '"/>';
      }
      s += '<text x="' + n.x + '" y="' + (n.y + 0.5) + '">' + esc(n.label) + "</text></g>";
    });
    s += "</g></svg>";
    return s;
  }

  function sentence(e) {
    return nodeById(e.source).label + " " + (VERB[e.type] || e.type) + " " + nodeById(e.target).label
      + " — net effect: " + e.effect + " (" + e.directness + ", " + e.timescale + ")";
  }

  /* ==== camera ========================================================= */
  function applyCam() {
    var c = S.cam;
    el.svg.setAttribute("viewBox", c.x.toFixed(1) + " " + c.y.toFixed(1) + " " + c.w.toFixed(1) + " " + c.h.toFixed(1));
    /* Band labels are pinned to the left edge of the CURRENT view. Drawn at a
       fixed canvas x they scrolled off as soon as the reader panned, and a
       half-clipped label reads as a broken diagram rather than as a label. */
    if (el.svg.__bandlabs) {
      var x = c.x + c.w * 0.012;
      el.svg.__bandlabs.forEach(function (g) {
        g.setAttribute("transform", "translate(" + (x - 16).toFixed(1) + ",0)");
      });
    }
  }
  function updateHint() {
    var box = $("pwHintBox"); if (!box) return;
    var shown = M.interactions.filter(edgePasses).length;
    var bits = [];
    bits.push("<b>" + (S.view === "mechanism" ? "Mechanism" : "Pathway") + " view</b> — "
      + shown + " of " + M.interactions.length + " steps");
    if (S.view === "mechanism") bits.push("molecular events only; switch VIEW to Pathway for compressed links and outcomes");
    if (S.timeMax !== "all") bits.push("cumulative up to <b>" + S.timeMax + "</b>");
    if (S.loopsOnly) bits.push("<b>feedback loops only</b>");
    box.innerHTML = bits.join(" · ");
  }


  /* Opening camera frames the signalling core (plasma membrane → lysosome),
     not the whole canvas. Outcomes and inputs are one scroll away rather
     than competing for attention with the mechanism on first paint. */
  function frameCore() {
    var band = M.bands.filter(function (b) {
      return ["pm", "cytosol", "lyso"].indexOf(b.compartment) >= 0;
    });
    if (!band.length) return fitAll();
    var y1 = Math.min.apply(null, band.map(function (b) { return b.y; }));
    var y2 = Math.max.apply(null, band.map(function (b) { return b.y + b.h; }));
    var r = el.canvas.clientWidth / Math.max(1, el.canvas.clientHeight);
    var h = (y2 - y1) + 40, w = h * r;
    if (w < M.meta.canvas.w * 0.86) { w = M.meta.canvas.w * 0.86; h = w / r; }
    S.cam = { x: (M.meta.canvas.w - w) / 2, y: y1 - (h - (y2 - y1)) / 2, w: w, h: h };
    applyCam();
  }

  function fitAll() {
    var W = M.meta.canvas.w, H = M.meta.canvas.h;
    var r = el.canvas.clientWidth / Math.max(1, el.canvas.clientHeight);
    var w = W, h = W / r;
    if (h < H) { h = H; w = H * r; }
    S.cam = { x: (W - w) / 2, y: (H - h) / 2, w: w, h: h };
    applyCam();
  }
  function frameBox(bx, by, bw, bh, pad) {
    pad = pad == null ? 190 : pad;
    var r = el.canvas.clientWidth / Math.max(1, el.canvas.clientHeight);
    var w = Math.max(bw + pad * 2, 420), h = w / r;
    if (h < bh + pad * 2) { h = bh + pad * 2; w = h * r; }
    animCam({ x: bx + bw / 2 - w / 2, y: by + bh / 2 - h / 2, w: w, h: h });
  }
  function frameNode(id) { var n = nodeById(id); if (n) frameBox(n.x - 60, n.y - 20, 120, 40, 240); }
  function frameEdge(id) {
    var e = edgeById(id); if (!e || !e._g) return;
    var A = nodeById(e.source), B = nodeById(e.target);
    var x1 = Math.min(A.x, B.x) - 90, x2 = Math.max(A.x, B.x) + 90;
    var y1 = Math.min(A.y, B.y) - 60, y2 = Math.max(A.y, B.y) + 60;
    frameBox(x1, y1, x2 - x1, y2 - y1, 90);
  }
  function animCam(to) {
    if (reduced()) { S.cam = to; applyCam(); return; }
    if (S.anim) cancelAnimationFrame(S.anim);
    if (S.snap) clearTimeout(S.snap);
    var from = { x: S.cam.x, y: S.cam.y, w: S.cam.w, h: S.cam.h }, t0 = performance.now(), T = 480;
    var done = false;
    /* Safety net. requestAnimationFrame does not fire at all in a hidden or
       heavily throttled tab, so a tween started while the tab is backgrounded
       would leave the camera stranded at frame 0 — the reader returns to a
       route step whose subject is off screen. The tween stays the nice path;
       this guarantees the destination regardless. */
    S.snap = setTimeout(function () {
      if (done) return;
      if (S.anim) cancelAnimationFrame(S.anim);
      S.cam = to; applyCam();
    }, T + 80);
    (function tick(now) {
      var p = Math.min(1, (now - t0) / T), k = p < .5 ? 4 * p * p * p : 1 - Math.pow(-2 * p + 2, 3) / 2;
      S.cam = { x: from.x + (to.x - from.x) * k, y: from.y + (to.y - from.y) * k,
                w: from.w + (to.w - from.w) * k, h: from.h + (to.h - from.h) * k };
      applyCam();
      if (p < 1) S.anim = requestAnimationFrame(tick);
      else { done = true; clearTimeout(S.snap); }
    })(t0);
  }
  function zoomAt(cx, cy, k) {
    var r = el.canvas.getBoundingClientRect();
    var fx = (cx - r.left) / r.width, fy = (cy - r.top) / r.height;
    var px = S.cam.x + S.cam.w * fx, py = S.cam.y + S.cam.h * fy;
    var w = Math.max(300, Math.min(M.meta.canvas.w * 2.4, S.cam.w * k));
    var h = w * (S.cam.h / S.cam.w);
    S.cam = { x: px - w * fx, y: py - h * fy, w: w, h: h };
    applyCam();
  }

  /* ==== paint (filters, focus, selection) ============================== */
  function neighbourhood(nid, hops) {
    var keep = {}, frontier = [nid];
    keep[nid] = 1;
    for (var h = 0; h < hops; h++) {
      var next = [];
      M.interactions.forEach(function (e) {
        if (keep[e.source] && !keep[e.target]) { next.push(e.target); }
        if (keep[e.target] && !keep[e.source]) { next.push(e.source); }
      });
      next.forEach(function (n) { keep[n] = 1; });
      frontier = next;
    }
    return keep;
  }
  function isCore(e) {
    return e.directness === "direct" && e.confidence.mechanistic === "high";
  }
  /* A compressed link stands in for several molecular events, or reports an
     organism-level consequence. Those belong to "who talks to whom", not to
     "how it works". */
  var COMPRESSED = { "signal-relay": 1, "functional-consequence": 1,
                     "clinical-outcome": 1, "association": 1 };
  function isMechanism(e) { return !COMPRESSED[e.type]; }

  var TIME_ORDER = ["constitutive", "seconds", "minutes", "hours", "days", "chronic"];
  function withinTime(e) {
    if (S.timeMax === "all") return true;
    // constitutive = always true, so it is present in every window
    if (e.timescale === "constitutive") return true;
    return TIME_ORDER.indexOf(e.timescale) <= TIME_ORDER.indexOf(S.timeMax);
  }
  function edgePasses(e) {
    var f = S.filters;
    /* Route mode always shows the route's own edges regardless of detail set:
       a guided lesson must never hide the step it is teaching. */
    if (S.mode !== "guided") {
      if (S.view === "mechanism" && !isMechanism(e)) return false;
      if (!withinTime(e)) return false;
      if (S.loopsOnly && !(e.loops && e.loops.length)) return false;
    }
    if (f.effect && e.effect !== f.effect) return false;
    if (f.evidence === "core" && !isCore(e)) return false;
    if (f.evidence === "human" && e.confidence.human_relevance !== "established") return false;
    if (f.evidence === "direct" && e.directness !== "direct") return false;
    if (f.evidence === "contested" && e.confidence.consensus !== "contested") return false;
    if (f.physOnly && !M.compIx[e.compartment].physical) return false;
    return true;
  }
  function paint() {
    var keep = S.focus ? neighbourhood(S.focus, S.hops) : null;
    var routeSet = null;
    if (S.mode === "guided" && S.routeId) {
      routeSet = {};
      (M.routeIx[S.routeId].interactions || []).forEach(function (i) { routeSet[i] = 1; });
    }
    var shownNodes = {};
    M.interactions.forEach(function (e) {
      var p = $("pwe-" + e.id); if (!p) return;
      var ok = edgePasses(e)
        && (!keep || (keep[e.source] && keep[e.target]))
        && (!routeSet || routeSet[e.id])
        && (!S.highlightLoop || (e.loops || []).indexOf(S.highlightLoop) >= 0);
      p.classList.toggle("dim", !ok);
      p.classList.toggle("sel", S.selKind === "edge" && S.sel === e.id);
      var tg = el.svg.querySelector('.pw-tagg[data-eid="' + e.id + '"]');
      if (tg) tg.style.opacity = ok ? (S.cam.w < 1100 ? 1 : 0) : 0;
      var ct = el.svg.querySelector('.pw-contest[data-eid="' + e.id + '"]');
      if (ct) ct.style.opacity = ok ? "" : 0;
      if (ok) { shownNodes[e.source] = 1; shownNodes[e.target] = 1; }
    });
    el.svg.querySelectorAll(".pw-n").forEach(function (g) {
      var id = g.dataset.nid;
      g.classList.toggle("dim", !shownNodes[id]);
      g.classList.toggle("sel", S.selKind === "node" && S.sel === id);
    });
  }

  /* ==== inspector ====================================================== */
  function tierDot(t) {
    var map = { A: "var(--tier-a)", B: "var(--tier-b)", C: "var(--tier-c)", D: "var(--tier-d)",
                PP: "var(--tier-pp)", RT: "var(--tier-rt)" };
    var c = map[t] || "var(--tier-d)";
    var meaning = TIER_MEANING[t] || "study type not recorded";
    /* PP and RT are completeness STATUS, not a kind of study, so they render
       outlined rather than filled — a different claim gets a different form,
       not just a different hue. */
    var status = (t === "PP" || t === "RT");
    var style = status ? "color:" + c + ";border:1.5px solid " + c + ";background:transparent;"
                       : "background:" + c + ";";
    return '<i class="pw-dot' + (status ? " st" : "") + '" style="' + style
      + '" title="' + esc(meaning + " — the kind of study, not its quality") + '">' + esc(t || "?") + "</i>";
  }
  /* Never a bare letter. The tier says what KIND of study it is; it is not a
     mark out of four, and a tier-D structural paper can be definitive. */
  function tierPhrase(t) {
    return tierDot(t) + " <span class=\"pw-tiername\">" + esc(TIER_MEANING[t] || "type not recorded") + "</span>";
  }
  function studyRows(sids, label) {
    if (!sids || !sids.length) return "";
    var out = '<div class="k">' + label + " (" + sids.length + ")</div>";
    sids.forEach(function (sid) {
      var st = (typeof studyBySid === "function") ? studyBySid(sid) : null;
      if (!st) { out += '<div class="pw-ev-m">' + esc(sid) + " — not in corpus</div>"; return; }
      var first = st.authors ? String(st.authors).split(";")[0].trim() : "";
      out += '<button class="pw-ev" data-sid="' + esc(sid) + '" type="button">'
        + '<span class="pw-ev-t">' + esc(st.title) + "</span>"
        + '<span class="pw-ev-m">' + tierDot((st.tier || "").toUpperCase()[0]) + esc(first)
        + (first ? " · " : "") + esc(st.year || "") + " · " + esc(sid) + "</span></button>";
    });
    return out;
  }
  function confBlock(e) {
    var c = e.confidence;
    return '<div class="k">Confidence — three separate things</div><div class="pw-conf">'
      + meter("Mechanism", c.mechanistic, CONF_W[c.mechanistic], CONF_C[c.mechanistic])
      + meter("Human relevance", c.human_relevance, HR_W[c.human_relevance], HR_C[c.human_relevance])
      + '<div class="pw-confrow"><span>Field consensus</span><span><b>' + esc(c.consensus) + "</b></span></div>"
      + '<div class="pw-confrow"><span>Strongest study</span><span>' + tierPhrase(e.evidence.best_tier)
      + "</span></div>"
      + '<div class="pw-confrow"><span>How it was shown</span><span>' + esc(e.evidence.kind) + "</span></div></div>"
      + '<p style="font-size:11.5px;color:var(--ink-soft);margin-top:9px;line-height:1.55;">'
      + "A step can be mechanistically certain and still untested in humans. "
      + "<b>Tiers describe the kind of study, not its quality</b> — A/B are human evidence, C is animal, "
      + "D is mechanistic work in cells, structures and reviews. A tier-D structural paper can settle a "
      + "mechanism outright; it simply is not human evidence. Mechanism confidence grades the "
      + "<em>biology</em>, tier grades the <em>study design</em>.</p>";
  }
  function meter(label, val, w, c) {
    return '<div class="pw-confrow"><span>' + label + '</span><span class="pw-meter ' + c
      + '"><i style="width:' + w + '%"></i></span><span style="flex:0 0 78px;text-align:right"><b>'
      + esc(val) + "</b></span></div>";
  }

  /* Reviewer point 4: the loops were in the data but never named, so the map
     read as linear. Loops are detected in the build, so this list can never
     disagree with the arrows it is made of. */
  function loopBlock(e) {
    if (!e.loops || !e.loops.length) return "";
    return '<div class="k">Part of a feedback loop</div>'
      + e.loops.map(function (lid) {
          var lp = M.loopIx[lid]; if (!lp) return "";
          return '<button class="pw-ev" data-loop="' + esc(lid) + '" type="button">'
            + '<span class="pw-ev-t">' + esc(lp.name) + "</span>"
            + '<span class="pw-ev-m">' + esc(lp.sign) + " feedback · " + lp.length
            + " steps · " + esc(lp.nodes.join(" → ")) + "</span></button>";
        }).join("");
  }

  function inspectLoops() {
    S.sel = null; S.selKind = "loops";
    var h = "<h4>" + M.loops.length + " feedback loops</h4>"
      + '<p class="pw-empty">mTOR is not a one-way cascade. A loop does not have a direction so much as a '
      + "<em>set point</em>, and its behaviour depends on the relative strength of each arm — which is "
      + "cell-type dependent. Detected automatically from the curated interactions, so this list cannot "
      + "disagree with the arrows it is built from.</p>";
    M.loops.forEach(function (lp) {
      h += '<div class="pw-loop"><button class="pw-ev" data-loop="' + esc(lp.id) + '" type="button">'
        + '<span class="pw-ev-t">' + esc(lp.name) + '</span><span class="pw-ev-m">'
        + esc(lp.sign) + " feedback · " + lp.length + " steps</span></button>"
        + (lp.why ? '<p style="font-size:12px;line-height:1.55;margin:6px 0 0;">' + esc(lp.why) + "</p>" : "")
        + "</div>";
    });
    h += '<div class="pw-bound"><b>Sign is a parity, not a strength.</b> '
      + esc((M.loops[0] || {}).sign_caveat || "") + "</div>";
    if (M.open_localisations && M.open_localisations.length) {
      h += '<div class="k">Where mTOR signals — what this map does and does not represent</div>';
      M.open_localisations.forEach(function (o) {
        h += '<div class="pw-ctxnote"><b>' + esc(o.name) + "</b> — <i>" + esc(o.status)
          + "</i><br>" + esc(o.why) + "</div>";
      });
    }
    if (M.open_loops && M.open_loops.length) {
      h += '<div class="k">Loops the literature describes that this map cannot close</div>';
      M.open_loops.forEach(function (o) {
        h += '<div class="pw-ctxnote"><b>' + esc(o.name) + "</b><br>Missing step: <i>" + esc(o.missing_step)
          + "</i><br>" + esc(o.why) + "</div>";
      });
    }
    setInsp(h, true);
  }

  function inspectEdge(id) {
    var e = edgeById(id); if (!e) return;
    S.sel = id; S.selKind = "edge";
    var A = nodeById(e.source), B = nodeById(e.target);
    var h = '<h4>' + esc(A.label) + " <span style=\"color:var(--ink-soft)\">" + esc(VERB[e.type] || e.type)
      + "</span> " + esc(B.label) + "</h4>"
      + '<div class="pw-verb">' + esc(e.type) + " · net effect " + esc(e.effect) + "</div>"
      + '<div class="pw-chips">'
      + '<span class="pw-chip"><b>where</b> ' + esc(M.compIx[e.compartment].name) + "</span>"
      + '<span class="pw-chip"><b>when</b> ' + esc(e.timescale) + "</span>"
      + '<span class="pw-chip' + (e.directness !== "direct" ? " warn" : "") + '"><b>link</b> '
      + esc(e.directness) + "</span>"
      + '<span class="pw-chip"><b>model</b> ' + esc(e.species.join(", ") || "—") + "</span>"
      + (e.confidence.consensus === "contested" ? '<span class="pw-chip bad">contested</span>' : "")
      + "</div>"
      + '<div class="k">Mechanism</div><p>' + esc(e.mechanism) + "</p>"
      + (e.teaching_note ? '<div class="pw-teach"><b>Why this distinction matters.</b> ' + esc(e.teaching_note) + "</div>" : "")
      + (e.directness === "indirect"
          ? '<div class="pw-bound"><b>Compressed.</b> This arrow spans more than one molecular event. '
            + "It is drawn as one line for readability, not because it is one step.</div>" : "")
      + (e.boundary ? '<div class="pw-bound"><b>Boundary conditions.</b> ' + esc(e.boundary) + "</div>" : "")
      /* Reviewer point 1, at edge level: context-dependence stated where the
         claim is made, not only in the global banner. */
      + (e.context_note ? '<div class="pw-ctxnote"><b>Context dependence.</b> ' + esc(e.context_note) + "</div>" : "")
      + loopBlock(e)
      + confBlock(e)
      + studyRows(e.evidence.supporting, "Supporting evidence")
      + studyRows(e.evidence.conflicting, "Conflicting evidence")
      + '<div class="k">Curation</div><p style="font-size:11.5px;color:var(--ink-soft)">'
      + esc(e.id) + " · reviewed " + esc(e.review.reviewed) + " by " + esc(e.review.reviewer) + "</p>";
    setInsp(h);
  }

  function inspectNode(id) {
    var n = nodeById(id); if (!n) return;
    S.sel = id; S.selKind = "node";
    var ins = [], outs = [];
    M.interactions.forEach(function (e) {
      if (e.target === id) ins.push(e);
      if (e.source === id) outs.push(e);
    });
    function list(arr, dir) {
      if (!arr.length) return '<p class="pw-empty">none in this model</p>';
      return arr.map(function (e) {
        var other = dir === "in" ? nodeById(e.source) : nodeById(e.target);
        return '<button class="pw-ev" data-eid="' + esc(e.id) + '" type="button">'
          + '<span class="pw-ev-t">' + (dir === "in" ? esc(other.label) + " → " : "→ " + esc(other.label))
          + "</span><span class=\"pw-ev-m\">" + esc(e.type) + " · " + esc(e.effect) + " · "
          + esc(e.confidence.mechanistic) + " mech · " + tierDot(e.evidence.best_tier) + "</span></button>";
      }).join("");
    }
    var c = M.compIx[n.compartment];
    var ne = n.evidence || {};
    /* Reviewer point 2: every node looked equally important. It is not. This
       is derived from the citations on the interactions touching the node, so
       it cannot drift from the edge data — and it is explicitly a count
       WITHIN THIS CORPUS, which is a different claim from a literature count. */
    var evBlock = '<div class="k">How well supported is this molecule?</div>'
      + '<div class="pw-nodeev">'
      + '<span class="pw-stat"><b>' + (ne.studies_in_corpus || 0) + "</b>studies in this corpus</span>"
      + '<span class="pw-stat"><b>' + (ne.first_cited_year || "—") + "</b>earliest paper cited here</span>"
      + '<span class="pw-stat"><b>' + ((ne.interactions_in || 0) + (ne.interactions_out || 0))
      + "</b>curated interactions</span>"
      + '<span class="pw-stat"><b>' + (ne.distinct_mechanisms || []).length + "</b>distinct mechanisms</span>"
      + "</div>"
      + '<div class="pw-confrow" style="margin-top:8px"><span>Strongest study</span><span>'
      + tierPhrase(ne.best_tier) + "</span></div>"
      + '<p class="pw-tinynote">' + esc(ne.caveat || "") + "</p>";
    /* Reviewer point 7: the same molecule does different things in different
       contexts, and this map only shows some of them. */
    var roleBlock = "";
    if (n.context_roles && n.context_roles.length) {
      roleBlock = '<div class="k">Context-dependent roles</div>'
        + n.context_roles.map(function (r) {
            return '<div class="pw-role"><span class="pw-rolelab">' + esc(r[0]) + "</span>"
              + "<span>" + esc(r[1]) + "</span></div>";
          }).join("");
    }
    setInsp('<h4>' + esc(n.label) + "</h4>"
      + '<div class="pw-verb">' + esc(n.cls) + " · " + esc(c.name) + "</div>"
      + "<p>" + esc(n.explain[S.level]) + "</p>"
      + evBlock
      + roleBlock
      + (!c.physical ? '<div class="pw-bound">' + esc(c.blurb) + "</div>"
                     : '<div class="k">Compartment</div><p style="font-size:12px;color:var(--ink-soft)">' + esc(c.blurb) + "</p>")
      /* Declared simplifications are shown, not buried. If a band compresses
         real cell biology, the reader is told so on every node in it. */
      + (c.headline ? '<div class="pw-teach"><b>Why this compartment matters.</b> ' + esc(c.headline) + "</div>" : "")
      + (c.interaction_count ? '<p class="pw-tinynote">' + c.interaction_count + " of "
          + M.meta.counts.interactions + " curated interactions (" + c.interaction_share
          + "%) happen here.</p>" : "")
      + (c.sensing_note ? '<div class="pw-bound"><b>Declared simplification.</b> ' + esc(c.sensing_note) + "</div>" : "")
      + '<div class="k">Inputs (' + ins.length + ")</div>" + list(ins, "in")
      + '<div class="k">Outputs (' + outs.length + ")</div>" + list(outs, "out")
      + '<div class="pw-nav"><button class="pw-btn" data-focus="' + esc(id) + '">Focus here</button>'
      + '<button class="pw-btn" data-entity="' + esc(id) + '">Open entity page</button></div>');
  }

  function inspectDefault() {
    S.sel = null; S.selKind = null;
    var n = M.meta.counts;
    setInsp('<h4>' + n.interactions + " curated steps · " + n.nodes + " molecules</h4>"
      + '<p class="pw-empty">Click any molecule or any arrow. The panel will tell you what kind of event it is, '
      + "where in the cell it happens, how fast, how certain we are, and which papers say so.</p>"
      + '<div class="k">How to read the diagram</div>'
      + '<p class="pw-empty">Bands are real cellular compartments, top to bottom. Two of them — Inputs and '
      + "Biological outcomes — are marked <em>not a cellular location</em>, because they are not.</p>"
      /* Say what is being withheld, and why. A subset the reader does not know
         about is a subset the reader will mistake for the whole pathway. */
      + '<div class="k">You are seeing the Mechanism view</div>'
      + '<p class="pw-empty">' + M.interactions.filter(isMechanism).length + " of the " + n.interactions
      + " curated steps: the ones that are single molecular events — binding, phosphorylation, GAP "
      + "activity, recruitment, transport. The other "
      + M.interactions.filter(function (e) { return !isMechanism(e); }).length
      + " are compressed multi-step links, contested claims or organism-level outcomes — all real, "
      + "all cited, all one click away under <b>VIEW → Pathway</b>. Nothing is withheld without saying so.</p>"
      + '<div class="k">The one thing to notice</div>'
      + '<p class="pw-empty">Nearly every arrow into mTORC1 lands on the lysosomal band. mTORC1 is only switched on '
      + "there. Nutrient sensing is not chemistry happening in free solution — it is a set of mechanisms for getting "
      + "one kinase onto one membrane.</p>", true);
  }

  function setInsp(html, isDefault) {
    el.insp.innerHTML = '<div class="pw-sheet-grip"></div>'
      + (isDefault ? "" : '<button class="pw-sheet-x" aria-label="Close details">×</button>') + html;
    if (!isDefault && window.matchMedia("(max-width:900px)").matches) el.insp.classList.add("open");
    if (isDefault) el.insp.classList.remove("open");
    el.insp.scrollTop = 0;
    var x = el.insp.querySelector(".pw-sheet-x");
    if (x) x.addEventListener("click", function () { el.insp.classList.remove("open"); inspectDefault(); paint(); });
    el.insp.querySelectorAll("[data-sid]").forEach(function (b) {
      b.addEventListener("click", function () {
        var st = (typeof studyBySid === "function") ? studyBySid(b.dataset.sid) : null;
        if (st && typeof filterStudiesByTitle === "function") filterStudiesByTitle(st.title);
      });
    });
    el.insp.querySelectorAll("[data-eid]").forEach(function (b) {
      b.addEventListener("click", function () { inspectEdge(b.dataset.eid); frameEdge(b.dataset.eid); paint(); });
    });
    el.insp.querySelectorAll("[data-loop]").forEach(function (b) {
      b.addEventListener("click", function () {
        var lp = M.loopIx[b.dataset.loop]; if (!lp) return;
        S.loopsOnly = true; S.view = "pathway";
        el.explorerUI.querySelectorAll("#pwView button").forEach(function (o) {
          o.setAttribute("aria-pressed", String(o.dataset.vw === "pathway"));
        });
        $("pwLoops").setAttribute("aria-pressed", "true");
        S.highlightLoop = lp.id;
        paint(); updateHint();
        // frame the whole loop
        var xs = [], ys = [];
        lp.nodes.forEach(function (nm) { var nd = nodeById(nm); if (nd) { xs.push(nd.x); ys.push(nd.y); } });
        if (xs.length) frameBox(Math.min.apply(null, xs) - 80, Math.min.apply(null, ys) - 60,
          Math.max.apply(null, xs) - Math.min.apply(null, xs) + 160,
          Math.max.apply(null, ys) - Math.min.apply(null, ys) + 120, 80);
        say("Highlighting " + lp.name + ", a " + lp.sign + " feedback loop of " + lp.length + " steps.");
      });
    });
    el.insp.querySelectorAll("[data-focus]").forEach(function (b) {
      b.addEventListener("click", function () {
        S.focus = S.focus === b.dataset.focus ? null : b.dataset.focus;
        el.focusBtn.setAttribute("aria-pressed", S.focus ? "true" : "false");
        if (S.focus) frameNode(S.focus); else fitAll();
        paint();
      });
    });
    el.insp.querySelectorAll("[data-entity]").forEach(function (b) {
      b.addEventListener("click", function () {
        var name = b.dataset.entity;
        if (typeof entityByName === "function" && entityByName(name) && typeof selectEntity === "function") {
          if (typeof showView === "function") showView("map");
          selectEntity(name);
          window.scrollTo({ top: 0, behavior: "smooth" });
        } else { say("No dedicated entity page for " + name + " yet."); }
      });
    });
  }

  /* ==== 3. GUIDED ROUTES =============================================== */
  /* Steps are hand-authored where authored; otherwise assembled from
     curated fields. The assembled version is explicit about being a
     derivation, and never claims more than the model records. */
  function stepFor(route, i) {
    var authored = (route.steps || []).find(function (s, k) { return k === i; });
    var eid = authored ? authored.interaction : route.spine[i];
    var e = edgeById(eid);
    if (!e) return null;
    var A = nodeById(e.source), B = nodeById(e.target), c = M.compIx[e.compartment];
    var nextE = edgeById(authored ? null : route.spine[i + 1]);
    var base = {
      interaction: eid,
      what: A.label + " " + (VERB[e.type] || e.type) + " " + B.label + ".",
      why: e.mechanism,
      changed: "The net effect on " + B.label + " is: " + e.effect
        + ". " + (e.type === "recruitment" || e.type === "localisation"
          ? "Note that this changes where " + B.label + " is, not whether it is switched on."
          : e.type === "phosphorylation"
            ? "A phosphate is added — which here " + (e.effect === "inhibits" ? "shuts down" : "switches on")
              + " " + B.label + "'s function."
            : ""),
      consequence: nextE
        ? "Because " + B.label + " changed, the next event becomes possible: "
          + nodeById(nextE.source).label + " → " + nodeById(nextE.target).label + "."
        : (B.explain[S.level] || ""),
      certainty: "Mechanistic confidence " + e.confidence.mechanistic + "; human relevance "
        + e.confidence.human_relevance + "; field consensus " + e.confidence.consensus
        + ". Best supporting study is tier " + e.evidence.best_tier + " (" + e.evidence.kind
        + ", " + (e.species.join(", ") || "model not stated") + ")."
        + (e.boundary ? " Boundary conditions: " + e.boundary : ""),
      matters: e.teaching_note || B.explain.research
    };
    if (authored) {
      Object.keys(authored).forEach(function (k) { if (authored[k]) base[k] = authored[k]; });
    }
    base._e = e; base._where = c.name; base._authored = !!authored;
    return base;
  }

  function renderGuided() {
    var r = M.routeIx[S.routeId] || M.routes[0];
    S.routeId = r.id;
    var total = (r.steps && r.steps.length) ? r.steps.length : r.spine.length;
    el.routes.innerHTML = M.routes.map(function (x) {
      var n = (x.steps && x.steps.length) ? x.steps.length : x.spine.length;
      return '<button class="pw-routebtn" data-r="' + esc(x.id) + '" aria-pressed="'
        + (x.id === r.id) + '">' + esc(x.name) + "<small>" + n + " STEPS · "
        + x.interactions.length + " CURATED LINKS</small></button>";
    }).join("");
    el.routes.querySelectorAll("[data-r]").forEach(function (b) {
      b.addEventListener("click", function () { S.routeId = b.dataset.r; S.step = -1; renderGuided(); });
    });

    if (S.step < 0) {
      el.prog.innerHTML = "";
      el.step.innerHTML = '<div class="pw-step-hd"><h4>' + esc(r.name) + '</h4>'
        + '<span class="pw-step-n">' + total + " steps</span></div>"
        + "<p>" + r.story + "</p>"
        + '<div class="pw-nav"><button class="pw-btn" id="pwStart">Start the walkthrough →</button>'
        + '<span class="pw-where">' + r.interactions.length + " curated links · every step cites its papers</span></div>";
      $("pwStart").addEventListener("click", function () { S.step = 0; renderGuided(); });
      fitAll(); paint();
      return;
    }

    var st = stepFor(r, S.step);
    if (!st) { S.step = -1; return renderGuided(); }
    el.prog.innerHTML = Array.apply(null, { length: total }).map(function (_, k) {
      return '<i class="' + (k < S.step ? "done" : k === S.step ? "now" : "") + '"></i>';
    }).join("");
    el.step.innerHTML = '<div class="pw-step-hd">'
      + "<h4>" + esc(st.what) + "</h4>"
      + '<span class="pw-step-n">Step ' + (S.step + 1) + " / " + total + " · " + esc(st._where) + "</span></div>"
      + '<dl class="pw-q"><dt>Why does it happen?</dt><dd>' + esc(st.why) + "</dd></dl>"
      + '<dl class="pw-q"><dt>What changed?</dt><dd>' + esc(st.changed) + "</dd></dl>"
      + '<dl class="pw-q"><dt>What follows from it?</dt><dd>' + esc(st.consequence) + "</dd></dl>"
      + '<dl class="pw-q"><dt>How certain are we?</dt><dd>' + esc(st.certainty) + "</dd></dl>"
      + '<dl class="pw-q"><dt>Why do scientists care?</dt><dd>' + esc(st.matters) + "</dd></dl>"
      + '<div class="pw-nav">'
      + '<button class="pw-btn" id="pwPrev"' + (S.step === 0 ? " disabled" : "") + ">← Back</button>"
      + '<button class="pw-btn" id="pwNext">' + (S.step === total - 1 ? "Finish" : "Next →") + "</button>"
      + '<button class="pw-btn" id="pwEvid">Evidence for this step</button>'
      + '<span class="pw-where">' + (st._authored ? "hand-authored" : "assembled from curated fields") + "</span></div>";

    $("pwPrev").addEventListener("click", function () { if (S.step > 0) { S.step--; renderGuided(); } });
    $("pwNext").addEventListener("click", function () {
      if (S.step < total - 1) { S.step++; renderGuided(); } else { S.step = -1; renderGuided(); }
    });
    $("pwEvid").addEventListener("click", function () { inspectEdge(st.interaction); });

    S.sel = st.interaction; S.selKind = "edge";
    paint();
    var p = $("pwe-" + st.interaction);
    if (p && !reduced()) { p.classList.add("flow"); setTimeout(function () { p.classList.remove("flow"); }, 2600); }
    var src = el.svg.querySelector('.pw-n[data-nid="' + CSS.escape(st._e.source) + '"]');
    var tgt = el.svg.querySelector('.pw-n[data-nid="' + CSS.escape(st._e.target) + '"]');
    [src, tgt].forEach(function (g) {
      if (!g) return; g.classList.add("pulse"); setTimeout(function () { g.classList.remove("pulse"); }, 3000);
    });
    frameEdge(st.interaction);
    say("Step " + (S.step + 1) + " of " + total + ", in the " + st._where + ". " + st.what);
  }

  /* ==== 4. SCENARIOS (Phase 2) ========================================= */
  function renderScenarios() {
    el.scen.innerHTML = '<div class="pw-step"><div class="pw-step-hd"><h4>Scenario Laboratory</h4>'
      /* NOT .pw-step-n. That class belongs to guided-route step badges, and
         reusing it here meant a global querySelector(".pw-step-n") found the
         Scenario Lab badge instead of the live route step, because #pwScen
         sits earlier in the DOM. Cost me a false negative in live testing and
         a vacuous pass in the smoke test. Shared card styling is fine;
         shared identity is not. */
      + '<span class="pw-badge">Phase 2 — in build</span></div>'
      + "<p>The Scenario Laboratory will let you switch on conditions — fed, starved, exercised, hypoxic, "
      + "PTEN-null, PIK3CA-mutant, TSC1/2-null, high or low leucine, acute or chronic rapamycin, Torin, "
      + "metformin — and watch the network change qualitatively.</p>"
      + '<div class="pw-bound"><b>Why it is not shipped yet, deliberately.</b> A sandbox that propagates '
      + "signals through this graph will produce a confident answer for every condition you give it, including "
      + "the conditions where the real biology is governed by feedback loops the graph compresses into single "
      + "arrows. Shipping that before it is constrained would make the Atlas less accurate while making it look "
      + "more impressive. The engine is being built against hand-curated, cited expected outcomes for each "
      + "scenario: if the propagation does not reproduce the literature, the build fails and nothing deploys.</p>"
      + '<div class="k">What it will never do</div>'
      + '<p class="pw-empty">It will not output numbers. There will be no predicted fold-changes, no simulated '
      + "western blots and no dose-response curves, because this graph cannot legitimately produce any of those. "
      + "Direction and confidence only, always labelled as educational modelling rather than validated simulation.</p>"
      + '<div class="pw-nav"><button class="pw-btn" data-go="guided">Follow a guided route instead →</button></div></div>';
    el.scen.querySelectorAll("[data-go]").forEach(function (b) {
      b.addEventListener("click", function () { setMode(b.dataset.go); });
    });
  }

  /* ==== mode switching ================================================= */
  function setMode(m) {
    S.mode = m;
    ["overview", "explorer", "guided", "scenarios"].forEach(function (k) {
      var b = $("pwMode-" + k);
      if (b) b.setAttribute("aria-selected", String(k === m));
    });
    el.ov.classList.toggle("pw-hide", m !== "overview");
    el.scen.classList.toggle("pw-hide", m !== "scenarios");
    el.explorerUI.classList.toggle("pw-hide", m !== "explorer");
    el.guidedUI.classList.toggle("pw-hide", m !== "guided");
    el.stageWrap.classList.toggle("pw-hide", m !== "explorer" && m !== "guided");
    if (m === "explorer") { S.routeId = null; S.step = -1; inspectDefault(); updateHint(); frameCore(); paint(); }
    if (m === "guided") { if (!S.routeId) S.routeId = M.routes[0].id; S.step = -1; renderGuided(); }
    if (m === "scenarios") renderScenarios();
    say("Switched to " + m);
  }

  /* ==== shell ========================================================== */
  function shell() {
    return ''
      + '<div class="pw" id="pwRoot">'
      + '<div class="pw-sr" id="pwSR" role="status" aria-live="polite"></div>'
      + '<div class="pw-modes" role="tablist" aria-label="Pathway views">'
      + '  <button class="pw-mode" id="pwMode-overview" role="tab" aria-selected="true">Overview</button>'
      + '  <button class="pw-mode" id="pwMode-explorer" role="tab" aria-selected="false">Mechanism Explorer</button>'
      + '  <button class="pw-mode" id="pwMode-guided" role="tab" aria-selected="false">Guided Routes</button>'
      + '  <button class="pw-mode" id="pwMode-scenarios" role="tab" aria-selected="false">Scenario Lab</button>'
      + "</div>"
      /* Reviewer point 1: the map read as a set of verified facts. It is a
         consensus model whose arrows carry different weight in different
         tissues. That is not a footnote — it is a standing condition on
         everything below it, so it is always visible, above the panels. */
      + '<div class="pw-caveat" role="note"><b>This is the current consensus model, not a list of '
      + 'verified facts.</b> Many interactions are context-dependent: their weight differs across cell '
      + 'types, species, nutrient state, stress, stimulus duration and dose. An arrow that dominates in '
      + 'one tissue can be negligible in another. Click any arrow for its boundary conditions, its '
      + 'evidence, and how certain we actually are.</div>'
      + '<div class="pw-panelwrap">'
      + '  <div id="pwOverview"></div>'
      + '  <div id="pwScen" class="pw-hide"></div>'
      + '  <div id="pwExplorerUI" class="pw-hide">'
      + '    <div class="pw-bar">'
      + '      <label class="pw-search"><span class="pw-lbl">FIND</span>'
      + '        <input id="pwFind" type="search" placeholder="protein, complex, drug…" aria-label="Find a molecule"></label>'
      + '      <span class="pw-lbl">LEVEL</span><div class="pw-seg" id="pwLevel" role="group" aria-label="Explanation level">'
      + '        <button data-lv="beginner">Beginner</button><button data-lv="student" aria-pressed="true">Student</button>'
      + '        <button data-lv="research">Research</button></div>'
      + '      <span class="pw-lbl">VIEW</span><div class="pw-seg" id="pwView" role="group" aria-label="Level of abstraction">'
      + '        <button data-vw="mechanism" aria-pressed="true" title="Molecular events only: binding, phosphorylation, GAP activity, recruitment, transport">Mechanism</button>'
      + '        <button data-vw="pathway" title="Who talks to whom, including compressed multi-step links and organism-level outcomes">Pathway</button></div>'
      + '      <span class="pw-lbl">BY TIME</span><div class="pw-seg" id="pwTime" role="group" aria-label="Cumulative timescale window">'
      + '        <button data-tm="seconds" title="Events that happen within seconds">s</button>'
      + '        <button data-tm="minutes" title="Cumulative: up to minutes">min</button>'
      + '        <button data-tm="hours" title="Cumulative: up to hours">hr</button>'
      + '        <button data-tm="chronic" title="Cumulative: up to chronic timescales">chronic</button>'
      + '        <button data-tm="all" aria-pressed="true" title="No time filter">all</button></div>'
      + '      <span class="pw-lbl">SHOW</span><div class="pw-seg" id="pwEffect" role="group" aria-label="Filter by effect">'
      + '        <button data-ef="" aria-pressed="true">All</button><button data-ef="activates">Activating</button>'
      + '        <button data-ef="inhibits">Inhibiting</button></div>'
      + '      <div class="pw-seg" id="pwEvid2" role="group" aria-label="Filter by evidence">'
      + '        <button data-ev="" aria-pressed="true">Any evidence</button><button data-ev="core">Well understood</button>'
      + '        <button data-ev="direct">Direct only</button>'
      + '        <button data-ev="human">Human-relevant</button><button data-ev="contested">Contested</button></div>'
      + '      <button class="pw-btn" id="pwLoops" aria-pressed="false" title="Show only interactions that form a feedback loop">Feedback loops</button>'
      + '      <button class="pw-btn" id="pwFocus" aria-pressed="false">Focus mode</button>'
      + '      <button class="pw-btn" id="pwReset">Reset view</button>'
      + "    </div></div>"
      + '  <div id="pwGuidedUI" class="pw-hide"><div class="pw-routes" id="pwRoutes"></div>'
      + '    <div class="pw-prog" id="pwProg"></div><div class="pw-step" id="pwStep"></div></div>'
      + '  <div class="pw-stage pw-hide" id="pwStageWrap">'
      + '    <div class="pw-canvas" id="pwCanvas">'
      + '      <div class="pw-zoom"><button id="pwIn" aria-label="Zoom in">+</button>'
      + '        <button id="pwOut" aria-label="Zoom out">−</button><button id="pwFit" aria-label="Fit to view">⤢</button></div>'
      + '      <div class="pw-hint" id="pwHintBox">Drag to pan · scroll to zoom · click any arrow</div></div>'
      + '    <div class="pw-insp" id="pwInsp" aria-live="polite"></div>'
      + "  </div>"
      + '  <details class="pw-legend"><summary>Visual language — what every line and box means</summary>'
      + '    <div class="pw-legend-grid">' + legend() + "</div></details>"
      + "</div></div>";
  }

  function legend() {
    /* Reviewer point 6 said phosphorylates/translocates were missing. They were
       not — but the legend only listed EFFECTS, so the mechanistic types were
       invisible unless you zoomed in far enough to see the mid-line tags. That
       is a legend bug, not a data gap. The two axes are now labelled as two
       axes, and every type in the model is listed with its tag. */
    function line(cls, mark, txt) {
      return '<div><svg width="46" height="14"><path class="pw-e ' + cls
        + '" d="M2,7 H34" marker-end="url(#' + mark + ')"/></svg>' + txt + "</div>";
    }
    var effects = ""
      + line("f-activates m-high d-direct", "pwArrowA", "<b>Activates</b> — arrowhead")
      + line("f-inhibits m-high d-direct", "pwBar", "<b>Inhibits</b> — bar, never colour alone")
      + line("f-required-for m-medium d-direct", "pwChev", "<b>Required for / recruits</b> — enables, does not switch on")
      + line("f-binds m-medium d-direct", "pwDot", "<b>Binds</b> — physical, no directional claim");
    var certainty = ""
      + line("f-activates m-high d-direct", "pwArrowA", "<b>Solid, thick</b> — direct, high mechanistic confidence")
      + line("f-activates m-medium d-indirect", "pwArrowA", "<b>Long dash</b> — indirect: more than one molecular step")
      + line("f-activates m-low d-unresolved", "pwArrowA", "<b>Dotted, thin</b> — unresolved mechanism, low confidence")
      + '<div><svg width="46" height="16"><path d="M2,8 H34" stroke="var(--amber)" stroke-width="6" opacity=".25"/>'
      + '<path d="M2,8 H34" stroke="var(--danger)" stroke-width="2"/></svg><b>Amber halo</b> — the field disagrees</div>';
    var types = Object.keys(TYPE_TAG).map(function (t) {
      var used = M.interactions.filter(function (e) { return e.type === t; }).length;
      if (!used) return "";
      return '<div><span class="pw-legtag">' + esc(TYPE_TAG[t]) + "</span>"
        + "<span><b>" + esc(t) + "</b> — " + esc(VERB[t] || t) + " <i>(" + used + ")</i></span></div>";
    }).join("");
    var shapes = ""
      + '<div><svg width="46" height="16"><rect x="2" y="3" width="30" height="11" fill="var(--paper)" stroke="var(--line-strong)"/></svg>Protein</div>'
      + '<div><svg width="46" height="16"><rect x="2" y="2" width="32" height="13" fill="var(--paper)" stroke="var(--line-strong)" stroke-width="1.8"/><rect x="5" y="5" width="26" height="7" fill="none" stroke="var(--line-strong)"/></svg><b>Complex</b> — double border</div>'
      + '<div><svg width="46" height="16"><rect x="2" y="3" width="30" height="11" fill="none" stroke="var(--line-strong)" stroke-dasharray="5 3"/></svg>Process</div>'
      + '<div><svg width="46" height="16"><rect x="2" y="3" width="30" height="11" fill="none" stroke="var(--line-strong)" stroke-dasharray="3 3"/></svg><i>Outcome / disease</i> — not a molecule</div>'
      + '<div><svg width="46" height="16"><rect x="2" y="2" width="30" height="13" fill="none" stroke="var(--ink)" stroke-width="2.6"/></svg><b>Thick border</b> — more curated evidence behind that molecule</div>';
    return '<div class="pw-legsec"><h5>Net effect <span>colour + line terminus</span></h5>'
      + '<div class="pw-legend-grid">' + effects + "</div></div>"
      + '<div class="pw-legsec"><h5>How certain <span>line style + weight</span></h5>'
      + '<div class="pw-legend-grid">' + certainty + "</div></div>"
      + '<div class="pw-legsec"><h5>Mechanistic type <span>the tag on the line — zoom in to see it</span>'
      + "</h5><p class=\"pw-tinynote\">Effect and mechanism are different claims. "
      + "<em>Phosphorylates</em> is a mechanism; <em>inhibits</em> is its consequence — and phosphorylation "
      + "can just as easily activate. Both are recorded separately for every interaction.</p>"
      + '<div class="pw-legend-grid pw-legtypes">' + types + "</div></div>"
      + '<div class="pw-legsec"><h5>What the boxes mean</h5>'
      + '<div class="pw-legend-grid">' + shapes + "</div></div>";
  }


  /* ==== interaction wiring ============================================= */
  function wire() {
    // canvas events
    var drag = null, lastWasPan = false, lastDown = null;
    /* 6px was too tight: ordinary trackpad clicks drift, and a drifted click
       was silently swallowed. 10px still distinguishes a pan clearly, and
       selection now lives on `click` anyway, so this only gates panning. */
    var PAN_PX = 10;
    el.canvas.addEventListener("pointerdown", function (ev) {
      if (ev.target.closest(".pw-zoom")) return;
      /* Record WHAT WAS PRESSED here, at pointerdown, because this is the last
         moment ev.target is the SVG shape. setPointerCapture below retargets
         every later pointer event — including pointerup — to the capturing
         element, so at pointerup ev.target is the canvas <div> and any
         closest("[data-eid]") lookup returns null. That is what made clicking
         a molecule or an arrow do nothing. */
      var t0 = ev.target, ge = t0.closest ? t0.closest("[data-eid]") : null;
      var gn = t0.closest ? t0.closest(".pw-n") : null;
      drag = { x: ev.clientX, y: ev.clientY, cx: S.cam.x, cy: S.cam.y, moved: 0,
               eid: ge ? ge.dataset.eid : null, nid: gn ? gn.dataset.nid : null };
      el.canvas.classList.add("grabbing");
      /* Guarded: setPointerCapture throws NotFoundError if the pointer id is
         no longer active — reachable with rapid multi-touch, and it surfaced
         as a live console exception. Capture is a nicety (it keeps the drag
         alive outside the element); pan works without it, so never let it
         break the gesture. */
      try { el.canvas.setPointerCapture(ev.pointerId); } catch (_) {}
    });
    el.canvas.addEventListener("pointermove", function (ev) {
      if (!drag) return;
      var r = el.canvas.getBoundingClientRect();
      var dx = (ev.clientX - drag.x) / r.width * S.cam.w, dy = (ev.clientY - drag.y) / r.height * S.cam.h;
      drag.moved = Math.max(drag.moved, Math.abs(ev.clientX - drag.x) + Math.abs(ev.clientY - drag.y));
      S.cam.x = drag.cx - dx; S.cam.y = drag.cy - dy; applyCam();
    });
    el.canvas.addEventListener("pointerup", function (ev) {
      var d = drag;
      drag = null;
      el.canvas.classList.remove("grabbing");
      try { el.canvas.releasePointerCapture(ev.pointerId); } catch (_) {}
      /* Selection is NOT done here — see the click handler below. This handler
         only decides whether the gesture was a pan, and records it so the
         click that follows can be ignored. */
      lastWasPan = !!(d && d.moved > PAN_PX);
      lastDown = d || null;
    });

    /* Selection runs on `click`, deliberately.
       An earlier version selected on `pointerup` and read ev.target there.
       That is fragile for three independent reasons: pointer capture can
       retarget the event to the capturing element; a few pixels of pointer
       drift during an ordinary click could trip the pan threshold and
       suppress selection entirely; and pointerup carries no notion of
       "the user activated this thing".
       `click` is that notion. The browser only fires it for a genuine
       activation, gives the correct target, is unaffected by capture, and is
       also what assistive technology and keyboard activation produce. The
       pointer handlers keep doing what only they can do: panning. */
    el.canvas.addEventListener("click", function (ev) {
      if (ev.target.closest && ev.target.closest(".pw-zoom")) return;
      if (lastWasPan) { lastWasPan = false; return; }
      var t = ev.target, eid = null, nid = null;
      var ge = t.closest ? t.closest("[data-eid]") : null;
      var gn = t.closest ? t.closest(".pw-n") : null;
      if (ge) eid = ge.dataset.eid; else if (gn) nid = gn.dataset.nid;
      // fall back to what was pressed, then to a hit-test of the click point
      if (!eid && !nid && lastDown) { eid = lastDown.eid; nid = lastDown.nid; }
      if (!eid && !nid && ev.clientX != null) {
        var u = document.elementFromPoint(ev.clientX, ev.clientY);
        if (u && u.closest) {
          var ue = u.closest("[data-eid]"), un = u.closest(".pw-n");
          if (ue) eid = ue.dataset.eid; else if (un) nid = un.dataset.nid;
        }
      }
      if (eid) { inspectEdge(eid); paint(); }
      else if (nid) { inspectNode(nid); paint(); }
    });
    el.canvas.addEventListener("wheel", function (ev) {
      ev.preventDefault();
      zoomAt(ev.clientX, ev.clientY, ev.deltaY > 0 ? 1.14 : 1 / 1.14);
      paint();
    }, { passive: false });
    // pinch
    var pts = {};
    el.canvas.addEventListener("pointerdown", function (e) { pts[e.pointerId] = e; });
    el.canvas.addEventListener("pointerup", function (e) { delete pts[e.pointerId]; });
    el.canvas.addEventListener("pointermove", function (e) {
      if (!pts[e.pointerId]) return;
      pts[e.pointerId] = e;
      var ids = Object.keys(pts);
      if (ids.length !== 2) return;
      var a = pts[ids[0]], b = pts[ids[1]];
      var d = Math.hypot(a.clientX - b.clientX, a.clientY - b.clientY);
      if (el.canvas._pd) {
        zoomAt((a.clientX + b.clientX) / 2, (a.clientY + b.clientY) / 2, el.canvas._pd / d);
      }
      el.canvas._pd = d;
    });
    el.canvas.addEventListener("pointercancel", function () { el.canvas._pd = null; });

    $("pwIn").addEventListener("click", function () { var r = el.canvas.getBoundingClientRect(); zoomAt(r.left + r.width / 2, r.top + r.height / 2, 1 / 1.35); paint(); });
    $("pwOut").addEventListener("click", function () { var r = el.canvas.getBoundingClientRect(); zoomAt(r.left + r.width / 2, r.top + r.height / 2, 1.35); paint(); });
    $("pwFit").addEventListener("click", function () { fitAll(); paint(); });
    $("pwReset").addEventListener("click", function () {
      S.focus = null; S.filters = { effect: null, evidence: null, physOnly: false };
      S.view = "mechanism"; S.timeMax = "all"; S.loopsOnly = false; S.highlightLoop = null;
      el.explorerUI.querySelectorAll("#pwView button").forEach(function (b) {
        b.setAttribute("aria-pressed", String(b.dataset.vw === "mechanism"));
      });
      el.explorerUI.querySelectorAll("#pwTime button").forEach(function (b) {
        b.setAttribute("aria-pressed", String(b.dataset.tm === "all"));
      });
      $("pwLoops").setAttribute("aria-pressed", "false");
      el.focusBtn.setAttribute("aria-pressed", "false");
      el.explorerUI.querySelectorAll("#pwEffect button,#pwEvid2 button").forEach(function (b) {
        b.setAttribute("aria-pressed", String(!b.dataset.ef && !b.dataset.ev));
      });
      el.find.value = ""; inspectDefault(); updateHint(); frameCore(); paint();
    });
    el.focusBtn.addEventListener("click", function () {
      if (S.focus) { S.focus = null; el.focusBtn.setAttribute("aria-pressed", "false"); fitAll(); }
      else if (S.selKind === "node") { S.focus = S.sel; el.focusBtn.setAttribute("aria-pressed", "true"); frameNode(S.focus); }
      else { say("Select a molecule first, then switch on focus mode."); }
      paint();
    });

    // segmented controls
    function seg(container, attr, apply) {
      container.querySelectorAll("button").forEach(function (b) {
        b.addEventListener("click", function () {
          container.querySelectorAll("button").forEach(function (o) { o.setAttribute("aria-pressed", "false"); });
          b.setAttribute("aria-pressed", "true");
          apply(b.dataset[attr] || null);
        });
      });
    }
    seg($("pwLevel"), "lv", function (v) {
      S.level = v || "student";
      if (S.selKind === "node") inspectNode(S.sel); else if (S.selKind === "edge") inspectEdge(S.sel);
      say("Explanation level: " + S.level + ". The network is unchanged — only the words change.");
    });
    seg($("pwView"), "vw", function (v) {
      S.view = v || "mechanism";
      say(S.view === "mechanism"
        ? "Mechanism view: molecular events only — binding, phosphorylation, GAP activity, recruitment, transport."
        : "Pathway view: who talks to whom, including compressed multi-step links and organism-level outcomes.");
      updateHint(); paint();
    });
    seg($("pwTime"), "tm", function (v) {
      S.timeMax = v || "all";
      say(S.timeMax === "all"
        ? "Time filter off."
        : "Showing everything that has happened by the " + S.timeMax + " timescale, cumulatively. "
          + "Constitutive links are always present.");
      updateHint(); paint();
    });
    $("pwLoops").addEventListener("click", function () {
      S.loopsOnly = !S.loopsOnly; S.highlightLoop = null;
      $("pwLoops").setAttribute("aria-pressed", S.loopsOnly ? "true" : "false");
      if (S.loopsOnly) inspectLoops();
      else inspectDefault();
      say(S.loopsOnly
        ? M.loops.length + " feedback loops highlighted. mTOR is full of them, and a loop behaves "
          + "differently from an arrow: it has a set point."
        : "Feedback highlight off.");
      updateHint(); paint();
    });
    seg($("pwEffect"), "ef", function (v) { S.filters.effect = v; paint(); });
    seg($("pwEvid2"), "ev", function (v) { S.filters.evidence = v; paint(); });

    // search
    el.find.addEventListener("input", function () {
      var q = el.find.value.trim().toLowerCase();
      if (!q) { paint(); return; }
      var hit = M.nodes.filter(function (n) { return n.label.toLowerCase().indexOf(q) >= 0; });
      el.svg.querySelectorAll(".pw-n").forEach(function (g) {
        g.classList.toggle("dim", !hit.some(function (n) { return n.id === g.dataset.nid; }));
      });
      if (hit.length === 1) { frameNode(hit[0].id); inspectNode(hit[0].id); }
      say(hit.length + " molecules match " + q);
    });
    el.find.addEventListener("keydown", function (ev) {
      if (ev.key !== "Enter") return;
      var q = el.find.value.trim().toLowerCase();
      var hit = M.nodes.filter(function (n) { return n.label.toLowerCase().indexOf(q) >= 0; })[0];
      if (hit) { frameNode(hit.id); inspectNode(hit.id); paint(); }
    });

    // keyboard on nodes
    el.canvas.addEventListener("keydown", function (ev) {
      var g = ev.target.closest ? ev.target.closest(".pw-n") : null;
      if (g && (ev.key === "Enter" || ev.key === " ")) {
        ev.preventDefault(); inspectNode(g.dataset.nid); frameNode(g.dataset.nid); paint();
      }
      if (ev.key === "Escape") { S.focus = null; inspectDefault(); fitAll(); paint(); }
      if (ev.key === "+" || ev.key === "=") { var r = el.canvas.getBoundingClientRect(); zoomAt(r.left + r.width / 2, r.top + r.height / 2, 1 / 1.3); }
      if (ev.key === "-") { var r2 = el.canvas.getBoundingClientRect(); zoomAt(r2.left + r2.width / 2, r2.top + r2.height / 2, 1.3); }
      if (ev.key === "0") fitAll();
    });

    // route step keys
    document.addEventListener("keydown", function (ev) {
      if (S.mode !== "guided" || S.step < 0) return;
      if (ev.target.tagName === "INPUT") return;
      if (ev.key === "ArrowRight") { var n = $("pwNext"); if (n) n.click(); }
      if (ev.key === "ArrowLeft") { var p = $("pwPrev"); if (p && !p.disabled) p.click(); }
    });

    // mode tabs
    ["overview", "explorer", "guided", "scenarios"].forEach(function (k) {
      $("pwMode-" + k).addEventListener("click", function () { setMode(k); });
    });

    window.addEventListener("resize", function () {
      if (S.mode === "explorer") { frameCore(); paint(); }
      else if (S.mode === "guided") { fitAll(); paint(); }
    });
  }

  /* ==== boot =========================================================== */
  function index() {
    M.nodeIx = {}; M.edgeIx = {}; M.compIx = {}; M.routeIx = {};
    M.nodes.forEach(function (n) { M.nodeIx[n.id] = n; });
    M.interactions.forEach(function (e) { M.edgeIx[e.id] = e; });
    M.compartments.forEach(function (c) { M.compIx[c.id] = c; });
    M.routes.forEach(function (r) { M.routeIx[r.id] = r; });
    M.loopIx = {};
    (M.loops || []).forEach(function (l) { M.loopIx[l.id] = l; });
  }

  function mount(host) {
    host.innerHTML = shell();
    el.ov = $("pwOverview"); el.scen = $("pwScen");
    el.explorerUI = $("pwExplorerUI"); el.guidedUI = $("pwGuidedUI");
    el.stageWrap = $("pwStageWrap"); el.canvas = $("pwCanvas"); el.insp = $("pwInsp");
    el.routes = $("pwRoutes"); el.prog = $("pwProg"); el.step = $("pwStep");
    el.find = $("pwFind"); el.focusBtn = $("pwFocus"); el.sr = $("pwSR");

    assignLanes();
    el.canvas.insertAdjacentHTML("afterbegin", buildSVG());
    el.svg = el.canvas.querySelector("svg");
    el.svg.__bandlabs = [].slice.call(el.svg.querySelectorAll(".pw-bandg"));
    renderOverview();
    wire();
    updateHint();
    frameCore();
    inspectDefault();
    paint();
    setMode(S.mode);
  }

  var booted = false;
  window.PathwayApp = {
    boot: function (host, modelUrl) {
      if (booted) return Promise.resolve();
      booted = true;
      return fetch(modelUrl, { cache: "no-cache" })
        .then(function (r) { if (!r.ok) throw new Error("HTTP " + r.status); return r.json(); })
        .then(function (json) { M = json; index(); mount(host); return M.meta; })
        .catch(function (err) {
          booted = false;
          host.innerHTML = '<div class="pw"><div class="pw-step"><h4>Pathway model could not be loaded</h4>'
            + '<p class="pw-empty">' + esc(String(err)) + ". The mechanism data lives in pathway/model.json; "
            + "if you are running this from a local file rather than a web server, the browser will block the fetch.</p></div></div>";
          throw err;
        });
    },
    setMode: function (m) { if (M) setMode(m); }
  };
})();
