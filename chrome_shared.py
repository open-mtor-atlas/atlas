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
.lvsw-btns button[aria-pressed="true"]{background:var(--ink);color:#fff;font-weight:600}
.lv-beginner,.lv-research{display:none}
[data-level="beginner"] .lv-beginner{display:block}
[data-level="beginner"] .lv-student{display:none}
[data-level="research"] .lv-research{display:block}
[data-level="research"] .lv-student{display:none}
[data-level="beginner"] .lv-hide-beginner{display:none}
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
