(function(){
  var D = PA.boot('pa-data'); if(!D) return;
  var S = PA.state(), CFG = D.cfg;
  var board = document.getElementById('paBoard');
  var fall = document.getElementById('paFallback');
  if(fall) fall.hidden = true;

  var mode = null, queue = [], qi = 0, session = {ok:0, n:0, xp:0};

  /* ---------------- chrome ---------------- */
  function esc(s){ return String(s==null?'':s); }
  function el(html){ var d = document.createElement('div'); d.innerHTML = html; return d.firstChild; }

  function paintRank(){
    var r = PA.rankDef(S.rank), nx = PA.nextRank();
    var bar = document.getElementById('paRank'); if(!bar) return;
    var pct = 0, to = '';
    if(nx && nx.phase === 'A'){
      var span = Math.max(1, nx.xp - r.xp);
      pct = Math.max(0, Math.min(100, Math.round((S.xp - r.xp) / span * 100)));
      to = (nx.xp - S.xp > 0 ? (nx.xp - S.xp) + ' XP to ' : 'ready for ') + nx.name;
    } else {
      pct = 100; to = 'Phase B ranks open with the next set of games';
    }
    bar.innerHTML =
      '<div><p class="pa-rk">Rank ' + r.n + '</p><p class="pa-rkname">' + esc(r.name) + '</p></div>' +
      '<span class="pa-xp"><b>' + S.xp + '</b> XP</span>' +
      '<span class="pa-meter"><i style="width:' + pct + '%"></i></span>' +
      '<span class="pa-to">' + esc(to) + '</span>' +
      (PA.rankReady() ? '<button class="pa-cbtn" id="paExam" type="button">Take the rank-up board</button>' : '');
    var ex = document.getElementById('paExam');
    if(ex) ex.addEventListener('click', function(){ startExam(); });
  }

  function paintTiles(){
    var wrap = document.getElementById('paTiles'); if(!wrap) return;
    var html = '', i, g, on;
    for(i=0;i<CFG.games.length;i++){
      g = CFG.games[i];
      on = S.rank >= g.rank;
      html += '<button class="pa-tile" type="button" data-game="' + g.id + '"' +
              (on ? '' : ' disabled') + ' aria-pressed="false">' +
              '<span class="pa-skill">' + esc(g.skill) + (on ? '' : ' &middot; rank ' + g.rank) + '</span>' +
              '<h3>' + esc(g.name) + '</h3><p>' + esc(g.blurb) + '</p></button>';
    }
    wrap.innerHTML = html;
    wrap.querySelectorAll('.pa-tile').forEach(function(b){
      b.addEventListener('click', function(){ start(b.getAttribute('data-game')); });
    });
  }
  function pressTile(id){
    var wrap = document.getElementById('paTiles'); if(!wrap) return;
    wrap.querySelectorAll('.pa-tile').forEach(function(b){
      b.setAttribute('aria-pressed', String(b.getAttribute('data-game') === id));
    });
  }

  /* ---------------- board shell ---------------- */
  function head(title, prog){
    return '<div class="pa-bhead"><span class="pa-t">' + esc(title) + '</span>' +
           '<span class="pa-prog">' + esc(prog||'') + '</span></div>';
  }
  function show(html){ board.innerHTML = html; board.hidden = false; }

  /* ---------------- confidence ---------------- */
  function confHtml(){
    if(S.rank >= CFG.confidence.sliderFromRank){
      return '<div class="pa-conf"><span class="pa-clab">How sure are you?</span>' +
        '<div class="pa-slider"><input type="range" id="paP" min="50" max="99" value="75" step="1" ' +
        'aria-label="Confidence in percent"><output id="paPo">75%</output>' +
        '<button class="pa-cbtn" id="paSubmit" type="button">Submit</button></div></div>';
    }
    var b = CFG.confidence.buttons, html = '', i;
    for(i=0;i<b.length;i++){
      html += '<button class="pa-cbtn" type="button" data-p="' + b[i].p + '">' + esc(b[i].label) + '</button>';
    }
    return '<div class="pa-conf"><span class="pa-clab">How sure are you?</span>' +
           '<div class="pa-cbtns">' + html + '</div></div>';
  }
  function wireConf(onPick){
    var slider = document.getElementById('paP');
    if(slider){
      var out = document.getElementById('paPo');
      slider.addEventListener('input', function(){ out.textContent = slider.value + '%'; });
      document.getElementById('paSubmit').addEventListener('click', function(){
        onPick(parseInt(slider.value,10)/100);
      });
      return;
    }
    board.querySelectorAll('.pa-cbtns .pa-cbtn').forEach(function(b){
      b.addEventListener('click', function(){
        board.querySelectorAll('.pa-cbtns .pa-cbtn').forEach(function(x){
          x.setAttribute('aria-pressed', String(x === b)); });
        onPick(parseFloat(b.getAttribute('data-p')));
      });
    });
  }

  /* ---------------- generic MCQ card ---------------- */
  function mcq(item, title, prog, after){
    var opts = '', i, letters = 'ABCDEFGH';
    for(i=0;i<item.options.length;i++){
      opts += '<button class="pa-opt" type="button" data-i="' + i + '">' +
              '<span class="pa-k">' + letters[i] + '</span><span>' + item.options[i] + '</span></button>';
    }
    show(head(title, prog) + '<div class="pa-body">' +
         (item.stem ? '<div class="pa-stem">' + item.stem + '</div>' : '') +
         '<p class="pa-q">' + item.prompt + '</p>' +
         (item.sub ? '<p class="pa-sub">' + esc(item.sub) + '</p>' : '') +
         '<div class="pa-opts">' + opts + '</div>' +
         (item.game === 'frontier' ? '<p class="pa-note">' + D.frontierHelp + '</p>' : '') +
         '<div id="paConf"></div><div id="paFb"></div></div>');

    var chosen = -1;
    board.querySelectorAll('.pa-opt').forEach(function(b){
      b.addEventListener('click', function(){
        if(chosen >= 0) return;
        chosen = parseInt(b.getAttribute('data-i'),10);
        board.querySelectorAll('.pa-opt').forEach(function(x){ x.setAttribute('aria-pressed', String(x===b)); });
        b.style.borderColor = 'var(--ink)';
        document.getElementById('paConf').innerHTML = confHtml();
        wireConf(function(p){ grade(item, chosen, p, after); });
        var f = board.querySelector('#paConf .pa-cbtn, #paConf input'); if(f) f.focus();
      });
    });
  }

  function grade(item, chosen, p, after){
    var ok = (chosen === item.answer);
    var res = PA.record(item, ok, p, chosen);
    session.n++; session.xp += res.xp; if(ok) session.ok++;
    board.querySelectorAll('.pa-opt').forEach(function(b){
      var i = parseInt(b.getAttribute('data-i'),10);
      b.disabled = true; b.style.borderColor = '';
      if(i === item.answer) b.setAttribute('data-state','right');
      else if(i === chosen) b.setAttribute('data-state','wrong');
    });
    var conf = document.getElementById('paConf'); if(conf) conf.innerHTML = '';
    var msg = ok ? 'Correct.' : 'Not this time.';
    if(!ok && p !== null && p >= CFG.confidence.sureThreshold)
      msg += ' You were confident &mdash; that is the combination worth slowing down for.';
    if(ok && p !== null && p < CFG.confidence.sureThreshold)
      msg += ' You had it and did not trust it.';
    document.getElementById('paFb').innerHTML =
      '<div class="pa-fb" data-ok="' + (ok?1:0) + '"><b>' + msg + '</b> ' + esc2(item.explain) +
      (item.sid ? ' <span class="pa-sub">' + esc(item.sid) + '</span>' : '') +
      '<span class="pa-xpgain">+' + res.xp + ' XP' + badgeLine(res.badges) + '</span></div>' +
      '<div class="pa-tools" style="margin-top:16px"><button id="paNext" type="button">Next &rarr;</button></div>';
    document.getElementById('paNext').addEventListener('click', after);
    document.getElementById('paNext').focus();
    paintRank(); paintWorld();
  }
  function esc2(s){ return s == null ? '' : String(s); }
  function badgeLine(bs){
    if(!bs || !bs.length) return '';
    var names = bs.map(function(b){ return b.name + (b.tier>1 ? ' ' + 'I'.repeat(b.tier) : ''); });
    return ' &middot; badge earned: ' + names.join(', ');
  }

  /* ---------------- queue runner (daily / limits / exam) ---------------- */
  function runQueue(title){
    if(qi >= queue.length) return finish(title);
    var item = queue[qi];
    var prog = (qi+1) + ' / ' + queue.length;
    if(item.game === 'pert'){ pertCard(item, title, prog, next); }
    else { mcq(item, title, prog, next); }
    function next(){ qi++; runQueue(title); }
  }
  function finish(title){
    var pass = null;
    if(mode === 'exam'){
      pass = session.ok >= Math.ceil(queue.length * CFG.rankup.passRatio);
      if(pass) PA.promote();
    }
    if(mode === 'daily'){ S.day.done = 1; PA.save(); }
    show(head(title, '') + '<div class="pa-body">' +
      '<p class="pa-q">' + session.ok + ' of ' + session.n + ' &middot; +' + session.xp + ' XP</p>' +
      (pass === null ? '' :
        '<p class="pa-fb">' + (pass ?
          '<b>Promoted.</b> You are now ' + esc(PA.rankDef(S.rank).name) + '. ' + esc(PA.rankDef(S.rank).blurb) :
          '<b>Not yet.</b> Nothing is lost &mdash; practise the weak nodes and take the board again.') + '</p>') +
      '<div class="pa-tools" style="margin-top:16px">' +
      '<button id="paBack" type="button">Back to the games</button>' +
      '<button id="paMap" type="button">See your pathway &rarr;</button></div></div>');
    document.getElementById('paBack').addEventListener('click', function(){
      board.hidden = true; pressTile(''); paintRank(); });
    document.getElementById('paMap').addEventListener('click', function(){
      location.href = '/academy/progress/'; });
    paintRank();
  }

  /* ---------------- Perturbation Lab ---------------- */
  function pertCard(item, title, prog, after){
    var M = PA.modelById(item.model);
    if(!M){ return mcq(item, title, prog, after); }
    var keys = (M.controls||[]).map(function(c){ return c.id; });
    var vals = item.state.split('|');
    var setting = '', i, c;
    for(i=0;i<(M.controls||[]).length;i++){
      c = M.controls[i];
      setting += '<div class="pa-ctrl"><span class="pa-clab2">' + esc(c.label) + '</span>' +
                 '<div class="pa-cgrp">' + c.options.map(function(o){
                   return '<button type="button" disabled aria-pressed="' +
                          (o === vals[i]) + '">' + esc(o) + '</button>'; }).join('') +
                 '</div></div>';
    }
    var readouts = PA.shuffle(M.readouts.slice()).slice(0,4);
    var right = M.states[item.state].readout;
    if(readouts.indexOf(right) < 0){ readouts[readouts.length-1] = right; }
    var q = dict(item, {options: readouts, answer: readouts.indexOf(right),
                        prompt: 'The controls are set as shown. <strong>Predict the readout</strong> before it is revealed.',
                        sub: M.title});
    show(head(title, prog) + '<div class="pa-body">' +
         '<div class="pa-ctrls">' + setting + '</div>' +
         '<div class="pa-diagram">' + diagram(M, null) + '</div>' +
         '<p class="pa-q">' + q.prompt + '</p><p class="pa-sub">' + esc(M.title) + '</p>' +
         '<div class="pa-opts">' + readouts.map(function(r,i){
            return '<button class="pa-opt" type="button" data-i="' + i + '">' +
                   '<span class="pa-k">' + 'ABCD'[i] + '</span><span>' + r + '</span></button>'; }).join('') +
         '</div><div id="paConf"></div><div id="paFb"></div></div>');

    var chosen = -1;
    board.querySelectorAll('.pa-opt').forEach(function(b){
      b.addEventListener('click', function(){
        if(chosen >= 0) return;
        chosen = parseInt(b.getAttribute('data-i'),10);
        b.style.borderColor = 'var(--ink)';
        document.getElementById('paConf').innerHTML = confHtml();
        wireConf(function(p){
          var st = M.states[item.state];
          document.querySelector('.pa-diagram').innerHTML = diagram(M, st);
          grade(q, chosen, p, after);
        });
      });
    });
  }
  function dict(base, over){
    var o = {}, k;
    for(k in base) o[k] = base[k];
    for(k in over) o[k] = over[k];
    return o;
  }
  function diagram(M, st){
    /* Kresli se z `layout` a `edges` modelu -- tedy z toho, co uz je v lekci.
       Bez stavu jsou vsechny uzly neutralni; se stavem se rozsviti flow a
       preruseny krok se vykresli carkovane. */
    var COLW = 168, BW = 132, BH = 34, GAPY = 52, PADX = 12, PADY = 16;
    var pos = {}, cols = M.layout || [], maxRows = 1, i, j;
    for(i=0;i<cols.length;i++) maxRows = Math.max(maxRows, cols[i].length);
    var H = PADY*2 + maxRows*BH + (maxRows-1)*(GAPY-BH);
    var W = PADX*2 + cols.length*COLW - (COLW-BW);
    for(i=0;i<cols.length;i++){
      for(j=0;j<cols[i].length;j++){
        pos[cols[i][j]] = {x: PADX + i*COLW + BW/2,
                           y: PADY + BH/2 + j*GAPY + (maxRows - cols[i].length)*GAPY/2};
      }
    }
    var on = {}, cut = {};
    if(st){ (st.flow||[]).forEach(function(n){ on[n]=1; }); (st.cut||[]).forEach(function(x){ cut[x]=1; }); }
    var svg = '<svg viewBox="0 0 ' + W + ' ' + H + '" width="' + W + '" height="' + H +
              '" role="img" aria-label="Model diagram">';
    (M.edges||[]).forEach(function(ed){
      var a = pos[ed.s], b = pos[ed.t]; if(!a || !b) return;
      var x1 = a.x + BW/2 + 3, x2 = b.x - BW/2 - 3, flow = st ? (cut[ed.id] ? 'off' : (on[ed.t] ? 'on' : 'off')) : '';
      if(x2 < x1){ x1 = a.x - BW/2 - 3; x2 = b.x + BW/2 + 3; }
      svg += '<path class="pa-dedge" data-flow="' + flow + '" d="M ' + x1 + ' ' + a.y +
             ' L ' + x2 + ' ' + b.y + '"/>';
      var dir = x2 > x1 ? 1 : -1;
      if(ed.eff === 'inhibits'){
        svg += '<path class="pa-dedge" data-flow="' + flow + '" d="M ' + x2 + ' ' + (b.y-7) +
               ' L ' + x2 + ' ' + (b.y+7) + '"/>';
      } else {
        svg += '<path class="pa-dedge" data-flow="' + flow + '" d="M ' + (x2-8*dir) + ' ' + (b.y-5) +
               ' L ' + x2 + ' ' + b.y + ' L ' + (x2-8*dir) + ' ' + (b.y+5) + '"/>';
      }
    });
    for(i=0;i<cols.length;i++){
      for(j=0;j<cols[i].length;j++){
        var id = cols[i][j], p = pos[id];
        svg += '<g class="pa-dnode" data-flow="' + (st ? (on[id]?'on':'off') : '') + '">' +
               '<rect x="' + (p.x-BW/2) + '" y="' + (p.y-BH/2) + '" width="' + BW + '" height="' + BH + '"/>' +
               '<text x="' + p.x + '" y="' + (p.y+1) + '">' + esc(M.labels[id] || id) + '</text></g>';
      }
    }
    return svg + '</svg>';
  }

  /* ---------------- Signal Sprint ---------------- */
  function sprint(){
    var cards = PA.shuffle(PA.pool('sprint').slice()).slice(0, CFG.sprint.cards);
    if(!cards.length) return;
    var left = CFG.sprint.seconds, k = 0, ok = 0, done = 0, timer;
    show(head('Signal Sprint', '') + '<div class="pa-body"><div class="pa-sprint">' +
         '<p class="pa-clock" id="paClock">' + left + 's</p>' +
         '<p class="pa-sprintq" id="paSq"></p>' +
         '<div class="pa-sprintbtns" id="paSb"></div>' +
         '<p class="pa-flash" id="paFlash"></p></div></div>');
    var clock = document.getElementById('paClock');
    timer = setInterval(function(){
      left--; clock.textContent = left + 's';
      if(left <= 0){ clearInterval(timer); end(); }
    }, 1000);
    function draw(){
      if(k >= cards.length) return end();
      var it = cards[k];
      document.getElementById('paSq').innerHTML = it.prompt;
      document.getElementById('paSb').innerHTML = it.options.map(function(o,i){
        return '<button type="button" data-i="' + i + '">' + esc(o) + '</button>'; }).join('');
      document.getElementById('paSb').querySelectorAll('button').forEach(function(b){
        b.addEventListener('click', function(){
          var i = parseInt(b.getAttribute('data-i'),10), good = (i === it.answer);
          var res = PA.record(it, good, null);
          done++; if(good) ok++;
          document.getElementById('paFlash').innerHTML = good
            ? 'correct &middot; +' + res.xp + ' XP'
            : 'no &mdash; ' + esc(it.options[it.answer]);
          k++; draw(); paintRank();
        });
      });
    }
    function end(){
      clearInterval(timer);
      session = {ok: ok, n: done, xp: 0};
      mode = 'sprint';
      show(head('Signal Sprint', '') + '<div class="pa-body">' +
        '<p class="pa-q">' + ok + ' of ' + done + ' in ' + CFG.sprint.seconds + ' seconds</p>' +
        '<p class="pa-note">Sprint is the one game scored on speed &mdash; everything else here rewards ' +
        'judgement instead. It is a warm-up, not a measure.</p>' +
        '<div class="pa-tools" style="margin-top:16px">' +
        '<button id="paAgain" type="button">Again</button>' +
        '<button id="paBack" type="button">Back to the games</button></div></div>');
      document.getElementById('paAgain').addEventListener('click', sprint);
      document.getElementById('paBack').addEventListener('click', function(){
        board.hidden = true; pressTile(''); });
      paintRank();
    }
    draw();
  }

  /* ---------------- Wire the Pathway ---------------- */
  function wire(){
    var puzzles = PA.wirePool();
    if(!puzzles.length) return;
    var P = puzzles[Math.floor(Math.random()*puzzles.length)];
    var labels = {}, i;
    for(i=0;i<P.seq.length;i++) labels[P.seq[i]] = D.nodes[P.seq[i]] ? D.nodes[P.seq[i]].label : P.seq[i];
    var chips = P.seq.slice();
    if(P.distractor){ chips.push(P.distractor); labels[P.distractor] = D.nodes[P.distractor].label; }
    chips = PA.shuffle(chips);
    var slots = new Array(P.seq.length), signs = new Array(P.seq.length-1), sel = null;
    var hard = P.diff >= 3;

    function render(){
      var html = head('Wire the Pathway', P.diff === 1 ? 'easy' : (P.diff === 2 ? 'medium' : 'hard')) +
        '<div class="pa-body"><p class="pa-q">' + esc(P.name || 'Rebuild this route') + '</p>' +
        '<p class="pa-sub">Place the steps in order, then set each arrow: &rarr; activates, &#8867; inhibits.' +
        (hard ? ' One chip does not belong on this route.' : '') + '</p>' +
        '<div class="pa-wire"><div class="pa-chips" id="paChips">' +
        chips.map(function(id){
          var used = slots.indexOf(id) >= 0;
          return '<button class="pa-chip" type="button" data-id="' + id + '" data-used="' + (used?1:0) + '"' +
                 ' aria-pressed="' + (sel===id) + '">' + esc(labels[id]) + '</button>'; }).join('') +
        '</div><div class="pa-slots" id="paSlots">';
      for(i=0;i<P.seq.length;i++){
        html += '<button class="pa-slot" type="button" data-s="' + i + '" data-filled="' +
                (slots[i]?1:0) + '">' + (slots[i] ? esc(labels[slots[i]]) : 'slot ' + (i+1)) + '</button>';
        if(i < P.seq.length-1){
          html += '<div class="pa-bond" data-b="' + i + '">' +
                  '<button type="button" data-sg="activates" aria-pressed="' + (signs[i]==='activates') + '" ' +
                  'title="activates">&rarr;</button>' +
                  '<button type="button" data-sg="inhibits" aria-pressed="' + (signs[i]==='inhibits') + '" ' +
                  'title="inhibits">&#8867;</button></div>';
        }
      }
      html += '</div></div><div class="pa-tools" style="margin-top:18px">' +
              '<button id="paCheck" type="button">Check</button>' +
              '<button id="paBack" type="button">Back to the games</button></div>' +
              '<div id="paFb"></div></div>';
      show(html);
      board.querySelectorAll('.pa-chip').forEach(function(b){
        b.addEventListener('click', function(){
          if(b.getAttribute('data-used') === '1') return;
          sel = (sel === b.getAttribute('data-id')) ? null : b.getAttribute('data-id');
          render();
        });
      });
      board.querySelectorAll('.pa-slot').forEach(function(b){
        b.addEventListener('click', function(){
          var k = parseInt(b.getAttribute('data-s'),10);
          if(slots[k]){ slots[k] = null; }
          else if(sel){ slots[k] = sel; sel = null; }
          render();
        });
      });
      board.querySelectorAll('.pa-bond button').forEach(function(b){
        b.addEventListener('click', function(){
          var k = parseInt(b.parentNode.getAttribute('data-b'),10);
          signs[k] = b.getAttribute('data-sg');
          render();
        });
      });
      document.getElementById('paCheck').addEventListener('click', check);
      document.getElementById('paBack').addEventListener('click', function(){
        board.hidden = true; pressTile(''); });
    }

    function check(){
      var okBonds = 0, wrong = [], i, allPlaced = true;
      for(i=0;i<P.seq.length;i++) if(!slots[i]) allPlaced = false;
      if(!allPlaced){
        document.getElementById('paFb').innerHTML =
          '<div class="pa-fb" data-ok="0"><b>Not finished.</b> Every slot needs a step before this can be checked.</div>';
        return;
      }
      for(i=0;i<P.steps.length;i++){
        var st = P.steps[i];
        var placed = (slots[i] === st.s && slots[i+1] === st.t);
        var signed = (signs[i] === st.eff);
        if(placed && signed) okBonds++;
        else wrong.push({i:i, st:st, placed:placed, signed:signed});
      }
      var perfect = (wrong.length === 0);
      var res = PA.recordWire(P, okBonds, perfect);
      board.querySelectorAll('.pa-slot').forEach(function(b){
        var k = parseInt(b.getAttribute('data-s'),10);
        b.setAttribute('data-ok', slots[k] === P.seq[k] ? '1' : '0');
      });
      var html = '<div class="pa-fb" data-ok="' + (perfect?1:0) + '"><b>' +
        (perfect ? 'The whole route is right.' : okBonds + ' of ' + P.steps.length + ' steps correct.') + '</b>';
      wrong.slice(0,3).forEach(function(w){
        html += '<br>' + esc(D.nodes[w.st.s].label) + ' ' + (w.st.eff === 'inhibits' ? 'inhibits' : 'activates') +
                ' ' + esc(D.nodes[w.st.t].label) +
                (w.st.dir === 'indirect' ? ' <em>(indirect &mdash; it runs through a step not drawn here)</em>' : '') +
                (w.st.why ? ' &mdash; ' + esc2(w.st.why) : '');
      });
      html += '<span class="pa-xpgain">+' + res.xp + ' XP' + badgeLine(res.badges) + '</span></div>' +
              '<div class="pa-tools" style="margin-top:14px"><button id="paAgain" type="button">Another route</button>' +
              '<button id="paBack2" type="button">Back to the games</button></div>';
      document.getElementById('paFb').innerHTML = html;
      document.getElementById('paAgain').addEventListener('click', wire);
      document.getElementById('paBack2').addEventListener('click', function(){
        board.hidden = true; pressTile(''); });
      paintRank();
    }
    render();
  }

  /* ---------------- entry points ---------------- */
  function startQueue(ids, title){
    queue = ids.map(PA.itemById).filter(Boolean);
    qi = 0; session = {ok:0, n:0, xp:0};
    runQueue(title);
  }
  function startExam(){
    mode = 'exam';
    var nx = PA.nextRank();
    var all = PA.pool(null).filter(function(it){ return it.game !== 'sprint'; });
    var ids = PA.shuffle(all).slice(0, CFG.rankup.size).map(function(it){ return it.id; });
    pressTile('');
    startQueue(ids, 'Rank-up board &middot; ' + (nx ? nx.name : ''));
  }
  function start(game){
    mode = game; pressTile(game);
    if(game === 'sprint') return sprint();
    if(game === 'wire') return wire();
    if(game === 'daily') return startQueue(PA.daily(), 'Daily 5');
    var p = PA.pool(game);
    if(!p.length){ return; }
    var ids = PA.shuffle(p.slice()).slice(0,5).map(function(it){ return it.id; });
    startQueue(ids, game === 'pert' ? 'Perturbation Lab' : "What It Doesn't Show");
  }

  /* ---------------- how much of the world is uncovered ---------------- */
  /* Procenta se pocitaji z uzlu, ktere JDOU zvladnout. Otevrene otazky do
     jmenovatele nepatri: kdyby patrily, hra by slibovala 100 % tam, kde obor
     zadnou odpoved nema. */
  function paintWorld(){
    var box = document.getElementById('paWorld'); if(!box) return;
    var ids = Object.keys(D.nodes), tot = ids.length;
    var seen = 0, mast = 0, gold = 0, i, v;
    for(i=0;i<ids.length;i++){
      v = PA.mastery(ids[i]);
      if(v >= CFG.mastery.goldFrom) gold++;
      else if(v >= CFG.mastery.masteredFrom) mast++;
      else if(v >= 1) seen++;
    }
    var touched = seen + mast + gold;
    var pct = Math.round(touched / tot * 100);
    var pctM = Math.round((mast + gold) / tot * 100);
    var w = function(x){ return (x / tot * 100).toFixed(2) + '%'; };

    box.innerHTML =
      '<div class="pa-wleft">' +
        '<div class="pa-wpct"><span class="pa-wnum">' + pctM + '%</span>' +
        '<span class="pa-wlab">of the pathway mastered &middot; ' + pct + '% explored</span></div>' +
        '<div class="pa-wbar">' +
          '<i class="w-gold" style="width:' + w(gold) + '"></i>' +
          '<i class="w-mast" style="width:' + w(mast) + '"></i>' +
          '<i class="w-seen" style="width:' + w(seen) + '"></i>' +
        '</div>' +
        '<div class="pa-wkeys">' +
          '<span><i class="w-gold"></i><b>' + gold + '</b> can predict</span>' +
          '<span><i class="w-mast"></i><b>' + mast + '</b> mastered</span>' +
          '<span><i class="w-seen"></i><b>' + seen + '</b> learning</span>' +
          '<span><i class="w-none"></i><b>' + (tot - touched) + '</b> untouched</span>' +
          '<span><i class="w-open"></i><b>2</b> open &mdash; never fill</span>' +
        '</div>' +
        '<a class="pa-wgo" href="/academy/progress/">Open the full map &rarr;</a>' +
      '</div>' +
      '<div class="pa-wmini">' + minimap() + '</div>';
  }
  function minimap(){
    /* Minimapa je tataz mapa jako na /academy/progress/, jen bez popisku:
       stejne souradnice z pathway/model.json, stejne barvy. */
    var W = 460, H = 460, X0 = 60, Y0 = 50, XS = 1400, YS = 1370;
    var sx = function(x){ return (x - X0) / XS * W; };
    var sy = function(y){ return (y - Y0) / YS * H; };
    var s = '<svg viewBox="0 0 ' + W + ' ' + H + '" role="img" ' +
            'aria-label="Miniature map of the pathway, coloured by what you have practised">';
    var i, r = D.map.rest;
    for(i=0;i<r.length;i++)
      s += '<circle class="m-rest" cx="' + sx(r[i][0]).toFixed(1) + '" cy="' +
           sy(r[i][1]).toFixed(1) + '" r="3"/>';
    var ids = Object.keys(D.nodes), id, nd, v, m;
    for(i=0;i<ids.length;i++){
      id = ids[i]; nd = D.nodes[id]; v = PA.mastery(id);
      m = v >= CFG.mastery.goldFrom ? 4 : (v >= CFG.mastery.masteredFrom ? 3 : (v >= 1 ? 1 : 0));
      s += '<rect class="m-n" data-m="' + m + '" x="' + (sx(nd.x) - 9).toFixed(1) + '" y="' +
           (sy(nd.y) - 4).toFixed(1) + '" width="18" height="8" rx="1"/>';
    }
    /* dve veci, ktere se nikdy nezaplni */
    s += '<rect class="m-open" x="' + (sx(1307) - 9).toFixed(1) + '" y="' + (sy(690) - 4).toFixed(1) +
         '" width="18" height="8" rx="1"/>';
    s += '<path class="m-open" d="M ' + sx(880).toFixed(1) + ' ' + sy(1148).toFixed(1) +
         ' C ' + sx(1430).toFixed(1) + ' ' + sy(1120).toFixed(1) + ', ' +
         sx(1440).toFixed(1) + ' ' + sy(300).toFixed(1) + ', ' +
         sx(1120).toFixed(1) + ' ' + sy(186).toFixed(1) + '" fill="none"/>';
    return s + '</svg>';
  }

  paintRank(); paintTiles(); paintWorld();
  var note = document.getElementById('paStorage');
  if(note) note.hidden = false;
})();