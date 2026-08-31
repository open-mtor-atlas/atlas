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
