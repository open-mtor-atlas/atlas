#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
_inject_pathway2.py — dokončení zapojení Pathway & Mechanism 2.0.

CO SE POKAZILO A PROČ
Po prvním injectu byl nový modul nasazený, ale nikdo mu neřekl, aby se
otevřel. Staré chování bylo: "Entity Map" je výchozí a Mechanism Explorer
se zapíná ručně, takže showView('map') nikdy setPathwayMode() nevolal.
Když se výchozí režim překlopil na modul, zůstaly oba panely skryté —
sekce Pathway se otevřela prázdná. Chyba nalezena ověřením na živém webu,
ne v testu; smoke test testuje modul, ne shell, který ho hostí.

CO TO DĚLÁ
  1. showView('map') vždy inicializuje režim dráhy. Deep-link s ?entity=
     jde do Entity Browseru (protože o entitu si uživatel řekl),
     všechno ostatní do Pathway & Mechanism.
  2. Deep-link ?pw=explorer|guided|scenarios otevře modul přímo v daném
     režimu, aby se dalo odkazovat na konkrétní pohled.
"""
import io, os, sys

ROOT = os.path.dirname(os.path.abspath(__file__))
P = os.path.join(ROOT, "index.html")
# Marker je jen text uvnitř komentáře, ne uzavřený komentář — první verze
# hledala "/* PATHWAY-2.0-BOOTSTRAP */", což se v souboru nikdy neobjeví,
# takže kontrola po zápisu hlásila False u úspěšného injectu.
MARK = "PATHWAY-2.0-BOOTSTRAP"

OLD = """  currentView = which;
  setActiveTab(which);
}"""
NEW = """  currentView = which;
  setActiveTab(which);
  /* PATHWAY-2.0-BOOTSTRAP
     Sekce Pathway se musí sama rozhodnout, který panel zobrazí. Bez tohohle
     zůstanou po přepnutí výchozího režimu oba skryté. Deep-link na entitu
     má přednost — o entitu si uživatel výslovně řekl. */
  if(which === 'map'){
    var p = new URLSearchParams(location.hash.slice(1));
    var wantEntities = !!p.get('entity');
    setPathwayMode(wantEntities ? 'entities' : 'mechanism');
    var pw = p.get('pw');
    if(!wantEntities && pw){
      pwEnsure().then(function(){ window.PathwayApp.setMode(pw); })
                .catch(function(e){ console.error(e); });
    }
  }
}"""


def main():
    html = io.open(P, encoding="utf-8").read()
    n0 = len(html)
    if MARK in html:
        print("already injected"); return 0
    if OLD not in html:
        print("FAIL: showView tail not found verbatim"); return 1
    html = html.replace(OLD, NEW, 1)

    with io.open(P, "w", encoding="utf-8") as f:
        f.write(html); f.flush(); os.fsync(f.fileno())

    chk = io.open(P, encoding="utf-8").read()
    ok = MARK in chk and chk.rstrip().endswith("</html>") and 'id="pathwayHost"' in chk
    print("wrote index.html  %d -> %d chars — markers:%s" % (n0, len(chk), ok))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
