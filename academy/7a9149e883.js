/* Interaktivni cviceni (Faze 2). Stejny kontrakt jako kviz vys: stranka je
   uplna i bez tohohle skriptu. JS tady jen (a) prepina stav vyukoveho modelu,
   (b) sekvencuje Predict -> Observe -> Explain a (c) po odeslani navrhu
   experimentu ukaze jen relevantni zpetnou vazbu. Vsechny tri veci maji
   v HTML <details> ekvivalent, ktery se tady schova prave proto, ze uz je
   nahrazeny necim lepsim. Zadny fetch, zadne localStorage, zadne skore. */
(function(){
  /* ---------- interaktivni model ---------- */
  document.querySelectorAll('.ac-model').forEach(function(md){
    var dataEl=md.querySelector('script.ac-mddata'); if(!dataEl) return;
    var D; try{D=JSON.parse(dataEl.textContent);}catch(e){return;}
    var fall=md.querySelector('.ac-mdfall'); if(fall) fall.hidden=true;
    var pick={}, order=D.order||[];
    order.forEach(function(c){pick[c]=D.start[c];});
    var out=md.querySelector('.ac-mdreadout'), note=md.querySelector('.ac-mdnote');
    function key(){return order.map(function(c){return pick[c];}).join('|');}
    function paint(){
      var st=D.states[key()];
      md.querySelectorAll('.ac-mdbtns button').forEach(function(b){
        b.setAttribute('aria-pressed',String(pick[b.dataset.ctl]===b.dataset.val));
      });
      if(!st) return;
      var on={}; (st.flow||[]).forEach(function(n){on[n]=1;});
      md.querySelectorAll('.ac-mdnode').forEach(function(n){
        n.setAttribute('data-flow', on[n.dataset.node]?'on':'off');
      });
      var cut={}; (st.cut||[]).forEach(function(e){cut[e]=1;});
      md.querySelectorAll('.ac-mdedge').forEach(function(e){
        e.setAttribute('data-flow', cut[e.dataset.edge]?'off':'on');
      });
      if(out) out.textContent=st.readout||'';
      if(note) note.innerHTML=st.note||'';
    }
    md.querySelectorAll('.ac-mdbtns button').forEach(function(b){
      b.addEventListener('click',function(){pick[b.dataset.ctl]=b.dataset.val;paint();});
    });
    var rst=md.querySelector('.ac-mdreset');
    if(rst) rst.addEventListener('click',function(){
      order.forEach(function(c){pick[c]=D.start[c];}); paint();
    });
    /* uzel -> zvyrazni jeho radek v legende (legenda je vzdy videt, nic se
       neschovava -- zvyrazneni je navigace, ne odhaleni) */
    /* Pozor: uzel je SVG <g>, ktere NEMA .click() -- volat ho z klavesnice
       tise spadne (stejna past uz jednou byla v Entity Browseru). Proto je
       zvyrazneni funkce a klavesnice i mys volaji ji, ne se navzajem. */
    function highlight(id){
      md.querySelectorAll('.ac-mdkey div').forEach(function(r){
        r.setAttribute('data-hi', r.dataset.node===id?'1':'0');
      });
    }
    md.querySelectorAll('.ac-mdnode').forEach(function(n){
      n.addEventListener('click',function(){highlight(n.dataset.node);});
      n.addEventListener('keydown',function(ev){
        if(ev.key==='Enter'||ev.key===' '){ev.preventDefault();highlight(n.dataset.node);}
      });
    });
    paint();
  });

  /* ---------- Predict -> Observe -> Explain ---------- */
  document.querySelectorAll('.ac-pd').forEach(function(pd){
    var fall=pd.querySelector('.ac-pdfall'); if(fall) fall.hidden=true;
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
        if(v) v.textContent=(picked===correct)?'That is the expected result':'Not the expected result';
        after.forEach(function(x){x.hidden=false;});
      });
    });
  });

  /* ---------- experiment builder ---------- */
  document.querySelectorAll('.ac-design').forEach(function(ds){
    var fall=ds.querySelector('.ac-dsfall'); if(fall) fall.hidden=true;
    var box=ds.querySelector('.ac-dsfb'); if(box) box.hidden=true;
    var btn=ds.querySelector('.ac-dssubmit');
    if(!btn||!box) return;
    var notes; try{notes=JSON.parse(ds.querySelector('script.ac-dsdata').textContent);}
    catch(e){return;}
    btn.addEventListener('click',function(){
      var chosen=[];
      ds.querySelectorAll('input[type=radio]:checked').forEach(function(r){
        chosen.push([r.name,r.value]);
      });
      if(!chosen.length) return;
      var html='';
      chosen.forEach(function(p){
        var t=notes[p[0]]&&notes[p[0]][p[1]];
        if(t) html+='<p><strong>'+p[1]+'.</strong> '+t+'</p>';
      });
      box.querySelector('.ac-dsout').innerHTML=html;
      box.hidden=false;
      box.querySelector('h4').focus&&box.querySelector('h4').focus();
    });
  });
})();