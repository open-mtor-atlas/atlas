/* Research Challenges. Same contract as every other interactive block on this
   site: the page is complete without this script. Here it only (a) keeps the
   research budget, (b) reveals the written feedback for the option a reader
   picked instead of showing all of them at once, and (c) reports six events to
   the analytics that shell() already loads. No fetch, no storage, no score.

   Nothing scientific exists only in JS: every result, every note and every
   limitation is in the HTML above, which is why the no-JS view is the same
   page with more of it visible at once. */
(function(){
  var root=document.body.getAttribute('data-rc-challenge');
  if(!root) return;
  function track(name,extra){
    try{ if(typeof gtag==='function'){
      var p={challenge:root}; if(extra) for(var k in extra) p[k]=extra[k];
      gtag('event',name,p);
    } }catch(e){}
  }
  track('challenge_started');

  /* ---------- option groups with written feedback ---------- */
  document.querySelectorAll('[data-rc-notes]').forEach(function(box){
    var notes=box.querySelectorAll('[data-rc-note]');
    notes.forEach(function(p){p.hidden=true;});
    /* cely kontejner, ne jen odstavce: jinak zbyde 3px pahyl leveho ramecku */
    box.hidden=true;
    var group=box.previousElementSibling;
    if(!group||!group.querySelectorAll) return;
    var step=box.closest('[data-rc-step]');
    var kind=step?step.getAttribute('data-rc-step'):'';
    group.querySelectorAll('[data-rc-opt]').forEach(function(b){
      b.addEventListener('click',function(){
        var i=b.getAttribute('data-rc-opt');
        group.querySelectorAll('[data-rc-opt]').forEach(function(o){
          o.setAttribute('aria-pressed',String(o===b));
        });
        notes.forEach(function(p){p.hidden=p.getAttribute('data-rc-note')!==i;});
        box.hidden=false;
        var tag=b.textContent.trim().slice(0,60);
        if(kind==='hypothesis'){
          track('hypothesis_committed',{choice:tag});
          var c=step.querySelector('[data-rc-committed]');
          if(c){c.textContent='Committed. You can revise this later \u2014 that is the point.';c.hidden=false;}
        }
        else if(kind==='revise') track('hypothesis_revised',{choice:tag});
        else if(kind==='confounder') track('confounder_answered',{choice:tag});
        else if(kind==='experiments') track('experiment_interpreted',{choice:tag});
        else if(kind==='reflect') track('challenge_completed',{choice:tag});
      });
    });
  });

  /* ---------- break-the-model predictions ---------- */
  document.querySelectorAll('.ac-rcpd').forEach(function(pd){
    var fall=pd.querySelector('.ac-rcfall'); if(fall) fall.hidden=true;
    var after=pd.querySelectorAll('[data-ac-after]');
    after.forEach(function(x){x.hidden=true;});
    var correct=parseInt(pd.getAttribute('data-answer'),10);
    var opts=pd.querySelectorAll('.ac-qzopt');
    opts.forEach(function(b){
      b.addEventListener('click',function(){
        if(pd.hasAttribute('data-done')) return;
        pd.setAttribute('data-done','1');
        var picked=parseInt(b.getAttribute('data-i'),10);
        opts.forEach(function(o){
          var i=parseInt(o.getAttribute('data-i'),10);
          o.setAttribute('aria-disabled','true');
          if(i===correct) o.setAttribute('data-mark','right');
          else if(i===picked) o.setAttribute('data-mark','wrong');
        });
        var v=pd.querySelector('.ac-qzverdict');
        if(v) v.textContent=(picked===correct)?'That is what the model does':'Not what the model does';
        after.forEach(function(x){x.hidden=false;});
      });
    });
  });

  /* ---------- vyzkumna cesta (lab) ----------
     Stavovy automat, ne nakupni seznam. Drzi ctyri veci: kde stojis (`cursor`),
     co uz jsi spustil (`ran`), kolik zbyva a jestli je investigace uzavrena.

     SUNK COST je tu zamerne: navrat na drivejsi krok je jen presun kurzoru,
     kredity se NEVRACEJI. Proto se da vratit a vzit jinou vetev, ale ne to
     odestat -- presne jako ve skutecnem programu.

     Karty kroku existuji v HTML od zacatku (bez JS je to cely rozpis
     vyzkumu); tenhle skript je jen presouva mezi "kde jsi", "co to otevrelo"
     a "co je jeste otevrene". Nic vedeckeho nevznika az tady. */
  var bx=document.querySelector('[data-rc-budget]');
  if(!bx) return;
  var dEl=document.querySelector('script.ac-rcdata'), D=null;
  if(dEl){try{D=JSON.parse(dEl.textContent);}catch(e){}}
  if(!D) return;
  var step=bx.closest('[data-rc-step]');
  var pool=step.querySelector('[data-lab-pool]');
  var hereBox=step.querySelector('[data-lab-here]');
  var nextBox=step.querySelector('[data-lab-next]');
  var nextLbl=step.querySelector('[data-lab-nextlbl]');
  var nextHead=step.querySelector('[data-lab-nexthead]');
  var remainEl=step.querySelector('[data-lab-remain]');
  var openBox=step.querySelector('[data-lab-open]');
  var openInner=openBox?openBox.querySelector('div'):null;
  var pathBox=step.querySelector('[data-lab-path]');
  var btns=step.querySelector('[data-lab-btns]');
  var deb=step.querySelector('[data-rc-debrief]');
  var leftEl=bx.querySelector('[data-rc-left]'), fill=bx.querySelector('[data-rc-fill]');
  var countEl=step.querySelector('[data-lab-count]');
  var cards={};
  [].forEach.call(step.querySelectorAll('[data-rc-exp]'),function(c){
    cards[c.getAttribute('data-rc-exp')]=c;});
  [].forEach.call(step.querySelectorAll('.ac-rcfall'),function(f){f.hidden=true;});
  /* zasobnik karet: bez JS je to cely rozpis vyzkumu shora dolu, s JS z nej
     karty jen berem a schovavame ho -- jinak by pod volbou visely vsechny
     kroky naraz a nebylo by poznat, mezi cim se vybira */
  if(pool) pool.hidden=true;

  var total=D.total, left=total, cursor=null, ran=[], closed=false;

  function findings(){var f={};ran.forEach(function(id){
    (D.nodes[id].yields||[]).forEach(function(y){f[y]=1;});});return f;}
  function answered(){var f=findings();
    return D.goals.filter(function(g){
      return g.need.every(function(y){return f[y];});});}
  function unlocked(){var u={};D.start.forEach(function(i){u[i]=1;});
    ran.forEach(function(id){(D.nodes[id].next||[]).forEach(function(i){u[i]=1;});});
    return u;}
  function childrenOf(id){return id===null?D.start.slice():(D.nodes[id].next||[]).slice();}
  function isRun(id){return ran.indexOf(id)>=0;}

  function place(card,box){if(card&&box&&card.parentNode!==box) box.appendChild(card);}

  function paint(){
    if(leftEl) leftEl.textContent=String(left);
    if(fill) fill.style.width=(total?Math.max(0,left)/total*100:0)+'%';

    /* dilci otazky */
    var got={};answered().forEach(function(g){got[g.id]=1;});
    if(countEl) countEl.textContent=String(answered().length);
    [].forEach.call(step.querySelectorAll('[data-goal]'),function(li){
      var on=!!got[li.getAttribute('data-goal')];
      li.setAttribute('data-done',on?'1':'0');
      var t=li.querySelector('.ac-labtick'); if(t) t.textContent=on?'✓':'○';
    });

    /* kam co patri */
    var u=unlocked(), kids=childrenOf(cursor), inKids={};
    kids.forEach(function(i){inKids[i]=1;});
    Object.keys(cards).forEach(function(id){
      var box=pool;
      if(id===cursor) box=hereBox;
      else if(inKids[id]&&(u[id]||isRun(id))) box=nextBox;
      else if(u[id]&&!isRun(id)) box=openInner;
      place(cards[id],box);
      /* volba vs. vysledek: dokud krok jen zvazujes, vidis kompaktni kartu,
         kterou jde porovnat s tou vedle. Rozbali se, az na nem stojis. */
      cards[id].setAttribute('data-view',box===hereBox?'result':'choice');

      var c=cards[id], run=c.querySelector('.ac-rcrun'), back=c.querySelector('.ac-labback');
      var sp=c.querySelector('.ac-rcspent'), no=c.querySelector('.ac-rcdenied');
      var outs=c.querySelectorAll('[data-rc-out],[data-rc-event]');
      var done=isRun(id);
      [].forEach.call(outs,function(x){x.hidden=!done;});
      if(sp) sp.hidden=!done;
      c.setAttribute('data-rc-spent',done?'1':'0');
      var after=c.querySelector('[data-lab-after]');
      if(done){
        if(run) run.hidden=true;
        if(no) no.hidden=true;
        if(after) after.hidden=true;
        if(back) back.hidden=(id===cursor);
      }else{
        if(back) back.hidden=true;
        var ok=(D.nodes[id].cost<=left)&&!closed;
        if(run){run.hidden=closed;run.disabled=!ok;run.setAttribute('aria-disabled',String(!ok));}
        if(no) no.hidden=ok||closed;
        /* co ti po tomhle kroku zbyde -- pri porovnavani dvou moznosti je to
           uzitecnejsi cislo nez jejich cena */
        if(after){
          after.hidden=!ok;
          after.textContent='leaves '+(left-D.nodes[id].cost);
        }
      }
    });

    /* nadpis nad moznostmi */
    var runnable=kids.length>0;
    if(remainEl) remainEl.textContent=String(left);
    if(nextHead) nextHead.hidden=closed||!runnable;
    if(nextLbl){
      nextLbl.textContent=((cursor===null)?'Where to start':'What this step opened up')+
                          (kids.length>1?' – pick one':'');
    }
    if(nextBox) nextBox.hidden=closed;
    if(openBox){
      var others=Object.keys(cards).filter(function(id){
        return u[id]&&!isRun(id)&&!inKids[id];});
      openBox.hidden=closed||!others.length;
      var sm=openBox.querySelector('summary');
      if(sm) sm.textContent=others.length+' other step'+(others.length===1?'':'s')+
        ' already open to you';
    }
    if(cursor!==null&&!runnable&&!closed&&nextLbl){
      if(nextHead) nextHead.hidden=false;
      nextLbl.textContent='This line is finished – go back to an earlier step to take another branch.';
    }

    /* trasa */
    if(pathBox){
      var ol=pathBox.querySelector('ol');
      var h='<li'+(cursor===null?' data-here="1"':'')+
            '><button type="button" data-lab-goto="__start__">The question</button></li>';
      ran.forEach(function(id){
        h+='<li'+(cursor===id?' data-here="1"':'')+'><button type="button" data-lab-goto="'+
           id+'">'+D.nodes[id].label+' <span>'+D.nodes[id].cost+'</span></button></li>';
      });
      if(ol) ol.innerHTML=h;
      pathBox.hidden=false;
    }
    if(btns) btns.hidden=false;
  }

  function goto_(id){
    cursor=(id==='__start__')?null:id;
    paint();
    var box=(cursor===null)?nextBox:hereBox;
    if(box&&box.scrollIntoView) box.scrollIntoView({block:'nearest'});
  }

  /* Practice Arena, odznak Falsifier: kdyz PRVNI zaplaceny experiment v teto
     vyzve umi rozhodnout mezi hypotezami (discriminates >= 2), zapise se to do
     stejneho uloziste jako zbytek herni vrstvy. Kazda vyzva se pocita jednou a
     jen kdyz uz nejaky postup existuje -- z teto stranky se stav nezaklada. */
  function paFalsifier(id){
    try{
      var nd=D.nodes[id]; if(!nd || (nd.disc||0) < 2) return;
      var KEY='atlas-practice-v1', st=JSON.parse(localStorage.getItem(KEY)||'null');
      if(!st || !st.met) return;
      st.met.discSeen = st.met.discSeen || [];
      if(st.met.discSeen.indexOf(location.pathname) >= 0) return;
      st.met.discSeen.push(location.pathname);
      st.met.discriminating = (st.met.discriminating || 0) + 1;
      localStorage.setItem(KEY, JSON.stringify(st));
    }catch(err){}
  }

  function run(id){
    if(closed||isRun(id)) return;
    var n=D.nodes[id];
    if(n.cost>left) return;
    var u=unlocked(); if(!u[id]) return;
    left-=n.cost; ran.push(id); cursor=id;
    if(ran.length===1) paFalsifier(id);
    paint();
    track('experiment_run',{experiment:id,cost:n.cost,remaining:left,
                            answers:answered().length});
  }

  step.addEventListener('click',function(ev){
    var t=ev.target.closest?ev.target.closest('button'):null;
    if(!t) return;
    if(t.classList.contains('ac-rcrun')){
      var c=t.closest('[data-rc-exp]'); if(c) run(c.getAttribute('data-rc-exp'));
    }else if(t.classList.contains('ac-labback')){
      var c2=t.closest('[data-rc-exp]'); if(c2) goto_(c2.getAttribute('data-rc-exp'));
    }else if(t.hasAttribute('data-lab-goto')){
      goto_(t.getAttribute('data-lab-goto'));
    }
  });

  function uniq(a){var s={},o=[];a.forEach(function(t){if(!s[t]){s[t]=1;o.push(t);}});return o;}
  function names(ids){return ids.map(function(i){return D.nodes[i].label;}).join(' → ');}

  function debrief(){
    var got=answered(), n=got.length, spent=total-left, tot=D.goals.length;
    var h='<h3 tabindex="-1">What your investigation bought</h3>';
    h+='<p class="ac-rcshort">You answered <strong>'+n+'</strong> of '+tot+
       ' sub-questions, and spent <strong>'+spent+'</strong> of '+total+' '+D.unit+'.</p>';
    var ch=D.cheapest[String(n)];
    if(n&&ch){
      h+='<p>The cheapest route to '+n+(n===1?' answer':' answers')+' is <strong>'+ch.cost+
         '</strong> '+D.unit+': '+names(ch.route)+'.'+
         (spent>ch.cost?' You spent '+(spent-ch.cost)+' more than that.':
          (spent===ch.cost?' That is exactly what you spent – you took the shortest way there.':''))+
         '</p>';
    }
    if(n<D.best.goals){
      h+='<p>This budget allows up to <strong>'+D.best.goals+'</strong> answers, for '+
         D.best.cost+' '+D.unit+': '+names(D.best.route)+'.</p>';
    }else if(n===D.best.goals){
      h+='<p>That is the most this budget allows. Everything beyond it costs more than the '+
         'budget holds, which is the ordinary condition of research rather than a failure.</p>';
    }
    var unb=D.goals.filter(function(g){return D.unbuyable.indexOf(g.id)>=0;});
    if(unb.length){
      h+='<p class="ac-showslbl">What no amount of budget would have bought</p><ul class="ac-shows">'+
         unb.map(function(g){return '<li class="ac-no">'+g.q+'</li>';}).join('')+'</ul>';
    }
    var hit=D.rules.filter(function(r){
      return r.ran.every(function(i){return ran.indexOf(i)>=0;}) &&
             r['not'].every(function(i){return ran.indexOf(i)<0;});
    }).slice(0,4);
    if(hit.length) h+='<ul class="ac-rcrules">'+
      hit.map(function(r){return '<li>'+r.note+'</li>';}).join('')+'</ul>';
    var sup=[],non=[];
    ran.forEach(function(id){sup=sup.concat(D.nodes[id].conclude);
                             non=non.concat(D.nodes[id].cannot);});
    if(sup.length) h+='<p class="ac-showslbl">What your route supports</p><ul class="ac-shows">'+
      uniq(sup).map(function(t){return '<li class="ac-yes">'+t+'</li>';}).join('')+'</ul>';
    if(non.length) h+='<p class="ac-showslbl">What it still leaves open</p><ul class="ac-shows">'+
      uniq(non).map(function(t){return '<li class="ac-no">'+t+'</li>';}).join('')+'</ul>';
    var skipped=Object.keys(D.nodes).filter(function(id){return ran.indexOf(id)<0;});
    if(skipped.length) h+='<p class="ac-showslbl">The steps you did not take</p><ul class="ac-rcskip">'+
      skipped.map(function(id){var x=D.nodes[id];
        return '<li><span class="ac-rcskipn">'+x.label+'</span><span class="ac-rcskipc">'+
               x.cost+' '+D.unit+'</span><span class="ac-rcskipa">'+x.addresses+'</span></li>';
      }).join('')+'</ul>';
    deb.innerHTML=h; deb.hidden=false;
    var hh=deb.querySelector('h3'); if(hh&&hh.focus) hh.focus();
  }

  var closeBtn=step.querySelector('[data-rc-close]');
  if(closeBtn) closeBtn.addEventListener('click',function(){
    closed=true; closeBtn.disabled=true;
    if(pathBox) pathBox.hidden=true;
    paint(); debrief();
    track('investigation_closed',{spent:total-left,steps:ran.length,
                                  answers:answered().length});
  });
  var rb=step.querySelector('[data-rc-reset]');
  if(rb) rb.addEventListener('click',function(){
    left=total; ran=[]; cursor=null; closed=false;
    if(closeBtn) closeBtn.disabled=false;
    if(deb){deb.hidden=true;deb.innerHTML='';}
    paint();
  });
  paint();
})();