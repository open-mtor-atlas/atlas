(function(){
var bar=document.getElementById('acFcFilter'); if(!bar) return;
bar.hidden=false;
var btns=bar.querySelectorAll('button');
function set(lv){
  for(var i=0;i<btns.length;i++){btns[i].setAttribute('aria-pressed', btns[i].getAttribute('data-lv')===lv?'true':'false');}
  var cards=document.querySelectorAll('.ac-res');
  for(var j=0;j<cards.length;j++){var ls=' '+cards[j].getAttribute('data-level')+' ';
    cards[j].hidden = lv!=='all' && ls.indexOf(' '+lv+' ')<0;}
  var gs=document.querySelectorAll('.ac-fcgroup');
  for(var k=0;k<gs.length;k++){gs[k].hidden=!gs[k].querySelector('.ac-res:not([hidden])');}
}
for(var i=0;i<btns.length;i++){btns[i].addEventListener('click',function(){set(this.getAttribute('data-lv'));});}
})();