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

import os, sys, json, re, html, shutil, unicodedata, datetime

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "atlas_data")
SITE = "https://mtor-atlas.org"

DRY = "--dry-run" in sys.argv
CLEAN = "--clean" in sys.argv

PAGE_THRESHOLD = 3          # quality gate z plánu fáze 6
GENERATED_MARKER = "<!-- generated-by-build-pages -->"

# Google Rich Results validuje i VNOŘENÉ Dataset uzly (isPartOf). Holý stub
# {name, url} = "chybí pole description / creator / license" v Search Console.
# Musí sedět s hlavním Dataset blokem v index.html.
DATASET_REF = {
    "@type": "Dataset",
    "name": "Oliver's mTOR Atlas",
    "url": SITE + "/",
    "description": (
        "A curated, evidence-graded database of mTOR pathway research: over 320 "
        "studies, with every eligible peer-reviewed primary study rated by evidence "
        "tier (A = systematic review/meta-analysis, B = human trial, C = animal model, "
        "D = mechanistic/in-vitro/review), linked to a knowledge graph of genes, "
        "diseases and interventions, plus AI-identified knowledge gaps and testable "
        "hypotheses."
    ),
    "creator": {"@type": "Organization", "name": "Oliver's mTOR Atlas",
                "url": SITE + "/"},
    "license": "https://creativecommons.org/licenses/by/4.0/",
    "isAccessibleForFree": True,
    "inLanguage": "en",
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
    return html.escape(str(s or ""), quote=True)


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
    ("welcome", "Welcome"), ("ask", "Ask Atlas"), ("map", "Pathway"),
    ("studies", "Studies"), ("authors", "Authors"), ("questions", "Open Questions"),
    ("lineage", "Timeline"), ("about", "About"),
]


def topbar_html(active_tab=None):
    """Site-wide header (logo + primary nav), added 2026-08-22 so every static
    entry-point page (study/entity/question/author/browse, plus the hand-baked
    /answers/ and /glossary/ pages) carries the same top-level branding and
    navigation as the SPA (index.html), instead of just a bare breadcrumb.

    Deliberately NOT a clone of the SPA topbar: no search box (nothing here to
    search against without the SPA's JS + data) and no Level/Mode switches
    (those are stateful reading-level/theme controls with nothing to act on
    on a static page). Just the wordmark and the 8 tabs, as plain links into
    the SPA's own hash-addressed views -- the SPA reads {SITE}/#view=<tab>
    (URLSearchParams over location.hash, see applyHash() in index.html), NOT
    a bare {SITE}/#<tab> fragment. Fixed 2026-08-23 after the bare-fragment
    version shipped broken (linked to "#questions" instead of "#view=questions").

    EXCEPTION (2026-08-23): the "about" tab points at the static /about/ page
    (STATIC_TAB_URLS below), not {SITE}/#view=about. That hash route is real
    but only resolves once the SPA's JS has run -- exactly the audit finding
    this fixes: a crawler or a skeptical reader landing on a /study/ or
    /answers/ page had no *static* link explaining who curates the Atlas or
    how it's graded. The other 7 tabs are left as hash links; they don't
    (yet) have static equivalents worth linking to instead."""
    static_urls = {"about": f"{SITE}/about/"}
    tabs = "".join(
        '<a href="{}"{}>{}</a>'.format(
            static_urls.get(tid, f"{SITE}/#view={tid}"),
            ' class="active"' if tid == active_tab else "", e(label))
        for tid, label in SITE_TABS)
    return f"""<div class="oma-topbar"><div class="oma-topbar-inner">
<a class="oma-wordmark" href="{SITE}/" title="Oliver's mTOR Atlas — home">
<img class="oma-emblem" src="{SITE}/apple-touch-icon.png" alt="">
<span class="oma-name">Oliver's mTOR Atlas</span>
<span class="oma-tag">Evidence Platform</span>
</a>
<nav class="oma-tabs" aria-label="Main">{tabs}</nav>
</div></div>"""


def shell(title, desc, canonical, jsonld, body, breadcrumb, active_tab=None):
    """Jedna šablona pro všechny stránky. Obsah je v HTML, ne v JS -- to je
    celý bod. Styl je inline, aby stránka nezávisela na dalším requestu.

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
    topbar = topbar_html(active_tab)
    return f"""<!DOCTYPE html>
<html lang="en">
{GENERATED_MARKER}
<head>
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
<meta name="robots" content="index, follow">
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
<style>
:root{{--paper:#fff;--ink:#0A0A0A;--soft:#55524C;--line:rgba(0,0,0,.13);
--teal:#A31F34;--amber:#A56827}}
*{{box-sizing:border-box}}
body{{margin:0;background:var(--paper);color:var(--ink);
font:16px/1.6 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif}}
.wrap{{max-width:760px;margin:0 auto;padding:26px 22px 70px}}
a{{color:var(--teal)}}
/* ---- Site-wide topbar (logo + primary nav), added 2026-08-22 ---- */
.oma-topbar{{border-bottom:2px solid var(--ink)}}
.oma-topbar-inner{{max-width:1100px;margin:0 auto;padding:14px 22px;
display:flex;align-items:center;gap:18px;flex-wrap:wrap}}
.oma-wordmark{{display:flex;align-items:baseline;gap:9px;text-decoration:none;
color:var(--ink);flex-shrink:0}}
.oma-wordmark:hover{{opacity:.75}}
.oma-emblem{{width:24px;height:24px;object-fit:contain;align-self:center}}
.oma-name{{font-family:'DM Sans',-apple-system,sans-serif;font-weight:700;
font-size:16px;letter-spacing:-.01em;white-space:nowrap}}
.oma-tag{{font-family:'IBM Plex Mono',monospace;font-size:10px;letter-spacing:.06em;
text-transform:uppercase;color:var(--soft);border-left:1px solid var(--line);
padding-left:9px;white-space:nowrap}}
.oma-tabs{{display:flex;flex-wrap:wrap;gap:2px;margin-left:auto}}
.oma-tabs a{{font-family:'IBM Plex Mono',monospace;font-weight:600;font-size:11px;
letter-spacing:.05em;text-transform:uppercase;padding:8px 12px;color:var(--ink);
text-decoration:none;border-bottom:3px solid transparent}}
.oma-tabs a:hover{{background:rgba(163,31,52,.08);color:var(--teal)}}
.oma-tabs a.active{{color:#fff;background:var(--teal)}}
nav.crumb{{max-width:760px;margin:0 auto;font-size:13px;color:var(--soft);
padding:14px 22px 14px;border-bottom:2px solid var(--ink);margin-bottom:22px}}
nav.crumb a{{color:var(--soft)}}
h1{{font-size:27px;line-height:1.25;margin:0 0 10px;letter-spacing:-.01em}}
h2{{font-size:17px;margin:30px 0 9px;padding-bottom:5px;
border-bottom:1px solid var(--line)}}
.meta{{color:var(--soft);font-size:14px;margin:0 0 18px}}
.tier{{display:inline-block;padding:2px 9px;border-radius:3px;color:#fff;
font-size:12px;font-weight:600;letter-spacing:.03em}}
.summary{{font-size:17px;line-height:1.55;border-left:3px solid var(--teal);
padding:2px 0 2px 15px;margin:0 0 20px}}
table{{border-collapse:collapse;width:100%;font-size:14px;margin:6px 0 18px}}
th{{text-align:left;font-size:12px;letter-spacing:.04em;text-transform:uppercase;
color:var(--soft);border-bottom:1.5px solid var(--ink);padding:5px 10px 5px 0}}
td{{padding:7px 10px 7px 0;border-bottom:1px solid var(--line);vertical-align:top}}
ul{{padding-left:19px}} li{{margin-bottom:6px}}
.tags a{{display:inline-block;font-size:13px;border:1px solid var(--line);
border-radius:3px;padding:3px 9px;margin:0 5px 6px 0;text-decoration:none}}
.cta{{display:inline-block;background:var(--ink);color:#fff;text-decoration:none;
padding:10px 17px;border-radius:3px;font-size:14px;margin:6px 0 0}}
footer.oma-footer{{margin-top:44px;padding:22px 22px 26px;border-top:1px solid var(--line);
font-family:'IBM Plex Mono',monospace;font-size:12px;color:var(--soft);
text-align:center}}
footer.oma-footer p{{max-width:640px;margin:0 auto 8px;font-family:-apple-system,
BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;font-size:13px;line-height:1.55}}
footer.oma-footer .oma-footer-links{{margin-top:10px}}
footer.oma-footer .oma-footer-links a{{margin:0 8px}}
.abstract{{font-size:15px;color:#26241F}}

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
  .wrap{{padding:20px 16px 56px;
    padding-left:max(16px,env(safe-area-inset-left));
    padding-right:max(16px,env(safe-area-inset-right))}}
  h1{{font-size:clamp(21px,5.4vw,25px);line-height:1.22}}
  h2{{font-size:16px;margin:26px 0 8px}}
  .summary{{font-size:16px;padding-left:13px}}
  body{{font-size:16px}}
  nav.crumb{{font-size:12.5px;line-height:1.9}}
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
}}
</style>
</head>
<body>
{topbar}
<div class="wrap">
<nav class="crumb">{breadcrumb}</nav>
{body}
<footer class="oma-footer">
<p><strong>Oliver's mTOR Atlas</strong> — an evidence-graded database of the mTOR
pathway. Every entry traces to a primary paper, graded A–D by strength of evidence.
Curated by Oliver Barton, Prague.</p>
<div class="oma-footer-links">
<a href="{SITE}/">Full interactive Atlas</a> · <a href="{SITE}/browse/">Browse the Atlas</a> · <a href="{SITE}/answers/">Answers</a> · <a href="{SITE}/glossary/">Glossary</a> · <a href="{SITE}/about/">About &amp; Methodology</a> · <a href="https://github.com/open-mtor-atlas/atlas">GitHub</a>
</div>
</footer>
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


def study_page(s, ent_by_sid, haspage):
    sid = s["sid"]
    code, label, colour = tier_bits(s.get("tier"))
    url = f"{SITE}/study/{sid}/"
    title = s.get("title") or sid
    desc = (s.get("finding") or s.get("abstract") or title)[:300]

    ld = {
        "@context": "https://schema.org", "@type": "ScholarlyArticle",
        "headline": title, "name": title,
        "datePublished": str(s.get("year") or ""),
        "url": url, "inLanguage": "en",
        "isPartOf": dict(DATASET_REF),
    }
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
        ld["abstract"] = s["abstract"]

    rows = [("Evidence tier", f'<span class="tier" style="background:{colour}">'
                              f'{e(code)}</span> {e(label)}'),
            ("Study type", e(s.get("pyramid") or s.get("category") or "—")),
            ("Model system", e(s.get("model") or s.get("ai_species") or "—")),
            ("Journal", e(s.get("journal") or "—")),
            ("Year", e(s.get("year") or "—")),
            ("Peer reviewed", e(s.get("peer") or "—"))]
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
    if s.get("finding"):
        body.append(f'<p class="summary">{e(s["finding"])}</p>')
    body.append("<h2>At a glance</h2><table class=\"kv\">")
    for k, v in rows:
        body.append(f"<tr><td><strong>{e(k)}</strong></td><td>{v}</td></tr>")
    body.append("</table>")
    if s.get("abstract"):
        body.append(f'<h2>Abstract</h2><p class="abstract">{e(s["abstract"])}</p>')
    if s.get("ai_effect") or s.get("ai_intervention"):
        body.append("<h2>Extracted findings</h2><table class=\"kv\">")
        for k, f in (("Intervention", "ai_intervention"), ("Target", "ai_target"),
                     ("Model", "ai_species"), ("Effect", "ai_effect"),
                     ("Dose", "ai_dose"), ("Sample size", "ai_samplesize"),
                     ("Effect size", "ai_effectsize"), ("Limitations", "ai_limitations")):
            if s.get(f):
                body.append(f"<tr><td><strong>{e(k)}</strong></td><td>{e(s[f])}</td></tr>")
        body.append("</table>")
    if tag_html:
        body.append(f'<h2>Related topics</h2><div class="tags">{tag_html}</div>')
    body.append(f'<p><a class="cta" href="{SITE}/#studies">Open in the Atlas explorer</a></p>')

    crumb = f'<a href="{SITE}/">Oliver\'s mTOR Atlas</a> › <a href="{SITE}/#studies">Studies</a> › {e(sid)}'
    bc = breadcrumb_ld([("Oliver's mTOR Atlas", SITE + "/"),
                        ("Studies", SITE + "/#studies"),
                        (sid, None)])
    return url, shell(f"{title} | Oliver's mTOR Atlas", desc, url, [ld, bc],
                      "\n".join(body), crumb, active_tab="studies")


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
    if ent.get("desc"):
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
            count = f' <span style="color:#7C7569">{n}</span>'
            if (d2, s2) in haspage:
                chips.append(f'<a href="/{d2}/{s2}/">{e(o["name"])}{count}</a>')
            else:
                chips.append(f'<span>{e(o["name"])}{count}</span>')
        body.append('<h2>Related entities</h2><div class="tags">'
                    + "".join(chips) + "</div>")

    body.append(f'<p><a class="cta" href="{SITE}/#entities">Open in the Atlas explorer</a></p>')
    crumb = (f'<a href="{SITE}/">Oliver\'s mTOR Atlas</a> › '
             f'<a href="{SITE}/#entities">{e(ent["type"])}</a> › {e(ent["name"])}')
    bc = breadcrumb_ld([("Oliver's mTOR Atlas", SITE + "/"),
                        (ent["type"], SITE + "/#entities"),
                        (ent["name"], None)])
    return url, d, slug, shell(f"{ent['name']} — evidence in the mTOR pathway | Oliver's mTOR Atlas",
                               desc, url, [ld, bc], "\n".join(body), crumb, active_tab="map")


# ------------------------------------------------------- question/gap pages ---
# Added 2026-08-04. The "Open Questions" tab (knowledge gaps + testable
# hypotheses, atlas_data/gaps_baked.json) is the Atlas's most original
# content -- not an aggregated abstract, but synthesis a crawler can't get
# anywhere else. It lived only inside the JS SPA. FAQPage/Question schema is
# exactly the shape AI answer engines lift straight into a response, so this
# is the single highest-leverage GEO gap on the site.

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
    if g.get("basis_beginner"):
        body.append(f'<h2>The gap</h2><p class="summary">{g["basis_beginner"]}</p>')
        if g.get("basis") and g["basis"] != g["basis_beginner"]:
            body.append(f'<p class="meta"><em>Technical framing:</em> {e(g["basis"])}</p>')
    elif g.get("basis"):
        body.append(f'<h2>The gap</h2><p class="summary">{e(g["basis"])}</p>')
    if g.get("hyp_beginner"):
        body.append(f'<h2>The hypothesis</h2><p>{g["hyp_beginner"]}</p>')
        if g.get("hyp") and g["hyp"] != g["hyp_beginner"]:
            body.append(f'<p class="meta"><em>Technical framing:</em> {e(g["hyp"])}</p>')
    elif g.get("hyp"):
        body.append(f'<h2>The hypothesis</h2><p>{e(g["hyp"])}</p>')
    if g.get("exp"):
        body.append(f'<h2>How it could be tested</h2><p>{e(g["exp"])}</p>')

    links = [f'<a href="/study/{e(sid)}/">{e(sid)}</a>'
             for sid in g.get("studies") or [] if sid in studies_by_sid]
    if links:
        body.append(f'<h2>Related studies</h2><p>{" · ".join(links)}</p>')
    body.append(f'<p><a class="cta" href="{SITE}/#questions">Open in the Atlas explorer</a></p>')

    crumb = (f'<a href="{SITE}/">Oliver\'s mTOR Atlas</a> › '
             f'<a href="{SITE}/#questions">Open Questions</a> › {e(g["title"])}')
    bc = breadcrumb_ld([("Oliver's mTOR Atlas", SITE + "/"),
                        ("Open Questions", SITE + "/#questions"),
                        (g["title"], None)])
    return url, slug, shell(f"{g['title']} | Open Questions | Oliver's mTOR Atlas",
                            desc, url, [ld, bc], "\n".join(body), crumb, active_tab="questions")


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
        ld["image"] = bio["photo"]

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

    crumb = (f'<a href="{SITE}/">Oliver\'s mTOR Atlas</a> › '
             f'<a href="{SITE}/#authors">Researchers</a> › {e(bio["full"])}')
    bc = breadcrumb_ld([("Oliver's mTOR Atlas", SITE + "/"),
                        ("Researchers", SITE + "/#authors"),
                        (bio["full"], None)])
    return url, slug, shell(f"{bio['full']} — {bio['role']} | Oliver's mTOR Atlas",
                            desc, url, [ld, bc], "\n".join(body), crumb, active_tab="authors")


# --------------------------------------------------------------- about page ---

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
    crumb = f'<a href="{SITE}/">Oliver\'s mTOR Atlas</a> › About &amp; Methodology'
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
<p><strong>Contact:</strong> oliver.barton1113(at)gmail.com.</p>

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

<h2>License &amp; reuse</h2>
<p>Content is <a href="https://creativecommons.org/licenses/by/4.0/">CC BY
4.0</a> -- free to cite and reuse with attribution to "Oliver's mTOR
Atlas". The dataset is archived and citable via Zenodo, concept DOI
<a href="https://doi.org/10.5281/zenodo.22059963">10.5281/zenodo.22059963</a>.</p>

<p><a class="cta" href="{SITE}/#view=about">Open the interactive About tab</a></p>
"""
    return url, shell(
        "About & Methodology | Oliver's mTOR Atlas",
        f"Who curates Oliver's mTOR Atlas, how studies are selected and "
        f"evidence-graded, what the grading doesn't guarantee, and how to "
        f"report a correction.",
        url, [ld_about, bc], body, crumb, active_tab="about")


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
            f'{e(x["name"])}</a> <span style="color:#7C7569">({len(x["studies"])})</span>'
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
            f'<span style="color:#55524C;font-size:14px">{e(s.get("year") or "")} · '
            f'{e(s.get("journal") or "")} · <span class="tier" '
            f'style="background:{colour}">{code}</span></span></p>')

    crumb = f'<a href="{SITE}/">Oliver\'s mTOR Atlas</a> › Browse'
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
    h = re.sub(re.escape(HOME_MARKER) + r".{0,400}?" + re.escape(HOME_END),
               "", h, flags=re.S)
    # starší formát bez koncové značky (vložení před 2026-07-27)
    h = re.sub(re.escape(HOME_MARKER)
               + r"\s*(?:&middot;|·)\s*<a href=\"/browse/\"[^>]*>[^<]*</a>"
                 r"(?:\s*<span[^>]*>[^<]*</span>)?", "", h)

    link = (f'{HOME_MARKER} &middot; '
            f'<a href="/browse/" style="color:inherit">Browse the Atlas</a> '
            f'<span class="mono" style="opacity:.65">{n_pages} pages</span>'
            f' &middot; <a href="/about/" style="color:inherit">About &amp; Methodology</a>'
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

    burl, bpage = browse_page(studies, entities, haspage, gap_links, author_links)
    write(os.path.join(HERE, "browse", "index.html"), bpage)
    urls.append(("entity", burl))
    print("rozcestník /browse/ :", patch_home(len(urls) + 1))
    print("odkazy uvnitř SPA  :", patch_spa_links())

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

    write(os.path.join(HERE, "sitemap-studies.xml"),
          sitemap([u for k, u in urls if k == "study"], "0.6"))
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
    write(os.path.join(HERE, "sitemap.xml"),
          '<?xml version="1.0" encoding="UTF-8"?>\n'
          '<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
          f'  <sitemap><loc>{SITE}/sitemap-entities.xml</loc><lastmod>{today}</lastmod></sitemap>\n'
          f'  <sitemap><loc>{SITE}/sitemap-studies.xml</loc><lastmod>{today}</lastmod></sitemap>\n'
          f'  <sitemap><loc>{SITE}/sitemap-questions.xml</loc><lastmod>{today}</lastmod></sitemap>\n'
          f'  <sitemap><loc>{SITE}/sitemap-authors.xml</loc><lastmod>{today}</lastmod></sitemap>\n'
          f'  <sitemap><loc>{SITE}/sitemap-home.xml</loc><lastmod>{today}</lastmod></sitemap>\n'
          + answers_line +
          '</sitemapindex>\n')
    # /about/ (2026-08-23) rides in sitemap-home.xml alongside the homepage --
    # it's a hand-authored, singular top-level page like home, not a
    # per-record page like study/entity/question/author.
    write(os.path.join(HERE, "sitemap-home.xml"),
          '<?xml version="1.0" encoding="UTF-8"?>\n'
          '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
          f'  <url><loc>{SITE}/</loc><changefreq>monthly</changefreq><priority>1.0</priority></url>\n'
          f'  <url><loc>{aurl}</loc><changefreq>monthly</changefreq><priority>0.7</priority></url>\n'
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

    write(os.path.join(HERE, "llms.txt"), f"""# Oliver's mTOR Atlas

> A curated, evidence-graded database of mTOR pathway research: {len(studies)} \
peer-reviewed primary studies rated by evidence tier (A = systematic review, \
B = human trial, C = animal model, D = mechanistic/in vitro/review), linked to \
a knowledge graph of genes, drugs, diseases and outcomes, plus AI-identified \
knowledge gaps and testable hypotheses. Content is CC BY 4.0 -- free to cite \
and reuse with attribution to "Oliver's mTOR Atlas".

## Start here
- [Browse the Atlas](https://mtor-atlas.org/browse/): plain-HTML index of every study and topic page
- [About & Methodology](https://mtor-atlas.org/about/): who curates this, how a study is selected and evidence-graded, what the grading doesn't guarantee, correction policy
- [Full interactive Atlas](https://mtor-atlas.org/): the SPA (pathway map, AI research assistant, timeline) -- requires JavaScript
{answers_section}
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
