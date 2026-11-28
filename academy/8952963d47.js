(function(){
  var KEY='atlas-academy-last', b=document.body, rec=null;
  var les=b.getAttribute('data-ac-current'), ch=b.getAttribute('data-rc-challenge');
  var h1=document.querySelector('h1'), t=h1?h1.textContent.trim().slice(0,140):'';
  if(les) rec={k:'lesson',slug:les,url:location.pathname,t:t};
  else if(ch) rec={k:'challenge',slug:ch,url:location.pathname,t:t};
  if(!rec) return;
  function save(){ rec.ts=Date.now(); try{localStorage.setItem(KEY,JSON.stringify(rec));}catch(e){} }
  save();
  if(rec.k!=='lesson') return;
  var hs=[].slice.call(document.querySelectorAll('h2[id]')).filter(function(h){
    return !h.classList.contains('ac-vh') && !h.closest('header,footer,nav');
  });
  if(!hs.length) return;
  var timer=null;
  function mark(){
    timer=null;
    var lim=window.innerHeight*0.35, cur=null;
    for(var i=0;i<hs.length;i++){ if(hs[i].getBoundingClientRect().top<lim) cur=hs[i]; else break; }
    var id=cur?cur.id:'', st=cur?cur.textContent.trim().slice(0,80):'';
    if(id===(rec.sec||'')) return;
    if(id){ rec.sec=id; rec.st=st; } else { delete rec.sec; delete rec.st; }
    save();
  }
  window.addEventListener('scroll',function(){ if(!timer) timer=setTimeout(mark,500); },{passive:true});
})();