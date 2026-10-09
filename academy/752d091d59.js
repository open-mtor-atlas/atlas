/* Academy mini-quiz. Same rules as the progress switch above: no storage, no
   score kept anywhere, no network. Answering marks the option you picked and
   the right one, and reveals WHY -- which is the part worth reading. Without
   JS every question still works: the <details> fallback below each question
   carries the answer and the same explanation, so the page is never a dead
   list of options. */
(function(){
  var qs=document.querySelectorAll('.ac-qz');
  if(!qs.length) return;
  var total=qs.length, answered=0, right=0;
  var tally=document.getElementById('acQzTally');
  qs.forEach(function(qz){
    var fall=qz.querySelector('.ac-qzfall');
    if(fall) fall.hidden=true;               /* JS is on -> feedback is inline */
    var why=qz.querySelector('.ac-qzwhy');
    var correct=parseInt(qz.getAttribute('data-answer'),10);
    var opts=qz.querySelectorAll('.ac-qzopt');
    opts.forEach(function(b){
      b.addEventListener('click',function(){
        if(qz.hasAttribute('data-done')) return;
        qz.setAttribute('data-done','1');
        var picked=parseInt(b.getAttribute('data-i'),10);
        var ok=picked===correct;
        opts.forEach(function(o){
          var i=parseInt(o.getAttribute('data-i'),10);
          o.setAttribute('aria-disabled','true');
          if(i===correct) o.setAttribute('data-mark','right');
          else if(i===picked) o.setAttribute('data-mark','wrong');
        });
        var v=qz.querySelector('.ac-qzverdict');
        if(v) v.textContent=ok?'Correct':'Not this one';
        if(why){why.hidden=false;}
        answered++; if(ok) right++;
        if(tally&&answered===total){
          tally.textContent=right+' of '+total+' first time. Nothing here is recorded '+
            '— the explanations are the point.';
        }
      });
    });
  });
})();