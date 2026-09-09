window.PA = (function(){
  var D = null, S = null, KEY = 'atlas-practice-v1';
  var DAY = 86400000;

  function today(){ return Math.floor(Date.now()/DAY); }
  function clamp(x,a,b){ return x<a?a:(x>b?b:x); }

  function boot(dataId){
    var el = document.getElementById(dataId);
    if(!el) return null;
    try { D = JSON.parse(el.textContent); } catch(err){ return null; }
    KEY = (D.cfg && D.cfg.storageKey) || KEY;
    S = read();
    return D;
  }

  function blank(){
    return {v:1, xp:0, rank:1, m:{}, seen:{}, br:[],
            met:{predictOk:0, predictLessons:[], wirePerfect:0, wirePerfectHard:0,
                 limitsOk:0, sprintOk:0, answered:0,
                 autopsyOk:0, autopsyKinds:[], sampleOk:0, sampleFalseReject:0,
                 openOk:0, openFalse:0, sourceOk:0, sourceWeakening:[], discriminating:0},
            bg:{}, day:{d:0, ids:[], done:0}, st:{n:0,d:0}, snaps:[], exam:null};
  }
  function read(){
    var o;
    try { o = JSON.parse(localStorage.getItem(KEY)||'null'); } catch(err){ o = null; }
    if(!o || typeof o !== 'object') return blank();
    var b = blank(), k;
    for(k in b){ if(!(k in o)) o[k] = b[k]; }
    for(k in b.met){ if(!(k in o.met)) o.met[k] = b.met[k]; }
    return o;
  }
  function save(){
    try { localStorage.setItem(KEY, JSON.stringify(S)); } catch(err){}
  }
  function state(){ return S; }
  function data(){ return D; }

  /* ---------------- mastery (with decay) ---------------- */
  /* Mastery is what you can do NOW. A node you stop practising slides back
     towards "learning" -- but never all the way to untouched, because you did
     once know it. That floor is deliberate: the review queue should nag, not
     erase. */
  function mastery(id){
    var rec = S.m[id]; if(!rec) return 0;
    var cf = D.cfg.mastery, lvl = rec[0], age = today() - rec[1];
    if(lvl >= cf.decayFrom && cf.halfLifeDays > 0){
      var drop = Math.floor(age / cf.halfLifeDays);
      lvl = Math.max(cf.decayFrom - 1, lvl - drop);
    }
    return clamp(lvl, 0, cf.max);
  }
  function bumpMastery(ids, ok, sure){
    var cf = D.cfg.mastery, i, id, lvl;
    for(i=0;i<(ids||[]).length;i++){
      id = ids[i];
      lvl = mastery(id);
      if(ok){ lvl += (sure ? cf.gainRightSure : cf.gainRight); }
      else  { lvl -= (sure ? cf.loseWrongSure : cf.loseWrong); }
      S.m[id] = [clamp(lvl,0,cf.max), today()];
    }
  }
  function masteredCount(minLevel){
    var n=0, id;
    for(id in D.nodes){ if(mastery(id) >= minLevel) n++; }
    return n;
  }

  /* ---------------- scoring ---------------- */
  function calibBand(p, ok){
    /* Sure and right pays most; sure and wrong pays nothing. Never negative --
       punishing points teaches people to stop committing to a judgement, which
       is the opposite of what this whole layer is for. */
    var c = D.cfg.xp.calibration, sure = (p >= D.cfg.confidence.sureThreshold);
    if(ok) return sure ? c.sureRight : c.unsureRight;
    return sure ? c.sureWrong : c.unsureWrong;
  }
  function noveltyFor(item){
    var seen = S.seen[item.id];
    if(!seen) return D.cfg.xp.novelty.first;
    if(seen[1] === today() && seen[0] >= D.cfg.xp.novelty.sameDayCap) return 0;
    return D.cfg.xp.novelty.review;
  }
  function scoreItem(item, ok, p){
    var cf = D.cfg.xp;
    var base = cf.base[item.game] || 10;
    var diff = cf.difficulty[String(item.diff||1)] || 1;
    var cal  = (p === null) ? (ok ? 1 : 0) : calibBand(p, ok);
    var nov  = noveltyFor(item);
    var xp = Math.round(base * diff * cal * nov);
    if(ok && nov === cf.novelty.first && !(S.seen[item.id])) xp += cf.firstTryBonus;
    return Math.max(0, xp);
  }

  /* ---------------- Brier ---------------- */
  function pushBrier(p, ok){
    if(p === null) return;
    S.br.push([Math.round(p*100)/100, ok?1:0]);
    var w = D.cfg.confidence.window * 2;
    if(S.br.length > w) S.br = S.br.slice(S.br.length - w);
  }
  function brier(){
    var w = D.cfg.confidence.window;
    var a = S.br.slice(Math.max(0, S.br.length - w));
    if(a.length < 5) return null;
    var s = 0, i;
    for(i=0;i<a.length;i++){ s += Math.pow(a[i][0] - a[i][1], 2); }
    return {v: s/a.length, n: a.length};
  }

  /* ---------------- answering ---------------- */
  function record(item, ok, p, chosen){
    if(chosen !== undefined) item.chosen = chosen;
    var sure = (p !== null && p >= D.cfg.confidence.sureThreshold);
    var xp = scoreItem(item, ok, p);
    var seen = S.seen[item.id];
    S.seen[item.id] = [ (seen?seen[0]:0) + 1, today(), seen ? seen[2] : (ok?1:0) ];
    S.xp += xp;
    S.met.answered++;
    bumpMastery(item.nodes, ok, sure);
    pushBrier(p, ok);
    if(ok){
      if(item.game === 'pert' || item.game === 'predict'){
        S.met.predictOk++;
        if(item.lesson && S.met.predictLessons.indexOf(item.lesson) < 0)
          S.met.predictLessons.push(item.lesson);
      }
      if(item.game === 'limits') S.met.limitsOk++;
      if(item.game === 'sprint') S.met.sprintOk++;
      if(item.game === 'autopsy'){
        S.met.autopsyOk++;
        /* Odznak Methods Reader chce SIRI zaber: kazdy druh slabiny se zapocita
           jednou, aby dvacet nalezu jednoho druhu nestacilo. */
        if(item.kind && S.met.autopsyKinds.indexOf(item.kind) < 0) S.met.autopsyKinds.push(item.kind);
        if(item.kind === 'sample') S.met.sampleOk++;
      }
      if(item.game === 'sources'){
        S.met.sourceOk++;
        if(item.variant === 'weaken' && S.met.sourceWeakening.indexOf(item.id) < 0)
          S.met.sourceWeakening.push(item.id);
      }
      if(item.game === 'frontier' && item.label === 'open') S.met.openOk++;
    } else {
      /* Chybne odpovedi, ktere maji vlastni vahu: obvinit z maleho vzorku neco,
         co ma uplne jinou slabinu, a oznacit usazeny mechanismus za otevrenou
         otazku. Obe jsou "skepse, ktera pali na vsechno" -- odznaky je hlidaji. */
      if(item.game === 'autopsy' && item.optKinds && item.chosen !== undefined
         && item.optKinds[item.chosen] === 'sample' && item.kind !== 'sample')
        S.met.sampleFalseReject++;
      if(item.game === 'frontier' && item.chosen === 3 && item.label === 'established')
        S.met.openFalse++;
    }
    touchStreak();
    snapshot();
    var gained = evalBadges();
    save();
    return {xp: xp, badges: gained};
  }
  function recordWire(puz, bonds, perfect){
    var cf = D.cfg.xp;
    var xp = Math.round((cf.base.wire + cf.wirePerBond*bonds) *
                        (cf.difficulty[String(puz.diff)]||1) * noveltyFor({id:puz.id}));
    var seen = S.seen[puz.id];
    S.seen[puz.id] = [ (seen?seen[0]:0)+1, today(), seen ? seen[2] : (perfect?1:0) ];
    S.xp += xp;
    S.met.answered++;
    bumpMastery(puz.seq, perfect, false);
    if(perfect){
      S.met.wirePerfect++;
      if(puz.diff >= 3) S.met.wirePerfectHard++;
    }
    touchStreak(); snapshot();
    var gained = evalBadges();
    save();
    return {xp: xp, badges: gained};
  }

  /* ---------------- streak (freezable, never punitive) ---------------- */
  function touchStreak(){
    var t = today(), gap = t - (S.st.d||0);
    if(gap === 0) return;
    if(S.st.d && gap <= (D.cfg.daily.streakFreezeDays||3)) S.st.n++;
    else S.st.n = 1;
    S.st.d = t;
  }

  /* ---------------- snapshots ("a month ago") ---------------- */
  function snapshot(){
    var t = today(), every = D.cfg.snapshotEveryDays || 7;
    var last = S.snaps.length ? S.snaps[S.snaps.length-1][0] : -9999;
    if(t - last < every) return;
    var m = {}, id;
    for(id in D.nodes){ var v = mastery(id); if(v) m[id] = v; }
    S.snaps.push([t, m]);
    if(S.snaps.length > (D.cfg.snapshotKeep||8)) S.snaps.shift();
  }
  function snapshotBack(days){
    var t = today() - days, best = null, i;
    for(i=0;i<S.snaps.length;i++){ if(S.snaps[i][0] <= t) best = S.snaps[i]; }
    if(!best && S.snaps.length) best = S.snaps[0];
    return best ? best[1] : {};
  }

  /* ---------------- badges ---------------- */
  function metricValue(b){
    if(b.metric === 'brier'){ var br = brier(); return br ? br.v : null; }
    if(b.metric === 'coreMastered'){
      var need = 0, have = 0, id;
      for(id in D.nodes){
        if(D.nodes[id].pool !== 'core') continue;
        need++; if(mastery(id) >= D.cfg.mastery.masteredFrom) have++;
      }
      return need && have === need ? 1 : 0;
    }
    return S.met[b.metric] || 0;
  }
  function badgeProgress(b){
    /* -> {tier, next, pct, value} ; tier 0 = not earned yet */
    var v = metricValue(b), tier = 0, i, pct = 0, next = b.tiers[0];
    if(b.metric === 'brier'){
      var br = brier(), min = b.minSamples || 0;
      if(!br || br.n < min){
        return {tier:0, value:v, next:b.tiers[0], pct: br ? Math.min(99, Math.round(br.n/min*100)) : 0,
                gate:'need ' + min + ' judgements'};
      }
      for(i=0;i<b.tiers.length;i++){ if(v <= b.tiers[i]) tier = i+1; }
      next = b.tiers[Math.min(tier, b.tiers.length-1)];
      pct = tier ? 100 : clamp(Math.round((0.25 - v) / (0.25 - b.tiers[0]) * 100), 0, 99);
      return {tier:tier, value:v, next:next, pct:pct};
    }
    if(b.spread && b.spread.min){
      var got = (S.met[b.spread.key]||[]).length || 0;
      if(got < b.spread.min && v >= b.tiers[0]){
        return {tier:0, value:v, next:b.tiers[0],
                pct: Math.min(99, Math.round(got/b.spread.min*100)),
                gate:'across ' + b.spread.min + ' lessons (' + got + ')'};
      }
    }
    for(i=0;i<b.tiers.length;i++){ if(v >= b.tiers[i]) tier = i+1; }
    next = b.tiers[Math.min(tier, b.tiers.length-1)];
    pct = tier >= b.tiers.length ? 100 : clamp(Math.round(v / next * 100), 0, 99);
    return {tier:tier, value:v, next:next, pct: tier ? Math.max(pct, 100/b.tiers.length*tier) : pct};
  }
  function evalBadges(){
    var gained = [], i, b, p;
    for(i=0;i<D.cfg.badges.length;i++){
      b = D.cfg.badges[i];
      p = badgeProgress(b);
      if(p.tier > (S.bg[b.id]||0)){
        S.bg[b.id] = p.tier;
        gained.push({id:b.id, name:b.name, tier:p.tier});
      }
    }
    return gained;
  }

  /* ---------------- ranks ---------------- */
  function rankDef(n){
    var i; for(i=0;i<D.cfg.ranks.length;i++){ if(D.cfg.ranks[i].n === n) return D.cfg.ranks[i]; }
    return D.cfg.ranks[0];
  }
  function nextRank(){ return rankDef(S.rank + 1); }
  function rankReady(){
    var r = nextRank();
    if(!r || r.n === S.rank) return false;
    if(S.xp < r.xp) return false;
    if(masteredCount(r.masteredAt || 3) < (r.masteredNodes||0)) return false;
    if(r.brier){ var br = brier(); if(!br || br.v > r.brier) return false; }
    return true;
  }
  function promote(){ S.rank = Math.min(S.rank+1, D.cfg.ranks.length); save(); }
  function unlocked(what){
    var i, r;
    for(i=0;i<D.cfg.ranks.length;i++){
      r = D.cfg.ranks[i];
      if(r.n > S.rank) continue;
      if((r.unlocks||[]).indexOf(what) >= 0) return true;
    }
    return false;
  }

  /* ---------------- item pools ---------------- */
  function allowed(item){
    if(item.pool === 'route' && !unlocked('routepool')) return false;
    if(item.game === 'pert' && !unlocked('pert')) return false;
    if(item.game === 'limits' && !unlocked('limits')) return false;
    if(item.game === 'autopsy' && !unlocked('autopsy')) return false;
    if(item.game === 'sources' && !unlocked('sources')) return false;
    if(item.game === 'frontier' && !unlocked('frontier')) return false;
    if((item.diff||1) > S.rank + 1) return false;
    return true;
  }
  function pool(game){
    var out = [], i, it;
    for(i=0;i<D.items.length;i++){
      it = D.items[i];
      if(game && it.game !== game) continue;
      if(!allowed(it)) continue;
      out.push(it);
    }
    return out;
  }
  function wirePool(){
    var out = [], i, p;
    for(i=0;i<D.wire.length;i++){
      p = D.wire[i];
      if(p.pool === 'route' && !unlocked('routepool')) continue;
      if(p.diff >= 3 && !unlocked('wirehard')) continue;
      out.push(p);
    }
    return out;
  }
  function shuffle(a){
    var i, j, t;
    for(i=a.length-1;i>0;i--){ j = Math.floor(Math.random()*(i+1)); t=a[i]; a[i]=a[j]; a[j]=t; }
    return a;
  }
  function weakestFirst(list){
    /* review order: lowest current mastery first, oldest first as tie-break */
    return list.slice().sort(function(a,b){
      var ma = itemMastery(a), mb = itemMastery(b);
      if(ma !== mb) return ma - mb;
      var sa = S.seen[a.id], sb = S.seen[b.id];
      return (sa?sa[1]:0) - (sb?sb[1]:0);
    });
  }
  function itemMastery(it){
    if(!it.nodes || !it.nodes.length) return 3;
    var s = 0, i;
    for(i=0;i<it.nodes.length;i++) s += mastery(it.nodes[i]);
    return s / it.nodes.length;
  }
  function daily(){
    var cf = D.cfg.daily, t = today();
    if(S.day.d === t && S.day.ids.length) return S.day.ids;
    var all = pool(null).filter(function(it){ return it.game !== 'sprint'; });
    var seen = [], fresh = [], stretch = [], i, it;
    for(i=0;i<all.length;i++){
      it = all[i];
      if(S.seen[it.id]) seen.push(it);
      else if((it.diff||1) > S.rank) stretch.push(it);
      else fresh.push(it);
    }
    var picked = [];
    picked = picked.concat(weakestFirst(seen).slice(0, cf.review));
    picked = picked.concat(shuffle(fresh).slice(0, cf.fresh));
    picked = picked.concat(shuffle(stretch).slice(0, cf.stretch));
    if(picked.length < cf.size)
      picked = picked.concat(shuffle(all).slice(0, cf.size - picked.length));
    var ids = [], used = {};
    for(i=0;i<picked.length && ids.length<cf.size;i++){
      if(used[picked[i].id]) continue;
      used[picked[i].id] = 1; ids.push(picked[i].id);
    }
    S.day = {d:t, ids:ids, done:0};
    save();
    return ids;
  }
  function itemById(id){
    var i; for(i=0;i<D.items.length;i++){ if(D.items[i].id === id) return D.items[i]; }
    return null;
  }
  function modelById(id){
    var i; for(i=0;i<D.models.length;i++){ if(D.models[i].id === id) return D.models[i]; }
    return null;
  }

  /* ---------------- export / import ---------------- */
  function exportBlob(){
    return JSON.stringify({app:'open-mtor-atlas-practice', v:1, saved:new Date().toISOString(),
                           state:S}, null, 1);
  }
  function importBlob(txt){
    var o;
    try { o = JSON.parse(txt); } catch(err){ return 'That file is not valid JSON.'; }
    var st = o && (o.state || (o.xp !== undefined ? o : null));
    if(!st || typeof st !== 'object') return 'That file does not look like a progress export.';
    S = st;
    var b = blank(), k;
    for(k in b){ if(!(k in S)) S[k] = b[k]; }
    save();
    return null;
  }
  function reset(){ S = blank(); save(); }

  return {boot:boot, state:state, data:data, save:save, today:today,
          mastery:mastery, masteredCount:masteredCount, record:record,
          recordWire:recordWire, brier:brier, badgeProgress:badgeProgress,
          rankDef:rankDef, nextRank:nextRank, rankReady:rankReady, promote:promote,
          unlocked:unlocked, pool:pool, wirePool:wirePool, daily:daily,
          itemById:itemById, modelById:modelById, shuffle:shuffle,
          snapshotBack:snapshotBack, exportBlob:exportBlob, importBlob:importBlob,
          reset:reset};
})();