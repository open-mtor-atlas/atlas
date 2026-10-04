(function(){
  var D = PA.boot('pa-data'); if(!D) return;
  var S = PA.state(), CFG = D.cfg, Q = CFG.qual;
  var board = document.getElementById('qlBoard');
  var fall = document.getElementById('qlFallback'); if(fall) fall.hidden = true;
  var set = [], qi = 0, res = [];
  var SKILL = {frontier:'Where the field stands', autopsy:'What the design cannot carry',
               sources:'Which study it stands on', quiz:'Experimental design'};

  function show(html){ board.innerHTML = html; board.hidden = false; }
  function head(prog){
    return '<div class="pa-bhead"><span class="pa-t">Qualifying Exam</span>' +
           '<span class="pa-prog">' + prog + '</span></div>';
  }
  /* postup bez skore: kolik otazek uz je za tebou, ne kolik spravne */
  function dots(i, n){
    var s = '', k;
    for(k=0;k<n;k++) s += '<i class="ql-dot' + (k < i ? ' done' : (k === i ? ' now' : '')) + '"></i>';
    return '<span class="ql-dots" aria-hidden="true">' + s + '</span>';
  }
  function pick(){
    var by = {}, i, it, g, out = [];
    for(i=0;i<D.items.length;i++){ it = D.items[i]; g = it.hand ? 'hand' : it.game; (by[g] = by[g] || []).push(it); }
    for(g in Q.mix){
      var pool = PA.shuffle((by[g] || []).slice()), n = Q.mix[g], take = [], used = {};
      if(g === 'frontier'){
        /* ruzne stitky, aby se nedalo uspet tipovanim "established" */
        for(i=0;i<pool.length && take.length<n;i++) if(!used[pool[i].label]){ used[pool[i].label] = 1; take.push(pool[i]); }
      }
      for(i=0;i<pool.length && take.length<n;i++) if(take.indexOf(pool[i]) < 0) take.push(pool[i]);
      out = out.concat(take);
    }
    return PA.shuffle(out);
  }
  function intro(){
    var ranks = CFG.ranks, top = ranks[Q.maxRank-1], pi = ranks[ranks.length-1];
    show(head(Q.size + ' questions &middot; ~5 min') + '<div class="pa-body">' +
      '<p class="pa-rk">The goal</p><p class="pa-qres">' + Q.hero.goal + '</p>' +
      '<p class="pa-q">Ten questions. For each one, say how sure you are.</p>' +
      '<p class="pa-note">A mix of four kinds: where the field actually stands on a pathway step, which ' +
      'limit of a real paper matters, which study in the Atlas a claim stands on, and hand-written ' +
      'experimental-design questions. You are scored on how many you get right <em>and</em> on ' +
      'calibration (Brier score: 0 is perfect, always answering 50 % gives 0.25).</p>' +
      '<p class="pa-note">The highest place the exam can give is <b>' + top.name + '</b>, and only with ' +
      'good calibration. <b>' + pi.name + '</b> is not examined: it is earned in the Arena. ' +
      'Placement can raise your Arena rank, never lower it, and it adds no XP.</p>' +
      '<div class="pa-tools" style="margin-top:16px"><button class="pa-cbtn pa-ngo" id="qlGo" type="button">Start &rarr;</button></div></div>');
    document.getElementById('qlGo').addEventListener('click', begin);
  }
  function begin(){
    set = pick(); qi = 0; res = [];
    PA.track('qual_started', {rank: S.rank});
    ask();
  }
  function ask(){
    if(qi >= set.length) return result();
    var it = set[qi], opts = '', i, L = 'ABCDEFGH';
    for(i=0;i<it.options.length;i++)
      opts += '<button class="pa-opt" type="button" data-i="' + i + '"><span class="pa-k">' + L[i] +
              '</span><span>' + it.options[i] + '</span></button>';
    show(head(dots(qi, set.length) + ' ' + (qi+1) + ' / ' + set.length + ' &middot; ' + (SKILL[it.game] || '')) + '<div class="pa-body">' +
      (it.stem ? '<div class="pa-stem">' + it.stem + '</div>' : '') +
      '<p class="pa-q">' + it.prompt + '</p>' + (it.sub ? '<p class="pa-sub">' + it.sub + '</p>' : '') +
      '<div class="pa-opts">' + opts + '</div>' +
      (it.game === 'frontier' ? '<p class="pa-note">' + D.frontierHelp + '</p>' : '') +
      '<div id="qlConf"></div><div id="qlFb"></div></div>');
    var chosen = -1;
    board.querySelectorAll('.pa-opt').forEach(function(b){
      b.addEventListener('click', function(){
        if(document.getElementById('qlFb').innerHTML) return;
        chosen = parseInt(b.getAttribute('data-i'), 10);
        board.querySelectorAll('.pa-opt').forEach(function(x){ x.setAttribute('aria-pressed', String(x === b)); });
        var c = document.getElementById('qlConf');
        if(!c.innerHTML){
          c.innerHTML = '<div class="pa-conf"><span class="pa-clab">How sure are you?</span>' +
            '<div class="pa-slider"><input type="range" id="qlP" min="50" max="99" value="70" step="1" ' +
            'aria-label="Confidence in percent"><output id="qlPo">70%</output>' +
            '<button class="pa-cbtn" id="qlSubmit" type="button">Submit</button></div></div>';
          var r = document.getElementById('qlP'), o = document.getElementById('qlPo');
          r.addEventListener('input', function(){ o.textContent = r.value + '%'; });
          document.getElementById('qlSubmit').addEventListener('click', function(){
            grade(it, chosen, parseInt(r.value, 10) / 100);
          });
        }
      });
    });
  }
  function grade(it, chosen, p){
    var ok = chosen === it.answer;
    res.push({ok:ok, p:p, game:it.hand ? 'hand' : it.game, lesson:it.lesson || ''});
    board.querySelectorAll('.pa-opt').forEach(function(b){
      var i = parseInt(b.getAttribute('data-i'), 10); b.disabled = true;
      if(i === it.answer) b.setAttribute('data-state', 'right');
      else if(i === chosen) b.setAttribute('data-state', 'wrong');
    });
    document.getElementById('qlConf').innerHTML = '';
    var msg = ok ? 'Correct.' : 'Not this one.';
    if(!ok && p >= Q.sureFrom) msg += ' At ' + Math.round(p*100) + ' % sure, this is the one to remember.';
    var tempt = (!ok && window.atlasTempt) ? window.atlasTempt(it, chosen) : '';
    document.getElementById('qlFb').innerHTML =
      (tempt ? '<p class="pa-tempt">' + tempt + '</p>' : '') +
      '<div class="pa-fb" data-ok="' + (ok?1:0) + '"><b>' + msg + '</b> ' + (it.explain || '') +
      (it.sid ? ' <span class="pa-sub">' + it.sid + '</span>' : '') + '</div>' +
      (it.game === 'frontier' ? '<div class="pa-disbox" id="qlDis"></div>' : '') +
      '<div class="pa-tools" style="margin-top:16px"><button id="qlNext" type="button">' +
      (qi + 1 < set.length ? 'Next &rarr;' : 'See your result &rarr;') + '</button></div>';
    if(it.game === 'frontier' && window.atlasDisagree)
      window.atlasDisagree(document.getElementById('qlDis'), it.id,
                           (it.options[chosen] || '').replace(/<[^>]+>/g, '').split(' ')[0], CFG.copy.disagree);
    var nx = document.getElementById('qlNext');
    nx.addEventListener('click', function(){ qi++; ask(); });
    nx.focus();
  }
  function place(score, brier){
    var r = 1, i, why = '';
    for(i=0;i<Q.placement.length;i++) if(score >= Q.placement[i].min){ r = Q.placement[i].rank; break; }
    var byScore = r;
    while(r > 1 && PA.rankDef(r).brier && brier > PA.rankDef(r).brier) r--;
    if(r < byScore)
      why = 'Your score alone would place you as ' + PA.rankDef(byScore).name + '; ' +
            PA.rankDef(byScore).name + ' needs a Brier score of ' + PA.rankDef(byScore).brier +
            ' or lower, and yours was ' + brier.toFixed(2) + '.';
    return {rank: r, why: why};
  }
  function result(){
    var n = res.length, ok = 0, b = 0, over = 0, i;
    for(i=0;i<n;i++){
      if(res[i].ok) ok++;
      b += Math.pow(res[i].p - (res[i].ok ? 1 : 0), 2);
      if(!res[i].ok && res[i].p >= Q.sureFrom) over++;
    }
    var brier = n ? b / n : 0.25;
    var pl = place(ok, brier), R = PA.rankDef(pl.rank);
    var raised = PA.place(pl.rank, {score: ok, n: n, brier: Math.round(brier*1000)/1000});
    PA.track('qual_finished', {score: ok, of: n, brier: Math.round(brier*100)/100, placed: pl.rank, raised: raised ? 1 : 0});
    var line = 'Right on ' + ok + ' of ' + n + '.';
    line += over ? ' Certain (90 % or more) on ' + over + ' you got wrong.' : ' Not once certain and wrong.';
    /* Po kategoriich jen pocty, zadne "Strong/Excellent": ze dvou az ctyr
       otazek se ziadne hodnoceni dovednosti udelat neda (review 4. 10. 2026). */
    var cats = {}, order = [], g, weak = null, wr = 2;
    for(i=0;i<n;i++){
      g = res[i].game;
      if(!cats[g]){ cats[g] = {ok:0, n:0, lesson:''}; order.push(g); }
      cats[g].n++; if(res[i].ok) cats[g].ok++;
      else if(res[i].lesson && !cats[g].lesson) cats[g].lesson = res[i].lesson;
    }
    var rows = order.map(function(c){
      var r = cats[c].ok / cats[c].n;
      if(r < 1 && r < wr){ wr = r; weak = c; }
      return '<li><span>' + (Q.categories[c] ? Q.categories[c].name : c) + '</span><b>' +
             cats[c].ok + ' / ' + cats[c].n + '</b></li>';
    }).join('');
    var fix = '';
    if(weak){
      var C = Q.categories[weak] || {}, href = C.href, lab = C.fix;
      if(!href && cats[weak].lesson){ href = '/academy/core/' + cats[weak].lesson + '/'; lab = 'The lesson behind the question you missed'; }
      if(href) fix = '<p class="pa-note"><b>One thing to work on:</b> ' + (C.name || weak) + '. <a href="' + href + '">' + lab + ' &rarr;</a></p>';
    }
    var fw = Q.firstWeek;
    var week = fw ? '<div class="ql-week"><p class="pa-rk">' + fw.title + '</p><p class="pa-note">' + fw.text + '</p><p>' +
      fw.links.map(function(l){ return '<a href="' + l.href + '">' + l.label + ' &rarr;</a>'; }).join('<br>') + '</p></div>' : '';
    show(head('Result') + '<div class="pa-body">' +
      '<p class="pa-rk">Placed as</p><p class="pa-qres">' + R.name + '</p>' +
      '<p class="pa-q">' + ok + ' / ' + n + ' &middot; Brier ' + brier.toFixed(2) + '</p>' +
      '<p class="pa-note">' + line + (pl.why ? ' ' + pl.why : '') + ' ' + Q.calibNote + '</p>' +
      '<ul class="ql-cats">' + rows + '</ul>' + fix +
      '<p class="pa-note">' + (raised ? 'Your Arena rank is now <b>' + R.name + '</b>, and the games up to that rank are open. Your XP is unchanged: it counts only answers given in the Arena.' :
        'Your Arena rank stays <b>' + PA.rankDef(S.rank).name + '</b>: placement never lowers a rank.') + '</p>' +
      '<div class="pa-tools" style="margin-top:16px">' +
      '<button class="pa-cbtn pa-ngo" id="qlShare" type="button">Challenge someone on Bluesky</button>' +
      '<a class="pa-cbtn" href="/academy/practice/" style="text-decoration:none">Go to the Arena &rarr;</a>' +
      '<button class="pa-cbtn" id="qlAgain" type="button">Another set</button></div>' + week + '</div>');
    document.getElementById('qlShare').addEventListener('click', function(){
      window.atlasShare(CFG.copy.shareQual.replace('{score}', ok).replace('{n}', n).replace('{rank}', R.name),
                        'https://mtor-atlas.org/academy/qual/', 'academy-qual');
    });
    document.getElementById('qlAgain').addEventListener('click', begin);
  }
  intro();
})();