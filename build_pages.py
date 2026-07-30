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
        "A curated, evidence-graded database of mTOR pathway research: about 275 "
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
}
LEGACY_SLUGS = {}           # {"stary-slug": "novy-slug"} -> vygeneruje redirect

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


def shell(title, desc, canonical, jsonld, body, breadcrumb):
    """Jedna šablona pro všechny stránky. Obsah je v HTML, ne v JS -- to je
    celý bod. Styl je inline, aby stránka nezávisela na dalším requestu."""
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
<script type="application/ld+json">
{json.dumps(jsonld, ensure_ascii=False, indent=1)}
</script>
<style>
:root{{--paper:#fff;--ink:#0A0A0A;--soft:#55524C;--line:rgba(0,0,0,.13);
--teal:#A31F34;--amber:#A56827}}
*{{box-sizing:border-box}}
body{{margin:0;background:var(--paper);color:var(--ink);
font:16px/1.6 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif}}
.wrap{{max-width:760px;margin:0 auto;padding:26px 22px 70px}}
a{{color:var(--teal)}}
nav.crumb{{font-size:13px;color:var(--soft);padding-bottom:14px;
border-bottom:2px solid var(--ink);margin-bottom:22px}}
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
footer{{margin-top:44px;padding-top:14px;border-top:1px solid var(--line);
font-size:13px;color:var(--soft)}}
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
<div class="wrap">
<nav class="crumb">{breadcrumb}</nav>
{body}
<footer>
<p><strong>Oliver's mTOR Atlas</strong> — an evidence-graded database of the mTOR
pathway. Every entry traces to a primary paper, graded A–D by strength of evidence.
Curated by Oliver Barton, Prague.</p>
<p><a href="{SITE}/">Full interactive Atlas</a></p>
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
    return url, shell(f"{title} | Oliver's mTOR Atlas", desc, url, ld,
                      "\n".join(body), crumb)


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
    return url, d, slug, shell(f"{ent['name']} — evidence in the mTOR pathway | Oliver's mTOR Atlas",
                               desc, url, ld, "\n".join(body), crumb)


# ------------------------------------------------------------------- main ---

def browse_page(studies, entities, haspage):
    """HTML rozcestník na všechny vygenerované stránky.

    Bez něj jsou nové stránky SIROTCI: sitemapa je jen pozvánka, ale hlavní
    signál, podle kterého se rozhoduje, co procházet a jakou tomu dát váhu, je
    interní prolinkování. A crawler bez JS na homepage nevidí žádný odkaz --
    SPA si je kreslí až za běhu, takže se k obsahu nemá kudy proklikat.
    """
    url = f"{SITE}/browse/"
    ld = {"@context": "https://schema.org", "@type": "CollectionPage",
          "name": "Browse the Atlas", "url": url,
          "isPartOf": dict(DATASET_REF)}
    body = ["<h1>Browse the Atlas</h1>",
            f'<p class="summary">Every study and every topic in the Atlas, as a '
            f'plain index. {len(studies)} studies, '
            f'{sum(1 for x in entities if len(x["studies"]) >= PAGE_THRESHOLD)} topics.</p>']

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
    return url, shell("Browse all studies and topics | Oliver's mTOR Atlas",
                      f"Index of all {len(studies)} curated mTOR studies and every "
                      f"pathway topic in the Atlas, each graded by strength of evidence.",
                      url, ld, "\n".join(body), crumb)


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
            f'<span class="mono" style="opacity:.65">{n_pages} pages</span>{HOME_END}')

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
    for d in ["study"] + sorted(set(TYPE_DIR.values())):
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

    burl, bpage = browse_page(studies, entities, haspage)
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
    write(os.path.join(HERE, "sitemap.xml"),
          '<?xml version="1.0" encoding="UTF-8"?>\n'
          '<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
          f'  <sitemap><loc>{SITE}/sitemap-entities.xml</loc><lastmod>{today}</lastmod></sitemap>\n'
          f'  <sitemap><loc>{SITE}/sitemap-studies.xml</loc><lastmod>{today}</lastmod></sitemap>\n'
          f'  <sitemap><loc>{SITE}/sitemap-home.xml</loc><lastmod>{today}</lastmod></sitemap>\n'
          '</sitemapindex>\n')
    write(os.path.join(HERE, "sitemap-home.xml"), sitemap([SITE + "/"], "1.0"))

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

    print("""
%s
  stránek studií : %d
  stránek entit  : %d   (pod prahem %d studií přeskočeno: %d)
  URL v sitemap  : %d   (bylo 1)
  zapsáno        : %d   (beze změny, nezapisováno: %d)
""" % ("DRY RUN — nic nezapsáno" if DRY else "Hotovo.",
       len([1 for k, _ in urls if k == "study"]), made, PAGE_THRESHOLD, skipped,
       len(urls) + 1, STATS["written"], STATS["unchanged"]))
    if not DRY:
        print("Kontrola, že crawler bez JS opravdu něco uvidí:")
        print("  py verify_prerender.py")


if __name__ == "__main__":
    main()
