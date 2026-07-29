#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
_inject_pathway.py — zapojí Pathway & Mechanism 2.0 do index.html.

Proč skript a ne ruční editace: index.html má 1,5 MB na několika extrémně
dlouhých řádcích. Editační nástroje na něm utínají konec souboru. Každá
změna tady projde jedním skriptem, který si na konci sám ověří, že se
zapsalo všechno (kontrola délky + přítomnost markerů) a fsyncne.

Idempotentní: druhé spuštění nic nerozbije, jen ohlásí "already injected".
"""
import os, re, sys, io

ROOT = os.path.dirname(os.path.abspath(__file__))
P = os.path.join(ROOT, "index.html")
MARK = "<!-- PATHWAY-2.0 -->"

OLD_SUBTAB = '''    <div class="subtab-bar">
      <button class="subtab-btn active" id="btnPwEntities" onclick="setPathwayMode('entities')" type="button">Entity Map</button>
      <button class="subtab-btn" id="btnPwMechanism" onclick="setPathwayMode('mechanism')" type="button">Mechanism Explorer</button>
    </div>'''

NEW_SUBTAB = MARK + '''
    <div class="subtab-bar">
      <button class="subtab-btn active" id="btnPwMechanism" onclick="setPathwayMode('mechanism')" type="button">Pathway &amp; Mechanism</button>
      <button class="subtab-btn" id="btnPwEntities" onclick="setPathwayMode('entities')" type="button">Entity Browser</button>
    </div>'''

# Retiruje se přepínač na "Full Pathway Map". Ta mapa kreslila přerušovanou
# čarou "linked via shared-study evidence" — tedy CO-CITACI, ne mechanismus,
# a to stejným vizuálním jazykem jako skutečné biologické hrany. Přesně ta
# tichá nepřesnost, kterou má redesign odstranit. Mechanismus je teď v
# Mechanism Exploreru, kde má hrana typ, kompartment a citace.
OLD_MAPTOGGLE = '''            <div class="map-toggle">
              <button class="map-toggle-btn" id="btnFocusMap" onclick="setMapMode('focus')" type="button">Focused</button>
              <button class="map-toggle-btn active" id="btnFullMap" onclick="setMapMode('full')" type="button">Full Pathway Map</button>
            </div>'''
NEW_MAPTOGGLE = '''            <span class="hint" style="font-size:10px;">shared-study links only — for mechanism, see Pathway &amp; Mechanism</span>'''


def main():
    html = io.open(P, encoding="utf-8").read()
    n0 = len(html)
    if MARK in html:
        print("already injected — nothing to do")
        return 0

    # 1. subtab bar ---------------------------------------------------------
    if OLD_SUBTAB not in html:
        print("FAIL: subtab bar not found verbatim"); return 1
    html = html.replace(OLD_SUBTAB, NEW_SUBTAB, 1)

    # 2. retire the co-citation full map toggle -----------------------------
    if OLD_MAPTOGGLE in html:
        html = html.replace(OLD_MAPTOGGLE, NEW_MAPTOGGLE, 1)
    else:
        print("warn: map toggle not found (already removed?)")

    # 3. replace the whole old mechanismView block with the module host ----
    i = html.find('<div id="mechanismView" style="display:none;">')
    if i < 0:
        print("FAIL: mechanismView not found"); return 1
    j = html.find('<div id="studiesView" style="display:none;">', i)
    if j < 0:
        print("FAIL: studiesView anchor not found"); return 1
    tail = html[i:j]
    # zachovat uzavírací </div> sekce Pathway, které stály za mechanismView
    closers = tail.rstrip()[-len("</div>\n  </div>"):]
    host = ('<div id="mechanismView" style="display:none;">\n'
            '      <div id="pathwayHost">\n'
            '        <noscript><p style="padding:18px 0;">The Pathway &amp; Mechanism explorer needs JavaScript. '
            'Every study and entity in the Atlas is also available as a plain HTML page — see the sitemap.</p></noscript>\n'
            '      </div>\n'
            '    </div>\n'
            '  </div>\n\n  ')
    html = html[:i] + host + html[j:]

    # 4. pathway mode switch + lazy loader ---------------------------------
    OLD_FN = html.find("function setPathwayMode(mode){")
    if OLD_FN < 0:
        print("FAIL: setPathwayMode not found"); return 1
    end = html.find("\n}", OLD_FN)
    new_fn = '''function pwLoadAsset(tag, attrs){
  return new Promise(function(res, rej){
    var e = document.createElement(tag);
    Object.keys(attrs).forEach(function(k){ e.setAttribute(k, attrs[k]); });
    e.onload = res; e.onerror = function(){ rej(new Error("failed to load " + (attrs.src||attrs.href))); };
    document.head.appendChild(e);
  });
}
/* Pathway & Mechanism 2.0 se stahuje teprve při prvním otevření tabu.
   Model má ~150 kB a modul ~40 kB; drží se to mimo first paint, což je
   celý důvod, proč sekce už nežije v index.html. */
var pwLoading = null;
function pwEnsure(){
  if(pwLoading) return pwLoading;
  var host = document.getElementById("pathwayHost");
  host.innerHTML = '<p class="mono" style="padding:26px 0;color:var(--ink-soft);font-size:12px;">'
    + 'loading pathway model\\u2026</p>';
  pwLoading = pwLoadAsset("link", {rel:"stylesheet", href:"pathway/pathway.css"})
    .then(function(){ return pwLoadAsset("script", {src:"pathway/pathway.js", defer:"defer"}); })
    .then(function(){ return window.PathwayApp.boot(host, "pathway/model.json"); })
    .catch(function(err){ pwLoading = null; throw err; });
  return pwLoading;
}
function setPathwayMode(mode){
  var ent  = document.getElementById("pwEntitiesPane");
  var mech = document.getElementById("mechanismView");
  var bE = document.getElementById("btnPwEntities");
  var bM = document.getElementById("btnPwMechanism");
  var showMech = (mode !== "entities");
  if(ent)  ent.style.display  = showMech ? "none" : "";
  if(mech) mech.style.display = showMech ? "" : "none";
  if(bE) bE.classList.toggle("active", !showMech);
  if(bM) bM.classList.toggle("active", showMech);
  if(showMech) pwEnsure().catch(function(e){ console.error(e); });
}'''
    html = html[:OLD_FN] + new_fn + html[end + 2:]

    # 5. neutralise the old explorer's boot call ---------------------------
    #    renderMechanism()/mxSetRoute() jsou nadále mrtvý kód. Nemažou se
    #    v témže releasu záměrně: ATLAS_EDGES je migrační zdroj pro
    #    model.json a chceme jeden release, kde se dá obojí porovnat.
    html = re.sub(r"(\brenderMechanism\s*\(\s*\)\s*;)",
                  r"/* deprecated by Pathway 2.0 — see build_pathway_model.py: \1 */", html)

    # 6. default the entity map to the focused graph -----------------------
    html = html.replace("state.mapMode = 'full'", "state.mapMode = 'focus'")
    html = html.replace('state.mapMode = "full"', 'state.mapMode = "focus"')

    with io.open(P, "w", encoding="utf-8") as f:
        f.write(html)
        f.flush(); os.fsync(f.fileno())

    check = io.open(P, encoding="utf-8").read()
    ok = (MARK in check and 'id="pathwayHost"' in check and "function pwEnsure()" in check
          and check.rstrip().endswith("</html>"))
    print("wrote index.html  %d -> %d chars" % (n0, len(check)))
    print("markers present:", ok)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
