#!/usr/bin/env python3
"""
build_paper_page.py -- landing page práce pro Google Scholar (6. 10. 2026).

PROČ TOHLE EXISTUJE
-------------------
Preprint je od 15. 9. 2026 na Figshare a Google Scholar ho tři týdny po
publikaci neindexoval. Figshare je obecné úložiště, ne preprintový server,
a Scholar ho sklízí pomalu a výběrově.

Tenhle skript staví to jediné, co je celé v naší režii: bibliografickou
landing page na vlastní doméně. Scholar podle svých inclusion guidelines
potřebuje stránku, která má v <head> Highwire tagy (citation_*) a v nich
odkaz na PDF **na téže doméně**. Web Atlasu je předrenderovaný, plně
crawlovatelný a v sitemapě, takže jakmile stránka existuje, Scholar má co
sklidit.

DVĚ ROZHODNUTÍ, KTERÁ SE NESMÍ ZTRATIT
--------------------------------------
1. `citation_doi` míří na Figshare DOI, ne na nějaké nové DOI téhle stránky.
   Záměrně: Scholar má landing page spojit s existujícím záznamem do JEDNOHO
   klastru. Bez DOI hrozí dva nesouvisející záznamy s rozdělenými citacemi --
   přesně to, čemu se celá operace vyhýbá. Ze stejného důvodu musí být TITLE
   níž znak za znakem shodný s Figshare a Zenodem.

2. `citation_pdf_url` míří na /papers/ na mtor-atlas.org, ne na Figshare.
   Scholar ignoruje PDF na jiné doméně, než je landing page. Proto musí být
   kopie PDF v repozitáři -- a build spadne, pokud tam není.

SPUŠTĚNÍ
--------
    py build_paper_page.py            # zapíše evidence/audit/paper/index.html
    py build_paper_page.py --dry-run  # jen vypíše, nic nezapisuje
"""
import io
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from build_pages import SITE, shell, e  # noqa: E402

# --------------------------------------------------------------------------
# Záznam práce. Jediný zdroj pravdy pro meta tagy, JSON-LD i viditelný text.
# Hodnoty odpovídají Figshare v5 (ověřeno proti api.figshare.com).
# --------------------------------------------------------------------------
PAPER = {
    "out": "evidence/audit/paper",
    "url": SITE + "/evidence/audit/paper/",
    "title": ("Ten percent human: an evidence-graded audit of the mTOR "
              "literature and the pathway's translational gap"),
    "author": "Oliver Barton",
    "author_citation": "Barton, Oliver",
    "orcid": "0009-0008-2025-2148",
    "doi": "10.6084/m9.figshare.33772297",
    "zenodo_doi": "10.5281/zenodo.23110710",
    "corpus_doi": "10.5281/zenodo.22059963",
    "pdf_file": "papers/Barton_2026_mTOR_Atlas_audit_v2.pdf",
    "published": "2026/09/15",
    "institution": "Oliver's mTOR Atlas",
    "keywords": ["mTOR", "evidence-graded audit", "meta-research",
                 "scientometrics", "translational research",
                 "literature curation", "knowledge base"],
}

# Abstrakt doslova podle Figshare. Shodný text pomáhá Scholaru poznat, že jde
# o tutéž práci -- neupravovat ani o větu.
ABSTRACT = [
    "The mTOR pathway is among the most heavily cited targets in ageing "
    "biology, and claims derived from it circulate widely in translational "
    "and public-facing contexts. What is rarely made explicit is the kind of "
    "evidence any given claim rests on. I report a systematic audit of a "
    "hand-curated corpus of 386 mTOR studies (1975-2026), in which every "
    "record carries an explicit classification of the biological system it "
    "was done in, assigned under a fixed rubric.",

    "Three findings emerge. First, the human evidence base is thin: 39 of "
    "386 studies (10.1%) are human work of any kind (systematic review, "
    "clinical trial, or observational study), while 305 (79.0%) are animal "
    "or mechanistic/in-vitro work. Second, the human evidence that does "
    "exist is overwhelmingly about disease indications rather than ageing: "
    "of 25 human clinical trials, 13 concern licensed uses (transplant "
    "immunosuppression, oncology, tuberous sclerosis complex / "
    "lymphangioleiomyomatosis) and two are physiology experiments in healthy "
    "volunteers, leaving ten ageing- or healthspan-oriented trials. Among "
    "those ten, every positive primary-endpoint result comes from an "
    "early-phase, small or uncontrolled design; the one adequately powered "
    "confirmatory trial (Mannick et al., 2021; n = 1024) missed its primary "
    "endpoint (26% vs 25%, p = 0.65) after a positive phase-2a by the same "
    "group; the only purpose-built healthspan RCT completed to date (PEARL; "
    "Moel et al., 2025; n = 114) reported a pre-registered null; and a "
    "pre-registered crossover trial in 63 healthy adults found that moderate "
    "dietary protein restriction did not raise autophagic flux at all (Singh "
    "et al., 2026), against a clear preclinical expectation that it should. "
    "Third, the proportion of human evidence is rising slowly but "
    "monotonically across eras - 0% before 2000, 5.5% in 2000-2009, 10.0% in "
    "2010-2019, 14.7% from 2020 - meaning that even in the most recent "
    "period roughly six in seven curated studies remain pre-clinical.",

    "I also report a structured gap layer derived from the corpus (ten "
    "hypotheses, each linked to a mean of 6.6 constituent studies), and "
    "describe a revision of the classification scheme itself prompted by "
    "external expert critique - a case in which the act of grading evidence "
    "exposed a defect in the grading rubric. The corpus, the rubric, and the "
    "generating code are openly available.",
]

CSS = """
.paper-dl{display:inline-block;background:var(--teal);color:#fff;
text-decoration:none;font-family:'IBM Plex Mono',monospace;font-weight:600;
font-size:13px;letter-spacing:.04em;text-transform:uppercase;
padding:11px 20px;border-radius:3px;margin:4px 0 2px}
.paper-dl:hover{opacity:.85;color:#fff}
.paper-byline{font-size:15px;margin:0 0 4px}
.paper-rec th{white-space:nowrap;vertical-align:top;width:170px}
.paper-cite{font-family:'IBM Plex Mono',monospace;font-size:13px;
line-height:1.65;background:rgba(0,0,0,.04);border-left:3px solid var(--line);
padding:12px 15px;margin:6px 0 18px;overflow-wrap:anywhere}
"""


def head_tags(p):
    """Highwire tagy, které Scholar čte. Vrací blok ZAČÍNAJÍCÍ newlinem --
    shell() ho lepí přímo za JSON-LD bez vlastního oddělovače, aby prázdná
    hodnota u ostatních stránek negenerovala ani prázdný řádek."""
    pdf_url = "%s/%s" % (SITE, p["pdf_file"])
    tags = [
        ("citation_title", p["title"]),
        ("citation_author", p["author_citation"]),
        ("citation_author_orcid", p["orcid"]),
        ("citation_publication_date", p["published"]),
        ("citation_online_date", p["published"]),
        ("citation_pdf_url", pdf_url),
        ("citation_abstract_html_url", p["url"]),
        ("citation_doi", p["doi"]),
        ("citation_technical_report_institution", p["institution"]),
        ("citation_language", "en"),
        ("citation_keywords", "; ".join(p["keywords"])),
    ]
    return "\n" + "\n".join(
        '<meta name="%s" content="%s">' % (name, e(val)) for name, val in tags)


def render(p):
    P = []
    A = P.append
    pdf_url = "%s/%s" % (SITE, p["pdf_file"])

    A('<h1>%s</h1>' % e(p["title"]))
    A('<p class="paper-byline">%s &middot; '
      '<a href="https://orcid.org/%s">ORCID %s</a></p>'
      % (e(p["author"]), e(p["orcid"]), e(p["orcid"])))
    A('<p class="meta">Preprint, posted 15 September 2026 &middot; '
      'not peer reviewed &middot; CC&nbsp;BY&nbsp;4.0</p>')
    A('<p><a class="paper-dl" href="/%s">Download PDF (12 pages, 160&nbsp;kB)</a></p>'
      % e(p["pdf_file"]))
    A('<p class="meta">DOI <a href="https://doi.org/%s">%s</a></p>'
      % (e(p["doi"]), e(p["doi"])))

    A('<h2 id="abstract">Abstract</h2>')
    for para in ABSTRACT:
        A('<p>%s</p>' % e(para))

    A('<h2 id="record">The record</h2>')
    A('<table class="aud paper-rec"><tbody>')
    rows = [
        ("Preprint DOI",
         '<a href="https://doi.org/%s">%s</a> (figshare)' % (e(p["doi"]), e(p["doi"]))),
        ("Mirror",
         '<a href="https://doi.org/%s">%s</a> (Zenodo)'
         % (e(p["zenodo_doi"]), e(p["zenodo_doi"]))),
        ("Corpus and code",
         '<a href="https://doi.org/%s">%s</a> (Zenodo) &middot; '
         '<a href="%s/data/">Data &amp; Citation</a>'
         % (e(p["corpus_doi"]), e(p["corpus_doi"]), SITE)),
        ("PDF on this site", '<a href="/%s">%s</a>'
         % (e(p["pdf_file"]), e(p["pdf_file"].rsplit("/", 1)[-1]))),
        ("Licence",
         '<a href="https://creativecommons.org/licenses/by/4.0/">CC BY 4.0</a>'),
        ("Peer review", "None. This is a preprint."),
    ]
    for k, v in rows:
        A('<tr><th>%s</th><td>%s</td></tr>' % (e(k), v))
    A('</tbody></table>')

    A('<h2 id="cite">How to cite</h2>')
    A('<div class="paper-cite">Barton, O. (2026). %s. figshare. Preprint. '
      'https://doi.org/%s</div>' % (e(p["title"]), e(p["doi"])))

    A('<h2 id="relation">How this relates to the live audit</h2>')
    A('<p>This paper is a fixed, citable snapshot. The '
      '<a href="%s/evidence/audit/">evidence audit</a> on this site is the '
      'same measurement recomputed from the corpus on every build, so its '
      'numbers move as the corpus grows and the paper\'s do not. Cite the '
      'paper for a figure that must stay put; read the audit for the current '
      'state.</p>' % SITE)
    A('<p>The corpus the paper measures (386 studies at the time of writing) '
      'is browsable study by study under <a href="%s/browse/">all studies</a>, '
      'and the pathway links it grades are in the '
      '<a href="%s/">interactive map</a>.</p>' % (SITE, SITE))

    return "\n".join(P), pdf_url


def build(p, dry_run=False):
    body, pdf_url = render(p)

    desc = ("A systematic audit of 386 curated mTOR studies (1975-2026): only "
            "10.1% are human work and 79.0% are animal or in-vitro, with the "
            "human evidence that exists aimed at disease rather than ageing. "
            "Preprint by Oliver Barton, CC BY 4.0.")

    ld = [{
        "@context": "https://schema.org",
        "@type": "ScholarlyArticle",
        "headline": p["title"],
        "name": p["title"],
        "url": p["url"],
        "description": desc,
        "abstract": " ".join(ABSTRACT),
        "datePublished": p["published"].replace("/", "-"),
        "inLanguage": "en",
        "keywords": ", ".join(p["keywords"]),
        "license": "https://creativecommons.org/licenses/by/4.0/",
        "author": {
            "@type": "Person",
            "name": p["author"],
            "identifier": "https://orcid.org/" + p["orcid"],
            "url": "https://orcid.org/" + p["orcid"],
        },
        "publisher": {"@type": "Organization", "name": p["institution"]},
        "identifier": "https://doi.org/" + p["doi"],
        "sameAs": ["https://doi.org/" + p["doi"],
                   "https://doi.org/" + p["zenodo_doi"]],
        "encoding": {
            "@type": "MediaObject",
            "contentUrl": pdf_url,
            "encodingFormat": "application/pdf",
        },
        "isBasedOn": SITE + "/data/",
        "creativeWorkStatus": "Preprint",
    }, {
        "@context": "https://schema.org",
        "@type": "BreadcrumbList",
        "itemListElement": [
            {"@type": "ListItem", "position": 1, "name": "Oliver's mTOR Atlas",
             "item": SITE + "/"},
            {"@type": "ListItem", "position": 2, "name": "Evidence",
             "item": SITE + "/evidence/"},
            {"@type": "ListItem", "position": 3, "name": "Audit",
             "item": SITE + "/evidence/audit/"},
            {"@type": "ListItem", "position": 4, "name": "Paper",
             "item": p["url"]},
        ],
    }]

    html = shell(
        title="%s — Oliver's mTOR Atlas" % p["title"],
        desc=desc,
        canonical=p["url"],
        jsonld=ld,
        body=body,
        breadcrumb="Oliver's mTOR Atlas · Evidence · Audit · <b>Paper</b>",
        active_tab="about",
        extra_css=CSS,
        extra_head=head_tags(p),
    )

    # Sanity. Stránka bez kteréhokoli z těchhle kusů je k ničemu -- Scholar ji
    # buď nenajde, nebo z ní udělá druhý klastr. Lepší spadnout tady než zjistit
    # to za tři týdny z prázdného výsledku vyhledávání.
    problems = []
    pdf_path = os.path.join(HERE, *p["pdf_file"].split("/"))
    if not os.path.exists(pdf_path):
        problems.append(
            "chybí %s -- citation_pdf_url musí mířit na PDF na téže doméně, "
            "jinak ho Scholar ignoruje" % p["pdf_file"])
    n_tags = html.count('<meta name="citation_')
    if n_tags != 11:
        problems.append("citation_* tagů je %d, čekáno 11" % n_tags)
    if p["doi"] not in html:
        problems.append("chybí Figshare DOI -- bez něj Scholar založí druhý klastr")
    if pdf_url not in html:
        problems.append("citation_pdf_url nemíří na %s" % pdf_url)
    if "G-420TPC8J46" not in html:
        problems.append("chybí GA4 tag")
    if 'rel="canonical"' not in html:
        problems.append("chybí canonical")
    if problems:
        raise SystemExit("build_paper_page: " + "; ".join(problems))

    if dry_run:
        print("(dry-run: nic nezapsáno; %d znaků HTML by šlo do %s/index.html, "
              "%d citation_* tagů)" % (len(html), p["out"], n_tags))
        return html

    out_dir = os.path.join(HERE, *p["out"].split("/"))
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, "index.html")
    tmp = path + ".tmp"
    with io.open(tmp, "w", encoding="utf-8", newline="\n") as f:
        f.write(html)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)
    print("zapsáno: %s (%d znaků, %d citation_* tagů)" % (path, len(html), n_tags))
    return html


if __name__ == "__main__":
    build(PAPER, dry_run="--dry-run" in sys.argv)
