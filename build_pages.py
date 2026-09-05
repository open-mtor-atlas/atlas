#!/usr/bin/env python3
"""
build_pages.py -- Fáze 6, krok B: statické pre-renderování.

PROČ TOHLE EXISTUJE
-------------------
Celý Atlas žije v jednom index.html jako JSON uvnitř <script>. Googlebot
JavaScript vyrenderuje, ale GPTBot, PerplexityBot, ClaudeBot ani Common Crawl
zpravidla ne -- po odstranění skriptů zbývá ve stránce ~18 000 znaků navigace a
žádná studie. Pro AI vyhledávače je Atlas dnes prázdný.

Tenhle skript z týchž dat vyrobí statické stránky, kde je text PŘÍMO V HTML.
SPA zůstává nedotčená; nové stránky jsou vstupní body, které na ni odkazují.

    py build_pages.py            # vygeneruje
    py build_pages.py --clean    # smaže dřív vygenerované a vygeneruje znovu
    py build_pages.py --dry-run  # jen spočítá, nic nezapíše

VSTUP   atlas_data/studies_baked.json, atlas_data/entities_baked.json
VÝSTUP  study/<SID>/index.html            (jedna na studii)
        <typ>/<slug>/index.html           (entity s >=3 studiemi)
        sitemap.xml + sitemap-*.xml
        robots.txt

URL JSOU NEMĚNNÉ. Jakmile je adresa venku a někdo na ni odkáže, přejmenovat ji
znamená rozbít odkaz -- což je přesně to, čemu má fáze 6 zabránit. Slug se
odvozuje z Entity_Name; když se entita v Airtable přejmenuje, PŘIDEJ starý slug
do LEGACY_SLUGS níž, nikdy negeneruj jinou adresu potichu.
"""

import os, sys, json, re, html, shutil, unicodedata, datetime, hashlib, io
from zoneinfo import ZoneInfo

from chrome_shared import (FOOTER_LINKS, static_footer_html,
                            spa_footer_link_html, assert_crumb_matches_ld,
                            entity_explain_for, ENTITY_NAME_TO_NODE_ID,
                            LEVEL_SWITCH_CSS, level_switch_html,
                            MODE_TOGGLE_CSS, mode_toggle_html, THEME_FOUC_SCRIPT)

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "atlas_data")
SITE = "https://mtor-atlas.org"

def _type_css_version():
    """Hash assets/type.css at build time and use it as the cache-busting
    ?v= for every generated static page's <link>. Unlike index.html (hand-
    maintained, needs stamp_type_version.py), static pages are regenerated
    from this template on every build, so there is nothing to stamp
    separately -- the hash is always current by construction."""
    try:
        with io.open(os.path.join(HERE, "assets", "type.css"), "rb") as f:
            return hashlib.sha256(f.read()).hexdigest()[:12]
    except OSError:
        return "missing"


TYPE_CSS_VERSION = _type_css_version()

# Prague-time timestamp for the static footer's "last updated" line --
# computed once per build run. Matches the SPA homepage's own footer, which
# converts ATLAS_UPDATED (UTC) to Europe/Prague via Intl.DateTimeFormat at
# view time (see index.html's #lastUpdated script) -- static pages have no
# such live JS conversion, so the same "YYYY-MM-DD HH:MM Prague time" text
# is baked in directly at build time instead, using the real wall-clock
# time in Prague (DST-aware) rather than a fixed UTC offset.
BUILD_TIMESTAMP = datetime.datetime.now(ZoneInfo("Europe/Prague")).strftime("%Y-%m-%d %H:%M") + " Prague time"

DRY = "--dry-run" in sys.argv
CLEAN = "--clean" in sys.argv

PAGE_THRESHOLD = 3          # quality gate z plánu fáze 6
GENERATED_MARKER = "<!-- generated-by-build-pages -->"

def _read_citation_version():
    """Single source of truth for the dataset's formal version: CITATION.cff's
    own `version:` field, bumped by hand whenever a new Zenodo release is cut.
    Read here instead of hardcoding the same string separately in DATASET_REF
    and in index.html's own JSON-LD block -- exactly the kind of two-copies
    drift this project has been bitten by before. No PyYAML dependency: the
    `version:` line in CITATION.cff is a single simple scalar, so a narrow
    regex is enough. Returns "unknown" (never invents a number) if the file
    or field is missing -- a bake still succeeds either way."""
    try:
        text = open(os.path.join(HERE, "CITATION.cff"), encoding="utf-8").read()
    except OSError:
        return "unknown"
    m = re.search(r'^version:\s*"?([^"\n]+?)"?\s*$', text, re.M)
    return m.group(1) if m else "unknown"


# --- SEO P0 Ukol 3 (2026-09-02): data exports -- DATASET_REF.distribution ---


def _load_export_distribution():
    """DataDownload entries for the live CSV/JSON exports in data/exports/,
    read from that directory's own manifest.json (written by
    tools/seo/build_data_exports.py, which must run before this module --
    same ordering convention as build_academy.py before build_pages.py).
    Returns [] (never fails the build) if the exports haven't been
    generated yet -- the Zenodo entry in DATASET_REF stays the one
    unconditional distribution. Reading contentUrl/contentSize/sha256 from
    the manifest instead of hand-listing file names here means this list
    can never silently drift from what's actually on disk."""
    p = os.path.join(HERE, "data", "exports", "manifest.json")
    if not os.path.exists(p):
        return []
    try:
        manifest = json.load(open(p, encoding="utf-8"))
    except Exception:
        return []
    out = []
    for m in manifest:
        out.append({
            "@type": "DataDownload",
            "name": m["name"],
            "encodingFormat": m["encodingFormat"],
            "contentUrl": m["contentUrl"],
            "contentSize": str(m["contentSize"]),
        })
    return out



# Google Rich Results validuje i VNOŘENÉ Dataset uzly (isPartOf). Holý stub
# {name, url} = "chybí pole description / creator / license" v Search Console.
# Musí sedět s hlavním Dataset blokem v index.html -- both read the SAME
# version (CITATION.cff, via _read_citation_version()) and are re-stamped
# with the same dateModified at build time; patch_dataset_meta() below is
# what pushes these two values into index.html's separate hand-written block.
DATASET_REF = {
    "@type": "Dataset",
    "name": "Oliver's mTOR Atlas",
    "url": SITE + "/",
    "description": (
        "A curated, evidence-graded database of mTOR pathway research: over 350 "
        "studies, with every eligible peer-reviewed primary study rated by evidence "
        "tier (A = systematic review/meta-analysis, B = human trial, C = animal model, "
        "D = mechanistic/in-vitro/review), linked to a knowledge graph of genes, "
        "diseases and interventions, plus AI-identified knowledge gaps and testable "
        "hypotheses."
    ),
    "identifier": "https://doi.org/10.5281/zenodo.22059963",
    "sameAs": [
        "https://doi.org/10.5281/zenodo.22059963",
        "https://bio.tools/olivers_mtor_atlas",
        "https://fairsharing.org/8905",
    ],
    "creator": {"@type": "Person", "name": "Oliver Barton",
                "url": "https://orcid.org/0009-0008-2025-2148",
                "sameAs": ["https://orcid.org/0009-0008-2025-2148"]},
    "publisher": {"@type": "Organization", "name": "Oliver's mTOR Atlas",
                  "url": SITE + "/"},
    "distribution": [
        {
            "@type": "DataDownload",
            "name": "Archived snapshot (Zenodo)",
            "encodingFormat": "text/html",
            "contentUrl": "https://doi.org/10.5281/zenodo.22059963",
        },
    ] + _load_export_distribution(),
    "license": "https://creativecommons.org/licenses/by/4.0/",
    "isAccessibleForFree": True,
    "inLanguage": "en",
    "keywords": ["mTOR", "mTORC1", "mTORC2", "autophagy", "rapamycin", "longevity",
                 "aging biology", "TSC complex", "evidence-based research"],
    # "version" is the last formally cut Zenodo release (tag v1.0.0, DOI
    # 10.5281/zenodo.22059964) -- NOT the live corpus size, which changes
    # far more often than a release should. dateModified tracks the living
    # corpus itself (stamped at build time, same convention as the sitemap
    # <lastmod>): a reader/crawler can see the page changed even between
    # formal version bumps.
    "version": _read_citation_version(),
    "dateModified": datetime.date.today().isoformat(),
}

# Entity_Type -> URL prefix. Změna = rozbité odkazy, viz hlavička.
TYPE_DIR = {
    "Gene/Protein": "gene",
    "Pathway/Complex": "complex",
    "Drug": "drug",
    "Intervention": "intervention",
    "Biological process": "process",
    "Disease": "disease",
    "Outcome": "outcome",
    "Organelle": "organelle",
    "Nutrient/Metabolite": "nutrient",
    # Přidáno 2026-08-04: "Condition" v Airtable existuje (např. "Energy &
    # cellular stress"), ale chybělo mapování -> padalo do fallbacku "entity/",
    # což by při prvním buildu vytvořilo adresu, kterou už nejde tiše změnit.
    # Tohle je PRVNÍ build s touto entitou, takže žádný LEGACY_SLUGS není potřeba.
    "Condition": "condition",
}
LEGACY_SLUGS = {}           # {"stary-slug": "novy-slug"} -> vygeneruje redirect

# 2026-08-04 -- SEO/GEO vylepšení, druhé kolo (schváleno Petrem).
#
# Wikidata Q-ID pro entity, kde jde jednoznačně přiřadit JEDNU konkrétní
# položku (gen, sloučenina, nemoc, proces). Každé ID bylo ověřeno přes
# wikidata.org search, ne odhadnuto z paměti -- špatné ID na vědeckém webu je
# horší než žádné. Composite entity (např. "TSC1/TSC2" ale ne jako pár genů
# dohromady, "IRS-1 / IRS-2", "Rag GTPases" jako rodina, "Energy & cellular
# stress") jsou vynechané záměrně: nejde je napojit na jedinou Wikidata
# položku, aniž by to bylo zavádějící.
EXTERNAL_IDS = {
    "mTOR": ["https://www.wikidata.org/wiki/Q14876086"],
    "Akt/PKB": ["https://www.wikidata.org/wiki/Q17816452"],
    "PI3K": ["https://www.wikidata.org/wiki/Q14887700"],
    "Raptor": ["https://www.wikidata.org/wiki/Q18043110"],
    "Rictor": ["https://www.wikidata.org/wiki/Q18053691"],
    "Rheb": ["https://www.wikidata.org/wiki/Q18031127"],
    "S6K1": ["https://www.wikidata.org/wiki/Q18031289"],
    "4E-BP1": ["https://www.wikidata.org/wiki/Q17916086"],
    "eIF4E": ["https://www.wikidata.org/wiki/Q5408696"],
    "SLC38A9": ["https://www.wikidata.org/wiki/Q18052220"],
    "ULK1": ["https://www.wikidata.org/wiki/Q18032908"],
    "TFEB": ["https://www.wikidata.org/wiki/Q18032677"],
    "AMPK": ["https://www.wikidata.org/wiki/Q295240"],
    "TSC1/TSC2": ["https://www.wikidata.org/wiki/Q14908106"],
    "mTORC1": ["https://www.wikidata.org/wiki/Q14876060"],
    "mTORC2": ["https://www.wikidata.org/wiki/Q14876061"],
    "Autophagy": ["https://www.wikidata.org/wiki/Q288322"],
    "Rapamycin": ["https://www.wikidata.org/wiki/Q32089"],
    "Everolimus": ["https://www.wikidata.org/wiki/Q421052"],
    "Metformin": ["https://www.wikidata.org/wiki/Q19484"],
    "Resveratrol": ["https://www.wikidata.org/wiki/Q407329"],
    "Alzheimer's disease": ["https://www.wikidata.org/wiki/Q11081"],
    "Breast cancer": ["https://www.wikidata.org/wiki/Q128581"],
    "Renal cell carcinoma (RCC)": ["https://www.wikidata.org/wiki/Q1164529"],
    "Tuberous sclerosis complex": ["https://www.wikidata.org/wiki/Q1362721"],
    "Arginine": ["https://www.wikidata.org/wiki/Q173670"],
    "Leucine": ["https://www.wikidata.org/wiki/Q483745"],
    "Lysosome": ["https://www.wikidata.org/wiki/Q83330"],
    "Longevity": ["https://www.wikidata.org/wiki/Q1066907"],
    "Caloric restriction": ["https://www.wikidata.org/wiki/Q1332886"],
    "Insulin resistance": ["https://www.wikidata.org/wiki/Q1053470"],
    "Protein synthesis": ["https://www.wikidata.org/wiki/Q211935"],
    "Actin cytoskeleton": ["https://www.wikidata.org/wiki/Q14860845"],
    "Cellular senescence": ["https://www.wikidata.org/wiki/Q9075999"],
    "Lipid synthesis": ["https://www.wikidata.org/wiki/Q21096257"],
    "Nucleotide synthesis": ["https://www.wikidata.org/wiki/Q14819381"],
    "Immune function": ["https://www.wikidata.org/wiki/Q1612119"],
    "Tumor growth": ["https://www.wikidata.org/wiki/Q133212"],
    "Muscle growth": ["https://www.wikidata.org/wiki/Q1955391"],
}

TIER_LABEL = {
    "A - Systematic review": ("A", "Systematic review of human data", "#2F7A52"),
    "B - Human": ("B", "Direct human evidence", "#2F6FA8"),
    "C - Animal": ("C", "Animal in vivo", "#A56827"),
    "D - Mechanistic/Review": ("D", "Mechanistic / in vitro / review", "#7C7569"),
    "Preprint": ("—", "Preprint, not peer-reviewed", "#8B5FBF"),
    "Registered trial": ("—", "Registered trial, no results yet", "#5278A6"),
}


# ---------------------------------------------------------------- helpers ---

def slugify(s):
    s = unicodedata.normalize("NFKD", s)
    s = s.replace("α", "alpha").replace("β", "beta").replace("γ", "gamma")
    # Apostrof se ZAHAZUJE, nenahrazuje pomlčkou. Jinak z "Alzheimer's disease"
    # vznikne /disease/alzheimer-s-disease/ -- adresa, kterou nikdo nenapíše ani
    # neodhadne, a po zveřejnění se už měnit nesmí.
    s = re.sub(r"['’ʼ`]", "", s)
    s = s.encode("ascii", "ignore").decode()
    s = s.lower()
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    return s or "unnamed"


def e(s):
    # html.unescape() nejdriv rozbali pripadne uz-zakodovane entity
    # (&mdash; &lsquo; &rsquo; &ndash; ...), ktere kuratori pisou rucne
    # primo do dat (funguje pro SPA, kde se vklada přes innerHTML) --
    # bez tohohle by html.escape() zakodoval i to & v nich znovu a
    # vysledek by se na strance zobrazil doslova jako "&amp;mdash;".
    # unescape+escape je bezpecne idempotentni i pro text bez entit.
    return html.escape(html.unescape(str(s or "")), quote=True)


def tier_bits(t):
    return TIER_LABEL.get((t or "").strip(), ("—", t or "ungraded", "#7C7569"))


def breadcrumb_ld(items):
    """BreadcrumbList schema z (name, url|None) dvojic -- doplněk 2026-08-04
    k viditelné <nav class="crumb">, kterou stránky měly už od fáze 6.
    Poslední položka (aktuální stránka) může mít url=None."""
    els = []
    for i, (name, url) in enumerate(items, 1):
        el = {"@type": "ListItem", "position": i, "name": name}
        if url:
            el["item"] = url
        els.append(el)
    return {"@context": "https://schema.org", "@type": "BreadcrumbList",
            "itemListElement": els}


SITE_TABS = [
    ("welcome", "Welcome"), ("learn", "Learn"), ("ask", "Ask Atlas"), ("map", "Pathway"),
    ("studies", "Studies"), ("authors", "Authors"), ("questions", "Open Questions"),
    ("lineage", "Timeline"), ("about", "About"),
]

# Taby, které mají SKUTEČNOU statickou stránku, a odkazují se tedy na ni místo
# na hash-route do SPA. "about" tu je od 2026-08-23, "learn" od 2026-08-30
# (Academy -- generuje build_academy.py, ne tenhle skript; odkaz sem patří,
# aby ho měly i všechny pre-renderované stránky, a crawler bez JS ho viděl).
STATIC_TAB_URLS = {
    "about": f"{SITE}/about/",
    "learn": f"{SITE}/academy/",
    # "map" -- 2026-09-05 (SEO P0 Ukol 5): the pathway map is a canvas
    # diagram with zero indexable text; /pathway/ is the static, crawlable
    # form of the same pathway/model.json (see pathway_page()).
    "map": f"{SITE}/pathway/",
}


def topbar_html(active_tab=None):
    """Site-wide header (logo + primary nav), added 2026-08-22 so every static
    entry-point page (study/entity/question/author/browse, plus the hand-baked
    /answers/ and /glossary/ pages) carries the same top-level branding and
    navigation as the SPA (index.html), instead of just a bare breadcrumb.

    Deliberately NOT a clone of the SPA topbar: no search box (nothing here to
    search against without the SPA's JS + data) and no Level switch (that's a
    stateful reading-level control that only some page types have anything to
    act on -- see shell(level_switch=...) instead, which renders it separately
    below the breadcrumb, only on entity/study/question pages, per Faze 2b/
    Faze 6's decision not to relocate it). Mode IS included here (Faze 6,
    2026-08-31): every page has visible color, so unlike Level there is no
    'only where it applies' branch -- mode_toggle_html() renders
    unconditionally inside .topbar-controls, mirroring the SPA's own
    .topbar-controls > .topbar-switch-group markup/class names (index.html)
    so the two chrome layers read as the same site in both themes. Just the
    wordmark, Mode toggle, and the 9 tabs, as plain links into
    the SPA's own hash-addressed views -- the SPA reads {SITE}/#view=<tab>
    (URLSearchParams over location.hash, see applyHash() in index.html), NOT
    a bare {SITE}/#<tab> fragment. Fixed 2026-08-23 after the bare-fragment
    version shipped broken (linked to "#questions" instead of "#view=questions").

    EXCEPTION (2026-08-23): the "about" tab points at the static /about/ page
    (STATIC_TAB_URLS above), not {SITE}/#view=about. That hash route is real
    but only resolves once the SPA's JS has run -- exactly the audit finding
    this fixes: a crawler or a skeptical reader landing on a /study/ or
    /answers/ page had no *static* link explaining who curates the Atlas or
    how it's graded. Same for "learn" -> /academy/ (2026-08-30), which has no
    hash route at all: the Academy is a static section, not an SPA view. The
    remaining 7 tabs are left as hash links; they don't (yet) have static
    equivalents worth linking to instead."""
    static_urls = STATIC_TAB_URLS
    tabs = "".join(
        '<a href="{}"{}>{}</a>'.format(
            static_urls.get(tid, f"{SITE}/#view={tid}"),
            ' class="active"' if tid == active_tab else "", e(label))
        for tid, label in SITE_TABS)
    return f"""<div class="oma-topbar"><div class="oma-topbar-inner">
<a class="oma-wordmark" href="{SITE}/" title="Oliver's mTOR Atlas — home">
<svg class="oma-emblem" viewBox="0 0 64 64" role="img" aria-label="Oliver's mTOR Atlas emblem"><path d="M40.89 7.57 A26 26 0 1 1 23.11 7.57" fill="none" stroke="currentColor" stroke-width="5" stroke-linecap="round"/><circle cx="32" cy="15" r="9" fill="currentColor"/></svg>
<span class="oma-name">Oliver's mTOR Atlas</span>
<span class="oma-tag">Evidence Platform</span>
</a>
<div class="topbar-controls">{mode_toggle_html()}</div>
</div></div>
<div class="oma-tabs-row"><div class="oma-tabs-inner"><nav class="oma-tabs" aria-label="Main">{tabs}</nav></div></div>"""


def shell(title, desc, canonical, jsonld, body, breadcrumb, active_tab=None,
          extra_css="", extra_body="", level_switch=False, robots="index, follow"):
    """Jedna šablona pro všechny stránky. Obsah je v HTML, ne v JS -- to je
    celý bod. Styl je inline, aby stránka nezávisela na dalším requestu.

    `extra_css` (přidáno 2026-08-30 kvůli build_academy.py): volitelný blok
    CSS připojený NA KONEC <style>, takže smí přepsat cokoli výš (Academy si
    tak rozšíří .wrap na dva sloupce, aniž by to ovlivnilo ostatní stránky --
    každá stránka je samostatný dokument). Prázdný řetězec = beze změny, takže
    všech ~390 dosavadních stránek se generuje bajt po bajtu stejně jako dřív.

    `extra_body`: volitelný HTML/JS blok vložený za patičku, uvnitř <body>.
    Academy tudy posílá svůj progress skript; nic jiného ho zatím nepoužívá.

    `jsonld` je buď jeden dict, nebo seznam dictů -- každý dostane vlastní
    <script> blok. Google Rich Results podporuje víc bloků na stránce; jeden
    blok s @graph by fungoval taky, ale oddělené bloky se snáz generují a
    snáz se v nich hledá při debugování.

    `active_tab` (přidáno 2026-08-22): id z SITE_TABS, který se v horní
    navigaci zvýrazní jako aktivní -- volitelné, viz volání v jednotlivých
    *_page() funkcích níž."""
    blocks = jsonld if isinstance(jsonld, list) else [jsonld]
    ld_html = "\n".join(
        '<script type="application/ld+json">\n'
        + json.dumps(b, ensure_ascii=False, indent=1) + "\n</script>"
        for b in blocks)
    # Bezpecnostni sit (plan SS11.3): viditelny drobecek MUSI sedet s
    # BreadcrumbList JSON-LD, jinak build spadne. Kontrola je tu jednou,
    # centralne pro vsech ~460 stranek, misto rucniho volani v kazde
    # *_page() funkci -- shell() uz oba kusy (breadcrumb, jsonld) dostava.
    for b in blocks:
        assert_crumb_matches_ld(breadcrumb, b, context=title)
    topbar = topbar_html(active_tab)
    return f"""<!DOCTYPE html>
<html lang="en">
{GENERATED_MARKER}
<head>
{THEME_FOUC_SCRIPT}
<!-- Google tag (gtag.js) -->
<script async src="https://www.googletagmanager.com/gtag/js?id=G-420TPC8J46"></script>
<script>
  window.dataLayer = window.dataLayer || [];
  function gtag(){{dataLayer.push(arguments);}}
  gtag('js', new Date());
  gtag('config', 'G-420TPC8J46');
</script>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{e(title)}</title>
<meta name="description" content="{e(desc)}">
<link rel="canonical" href="{e(canonical)}">
<meta name="robots" content="{robots}">
<meta property="og:type" content="article">
<meta property="og:site_name" content="Oliver's mTOR Atlas">
<meta property="og:title" content="{e(title)}">
<meta property="og:description" content="{e(desc)}">
<meta property="og:url" content="{e(canonical)}">
<meta property="og:image" content="{SITE}/og-image.png">
<meta name="twitter:card" content="summary_large_image">
<link rel="icon" type="image/png" href="/favicon.png">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=DM+Sans:opsz,wght@9..40,400;9..40,700&family=IBM+Plex+Mono:wght@400;500;600&display=swap" rel="stylesheet">
{ld_html}
<link rel="stylesheet" href="/assets/type.css?v={TYPE_CSS_VERSION}">
<style>
:root{{--paper:#fff;--ink:#0A0A0A;--soft:#55524C;--line:rgba(0,0,0,.13);
--teal:#A31F34;--amber:#A56827}}
*{{box-sizing:border-box}}
body{{margin:0;background:var(--paper);color:var(--ink);
font:var(--fs-body,16px)/var(--lh-body,1.62) var(--font-text,
-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif)}}
.wrap{{max-width:var(--measure-wide,1100px);margin:0 auto;padding:26px 22px 70px}}
a{{color:var(--teal)}}
/* ---- Site-wide topbar (logo + primary nav) -- unified 2026-08-30 with the
   SPA's own header so every static page (Academy, Browse, Study, Answers,
   Glossary, About...) reads as the same site as the interactive Atlas
   instead of a second, smaller-looking nav bolted on beside it. ---- */
.oma-topbar{{border-bottom:2px solid var(--ink)}}
.oma-topbar-inner{{max-width:1100px;margin:0 auto;padding:22px 26px 16px;
display:flex;align-items:center;gap:9px;flex-wrap:wrap}}
.oma-wordmark{{display:flex;align-items:center;gap:9px;text-decoration:none;
color:var(--ink);flex-shrink:0}}
.oma-wordmark:hover{{opacity:.75}}
.oma-emblem{{width:34px;height:34px;flex-shrink:0;align-self:center;color:var(--teal)}}
.oma-name{{font-family:'DM Sans',-apple-system,sans-serif;font-weight:700;
font-size:19px;letter-spacing:-.01em;white-space:nowrap}}
.oma-tag{{font-family:'IBM Plex Mono',monospace;font-size:10px;letter-spacing:.06em;
text-transform:uppercase;color:var(--soft);border-left:1px solid var(--line);
padding-left:9px;white-space:nowrap}}
.oma-tabs-row{{border-bottom:2px solid var(--ink)}}
.oma-tabs-inner{{max-width:1100px;margin:0 auto;padding:0 26px}}
.oma-tabs{{display:flex;flex-wrap:wrap;gap:4px}}
.oma-tabs a{{font-family:'IBM Plex Mono',monospace;font-weight:600;font-size:12px;
letter-spacing:.05em;text-transform:uppercase;padding:11px 18px;color:var(--ink);
text-decoration:none;border-bottom:3px solid transparent;margin-bottom:-2px}}
.oma-tabs a:hover{{background:rgba(163,31,52,.08);color:var(--teal)}}
.oma-tabs a.active{{color:var(--on-teal,#fff);background:var(--teal);border-bottom-color:var(--teal);font-weight:700}}
nav.crumb{{max-width:var(--measure-wide,1100px);margin:0 auto;padding:14px 22px 0;
font-family:var(--font-mono,'IBM Plex Mono',monospace);
font-size:var(--fs-micro,11px);letter-spacing:.14em;text-transform:uppercase;
color:var(--soft);border:0;margin-bottom:var(--sp-3,12px)}}
nav.crumb a{{color:inherit;text-decoration:none}}
nav.crumb a:hover{{color:var(--teal)}}
h1{{font-size:var(--fs-h1,clamp(26px,3.4vw,34px));line-height:1.2;
margin:0 0 10px;letter-spacing:-.01em;max-width:var(--measure,68ch)}}
.wrap ul{{max-width:var(--measure,68ch)}}
h2{{font-size:var(--fs-h2,21px);margin:var(--sp-6,34px) 0 9px;padding-bottom:5px;
border-bottom:1px solid var(--line)}}
.meta{{color:var(--soft);font-size:14px;margin:0 0 18px}}
.tier{{display:inline-block;padding:2px 9px;border-radius:3px;color:#fff;
font-size:12px;font-weight:600;letter-spacing:.03em}}
.summary{{font-size:var(--fs-lead,17px);line-height:var(--lh-body,1.62);
border-left:3px solid var(--teal);padding:2px 0 2px 15px;margin:0 0 20px;
max-width:var(--measure,68ch)}}
table{{border-collapse:collapse;width:100%;font-size:14px;margin:6px 0 18px}}
th{{text-align:left;font-size:12px;letter-spacing:.04em;text-transform:uppercase;
color:var(--soft);border-bottom:1.5px solid var(--ink);padding:5px 10px 5px 0}}
td{{padding:7px 10px 7px 0;border-bottom:1px solid var(--line);vertical-align:top}}
ul{{padding-left:19px}} li{{margin-bottom:6px}}
.tags a{{display:inline-block;font-size:13px;border:1px solid var(--line);
border-radius:3px;padding:3px 9px;margin:0 5px 6px 0;text-decoration:none}}
.cta{{display:inline-block;background:var(--ink);color:var(--on-ink,#fff);text-decoration:none;
padding:10px 17px;border-radius:3px;font-size:14px;margin:6px 0 0}}
footer.oma-footer{{margin-top:44px;padding:22px 22px 26px;border-top:1px solid var(--line);
font-family:'IBM Plex Mono',monospace;font-size:12px;color:var(--soft);
text-align:center}}
footer.oma-footer p{{max-width:640px;margin:0 auto 8px;font-family:-apple-system,
BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;font-size:13px;line-height:1.55}}
footer.oma-footer .oma-footer-links{{margin-top:10px}}
footer.oma-footer .oma-footer-links a{{margin:0 8px}}
footer.oma-footer .oma-footer-meta{{margin-top:10px;opacity:.7}}
.abstract{{font-size:var(--fs-lead,17px);line-height:var(--lh-body,1.62);
color:var(--prose-ink,#26241F);max-width:var(--measure,68ch)}}
.tier-why{{color:var(--soft);font-size:14px;margin:-10px 0 20px;max-width:var(--measure,68ch)}}
pre.cite{{background:var(--code-bg,rgba(0,0,0,.04));border:1px solid var(--line);
border-radius:4px;padding:12px 14px;font-family:'IBM Plex Mono',monospace;
font-size:12.5px;line-height:1.6;white-space:pre-wrap;word-break:break-word;
max-width:var(--measure,68ch)}}
h3{{font-size:var(--fs-h3,16px);margin:18px 0 8px}}

/* ─────────────────────────────────────────────────────────────────────
   MOBILE LAYER (added 2026-07-29)
   These pages previously had no media queries at all: a fixed 760px wrap
   and a four-column Studies table, which on a 360px phone meant a
   permanently horizontally-scrolled page with ~90px columns.
   ───────────────────────────────────────────────────────────────────── */
html{{-webkit-text-size-adjust:100%;text-size-adjust:100%}}
img,svg{{max-width:100%;height:auto}}
.wrap{{overflow-wrap:break-word}}
a{{overflow-wrap:anywhere}}

@media (max-width:760px){{
  .oma-tabs-inner{{overflow-x:auto;-webkit-overflow-scrolling:touch}}
  .oma-tabs{{flex-wrap:nowrap;min-width:max-content}}
  .wrap{{padding:20px 16px 56px;
    padding-left:max(16px,env(safe-area-inset-left));
    padding-right:max(16px,env(safe-area-inset-right))}}
  h1{{font-size:clamp(21px,5.4vw,25px);line-height:1.22}}
  h2{{font-size:16px;margin:26px 0 8px}}
  .summary{{font-size:16px;padding-left:13px}}
  body{{font-size:16px}}
  nav.crumb{{font-size:10.5px;line-height:1.9}}
  /* breadcrumb + tag links need finger-sized targets */
  nav.crumb a,footer a{{display:inline-flex;align-items:center;
    padding:6px 0;min-height:44px}}
  .tags a{{padding:9px 12px;margin:0 6px 8px 0;font-size:14px;min-height:44px;
    display:inline-flex;align-items:center}}
  .cta{{padding:13px 20px;font-size:15px;min-height:44px;
    display:inline-flex;align-items:center}}
  /* study-id and entity links inside tables were 21px tall */
  table a,.wrap li>a,.wrap p>a{{display:inline-flex;align-items:center;min-height:44px}}
  table{{font-size:15px}}
}}

@media (max-width:560px){{
  /* two-column key/value tables stay tabular but tighten up */
  table.kv td{{padding:7px 8px 7px 0}}
  table.kv td:first-child{{width:38%}}

  /* the Studies and Evidence tables become cards */
  table.st,table.ev{{display:block}}
  table.st tr:first-child,table.ev tr:first-child{{
    position:absolute;width:1px;height:1px;padding:0;margin:-1px;
    overflow:hidden;clip:rect(0,0,0,0);white-space:nowrap;border:0}}
  table.st tbody,table.ev tbody,
  table.st tr,table.ev tr,
  table.st td,table.ev td{{display:block;width:100%}}
  table.st tr,table.ev tr{{
    border:1px solid var(--line);padding:11px 13px;margin:0 0 10px}}
  table.st td,table.ev td{{border:none;padding:3px 0}}
  table.st td[data-l]::before,table.ev td[data-l]::before{{
    content:attr(data-l);display:block;
    font-size:10.5px;letter-spacing:.07em;text-transform:uppercase;
    color:var(--soft);margin-bottom:2px}}
  /* Study id, Year and Tier read as one compact header line */
  table.st td[data-l="Study"]{{font-weight:600;font-size:16px}}
  table.st td[data-l="Year"],table.st td[data-l="Tier"]{{
    display:inline-block;width:auto;margin-right:20px}}
  table.st td[data-l="Finding"]{{padding-top:7px;line-height:1.55}}
  table.ev td[data-l="Tier"],table.ev td[data-l="Studies"]{{
    display:inline-block;width:auto;margin-right:22px}}
}}

@media (max-width:380px){{
  .wrap{{padding:16px 13px 48px}}
  h1{{font-size:20px}}
}}

@media (prefers-reduced-motion:reduce){{
  *{{animation:none!important;transition:none!important}}
}}{extra_css}
{LEVEL_SWITCH_CSS}
{MODE_TOGGLE_CSS}</style>
</head>
<body>
{topbar}
<div class="wrap">
<nav class="crumb">{breadcrumb}</nav>
{level_switch_html() if level_switch else ""}
{body}
{static_footer_html(SITE, BUILD_TIMESTAMP)}{extra_body}
</div>
</body>
</html>
"""


# ------------------------------------------------------------ study pages ---

def ent_ref(x, haspage):
    """Odkaz na entitu POUZE když její stránka existuje.

    Entity pod prahem PAGE_THRESHOLD stránku nedostanou, ale pořád se objevují
    jako sousedé. Odkazovat na ně znamená vyrobit 404 -- při prvním generování
    jich takhle vzniklo 110. Bez stránky se vypíšou jako text: informace
    zůstane, rozbitý odkaz ne.
    """
    d = TYPE_DIR.get(x["type"], "entity")
    slug = slugify(x["name"])
    if (d, slug) in haspage:
        return f'<a href="/{d}/{slug}/">{e(x["name"])}</a>'
    return f'<span>{e(x["name"])}</span>'


def _load_academy_index():
    """Reverzní index {SID: [{title, url}]}, který zapisuje build_academy.py.
    Chybí-li (první běh, nebo Academy zatím nevygenerovaná), vrátí prázdno a
    blok "Learn the biology" se prostě nevykreslí -- žádný mrtvý odkaz, žádná
    tvrdá závislost jedním směrem. build_academy.py se proto spouští PŘED
    tímhle skriptem, viz deploy.bat / deploy.sh."""
    p = os.path.join(HERE, "academy_data", "_sid_to_lesson.json")
    if not os.path.exists(p):
        return {}
    try:
        return json.load(open(p, encoding="utf-8"))
    except Exception:
        return {}


ACADEMY_BY_SID = _load_academy_index()


# --- SEO P0 Ukol 2 (2026-09-02): study_page rebuild -- new helpers ---


def _load_gap_citations():
    """Reverse index {SID: [(title, url)]} for Open Questions/hypotheses that
    cite this study -- Ukol 2, "In the Atlas" section. Empty if gaps_baked.json
    is missing (mirrors _load_academy_index's no-hard-dependency pattern).
    URL construction mirrors gap_page()'s own slug -- if that ever changes,
    change it there and here together or the two will silently disagree."""
    p = os.path.join(DATA, "gaps_baked.json")
    if not os.path.exists(p):
        return {}
    try:
        gaps = json.load(open(p, encoding="utf-8"))
    except Exception:
        return {}
    out = {}
    for g in gaps:
        url = f"{SITE}/question/{slugify(g['title'])}/"
        for sid in g.get("studies") or []:
            out.setdefault(sid, []).append((g["title"], url))
    return out


GAPS_BY_SID = _load_gap_citations()


def _load_answer_citations():
    """Reverse index {SID: [(title, url)]} for /answers/ pages that cite this
    study. /answers/ is hand-baked by generate.py (Petr's explicit static-
    section decision, 2026-08-22) with no separate machine-readable source,
    so the already-published HTML *is* the source here -- grep, not a data
    file. Re-run after any /answers/ content change or this index goes
    stale (same caveat as ACADEMY_BY_SID: no hard dependency, just silently
    empty until the next build)."""
    out = {}
    base = os.path.join(HERE, "answers")
    if not os.path.isdir(base):
        return out
    for slug in sorted(os.listdir(base)):
        fp = os.path.join(base, slug, "index.html")
        if not os.path.isfile(fp):
            continue
        try:
            text = open(fp, encoding="utf-8").read()
        except OSError:
            continue
        m = re.search(r"<h1>(.*?)</h1>", text, re.S)
        title = re.sub(r"<[^>]+>", "", m.group(1)).strip() if m else slug
        url = f"{SITE}/answers/{slug}/"
        for sid in set(re.findall(r"/study/([A-Za-z0-9]+)/", text)):
            out.setdefault(sid, []).append((title, url))
    return out


ANSWERS_BY_SID = _load_answer_citations()


# --- SEO P0 Ukol 11.4 (2026-09-02): answers->question backlinks ---


def _load_answer_gap_backlinks():
    """Reverse index {question-slug: [(answer_title, answer_url), ...]} --
    which /answers/ pages link to a given /question/ page. Same source-of-
    truth approach as _load_answer_citations() (grep the published /answers/
    HTML, since it has no separate machine-readable source) but matching
    /question/ links instead of /study/ links.

    Supersedes the old hand-picked GAP_TO_ANSWER dict (2026-08-29, exactly
    one pair): that fix assumed every gap<->answer relationship is a clean
    1:1 pair, but this session's audit (Ukol 11.4) found questions cited by
    MULTIPLE different answer pages -- a many-to-one relationship a single
    hardcoded pair can't express. This index handles both cases uniformly
    and never goes stale when a new /answers/ page is added, unlike the
    hardcoded dict."""
    out = {}
    base = os.path.join(HERE, "answers")
    if not os.path.isdir(base):
        return out
    for slug in sorted(os.listdir(base)):
        fp = os.path.join(base, slug, "index.html")
        if not os.path.isfile(fp):
            continue
        try:
            text = open(fp, encoding="utf-8").read()
        except OSError:
            continue
        m = re.search(r"<h1>(.*?)</h1>", text, re.S)
        title = re.sub(r"<[^>]+>", "", m.group(1)).strip() if m else slug
        url = f"{SITE}/answers/{slug}/"
        for qslug in set(re.findall(r"/question/([a-z0-9-]+)/", text)):
            out.setdefault(qslug, []).append((title, url))
    return out


ANSWER_GAP_BACKLINKS = _load_answer_gap_backlinks()




def _load_record_dates():
    """SID -> ISO date for the "Record last updated" row + JSON-LD
    dateModified (Ukol 2 item 7). CAVEAT (checked 2026-09-02): neither
    AUDIT_changelog_studies.json nor REVIEW_changelog_studies.json carries a
    per-entry date -- their keys are only sid/field/old/new/why. Both files
    correspond to the audit round documented alongside AUDIT_scientific_
    calibration_2026-07-29.md / REVIEW_external_scientific_2026-07-29.md, so
    a SID appearing in either gets that round's date; everything else falls
    back to CITATION.cff's date-released. This is coarser than a real
    per-field timestamp -- flagged in the handover, not silently assumed."""
    AUDIT_ROUND_DATE = "2026-07-29"
    fallback = "unknown"
    try:
        cff = open(os.path.join(HERE, "CITATION.cff"), encoding="utf-8").read()
        m = re.search(r'^date-released:\s*"?([\d-]+)"?\s*$', cff, re.M)
        if m:
            fallback = m.group(1)
    except OSError:
        pass
    dates = {}
    for fn in ("AUDIT_changelog_studies.json", "REVIEW_changelog_studies.json"):
        p = os.path.join(DATA, fn)
        if not os.path.exists(p):
            continue
        try:
            rows = json.load(open(p, encoding="utf-8"))
        except Exception:
            continue
        for row in rows:
            sid = row.get("sid")
            if sid:
                dates[sid] = AUDIT_ROUND_DATE
    return dates, fallback


RECORD_DATE_BY_SID, RECORD_DATE_FALLBACK = _load_record_dates()


def _load_noindex_studies():
    """SIDs to serve noindex,follow -- decided by tools/seo/decide_noindex.py
    from a post-rebuild seo_study_audit.csv and stored here so the decision
    is reversible/auditable (a plain JSON list) instead of baked silently
    into a one-off script run. Empty (not an error) on first run, before
    that file exists -- every study indexes normally until a human/curator
    decision produces the list."""
    p = os.path.join(DATA, "seo_noindex_studies.json")
    if not os.path.exists(p):
        return set()
    try:
        return set(json.load(open(p, encoding="utf-8")))
    except Exception:
        return set()


NOINDEX_STUDIES = _load_noindex_studies()


def tier_reason(s):
    """One sentence on WHY this record has this tier -- Ukol 2 item 2: a
    beginner reads "D" as "D-minus" without this. 8 templates keyed by
    (tier, category), not one generic sentence, so the reader can tell which
    kind of C or D this is (a null result is not a weak result; mechanistic
    work is not lesser work -- it is often where causal biology actually
    gets established)."""
    tier = (s.get("tier") or "").strip()
    category = (s.get("category") or "").strip()
    model = s.get("model") or s.get("ai_species") or "the studied system"
    if tier == "A - Systematic review":
        return ("Tier A because it systematically synthesizes multiple human "
                "studies (a systematic review or meta-analysis); tier describes "
                "study design, not the quality of any single included study.")
    if tier == "B - Human":
        return ("Tier B because it is direct evidence from a human clinical "
                "trial or human cohort; tier describes study design, not "
                "quality -- a small, well-run trial is still tier B.")
    if tier == "C - Animal":
        if category == "Negative_result":
            return (f"Tier C because it is an animal study reporting a "
                    f"negative or null result (model: {e(model)}); a "
                    f"well-designed null result is still evidence, and tier "
                    f"reflects design, not importance.")
        return (f"Tier C because it is an animal intervention or observation "
                f"study measuring an organismal outcome (model: {e(model)}); "
                f"tier describes study design, not quality -- animal evidence "
                f"can be rigorous and still sit below direct human data.")
    if tier == "D - Mechanistic/Review":
        if category == "Review":
            return ("Tier D because it is a review or synthesis of existing "
                    "evidence rather than a new primary result; tier "
                    "describes study design (secondary synthesis), not "
                    "quality.")
        if category == "Side effect":
            return (f"Tier D because it reports a mechanistic or side-effect "
                    f"finding (model: {e(model)}) rather than a primary "
                    f"organismal health outcome; tier describes study design, "
                    f"not quality.")
        return (f"Tier D because it is mechanistic or in-vitro work (model: "
                f"{e(model)}), not a whole-organism health-outcome study; "
                f"tier describes study design, not quality -- this is often "
                f"exactly where causal biology gets established.")
    if tier == "Preprint":
        return ("This is a preprint, not yet peer-reviewed -- treat its "
                "findings as provisional until formal publication. Preprints "
                "sit outside the A-D tier ladder for that reason, not "
                "because the work is weak.")
    if tier == "Registered trial":
        return ("This is a registered clinical trial with no results "
                "reported yet. There is no tier grade until results are "
                "published -- registration alone is not evidence of an "
                "effect.")
    return f"Tier {e(tier or '—')}; tier describes study design, not quality."


def _truncate_at_sentence(text, limit=600):
    """First ~limit chars of text, cut at the end of the last full sentence
    at-or-before the limit. Falls back to a word-boundary cut (+ ellipsis)
    only when there is no sentence boundary at all before the limit -- never
    a mid-word cut. Returns (snippet, was_truncated)."""
    text = text.strip()
    if len(text) <= limit:
        return text, False
    window = text[:limit]
    cut = max(window.rfind(". "), window.rfind(".\n"),
              window.rfind("? "), window.rfind("! "))
    if cut == -1:
        cut = window.rfind(" ")
        if cut == -1:
            cut = limit
        return text[:cut].rstrip() + "…", True
    return text[:cut + 1], True


def _cite_block(sid, title, url):
    """APA-style line + BibTeX for the ATLAS RECORD (not the original paper
    -- Ukol 2 item 6). Built with plain concatenation, not nested f-string
    braces, on purpose: BibTeX's own {...} syntax and an f-string's {{
    escaping are an easy way to silently produce the wrong literal braces."""
    year = (RECORD_DATE_BY_SID.get(sid) or RECORD_DATE_FALLBACK or "2026")[:4]
    if not year.isdigit():
        year = "2026"
    apa = (f"Barton, O. ({year}). {title} — evidence-graded record {sid}. "
           f"In Oliver's mTOR Atlas. {url} · Dataset DOI 10.5281/zenodo.22059963")
    bibtex_lines = [
        "@misc{atlas_" + sid + ",",
        "  author       = {Barton, Oliver},",
        "  title        = {{" + title + "} --- evidence-graded record " + sid + "},",
        "  howpublished = {Oliver's mTOR Atlas},",
        "  year         = {" + year + "},",
        "  url          = {" + url + "},",
        "  note         = {Dataset DOI: 10.5281/zenodo.22059963}",
        "}",
    ]
    return apa, "\n".join(bibtex_lines)



def study_page(s, ent_by_sid, haspage):
    sid = s["sid"]
    code, label, colour = tier_bits(s.get("tier"))
    url = f"{SITE}/study/{sid}/"
    title = s.get("title") or sid
    desc = (s.get("finding") or s.get("abstract") or title)[:300]
    record_date = RECORD_DATE_BY_SID.get(sid, RECORD_DATE_FALLBACK)
    noindex = sid in NOINDEX_STUDIES

    ld = {
        "@context": "https://schema.org", "@type": "ScholarlyArticle",
        "headline": title, "name": title,
        "datePublished": str(s.get("year") or ""),
        "url": url, "inLanguage": "en",
        "isPartOf": dict(DATASET_REF),
    }
    if record_date and record_date != "unknown":
        ld["dateModified"] = record_date
    if s.get("journal"):
        ld["publication"] = {"@type": "Periodical", "name": s["journal"]}
    if s.get("authors"):
        ld["author"] = [{"@type": "Person", "name": a.strip()}
                        for a in re.split(r";|,(?![^(]*\))", s["authors"])
                        if a.strip() and "et al" not in a.lower()][:12]
    ids = []
    if s.get("doi"):
        ids.append({"@type": "PropertyValue", "propertyID": "DOI", "value": s["doi"]})
        ld["sameAs"] = "https://doi.org/" + s["doi"]
    if s.get("pmid"):
        ids.append({"@type": "PropertyValue", "propertyID": "PMID", "value": s["pmid"]})
    if ids:
        ld["identifier"] = ids
    if s.get("abstract"):
        # Full text stays in JSON-LD for machines even though the visible
        # <p class="abstract"> below is truncated (Ukol 2 item 5) -- Google
        # does not count a JSON-LD-only field as visible duplicate content.
        ld["abstract"] = s["abstract"]

    rows = [("Evidence tier", f'<span class="tier" style="background:{colour}">'
                              f'{e(code)}</span> {e(label)}'),
            ("Study type", e(s.get("pyramid") or s.get("category") or "—")),
            ("Model system", e(s.get("model") or s.get("ai_species") or "—")),
            ("Journal", e(s.get("journal") or "—")),
            ("Year", e(s.get("year") or "—")),
            ("Peer reviewed", e(s.get("peer") or "—")),
            ("Record last updated", e(record_date if record_date != "unknown" else "—"))]
    links = []
    if s.get("doi"):
        links.append(f'<a href="https://doi.org/{e(s["doi"])}">DOI {e(s["doi"])}</a>')
    if s.get("pmid"):
        links.append(f'<a href="https://pubmed.ncbi.nlm.nih.gov/{e(s["pmid"])}/">'
                     f'PMID {e(s["pmid"])}</a>')
    if s.get("pmcid"):
        links.append(f'<a href="https://www.ncbi.nlm.nih.gov/pmc/articles/'
                     f'{e(s["pmcid"])}/">Free full text ({e(s["pmcid"])})</a>')
    if links:
        rows.append(("Source", " · ".join(links)))

    ents = ent_by_sid.get(sid, [])
    tag_html = "".join(ent_ref(x, haspage) for x in ents)

    body = [f"<h1>{e(title)}</h1>",
            f'<p class="meta">{e(s.get("authors") or "")} · {e(s.get("year") or "")} · '
            f'<em>{e(s.get("journal") or "")}</em> · Atlas ID <code>{e(sid)}</code></p>']

    # 1) What this study shows -- finding + one sentence on why this tier
    # (Ukol 2 item 2).
    body.append("<h2>What this study shows</h2>")
    if s.get("finding"):
        body.append(f'<p class="summary">{e(s["finding"])}</p>')
    body.append(f'<p class="tier-why">{tier_reason(s)}</p>')

    body.append("<h2>At a glance</h2><table class=\"kv\">")
    for k, v in rows:
        body.append(f"<tr><td><strong>{e(k)}</strong></td><td>{v}</td></tr>")
    body.append("</table>")

    # 2) Extracted findings -- ALWAYS visible (no lv-hide-beginner: this is
    # the most valuable curatorial content on the page) whenever ANY field
    # is present, now including the four Phase-4 deep-extraction fields
    # (dose/n/effect size/limitations) that sync_airtable.py started pulling
    # down in this same commit -- see fetch_studies() and projektova pamet
    # entities-bake-path for the same class of bug on the entities side.
    ef_fields = [("Intervention", "ai_intervention"), ("Target", "ai_target"),
                 ("Model", "ai_species"), ("Effect", "ai_effect"),
                 ("Dose", "ai_dose"), ("Sample size", "ai_samplesize"),
                 ("Effect size", "ai_effectsize"), ("Limitations", "ai_limitations")]
    if any(s.get(f) for _, f in ef_fields):
        body.append("<h2>Extracted findings</h2><table class=\"kv\">")
        for k, f in ef_fields:
            if s.get(f):
                body.append(f"<tr><td><strong>{e(k)}</strong></td><td>{e(s[f])}</td></tr>")
        body.append("</table>")

    # 3) In the Atlas -- every internal cross-link this record has, each
    # with a sentence of context instead of a bare list (Ukol 2 item 4).
    atlas_blocks = []
    if tag_html:
        atlas_blocks.append(f'<h3>Related topics</h3><div class="tags">{tag_html}</div>')
    gap_hits = GAPS_BY_SID.get(sid, [])
    if gap_hits:
        items = "".join(f'<li>Cited as supporting evidence for the open question '
                        f'<a href="{e(u)}">{e(t)}</a>.</li>' for t, u in gap_hits)
        atlas_blocks.append(f"<h3>Open questions that cite this study</h3><ul>{items}</ul>")
    answer_hits = ANSWERS_BY_SID.get(sid, [])
    if answer_hits:
        items = "".join(f'<li>Discussed in the plain-language answer '
                        f'<a href="{e(u)}">{e(t)}</a>.</li>' for t, u in answer_hits)
        atlas_blocks.append(f"<h3>Answers that reference this study</h3><ul>{items}</ul>")
    for les in ACADEMY_BY_SID.get(sid, []):
        atlas_blocks.append('<h3>Learn the biology</h3>'
                            '<p>Want to understand the biology behind this study? '
                            '&rarr; ' + f'<a href="{e(les["url"])}">{e(les["title"])}</a></p>')
        break
    if atlas_blocks:
        body.append("<h2>In the Atlas</h2>")
        body.extend(atlas_blocks)

    # 4) Abstract -- truncated, moved below "In the Atlas" (Ukol 2 item 5):
    # the full PubMed abstract is exactly the text Google was reading as
    # thin/duplicate content.
    if s.get("abstract"):
        snippet, truncated = _truncate_at_sentence(s["abstract"], 600)
        more = ""
        if truncated:
            if s.get("pmid"):
                more = (f' <a href="https://pubmed.ncbi.nlm.nih.gov/{e(s["pmid"])}/">'
                       f'Read the full abstract on PubMed &rarr;</a>')
            elif s.get("doi"):
                more = f' <a href="https://doi.org/{e(s["doi"])}">Read the full abstract &rarr;</a>'
        body.append(f'<div class="lv-hide-beginner"><h2>Abstract</h2>'
                    f'<p class="abstract">{e(snippet)}{more}</p></div>')

    # 5) Cite this record -- the ATLAS RECORD, not the original paper
    # (Ukol 2 item 6).
    apa, bibtex = _cite_block(sid, title, url)
    body.append('<h2>Cite this record</h2><pre class="cite">'
               + e(apa) + "\n\n" + e(bibtex) + "</pre>")

    body.append(f'<p><a class="cta" href="{SITE}/#studies">Open in the Atlas explorer</a></p>')

    crumb = f'<a href="{SITE}/">Oliver\'s mTOR Atlas</a> · <a href="{SITE}/#studies">Studies</a> · {e(sid)}'
    bc = breadcrumb_ld([("Oliver's mTOR Atlas", SITE + "/"),
                        ("Studies", SITE + "/#studies"),
                        (sid, None)])
    robots = "noindex, follow" if noindex else "index, follow"
    return url, shell(f"{title} | Oliver's mTOR Atlas", desc, url, [ld, bc],
                      "\n".join(body), crumb, active_tab="studies",
                      level_switch=True, robots=robots)


# ----------------------------------------------------------- entity pages ---

def entity_page(ent, studies_by_sid, all_entities, haspage):
    d = TYPE_DIR.get(ent["type"], "entity")
    slug = slugify(ent["name"])
    url = f"{SITE}/{d}/{slug}/"
    linked = [studies_by_sid[x] for x in ent["studies"] if x in studies_by_sid]
    linked.sort(key=lambda s: (["A - Systematic review", "B - Human", "C - Animal",
                                "D - Mechanistic/Review"].index(s["tier"])
                               if s.get("tier") in TIER_LABEL and s["tier"] in
                               ["A - Systematic review", "B - Human", "C - Animal",
                                "D - Mechanistic/Review"] else 9,
                               -(s.get("year") or 0)))

    counts = {}
    for s in linked:
        counts[tier_bits(s.get("tier"))[0]] = counts.get(tier_bits(s.get("tier"))[0], 0) + 1

    syn = [x.strip() for x in re.split(r"[;\n]", ent.get("synonyms") or "")
           if x.strip() and not x.lower().startswith("pozn")]
    desc = (ent.get("desc") or
            f"{ent['name']} in the mTOR pathway: {len(linked)} curated studies, "
            f"graded by strength of evidence.")[:300]

    ld = {"@context": "https://schema.org", "@type": "DefinedTerm",
          "name": ent["name"], "description": desc, "url": url,
          "inDefinedTermSet": {"@type": "DefinedTermSet",
                               "name": "Oliver's mTOR Atlas", "url": SITE + "/"}}
    if syn:
        ld["alternateName"] = syn
    if ent["name"] in EXTERNAL_IDS:
        ld["sameAs"] = EXTERNAL_IDS[ent["name"]]

    body = [f"<h1>{e(ent['name'])}</h1>",
            f'<p class="meta">{e(ent["type"])} · {len(linked)} studies in the Atlas'
            + (f' · also known as {e(", ".join(syn[:6]))}' if syn else "") + "</p>"]
    explain = entity_explain_for(ent["name"])
    if explain and ent.get("desc"):
        body.append(f'<p class="summary lv-student">{e(ent["desc"])}</p>')
        body.append(f'<p class="summary lv-beginner">{e(explain["beginner"])}</p>')
        body.append(f'<p class="summary lv-research">{e(explain["research"])}</p>')
    elif ent.get("desc"):
        body.append(f'<p class="summary">{e(ent["desc"])}</p>')

    body.append("<h2>Evidence at a glance</h2><table class=\"ev\">"
                "<tr><th>Tier</th><th>What it means</th><th>Studies</th></tr>")
    for key, (code, label, colour) in TIER_LABEL.items():
        n = counts.get(code, 0)
        if code == "—" or n == 0:
            continue
        body.append(f'<tr><td data-l="Tier"><span class="tier" style="background:{colour}">{code}'
                    f'</span></td><td data-l="Meaning">{e(label)}</td><td data-l="Studies">{n}</td></tr>')
    body.append("</table>")
    if not counts.get("A") and not counts.get("B"):
        body.append("<p><em>No direct human evidence in the Atlas for this entity yet — "
                    "everything below rests on animal or mechanistic work.</em></p>")

    body.append("<h2>Studies</h2><table class=\"st\">"
                "<tr><th>Study</th><th>Year</th><th>Tier</th><th>Finding</th></tr>")
    for s in linked:
        code, _, colour = tier_bits(s.get("tier"))
        body.append(
            f'<tr><td data-l="Study"><a href="/study/{e(s["sid"])}/">{e(s["sid"])}</a></td>'
            f'<td data-l="Year">{e(s.get("year") or "")}</td>'
            f'<td data-l="Tier"><span class="tier" style="background:{colour}">{code}</span></td>'
            f'<td data-l="Finding">{e((s.get("finding") or s.get("title") or "")[:200])}</td></tr>')
    body.append("</table>")

    # Sousední entity podle sdílených studií.
    shared = {}
    mine = set(ent["studies"])
    for o in all_entities:
        if o["id"] == ent["id"]:
            continue
        n = len(mine & set(o["studies"]))
        if n:
            shared[o["id"]] = (n, o)
    top = sorted(shared.values(), key=lambda kv: -kv[0])[:12]
    if top:
        chips = []
        for n, o in top:
            d2, s2 = TYPE_DIR.get(o["type"], "entity"), slugify(o["name"])
            count = f' <span style="color:var(--muted-count,#7C7569)">{n}</span>'
            if (d2, s2) in haspage:
                chips.append(f'<a href="/{d2}/{s2}/">{e(o["name"])}{count}</a>')
            else:
                chips.append(f'<span>{e(o["name"])}{count}</span>')
        body.append('<h2>Related entities</h2><div class="tags">'
                    + "".join(chips) + "</div>")

    body.append(f'<p><a class="cta" href="{SITE}/#entities">Open in the Atlas explorer</a></p>')
    crumb = (f'<a href="{SITE}/">Oliver\'s mTOR Atlas</a> · '
             f'<a href="{SITE}/#entities">{e(ent["type"])}</a> · {e(ent["name"])}')
    bc = breadcrumb_ld([("Oliver's mTOR Atlas", SITE + "/"),
                        (ent["type"], SITE + "/#entities"),
                        (ent["name"], None)])
    return url, d, slug, shell(f"{ent['name']} — evidence in the mTOR pathway | Oliver's mTOR Atlas",
                               desc, url, [ld, bc], "\n".join(body), crumb, active_tab="map",
                               level_switch=bool(explain and ent.get("desc")))


# ------------------------------------------------------- question/gap pages ---
# Added 2026-08-04. The "Open Questions" tab (knowledge gaps + testable
# hypotheses, atlas_data/gaps_baked.json) is the Atlas's most original
# content -- not an aggregated abstract, but synthesis a crawler can't get
# anywhere else. It lived only inside the JS SPA. FAQPage/Question schema is
# exactly the shape AI answer engines lift straight into a response, so this
# is the single highest-leverage GEO gap on the site.

# --- SEO P0 Ukol 11.4 (2026-09-02): answers->question backlinks (removal): the hand-picked pair above (2026-08-29) is now
# handled generally by ANSWER_GAP_BACKLINKS, defined earlier in this file
# alongside ANSWERS_BY_SID -- see gap_page() below. ---

GAP_TYPE_LABEL = {
    "Evidence desert": "No study yet tests this",
    "Contradiction / tension": "Studies point in different directions",
    "Mechanism-to-outcome gap": "Mechanism shown, outcome untested",
    "Human-endpoint gap": "No human trial endpoint yet",
}


def gap_page(g, studies_by_sid):
    slug = slugify(g["title"])
    url = f"{SITE}/question/{slug}/"
    kind = GAP_TYPE_LABEL.get(g.get("type"), g.get("type") or "Open question")
    conf = g.get("conf")
    desc = (g.get("basis_beginner") or g.get("basis") or g["title"])[:300]

    qa = [
        ("What's the evidence gap?", g.get("basis_beginner") or g.get("basis") or ""),
        ("What's the testable hypothesis?", g.get("hyp_beginner") or g.get("hyp") or ""),
        ("How could this be tested?", g.get("exp") or ""),
    ]
    ld = {"@context": "https://schema.org", "@type": "FAQPage",
          "mainEntity": [
              {"@type": "Question", "name": q,
               "acceptedAnswer": {"@type": "Answer", "text": re.sub(r"<[^>]+>", "", a)}}
              for q, a in qa if a]}

    body = [f"<h1>{e(g['title'])}</h1>",
            f'<p class="meta">{e(kind)}'
            + (f' · confidence {e(round(conf*100))}%' if conf is not None else "")
            + f' · Atlas ID <code>{e(g["id"])}</code></p>']
    lv_needed = False
    if g.get("basis_beginner"):
        body.append(f'<h2>The gap</h2><p class="summary">{g["basis_beginner"]}</p>')
        if g.get("basis") and g["basis"] != g["basis_beginner"]:
            body.append(f'<p class="meta lv-hide-beginner"><em>Technical framing:</em> {e(g["basis"])}</p>')
            lv_needed = True
    elif g.get("basis"):
        body.append(f'<h2>The gap</h2><p class="summary">{e(g["basis"])}</p>')
    if g.get("hyp_beginner"):
        body.append(f'<h2>The hypothesis</h2><p>{g["hyp_beginner"]}</p>')
        if g.get("hyp") and g["hyp"] != g["hyp_beginner"]:
            body.append(f'<p class="meta lv-hide-beginner"><em>Technical framing:</em> {e(g["hyp"])}</p>')
            lv_needed = True
    elif g.get("hyp"):
        body.append(f'<h2>The hypothesis</h2><p>{e(g["hyp"])}</p>')
    if g.get("exp"):
        body.append(f'<h2>How it could be tested</h2><p>{e(g["exp"])}</p>')

    links = [f'<a href="/study/{e(sid)}/">{e(sid)}</a>'
             for sid in g.get("studies") or [] if sid in studies_by_sid]
    if links:
        body.append(f'<h2>Related studies</h2><p>{" · ".join(links)}</p>')
    backlinks = ANSWER_GAP_BACKLINKS.get(slug, [])
    if backlinks:
        label = "Discussed in the plain-language answer" if len(backlinks) == 1 \
            else "Discussed in these plain-language answers"
        items = " · ".join(f'<a href="{e(u)}">{e(t)}</a>' for t, u in backlinks)
        body.append(f'<p class="meta">{label}: {items}</p>')
    body.append(f'<p><a class="cta" href="{SITE}/#questions">Open in the Atlas explorer</a></p>')

    crumb = (f'<a href="{SITE}/">Oliver\'s mTOR Atlas</a> · '
             f'<a href="{SITE}/#questions">Open Questions</a> · {e(g["title"])}')
    bc = breadcrumb_ld([("Oliver's mTOR Atlas", SITE + "/"),
                        ("Open Questions", SITE + "/#questions"),
                        (g["title"], None)])
    return url, slug, shell(f"{g['title']} | Open Questions | Oliver's mTOR Atlas",
                            desc, url, [ld, bc], "\n".join(body), crumb, active_tab="questions",
                            level_switch=lv_needed)


# --------------------------------------------------------- author pages ---
# Added 2026-08-04. The five scientist bio cards (AUTHOR_BIOS in index.html)
# are hand-written narrative content -- exactly the kind of thing that signals
# authorship/expertise (E-E-A-T) to Google and gives an AI answer engine a
# citable source for "who discovered mTORC2" style questions. Until now they
# only rendered inside a JS modal (showAuthorBio()), invisible to a
# non-JS crawler. Source of truth stays index.html; this script reads a baked
# export (atlas_data/author_bios_baked.json) so the Python build has no Node
# dependency. If AUTHOR_BIOS in index.html changes, re-export it -- see the
# comment at the top of that JSON file... actually there isn't one yet, so:
# re-extract with a small Node snippet that assigns AUTHOR_BIOS and
# JSON.stringifies it (same technique used to build this file originally).

def build_author_index(studies):
    """Replicates buildAuthorsIndex() from index.html in Python: split each
    study's `authors` field on ';', strip trailing 'et al.'. Must stay in
    sync with the JS version or a name matches in the SPA but not here."""
    idx = {}
    for s in studies:
        for part in (s.get("authors") or "").split(";"):
            name = re.sub(r"\s*et al\.?\s*$", "", part, flags=re.I).strip()
            if name:
                idx.setdefault(name, []).append(s)
    return idx


def author_page(key, bio, studies):
    slug = slugify(bio["full"])
    url = f"{SITE}/author/{slug}/"
    desc = f"{bio['full']} ({bio['role']}) — publication timeline in Oliver's mTOR Atlas."[:300]

    ld = {"@context": "https://schema.org", "@type": "Person",
          "name": bio["full"], "description": bio["role"], "url": url}
    if bio.get("photo"):
        # JSON-LD image musi byt absolutni URL -- konzumenti schema.org
        # relativni cestu nerozresi, protoze strukturovana data ctou mimo
        # kontext stranky. <img src> nize relativni zustava. Doplneno
        # 2026-09-05 spolu s vytazenim base64 fotek do /img/people/.
        ld["image"] = (SITE + bio["photo"]) if bio["photo"].startswith("/") else bio["photo"]

    ordered = sorted(studies, key=lambda s: (s.get("year") or 0))
    body = [f"<h1>{e(bio['full'])}</h1>",
            f'<p class="meta">{e(bio["role"])}'
            + (f' · {bio["sub"]}' if bio.get("sub") else "") + "</p>"]
    if bio.get("photo"):
        cred = f'<div style="font-size:12px;color:var(--soft);margin:-12px 0 16px">{bio["credit"]}</div>' if bio.get("credit") else ""
        body.append(f'<img src="{e(bio["photo"])}" alt="{e(bio["full"])}" loading="lazy" '
                    f'style="max-width:220px;border-radius:4px;margin:0 0 6px" '
                    f'onerror="this.style.display=\'none\'">' + cred)
    for p in bio.get("story") or []:
        body.append(f"<p>{p}</p>")

    if ordered:
        body.append("<h2>Milestones in the Atlas</h2><table class=\"st\">"
                    "<tr><th>Study</th><th>Year</th><th>Tier</th><th>Finding</th></tr>")
        for s in ordered:
            if not s.get("sid"):
                continue
            code, _, colour = tier_bits(s.get("tier"))
            hl = (bio.get("highlights") or {}).get(s["sid"])
            finding = hl if hl else (s.get("finding") or s.get("title") or "")
            finding_html = finding if hl else e(finding[:220])
            body.append(
                f'<tr><td data-l="Study"><a href="/study/{e(s["sid"])}/">{e(s["sid"])}</a></td>'
                f'<td data-l="Year">{e(s.get("year") or "")}</td>'
                f'<td data-l="Tier"><span class="tier" style="background:{colour}">{code}</span></td>'
                f'<td data-l="Finding">{finding_html}</td></tr>')
        body.append("</table>")
    body.append(f'<p><a class="cta" href="{SITE}/#authors">Open in the Atlas explorer</a></p>')

    crumb = (f'<a href="{SITE}/">Oliver\'s mTOR Atlas</a> · '
             f'<a href="{SITE}/#authors">Researchers</a> · {e(bio["full"])}')
    bc = breadcrumb_ld([("Oliver's mTOR Atlas", SITE + "/"),
                        ("Researchers", SITE + "/#authors"),
                        (bio["full"], None)])
    return url, slug, shell(f"{bio['full']} — {bio['role']} | Oliver's mTOR Atlas",
                            desc, url, [ld, bc], "\n".join(body), crumb, active_tab="authors")


# --------------------------------------------------------------- about page ---

# --- SEO P0 Ukol 11.3 (2026-09-02): /changelog/ ---
def changelog_page(studies):
    """Static /changelog/ page -- Ukol 11.3 (SEO P0 brief 2026-09-02): a
    public corrections log, requested by the 2026-08-23 audit as a missing
    E-E-A-T signal (a site that grades OTHER people's evidence should be
    checkable itself). Built from the same two changelog JSON files
    _load_record_dates() already reads for "Record last updated" -- one
    entry per correction: SID, which field changed, and the curator's own
    one-sentence reason (the `why` field), never the full old/new diff
    text (some of those run to several paragraphs and belong in the
    underlying audit docs, not a public list).

    Same date caveat as _load_record_dates(): neither changelog file
    carries a true per-entry date, only the audit-round association
    (2026-07-29 for both rounds currently on file) -- shown here as-is,
    flagged, not invented as a fake precise timestamp."""
    url = f"{SITE}/changelog/"
    AUDIT_ROUND_DATE = "2026-07-29"

    entries = []  # (date, sid, field, why)
    for fn in ("AUDIT_changelog_studies.json", "REVIEW_changelog_studies.json"):
        p = os.path.join(DATA, fn)
        if not os.path.exists(p):
            continue
        try:
            rows = json.load(open(p, encoding="utf-8"))
        except Exception:
            continue
        for row in rows:
            sid = row.get("sid")
            why = row.get("why")
            if sid and why:
                entries.append((AUDIT_ROUND_DATE, sid, row.get("field") or "—", why))
    # novejsi datum prvni; pri stejnem datu podle SID pro stabilni poradi
    entries.sort(key=lambda t: (t[0], t[1]), reverse=True)

    if entries:
        rows_html = "".join(
            f'<tr><td data-l="Date">{e(d)}</td>'
            f'<td data-l="Study"><a href="{SITE}/study/{e(sid)}/">{e(sid)}</a></td>'
            f'<td data-l="Field">{e(field)}</td>'
            f'<td data-l="What changed and why">{e(why)}</td></tr>'
            for d, sid, field, why in entries)
        table_html = (f'<table class="st"><tr><th>Date</th><th>Study</th>'
                      f'<th>Field</th><th>What changed and why</th></tr>'
                      f'{rows_html}</table>')
        count_line = (f"<p>{len(entries)} corrections on record, from "
                      f"{len(set(e2[1] for e2 in entries))} distinct study records.</p>")
    else:
        table_html = "<p><em>No corrections on record yet.</em></p>"
        count_line = ""

    ld = {"@context": "https://schema.org", "@type": "CollectionPage",
          "name": "Corrections log | Oliver's mTOR Atlas", "url": url,
          "isPartOf": dict(DATASET_REF)}
    crumb = f'<a href="{SITE}/">Oliver\'s mTOR Atlas</a> · Corrections log'
    bc = breadcrumb_ld([("Oliver's mTOR Atlas", SITE + "/"),
                        ("Corrections log", None)])

    body = f"""<h1>Corrections log</h1>
<p class="summary">Every recorded correction to a study record's finding or
supporting fields, with the curator's own reason for the change. This is
the log referenced from <a href="{SITE}/about/">About &amp; Methodology</a>'s
correction policy.</p>
{count_line}
<p><em>Dates below mark the audit round in which each correction was made,
not the individual edit's own timestamp -- neither source file this page
reads carries a true per-entry date. See
<a href="{SITE}/about/">About &amp; Methodology</a> for how the review
process itself works.</em></p>
{table_html}
<p><a class="cta" href="{SITE}/about/">About &amp; Methodology</a></p>
"""
    return url, shell(
        "Corrections log | Oliver's mTOR Atlas",
        "Every recorded correction to an Oliver's mTOR Atlas study record, "
        "with the field changed and the curator's reason -- a public "
        "accountability log.",
        url, [ld, bc], body, crumb, active_tab=None)


def pathway_page(model, entities, haspage):
    """Static /pathway/ page -- Ukol 5 (SEO P0 handover 2026-09-04): the
    interactive pathway map (SPA #view=map) is a canvas-drawn diagram --
    zero indexable text for a crawler that doesn't execute JS. This page
    is NOT a second copy of the diagram; it's the same underlying model
    (pathway/model.json, read-only, generated by build_pathway_model.py)
    written out as prose + a full reference table, so the mechanistic
    content the SPA already has becomes crawlable.

    Deliberately ONE page, not two: an earlier draft split this into
    /pathway/ (routes) and /mechanism/ (interaction table), but the data
    model doesn't distinguish the two -- a route IS a curated walk through
    a subset of the interaction table. Splitting them would mean a second
    thin page and a false distinction; Petr agreed (2026-09-05) to keep it
    as one page, same shape as changelog_page(studies).

    `model` is pathway/model.json's already-parsed dict. `entities` /
    `haspage` are the same objects main() already builds for every other
    page -- reused here so node links point at real entity pages (never a
    404), via the same ent_ref() every other page uses."""
    url = f"{SITE}/pathway/"
    entities_by_name = {x["name"]: x for x in entities}
    node_id_to_entity = {v: k for k, v in ENTITY_NAME_TO_NODE_ID.items()}
    tier_color = {t[0]: t[2] for t in TIER_LABEL.values()}

    def node_link(node_id):
        name = node_id_to_entity.get(node_id, node_id)
        ent = entities_by_name.get(name)
        if ent:
            return ent_ref(ent, haspage)
        return f'<span>{e(node_id)}</span>'

    counts = model["meta"]["counts"]

    # ---- 11 guided "routes", each a narrated walk through a subset of
    # the interaction graph -------------------------------------------
    toc_items = []
    route_html = []
    for r in model["routes"]:
        rid = "route-" + slugify(r["id"])
        toc_items.append(f'<li><a href="#{rid}">{e(r["name"])}</a></li>')
        j = r.get("journey", {}) or {}
        steps_html = []
        for n, st in enumerate(r.get("steps", []), 1):
            iid = st.get("interaction", "")
            anchor = "int-" + slugify(iid)
            matters = st.get("matters", "")
            matters_html = f'<p class="summary">{e(matters)}</p>' if matters else ""
            steps_html.append(f"""<li class="step">
<p class="step-what"><strong>{n}. {e(st.get("what", ""))}</strong>
<a class="step-jump" href="#{anchor}">mechanism &darr;</a></p>
<p>{e(st.get("why", ""))}</p>
<p><em>{e(st.get("changed", ""))}</em> {e(st.get("consequence", ""))}</p>
<p class="tier-why">Certainty: {e(st.get("certainty", ""))}</p>
{matters_html}</li>""")
        bt = j.get("breakthrough") or {}
        bt_html = ""
        if bt.get("sid"):
            bt_html = (f'<p><strong>Key paper:</strong> '
                       f'<a href="{SITE}/study/{e(bt["sid"])}/">{e(bt["sid"])}</a>'
                       f' &mdash; {e(bt.get("why", ""))}</p>')
        story = r.get("story") or e(r.get("summary", ""))
        route_html.append(f"""<section class="route-block" id="{rid}">
<h2>{e(r["name"])}</h2>
<p class="meta">{e(r.get("territory", ""))}</p>
<p class="summary">{e(j.get("question", r.get("summary", "")))}</p>
<p>{story}</p>
<ol class="step-list">
{"".join(steps_html)}
</ol>
{bt_html}
<p class="tier-why"><strong>Evidence base:</strong> {e(j.get("evidence", ""))}</p>
<p class="tier-why"><strong>Still unresolved:</strong> {e(j.get("unknowns", ""))}</p>
</section>""")

    # ---- full reference table of all interactions ----------------------
    rows = []
    for i in model["interactions"]:
        ev = i.get("evidence", {}) or {}
        best = ev.get("best_tier", "—")
        color = tier_color.get(best, "#7C7569")
        supporting = ev.get("supporting", []) or []
        study_links = ", ".join(
            f'<a href="{SITE}/study/{e(sid)}/">{e(sid)}</a>' for sid in supporting) or "—"
        conflicting = ev.get("conflicting") or []
        conflict_note = (f' <span class="tier-why">(conflicting: '
                          f'{", ".join(e(s) for s in conflicting)})</span>'
                          if conflicting else "")
        mech = i.get("mechanism", "")
        mech_beginner = i.get("mechanism_beginner") or mech
        rows.append(f"""<tr id="int-{slugify(i["id"])}">
<td data-l="Source">{node_link(i["source"])}</td>
<td data-l="Effect">{e(i.get("effect", ""))}</td>
<td data-l="Target">{node_link(i["target"])}</td>
<td data-l="Type">{e(i.get("type", ""))}</td>
<td data-l="Mechanism"><span class="lv-beginner">{e(mech_beginner)}</span>\
<span class="lv-student">{e(mech)}</span>\
<span class="lv-research">{e(mech)}</span></td>
<td data-l="Tier"><span class="tier" style="background:{color}">{e(best)}</span></td>
<td data-l="Studies">{study_links}{conflict_note}</td>
</tr>""")

    table_html = ("""<table class="st int-table"><tr><th>Source</th><th>Effect</th>
<th>Target</th><th>Type</th><th>Mechanism</th><th>Tier</th><th>Studies</th></tr>"""
                  + "".join(rows) + "</table>")

    ld = {"@context": "https://schema.org", "@type": "CollectionPage",
          "name": "The mTOR pathway map | Oliver's mTOR Atlas", "url": url,
          "isPartOf": dict(DATASET_REF)}
    crumb = f'<a href="{SITE}/">Oliver\'s mTOR Atlas</a> · Pathway map'
    bc = breadcrumb_ld([("Oliver's mTOR Atlas", SITE + "/"), ("Pathway map", None)])

    body = f"""<h1>The mTOR pathway, node by node</h1>
<p class="summary">The same curated model behind the Atlas's interactive
pathway map ({counts["nodes"]} nodes, {counts["interactions"]} interactions,
{counts["routes"]} guided routes, {counts["loops"]} feedback loops), written
out as text: eleven guided walks through the network, each followed by the
full interaction reference table below. For the drag-and-explore diagram
itself, see the <a href="{SITE}/#view=map">interactive pathway map</a>
(requires JavaScript).</p>
<p><strong>Guided routes:</strong></p>
<ol>{"".join(toc_items)}</ol>
{"".join(route_html)}
<h2 id="interactions">All {counts["interactions"]} interactions</h2>
<p class="summary">Every modelled interaction in the network: source,
direction of effect, target, mechanism, the strongest evidence tier behind
it, and the studies that support it. Rows are the same interactions the
eleven routes above walk through, cross-referenced by each step's
&quot;mechanism&quot; link.</p>
{table_html}
"""
    extra_css = """
.route-block{margin-top:38px}
.step-list{padding-left:0;list-style:none}
.step-list .step{margin-bottom:16px;padding-left:16px;border-left:2px solid var(--line)}
.step-what{margin-bottom:4px}
.step-jump{font-size:12px;margin-left:8px;white-space:nowrap}
table.int-table{font-size:13px}
table.int-table td[data-l="Mechanism"]{max-width:420px}
"""
    return url, shell(
        "The mTOR pathway, node by node | Oliver's mTOR Atlas",
        f"All {counts['nodes']} nodes and {counts['interactions']} interactions "
        "of the curated mTOR pathway model, as eleven guided routes plus a full "
        "evidence-graded interaction table -- the static, crawlable form of the "
        "Atlas's interactive pathway map.",
        url, [ld, bc], body, crumb, active_tab="map", level_switch=True,
        extra_css=extra_css)


def events_page(events):
    """Static /events/ page -- Ukol 5 (SEO P0 handover 2026-09-04): the
    Timeline tab's conference/meeting list (#eventsView in index.html) is
    filled by renderEvents() at JS runtime. prerender_tabs.js already bakes
    that same HTML statically into index.html so a crawler sees something
    there, but it's still one collapsed-by-default tab inside a single-page
    app, with no URL of its own to link to or cite. This page is the same
    atlas_data/events_baked.json content at its own indexable address,
    always fully expanded -- no accordion JS -- the opposite of the SPA's
    click-to-expand list, on purpose: nothing here needs to be interactive
    for a page whose whole point is to be read by a crawler in one pass."""
    url = f"{SITE}/events/"
    today = datetime.date.today().isoformat()

    def block(ev):
        auth = ""
        if ev.get("authors"):
            auth = (f'<p class="tier-why"><strong>Speakers in the Atlas '
                    f'(authors):</strong> {e(", ".join(ev["authors"]))}</p>')
        return f"""<article class="ev-block">
<h3>{e(ev.get("name", ""))}</h3>
<p class="meta">{e(ev.get("dates", ""))} &middot; {e(ev.get("city", ""))}, \
{e(ev.get("country", ""))} &middot; {e(ev.get("venue", ""))}</p>
<p>{e(ev.get("desc", ""))}</p>
<p class="tier-why"><strong>Why it matters for mTOR:</strong> {e(ev.get("mtor", ""))}</p>
<p class="tier-why"><strong>Organizers:</strong> {e(ev.get("organizers", ""))}</p>
<p class="tier-why"><strong>Speakers:</strong> {e(ev.get("speakers", ""))}</p>
{auth}<p><a href="{e(ev.get("url", ""))}" target="_blank" rel="noopener">Conference site &rarr;</a></p>
</article>"""

    upcoming = sorted([ev for ev in events if (ev.get("end") or "") >= today],
                       key=lambda ev: ev.get("start", ""))
    past = sorted([ev for ev in events if (ev.get("end") or "") < today],
                  key=lambda ev: ev.get("start", ""), reverse=True)

    sections = []
    if upcoming:
        sections.append(f'<h2>Upcoming ({len(upcoming)})</h2>'
                         + "".join(block(ev) for ev in upcoming))
    if past:
        sections.append(f'<h2>Past ({len(past)})</h2>'
                         + "".join(block(ev) for ev in past))

    ld = {"@context": "https://schema.org", "@type": "CollectionPage",
          "name": "mTOR conferences & meetings | Oliver's mTOR Atlas", "url": url,
          "isPartOf": dict(DATASET_REF)}
    crumb = f'<a href="{SITE}/">Oliver\'s mTOR Atlas</a> · Events'
    bc = breadcrumb_ld([("Oliver's mTOR Atlas", SITE + "/"), ("Events", None)])

    body = f"""<h1>mTOR conferences &amp; meetings</h1>
<p class="summary">{len(events)} conferences and scientific meetings relevant
to mTOR, autophagy, nutrient sensing and longevity research, each rated for
how directly it bears on the pathway this Atlas curates. See also the
<a href="{SITE}/#view=lineage">interactive timeline</a>, which places these
events alongside the Atlas's own study corpus.</p>
{"".join(sections)}
"""
    extra_css = """
.ev-block{margin:0 0 28px;padding-bottom:22px;border-bottom:1px solid var(--line)}
.ev-block:last-child{border-bottom:none}
.ev-block h3{margin:0 0 6px;font-size:18px}
"""
    return url, shell(
        "mTOR conferences & meetings | Oliver's mTOR Atlas",
        f"{len(events)} conferences and scientific meetings relevant to mTOR, "
        "autophagy and longevity research, each rated for relevance to the "
        "pathway -- upcoming and past, with organizers, speakers and dates.",
        url, [ld, bc], body, crumb, active_tab="lineage", extra_css=extra_css)


def about_page(studies, entities):
    """Statická /about/ stránka -- přidáno 2026-08-23 v reakci na audit finding
    (SEO_GEO_AUDIT.md §14): AI systém nebo skeptický čtenář, co přistane na
    /study/... nebo /answers/... ze search výsledků, neměl žádný STATICKÝ odkaz
    vysvětlující kdo je Oliver, proč věřit hodnocení důkazů od středoškoláka,
    jaká je politika oprav, ani jak projekt kontaktovat -- ta stránka existovala
    jen jako SPA view ({SITE}/#view=about), neviditelná pro crawlery bez JS,
    tedy přesně ty, kvůli kterým celá fáze 6 (build_pages.py) existuje.

    Obsah je věcně převzatý z existujícího AUTHOR_BIOS / About tabu v index.html
    (abProjectPane/abMethodologyPane/abAuthorPane) -- nic tu není nové ani
    vymyšlené, jen zpřístupněné bez JS. Počty studií/entit se počítají ze
    stejných dat jako zbytek buildu (`studies`, `entities`), NE napsané ručně --
    přesně to, co se pokazilo u "about 275 studies" bugu, co tenhle audit
    našel a opravil (viz DATASET_REF výše). Kontrolní poznámka: SPA text v
    Methodology panelu ("corpus size currently 283") je STEJNÝ typ zastaralého
    čísla -- žádané tady, ale mimo rozsah tohohle patche (je to v index.html,
    ne v datech, které tenhle skript čte); stojí za samostatnou opravu."""
    url = f"{SITE}/about/"
    n_studies = len(studies)
    n_entities = len(entities)
    n_entity_pages = sum(1 for x in entities if len(x["studies"]) >= PAGE_THRESHOLD)

    ld_about = {
        "@context": "https://schema.org", "@type": "AboutPage",
        "name": "About Oliver's mTOR Atlas", "url": url,
        "mainEntity": dict(DATASET_REF),
        "author": {
            "@type": "Person", "name": "Oliver Barton",
            "jobTitle": "Creator & Curator",
            "description": "High school student in Prague, Czech Republic, "
                            "curating an evidence-graded database of mTOR "
                            "pathway research.",
        },
    }
    crumb = f'<a href="{SITE}/">Oliver\'s mTOR Atlas</a> · About &amp; Methodology'
    bc = breadcrumb_ld([("Oliver's mTOR Atlas", SITE + "/"),
                        ("About & Methodology", None)])

    body = f"""<h1>About Oliver's mTOR Atlas</h1>
<p class="summary">A curated, evidence-graded database of mTOR pathway
research -- {n_studies} studies and {n_entities} cross-linked entities
({n_entity_pages} with their own page), each claim traced to a primary
source and rated by strength of evidence. This page explains who curates
it, how a study earns a place, what the grading does and doesn't
guarantee, and how to report an error.</p>

<h2>What this is</h2>
<p>Oliver's mTOR Atlas is a narrow, hand-curated corpus -- not an attempt
to index all of PubMed's roughly sixty thousand mTOR-related records, but
a smaller set small enough that every entry can be read, graded and
defended by one person, then connected by hand into a knowledge graph of
genes, drugs, diseases and outcomes. Every claim carries an explicit
evidence tier (A = systematic review of human data, B = human trial,
C = animal model, D = mechanistic/in-vitro/review), and the corpus
deliberately keeps negative results -- studies where a popular longevity
compound did <em>not</em> extend lifespan -- with the same visibility as
positive findings.</p>

<h2>Who curates it</h2>
<p><strong>Oliver Barton</strong> -- Creator &amp; Curator, Prague, Czech
Republic, age 15. A high school student with a self-directed research
interest in mTOR signaling and evidence-based science curation, who built
the Atlas to be the structured resource he wished existed when he started
reading primary literature on the pathway: studies, mechanisms and honest
evidence grades held side by side, rather than scattered across review
articles.</p>
<p>There is no editorial board and no second reviewer -- see "Who reviews
the selection" below for what that does and doesn't mean for trust.</p>
<p><strong>Contact:</strong> oliver.barton1113(at)gmail.com &middot; Bluesky: <a href="https://bsky.app/profile/oliver-barton.bsky.social">@oliver-barton.bsky.social</a>.</p>

<h2>How a study gets in</h2>
<p>Every study passes through the same four steps before it's added:</p>
<ol>
<li><strong>Source</strong> -- candidates are found via PubMed, prioritizing
landmark discovery papers, systematic reviews and large human RCTs over
secondary commentary; bioRxiv supplies preprints (always flagged as such,
never treated as equivalent to peer-reviewed work), and ClinicalTrials.gov
supplies ongoing human trials.</li>
<li><strong>Verify</strong> -- each citation's PMID, DOI, year and journal
are confirmed against PubMed's own metadata before the entry is written;
no citation is added from memory alone.</li>
<li><strong>Grade</strong> -- the study gets an A&ndash;D evidence tier
based on the strength of the model system the claim actually rests on, not
the size of the headline finding.</li>
<li><strong>Link</strong> -- the genes, drugs and outcomes the study
mentions are connected to it in the graph, so the same paper surfaces
wherever any of its subjects is explored.</li>
</ol>
<p>Every DOI resolves to the publisher's own page (Nature, Cell, Science,
NEJM, Lancet and others), so any claim traces back to the original paper
in one click.</p>

<h2>Inclusion &amp; exclusion criteria</h2>
<p>A study earns a place if it does at least one of four things: establishes
a landmark mechanism in mTOR biology; supplies the strongest available
human evidence for a claim (a systematic review or a large RCT, not an
isolated small trial); fills in representative animal or mechanistic work
for a pathway node that would otherwise be uncovered; or reports a negative
or null result that the rest of the literature tends to under-report --
included deliberately, since a database that only shows what worked
misrepresents the actual state of the science.</p>
<p>A candidate is left out if it's a secondary commentary, editorial or
news piece rather than a primary study or review; if it duplicates a
pathway node already covered by a stronger study and adds no new claim; if
its metadata can't be verified against PubMed (no PMID or DOI resolving to
the publisher's own record); or if its connection to mTOR is incidental --
mTOR measured as one readout among many in a paper about something else.
Preprints and registered trials are admitted only when they're the best
available evidence for a claim, and are then labelled ungraded rather than
given an A&ndash;D tier.</p>

<h2>What this doesn't guarantee</h2>
<p>An honest limitation: the Atlas does not keep a screening log. Candidates
that were considered and rejected leave no record, so no exclusion count
can be quoted or inferred. That's a real weakness compared with a
systematic review, where the screening flow is itself evidence that the
search was unbiased -- here it isn't. Selection is a judgement call, made
paper by paper, and it is not currently auditable from the outside. The
Atlas should be read as a curated reading list with grades attached, not
as a systematic review of the mTOR literature. Logging rejected candidates
and the reason is a planned change.</p>
<p><strong>Who reviews the selection:</strong> one person, the curator.
There is no second reviewer or independent adjudication of borderline
calls -- the usual safeguard against a single reader's blind spots is
absent. The one external check to date was an unsolicited scientific
review in July 2026, which raised sixteen points; all were addressed
rather than quietly dropped, and one exposed a real inconsistency between
the stated A&ndash;D tier definition and how it was actually being applied.
An automated validator rule now blocks any deploy where a study's tier and
its underlying evidence level disagree.</p>

<h2>How often it updates</h2>
<p>An automated job screens PubMed for new candidate mTOR studies and
relevant conferences once daily, at 02:00; the decision to include and
grade a flagged paper is made by hand, and publishing the updated site is
a manual step. So the <em>screening</em> is daily, but the <em>corpus</em>
changes only when a human accepts a candidate -- typically a handful of
papers a month, sometimes none. The exact timestamp of the live corpus is
printed in the footer of every page, and every count on this site,
including the ones above, is computed from that snapshot rather than
typed in by hand.</p>

<h2>Corrections log</h2>
<p>Every recorded correction to a study record -- what changed and why, going back to the first external review -- is public at <a href="{SITE}/changelog/">/changelog/</a>. This is what "all were addressed rather than quietly dropped" above actually means: a checkable list, not a claim to take on faith.</p>

<h2>License &amp; reuse</h2>
<p>Content is <a href="https://creativecommons.org/licenses/by/4.0/">CC BY
4.0</a> -- free to cite and reuse with attribution to "Oliver's mTOR
Atlas". The dataset is archived and citable via Zenodo, concept DOI
<a href="https://doi.org/10.5281/zenodo.22059963">10.5281/zenodo.22059963</a>.
Full identifiers, registrations (including <a href="https://bio.tools/olivers_mtor_atlas">bio.tools</a>
and <a href="https://fairsharing.org/8905">FAIRsharing</a>)
and a ready-to-use citation are on the <a href="{SITE}/data/">Data &amp; Citation</a> page.</p>

<p><a class="cta" href="{SITE}/#view=about">Open the interactive About tab</a></p>
"""
    return url, shell(
        "About & Methodology | Oliver's mTOR Atlas",
        f"Who curates Oliver's mTOR Atlas, how studies are selected and "
        f"evidence-graded, what the grading doesn't guarantee, and how to "
        f"report a correction.",
        url, [ld_about, bc], body, crumb, active_tab="about")


# --- SEO P0 Ukol 3 (2026-09-02): /data/ download section -- html fragment ---
def _export_files_html():
    """<ul> of data/exports/*.csv|json from manifest.json (same file
    _load_export_distribution() reads for DATASET_REF) -- human-readable
    counterpart to that machine-readable JSON-LD list, one source of
    truth for both."""
    p = os.path.join(HERE, "data", "exports", "manifest.json")
    if not os.path.exists(p):
        return ("<p><em>Exports are generated at build time and were not "
                "present in this build.</em></p>\n")
    try:
        manifest = json.load(open(p, encoding="utf-8"))
    except Exception:
        return ""
    items = []
    for m in manifest:
        kb = m["contentSize"] / 1024
        items.append(f'<li><a href="{m["contentUrl"]}">{m["name"]}</a> '
                     f'({m["encodingFormat"]}, {kb:.0f} KB)</li>')
    return "<ul>" + "".join(items) + "</ul>\n"


def data_page(studies, entities):
    """Static /data/ page -- added 2026-08-29 at Petr's request: one page
    that states, in plain HTML (no JS, no clicking through /about/,
    CITATION.cff, README.md and the JSON-LD separately), the handful of
    machine-checkable facts a registry reviewer, citation manager, or AI
    agent needs about the Atlas AS A DATASET: that it is registered with
    bio.tools, its dataset DOI, the curator's ORCID, its
    license, and exactly how to cite it. None of this is new information --
    it already lives in DATASET_REF's JSON-LD, /about/'s "License & reuse"
    section, README.md and CITATION.cff -- this page is the single
    human-readable place that puts it all together."""
    url = f"{SITE}/data/"
    n_studies = len(studies)
    year = datetime.date.today().year

    ld_dataset = dict(DATASET_REF)
    ld_dataset["identifier"] = [
        {"@type": "PropertyValue", "propertyID": "DOI",
         "value": "10.5281/zenodo.22059963",
         "url": "https://doi.org/10.5281/zenodo.22059963"},
        {"@type": "PropertyValue", "propertyID": "bio.tools",
         "value": "olivers_mtor_atlas",
         "url": "https://bio.tools/olivers_mtor_atlas"},
        {"@type": "PropertyValue", "propertyID": "FAIRsharing",
         "value": "FAIRsharing.org8905",
         "url": "https://fairsharing.org/8905"},
    ]
    ld_page = {
        "@context": "https://schema.org", "@type": "CollectionPage",
        "name": "Data & Citation | Oliver's mTOR Atlas", "url": url,
        "mainEntity": ld_dataset,
    }
    crumb = f'<a href="{SITE}/">Oliver\'s mTOR Atlas</a> · Data &amp; Citation'
    bc = breadcrumb_ld([("Oliver's mTOR Atlas", SITE + "/"),
                        ("Data & Citation", None)])

    export_files_html = _export_files_html()
    body = f"""<h1>Data &amp; Citation</h1>
<p class="summary">Machine- and reviewer-facing facts about Oliver's mTOR
Atlas as a dataset: where it is registered, how it is identified, and how
to cite it. Everything below also appears in this dataset's
<code>CITATION.cff</code> and <code>LICENSE</code> files and in this
page's own JSON-LD, in case a script needs it rather than a human.</p>

<h2>Registered with</h2>
<table class="kv">
<tr><td>bio.tools</td><td>Oliver's mTOR Atlas is registered with
<a href="https://bio.tools/olivers_mtor_atlas">bio.tools</a> &mdash;
ELIXIR's registry of bioinformatics tools and databases &mdash; listed as
a Database portal under Genetics, Molecular biology and Systems
biology.</td></tr>
<tr><td>FAIRsharing</td><td>Oliver's mTOR Atlas is registered with
<a href="https://fairsharing.org/8905">FAIRsharing.org</a> (record
FAIRsharing.org8905) &mdash; a curated registry of databases, standards and
policies for the life sciences &mdash; listed as a Database resource under
Molecular Biology, Biochemistry, Bioinformatics and Aging.</td></tr>
</table>

<h2>Identifiers</h2>
<table class="kv">
<tr><td>Dataset DOI</td><td><a href="https://doi.org/10.5281/zenodo.22059963">10.5281/zenodo.22059963</a>
&mdash; concept DOI, always resolves to the latest archived version on
Zenodo</td></tr>
<tr><td>Curator ORCID</td><td><a href="https://orcid.org/0009-0008-2025-2148">0009-0008-2025-2148</a>
(Oliver Barton)</td></tr>
<tr><td>License</td><td><a href="https://creativecommons.org/licenses/by/4.0/">CC BY 4.0</a>
&mdash; free to share and adapt, including commercially, with
attribution</td></tr>
</table>

<h2>Cite this resource</h2>
<p>If you use this dataset, please cite it as:</p>
<p style="font-family:'IBM Plex Mono',monospace;font-size:13px;
background:rgba(0,0,0,.03);padding:12px 14px;border-radius:4px;line-height:1.6;">
Barton, O. ({year}). <em>Oliver's mTOR Atlas</em> [Data set]. Zenodo.
<a href="https://doi.org/10.5281/zenodo.22059963">https://doi.org/10.5281/zenodo.22059963</a></p>
<p>A machine-readable citation file is also available:
<a href="{SITE}/CITATION.cff">CITATION.cff</a>.</p>

# --- SEO P0 Ukol 3 (2026-09-02): /data/ download section ---
<h2>Download the data</h2>
<p>The full corpus as flat CSV/JSON files -- the same data behind every
page on this site, without scraping HTML. Regenerated on every deploy,
so file sizes below reflect the current corpus, not a stale snapshot.</p>
{export_files_html}<p>These exports are living data, not a permanent citable snapshot -- for a
DOI-versioned copy, use the Zenodo archive above.</p>

<h2>What's in the corpus right now</h2>
<p>{n_studies} hand-curated primary studies on the mTOR signaling pathway,
each rated A&ndash;D by strength of evidence and linked back to its DOI or
PubMed record. See <a href="{SITE}/about/">About &amp; Methodology</a>
for how a study earns a place and how the grading works.</p>

<p><a class="cta" href="{SITE}/about/">About &amp; Methodology</a></p>
"""
    return url, shell(
        "Data & Citation | Oliver's mTOR Atlas",
        "Where Oliver's mTOR Atlas is registered (bio.tools, FAIRsharing), its "
        "dataset DOI, curator ORCID, license, and how to cite it.",
        url, [ld_page, bc], body, crumb, active_tab=None)


# ------------------------------------------------------------------- main ---

def browse_page(studies, entities, haspage, gaps=(), authors=()):
    """HTML rozcestník na všechny vygenerované stránky.

    Bez něj jsou nové stránky SIROTCI: sitemapa je jen pozvánka, ale hlavní
    signál, podle kterého se rozhoduje, co procházet a jakou tomu dát váhu, je
    interní prolinkování. A crawler bez JS na homepage nevidí žádný odkaz --
    SPA si je kreslí až za běhu, takže se k obsahu nemá kudy proklikat.

    `gaps` a `authors` (přidáno 2026-08-04): [(title/name, url), ...] pro
    stránky otázek a autorů -- stejný důvod, jen novější obsah.
    """
    url = f"{SITE}/browse/"
    ld = {"@context": "https://schema.org", "@type": "CollectionPage",
          "name": "Browse the Atlas", "url": url,
          "isPartOf": dict(DATASET_REF)}
    body = ["<h1>Browse the Atlas</h1>",
            f'<p class="summary">Every study and every topic in the Atlas, as a '
            f'plain index. {len(studies)} studies, '
            f'{sum(1 for x in entities if len(x["studies"]) >= PAGE_THRESHOLD)} topics.</p>']

    if gaps:
        body.append("<h2>Open questions &amp; testable hypotheses</h2>"
                    "<p>AI-identified knowledge gaps in the pathway, each with a proposed "
                    "experiment.</p><p>" + " · ".join(
                        f'<a href="{u}">{e(t)}</a>' for t, u in gaps) + "</p>")
    if authors:
        body.append("<h2>Researchers</h2><p>Scientist bios with a study-by-study "
                    "timeline of their work in the Atlas.</p><p>" + " · ".join(
                        f'<a href="{u}">{e(t)}</a>' for t, u in authors) + "</p>")

    by_type = {}
    for x in entities:
        if len(x["studies"]) < PAGE_THRESHOLD:
            continue
        by_type.setdefault(x["type"], []).append(x)
    body.append("<h2>Topics</h2>")
    for t in sorted(by_type):
        items = sorted(by_type[t], key=lambda x: -len(x["studies"]))
        body.append(f"<h3>{e(t)}</h3><p>" + " · ".join(
            f'<a href="/{TYPE_DIR.get(t,"entity")}/{slugify(x["name"])}/">'
            f'{e(x["name"])}</a> <span style="color:var(--muted-count,#7C7569)">({len(x["studies"])})</span>'
            for x in items) + "</p>")

    body.append(f"<h2>Studies</h2><p>Sorted by year, newest first. "
                f"Each links to a page with the abstract, evidence tier, DOI and PMID.</p>")
    for s in sorted(studies, key=lambda s: -(s.get("year") or 0)):
        if not s.get("sid"):
            continue
        code, _, colour = tier_bits(s.get("tier"))
        body.append(
            f'<p style="margin:0 0 7px"><a href="/study/{e(s["sid"])}/">'
            f'{e(s.get("title") or s["sid"])}</a><br>'
            f'<span style="color:var(--soft);font-size:14px">{e(s.get("year") or "")} · '
            f'{e(s.get("journal") or "")} · <span class="tier" '
            f'style="background:{colour}">{code}</span></span></p>')

    crumb = f'<a href="{SITE}/">Oliver\'s mTOR Atlas</a> · Browse'
    bc = breadcrumb_ld([("Oliver's mTOR Atlas", SITE + "/"), ("Browse", None)])
    return url, shell("Browse all studies and topics | Oliver's mTOR Atlas",
                      f"Index of all {len(studies)} curated mTOR studies and every "
                      f"pathway topic in the Atlas, each graded by strength of evidence.",
                      url, [ld, bc], "\n".join(body), crumb, active_tab="studies")


HOME_MARKER = "<!-- browse-link-added-by-build-pages -->"
HOME_END = "<!-- /browse-link -->"


def patch_home(n_pages):
    """Vloží do patičky index.html odkaz na /browse/. Idempotentní.

    Musí to být obyčejné <a> ve statickém HTML -- odkaz vykreslený JavaScriptem
    crawler, kvůli kterému to celé děláme, neuvidí.
    """
    p = os.path.join(HERE, "index.html")
    if not os.path.exists(p):
        return "index.html nenalezen"
    h = open(p, encoding="utf-8").read()
    orig = h

    # Odstraň dřívější vložení kdekoli v souboru.
    #
    # Délkový limit {0,400} je tam schválně. Bez něj se mazalo od PRVNÍ značky
    # k PRVNÍ koncové -- a protože starší vložení koncovou značku nemá, druhý
    # běh smazal celý blok dokumentu mezi nimi, včetně patičky webu. Omezená
    # délka zaručí, že se v nejhorším případě nesmaže nic.
    h = re.sub(re.escape(HOME_MARKER) + r".{0,900}?" + re.escape(HOME_END),
               "", h, flags=re.S)
    # starší formát bez koncové značky (vložení před 2026-07-27)
    h = re.sub(re.escape(HOME_MARKER)
               + r"\s*(?:&middot;|·)\s*<a href=\"/browse/\"[^>]*>[^<]*</a>"
                 r"(?:\s*<span[^>]*>[^<]*</span>)?", "", h)

    link = (f'{HOME_MARKER} &middot; '
            f'{spa_footer_link_html(n_pages)}'
            f'{HOME_END}')

    # Ukotveno na SPRÁVNOU patičku, ne na první </footer> v souboru.
    m = re.search(r'<footer class="site-footer">.*?</footer>', h, re.S)
    if not m:
        return "POZOR: <footer class=\"site-footer\"> nenalezen, odkaz NEVLOŽEN"
    h = h[:m.end() - len("</footer>")] + link + h[m.end() - len("</footer>"):]

    if h == orig:
        return "odkaz už tam je"
    if DRY:
        return "dry-run"
    tmp = p + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(h)
        f.flush()
        os.fsync(f.fileno())
    chk = open(tmp, encoding="utf-8").read()
    if len(chk) != len(h) or not chk.rstrip().endswith("</html>"):
        os.remove(tmp)
        return "POZOR: ověření zápisu index.html selhalo, NEZAPSÁNO"
    os.replace(tmp, p)
    return "odkaz v patičce webu"


SPA_MARKER = "/* deep-links-added-by-build-pages */"

SPA_HELPER = """
%s
function atlasPageUrl(ent){
  var TD={"Gene/Protein":"gene","Pathway/Complex":"complex","Drug":"drug",
          "Intervention":"intervention","Biological process":"process",
          "Disease":"disease","Outcome":"outcome","Organelle":"organelle",
          "Nutrient/Metabolite":"nutrient"};
  if(!ent || !ent.studies || ent.studies.length < 3) return null;
  var d = TD[ent.type] || "entity";
  var s = (ent.name||"").normalize("NFKD")
            .replace(/['’ʼ`]/g,"")
            .replace(/[\\u0300-\\u036f]/g,"")
            .toLowerCase().replace(/[^a-z0-9]+/g,"-").replace(/^-+|-+$/g,"");
  return "/"+d+"/"+s+"/";
}
""" % SPA_MARKER


def patch_spa_links():
    """Prolinkuje obsah SPA na statické stránky.

    POZOR NA OČEKÁVÁNÍ: tyhle odkazy vznikají až v JavaScriptu, takže je uvidí
    uživatel a Googlebot (ten JS renderuje), ale NE crawlery bez JS, kvůli
    kterým celá fáze 6 vznikla. Pro ně zůstává cestou /browse/ a vzájemné
    odkazy mezi statickými stránkami. Tohle je bonus pro lidi a pro Google,
    ne náhrada za pre-rendering.
    """
    p = os.path.join(HERE, "index.html")
    if not os.path.exists(p):
        return "index.html nenalezen"
    h = open(p, encoding="utf-8").read()
    if SPA_MARKER in h:
        return "odkazy už tam jsou"
    orig_len = len(h)
    done = []

    # 1) pomocná funkce před renderDetail()
    h, c = re.subn(r"function renderDetail\(\)\{",
                   lambda m: SPA_HELPER + "\nfunction renderDetail(){",
                   h, count=1)
    if not c:
        return "POZOR: renderDetail() nenalezen, nic nezměněno"
    done.append("helper")

    # 2) odkaz na stránku entity vedle type-badge
    old = ('<span class="type-badge" style="background:${TYPE_COLOR[e.type]}">'
           '${e.type}</span></div>')
    new = ('<span class="type-badge" style="background:${TYPE_COLOR[e.type]}">'
           '${e.type}</span>'
           '${atlasPageUrl(e) ? `<a class="doi-link" href="${atlasPageUrl(e)}" '
           'style="margin-left:10px;white-space:nowrap">standalone page &rarr;</a>` : ``}'
           '</div>')
    if old in h:
        h = h.replace(old, new, 1)
        done.append("entita")

    # 3) odkaz na stránku studie do sloupce Source v tabulce studií.
    #    stopPropagation, jinak by klik na odkaz zároveň rozbalil abstrakt.
    old2 = ('<td>${s.doi.startsWith(\'10.\') ? `<a class="doi-link" '
            'href="https://doi.org/${s.doi}" target="_blank">${s.doi}</a>` : '
            '`<span class="mono" style="font-size:10.5px;">${s.doi}</span>`}</td>')
    new2 = ('<td>${s.doi.startsWith(\'10.\') ? `<a class="doi-link" '
            'href="https://doi.org/${s.doi}" target="_blank">${s.doi}</a>` : '
            '`<span class="mono" style="font-size:10.5px;">${s.doi}</span>`}'
            '${s.sid ? `<br><a class="doi-link" href="/study/${s.sid}/" '
            'onclick="event.stopPropagation()">Atlas page &rarr;</a>` : ``}</td>')
    if old2 in h:
        h = h.replace(old2, new2, 1)
        done.append("studie")

    if len(done) < 2:
        return "POZOR: nalezeno jen %s — vzory se rozešly, NEZAPSÁNO" % done

    if DRY:
        return "dry-run (%s)" % ", ".join(done)
    tmp = p + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(h); f.flush(); os.fsync(f.fileno())
    chk = open(tmp, encoding="utf-8").read()
    if len(chk) != len(h) or not chk.rstrip().endswith("</html>") or len(h) < orig_len:
        os.remove(tmp)
        return "POZOR: ověření zápisu selhalo, NEZAPSÁNO"
    os.replace(tmp, p)
    return "prolinkováno: " + ", ".join(done)


def purge_generated():
    """Smaže jen to, co tenhle skript vyrobil -- pozná se podle markeru.
    Ručně psané soubory zůstanou i kdyby ležely ve stejné složce."""
    n = 0
    for d in ["study", "question", "author"] + sorted(set(TYPE_DIR.values())):
        p = os.path.join(HERE, d)
        if not os.path.isdir(p):
            continue
        for root, _, files in os.walk(p):
            for fn in files:
                fp = os.path.join(root, fn)
                try:
                    if GENERATED_MARKER in open(fp, encoding="utf-8").read(400):
                        os.remove(fp)
                        n += 1
                except Exception:
                    pass
        for root, dirs, files in os.walk(p, topdown=False):
            if not os.listdir(root):
                os.rmdir(root)
    return n


STATS = {"written": 0, "unchanged": 0}


def write(path, content):
    """Zapíše JEN když se obsah opravdu změnil.

    Bez tohohle by každý deploy přepsal všech ~306 stránek, git by je viděl jako
    změněné a do historie by šlo ~4,6 MB rozdílu i ve chvíli, kdy se v datech
    nezměnilo nic. Při týdenním nasazování je to čtvrt giga ročně za nic, a
    z historie už to nikdo nedostane bez jejího přepsání. Ze stejného důvodu
    není v patičce stránek datum buildu -- jinak by se každá stránka lišila
    pokaždé, i kdyby studie zůstala identická.
    """
    if DRY:
        return
    if os.path.exists(path):
        try:
            if open(path, encoding="utf-8").read() == content:
                STATS["unchanged"] += 1
                return
        except Exception:
            pass
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(content)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)
    STATS["written"] += 1


def patch_dataset_meta(version, date_modified):
    """Keeps index.html's own hand-written Dataset JSON-LD block (head of the
    file -- separate from DATASET_REF, which every *_page() function below
    uses) in sync with the same version/dateModified DATASET_REF just computed.
    Same idempotent read-check-write pattern as patch_home()/patch_spa_links()
    above; scoped to the FIRST <script type="application/ld+json"> block only,
    so it can never touch anything else in a 3+MB file by accident."""
    p = os.path.join(HERE, "index.html")
    if not os.path.exists(p):
        return "index.html nenalezen"
    h = open(p, encoding="utf-8").read()
    m = re.search(r'(<script type="application/ld\+json">\n)(.*?)(\n</script>)', h, re.S)
    if not m:
        return "POZOR: hlavni JSON-LD blok nenalezen, NEZAPSANO"
    block = m.group(2)
    new_block, n1 = re.subn(r'"version":\s*"[^"]*"', f'"version": "{version}"', block, count=1)
    new_block, n2 = re.subn(r'"dateModified":\s*"[^"]*"', f'"dateModified": "{date_modified}"', new_block, count=1)
    if not (n1 and n2):
        return "POZOR: version/dateModified pole v JSON-LD nenalezena, NEZAPSANO"
    json.loads(new_block)  # must still be valid JSON after the edit
    if new_block == block:
        return "verze uz sedi"
    if DRY:
        return "dry-run"
    h2 = h[:m.start(2)] + new_block + h[m.end(2):]
    tmp = p + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(h2)
        f.flush()
        os.fsync(f.fileno())
    chk = open(tmp, encoding="utf-8").read()
    if len(chk) != len(h2) or not chk.rstrip().endswith("</html>"):
        os.remove(tmp)
        return "POZOR: overeni zapisu index.html selhalo, NEZAPSANO"
    os.replace(tmp, p)
    return f"version={version}, dateModified={date_modified}"


def main():
    sp = os.path.join(DATA, "studies_baked.json")
    ep = os.path.join(DATA, "entities_baked.json")
    if not os.path.exists(ep):
        sys.exit("Chybí atlas_data/entities_baked.json — spusť nejdřív sync_airtable.py\n"
                 "(vyžaduje AIRTABLE_TOKEN; ověř přes `py check_token.py`).")
    studies = json.load(open(sp, encoding="utf-8"))
    entities = json.load(open(ep, encoding="utf-8"))
    by_sid = {s["sid"]: s for s in studies if s.get("sid")}
    print("studií: %d | entit: %d" % (len(studies), len(entities)))

    if CLEAN and not DRY:
        print("smazáno dřív vygenerovaných souborů:", purge_generated())

    ent_by_sid = {}
    for x in entities:
        for sid in x["studies"]:
            ent_by_sid.setdefault(sid, []).append(x)

    # Které entity stránku DOSTANOU. Musí se spočítat PŘED generováním, jinak
    # se odkazuje na adresy, které nikdy nevzniknou.
    haspage = {(TYPE_DIR.get(x["type"], "entity"), slugify(x["name"]))
               for x in entities if len(x["studies"]) >= PAGE_THRESHOLD}

    urls = []

    for s in studies:
        if not s.get("sid"):
            continue
        url, page = study_page(s, ent_by_sid, haspage)
        write(os.path.join(HERE, "study", s["sid"], "index.html"), page)
        urls.append(("study", url))

    made, skipped, seen = 0, 0, {}
    for x in entities:
        if len(x["studies"]) < PAGE_THRESHOLD:
            skipped += 1
            continue
        url, d, slug, page = entity_page(x, by_sid, entities, haspage)
        if (d, slug) in seen:
            print("  ! kolize slugu %s/%s: %s vs %s — přeskočeno"
                  % (d, slug, seen[(d, slug)], x["name"]))
            continue
        seen[(d, slug)] = x["name"]
        write(os.path.join(HERE, d, slug, "index.html"), page)
        urls.append(("entity", url))
        made += 1

    # Open Questions / hypotheses -- statické FAQPage stránky (2026-08-04).
    gp = os.path.join(DATA, "gaps_baked.json")
    gap_links = []
    if os.path.exists(gp):
        gaps = json.load(open(gp, encoding="utf-8"))
        seen_gap_slugs = {}
        for g in gaps:
            gurl, gslug, gpage = gap_page(g, by_sid)
            if gslug in seen_gap_slugs:
                print("  ! kolize slugu question/%s: %s vs %s — přeskočeno"
                      % (gslug, seen_gap_slugs[gslug], g["title"]))
                continue
            seen_gap_slugs[gslug] = g["title"]
            write(os.path.join(HERE, "question", gslug, "index.html"), gpage)
            urls.append(("question", gurl))
            gap_links.append((g["title"], gurl))
    else:
        gaps = []
        print("atlas_data/gaps_baked.json chybí -- Open Questions stránky přeskočeny")

    # Author bio stránky (2026-08-04) -- zdroj pravdy je AUTHOR_BIOS v
    # index.html, exportovaný do atlas_data/author_bios_baked.json.
    abp = os.path.join(DATA, "author_bios_baked.json")
    author_links = []
    if os.path.exists(abp):
        author_bios = json.load(open(abp, encoding="utf-8"))
        author_idx = build_author_index(studies)
        for key, bio in author_bios.items():
            aurl, aslug, apage = author_page(key, bio, author_idx.get(key, []))
            write(os.path.join(HERE, "author", aslug, "index.html"), apage)
            urls.append(("author", aurl))
            author_links.append((bio["full"], aurl))
    else:
        print("atlas_data/author_bios_baked.json chybí -- author stránky přeskočeny")

    aurl, apage = about_page(studies, entities)
    write(os.path.join(HERE, "about", "index.html"), apage)
    urls.append(("about", aurl))

    durl, dpage = data_page(studies, entities)
    write(os.path.join(HERE, "data", "index.html"), dpage)
    urls.append(("about", durl))

    changelog_url, changelog_page_html = changelog_page(studies)
    write(os.path.join(HERE, "changelog", "index.html"), changelog_page_html)
    urls.append(("about", changelog_url))

    # /pathway/ + /events/ (2026-09-05, Ukol 5 ze SEO P0 handoveru): stejny
    # duvod jako u about/data/changelog vys -- oba jsou samostatne, jednou
    # generovane top-level stranky, ne stranka na zaznam.
    pathway_model_path = os.path.join(HERE, "pathway", "model.json")
    if os.path.exists(pathway_model_path):
        pathway_model = json.load(open(pathway_model_path, encoding="utf-8"))
        purl, ppage = pathway_page(pathway_model, entities, haspage)
        write(os.path.join(HERE, "pathway", "index.html"), ppage)
        urls.append(("about", purl))
    else:
        purl = None
        print("pathway/model.json chybí -- /pathway/ přeskočeno")

    events_path = os.path.join(DATA, "events_baked.json")
    if os.path.exists(events_path):
        events = json.load(open(events_path, encoding="utf-8"))
        eurl, epage = events_page(events)
        write(os.path.join(HERE, "events", "index.html"), epage)
        urls.append(("about", eurl))
    else:
        eurl = None
        print("atlas_data/events_baked.json chybí -- /events/ přeskočeno")

    burl, bpage = browse_page(studies, entities, haspage, gap_links, author_links)
    write(os.path.join(HERE, "browse", "index.html"), bpage)
    urls.append(("entity", burl))
    print("rozcestník /browse/ :", patch_home(len(urls) + 1))
    print("odkazy uvnitř SPA  :", patch_spa_links())
    print("dataset meta v SPA :", patch_dataset_meta(DATASET_REF["version"], DATASET_REF["dateModified"]))

    for old, new in LEGACY_SLUGS.items():
        write(os.path.join(HERE, old, "index.html"),
              f'<!DOCTYPE html>{GENERATED_MARKER}<html><head><meta charset="utf-8">'
              f'<title>Moved</title><link rel="canonical" href="{SITE}/{new}/">'
              f'<meta http-equiv="refresh" content="0;url={SITE}/{new}/"></head>'
              f'<body><p>Moved to <a href="{SITE}/{new}/">{SITE}/{new}/</a></p></body></html>')

    today = datetime.date.today().isoformat()

    def sitemap(items, prio):
        # Žádný <lastmod> na úrovni URL. Razítkovat každou stránku datem buildu
        # by Googlu tvrdilo, že se změnilo všech 306 stránek při každém deployi
        # -- což je nepravda, a Google si nedůvěryhodný lastmod pamatuje a začne
        # ho ignorovat. Chybějící lastmod je lepší než falešný.
        out = ['<?xml version="1.0" encoding="UTF-8"?>',
               '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
        for u in items:
            out.append(f"  <url><loc>{u}</loc>"
                       f"<changefreq>monthly</changefreq><priority>{prio}</priority></url>")
        out.append("</urlset>")
        return "\n".join(out) + "\n"

    def _study_sid_from_url(u):
        m = re.search(r"/study/([^/]+)/$", u)
        return m.group(1) if m else None

    write(os.path.join(HERE, "sitemap-studies.xml"),
          sitemap([u for k, u in urls if k == "study"
                   and _study_sid_from_url(u) not in NOINDEX_STUDIES], "0.6"))
    write(os.path.join(HERE, "sitemap-entities.xml"),
          sitemap([u for k, u in urls if k == "entity"], "0.8"))
    write(os.path.join(HERE, "sitemap-questions.xml"),
          sitemap([u for k, u in urls if k == "question"], "0.7"))
    write(os.path.join(HERE, "sitemap-authors.xml"),
          sitemap([u for k, u in urls if k == "author"], "0.5"))
    # sitemap-answers.xml (2026-08-22) is NOT generated by this script -- it's
    # hand-baked by a separate generate.py alongside /answers/ and /glossary/,
    # per Petr's explicit "static section" decision. This script still needs
    # to reference it here, or every build_pages.py re-run would silently
    # drop it from the sitemap index (it was hand-patched in once already;
    # that patch does NOT survive a re-run without this line).
    answers_line = (f'  <sitemap><loc>{SITE}/sitemap-answers.xml</loc><lastmod>{today}</lastmod></sitemap>\n'
                     if os.path.exists(os.path.join(HERE, "sitemap-answers.xml")) else "")
    # sitemap-academy.xml (2026-08-30) -- stejny pripad jako answers vys: pise
    # ho build_academy.py, ne tenhle skript, ale bez teto radky by ho kazdy
    # dalsi beh build_pages.py z indexu sitemap tise vyhodil.
    academy_line = (f'  <sitemap><loc>{SITE}/sitemap-academy.xml</loc><lastmod>{today}</lastmod></sitemap>\n'
                    if os.path.exists(os.path.join(HERE, "sitemap-academy.xml")) else "")
    write(os.path.join(HERE, "sitemap.xml"),
          '<?xml version="1.0" encoding="UTF-8"?>\n'
          '<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
          f'  <sitemap><loc>{SITE}/sitemap-entities.xml</loc><lastmod>{today}</lastmod></sitemap>\n'
          f'  <sitemap><loc>{SITE}/sitemap-studies.xml</loc><lastmod>{today}</lastmod></sitemap>\n'
          f'  <sitemap><loc>{SITE}/sitemap-questions.xml</loc><lastmod>{today}</lastmod></sitemap>\n'
          f'  <sitemap><loc>{SITE}/sitemap-authors.xml</loc><lastmod>{today}</lastmod></sitemap>\n'
          f'  <sitemap><loc>{SITE}/sitemap-home.xml</loc><lastmod>{today}</lastmod></sitemap>\n'
          + answers_line + academy_line +
          '</sitemapindex>\n')
    # /about/ (2026-08-23) rides in sitemap-home.xml alongside the homepage --
    # it's a hand-authored, singular top-level page like home, not a
    # per-record page like study/entity/question/author.
    pathway_events_lines = ""
    if purl:
        pathway_events_lines += (
            f'  <url><loc>{purl}</loc><changefreq>monthly</changefreq><priority>0.7</priority></url>\n')
    if eurl:
        pathway_events_lines += (
            f'  <url><loc>{eurl}</loc><changefreq>monthly</changefreq><priority>0.5</priority></url>\n')
    write(os.path.join(HERE, "sitemap-home.xml"),
          '<?xml version="1.0" encoding="UTF-8"?>\n'
          '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
          f'  <url><loc>{SITE}/</loc><changefreq>monthly</changefreq><priority>1.0</priority></url>\n'
          f'  <url><loc>{aurl}</loc><changefreq>monthly</changefreq><priority>0.7</priority></url>\n'
          f'  <url><loc>{durl}</loc><changefreq>monthly</changefreq><priority>0.6</priority></url>\n'
          f'  <url><loc>{changelog_url}</loc><changefreq>monthly</changefreq><priority>0.4</priority></url>\n'
          + pathway_events_lines +
          '</urlset>\n')

    # robots.txt: povolení AI crawlerů explicitně. "Allow: /" je funkčně totéž,
    # ale pojmenovaný záznam je dokumentace záměru a chrání před budoucím omylem.
    write(os.path.join(HERE, "robots.txt"),
          "# Oliver's mTOR Atlas\n"
          "# AI search crawlers are explicitly welcome: the point of this site is\n"
          "# to be cited. Most of them do not execute JavaScript, which is why the\n"
          "# /study/ and entity pages exist as pre-rendered HTML.\n\n"
          + "".join("User-agent: %s\nAllow: /\n\n" % b for b in [
              "*", "Googlebot", "Google-Extended", "Bingbot", "GPTBot",
              "OAI-SearchBot", "ChatGPT-User", "ClaudeBot", "Claude-Web",
              "anthropic-ai", "PerplexityBot", "Perplexity-User", "CCBot",
              "Applebot", "Applebot-Extended"])
          + f"Sitemap: {SITE}/sitemap.xml\n")

    # llms.txt (2026-08-04): an emerging, informal convention (llmstxt.org),
    # not yet universally read by AI crawlers, but cheap to provide -- a
    # plain-text map straight to the most citable content, so an agent
    # doesn't have to guess which of 343 URLs matter most.
    core_entities = sorted(
        [x for x in entities if len(x["studies"]) >= 8],
        key=lambda x: -len(x["studies"]))
    core_lines = "\n".join(
        f'- [{x["name"]}](https://mtor-atlas.org/{TYPE_DIR.get(x["type"],"entity")}/'
        f'{slugify(x["name"])}/): {x["type"]}, {len(x["studies"])} studies'
        for x in core_entities)
    gap_lines = "\n".join(f"- [{t}]({u})" for t, u in gap_links)
    author_lines = "\n".join(f"- [{t}]({u})" for t, u in author_links)

    # /answers/ + /glossary/ (2026-08-22): hand-baked by a separate generate.py,
    # NOT written by this script -- same reasoning as the sitemap-answers.xml
    # guard above. Templated here (not hardcoded) so the list stays a single
    # source of truth if a page gets added or renamed later.
    answers_titles = [
        ("Does rapamycin extend lifespan in humans?", "rapamycin-lifespan-humans"),
        ("mTORC1 vs mTORC2 -- what's the difference?", "mtorc1-vs-mtorc2"),
        ("What are mTOR inhibitors? The full list", "mtor-inhibitors-list"),
        ("What are rapamycin's side effects?", "rapamycin-side-effects"),
        ("Is autophagy actually required for the lifespan benefit?", "autophagy-required-lifespan"),
        ("How is rapamycin dosed in the longevity studies?", "rapamycin-dosing-longevity"),
        ("What is mTOR?", "what-is-mtor"),
        ("Rapamycin vs metformin -- how do they compare?", "rapamycin-vs-metformin"),
        ("Are sirolimus and everolimus the same drug?", "sirolimus-everolimus-same-drug"),
        ("How does mTOR connect to cancer?", "mtor-cancer-connection"),
    ]
    answers_section = ""
    if os.path.exists(os.path.join(HERE, "answers", "index.html")):
        answers_lines = "\n".join(
            f"- [{t}](https://mtor-atlas.org/answers/{s}/)" for t, s in answers_titles)
        answers_section = (
            "\n## Direct answers & glossary\n"
            "Plain-language answers to the questions people most often ask about mTOR, "
            "rapamycin and longevity, each graded by the same evidence system used "
            "throughout the Atlas.\n"
            "- [Answers index](https://mtor-atlas.org/answers/): all "
            f"{len(answers_titles)} answer pages\n"
            f"{answers_lines}\n"
            "- [Glossary of mTOR terms](https://mtor-atlas.org/glossary/): 25 core "
            "terms, linked to the full Atlas entry for each\n")

    # /academy/ (2026-08-30): same guard-and-template pattern as answers above.
    # The list is READ from academy_data, never retyped here -- a lesson renamed
    # in lessons.json must not be able to leave a stale title in llms.txt.
    academy_section = ""
    if os.path.exists(os.path.join(HERE, "academy", "index.html")):
        try:
            _les = {l["slug"]: l for l in json.load(
                open(os.path.join(HERE, "academy_data", "lessons.json"),
                     encoding="utf-8"))["lessons"]}
            _mods = json.load(open(os.path.join(HERE, "academy_data", "modules.json"),
                                   encoding="utf-8"))["modules"]
            _lines = []
            for _m in _mods:
                _lines.append(f'- [{_m["title"]} curriculum]'
                              f'(https://mtor-atlas.org/academy/{_m["slug"]}/): '
                              f'{len(_m["lessons"])}-lesson sequence')
                for _r in _m["lessons"]:
                    if _r["status"] != "published":
                        continue
                    _l = _les[_r["lesson"]]
                    _lines.append(
                        f'- [{_r["n"]} - {_l["title"]}]'
                        f'(https://mtor-atlas.org/academy/{_m["slug"]}/{_l["slug"]}/): '
                        f'{_l["subtitle"]}')
            academy_section = (
                "\n## Learn the mechanisms (mTOR Academy)\n"
                "Short, question-led lessons that build the mental model most mTOR papers "
                "assume. Every mechanistic claim links to the Atlas study behind it, with "
                "that study's A-D evidence tier attached, and every lesson names what is "
                "still uncertain.\n"
                "- [mTOR Academy](https://mtor-atlas.org/academy/): course overview and "
                "entry points\n"
                + "\n".join(_lines) + "\n")
        except Exception as exc:
            print("  ! llms.txt: sekce Academy přeskočena (%s)" % exc)

    write(os.path.join(HERE, "llms.txt"), f"""# Oliver's mTOR Atlas

> A curated, evidence-graded database of mTOR pathway research: {len(studies)} \
peer-reviewed primary studies rated by evidence tier (A = systematic review, \
B = human trial, C = animal model, D = mechanistic/in vitro/review), linked to \
a knowledge graph of genes, drugs, diseases and outcomes, plus AI-identified \
knowledge gaps and testable hypotheses. Content is CC BY 4.0 -- free to cite \
and reuse with attribution to "Oliver's mTOR Atlas".

## Start here
- [Browse the Atlas](https://mtor-atlas.org/browse/): plain-HTML index of every study and topic page
- [The mTOR pathway, node by node](https://mtor-atlas.org/pathway/): the full pathway model (88 nodes, 119 interactions, 11 guided routes) as text -- the static form of the interactive pathway map
- [mTOR conferences & meetings](https://mtor-atlas.org/events/): upcoming and past conferences relevant to mTOR, autophagy and longevity research
- [About & Methodology](https://mtor-atlas.org/about/): who curates this, how a study is selected and evidence-graded, what the grading doesn't guarantee, correction policy
- [Full interactive Atlas](https://mtor-atlas.org/): the SPA (pathway map, AI research assistant, timeline) -- requires JavaScript
- [Data & Citation](https://mtor-atlas.org/data/): bio.tools/FAIRsharing registration, dataset DOI, ORCID, license, how to cite
{academy_section}{answers_section}
## Open questions & testable hypotheses
Original synthesis, not aggregated abstracts -- each page states an evidence gap, a hypothesis and a proposed experiment.
{gap_lines}

## Core pathway entities
Every entity page lists its full evidence tier breakdown and every linked study; this is a subset with the deepest evidence base.
{core_lines}

## Researchers
Publication timelines for the scientists most represented in the corpus.
{author_lines}

## Machine-readable
- [Data & Citation](https://mtor-atlas.org/data/): DOI, ORCID, license, bio.tools/FAIRsharing registration, citation string
- [Data exports (CSV/JSON)](https://mtor-atlas.org/data/exports/): the full corpus as flat files, regenerated on every deploy
- [Corrections log](https://mtor-atlas.org/changelog/): every recorded correction to a study record, with reason
- [Sitemap index](https://mtor-atlas.org/sitemap.xml)
- [robots.txt](https://mtor-atlas.org/robots.txt)

## License
Creative Commons Attribution 4.0 International. Reuse and citation welcome with attribution.
""")

    print("""
%s
  stránek studií  : %d
  stránek entit   : %d   (pod prahem %d studií přeskočeno: %d)
  stránek otázek  : %d
  stránek autorů  : %d
  URL v sitemap   : %d   (bylo 1)
  zapsáno         : %d   (beze změny, nezapisováno: %d)
""" % ("DRY RUN — nic nezapsáno" if DRY else "Hotovo.",
       len([1 for k, _ in urls if k == "study"]), made, PAGE_THRESHOLD, skipped,
       len(gap_links), len(author_links),
       len(urls) + 1, STATS["written"], STATS["unchanged"]))
    if not DRY:
        print("Kontrola, že crawler bez JS opravdu něco uvidí:")
        print("  py verify_prerender.py")


if __name__ == "__main__":
    main()
