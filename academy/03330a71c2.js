/* Academy progress. One localStorage key, same defensive pattern as the SPA's
   atlas-theme / atlas-level switches: every read and write is wrapped, and the
   page renders correctly when storage is unavailable or empty. No accounts, no
   XP, no streaks -- a tick next to what you have read (spec §2, §18). */
(function(){
  var KEY='atlas-academy-progress';
  function read(){try{return JSON.parse(localStorage.getItem(KEY)||'{}')||{};}catch(e){return {};}}
  function save(o){try{localStorage.setItem(KEY,JSON.stringify(o));}catch(e){}}
  var p=read();
  document.querySelectorAll('[data-ac-lesson]').forEach(function(el){
    if(p[el.getAttribute('data-ac-lesson')]==='done'){
      var g=el.querySelector('.ac-state'); if(g){g.textContent='\u2713';g.setAttribute('data-done','1');}
    }
  });
  var here=document.body.getAttribute('data-ac-current');
  var btn=document.getElementById('acDone');
  if(here&&btn){
    function paint(){
      var d=read()[here]==='done';
      btn.textContent=d?'\u2713 Marked as read':'Mark as read';
      btn.setAttribute('aria-pressed',String(d));
    }
    btn.addEventListener('click',function(){
      var o=read(); if(o[here]==='done'){delete o[here];}else{o[here]='done';} save(o); paint();
    });
    paint();
  }
})();