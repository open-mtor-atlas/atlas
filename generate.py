#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Generates the /answers/ answer pages, the /answers/ hub, the /glossary/ page,
and sitemap-answers.xml for Oliver's mTOR Atlas.

Pure additive static content -- does not touch index.html, build_pages.py,
or any Airtable-driven TYPE_DIR. Matches the existing generated-page template
(same CSS, same head boilerplate, same tier colors) pulled from
drug/rapamycin/index.html and question/.../index.html on 2026-08-22.
"""
import os
import html
import re
import json

OUT = os.path.join(os.path.dirname(__file__), "out")

TIER_COLOR = {
    "A": "#2F7A52",
    "B": "#2F6FA8",
    "C": "#A56827",
    "D": "#7C7569",
}
TIER_MEANING = {
    "A": "Systematic review of human data",
    "B": "Direct human evidence",
    "C": "Animal in vivo",
    "D": "Mechanistic / in vitro / review",
}

STYLE = """:root{--paper:#fff;--ink:#0A0A0A;--soft:#55524C;--line:rgba(0,0,0,.13);
--teal:#A31F34;--amber:#A56827}
*{box-sizing:border-box}
body{margin:0;background:var(--paper);color:var(--ink);
font:16px/1.6 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif}
.wrap{max-width:760px;margin:0 auto;padding:26px 22px 70px}
a{color:var(--teal)}
/* ---- Site-wide topbar (logo + primary nav), matches build_pages.py shell() ---- */
.oma-topbar{border-bottom:2px solid var(--ink)}
.oma-topbar-inner{max-width:1100px;margin:0 auto;padding:22px 26px 16px;
display:flex;align-items:center;gap:9px;flex-wrap:wrap}
.oma-wordmark{display:flex;align-items:center;gap:9px;text-decoration:none;
color:var(--ink);flex-shrink:0}
.oma-wordmark:hover{opacity:.75}
.oma-emblem{width:34px;height:34px;flex-shrink:0;align-self:center;color:var(--teal)}
.oma-name{font-family:'DM Sans',-apple-system,sans-serif;font-weight:700;
font-size:19px;letter-spacing:-.01em;white-space:nowrap}
.oma-tag{font-family:'IBM Plex Mono',monospace;font-size:10px;letter-spacing:.06em;
text-transform:uppercase;color:var(--soft);border-left:1px solid var(--line);
padding-left:9px;white-space:nowrap}
.oma-tabs-row{border-bottom:2px solid var(--ink)}
.oma-tabs-inner{max-width:1100px;margin:0 auto;padding:0 26px}
.oma-tabs{display:flex;flex-wrap:wrap;gap:4px}
.oma-tabs a{font-family:'IBM Plex Mono',monospace;font-weight:600;font-size:12px;
letter-spacing:.05em;text-transform:uppercase;padding:11px 18px;color:var(--ink);
text-decoration:none;border-bottom:3px solid transparent;margin-bottom:-2px}
.oma-tabs a:hover{background:rgba(163,31,52,.08);color:var(--teal)}
.oma-tabs a.active{color:#fff;background:var(--teal);border-bottom-color:var(--teal);font-weight:700}
nav.crumb{max-width:760px;margin:0 auto;font-size:13px;color:var(--soft);
padding:14px 22px 14px;border-bottom:2px solid var(--ink);margin-bottom:22px}
nav.crumb a{color:var(--soft)}
h1{font-size:27px;line-height:1.25;margin:0 0 10px;letter-spacing:-.01em}
h2{font-size:17px;margin:30px 0 9px;padding-bottom:5px;
border-bottom:1px solid var(--line)}
.meta{color:var(--soft);font-size:14px;margin:0 0 18px}
.tier{display:inline-block;padding:2px 9px;border-radius:3px;color:#fff;
font-size:12px;font-weight:600;letter-spacing:.03em}
.summary{font-size:17px;line-height:1.55;border-left:3px solid var(--teal);
padding:2px 0 2px 15px;margin:0 0 20px}
table{border-collapse:collapse;width:100%;font-size:14px;margin:6px 0 18px}
th{text-align:left;font-size:12px;letter-spacing:.04em;text-transform:uppercase;
color:var(--soft);border-bottom:1.5px solid var(--ink);padding:5px 10px 5px 0}
td{padding:7px 10px 7px 0;border-bottom:1px solid var(--line);vertical-align:top}
ul{padding-left:19px} li{margin-bottom:6px}
.tags a{display:inline-block;font-size:13px;border:1px solid var(--line);
border-radius:3px;padding:3px 9px;margin:0 5px 6px 0;text-decoration:none}
.cta{display:inline-block;background:var(--ink);color:#fff;text-decoration:none;
padding:10px 17px;border-radius:3px;font-size:14px;margin:6px 0 0}
footer.oma-footer{margin-top:44px;padding:22px 22px 26px;border-top:1px solid var(--line);
font-family:'IBM Plex Mono',monospace;font-size:12px;color:var(--soft);
text-align:center}
footer.oma-footer p{max-width:640px;margin:0 auto 8px;font-family:-apple-system,
BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;font-size:13px;line-height:1.55}
footer.oma-footer .oma-footer-links{margin-top:10px}
footer.oma-footer .oma-footer-links a{margin:0 8px}
.abstract{font-size:15px;color:#26241F}
.gloss dt{font-weight:600;font-size:16px;margin-top:20px}
.gloss dd{margin:4px 0 0;color:#26241F}
.gloss .cnt{color:var(--soft);font-weight:400;font-size:13px}

/* ─────────────────────────────────────────────────────────────────────
   MOBILE LAYER (added 2026-07-29)
   These pages previously had no media queries at all: a fixed 760px wrap
   and a four-column Studies table, which on a 360px phone meant a
   permanently horizontally-scrolled page with ~90px columns.
   ───────────────────────────────────────────────────────────────────── */
html{-webkit-text-size-adjust:100%;text-size-adjust:100%}
img,svg{max-width:100%;height:auto}
.wrap{overflow-wrap:break-word}
a{overflow-wrap:anywhere}

@media (max-width:760px){
  .oma-tabs-inner{overflow-x:auto;-webkit-overflow-scrolling:touch}
  .oma-tabs{flex-wrap:nowrap;min-width:max-content}
  .wrap{padding:20px 16px 56px;
    padding-left:max(16px,env(safe-area-inset-left));
    padding-right:max(16px,env(safe-area-inset-right))}
  h1{font-size:clamp(21px,5.4vw,25px);line-height:1.22}
  h2{font-size:16px;margin:26px 0 8px}
  .summary{font-size:16px;padding-left:13px}
  body{font-size:16px}
  nav.crumb{font-size:12.5px;line-height:1.9}
  nav.crumb a,footer.oma-footer .oma-footer-links a{display:inline-flex;align-items:center;
    padding:6px 0;min-height:44px}
  .oma-tabs a{padding:9px 10px;font-size:10.5px;min-height:38px;
    display:inline-flex;align-items:center}
  .tags a{padding:9px 12px;margin:0 6px 8px 0;font-size:14px;min-height:44px;
    display:inline-flex;align-items:center}
  .cta{padding:13px 20px;font-size:15px;min-height:44px;
    display:inline-flex;align-items:center}
  table a,.wrap li>a,.wrap p>a{display:inline-flex;align-items:center;min-height:44px}
  table{font-size:15px}
}

@media (max-width:560px){
  table.kv td{padding:7px 8px 7px 0}
  table.kv td:first-child{width:38%}
  table.st,table.ev{display:block}
  table.st tr:first-child,table.ev tr:first-child{
    position:absolute;width:1px;height:1px;padding:0;margin:-1px;
    overflow:hidden;clip:rect(0,0,0,0);white-space:nowrap;border:0}
  table.st tbody,table.ev tbody,
  table.st tr,table.ev tr,
  table.st td,table.ev td{display:block;width:100%}
  table.st tr,table.ev tr{
    border:1px solid var(--line);padding:11px 13px;margin:0 0 10px}
  table.st td,table.ev td{border:none;padding:3px 0}
  table.st td[data-l]::before,table.ev td[data-l]::before{
    content:attr(data-l);display:block;
    font-size:10.5px;letter-spacing:.07em;text-transform:uppercase;
    color:var(--soft);margin-bottom:2px}
  table.st td[data-l="Study"]{font-weight:600;font-size:16px}
  table.st td[data-l="Year"],table.st td[data-l="Tier"]{
    display:inline-block;width:auto;margin-right:20px}
  table.st td[data-l="Finding"]{padding-top:7px;line-height:1.55}
  table.ev td[data-l="Tier"],table.ev td[data-l="Studies"]{
    display:inline-block;width:auto;margin-right:22px}
}

@media (max-width:380px){
  .wrap{padding:16px 13px 48px}
  h1{font-size:20px}
}

@media (prefers-reduced-motion:reduce){
  *{animation:none!important;transition:none!important}
}
"""

HEAD_TMPL = """<!DOCTYPE html>
<html lang="en">
<!-- generated-by-generate-answers-2026-08-22 -->
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
<title>{title}</title>
<meta name="description" content="{description}">
<link rel="canonical" href="{canonical}">
<meta name="robots" content="index, follow">
<meta property="og:type" content="article">
<meta property="og:site_name" content="Oliver's mTOR Atlas">
<meta property="og:title" content="{title}">
<meta property="og:description" content="{description}">
<meta property="og:url" content="{canonical}">
<meta property="og:image" content="https://mtor-atlas.org/og-image.png">
<meta name="twitter:card" content="summary_large_image">
<link rel="icon" type="image/png" href="/favicon.png">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=DM+Sans:opsz,wght@9..40,400;9..40,700&family=IBM+Plex+Mono:wght@400;500;600&display=swap" rel="stylesheet">
{jsonld}
<style>
{style}</style>
</head>
"""

SITE = "https://mtor-atlas.org"

SITE_TABS = [
    ("welcome", "Welcome"), ("learn", "Learn"), ("ask", "Ask Atlas"), ("map", "Pathway"),
    ("studies", "Studies"), ("authors", "Authors"), ("questions", "Open Questions"),
    ("lineage", "Timeline"), ("about", "About"),
]

# Tabs with a real static page. Mirrors STATIC_TAB_URLS in build_pages.py --
# kept as a literal copy for the same reason SITE_TABS is (this script ships
# independently of the live repo checkout). 2026-08-30: "about" was previously
# missing here, so /answers/ and /glossary/ linked the JS-only #view=about hash
# while every build_pages.py page linked /about/; fixed in the same pass that
# added "learn" -> /academy/.
STATIC_TAB_URLS = {
    "about": "https://mtor-atlas.org/about/",
    "learn": "https://mtor-atlas.org/academy/",
}


def topbar_html(active_tab="ask"):
    """Same site-wide header as build_pages.py's topbar_html() -- kept as a
    literal copy (not imported) since this script ships independently of the
    live repo checkout. Defaults to highlighting 'Ask Atlas', since the
    /answers/ and /glossary/ pages are this site's Q&A / reference layer.

    Links use {SITE}/#view=<tab> -- the SPA reads the hash via
    URLSearchParams (applyHash() in index.html expects a `view` param), not
    a bare #<tab> fragment. Fixed 2026-08-23."""
    tabs = "".join(
        '<a href="{}"{}>{}</a>'.format(
            STATIC_TAB_URLS.get(tid, "{}/#view={}".format(SITE, tid)),
            ' class="active"' if tid == active_tab else "", esc(label))
        for tid, label in SITE_TABS)
    return f"""<div class="oma-topbar"><div class="oma-topbar-inner">
<a class="oma-wordmark" href="{SITE}/" title="Oliver's mTOR Atlas — home">
<svg class="oma-emblem" viewBox="0 0 64 64" role="img" aria-label="Oliver's mTOR Atlas emblem"><path d="M40.89 7.57 A26 26 0 1 1 23.11 7.57" fill="none" stroke="currentColor" stroke-width="5" stroke-linecap="round"/><circle cx="32" cy="15" r="9" fill="currentColor"/></svg>
<span class="oma-name">Oliver's mTOR Atlas</span>
<span class="oma-tag">Evidence Platform</span>
</a>
</div></div>
<div class="oma-tabs-row"><div class="oma-tabs-inner"><nav class="oma-tabs" aria-label="Main">{tabs}</nav></div></div>"""


def esc(s):
    return html.escape(s, quote=True)


def faq_jsonld(question, answer):
    return """<script type="application/ld+json">
{{
 "@context": "https://schema.org",
 "@type": "FAQPage",
 "mainEntity": [
  {{
   "@type": "Question",
   "name": {q},
   "acceptedAnswer": {{
    "@type": "Answer",
    "text": {a}
   }}
  }}
 ]
}}
</script>""".format(q=jstr(question), a=jstr(answer))


def breadcrumb_jsonld(name):
    return """<script type="application/ld+json">
{{
 "@context": "https://schema.org",
 "@type": "BreadcrumbList",
 "itemListElement": [
  {{
   "@type": "ListItem",
   "position": 1,
   "name": "Oliver's mTOR Atlas",
   "item": "https://mtor-atlas.org/"
  }},
  {{
   "@type": "ListItem",
   "position": 2,
   "name": "Answers",
   "item": "https://mtor-atlas.org/answers/"
  }},
  {{
   "@type": "ListItem",
   "position": 3,
   "name": {name}
  }}
 ]
}}
</script>""".format(name=jstr(name))


def jstr(s):
    # minimal JSON string escaper (no external deps)
    return '"' + s.replace('\\', '\\\\').replace('"', '\\"').replace('\n', '\\n') + '"'


def ev_table(rows):
    out = ['<table class="ev"><tr><th>Tier</th><th>What it means</th><th>Studies</th></tr>']
    for tier, n in rows:
        out.append(
            '<tr><td data-l="Tier"><span class="tier" style="background:{c}">{t}</span></td>'
            '<td data-l="Meaning">{m}</td><td data-l="Studies">{n}</td></tr>'.format(
                c=TIER_COLOR[tier], t=tier, m=TIER_MEANING[tier], n=n
            )
        )
    out.append("</table>")
    return "".join(out)


def cite(code, tier, text):
    return (
        '<li><a href="/study/{code}/">{code}</a> '
        '<span class="tier" style="background:{c}">{t}</span> — {text}</li>'
    ).format(code=code, c=TIER_COLOR[tier], t=tier, text=text)


def page(slug, title, description, h1, tldr, sections, related_links, faq_q=None, faq_a=None,
         base="answers", active_tab="ask"):
    canonical = "https://mtor-atlas.org/{}/{}/".format(base, slug)
    jsonld = ""
    if faq_q:
        jsonld += faq_jsonld(faq_q, faq_a) + "\n"
    jsonld += breadcrumb_jsonld(h1)
    head = HEAD_TMPL.format(
        title=esc(title), description=esc(description), canonical=canonical,
        jsonld=jsonld, style=STYLE,
    )
    body = ["<body>\n" + topbar_html(active_tab) + '\n<div class="wrap">']
    body.append(
        '<nav class="crumb"><a href="https://mtor-atlas.org/">Oliver\'s mTOR Atlas</a> '
        '› <a href="https://mtor-atlas.org/answers/">Answers</a> › {}</nav>'.format(esc(h1))
    )
    body.append("<h1>{}</h1>".format(esc(h1)))
    body.append('<p class="summary">{}</p>'.format(tldr))
    for heading, html_content in sections:
        if heading:
            body.append("<h2>{}</h2>{}".format(esc(heading), html_content))
        else:
            body.append(html_content)
    if related_links:
        body.append('<h2>Related entities</h2><div class="tags">{}</div>'.format(related_links))
    body.append('<p><a class="cta" href="https://mtor-atlas.org/">Open in the Atlas explorer</a></p>')
    body.append(
        '<footer class="oma-footer">\n'
        "<p><strong>Oliver's mTOR Atlas</strong> — an evidence-graded database of the mTOR\n"
        "pathway. Every entry traces to a primary paper, graded A–D by strength of evidence.\n"
        "Curated by Oliver Barton, Prague.</p>\n"
        '<div class="oma-footer-links">\n'
        '<a href="https://mtor-atlas.org/">Full interactive Atlas</a> · '
        '<a href="https://mtor-atlas.org/browse/">Browse the Atlas</a> · '
        '<a href="https://mtor-atlas.org/academy/">Academy</a> · '
        '<a href="https://mtor-atlas.org/answers/">Answers</a> · '
        '<a href="https://mtor-atlas.org/glossary/">Glossary</a> · '
        '<a href="https://github.com/open-mtor-atlas/atlas">GitHub</a>\n'
        '</div>\n</footer>'
    )
    body.append("</div>\n</body>\n</html>\n")
    return head + "\n".join(body)


PAGES = []


def add(slug, title, description, h1, tldr, sections, related_links, faq_a):
    PAGES.append(dict(
        slug=slug, title=title, description=description, h1=h1, tldr=tldr,
        sections=sections, related_links=related_links, faq_q=h1, faq_a=faq_a,
    ))


# ---------------------------------------------------------------------------
# 1. Does rapamycin extend lifespan in humans?
# ---------------------------------------------------------------------------
add(
    slug="rapamycin-lifespan-humans",
    title="Does Rapamycin Extend Lifespan in Humans? | Oliver's mTOR Atlas",
    description="38 rapamycin studies rated A–D by evidence strength — what's proven in mice, what's only measured as biomarkers in humans, and what's still an open question.",
    h1="Does rapamycin extend lifespan in humans?",
    tldr=(
        "Short answer: we don't know yet, and no study has directly tested it. What's well "
        "established is that rapamycin extends lifespan in mice (Tier C, animal evidence). "
        "In humans, the evidence so far covers biomarkers and short-term safety, not actual "
        "lifespan — a human lifespan trial would take decades. The strongest human evidence "
        "to date is a systematic review (Tier A) reporting improvements in immune, "
        "cardiovascular, and skin parameters, not a mortality outcome."
    ),
    sections=[
        ("The evidence, by tier", ev_table([("A", 1), ("B", 7), ("C", 14), ("D", 15)]) +
         "<p>Rapamycin is the most-studied intervention in this Atlas for its effect on the "
         "mTOR pathway (38 studies total).</p>"),
        ("What each tier actually shows", "<ul>" + "".join([
            cite("LEE2024", "A", "the first systematic review of rapamycin/rapalogs in "
                 "humans specifically for aging; found improvements in immune, "
                 "cardiovascular, and skin parameters — biomarkers and safety, not a "
                 "lifespan endpoint."),
            cite("MOE2025", "B", "a 48-week randomized controlled trial (n=114) found NO "
                 "significant change in its primary endpoint, visceral fat by DXA "
                 "(p=0.942) — a null result worth knowing about, since not every human "
                 "trial confirms the mouse findings."),
            cite("KRA2018", "B", "low-dose rapamycin was tolerable in older adults over "
                 "8+ weeks, with only minor adverse events."),
            cite("HAR2009", "C", "rapamycin fed starting at 600 days of age (late-middle-age "
                 "for a mouse) extended median lifespan by 9–14% in both sexes."),
            cite("BIT2016", "C", "just 3 months of rapamycin late in life increased "
                 "subsequent life expectancy by up to 60% — the lifespan benefit doesn't "
                 "require lifelong dosing."),
            cite("SAR2006", "D", "long-term dosing also suppresses mTORC2 signaling in many "
                 "cell types — the likely mechanism behind the insulin resistance seen "
                 "with daily dosing."),
        ]) + "</ul>"),
        ("The honest gap", "<p>Nobody has run — or can easily run — a randomized trial that "
         "follows healthy humans on rapamycin for the decades it would take to measure an "
         "actual lifespan effect. Every human data point so far is a proxy: biomarkers, "
         "short-term safety, or one physiological outcome like visceral fat. Whether "
         "mTORC1-selective (mTORC2-sparing) dosing could capture the mouse-study longevity "
         "signal without the human metabolic downside is one of the Atlas's 10 open "
         "questions, each paired with a proposed experiment. See "
         '<a href="/question/mtorc1-selective-mtorc2-sparing-dosing-captures-longevity-without-insulin-resistance/">'
         "the full open question</a>.</p>"),
    ],
    related_links='<a href="/drug/rapamycin/">Rapamycin <span style="color:#7C7569">38</span></a>'
                  '<a href="/outcome/longevity/">Longevity</a>'
                  '<a href="/complex/mtorc1/">mTORC1</a>'
                  '<a href="/complex/mtorc2/">mTORC2</a>',
    faq_a=(
        "No study has directly tested this — a human lifespan trial would take decades. "
        "Rapamycin reliably extends lifespan in mice (Tier C evidence, e.g. a 9-14% median "
        "lifespan increase in HAR2009). In humans, the evidence so far covers biomarkers, "
        "immune/cardiovascular/skin parameters, and short-term safety (Tier A-B), not "
        "an actual mortality outcome."
    ),
)

# ---------------------------------------------------------------------------
# 2. mTORC1 vs mTORC2
# ---------------------------------------------------------------------------
add(
    slug="mtorc1-vs-mtorc2",
    title="mTORC1 vs mTORC2: What's the Difference? | Oliver's mTOR Atlas",
    description="mTOR forms two distinct complexes with different jobs and different drug sensitivity. What each does, backed by 89 evidence-graded studies.",
    h1="mTORC1 vs mTORC2 — what's the difference?",
    tldr=(
        "mTOR (the protein) forms two separate complexes that do different jobs. "
        "<strong>mTORC1</strong> regulates protein synthesis, autophagy, and growth in "
        "response to nutrients and growth factors — and it's the one rapamycin blocks. "
        "<strong>mTORC2</strong> phosphorylates Akt/PKB and affects cell survival and "
        "glucose metabolism — and critically, it is <em>not</em> directly blocked by "
        "rapamycin (it doesn't use the same Raptor-dependent mechanism). Long-term "
        "rapamycin dosing eventually suppresses mTORC2 too, indirectly — the likely "
        "source of the insulin-resistance side effect seen with daily dosing."
    ),
    sections=[
        ("Side by side", ev_table([("B", 13), ("C", 17), ("D", 43)]) +
         "<p><strong>mTORC1</strong> — 75 studies total. \"mTOR Complex 1; regulates protein "
         "synthesis, autophagy, and growth in response to nutrients and growth factors.\"</p>"
         + ev_table([("B", 1), ("C", 2), ("D", 11)]) +
         "<p><strong>mTORC2</strong> — 14 studies total. \"mTOR Complex 2; phosphorylates "
         "Akt/PKB, affects cell survival and glucose metabolism.\" mTORC2 "
         + "".join([cite("THO2009", "D", "rapamycin does NOT fully block mTORC1 either — "
             "using Torin1 (which jams the active site directly), this study showed "
             "rapamycin leaves important mTORC1 jobs running, notably 4E-BP1 "
             "phosphorylation.")]).replace("<li>", "").replace("</li>", "")
         + "</p>"),
        ("Why the distinction matters", "<p>mTORC1 is rapamycin's direct target, so its "
         "studies are where you'll find the growth/autophagy/protein-synthesis effects; "
         "mTORC2 is where the metabolic side effects trace back to, and it only shows up "
         "because chronic rapamycin dosing eventually reaches it indirectly — not because "
         "rapamycin was designed to hit it. This is the basis of one of the Atlas's "
         "flagged open questions: whether a dosing strategy that hits mTORC1 (for the "
         "benefit) while sparing mTORC2 (avoiding the metabolic cost) is achievable, and "
         "if so, whether it's a matter of drug selectivity, dose, or timing. See "
         '<a href="/question/mtorc1-selective-mtorc2-sparing-dosing-captures-longevity-without-insulin-resistance/">'
         "the full open question</a>.</p>"),
    ],
    related_links='<a href="/gene/mtor/">mTOR <span style="color:#7C7569">62</span></a>'
                  '<a href="/complex/mtorc1/">mTORC1 <span style="color:#7C7569">75</span></a>'
                  '<a href="/complex/mtorc2/">mTORC2 <span style="color:#7C7569">14</span></a>'
                  '<a href="/drug/rapamycin/">Rapamycin</a>',
    faq_a=(
        "mTORC1 regulates protein synthesis, autophagy, and growth, and is rapamycin's "
        "direct target (75 studies in the Atlas). mTORC2 phosphorylates Akt/PKB and "
        "affects cell survival and glucose metabolism, and is NOT directly blocked by "
        "rapamycin — only indirectly, with chronic dosing (14 studies in the Atlas). "
        "The mTORC2 disruption is the likely mechanism behind rapamycin's insulin-"
        "resistance side effect."
    ),
)

# ---------------------------------------------------------------------------
# 3. What are mTOR inhibitors? (list)
# ---------------------------------------------------------------------------
add(
    slug="mtor-inhibitors-list",
    title="What Are mTOR Inhibitors? Full List | Oliver's mTOR Atlas",
    description="Rapalogs vs ATP-competitive TORKinibs vs bi-steric inhibitors — every class of mTOR inhibitor, with the Atlas study that established each.",
    h1="What are mTOR inhibitors? The full list, by mechanism",
    tldr=(
        "mTOR inhibitors fall into three mechanistic classes. <strong>Rapalogs</strong> "
        "(rapamycin/sirolimus and its analogs everolimus, temsirolimus, ridaforolimus) bind "
        "FKBP12 and allosterically block mTORC1 — the original class, in clinical use since "
        "1999. <strong>ATP-competitive inhibitors</strong> (\"TORKinibs\": Torin1, PP242, "
        "AZD8055, sapanisertib) jam the kinase's active site directly, blocking mTORC1 "
        "<em>and</em> mTORC2 — more complete inhibition, but less selective. "
        "<strong>Bi-steric inhibitors</strong> (RMC-6272 and related compounds) are the newest "
        "class, engineered for mTORC1 selectivity even higher than rapalogs while still "
        "hitting the rapamycin-resistant substrate 4E-BP1."
    ),
    sections=[
        ("Rapalogs — allosteric, FKBP12-dependent, mTORC1-selective", "<ul>" + "".join([
            cite("VEZ1975", "D", "rapamycin (then \"AY-22,989\") was first isolated from "
                 "<i>Streptomyces hygroscopicus</i>, a soil bacterium collected on Rapa Nui "
                 "(Easter Island) — the parent compound of every rapalog since."),
            cite("HUD2007", "B", "temsirolimus (CCI-779, an IV rapalog) extended median "
                 "overall survival to 10.9 vs 7.3 months over interferon alfa in "
                 "poor-prognosis metastatic kidney cancer — the trial that made rapalogs "
                 "an oncology drug class, not just a transplant drug."),
            cite("BAS2012", "B", "everolimus (RAD001, an oral rapalog) added to endocrine "
                 "therapy roughly doubled progression-free survival in hormone-resistant "
                 "advanced breast cancer (n=724 phase 3 RCT)."),
        ]) + "</ul>"),
        ("ATP-competitive inhibitors (\"TORKinibs\") — hit both complexes", "<ul>" + "".join([
            cite("THO2009", "D", "using Torin1, a true ATP-competitive inhibitor, this study "
                 "showed rapamycin actually leaves some mTORC1 jobs running (notably "
                 "4E-BP1 phosphorylation) — the discovery that motivated building "
                 "TORKinibs in the first place, for more complete mTORC1 blockade."),
        ]) + "</ul><p>TORKinibs block the shared catalytic site both complexes use, so "
             "they inhibit mTORC1 and mTORC2 together — more complete, but harder to "
             "dose without hitting mTORC2-dependent side effects.</p>"),
        ("Bi-steric inhibitors — the newest, most mTORC1-selective class", "<ul>" + "".join([
            cite("MEN2023", "C", "RMC-6272, a bi-steric molecule with >25-fold selectivity "
                 "for mTORC1 over mTORC2, completely suppresses mTORC1 — including "
                 "4E-BP1, the substrate rapamycin itself can't fully block — while largely "
                 "sparing mTORC2."),
            cite("SCH2025", "B", "the first human trial (n=57, advanced solid tumors) of a "
                 "bi-steric mTORC1-selective inhibitor; treatment-related hyperglycemia "
                 "was reported, showing even this more selective class isn't side-effect-free."),
        ]) + "</ul>"),
        ("Where this connects to the Atlas's open questions", "<p>Whether higher mTORC1 "
         "selectivity actually delivers rapamycin's longevity benefit without its metabolic "
         "cost is untested in humans at aging-relevant doses — see the open question on "
         '<a href="/question/mtorc1-selective-mtorc2-sparing-dosing-captures-longevity-without-insulin-resistance/">'
         "mTORC1-selective, mTORC2-sparing dosing</a>.</p>"),
    ],
    related_links='<a href="/drug/rapamycin/">Rapamycin <span style="color:#7C7569">38</span></a>'
                  '<a href="/drug/everolimus/">Everolimus <span style="color:#7C7569">14</span></a>'
                  '<a href="/complex/mtorc1/">mTORC1</a>'
                  '<a href="/complex/mtorc2/">mTORC2</a>',
    faq_a=(
        "Three classes: rapalogs (rapamycin/sirolimus, everolimus, temsirolimus, "
        "ridaforolimus — allosteric, FKBP12-dependent, mTORC1-selective, in clinical use "
        "since 1999); ATP-competitive \"TORKinibs\" (Torin1, PP242, AZD8055, sapanisertib — "
        "block the shared catalytic site, hitting both mTORC1 and mTORC2); and bi-steric "
        "inhibitors (RMC-6272 and related compounds — the newest class, >25-fold "
        "mTORC1-over-mTORC2 selectivity, in early human trials as of 2025)."
    ),
)

# ---------------------------------------------------------------------------
# 4. Rapamycin side effects
# ---------------------------------------------------------------------------
add(
    slug="rapamycin-side-effects",
    title="Rapamycin Side Effects — What the Evidence Shows | Oliver's mTOR Atlas",
    description="Rapamycin's side-effect profile differs sharply by dose and context — transplant immunosuppression vs. low-dose aging trials. What the Atlas's studies actually measured.",
    h1="What are rapamycin's side effects?",
    tldr=(
        "It depends enormously on dose. At the high, continuous doses used for decades to "
        "prevent transplant rejection, rapamycin (sirolimus) causes well-documented issues: "
        "mouth ulcers, elevated blood lipids, delayed wound healing, and — mechanistically — "
        "insulin resistance from chronic mTORC2 suppression. At the much lower, often "
        "intermittent doses tested in recent aging trials, the picture looks different: "
        "the Atlas's own human studies report the drug as well tolerated, with only minor "
        "adverse events."
    ),
    sections=[
        ("The mechanism behind the metabolic side effects", "<ul>" + "".join([
            cite("SAR2006", "D", "chronic rapamycin dosing eventually suppresses mTORC2 "
                 "signaling too, not just mTORC1 — and mTORC2 is what phosphorylates "
                 "Akt/PKB, a key node in insulin signaling. This is the mechanistic basis "
                 "for rapamycin-associated insulin resistance: it's a chronic-dosing, "
                 "off-target effect, not what the drug was designed to do."),
        ]) + "</ul>"),
        ("What the Atlas's low-dose human trials actually report", "<ul>" + "".join([
            cite("KRA2018", "B", "a safety-first pilot RCT (n=25, ages 70–95) asking the "
                 "basic tolerability question before any longevity trial: daily rapamycin "
                 "over 8+ weeks was well tolerated, with only minor adverse events."),
            cite("MAN2018", "B", "a low-dose, selective mTORC1-inhibiting combination in "
                 "264 elderly people improved immune function — the opposite direction of "
                 "\"more immunosuppression\", showing dose and selectivity change the "
                 "safety picture, not just the benefit."),
            cite("GIL2026", "B", "low-dose rapamycin in ME/CFS patients reduced fatigue "
                 "symptoms and modulated inflammation without the profile reported at "
                 "transplant-immunosuppression doses."),
            cite("MOE2025", "B", "a 48-week RCT (n=114) at an aging-relevant dose found no "
                 "significant change in its primary endpoint — a null efficacy result, "
                 "but also no signal of the adverse effects associated with chronic "
                 "high-dose use."),
        ]) + "</ul>"),
        ("Not every rapalog trial succeeds — or is side-effect free", "<ul>" + "".join([
            cite("MAN2021", "B", "the crucial reality check: after a promising phase 2a, "
                 "the large phase 3 trial (n=1024) of RTB101 (a rapalog-class mTOR "
                 "inhibitor) FAILED its primary endpoint for reducing respiratory illness — "
                 "a reminder that dose-sparing strategies don't automatically preserve "
                 "efficacy just because they reduce side effects."),
        ]) + "</ul>"),
        ("Why the dose distinction matters", "<p>Nearly everything people cite as "
         "\"rapamycin's side effects\" — mouth sores, hyperlipidemia, poor wound healing — "
         "comes from the transplant-immunosuppression literature, where the drug is dosed "
         "continuously and at levels that fully occupy mTORC1 (and, over time, mTORC2). "
         "The aging-research community's central bet is that much lower, often intermittent "
         "dosing keeps enough benefit while avoiding that profile — a bet the Atlas's open "
         "question on "
         '<a href="/question/mtorc1-selective-mtorc2-sparing-dosing-captures-longevity-without-insulin-resistance/">'
         "mTORC1-selective, mTORC2-sparing dosing</a> and "
         '<a href="/question/muscle-sparing-pulsed-mtorc1-inhibition/">pulsed dosing</a> '
         "track directly.</p>"),
    ],
    related_links='<a href="/drug/rapamycin/">Rapamycin <span style="color:#7C7569">38</span></a>'
                  '<a href="/complex/mtorc2/">mTORC2</a>'
                  '<a href="/complex/mtorc1/">mTORC1</a>',
    faq_a=(
        "At transplant-immunosuppression doses (continuous, high), documented side effects "
        "include mouth ulcers, elevated blood lipids, delayed wound healing, and insulin "
        "resistance — the last one traced mechanistically to chronic mTORC2 suppression "
        "(SAR2006), not mTORC1, rapamycin's intended target. At the lower, often "
        "intermittent doses tested in recent aging trials, human studies in the Atlas "
        "report the drug as well tolerated with only minor adverse events (KRA2018, "
        "GIL2026, MOE2025)."
    ),
)

# ---------------------------------------------------------------------------
# 5. Is autophagy required for the lifespan benefit?
# ---------------------------------------------------------------------------
add(
    slug="autophagy-required-lifespan",
    title="Is Autophagy Required for Rapamycin's Lifespan Benefit? | Oliver's mTOR Atlas",
    description="Autophagy is mTORC1's best-known downstream effect on longevity — but is it actually required for the lifespan extension, or just correlated with it? The Atlas's open question.",
    h1="Is autophagy actually required for the lifespan benefit of mTOR inhibition?",
    tldr=(
        "Autophagy — the cell's recycling process, suppressed by active mTORC1 and switched "
        "on when mTORC1 is inhibited — is the textbook explanation for how rapamycin "
        "extends lifespan. But \"autophagy goes up when you give rapamycin, and rapamycin "
        "extends lifespan\" is a correlation, not proof that autophagy is the mechanism. "
        "This is one of the Atlas's ten flagged open questions: an evidence gap, not a "
        "settled fact."
    ),
    sections=[
        ("What's actually established", "<ul>" + "".join([
            cite("SPI2010", "C", "long-term rapamycin prevented memory deficits and "
                 "lowered toxic amyloid-beta in an Alzheimer's mouse model — one of "
                 "several disease-model studies where an autophagy-linked benefit tracks "
                 "with mTORC1 inhibition."),
            cite("CAC2010", "C", "revealed a vicious cycle: amyloid-beta raises mTOR "
                 "activity, and high mTOR in turn blocks the autophagy needed to clear "
                 "amyloid and tau — so the disease feeds itself, and rapamycin breaks "
                 "the loop at the mTOR step."),
        ]) + "</ul><p>18 studies in the Atlas touch autophagy directly (9 animal, 9 "
             "mechanistic/in vitro) — a substantial mechanistic case that autophagy "
             "<em>changes</em> when mTORC1 is inhibited.</p>"),
        ("What's actually missing", "<p>What's missing is the causal experiment: block "
         "autophagy genetically (e.g. knock out an ATG gene) in an animal also given "
         "rapamycin, and see whether the lifespan benefit disappears. If it does, autophagy "
         "is required. If lifespan extends anyway, something else in the mTORC1 pathway is "
         "doing the work and autophagy is a correlated side effect, not the mechanism. This "
         "exact experiment is the Atlas's flagged evidence gap — read the full breakdown, "
         "including the proposed test, on the open question page: "
         '<a href="/question/is-autophagy-actually-required-for-the-mammalian-lifespan-benefit/">'
         "Is autophagy actually required for the mammalian lifespan benefit?</a></p>"),
        ("Why this matters beyond biology trivia", "<p>If autophagy isn't strictly "
         "required, then drugs or lifestyle interventions that boost autophagy through a "
         "completely different pathway (independent of mTOR) might not deliver the same "
         "longevity benefit rapamycin does — an assumption a lot of \"autophagy-boosting\" "
         "supplement marketing quietly skips over.</p>"),
    ],
    related_links='<a href="/process/autophagy/">Autophagy <span style="color:#7C7569">18</span></a>'
                  '<a href="/complex/mtorc1/">mTORC1</a>'
                  '<a href="/drug/rapamycin/">Rapamycin</a>',
    faq_a=(
        "Not proven — it's one of the Atlas's flagged open questions. Autophagy reliably "
        "increases when mTORC1 is inhibited, and several disease-model studies (SPI2010, "
        "CAC2010) show autophagy-linked benefits tracking with mTOR inhibition. But no "
        "study has shown the causal experiment: blocking autophagy genetically while still "
        "giving rapamycin, to see whether the lifespan benefit survives. Until that's done, "
        "autophagy's role is correlational, not confirmed as required."
    ),
)

# ---------------------------------------------------------------------------
# 6. Rapamycin dosing for longevity
# ---------------------------------------------------------------------------
add(
    slug="rapamycin-dosing-longevity",
    title="Rapamycin Dosing for Longevity — What the Studies Used | Oliver's mTOR Atlas",
    description="Continuous vs. intermittent, early vs. late-life — the actual dosing schedules behind rapamycin's mouse lifespan data, and why dosing is still an open question in humans.",
    h1="How is rapamycin dosed in the longevity studies?",
    tldr=(
        "The mouse lifespan data behind rapamycin's reputation as a longevity drug didn't "
        "use one fixed protocol. Two separate findings matter: rapamycin still works when "
        "started late in life (not just from birth), and it still works when given only "
        "briefly rather than continuously. Neither finding has been replicated with a "
        "matched dosing protocol in a human lifespan trial — that trial doesn't exist and "
        "may never be practical to run."
    ),
    sections=[
        ("Late-onset, continuous dosing", "<ul>" + "".join([
            cite("HAR2009", "C", "rapamycin fed starting at 600 days of age — "
                 "late-middle-age for a mouse — extended median lifespan by 9–14% in both "
                 "sexes. This was the finding that established rapamycin doesn't need to "
                 "start early to work."),
        ]) + "</ul>"),
        ("Brief, late-life dosing", "<ul>" + "".join([
            cite("BIT2016", "C", "just 3 months of rapamycin, given late in life, increased "
                 "subsequent life expectancy by up to 60% — the lifespan benefit doesn't "
                 "require lifelong daily dosing, at least in mice."),
        ]) + "</ul>"),
        ("Why intermittent/pulsed dosing is a live research question, not settled practice",
         "<p>If a few months of treatment can extend lifespan as much as continuous dosing "
         "in mice, the practical implication for humans is large: intermittent dosing could "
         "in principle deliver most of the benefit while limiting cumulative exposure to "
         "side effects like the mTORC2-linked insulin resistance discussed in the Atlas's "
         '<a href="/answers/rapamycin-side-effects/">side-effects answer page</a>. But the '
         "specific schedule — how often, how much, for how long — hasn't been established "
         "in humans at longevity-relevant doses. This is tracked directly by two of the "
         "Atlas's open questions: "
         '<a href="/question/muscle-sparing-pulsed-mtorc1-inhibition/">muscle-sparing '
         "pulsed mTORC1 inhibition</a> and "
         '<a href="/question/mtorc1-selective-mtorc2-sparing-dosing-captures-longevity-without-insulin-resistance/">'
         "mTORC1-selective, mTORC2-sparing dosing</a>.</p>"),
        ("What human trials have actually tested", "<ul>" + "".join([
            cite("KRA2018", "B", "a safety-first pilot RCT in older adults (n=25, ages "
                 "70–95) testing daily low-dose rapamycin over 8+ weeks for basic "
                 "tolerability — not a lifespan endpoint."),
            cite("MOE2025", "B", "the first completed long-term RCT of rapamycin for "
                 "healthy human aging (48 weeks, n=114) — still not a lifespan endpoint, "
                 "and its primary metabolic endpoint showed no significant change."),
        ]) + "</ul>"),
    ],
    related_links='<a href="/drug/rapamycin/">Rapamycin <span style="color:#7C7569">38</span></a>'
                  '<a href="/complex/mtorc1/">mTORC1</a>'
                  '<a href="/complex/mtorc2/">mTORC2</a>',
    faq_a=(
        "The mouse data uses varied protocols, not one fixed dose. Two key findings: "
        "rapamycin still extends lifespan when started late (600 days old — HAR2009, 9–14% "
        "median lifespan increase) and when given only briefly (3 months late in life — "
        "BIT2016, up to 60% increase in subsequent life expectancy). No human trial has "
        "tested a matched dosing protocol against a lifespan endpoint — human trials to "
        "date (KRA2018, MOE2025) have tested safety and short-term metabolic markers, "
        "not survival."
    ),
)

# ---------------------------------------------------------------------------
# 7. What is mTOR?
# ---------------------------------------------------------------------------
add(
    slug="what-is-mtor",
    title="What Is mTOR? The Basics | Oliver's mTOR Atlas",
    description="mTOR in plain language: what it is, what it does, and how a soil bacterium from Easter Island led to its discovery — with the Atlas's 62 mTOR-specific studies behind it.",
    h1="What is mTOR?",
    tldr=(
        "mTOR (mechanistic target of rapamycin, also written FRAP1 in older literature) is "
        "a serine/threonine protein kinase — an enzyme that turns other proteins on or off "
        "by adding phosphate groups to them. It sits at the center of how a cell decides "
        "whether to grow: when nutrients, growth factors, and energy are abundant, mTOR is "
        "active and pushes the cell to build proteins and grow; when any of those are "
        "scarce, mTOR switches off and the cell shifts to conserving and recycling "
        "resources instead."
    ),
    sections=[
        ("Named after the drug that found it, not the other way around",
         "<p>mTOR wasn't discovered by studying growth signaling directly — it was found "
         "because of a drug.</p><ul>" + "".join([
            cite("VEZ1975", "D", "rapamycin was first isolated in 1975 from "
                 "<i>Streptomyces hygroscopicus</i>, a bacterium in a soil sample from Rapa "
                 "Nui (Easter Island) — originally studied as an antifungal antibiotic, "
                 "years before anyone knew what it did to cells."),
            cite("HEI1991", "D", "geneticists studying why yeast cells resist "
                 "growth-arrest by the immunosuppressant rapamycin found the genes "
                 "responsible — TOR1 and TOR2 (\"target of rapamycin\") — giving the "
                 "pathway its name before the human version was even known."),
            cite("PRI1992", "D", "showed rapamycin inhibits the 70-kilodalton S6 kinase, "
                 "identifying one of the first known downstream targets of the "
                 "then-unnamed pathway in mammalian cells."),
        ]) + "</ul><p>The mammalian version of TOR — what we now call mTOR — was cloned "
             "by three independent labs in 1994, using rapamycin itself as the molecular "
             "hook to fish it out.</p>"),
        ("What mTOR actually does", "<p>mTOR works as the catalytic core of two distinct "
         "protein complexes with different jobs — "
         '<a href="/answers/mtorc1-vs-mtorc2/">mTORC1 and mTORC2</a>, covered in full on '
         "their own answer page. In short: mTORC1 is the nutrient/growth-factor sensor "
         "that controls protein synthesis, autophagy, and growth — and is rapamycin's "
         "direct target. mTORC2 is involved in cell survival and glucose metabolism, and "
         "is only reached by rapamycin indirectly, with chronic dosing.</p>"),
        ("Why it matters beyond basic biology", "<p>Because mTOR sits at the intersection "
         "of nutrient sensing, growth, and metabolism, its dysregulation shows up across an "
         "unusually wide range of conditions: cancer (see "
         '<a href="/answers/mtor-cancer-connection/">how mTOR connects to cancer</a>), '
         "the genetic disorder tuberous sclerosis complex (where a mutation leaves mTORC1 "
         "stuck permanently \"on\"), and the biology of aging, where inhibiting it with "
         "rapamycin is the single most consistent way known to extend lifespan in "
         "laboratory animals across species.</p>"),
    ],
    related_links='<a href="/gene/mtor/">mTOR <span style="color:#7C7569">62</span></a>'
                  '<a href="/complex/mtorc1/">mTORC1</a>'
                  '<a href="/complex/mtorc2/">mTORC2</a>'
                  '<a href="/drug/rapamycin/">Rapamycin</a>',
    faq_a=(
        "mTOR (mechanistic target of rapamycin) is a serine/threonine kinase that acts as "
        "a cell's central growth-vs-conservation switch, integrating nutrient availability, "
        "growth factor signals, and cellular energy status. It forms two complexes, "
        "mTORC1 (protein synthesis, autophagy, growth) and mTORC2 (cell survival, glucose "
        "metabolism). It was discovered indirectly, through the drug rapamycin — isolated "
        "from a soil bacterium on Easter Island in 1975 — years before the protein itself "
        "was identified and cloned in 1994."
    ),
)

# ---------------------------------------------------------------------------
# 8. Rapamycin vs metformin
# ---------------------------------------------------------------------------
add(
    slug="rapamycin-vs-metformin",
    title="Rapamycin vs Metformin for Longevity | Oliver's mTOR Atlas",
    description="Two very different mechanisms, two very different evidence bases — how rapamycin's direct mTOR inhibition compares to metformin's indirect, AMPK-mediated route.",
    h1="Rapamycin vs metformin — how do they compare for longevity?",
    tldr=(
        "They're often mentioned together as geroprotector candidates, but they work "
        "differently and have very different evidence behind them in this Atlas. Rapamycin "
        "directly and potently inhibits mTORC1 (its designed mechanism) and has 38 "
        "evidence-graded studies here, including a Tier A systematic review. Metformin "
        "inhibits mTORC1 only indirectly — mainly by activating AMPK, though it also acts "
        "on mTORC1 through AMPK-independent routes — and has just 3 studies in the Atlas, "
        "none of them a randomized trial for a longevity endpoint."
    ),
    sections=[
        ("Mechanism: direct vs indirect", "<p>Rapamycin binds FKBP12 and directly blocks "
         "mTORC1's Raptor-dependent activity — a precise, well-characterized mechanism. "
         "Metformin's route to mTORC1 is murkier and is itself an open scientific question: "
         "it activates AMPK, an energy-sensor that inhibits mTORC1 upstream, but studies "
         "in the Atlas show metformin still suppresses hepatic gluconeogenesis in "
         "AMPK-null and LKB1-null mouse liver, and still inhibits mTORC1 in AMPK-null "
         "cells via the Rag GTPases — meaning at least part of its action bypasses AMPK "
         "entirely.</p>"),
        ("What the human evidence actually shows", "<ul>" + "".join([
            cite("BAN2014", "B", "diabetic patients started on metformin had longer median "
                 "survival than matched non-diabetic controls who weren't on the drug. "
                 "Retrospective and observational — consistent with a benefit, but not "
                 "proof of one, since diabetics who get prescribed and stay on metformin "
                 "may differ from non-diabetics in other health-relevant ways."),
            cite("LEE2024", "A", "the Atlas's one systematic review of an mTOR-pathway "
                 "drug for human aging covers rapamycin and its rapalogs — not metformin, "
                 "reflecting how much further along the rapamycin evidence base is for "
                 "this specific question."),
        ]) + "</ul>"),
        ("The practical trade-off", "<p>Metformin has decades of safety data as an "
         "FDA-approved diabetes drug, is inexpensive, and is already prescribed off-label "
         "by some longevity-focused physicians — its safety profile is a real practical "
         "advantage. But the Atlas's evidence for metformin specifically extending healthy "
         "lifespan rests on one retrospective observational study, not a randomized trial. "
         "Rapamycin's mechanism is more direct and its dose-response in animal models "
         "better characterized, but comes with the mTORC2-linked side-effect profile "
         "covered on the "
         '<a href="/answers/rapamycin-side-effects/">side-effects answer page</a>.</p>'),
    ],
    related_links='<a href="/drug/rapamycin/">Rapamycin <span style="color:#7C7569">38</span></a>'
                  '<a href="/drug/metformin/">Metformin <span style="color:#7C7569">3</span></a>'
                  '<a href="/complex/mtorc1/">mTORC1</a>',
    faq_a=(
        "Rapamycin directly and potently inhibits mTORC1 (38 studies in the Atlas, "
        "including one Tier A systematic review). Metformin inhibits mTORC1 mostly "
        "indirectly, via AMPK activation (though some of its action is AMPK-independent), "
        "and has only 3 studies in the Atlas — the human evidence (BAN2014) is a "
        "retrospective observational study of diabetic patients, not a randomized trial "
        "for a longevity endpoint. Metformin has a longer safety track record as an "
        "approved diabetes drug; rapamycin's mechanism and animal dose-response are "
        "better characterized."
    ),
)

# ---------------------------------------------------------------------------
# 9. Are sirolimus and everolimus the same drug?
# ---------------------------------------------------------------------------
add(
    slug="sirolimus-everolimus-same-drug",
    title="Sirolimus vs Everolimus — Same Drug? | Oliver's mTOR Atlas",
    description="Everolimus is a chemically modified derivative of sirolimus (rapamycin), not the same molecule — here's exactly what differs and why it matters clinically.",
    h1="Are sirolimus and everolimus the same drug?",
    tldr=(
        "No — closely related, but not the same molecule. Sirolimus <em>is</em> rapamycin "
        "(same drug, two names). Everolimus (brand names include Afinitor and Zortress) is "
        "a semi-synthetic derivative of sirolimus — a \"rapalog\" — with one chemical "
        "modification (a 2-hydroxyethyl group at position 40) that gives it better oral "
        "bioavailability and a shorter half-life, making it easier to dose predictably for "
        "cancer treatment. Both share the same core mechanism: binding FKBP12 and "
        "allosterically inhibiting mTORC1."
    ),
    sections=[
        ("Same target, same core mechanism", "<p>Everolimus works the same way sirolimus "
         "does — it's why the Atlas's systematic review of aging-relevant mTOR-inhibitor "
         "trials covers both together as one drug class.</p><ul>" + "".join([
            cite("LEE2024", "A", "the Atlas's systematic review of \"rapamycin/rapalogs\" "
                 "in humans explicitly groups sirolimus and its analogs, including "
                 "everolimus, as one mechanistic class for the purposes of assessing "
                 "aging-relevant effects."),
        ]) + "</ul>"),
        ("Where everolimus has its own, separate evidence base", "<p>Despite the shared "
         "mechanism, everolimus has been studied far more extensively than sirolimus in "
         "oncology specifically — it has 14 studies in the Atlas, 11 of them direct human "
         "trials, versus fewer human oncology trials for sirolimus itself.</p><ul>" + "".join([
            cite("BAS2012", "B", "a phase 3 RCT (n=724) showing everolimus added to "
                 "endocrine therapy roughly doubles progression-free survival in "
                 "hormone-resistant advanced breast cancer."),
            cite("YAO2011", "B", "a phase 3 RCT (n=410) that made everolimus a standard "
                 "treatment for pancreatic neuroendocrine tumors, more than doubling "
                 "progression-free survival (11.0 vs 4.6 months)."),
            cite("FRA2013", "B", "a phase 3 RCT (n=117) in tuberous sclerosis showing "
                 "everolimus shrinks SEGA brain tumors by ≥50% in over a third of "
                 "patients — a genetic disease where mTOR is stuck permanently \"on\"."),
        ]) + "</ul>"),
        ("The practical difference", "<p>The two drugs aren't interchangeable in clinical "
         "practice, even though they share a mechanism: sirolimus is mainly used for "
         "transplant immunosuppression (its original, longest-standing indication) and is "
         "the molecule almost all the aging/longevity mouse and human trials in this Atlas "
         "actually test. Everolimus is mainly used in oncology and for tuberous sclerosis "
         "complex, where its more predictable pharmacokinetics matter for precise dosing "
         "against tumors.</p>"),
    ],
    related_links='<a href="/drug/rapamycin/">Rapamycin <span style="color:#7C7569">38</span></a>'
                  '<a href="/drug/everolimus/">Everolimus <span style="color:#7C7569">14</span></a>'
                  '<a href="/complex/mtorc1/">mTORC1</a>',
    faq_a=(
        "No — sirolimus is rapamycin itself, while everolimus is a semi-synthetic "
        "chemical derivative of it (a \"rapalog\"), modified for better oral "
        "bioavailability and a shorter, more predictable half-life. Both bind FKBP12 and "
        "allosterically inhibit mTORC1 through the same core mechanism. Sirolimus is "
        "mainly used for transplant immunosuppression and is the molecule tested in most "
        "aging/longevity studies; everolimus is mainly used in oncology and for tuberous "
        "sclerosis complex, where 11 of its 14 Atlas studies are direct human trials."
    ),
)

# ---------------------------------------------------------------------------
# 10. How does mTOR connect to cancer?
# ---------------------------------------------------------------------------
add(
    slug="mtor-cancer-connection",
    title="How Does mTOR Connect to Cancer? | Oliver's mTOR Atlas",
    description="From a genetic proof-of-concept disease to three FDA-approved cancer indications — how mTOR hyperactivation drives tumors, and where mTOR inhibitors are already standard treatment.",
    h1="How does mTOR connect to cancer?",
    tldr=(
        "mTORC1 promotes cell growth and proliferation — the same activity that makes it a "
        "longevity target makes its hyperactivation a cancer risk. The clearest "
        "proof-of-concept is tuberous sclerosis complex, a genetic disorder where losing "
        "the TSC1/TSC2 brake leaves mTORC1 stuck permanently \"on\" and drives tumor "
        "growth — and where an mTOR inhibitor (everolimus) is a direct, FDA-approved "
        "treatment. mTOR inhibitors are also approved treatments in kidney cancer, "
        "hormone-resistant breast cancer, and pancreatic neuroendocrine tumors."
    ),
    sections=[
        ("The genetic proof of concept: tuberous sclerosis complex", "<ul>" + "".join([
            cite("FRA2013", "B", "a phase 3 RCT (n=117) in TSC — the disease where mTOR is "
                 "stuck \"on\" by a genetic fault — showed everolimus shrinks SEGA brain "
                 "tumors by ≥50% in 35% of patients versus far fewer on placebo."),
            cite("BIS2013", "B", "the companion phase 3 RCT (n=118) targeting kidney "
                 "tumors (angiomyolipomas) in the same disease: everolimus shrank them by "
                 "≥50% in 42% of patients."),
            cite("GAO2026B", "B", "in a multicenter cohort of 183 TSC-associated renal "
                 "angiomyolipoma patients, everolimus reduced tumor volume by ≥50% in 44% "
                 "of patients at 3 months, rising further with continued treatment."),
        ]) + "</ul><p>TSC matters because it isolates mTOR as the cause, not just a "
             "correlate — the tumors exist specifically because mTORC1 can't be switched "
             "off, and switching it off pharmacologically shrinks them.</p>"),
        ("Sporadic cancers where mTOR signaling gets switched on", "<ul>" + "".join([
            cite("BAS2012", "B", "in hormone-receptor-positive advanced breast cancer, "
                 "resistance to endocrine therapy is partly driven by mTOR signaling "
                 "switching on; adding everolimus to endocrine therapy roughly doubled "
                 "progression-free survival in a phase 3 RCT (n=724)."),
            cite("HUD2007", "B", "in poor-prognosis metastatic kidney cancer, temsirolimus "
                 "(a rapalog) extended median overall survival to 10.9 vs 7.3 months over "
                 "standard interferon therapy."),
            cite("YAO2011", "B", "in pancreatic neuroendocrine tumors, everolimus more "
                 "than doubled progression-free survival (11.0 vs 4.6 months) in a phase "
                 "3 RCT (n=410), making it a standard treatment for this cancer."),
        ]) + "</ul>"),
        ("The double-edged-sword problem for longevity research", "<p>This is exactly why "
         "mTOR inhibition is scientifically interesting for aging, not just cancer: a "
         "pathway that drives unwanted growth when stuck \"on\" is a plausible target for "
         "slowing the growth-related decline of aging when partially turned down. But it "
         "also means any long-term, population-wide use of mTOR inhibitors for healthy "
         "aging needs to reckon with a drug class whose clearest, best-proven human "
         "benefit so far is in treating cancers that mTOR hyperactivation helps drive.</p>"),
    ],
    related_links='<a href="/disease/tuberous-sclerosis-complex/">Tuberous sclerosis complex <span style="color:#7C7569">5</span></a>'
                  '<a href="/disease/breast-cancer/">Breast cancer <span style="color:#7C7569">3</span></a>'
                  '<a href="/disease/renal-cell-carcinoma-rcc/">Renal cell carcinoma (RCC) <span style="color:#7C7569">3</span></a>'
                  '<a href="/drug/everolimus/">Everolimus</a>'
                  '<a href="/complex/mtorc1/">mTORC1</a>',
    faq_a=(
        "mTORC1 promotes cell growth and proliferation, so its hyperactivation is a "
        "cancer driver. The clearest proof is tuberous sclerosis complex, a genetic "
        "disorder where losing the TSC1/TSC2 brake leaves mTORC1 permanently active and "
        "causes tumors — treatable with the mTOR inhibitor everolimus (FRA2013, BIS2013). "
        "mTOR inhibitors are also FDA-approved treatments in kidney cancer (temsirolimus, "
        "HUD2007), hormone-resistant breast cancer (everolimus, BAS2012), and pancreatic "
        "neuroendocrine tumors (everolimus, YAO2011)."
    ),
)

print("Loaded {} answer page definitions".format(len(PAGES)))


# ===========================================================================
# GLOSSARY -- 25 terms, DefinedTermSet schema, linked to real Atlas entity
# pages wherever one exists (verified against the live repo's directory
# listing on 2026-08-22 -- never link a slug that wasn't confirmed to exist).
# ===========================================================================

GLOSSARY = [
    ("mTOR", "/gene/mtor/", "62",
     "Mechanistic target of rapamycin. A serine/threonine kinase that acts as a cell's "
     "central growth-vs-conservation switch, integrating nutrient availability, growth "
     "factor signals, and energy status. Forms two distinct complexes, mTORC1 and mTORC2."),
    ("mTORC1", "/complex/mtorc1/", "75",
     "mTOR Complex 1. Regulates protein synthesis, autophagy, and cell growth in response "
     "to nutrients and growth factors. This is the complex rapamycin directly and "
     "potently inhibits."),
    ("mTORC2", "/complex/mtorc2/", "14",
     "mTOR Complex 2. Phosphorylates Akt/PKB and affects cell survival and glucose "
     "metabolism. Not directly blocked by rapamycin — only reached indirectly, with "
     "chronic dosing, which is the likely source of rapamycin's insulin-resistance "
     "side effect."),
    ("Rapamycin (Sirolimus)", "/drug/rapamycin/", "38",
     "The founding mTOR inhibitor, first isolated in 1975 from a soil bacterium on Rapa "
     "Nui (Easter Island). Binds the protein FKBP12 and allosterically blocks mTORC1. "
     "The most consistently lifespan-extending drug in laboratory animal studies."),
    ("Rapalog", "/answers/mtor-inhibitors-list/", None,
     "Any chemical analog of rapamycin engineered from the same core structure — "
     "everolimus, temsirolimus, and ridaforolimus are the main examples. All share "
     "rapamycin's FKBP12-dependent, mTORC1-selective mechanism."),
    ("Everolimus", "/drug/everolimus/", "14",
     "A semi-synthetic rapalog with better oral bioavailability and a shorter half-life "
     "than rapamycin itself. Used clinically in oncology (breast cancer, pancreatic "
     "neuroendocrine tumors, kidney cancer) and for tuberous sclerosis complex."),
    ("Metformin", "/drug/metformin/", "3",
     "A widely used antidiabetic drug that activates AMPK and inhibits mTORC1 indirectly "
     "— though part of its action bypasses AMPK entirely. Frequently proposed as a "
     "geroprotector candidate alongside rapamycin, with a weaker evidence base in "
     "this Atlas."),
    ("Resveratrol", "/drug/resveratrol/", "3",
     "A plant polyphenol popularized as a sirtuin activator and \"calorie-restriction "
     "mimetic.\" Failed to extend lifespan in the Interventions Testing Program's mouse "
     "studies and showed no metabolic benefit in a human RCT."),
    ("Autophagy", "/process/autophagy/", "18",
     "The cell's internal recycling process — breaking down and reusing damaged proteins "
     "and organelles. Suppressed by active mTORC1 and switched on when mTORC1 is "
     "inhibited. Widely proposed, but not proven, as the mechanism behind rapamycin's "
     "lifespan benefit."),
    ("Cellular senescence", "/process/cellular-senescence/", "3",
     "A state in which a cell permanently stops dividing but stays alive, secreting "
     "inflammatory signals (the SASP). Senescent cells accumulate with age and drive "
     "age-related disease; mTOR both promotes the senescent state and powers its "
     "inflammatory secretions."),
    ("TSC1/TSC2", "/gene/tsc1-tsc2/", None,
     "A two-protein complex that acts as the principal brake on mTORC1, integrating "
     "signals about cellular stress and growth-factor availability. Loss-of-function "
     "mutations in either gene cause tuberous sclerosis complex."),
    ("Tuberous sclerosis complex", "/disease/tuberous-sclerosis-complex/", "5",
     "A genetic disorder caused by TSC1/TSC2 mutations that leaves mTORC1 stuck "
     "permanently active, causing benign tumors in the brain, kidney, and elsewhere. The "
     "clearest human proof-of-concept that mTOR hyperactivation alone can drive tumor "
     "growth — and that mTOR inhibitors (everolimus) can treat it directly."),
    ("AMPK", "/gene/ampk/", None,
     "AMP-activated protein kinase — a cellular energy sensor that activates when ATP "
     "runs low. Inhibits mTORC1 upstream, making it mTOR's functional opposite in the "
     "growth-vs-conservation decision. The main (though not sole) route by which "
     "metformin affects mTORC1."),
    ("Akt/PKB", "/gene/akt-pkb/", None,
     "A kinase downstream of growth-factor signaling (via PI3K) that activates mTORC1 and "
     "is itself phosphorylated by mTORC2 — placing it at a hinge point between the "
     "pathway's two complexes."),
    ("4E-BP1", "/gene/4e-bp1/", None,
     "A direct mTORC1 substrate that, when phosphorylated, releases the translation "
     "initiation factor eIF4E to start protein synthesis. Notable as one of the mTORC1 "
     "substrates rapamycin blocks incompletely — a gap that motivated newer, more potent "
     "ATP-competitive and bi-steric mTOR inhibitors."),
    ("S6K1", "/gene/s6k1/", None,
     "p70 S6 kinase — one of the first mTORC1 substrates identified, back when the "
     "pathway itself was still unnamed. Promotes protein synthesis and cell growth "
     "downstream of active mTORC1."),
    ("Raptor", "/gene/raptor/", None,
     "Regulatory-associated protein of mTOR — the defining scaffold subunit of mTORC1, "
     "required for rapamycin's allosteric inhibition of the complex."),
    ("Rictor", "/gene/rictor/", None,
     "Rapamycin-insensitive companion of mTOR — the defining scaffold subunit of mTORC2, "
     "and the reason mTORC2 isn't directly blocked by rapamycin the way mTORC1 is."),
    ("Rheb", "/gene/rheb/", None,
     "A small GTPase that directly activates mTORC1 at the lysosomal membrane once "
     "TSC1/TSC2's inhibitory brake is released. The final switch mTORC1's upstream "
     "signals converge on."),
    ("Rag GTPases", "/gene/rag-gtpases/", None,
     "A family of GTPases that recruit mTORC1 to the lysosomal surface in response to "
     "amino acid availability — the mechanism by which mTORC1 senses nutrients, "
     "independent of growth-factor signaling through Rheb."),
    ("TFEB", "/gene/tfeb/", None,
     "A transcription factor that drives expression of autophagy and lysosomal genes. "
     "Normally kept inactive by mTORC1-dependent phosphorylation; when mTORC1 is "
     "inhibited, TFEB moves to the nucleus and switches on the cell's recycling program."),
    ("Lysosome", "/organelle/lysosome/", None,
     "The cell's main digestive/recycling organelle, and the physical platform where "
     "mTORC1 is activated (via the Rag GTPases and Ragulator complex) and where "
     "autophagy's breakdown products are processed."),
    ("Caloric restriction", "/intervention/caloric-restriction/", None,
     "Sustained reduction in calorie intake without malnutrition — the original, "
     "best-replicated lifespan-extending intervention across species, and one that "
     "lowers mTORC1 activity through multiple converging nutrient- and energy-sensing "
     "pathways."),
    ("Insulin resistance", "/outcome/insulin-resistance/", None,
     "A reduced cellular response to insulin. Relevant to mTOR biology as rapamycin's "
     "best-documented metabolic side effect, mechanistically linked to chronic "
     "suppression of mTORC2 rather than mTORC1, its intended target."),
    ("Evidence tier (A–D)", None, None,
     "This Atlas's own grading system for how directly a study supports a claim: "
     "A = systematic review/meta-analysis, B = human trial, C = animal model, "
     "D = mechanistic, in vitro, or review. Every study and every claim in the Atlas "
     "carries one of these tiers, visible as a colored badge next to its citation."),
]


def glossary_page():
    dts = []
    for term, url, count, definition in GLOSSARY:
        entry = {"@type": "DefinedTerm", "name": term,
                 "description": re.sub(r'\s+', ' ', definition).strip()}
        if url:
            entry["url"] = "https://mtor-atlas.org" + url
        dts.append(entry)
    ld = {
        "@context": "https://schema.org", "@type": "DefinedTermSet",
        "name": "Oliver's mTOR Atlas — Glossary",
        "description": "25 core terms for understanding mTOR biology, from the complexes "
                        "themselves to the genes, drugs, and processes around them.",
        "url": "https://mtor-atlas.org/glossary/",
        "hasDefinedTerm": dts,
    }
    bc = breadcrumb_jsonld_flat("Glossary", "https://mtor-atlas.org/glossary/")

    dl = ['<dl class="gloss">']
    for term, url, count, definition in GLOSSARY:
        name_html = ('<a href="{}">{}</a>'.format(url, esc(term)) if url else esc(term))
        count_html = (' <span class="cnt">({} studies in the Atlas)</span>'.format(count)
                      if count else "")
        dl.append("<dt>{}{}</dt><dd>{}</dd>".format(name_html, count_html, definition))
    dl.append("</dl>")

    body_html = (
        '<p class="summary">25 core terms for understanding mTOR biology — from the two '
        "mTOR complexes themselves down to the individual genes, drugs, and processes "
        "that make up the pathway. Each term links to its full evidence page in the "
        "Atlas where one exists.</p>" + "".join(dl)
    )
    head = HEAD_TMPL.format(
        title=esc("Glossary of mTOR Terms | Oliver's mTOR Atlas"),
        description=esc("25 core mTOR-pathway terms, plain-language definitions, linked to "
                         "the full evidence-graded Atlas entry for each."),
        canonical="https://mtor-atlas.org/glossary/",
        jsonld="\n".join([
            '<script type="application/ld+json">\n' + json.dumps(ld, ensure_ascii=False, indent=1) + '\n</script>',
            bc,
        ]),
        style=STYLE,
    )
    out = [head, "<body>\n" + topbar_html("ask") + '\n<div class="wrap">']
    out.append('<nav class="crumb"><a href="https://mtor-atlas.org/">Oliver\'s mTOR Atlas</a> '
               '› Glossary</nav>')
    out.append("<h1>Glossary of mTOR terms</h1>")
    out.append(body_html)
    out.append('<p><a class="cta" href="https://mtor-atlas.org/">Open in the Atlas explorer</a></p>')
    out.append(
        '<footer class="oma-footer">\n'
        "<p><strong>Oliver's mTOR Atlas</strong> — an evidence-graded database of the mTOR\n"
        "pathway. Every entry traces to a primary paper, graded A–D by strength of evidence.\n"
        "Curated by Oliver Barton, Prague.</p>\n"
        '<div class="oma-footer-links">\n'
        '<a href="https://mtor-atlas.org/">Full interactive Atlas</a> · '
        '<a href="https://mtor-atlas.org/browse/">Browse the Atlas</a> · '
        '<a href="https://mtor-atlas.org/academy/">Academy</a> · '
        '<a href="https://mtor-atlas.org/answers/">Answers</a> · '
        '<a href="https://github.com/open-mtor-atlas/atlas">GitHub</a>\n'
        '</div>\n</footer>'
    )
    out.append("</div>\n</body>\n</html>\n")
    return "\n".join(out)


def breadcrumb_jsonld_flat(name, url):
    return """<script type="application/ld+json">
{{
 "@context": "https://schema.org",
 "@type": "BreadcrumbList",
 "itemListElement": [
  {{"@type": "ListItem", "position": 1, "name": "Oliver's mTOR Atlas", "item": "https://mtor-atlas.org/"}},
  {{"@type": "ListItem", "position": 2, "name": {name}}}
 ]
}}
</script>""".format(name=jstr(name))


# ===========================================================================
# /answers/ HUB PAGE -- avoids orphan pages (linked from footer + glossary +
# each other, but each answer page also needs an index that links back to
# ALL 10, matching the site's existing pattern of /browse/ as a rozcestník).
# ===========================================================================

def hub_page():
    ld = {
        "@context": "https://schema.org", "@type": "CollectionPage",
        "name": "Answers", "url": "https://mtor-atlas.org/answers/",
        "description": "Direct answers to the most common questions about mTOR, rapamycin, "
                        "and longevity, each graded by the evidence behind it.",
    }
    bc = breadcrumb_jsonld_flat("Answers", "https://mtor-atlas.org/answers/")
    items = "".join(
        '<p style="margin:0 0 10px"><a href="/answers/{slug}/"><strong>{h1}</strong></a><br>'
        '<span style="color:#55524C;font-size:14px">{desc}</span></p>'.format(
            slug=p["slug"], h1=esc(p["h1"]), desc=esc(p["description"]))
        for p in PAGES
    )
    body_html = (
        '<p class="summary">Ten direct answers to the questions people most often ask '
        "about mTOR, rapamycin, and longevity — each graded by the same A–D evidence "
        "system used throughout the Atlas, and each linking back to the primary studies "
        "behind it.</p><h2>All 10 answers</h2>" + items +
        '<h2>Also see</h2><p><a href="/glossary/">Glossary of mTOR terms</a> · '
        '<a href="/browse/">Browse all studies and topics</a></p>'
    )
    head = HEAD_TMPL.format(
        title=esc("Answers | Oliver's mTOR Atlas"),
        description=esc("Direct, evidence-graded answers to the most common questions "
                         "about mTOR, rapamycin, and longevity."),
        canonical="https://mtor-atlas.org/answers/",
        jsonld="\n".join([
            '<script type="application/ld+json">\n' + json.dumps(ld, ensure_ascii=False, indent=1) + '\n</script>',
            bc,
        ]),
        style=STYLE,
    )
    out = [head, "<body>\n" + topbar_html("ask") + '\n<div class="wrap">']
    out.append('<nav class="crumb"><a href="https://mtor-atlas.org/">Oliver\'s mTOR Atlas</a> '
               '› Answers</nav>')
    out.append("<h1>Answers</h1>")
    out.append(body_html)
    out.append('<p><a class="cta" href="https://mtor-atlas.org/">Open in the Atlas explorer</a></p>')
    out.append(
        '<footer class="oma-footer">\n'
        "<p><strong>Oliver's mTOR Atlas</strong> — an evidence-graded database of the mTOR\n"
        "pathway. Every entry traces to a primary paper, graded A–D by strength of evidence.\n"
        "Curated by Oliver Barton, Prague.</p>\n"
        '<div class="oma-footer-links">\n'
        '<a href="https://mtor-atlas.org/">Full interactive Atlas</a> · '
        '<a href="https://mtor-atlas.org/browse/">Browse the Atlas</a> · '
        '<a href="https://mtor-atlas.org/academy/">Academy</a> · '
        '<a href="https://mtor-atlas.org/glossary/">Glossary</a> · '
        '<a href="https://github.com/open-mtor-atlas/atlas">GitHub</a>\n'
        '</div>\n</footer>'
    )
    out.append("</div>\n</body>\n</html>\n")
    return "\n".join(out)


def sitemap_answers_xml():
    urls = ["https://mtor-atlas.org/answers/", "https://mtor-atlas.org/glossary/"]
    urls += ["https://mtor-atlas.org/answers/{}/".format(p["slug"]) for p in PAGES]
    lines = ['<?xml version="1.0" encoding="UTF-8"?>',
             '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    for u in urls:
        lines.append('  <url><loc>{}</loc><changefreq>monthly</changefreq>'
                     '<priority>0.7</priority></url>'.format(u))
    lines.append('</urlset>')
    lines.append('')
    return "\n".join(lines)


def write(rel_path, content):
    fp = os.path.join(OUT, rel_path)
    os.makedirs(os.path.dirname(fp), exist_ok=True)
    with open(fp, "w", encoding="utf-8") as f:
        f.write(content)
        f.flush()
        os.fsync(f.fileno())
    # independent fresh read-back verification
    with open(fp, encoding="utf-8") as f:
        check = f.read()
    assert check == content, "write/readback mismatch for " + fp
    return len(content)


if __name__ == "__main__":
    os.makedirs(OUT, exist_ok=True)
    assert len(PAGES) == 10, "expected exactly 10 answer pages, got {}".format(len(PAGES))
    assert len(GLOSSARY) == 25, "expected exactly 25 glossary terms, got {}".format(len(GLOSSARY))

    total = 0
    for p in PAGES:
        html_out = page(p["slug"], p["title"], p["description"], p["h1"], p["tldr"],
                        p["sections"], p["related_links"], p["faq_q"], p["faq_a"])
        n = write("answers/{}/index.html".format(p["slug"]), html_out)
        total += n
        print("wrote answers/{}/index.html  ({} bytes)".format(p["slug"], n))

    n = write("answers/index.html", hub_page())
    total += n
    print("wrote answers/index.html  ({} bytes)".format(n))

    n = write("glossary/index.html", glossary_page())
    total += n
    print("wrote glossary/index.html  ({} bytes)".format(n))

    n = write("sitemap-answers.xml", sitemap_answers_xml())
    total += n
    print("wrote sitemap-answers.xml  ({} bytes)".format(n))

    print()
    print("Done. {} files, {} bytes total.".format(len(PAGES) + 3, total))
