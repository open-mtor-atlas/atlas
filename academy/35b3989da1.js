(function(){
  var DAY = 86400000;
  function today(){ return Math.floor(Date.now()/DAY); }
  function readJSON(key){
    try { return JSON.parse(localStorage.getItem(key)||'null'); } catch(err){ return null; }
  }
  function track(name, p){
    try { if(typeof gtag === 'function') gtag('event', name, p||{}); } catch(err){}
  }
  /* o = {lessons:[{slug,n,t,url,min}], pa, practice, check, rankReady} */
  function atlasNext(o){
    var read = readJSON('atlas-academy-progress') || {};
    var pa = o.pa || null, L = o.lessons || [], i, last = null, nextL = null;
    for(i=0;i<L.length;i++){
      if(read[L[i].slug] === 'done') last = L[i];
      else if(!nextL) nextL = L[i];
    }
    var answered = pa && pa.met ? (pa.met.answered||0) : 0;
    if(!last && !answered && L.length){
      return {kick:'Start here', title:'Lesson ' + L[0].n + ' &middot; ' + L[0].t,
              meta: L[0].min + ' min. The games and challenges all point back at the lessons.',
              href:L[0].url, label:'Read lesson ' + L[0].n + ' &rarr;'};
    }
    if(last && ((pa && pa.lsn && pa.lsn[last.slug]) || 0) < (o.check||3)){
      return {kick:'Your next step', title:'Check yourself on lesson ' + last.n,
              meta:'A few questions from &ldquo;' + last.t + '&rdquo;. Predict before you look; about five minutes.',
              href:o.practice + '?lesson=' + last.slug, lesson:last.slug,
              label:'Practise lesson ' + last.n + ' &rarr;'};
    }
    if(o.rankReady){
      return {kick:'Your next step', title:'Take the rank-up board',
              meta:'Eight mixed questions. Three in four right moves you up a rank.',
              href:o.practice + '?game=exam', game:'exam', label:'Take the board &rarr;'};
    }
    if(pa && answered && !(pa.day && pa.day.d === today() && pa.day.done)){
      return {kick:'Your next step', title:'Daily 5',
              meta:'Two you have seen, two new, one a level up. Three minutes.',
              href:o.practice + '?game=daily', game:'daily', label:'Play the Daily 5 &rarr;'};
    }
    if(nextL){
      return {kick:'Your next step', title:'Lesson ' + nextL.n + ' &middot; ' + nextL.t,
              meta: nextL.min ? nextL.min + ' min' : 'The next lesson in the course.',
              href:nextL.url, label:'Read lesson ' + nextL.n + ' &rarr;'};
    }
    return {kick:'Your next step', title:'A Research Challenge',
            meta:'You have read every lesson. Spend a research budget on a question the field has not closed.',
            href:'/academy/research-challenges/', label:'Investigate &rarr;'};
  }
  function atlasShare(text, url, where){
    track('bluesky_cta', {cta:'challenge', page_type: where || 'academy'});
    var u = 'https://bsky.app/intent/compose?text=' + encodeURIComponent(text + ' ' + url);
    try { window.open(u, '_blank', 'noopener'); } catch(err){ location.href = u; }
  }
  /* box = element, kam se tlacitko vlozi; ref = id polozky; chose = popisek volby */
  function atlasDisagree(box, ref, chose, label){
    if(!box) return;
    var path = location.pathname + '#' + ref + (chose ? ':chose-' + String(chose).toLowerCase().replace(/[^a-z]+/g,'-') : '');
    box.innerHTML = '<button type="button" class="pa-dis">' + (label || "I'd call this differently") + '</button>';
    box.querySelector('button').addEventListener('click', function(){
      track('correction_open', {page_path: path, page_type: 'academy-frontier'});
      box.innerHTML = '<label class="pa-dislab" for="paDisTxt">How would you call it, and why? ' +
        'Sent anonymously to the curators, exactly as typed (max. 100 characters).</label>' +
        '<div class="pa-disrow"><input id="paDisTxt" type="text" maxlength="100" autocomplete="off">' +
        '<button type="button" class="pa-cbtn" id="paDisGo">Send</button></div>';
      var inp = document.getElementById('paDisTxt'); inp.focus();
      document.getElementById('paDisGo').addEventListener('click', function(){
        var t = (inp.value||'').trim(); if(!t) { inp.focus(); return; }
        track('correction_report', {report_text: t.slice(0,100), page_path: path, page_type: 'academy-frontier'});
        box.innerHTML = '<p class="pa-note">Thank you. A curator reads every one of these against the studies behind the label.</p>';
      });
    });
  }
  window.atlasNext = atlasNext; window.atlasShare = atlasShare; window.atlasDisagree = atlasDisagree;
})();