(function(){
  var el = document.getElementById('acHome'); if(!el) return;
  var D; try{ D = JSON.parse(el.textContent); }catch(err){ return; }

  function read(key){
    try{ return JSON.parse(localStorage.getItem(key)||'null'); }catch(err){ return null; }
  }
  var lessons = read('atlas-academy-progress') || {};
  var pa = read(D.key);

  /* --- kolik lekci je precteno ------------------------------------------ */
  var done = 0, next = null, i;
  for(i=0;i<D.lessons.length;i++){
    if(lessons[D.lessons[i].slug] === 'done') done++;
    else if(!next) next = D.lessons[i];
  }
  if(!next) next = D.lessons[D.lessons.length-1];

  /* --- mastery s decay, stejny vzorec jako v Practice Arene -------------- */
  function mastery(rec){
    if(!rec) return 0;
    var lvl = rec[0], age = Math.floor(Date.now()/86400000) - rec[1];
    if(lvl >= D.decayFrom && D.half > 0) lvl = Math.max(D.decayFrom-1, lvl - Math.floor(age/D.half));
    return lvl < 0 ? 0 : lvl;
  }
  var seen = 0, mast = 0, gold = 0;
  if(pa && pa.m){
    for(i=0;i<D.nodes.length;i++){
      var v = mastery(pa.m[D.nodes[i][0]]);
      if(v >= D.gold) gold++; else if(v >= D.mastered) mast++; else if(v >= 1) seen++;
    }
  }
  var touched = seen + mast + gold;
  var pct = Math.round(touched / D.nodes.length * 100);
  /* Hlavni cislo je ZVLADNUTO, ne "videno". Prohlednout si uzel je levne;
     mit ho na urovni 3+ znamena, ze na nej clovek odpovedel spravne a jeste to
     neprovalo decayem. Explored zustava jako druhe cislo. */
  var pctM = Math.round((mast + gold) / D.nodes.length * 100);
  var rank = null;
  if(pa){
    for(i=0;i<D.ranks.length;i++){ if(D.ranks[i].n === (pa.rank||1)) rank = D.ranks[i]; }
  }
  var last = read('atlas-academy-last');
  if(last && (typeof last.url !== 'string' || last.url.indexOf('/academy/') !== 0 ||
              last.url.indexOf('//') >= 0)) last = null;
  var started = (done > 0) || (pa && pa.xp > 0) || !!last;
  var DAY = 86400000;
  function esc(x){ return String(x).replace(/[&<>"]/g, function(c){
    return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]; }); }
  function ago(ts){
    var d = Math.floor((Date.now() - (ts||0)) / DAY);
    return d <= 0 ? 'today' : (d === 1 ? 'yesterday' : d + ' days ago');
  }
  /* --- kde clovek skoncil: posledni otevrena lekce, ktera jeste neni
     oznacena jako prectena, nebo rozehrana vyzva (do 60 dni) ------------- */
  var resume = null, resumeLesson = null;
  if(last && (Date.now() - (last.ts||0)) < 60*DAY){
    if(last.k === 'lesson' && lessons[last.slug] !== 'done'){
      for(i=0;i<D.lessons.length;i++){ if(D.lessons[i].slug === last.slug) resumeLesson = D.lessons[i]; }
      if(resumeLesson){
        var sec = (last.sec && /^[A-Za-z0-9_-]+$/.test(last.sec)) ? '#' + last.sec : '';
        resume = {href: resumeLesson.url + sec,
                  title: 'Lesson ' + resumeLesson.n + ' &middot; ' + esc(resumeLesson.t),
                  where: (sec && last.st ? 'You stopped at &ldquo;' + esc(last.st) + '&rdquo;'
                                         : 'Opened, not yet marked as read') + ' &middot; ' + ago(last.ts),
                  btn: 'Continue lesson ' + resumeLesson.n + ' &rarr;'};
      }
    } else if(last.k === 'challenge' && last.t){
      resume = {href: last.url, title: esc(last.t),
                where: 'Research Challenge &middot; ' + ago(last.ts),
                btn: 'Continue the challenge &rarr;'};
    }
  }

  /* --- minimapa ---------------------------------------------------------- */
  if(pa && pa.m){
    var svg = document.getElementById('acMiniSvg');
    if(svg){
      svg.querySelectorAll('.m-n').forEach(function(r){
        var v = mastery(pa.m[r.getAttribute('data-id')]);
        r.setAttribute('data-m', v >= D.gold ? 4 : (v >= D.mastered ? 3 : (v >= 1 ? 1 : 0)));
      });
      var cap = document.getElementById('acMiniCap');
      if(cap) cap.textContent = pctM + '% mastered';
    }
  }

  /* --- pruh "kde jsi" ---------------------------------------------------- */
  /* Primarni tlacitko se meni podle toho, co ma clovek rozecteno. Dokud neni
     petka lekci, vede na lekci -- trenink bez latky je zabavnejsi, ale uci min.
     Pak se poradi obraci a Practice Arena jde dopredu. */
  var box = document.getElementById('acResumeText');
  var fork = document.getElementById('acFork');
  var rbox = document.getElementById('acResume');
  if(fork && started) fork.hidden = true;
  if(rbox && started) rbox.hidden = false;
  if(!pa){ var mn = document.querySelector('#acResume .ac-mini'); if(mn) mn.hidden = true; }
  if(box && started){
    var lessonBtn = '<a class="ac-cta ac-quiet" href="' + next.url + '">Continue lesson ' +
                    next.n + ' &rarr;</a>';
    var dailyBtn  = '<a class="ac-cta ac-quiet" href="' + D.practice + '">Practice Arena &rarr;</a>';
    var lessonPri = '<a class="ac-cta" href="' + next.url + '">Continue lesson ' +
                    next.n + ' &middot; ' + next.min + ' min &rarr;</a>';
    var dailyPri  = '<a class="ac-cta" href="' + D.practice + '">Practice Arena &middot; ' +
                    D.games + ' games</a>';
    var first = (done >= 5 && pa) ? (dailyPri + lessonBtn) : (lessonPri + (pa ? dailyBtn : ''));
    /* Od 4. 10. 2026 vede primarni tlacitko tam, kam ukazuje atlasNext() --
       stejne doporuceni jako "Your next step" v Arene, aby si homepage a hra
       neodporovaly. Druhe tlacitko zustava na Arenu / lekci. */
    if(window.atlasNext){
      var st = window.atlasNext({lessons:D.lessons, pa:pa, practice:D.practice,
                                 check:(D.next && D.next.check) || 3, rankReady:false});
      first = '<a class="ac-cta" href="' + st.href + '">' + st.title + ' &rarr;</a>' +
              (st.href.indexOf(D.practice) === 0 ? lessonBtn : (pa ? dailyBtn : ''));
    }
    var meta = [];
    if(pa && pa.xp) meta.push('<b>' + pa.xp + '</b> XP');
    meta.push('<b>' + done + '</b> of ' + D.lessons.length + ' lessons read');
    if(pa && pa.m){
      meta.push('<b>' + pctM + '%</b> of the pathway mastered');
      meta.push(pct + '% explored');
    }
    if(resume){
      /* Druhe tlacitko = doporuceni atlasNext(), jen kdyz vede jinam nez
         "pokracuj" -- dva odkazy na tutez stranku by byly sum. */
      var alt = '';
      if(window.atlasNext){
        var st2 = window.atlasNext({lessons:D.lessons, pa:pa, practice:D.practice,
                                    check:(D.next && D.next.check) || 3, rankReady:false});
        if(st2.href.split('#')[0] !== resume.href.split('#')[0])
          alt = '<a class="ac-cta ac-quiet" href="' + st2.href + '">' + st2.title + ' &rarr;</a>';
      }
      first = '<a class="ac-cta" href="' + resume.href + '">' + resume.btn + '</a>' + alt;
    }
    box.innerHTML =
      '<p class="ac-rk">' + (resume ? 'Pick up where you left off' : 'Where you are') + '</p>' +
      (resume ? '<p class="ac-rbig">' + resume.title + '</p><p class="ac-rmeta ac-rwhere">' +
                resume.where + '</p>' : '') +
      (resume ? '' : '<p class="ac-rbig">' + (rank ? ('Rank ' + rank.n + ' &middot; ' + rank.name) : 'Reading the course') + '</p>') +
      '<p class="ac-rmeta">' + (resume && rank ? 'Rank ' + rank.n + ' &middot; ' : '') + meta.join(' &middot; ') + '</p>' +
      '<div class="ac-rbtns">' + first +
      (pa ? '<a class="ac-cta ac-quiet" href="' + D.progress + '">Your map &rarr;</a>' : '') +
      '</div>';
  }

  /* --- stavy na kartach --------------------------------------------------- */
  function setWay(id, state, cta, href){
    var w = document.querySelector('.ac-way[data-way="' + id + '"]'); if(!w) return;
    var st = w.querySelector('.ac-state'); if(st && state) st.innerHTML = state;
    var go = w.querySelector('.ac-go'); if(go && cta) go.innerHTML = cta;
    if(go && href) go.setAttribute('href', href);
  }
  if(done > 0 || resumeLesson){
    var cl = resumeLesson || next;
    setWay('learn', done + ' / ' + D.lessons.length + ' read<span class="ac-bar"><i style="width:' +
           Math.round(done / D.lessons.length * 100) + '%"></i></span>',
           'Continue lesson ' + cl.n + ' &rarr;', resumeLesson ? resume.href : next.url);
  }
  if(pa && (pa.xp || pa.m))
    setWay('practice', (rank ? 'Rank ' + rank.n + ' &middot; ' : '') + pctM +
           '% mastered <i>&middot; ' + pct + '% explored</i>' +
           '<span class="ac-bar"><u style="width:' + pct + '%"></u>' +
           '<i style="width:' + pctM + '%"></i></span>',
           'Play &rarr;');
  if(pa && pa.met && pa.met.discSeen && pa.met.discSeen.length)
    setWay('challenge', pa.met.discSeen.length + ' started <i>&middot; pick up where you stopped</i>');
})();