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
    "C - Animal": ("C", "Animal in vivo", "#C17A2E"),
    "D - Mechanistic/Review": ("D", "Mechanistic / in vitro / review", "#8A8375"),
    "Preprint": ("—", "Preprint, not peer-reviewed", "#8B5FBF"),
    "Registered trial": ("—", "Registered trial, no results yet", "#5F8BBF"),
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
    return TIER_LABEL.get((t or "").strip(), ("—", t or "ungraded", "#8A8375"))


def shell(title, desc, canonical, jsonld, body, breadcrumb):
    """Jedna šablona pro všechny stránky. Obsah je v HTML, ne v JS -- to je
    celý bod. Styl je inline, aby stránka nezávisela na dalším requestu."""
    return f"""<!DOCTYPE html>
<html lang="en">
{GENERATED_MARKER}
<head>
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
--teal:#A31F34;--amber:#C17A2E}}
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
        "isPartOf": {"@type": "Dataset", "name": "Oliver's mTOR Atlas", "url": SITE + "/"},
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
    body.append("<h2>At a glance</h2><table>")
    for k, v in rows:
        body.append(f"<tr><td><strong>{e(k)}</strong></td><td>{v}</td></tr>")
    body.append("</table>")
    if s.get("abstract"):
        body.append(f'<h2>Abstract</h2><p class="abstract">{e(s["abstract"])}</p>')
    if s.get("ai_effect") or s.get("ai_intervention"):
        body.append("<h2>Extracted findings</h2><table>")
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

    crumb = f'<a href="{SITE}/">Atlas</a> › <a href="{SITE}/#studies">Studies</a> › {e(sid)}'
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

    body.append("<h2>Evidence at a glance</h2><table>"
                "<tr><th>Tier</th><th>What it means</th><th>Studies</th></tr>")
    for key, (code, label, colour) in TIER_LABEL.items():
        n = counts.get(code, 0)
        if code == "—" or n == 0:
            continue
        body.append(f'<tr><td><span class="tier" style="background:{colour}">{code}'
                    f'</span></td><td>{e(label)}</td><td>{n}</td></tr>')
    body.append("</table>")
    if not counts.get("A") and not counts.get("B"):
        body.append("<p><em>No direct human evidence in the Atlas for this entity yet — "
                    "everything below rests on animal or mechanistic work.</em></p>")

    body.append("<h2>Studies</h2><table>"
                "<tr><th>Study</th><th>Year</th><th>Tier</th><th>Finding</th></tr>")
    for s in linked:
        code, _, colour = tier_bits(s.get("tier"))
        body.append(
            f'<tr><td><a href="/study/{e(s["sid"])}/">{e(s["sid"])}</a></td>'
            f'<td>{e(s.get("year") or "")}</td>'
            f'<td><span class="tier" style="background:{colour}">{code}</span></td>'
            f'<td>{e((s.get("finding") or s.get("title") or "")[:200])}</td></tr>')
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
            count = f' <span style="color:#8A8375">{n}</span>'
            if (d2, s2) in haspage:
                chips.append(f'<a href="/{d2}/{s2}/">{e(o["name"])}{count}</a>')
            else:
                chips.append(f'<span>{e(o["name"])}{count}</span>')
        body.append('<h2>Related entities</h2><div class="tags">'
                    + "".join(chips) + "</div>")

    body.append(f'<p><a class="cta" href="{SITE}/#entities">Open in the Atlas explorer</a></p>')
    crumb = (f'<a href="{SITE}/">Atlas</a> › '
             f'<a href="{SITE}/#entities">{e(ent["type"])}</a> › {e(ent["name"])}')
    return url, d, slug, shell(f"{ent['name']} — evidence in the mTOR pathway | Oliver's mTOR Atlas",
                               desc, url, ld, "\n".join(body), crumb)


# ------------------------------------------------------------------- main ---

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
