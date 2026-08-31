#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
chrome_shared.py -- jediný zdroj markupu patičky (a bezpečnostní kontrola
drobečků) sdílený mezi build_pages.py (shell(), patch_home()) a generate.py
(page()/hub_page()/glossary_page()). Fáze 2, §5.1 plánu typografické
unifikace (claude/typography-unification-plan-2026-08-31.md).

PROČ TOHLE EXISTUJE
Patička žila donedávna ve 4 nezávislých kopiích (shell() + 3x v generate.py)
a pátá (SPA, přes patch_home() v build_pages.py) měla vlastní, jinak
formátovaný duplikát téhož obsahu. Přidat/odebrat odkaz znamenalo upravit
všechny kopie zvlášť -- a přesně tohle se opakovaně stalo: Search Surface
Audit 2026-08-22 našel, že generate.py mělo jen 5 ze 7 odkazů (chybělo
About + Data); GitHub-link removal 2026-08-31 muselo editovat 6 míst zvlášť.

Tenhle modul dává OBSAHU (které odkazy, jaký text) jedno místo. Jednotlivé
generátory si dál volí FORMÁT -- SPA injektáž (patch_home) má jiný markup
(&middot; separátor, style="color:inherit", "n pages" vsuvka za odkazem
Browse) než statický `.oma-footer` (shell(), generate.py) -- ale obsah už
nemůže mezi nimi nezávisle zaostat, protože ho obojí čte ze stejného
FOOTER_LINKS.
"""

# Sedm odkazů v patičce, ve fixním pořadí. Přidat/odebrat odkaz znamená
# upravit TOHLE, ne pět různých f-stringů roztroušených po dvou souborech.
FOOTER_LINKS = [
    ("Full interactive Atlas", "/"),
    ("Browse the Atlas", "/browse/"),
    ("Academy", "/academy/"),
    ("Answers", "/answers/"),
    ("Glossary", "/glossary/"),
    ("About & Methodology", "/about/"),
    ("Data & Citation", "/data/"),
]


def _static_footer_links_html(site):
    """Odkazová řádka pro `.oma-footer-links` (shell() i generate.py).
    Jediný label s '&' (About & Methodology) potřebuje &amp; v HTML výstupu,
    stejně jako předtím v obou ručně psaných verzích."""
    out = []
    for label, href in FOOTER_LINKS:
        vis = label.replace("&", "&amp;") if "&" in label else label
        out.append(f'<a href="{site}{href}">{vis}</a>')
    return " · ".join(out)


def static_footer_html(site, build_timestamp):
    """Celý <footer class="oma-footer">...</footer> blok -- stejný pro
    shell() (build_pages.py) i pro page()/hub_page()/glossary_page()
    (generate.py). Mění se jen `site` (typicky {SITE} f-string vs. literál
    "https://mtor-atlas.org" -- dnes vždy stejná hodnota) a `build_timestamp`."""
    links = _static_footer_links_html(site)
    return (
        '<footer class="oma-footer">\n'
        "<p><strong>Oliver's mTOR Atlas</strong> — an evidence-graded database of the mTOR\n"
        "pathway. Every entry traces to a primary paper, graded A–D by strength of evidence.\n"
        "Curated by Oliver Barton, Prague.</p>\n"
        f'<div class="oma-footer-links">\n{links}\n</div>\n'
        f'<div class="oma-footer-meta">Oliver&#39;s mTOR Atlas &middot; last updated '
        f'{build_timestamp}</div>\n</footer>'
    )


def spa_footer_link_html(n_pages):
    """SPA verze (injektovaná přes patch_home() v build_pages.py mezi
    značky HOME_MARKER/HOME_END) -- jiný markup (&middot; separátor,
    style="color:inherit", "n pages" vsuvka hned za odkazem Browse), ale
    odkazy a popisky ze stejného FOOTER_LINKS jako static_footer_html()."""
    segs = []
    for label, href in FOOTER_LINKS:
        vis = label.replace("&", "&amp;") if "&" in label else label
        seg = f'<a href="{href}" style="color:inherit">{vis}</a>'
        if href == "/browse/":
            seg += f' <span class="mono" style="opacity:.65">{n_pages} pages</span>'
        segs.append(seg)
    return " &middot; ".join(segs)


def assert_crumb_matches_ld(crumb_html, ld, context=""):
    """Bezpečnostní síť z §11.3 plánu: viditelný text drobečku se MUSÍ
    rovnat `name` polím v BreadcrumbList JSON-LD, jinak build spadne.
    Google penalizuje schéma, které neodpovídá viditelnému textu -- a se
    sdíleným chrome markupem je snazší, aby se to nepozorovaně rozjelo.

    Porovnává jen ČISTÝ TEXT (tagy pryč, entity rozbalené), ne HTML bajty --
    různé generátory escapují jinak (SPA nechává apostrof syrový,
    build_pages.py entity escapuje přes e()), a to je v pořádku, pokud
    html.escape/html.unescape jsou vzájemně inverzní (jsou)."""
    import re as _re
    import html as _html
    if not isinstance(ld, dict) or ld.get("@type") != "BreadcrumbList":
        return  # volající předal jiný typ JSON-LD -- nic ke kontrole
    visible = _html.unescape(_re.sub(r"<[^>]+>", "", crumb_html)).strip()
    visible_parts = [p.strip() for p in visible.split("·") if p.strip()]
    ld_names = [item["name"] for item in ld.get("itemListElement", [])]
    if visible_parts != ld_names:
        raise AssertionError(
            f"Drobeček != BreadcrumbList JSON-LD ({context}): "
            f"viditelné {visible_parts!r} != JSON-LD {ld_names!r}"
        )


# ---------------------------------------------------------------------------
# Level switch (Beginner/Student/Research) -- Fáze 2b, §5.5 plánu
# typografické unifikace. Stejný mechanismus jako patička/drobečky výš:
# jeden zdroj (tady: model.json + tenhle modul), volající stránky si řeknou
# jen o výstup.
#
# Návrh (viz §5.5): Student je KANONICKÁ, výchozí úroveň -- viditelná i bez
# JS a beze změny `data-level` atributu na <html>. To je záměrně shodné
# s tím, co stránka zobrazovala PŘED zavedením přepínače, takže žádná
# stránka bez level_switch=True se ani o pixel nezmění a stránky
# S přepínačem se ve výchozím (student) stavu taky nezmění -- jen přibude
# widget a možnost přepnout.
#
# Dva nezávislé mechanismy, obě řízené stejným `data-level` atributem:
#   .lv-beginner / .lv-student / .lv-research
#       tři alternativní verze TÉHOŽ obsahu (entity stránky: krátký
#       plain-language popis vs. dnešní kurátorský popis vs. technická
#       poznámka z model.json). Bez JS/na studentu vidět jen .lv-student.
#   .lv-hide-beginner
#       jeden blok obsahu, který beginner úroveň schová (question stránky:
#       technická poznámka; study stránky: Abstract + Extracted findings).
#       Bez JS/na studentu i na researchi viditelné -- výchozí chování se
#       tímhle NEMĚNÍ, jen beginner dostane kratší stránku.
# ---------------------------------------------------------------------------

import json as _json
import os as _os

_MODEL_PATH = _os.path.join(_os.path.dirname(__file__), "pathway", "model.json")
_explain_cache = None

# Entity v Atlasu se jmenují jinak než uzly v pathway/model.json jen ve
# čtyřech případech (ověřeno 2026-08-31 skriptem, který spároval 45
# entit-se-stránkou proti 88 uzlům modelu jménem case-insensitive): tři
# entity (p62/SQSTM1, Alzheimer's disease, Resveratrol) v modelu vůbec
# nemají uzel -- pro ty žádný mapping není a přepínač se na jejich
# stránkách nezobrazí (nic k přepínání). Jen "Caloric restriction" má
# v modelu uzel pod jiným jménem.
ENTITY_NAME_TO_NODE_ID = {
    "Caloric restriction": "Fasting / caloric restriction",
}


def _load_explain():
    global _explain_cache
    if _explain_cache is not None:
        return _explain_cache
    try:
        with open(_MODEL_PATH, encoding="utf-8") as f:
            model = _json.load(f)
        _explain_cache = {n["id"]: n.get("explain") for n in model.get("nodes", [])
                          if n.get("explain")}
    except (OSError, ValueError):
        _explain_cache = {}
    return _explain_cache


def entity_explain_for(name):
    """Vrátí {"beginner":..,"student":..,"research":..} pro entitu podle
    jejího jména v Atlasu, nebo None, když pathway/model.json pro ni nemá
    uzel (žádný přepínač na té stránce -- nic k přepnutí)."""
    explain = _load_explain()
    node_id = ENTITY_NAME_TO_NODE_ID.get(name, name)
    exact = explain.get(node_id)
    if exact:
        return exact
    lower = node_id.lower()
    for nid, exp in explain.items():
        if nid.lower() == lower:
            return exp
    return None


LEVEL_SWITCH_CSS = """
.lvsw{display:flex;align-items:center;gap:10px;margin:0 0 18px;
  font-family:'IBM Plex Mono',monospace;flex-wrap:wrap}
.lvsw-label{font-size:11px;letter-spacing:.08em;text-transform:uppercase;color:var(--soft)}
.lvsw-btns{display:flex;border:1px solid var(--line)}
.lvsw-btns button{font-family:inherit;font-size:11px;letter-spacing:.05em;
  text-transform:uppercase;background:none;border:none;border-right:1px solid var(--line);
  padding:6px 11px;cursor:pointer;color:var(--soft)}
.lvsw-btns button:last-child{border-right:none}
.lvsw-btns button:hover{color:var(--teal)}
.lvsw-btns button[aria-pressed="true"]{background:var(--ink);color:var(--on-ink,#fff);font-weight:600}
.lv-beginner,.lv-research{display:none}
[data-level="beginner"] .lv-beginner{display:block}
[data-level="beginner"] .lv-student{display:none}
[data-level="research"] .lv-research{display:block}
[data-level="research"] .lv-student{display:none}
[data-level="beginner"] .lv-hide-beginner{display:none}
@media (max-width:768px){
  .lvsw-btns button{min-height:44px;padding:0 12px;}
}
"""


def level_switch_html():
    """Widget + skript. Vkládá se hned za drobeček, jen na stránkách, které
    volají shell(level_switch=True). Bez JS / na studentu se nezmění vůbec
    nic -- data-level atribut na <html> se nastaví jen tehdy, když si
    čtenář zvolí jinou úroveň (a persistuje přes localStorage['atlas-level'],
    stejný klíč jako SPA)."""
    return (
        '<div class="lvsw" role="group" aria-label="Reading level">'
        '<span class="lvsw-label">Reading level</span>'
        '<div class="lvsw-btns" id="lvsw">'
        '<button type="button" data-lv="beginner">Beginner</button>'
        '<button type="button" data-lv="student" aria-pressed="true">Student</button>'
        '<button type="button" data-lv="research">Research</button>'
        '</div></div>'
        '<script>(function(){'
        "var KEY='atlas-level',LEVELS=['beginner','student','research'];"
        "function saved(){try{var v=localStorage.getItem(KEY);"
        "return LEVELS.indexOf(v)>-1?v:'student';}catch(e){return 'student';}}"
        "function apply(l){"
        "if(l==='student')document.documentElement.removeAttribute('data-level');"
        "else document.documentElement.setAttribute('data-level',l);"
        "document.querySelectorAll('#lvsw button').forEach(function(b){"
        "b.setAttribute('aria-pressed',String(b.dataset.lv===l));});}"
        "var lv=saved();apply(lv);"
        "document.querySelectorAll('#lvsw button').forEach(function(b){"
        "b.addEventListener('click',function(){lv=b.dataset.lv;"
        "try{localStorage.setItem(KEY,lv);}catch(e){}apply(lv);});});"
        '})();</script>'
    )


# ---------------------------------------------------------------------------
# Mode toggle (dark/light) -- Faze 6, S7 planu typograficke unifikace.
# Univerzalni na rozdil od LEVEL: kazda stranka ma viditelnou barvu, takze
# na rozdil od level_switch_html() tu neni "jen kde to ma smysl" vetev --
# mode_toggle_html() se vklada bez podminky do KAZDE stranky pres
# topbar_html() (build_pages.py i generate.py, obe maji vlastni kopii
# topbar_html() ze stejneho duvodu jako u FOOTER_LINKS vys -- generate.py
# se distribuuje nezavisle na zivem checkoutu repa).
#
# Stejny localStorage['atlas-theme'] klic + data-theme atribut + hodnoty
# ('light'/'dark') jako index.html's vlastni toggleTheme() (viz tam,
# ~radek 5882-5934) -- jeden sdileny stav tematu napric SPA i statickymi
# strankami, ne druha nezavisla implementace. Ikony (slunce/mesic SVG) jsou
# bajt-pro-bajt kopie tech ze index.html, ze stejneho duvodu.
#
# THEME_FOUC_SCRIPT je oddeleny, minimalni blokujici <script>, ktery patri
# jako UPLNE PRVNI vec v <head> -- PRED <link rel="stylesheet"> na type.css
# i pred inline <style> blok. Nastavi data-theme na <html> drive, nez
# prohlizec cokoli vykresli, takze stranka s ulozenou tmavou preferenci
# neblikne pri nacteni bile (FOUC). To je rozdil oproti tomu, jak to dnes
# dela SPA (index.html): tam toggleTheme() skript sedi az bl blizko konce
# <body> (po vetsine obsahu), takze SPA samo o sobe FOUC prevenci nema --
# staticke stranky jsou jednodussi (male <head>, zadny velky JS aplikacni
# strom pred nim) a tenhle spravny vzor si tu muzeme dovolit. Neni to
# druha nezavisla logika: cte/pise STEJNY klic/atribut, jen driv.
# ---------------------------------------------------------------------------

THEME_FOUC_SCRIPT = (
    '<script>(function(){'
    "try{if(localStorage.getItem('atlas-theme')==='dark')"
    "document.documentElement.setAttribute('data-theme','dark');"
    "}catch(e){}"
    '})();</script>'
)

MODE_TOGGLE_CSS = """
.topbar-controls{margin-left:auto;display:flex;align-items:center;gap:16px;flex-shrink:0}
.topbar-switch-group{display:flex;align-items:center;gap:7px}
.topbar-switch-label{font-family:'IBM Plex Mono',monospace;font-size:9px;
  letter-spacing:.08em;text-transform:uppercase;color:var(--soft)}
.theme-toggle{background:none;border:1px solid var(--line-strong);padding:5px 12px;
  cursor:pointer;color:var(--soft);font-family:'IBM Plex Mono',monospace;font-size:10px;
  letter-spacing:.06em;text-transform:uppercase;display:flex;align-items:center;gap:7px;
  flex-shrink:0;border-radius:0;line-height:1.4;transition:all .15s}
.theme-toggle:hover{border-color:var(--teal);color:var(--teal)}
.theme-toggle svg{width:13px;height:13px;stroke:currentColor;fill:none;stroke-width:2;
  stroke-linecap:round;stroke-linejoin:round;flex-shrink:0}
@media (max-width:760px){
  .topbar-controls{margin-left:0}
}
@media (max-width:768px){
  .theme-toggle{min-height:44px;padding:0 14px;}
}
"""


def mode_toggle_html():
    """Tlacitko + skript pro topbar_html(). Shodny mechanismus jako
    index.html's theme-toggle (stejne SVG ikony, stejny localStorage klic
    'atlas-theme', stejne hodnoty 'light'/'dark'). Na rozdil od
    level_switch_html() nema podminku (viz komentar vys) -- kazda stranka,
    ktera zavola topbar_html(), ho dostane."""
    return (
        '<div class="topbar-switch-group">'
        '<span class="topbar-switch-label">Mode</span>'
        '<button class="theme-toggle" id="themeToggle" onclick="toggleTheme()" '
        'type="button" title="Switch theme">'
        '<svg viewBox="0 0 24 24"><path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/></svg>'
        '<span id="themeLabel">Dark</span>'
        '</button></div>'
        '<script>(function(){'
        "function updateBtn(theme){"
        "var btn=document.getElementById('themeToggle'),lbl=document.getElementById('themeLabel');"
        "if(!btn||!lbl)return;"
        "if(theme==='dark'){"
        "btn.querySelector('svg').innerHTML='<circle cx=\"12\" cy=\"12\" r=\"4\"/>"
        "<path d=\"M12 2v2M12 20v2M4.93 4.93l1.41 1.41M17.66 17.66l1.41 1.41M2 12h2M20 12h2"
        "M4.93 19.07l1.41-1.41M17.66 6.34l1.41-1.41\"/>';lbl.textContent='Light';"
        "}else{"
        "btn.querySelector('svg').innerHTML='<path d=\"M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z\"/>';"
        "lbl.textContent='Dark';}}"
        "window.toggleTheme=function(){"
        "var cur=document.documentElement.getAttribute('data-theme')||'light';"
        "var next=cur==='dark'?'light':'dark';"
        "document.documentElement.setAttribute('data-theme',next);"
        "try{localStorage.setItem('atlas-theme',next);}catch(e){}"
        "updateBtn(next);};"
        "updateBtn(document.documentElement.getAttribute('data-theme')||'light');"
        '})();</script>'
    )
