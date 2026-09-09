(function(){
  var D = PA.boot('pa-data'); if(!D) return;
  var S = PA.state(), CFG = D.cfg, MAP = D.map;
  var fall = document.getElementById('paFallback'); if(fall) fall.hidden = true;
  var snap = 'now', sel = null, snapM = {};

  function esc(s){ return String(s==null?'':s); }
  function lvl(id){
    if(snap === 'now') return PA.mastery(id);
    return snapM[id] || 0;
  }
  /* Sirku i zkraceny popisek spocital build (fit_labels) z toho, kolik ma uzel
     na mape opravdu mista -- tady uz se jen cte, aby staticka a zivá mapa
     kreslily pixel po pixelu totez. */
  function mapLabel(n){ return n.dlab || n.label; }
  function boxW(n){ return n.dw || 78; }

  /* ---------------- map ---------------- */
  function clip(a, b, w, h){
    var dx = b.x-a.x, dy = b.y-a.y, hw = w/2+4, hh = h/2+4;
    if(!dx && !dy) return {x:a.x, y:a.y};
    var sx = dx ? hw/Math.abs(dx) : 1e9, sy = dy ? hh/Math.abs(dy) : 1e9;
    var s = Math.min(sx, sy);
    return {x: a.x + dx*s, y: a.y + dy*s};
  }
  function drawMap(){
    var svg = document.getElementById('paMap'); if(!svg) return;
    var BH = 34, s = '', i, id, n;
    s += '<defs><pattern id="paHatch" width="7" height="7" patternTransform="rotate(45)" ' +
         'patternUnits="userSpaceOnUse"><line x1="0" y1="0" x2="0" y2="7" stroke="currentColor" ' +
         'stroke-width="2.2" opacity=".26"/></pattern></defs>';
    for(i=0;i<MAP.bands.length;i++){
      var b = MAP.bands[i], c = MAP.comps[b.compartment] || {short:'', name:''};
      if(i % 2 === 0) s += '<rect class="pa-band" x="60" y="' + b.y + '" width="1400" height="' + b.h + '"/>';
      s += '<line x1="60" y1="' + b.y + '" x2="1460" y2="' + b.y + '" stroke="var(--line)"/>';
      var cy = b.y + b.h/2;
      s += '<text class="pa-bandlab" x="92" y="' + cy + '" text-anchor="middle" ' +
           'transform="rotate(-90 92 ' + cy + ')">' + esc(c.short) + '</text>';
      s += '<text class="pa-bandsub" x="112" y="' + cy + '" text-anchor="middle" ' +
           'transform="rotate(-90 112 ' + cy + ')">' + esc(c.name) + '</text>';
    }
    for(i=0;i<MAP.rest.length;i++)
      s += '<circle class="pa-rest" cx="' + MAP.rest[i][0] + '" cy="' + MAP.rest[i][1] + '" r="4.5"/>';

    /* open loop, drawn as a ghost edge that never resolves */
    s += '<path class="pa-openedge" d="M 860 1148 C 1430 1120 1440 300 1120 186"/>';
    s += '<text class="pa-opentag" x="1398" y="720" text-anchor="middle" ' +
         'transform="rotate(-90 1398 720)">open loop &middot; autophagy &rarr; amino-acid pool</text>';

    for(i=0;i<MAP.edges.length;i++){
      var ed = MAP.edges[i], A = D.nodes[ed.s], B = D.nodes[ed.t];
      if(!A || !B) continue;
      var on = (lvl(ed.s) >= CFG.mastery.masteredFrom && lvl(ed.t) >= CFG.mastery.masteredFrom) ? 1 : 0;
      var pa = clip(A, B, boxW(A), BH), pb = clip(B, A, boxW(B), BH);
      s += '<line class="pa-mede" data-on="' + on + '" data-ind="' + (ed.dir === 'indirect' ? 1 : 0) +
           '" x1="' + pa.x + '" y1="' + pa.y + '" x2="' + pb.x + '" y2="' + pb.y + '"/>';
      var ang = Math.atan2(pb.y-pa.y, pb.x-pa.x), cc = Math.cos(ang), ss = Math.sin(ang);
      if(ed.eff === 'inhibits'){
        s += '<line class="pa-mede" data-on="' + on + '" x1="' + (pb.x-8*ss) + '" y1="' + (pb.y+8*cc) +
             '" x2="' + (pb.x+8*ss) + '" y2="' + (pb.y-8*cc) + '"/>';
      } else {
        s += '<polygon class="pa-mehead" data-on="' + on + '" points="' + pb.x + ',' + pb.y + ' ' +
             (pb.x-13*cc-5.6*ss) + ',' + (pb.y-13*ss+5.6*cc) + ' ' +
             (pb.x-13*cc+5.6*ss) + ',' + (pb.y-13*ss-5.6*cc) + '"/>';
      }
    }
    /* the one localisation the Atlas keeps open */
    s += '<g class="pa-open"><rect x="1237" y="673" width="140" height="34"/>' +
         '<text x="1307" y="690">Golgi ?</text></g>';

    for(id in D.nodes){
      n = D.nodes[id];
      var v = lvl(id), w = boxW(n), m = v >= 4 ? 4 : (v >= 3 ? 3 : (v >= 2 ? 2 : (v >= 1 ? 1 : 0)));
      s += '<g class="pa-mn" data-m="' + m + '" data-id="' + esc(id) + '" tabindex="0" role="button">';
      if(v >= CFG.mastery.goldFrom)
        s += '<rect class="pa-gold" x="' + (n.x-w/2-5) + '" y="' + (n.y-BH/2-5) + '" width="' + (w+10) +
             '" height="' + (BH+10) + '"/>';
      s += '<rect x="' + (n.x-w/2) + '" y="' + (n.y-BH/2) + '" width="' + w + '" height="' + BH + '"/>' +
           '<text x="' + n.x + '" y="' + (n.y+1) + '">' + esc(mapLabel(n)) + '</text></g>';
    }
    svg.innerHTML = s;
    svg.querySelectorAll('.pa-mn').forEach(function(g){
      function pick(){ sel = g.getAttribute('data-id'); paintNode(); }
      g.addEventListener('click', pick);
      g.addEventListener('keydown', function(ev){
        if(ev.key === 'Enter' || ev.key === ' '){ ev.preventDefault(); pick(); }
      });
    });
    paintStats();
  }

  function paintStats(){
    var el = document.getElementById('paStats'); if(!el) return;
    var core = 0, tot = 0, mast = 0, gold = 0, learn = 0, id, v;
    for(id in D.nodes){
      tot++; if(D.nodes[id].pool === 'core') core++;
      v = lvl(id);
      if(v >= CFG.mastery.goldFrom) gold++;
      if(v >= CFG.mastery.masteredFrom) mast++;
      else if(v >= 1) learn++;
    }
    el.innerHTML = tot + ' Academy nodes of ' + D.counts.atlas + ' in the Atlas &middot; <b>' + mast +
      '</b> mastered (<b>' + gold + '</b> gold) &middot; <b>' + learn + '</b> learning &middot; <b>' +
      (tot-mast-learn) + '</b> untouched &middot; <b>2</b> open';
  }

  function paintNode(){
    var el = document.getElementById('paNodePanel'); if(!el) return;
    if(!sel){ el.innerHTML = '<div class="pa-col"><p class="pa-note">' +
      esc(CFG.copy.progressLede) + '</p></div>'; return; }
    var n = D.nodes[sel], v = lvl(sel), pips = '', i;
    for(i=0;i<CFG.mastery.max;i++)
      pips += '<i class="' + (i < v ? (v >= CFG.mastery.goldFrom ? 'on gold' : 'on') : '') + '"></i>';
    var next = v >= CFG.mastery.goldFrom
      ? 'You can predict what happens when this node is removed. Keep it fresh &mdash; mastery decays.'
      : (v >= CFG.mastery.masteredFrom
         ? 'Predict a perturbation involving this node in the Perturbation Lab to reach gold.'
         : (v > 0 ? 'Wire it correctly and answer a question about it to raise it.'
                  : 'Untouched. It shows up in Daily 5 once you reach the lesson that covers it.'));
    el.innerHTML =
      '<div class="pa-col"><p class="pa-q" style="font-size:18px;margin:0 0 2px">' + esc(n.label) + '</p>' +
      '<p class="pa-sub">mastery ' + v + ' / ' + CFG.mastery.max + ' &middot; ' + esc(n.comp) +
      ' &middot; ' + (n.pool === 'core' ? 'core' : 'guided route') + '</p>' +
      '<div class="pa-pips">' + pips + '</div></div>' +
      '<div class="pa-col"><p class="pa-sub">What moves it</p><p class="pa-note">' + next + '</p>' +
      (n.url ? '<p class="pa-note"><a href="' + esc(n.url) + '">Lesson: ' +
        esc(n.lesson.replace(/-/g, ' ')) + ' &rarr;</a></p>' : '') + '</div>';
  }

  /* ---------------- badges ---------------- */
  var RING = 'M40.89 7.57 A26 26 0 1 1 23.11 7.57';
  var GLYPH = {
   predictor: '<g class="pa-bglyph"><path d="M12 37 H24" stroke-dasharray="4 5"/>' +
     '<path d="M27 37 H38"/><path d="M34 33 l4 4 -4 4"/><circle class="pa-solid" cx="47" cy="37" r="4"/></g>',
   architect: '<g class="pa-bglyph"><path d="M17 47 L29 34"/><path d="M28 39 l1 -5 5 1"/>' +
     '<path d="M35 34 L47 47"/><path d="M43 49 l7 -4"/><circle class="pa-solid" cx="14" cy="49" r="3.6"/>' +
     '<circle class="pa-solid" cx="32" cy="32" r="3.6"/></g>',
   calibrated: '<g class="pa-bglyph"><path d="M15 47 A17 17 0 0 1 49 47"/><path d="M32 47 L43 36"/>' +
     '<circle class="pa-solid" cx="32" cy="47" r="3.2"/></g>',
   core: '<g class="pa-bglyph"><path d="M19 31 H27"/><path d="M37 31 H45"/><path d="M19 45 H27"/>' +
     '<path d="M37 45 H45"/><circle class="pa-solid" cx="15" cy="31" r="3.4"/>' +
     '<circle class="pa-solid" cx="32" cy="31" r="3.4"/><circle class="pa-solid" cx="49" cy="31" r="3.4"/>' +
     '<circle class="pa-solid" cx="15" cy="45" r="3.4"/><circle class="pa-solid" cx="32" cy="45" r="3.4"/>' +
     '<circle class="pa-solid" cx="49" cy="45" r="3.4"/></g>',
   limits: '<g class="pa-bglyph"><path d="M14 39 H27"/><path d="M27 39 L44 29"/><path d="M27 39 L44 49"/>' +
     '<path d="M40 28 l4 1 -1 4"/><circle class="pa-solid" cx="43" cy="49" r="4.4"/></g>',
   methods: '<g class="pa-bglyph"><path d="M20 26 H44 V50 H20 Z"/><path d="M25 33 H39"/>' +
     '<path d="M25 39 H35"/><path d="M25 45 H33" stroke-width="4"/><circle cx="41" cy="45" r="4.6"/></g>',
   smalln: '<g class="pa-bglyph"><path d="M17 29 V47"/><path d="M13 29 H21"/><path d="M13 47 H21"/>' +
     '<path d="M32 32 V50"/><path d="M28 32 H36"/><path d="M28 50 H36"/><path d="M47 27 V45"/>' +
     '<path d="M43 27 H51"/><path d="M43 45 H51"/><circle class="pa-solid" cx="17" cy="38" r="2.6"/>' +
     '<circle class="pa-solid" cx="32" cy="41" r="2.6"/><circle class="pa-solid" cx="47" cy="36" r="2.6"/></g>',
   unknown: '<g class="pa-bglyph"><clipPath id="paUnk"><circle cx="32" cy="38" r="12.5"/></clipPath>' +
     '<g clip-path="url(#paUnk)" stroke-width="2.4"><path d="M16 44 L28 26"/><path d="M22 48 L36 28"/>' +
     '<path d="M29 50 L44 30"/><path d="M37 52 L50 34"/></g><circle cx="32" cy="38" r="12.5"/></g>',
   sources: '<g class="pa-bglyph"><path d="M22 26 H16 V50 H22"/><path d="M42 26 H48 V50 H42"/>' +
     '<path d="M26 43 H38"/><circle class="pa-solid" cx="32" cy="34" r="4.2"/></g>',
   falsifier: '<g class="pa-bglyph"><circle cx="21" cy="38" r="8.5"/>' +
     '<circle cx="44" cy="38" r="8.5" stroke-dasharray="3.5 4.5"/><path d="M35 47 L53 29" stroke-width="3.4"/></g>'
  };
  function badgeSvg(id, size, state, pct, tiers, tier){
    var p = state === 'earned' ? 100 : (state === 'progress' ? (pct||0) : 0);
    var seal = state === 'earned'
      ? '<circle class="pa-bseal" cx="32" cy="15" r="9"/>'
      : '<circle class="pa-bseal-h" cx="32" cy="15" r="8"/>';
    var pips = '', i;
    if(tiers > 1){
      var gap = 7, x0 = 32 - gap*(tiers-1)/2;
      for(i=0;i<tiers;i++)
        pips += '<circle class="pa-pip' + ((state === 'earned' && i < (tier||1)) ? ' on' : '') +
                '" cx="' + (x0+i*gap) + '" cy="68" r="2.4"/>';
    }
    return '<svg width="' + size + '" height="' + Math.round(size*74/64) + '" viewBox="0 0 64 74" ' +
      'aria-hidden="true"><path class="pa-bring-track" d="' + RING + '" stroke-width="4.4" ' +
      'stroke-linecap="round" pathLength="100"/>' +
      (p > 0 ? '<path class="pa-bring-fill" d="' + RING + '" stroke-width="4.4" stroke-linecap="round" ' +
        'pathLength="100" stroke-dasharray="' + p + ' 100"/>' : '') +
      seal + (GLYPH[id]||'') + pips + '</svg>';
  }
  function roman(n){ return ['','I','II','III'][n] || String(n); }
  function paintBadges(){
    var shelf = document.getElementById('paShelf'), list = document.getElementById('paCrit');
    if(!shelf) return;
    var html = '', crit = '', i, b, p, state, sub;
    for(i=0;i<CFG.badges.length;i++){
      b = CFG.badges[i];
      if(b.phase === 'A'){
        p = PA.badgeProgress(b);
        state = p.tier ? 'earned' : (p.pct > 0 ? 'progress' : 'locked');
        sub = p.tier ? (b.tiers.length > 1 ? 'Tier ' + roman(p.tier) : 'Earned')
                     : (p.gate ? p.gate : (b.metric === 'brier'
                        ? (p.value ? p.value.toFixed(2) + ' &rarr; ' + b.tiers[0] : 'no data yet')
                        : p.value + ' / ' + p.next));
      } else {
        p = {tier:0, pct:0}; state = 'locked'; sub = 'phase B';
      }
      html += '<div class="pa-badge" data-state="' + state + '">' +
              badgeSvg(b.id, 76, state, p.pct, b.tiers.length, p.tier) +
              '<div class="pa-bn">' + esc(b.name) + '</div><div class="pa-bs">' + sub + '</div></div>';
      crit += '<li><span class="pa-cn">' + esc(b.name) + '</span>' +
              '<span class="pa-cc">' + esc(b.criterion) + '</span>' +
              '<span class="pa-cv">' + (b.phase === 'A' ? sub : 'phase B') + '</span></li>';
    }
    shelf.innerHTML = html;
    if(list) list.innerHTML = crit;
  }

  /* ---------------- calibration ---------------- */
  function paintCal(){
    var el = document.getElementById('paCal'); if(!el) return;
    var br = PA.brier();
    if(S.rank < CFG.confidence.showScoreFromRank){
      el.innerHTML = '<p class="pa-note">Your calibration is being recorded from the first question, ' +
        'but the score only starts showing at rank ' + CFG.confidence.showScoreFromRank +
        ' &mdash; below about 50 judgements the number says more about luck than about you.</p>';
      return;
    }
    if(!br){ el.innerHTML = '<p class="pa-note">Answer a few more questions with a confidence level ' +
      'and the score appears here.</p>'; return; }
    var curve = PA.unlocked('calibration-curve') ? calCurve() : '';
    el.innerHTML = '<p class="pa-q" style="font-size:17px;margin:0 0 6px">Brier ' + br.v.toFixed(3) +
      ' <span class="pa-sub" style="margin-left:10px">over your last ' + br.n + ' judgements</span></p>' +
      '<p class="pa-note">Random guessing scores 0.25. &ldquo;Always 80% sure and right 80% of the time&rdquo; ' +
      'scores 0.16. A good expert sits near 0.10. Lower is better, and being wrong while certain is what ' +
      'moves it most.</p>' + curve;
  }

  /* ---------------- calibration curve (rank 5+) ---------------- */
  /* Cara na uhloprice = rikas 80 % a mas pravdu v 80 %. Bod nad ni znamena, ze
     si veris min, nez bys mel; pod ni, ze si veris vic. Zadne vyhlazovani --
     kdyz je v kosi peti odpovedi, vidis peti odpovedi. */
  function calCurve(){
    var bins = [[50,60],[60,70],[70,80],[80,90],[90,100]], i, j, out = [];
    for(i=0;i<bins.length;i++){
      var lo = bins[i][0]/100, hi = bins[i][1]/100, n = 0, ok = 0;
      for(j=0;j<S.br.length;j++){
        var p = S.br[j][0];
        if(p >= lo && (p < hi || (i === bins.length-1 && p <= hi))){ n++; ok += S.br[j][1]; }
      }
      out.push({lo:lo, hi:hi, n:n, acc: n ? ok/n : null});
    }
    var W = 340, H = 200, PAD = 34, x, y, s2 = '';
    s2 += '<svg viewBox="0 0 ' + W + ' ' + H + '" width="' + W + '" height="' + H +
          '" role="img" aria-label="Calibration: stated confidence against how often you were right">';
    s2 += '<line x1="' + PAD + '" y1="' + (H-PAD) + '" x2="' + (W-8) + '" y2="' + (H-PAD) +
          '" stroke="var(--line)"/>';
    s2 += '<line x1="' + PAD + '" y1="8" x2="' + PAD + '" y2="' + (H-PAD) + '" stroke="var(--line)"/>';
    s2 += '<line x1="' + PAD + '" y1="' + (H-PAD) + '" x2="' + (W-8) + '" y2="8" ' +
          'stroke="var(--soft)" stroke-dasharray="4 4" opacity=".6"/>';
    var px = function(v){ return PAD + (v - 0.5) / 0.5 * (W - 8 - PAD); };
    var py = function(v){ return (H-PAD) - v * (H - PAD - 8); };
    var pts = [];
    for(i=0;i<out.length;i++){
      if(out[i].acc === null) continue;
      x = px((out[i].lo + out[i].hi)/2); y = py(out[i].acc);
      pts.push(x.toFixed(1) + ',' + y.toFixed(1));
      s2 += '<circle cx="' + x.toFixed(1) + '" cy="' + y.toFixed(1) + '" r="' +
            Math.min(7, 3 + out[i].n/8).toFixed(1) + '" fill="var(--teal)"/>';
    }
    if(pts.length > 1)
      s2 += '<polyline points="' + pts.join(' ') + '" fill="none" stroke="var(--teal)" stroke-width="2"/>';
    s2 += '<text x="' + PAD + '" y="' + (H-10) + '" class="pa-bandsub">50%</text>' +
          '<text x="' + (W-30) + '" y="' + (H-10) + '" class="pa-bandsub">100%</text>' +
          '<text x="4" y="14" class="pa-bandsub">right</text>';
    s2 += '</svg>';
    return '<div style="margin-top:14px">' + s2 +
           '<p class="pa-note">Stated confidence across the bottom, how often you were actually right ' +
           'up the side. On the dashed line you are calibrated; above it you are underrating yourself, ' +
           'below it you are overconfident. Dot size is how many judgements sit in that bin.</p></div>';
  }

  /* ---------------- tools ---------------- */
  function wireTools(){
    var ex = document.getElementById('paExport');
    if(ex) ex.addEventListener('click', function(){
      var blob = new Blob([PA.exportBlob()], {type:'application/json'});
      var a = document.createElement('a');
      a.href = URL.createObjectURL(blob);
      a.download = 'mtor-atlas-practice.json';
      document.body.appendChild(a); a.click(); document.body.removeChild(a);
      setTimeout(function(){ URL.revokeObjectURL(a.href); }, 2000);
    });
    var imp = document.getElementById('paImport'), file = document.getElementById('paFile');
    if(imp && file){
      imp.addEventListener('click', function(){ file.click(); });
      file.addEventListener('change', function(){
        var f = file.files && file.files[0]; if(!f) return;
        var rd = new FileReader();
        rd.onload = function(){
          var err = PA.importBlob(String(rd.result));
          document.getElementById('paToolMsg').textContent =
            err ? err : 'Progress restored from that file.';
          if(!err){ S = PA.state(); redraw(); }
        };
        rd.readAsText(f);
      });
    }
    var rs = document.getElementById('paReset');
    if(rs) rs.addEventListener('click', function(){
      if(!window.confirm('Erase all practice progress in this browser? Export first if you want to keep it.')) return;
      PA.reset(); S = PA.state(); redraw();
      document.getElementById('paToolMsg').textContent = 'Progress cleared.';
    });
    document.querySelectorAll('#paSnap button').forEach(function(b){
      b.addEventListener('click', function(){
        snap = b.getAttribute('data-snap');
        document.querySelectorAll('#paSnap button').forEach(function(x){
          x.setAttribute('aria-pressed', String(x === b)); });
        snapM = snap === 'now' ? {} : PA.snapshotBack(30);
        drawMap(); paintNode();
      });
    });
  }

  function redraw(){ drawMap(); paintNode(); paintBadges(); paintCal(); paintHead(); }
  function paintHead(){
    var el = document.getElementById('paRank2'); if(!el) return;
    var r = PA.rankDef(S.rank);
    el.innerHTML = '<span class="pa-rk">Rank ' + r.n + '</span> <b>' + esc(r.name) + '</b> &middot; ' +
      S.xp + ' XP &middot; ' + S.met.answered + ' judgements';
  }

  wireTools(); redraw();
})();