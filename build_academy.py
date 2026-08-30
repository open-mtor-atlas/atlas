#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
build_academy.py -- generuje /academy/ (Academy / Learn MVP).

PROC TOHLE EXISTUJE
-------------------
Academy je ADITIVNI vrstva nad Atlasem, ne jeho predelavka. Spec zada skutecne
adresy (/academy/core/rheb), ne hash-routy -- a to je presne tvar, ktery uz
umi staticka vrstva (build_pages.py, generate.py). Takze Academy je ctvrty
staticky generator, ne devaty pohled v index.html:

  * index.html se nedotyka (krome jedne polozky v navigaci, viz deploy poznamka)
  * sablona, hlavicka, paticka, mobilni media queries a fonty se BEROU z
    build_pages.shell() -- zadny druhy design system
  * lekce ukladaji jen ID (sid studie, jmeno entity, id guided route);
    nazvy, roky, tiery a findings se resolvuji az tady, ze stejnych
    atlas_data/*.json, ktere pouziva zbytek webu. Zadna kopie vedecke databaze.

VSTUP   academy_data/lessons.json, academy_data/modules.json
        atlas_data/studies_baked.json, atlas_data/entities_baked.json
        pathway/model.json  (guided routes -- jen nazvy a existence id)
VYSTUP  academy/index.html
        academy/<module>/index.html
        academy/<module>/<lesson>/index.html
        sitemap-academy.xml
        academy_data/_sid_to_lesson.json   (reverzni index pro build_pages.py)

    py build_academy.py            # vygeneruje
    py build_academy.py --dry-run  # nic nezapise
    py build_academy.py --clean    # smaze drive vygenerovane academy/ stranky

POZOR NA PORADI: spousti se PRED build_pages.py, protoze build_pages.py cte
_sid_to_lesson.json a podle nej pridava na stranky studii blok "Learn the
biology". Pri uplne prvnim behu blok proste chybi -- to je bezpecne.

URL JSOU NEMENNE, stejne pravidlo jako v build_pages.py. Slug lekce je v
lessons.json, ne odvozeny z nazvu, prave proto, aby se nazev dal prepsat bez
zmeny adresy.
"""

import os
import sys
import json
import re

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

# build_pages.py je bezpecne importovatelny (ma `if __name__ == "__main__"`).
# Bereme z nej sablonu i vsechny sdilene konstanty, aby Academy nemohla
# vizualne odejit od zbytku statickych stranek.
import build_pages as BP
from build_pages import (SITE, GENERATED_MARKER, shell, breadcrumb_ld,
                         slugify, e, tier_bits, TYPE_DIR, DATASET_REF, write)

DRY = "--dry-run" in sys.argv
CLEAN = "--clean" in sys.argv
# build_pages.write() se ridi SVYM vlastnim BP.DRY, ktere se nastavilo pri
# importu z naseho argv -- pro --dry-run to vyjde stejne, pro jistotu ale
# srovname explicitne, at se to nerozejde, kdyby se flag jednou prejmenoval.
BP.DRY = DRY

ACADEMY_DIR = os.path.join(HERE, "academy")
ADATA = os.path.join(HERE, "academy_data")
DATA = os.path.join(HERE, "atlas_data")

# Uzky whitelist inline znacek povolenych v proze lekci. verify_academy.py
# kontroluje totez nezavisle; tady je to druha pojistka pred zapisem.
ALLOWED_INLINE = re.compile(
    r"</?(?:strong|em|code|sub|sup)>|<a href=\"[^\"<>]*\">|</a>")
TAG_RE = re.compile(r"<[^>]+>")


# ------------------------------------------------------------------ prose ---

def prose(s):
    """Propusti povolenou inline sadu, jinak zahlasi. Prose v lessons.json je
    rucne psana kuratorem, ne uzivatelsky vstup -- tohle neni bezpecnostni
    sanitizer, ale kontrola, ze se do dat nedostane nahodou blok/skript."""
    for m in TAG_RE.finditer(s):
        if not ALLOWED_INLINE.fullmatch(m.group(0)):
            raise SystemExit("build_academy: nepovolena znacka %r v proze:\n  %s"
                             % (m.group(0), s[:160]))
    return s


def paras(items, cls=None):
    c = ' class="%s"' % cls if cls else ""
    return "".join("<p%s>%s</p>" % (c, prose(x)) for x in items)


# ------------------------------------------------------------------- data ---

def load():
    lessons = json.load(open(os.path.join(ADATA, "lessons.json"), encoding="utf-8"))["lessons"]
    modules = json.load(open(os.path.join(ADATA, "modules.json"), encoding="utf-8"))
    studies = json.load(open(os.path.join(DATA, "studies_baked.json"), encoding="utf-8"))
    entities = json.load(open(os.path.join(DATA, "entities_baked.json"), encoding="utf-8"))

    by_sid = {s["sid"]: s for s in studies if s.get("sid")}

    # Stranku dostane jen entita s >= PAGE_THRESHOLD studiemi -- stejne
    # pravidlo jako v build_pages.py. Odkazovat na entitu bez stranky by
    # vyrobilo 404, coz je presne to, cemu se cely staticky layer vyhyba.
    ent_url = {}
    for x in entities:
        st = x.get("studies")
        if isinstance(st, str):
            try:
                st = json.loads(st.replace("'", '"'))
            except Exception:
                st = [t.strip(" '\"") for t in st.strip("[]").split(",") if t.strip()]
        if len(st or []) < BP.PAGE_THRESHOLD:
            continue
        d = TYPE_DIR.get(x["type"], "entity")
        ent_url[x["name"].lower()] = ("%s/%s/%s/" % (SITE, d, slugify(x["name"])), x["name"])

    routes = {}
    mp = os.path.join(HERE, "pathway", "model.json")
    if os.path.exists(mp):
        for r in json.load(open(mp, encoding="utf-8")).get("routes", []):
            routes[r["id"]] = r

    gaps = {}
    gp = os.path.join(DATA, "gaps_baked.json")
    if os.path.exists(gp):
        for g in json.load(open(gp, encoding="utf-8")):
            gaps[slugify(g["title"])] = g["title"]

    return lessons, modules, by_sid, ent_url, routes, gaps


# ---------------------------------------------------------------- figures ---
#
# Rucne kreslene inline SVG. Zadna knihovna, zadny dalsi request, zadna
# kreslena biologie (spec §7). Barvy jdou pres currentColor a CSS promenne
# stranky, takze diagram nikdy neodejde od zbytku typografie. viewBox +
# width:100% => skaluje se se ctecim sloupcem, na mobilu se nic neoreze.

def _svg(vb, inner, label):
    return ('<figure class="ac-fig"><svg viewBox="%s" role="img" '
            'aria-label="%s" class="ac-svg">%s</svg></figure>'
            % (vb, e(label), inner))


def fig_mtor_integrator():
    ins = ["Amino acids", "Energy state", "Growth factors", "Stress"]
    outs = ["Protein synthesis", "Lipid &amp; nucleotide synthesis", "Growth", "Autophagy (restrained)"]
    g = []
    for i, t in enumerate(ins):
        y = 26 + i * 42
        g.append('<rect class="ac-box" x="6" y="%d" width="148" height="30" rx="3"/>'
                 '<text class="ac-t" x="80" y="%d">%s</text>'
                 '<path class="ac-arrow" d="M158 %d H206" marker-end="url(#acArrow)"/>'
                 % (y, y + 19, t, y + 15))
    for i, t in enumerate(outs):
        y = 26 + i * 42
        g.append('<path class="ac-arrow" d="M334 %d H382" marker-end="url(#acArrow)"/>'
                 '<rect class="ac-box" x="386" y="%d" width="188" height="30" rx="3"/>'
                 '<text class="ac-t" x="480" y="%d">%s</text>' % (y + 15, y, y + 19, t))
    g.append('<rect class="ac-box ac-accent" x="210" y="72" width="120" height="72" rx="3"/>'
             '<text class="ac-t ac-lead" x="270" y="104">mTOR</text>'
             '<text class="ac-t ac-sub" x="270" y="124">in complexes</text>')
    return _svg("0 0 580 210", "".join(g),
                "Nutrients, energy state, growth factors and stress converge on mTOR, "
                "which shifts the balance between building programs and autophagy.")


def fig_two_complexes():
    def block(x, name, subs, subst, note):
        r = ['<rect class="ac-box ac-accent" x="%d" y="14" width="250" height="42" rx="3"/>'
             '<text class="ac-t ac-lead" x="%d" y="41">%s</text>' % (x, x + 125, name)]
        r.append('<text class="ac-t ac-sub" x="%d" y="78">%s</text>' % (x + 125, subs))
        r.append('<path class="ac-arrow" d="M%d 88 V116" marker-end="url(#acArrow)"/>' % (x + 125))
        r.append('<rect class="ac-box" x="%d" y="120" width="250" height="34" rx="3"/>'
                 '<text class="ac-t" x="%d" y="141">%s</text>' % (x, x + 125, subst))
        r.append('<text class="ac-t ac-sub" x="%d" y="176">%s</text>' % (x + 125, note))
        return "".join(r)
    g = block(6, "mTORC1", "mTOR + RAPTOR + mLST8", "S6K1 · 4E-BP1 · ULK1",
              "translation, autophagy restraint")
    g += block(300, "mTORC2", "mTOR + RICTOR + SIN1 + mLST8", "AKT (Ser473) · SGK · PKC",
               "survival, metabolism, cytoskeleton")
    g += ('<path class="ac-dash" d="M131 190 C131 206 425 206 425 190"/>'
          '<text class="ac-t ac-sub" x="278" y="207">shared subunits &amp; feedback between them</text>')
    return _svg("0 0 560 216", g,
                "mTORC1 and mTORC2 share the mTOR kinase but differ in partner subunits "
                "and substrates, and influence each other.")


def fig_rheb_axis():
    nodes = [("Growth factors", 6, 150), ("AKT", 176, 90), ("TSC1/TSC2", 296, 120),
             ("Rheb-GTP", 446, 120), ("mTORC1", 596, 110)]
    g = []
    for label, x, w in nodes:
        cls = "ac-box ac-accent" if label in ("Rheb-GTP", "mTORC1") else "ac-box"
        g.append('<rect class="%s" x="%d" y="30" width="%d" height="34" rx="3"/>'
                 '<text class="ac-t" x="%d" y="52">%s</text>' % (cls, x, w, x + w // 2, label))
    # aktivacni sipka, pak dve inhibice (kolmicka), pak aktivace
    g.append('<path class="ac-arrow" d="M160 47 H172" marker-end="url(#acArrow)"/>')
    g.append('<path class="ac-inh" d="M268 47 H290"/><path class="ac-inh" d="M290 38 V56"/>')
    g.append('<path class="ac-inh" d="M418 47 H440"/><path class="ac-inh" d="M440 38 V56"/>')
    g.append('<path class="ac-arrow" d="M568 47 H592" marker-end="url(#acArrow)"/>')
    g.append('<text class="ac-t ac-sub" x="279" y="24">inhibits</text>')
    g.append('<text class="ac-t ac-sub" x="429" y="24">inhibits</text>')
    g.append('<text class="ac-t ac-sub" x="353" y="86">AMPK and other stress inputs '
             'act on the same brake</text>')
    g.append('<path class="ac-arrow ac-thin" d="M353 76 V68" marker-end="url(#acArrow)"/>')
    return _svg("0 0 716 96", "".join(g),
                "Growth factors activate AKT, which inhibits the TSC complex, which inhibits "
                "Rheb-GTP, which activates mTORC1. Two inhibitory steps in series.")


def fig_rheb_spatial():
    g = [
        # mTORC1 waiting in the cytosol, then recruited down onto the membrane
        '<rect class="ac-box" x="228" y="10" width="150" height="30" rx="3"/>'
        '<text class="ac-t" x="303" y="30">mTORC1 (cytosol)</text>',
        '<path class="ac-arrow" d="M303 44 V78" marker-end="url(#acArrow)"/>',
        # the lysosome
        '<rect class="ac-organelle" x="20" y="82" width="520" height="86" rx="12"/>',
        '<text class="ac-t ac-sub" x="74" y="160">lysosome</text>',
        '<rect class="ac-box" x="44" y="104" width="164" height="32" rx="3"/>'
        '<text class="ac-t" x="126" y="125">Ragulator · Rag</text>',
        '<rect class="ac-box ac-accent" x="248" y="104" width="120" height="32" rx="3"/>'
        '<text class="ac-t" x="308" y="125">mTORC1</text>',
        '<rect class="ac-box ac-accent" x="408" y="104" width="112" height="32" rx="3"/>'
        '<text class="ac-t" x="464" y="125">Rheb-GTP</text>',
        # left arrow: amino acids -> where
        '<path class="ac-arrow" d="M212 120 H242" marker-end="url(#acArrow)"/>',
        '<text class="ac-t ac-sub" x="126" y="74">amino acids decide '
        '<tspan class="ac-em">where</tspan></text>',
        # right arrow: growth factors -> whether active
        '<path class="ac-arrow" d="M404 120 H376" marker-end="url(#acArrow)"/>',
        '<text class="ac-t ac-sub" x="464" y="74">growth factors decide '
        '<tspan class="ac-em">whether</tspan></text>',
        # TSC brought to the same membrane under stress
        '<rect class="ac-box" x="408" y="196" width="112" height="30" rx="3"/>'
        '<text class="ac-t" x="464" y="216">TSC complex</text>',
        '<path class="ac-dash" d="M464 192 V142"/>',
        '<text class="ac-t ac-sub" x="196" y="215">under stress the brake is recruited '
        'here too</text>',
    ]
    return _svg("0 0 560 236", "".join(g),
                "mTORC1 is recruited to the lysosome by the Rag GTPases in response to amino "
                "acids, where it meets Rheb; the TSC complex can also be recruited to the "
                "lysosome under stress.")


FIGURES = {
    "mtor-integrator": fig_mtor_integrator,
    "two-complexes": fig_two_complexes,
    "rheb-axis": fig_rheb_axis,
    "rheb-spatial": fig_rheb_spatial,
}

SVG_DEFS = ('<svg width="0" height="0" aria-hidden="true" focusable="false" '
            'style="position:absolute"><defs><marker id="acArrow" viewBox="0 0 10 10" '
            'refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">'
            '<path d="M0 0 L10 5 L0 10 z" fill="currentColor"/></marker></defs></svg>')


# -------------------------------------------------------------------- css ---

ACADEMY_CSS = """
/* ---- Academy (build_academy.py) -------------------------------------
   Appended to shell()'s stylesheet, so it may override anything above it.
   Scoped by document: only Academy pages carry this block, which is why
   widening .wrap here cannot affect /study/ or /answers/ pages. Tokens are
   the ones shell() already defines -- no new palette, no new type scale.
   Card radius stays 3px to match every other static page (spec §8 defers
   to the existing Atlas design system).                                */
.wrap{max-width:1060px}
nav.crumb{max-width:1060px}
.ac-eyebrow{font-family:'IBM Plex Mono',monospace;font-size:11px;letter-spacing:.1em;
  text-transform:uppercase;color:var(--teal);font-weight:600;margin:0 0 10px}
.ac-hero{max-width:780px;margin:0 0 34px}
.ac-hero h1{font-size:clamp(26px,3.4vw,34px);line-height:1.18;margin:0 0 12px}
.ac-hero .ac-lede{font-size:17px;line-height:1.62;color:var(--soft);margin:0 0 20px}
.ac-cta{display:inline-flex;align-items:center;min-height:44px;background:var(--ink);
  color:#fff;text-decoration:none;padding:11px 20px;border-radius:3px;font-size:15px;
  font-weight:600}
.ac-cta:hover{background:var(--teal)}
.ac-cta.ac-quiet{background:none;color:var(--ink);border:1px solid var(--line);font-weight:400}
.ac-cta.ac-quiet:hover{background:rgba(163,31,52,.06);color:var(--teal)}

/* entry cards + curriculum -------------------------------------------- */
.ac-cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:14px;
  margin:0 0 34px}
.ac-card{border:1px solid var(--line);border-radius:3px;padding:20px 22px;
  display:flex;flex-direction:column;gap:8px}
.ac-card h3{margin:0;font-size:16px}
.ac-card p{margin:0;font-size:14px;color:var(--soft);line-height:1.55;flex:1}
.ac-card .ac-go{font-family:'IBM Plex Mono',monospace;font-size:12px;font-weight:600;
  letter-spacing:.04em;text-decoration:none}
.ac-card.ac-soon{opacity:.62}
.ac-card.ac-soon .ac-go{color:var(--soft)}

.ac-list{list-style:none;padding:0;margin:0 0 8px;border-top:1px solid var(--line)}
.ac-list li{border-bottom:1px solid var(--line)}
.ac-list a,.ac-list .ac-row{display:flex;align-items:baseline;gap:12px;padding:13px 4px;
  text-decoration:none;color:var(--ink);min-height:44px}
.ac-list a:hover{background:rgba(163,31,52,.05)}
.ac-list .ac-n{font-family:'IBM Plex Mono',monospace;font-size:12px;color:var(--soft);
  width:22px;flex:none}
.ac-list .ac-state{font-family:'IBM Plex Mono',monospace;font-size:13px;width:16px;flex:none;
  color:var(--soft)}
.ac-list .ac-state[data-done="1"]{color:var(--teal)}
.ac-list .ac-ttl{flex:1;font-size:15px;font-weight:600}
.ac-list .ac-meta{font-family:'IBM Plex Mono',monospace;font-size:11px;color:var(--soft);
  letter-spacing:.03em;white-space:nowrap}
.ac-list li.ac-planned .ac-ttl{font-weight:400;color:var(--soft)}

/* "Your path" strip -- a map of the course, not a score. */
.ac-path{list-style:none;display:flex;gap:0;padding:0;margin:0 0 34px;overflow-x:auto;
  -webkit-overflow-scrolling:touch;scrollbar-width:none;border-top:1px solid var(--line);
  border-bottom:1px solid var(--line)}
.ac-path::-webkit-scrollbar{display:none}
.ac-path li{flex:0 0 auto;border-right:1px solid var(--line)}
.ac-path li:last-child{border-right:none}
.ac-path a,.ac-path .ac-row{display:flex;align-items:center;gap:7px;padding:11px 16px;
  min-height:44px;text-decoration:none;color:var(--ink);
  font-family:'IBM Plex Mono',monospace;font-size:11.5px;letter-spacing:.03em}
.ac-path a:hover{background:rgba(163,31,52,.05);color:var(--teal)}
.ac-path .ac-pathttl{font-family:'DM Sans',-apple-system,sans-serif;font-size:13px;
  letter-spacing:0;white-space:nowrap}
.ac-path li.ac-planned .ac-pathttl,.ac-path li.ac-planned .ac-row{color:var(--soft)}

/* lesson layout -------------------------------------------------------- */
.ac-lesson{display:grid;grid-template-columns:minmax(0,1fr) 230px;gap:44px;align-items:start}
.ac-main{min-width:0;max-width:760px}
.ac-rail{position:sticky;top:18px;font-size:13px}
.ac-rail h4{font-family:'IBM Plex Mono',monospace;font-size:10.5px;letter-spacing:.1em;
  text-transform:uppercase;color:var(--soft);margin:0 0 9px;font-weight:600}
.ac-rail ol{list-style:none;padding:0;margin:0 0 24px;border-left:1px solid var(--line)}
.ac-rail ol li{margin:0}
.ac-rail ol a{display:block;padding:5px 0 5px 12px;color:var(--soft);text-decoration:none;
  line-height:1.4;border-left:2px solid transparent;margin-left:-1px}
.ac-rail ol a:hover{color:var(--teal);border-left-color:var(--teal)}
.ac-ctx{border-top:1px solid var(--line);padding-top:14px}
.ac-chain{list-style:none;padding:0;margin:0}
.ac-chain li{padding:4px 0 4px 12px;border-left:1px solid var(--line);color:var(--soft);
  line-height:1.4}
.ac-chain li.ac-here{border-left:2px solid var(--teal);color:var(--ink);font-weight:600}
.ac-chain a{color:inherit;text-decoration:none}
.ac-chain a:hover{color:var(--teal)}
.ac-conceptlbl{font-family:'IBM Plex Mono',monospace;font-size:10.5px;letter-spacing:.09em;
  text-transform:uppercase;color:var(--soft);margin:18px 0 3px}
.ac-concepts{font-size:14px;color:var(--soft);margin:0}

.ac-q{font-family:'Cormorant Garamond',Georgia,serif;font-size:clamp(21px,2.6vw,26px);
  line-height:1.3;color:var(--teal);margin:0 0 22px;font-weight:500}
.ac-section{margin:0 0 34px}
.ac-section>h2{font-size:17px;margin:34px 0 12px}
.ac-note{border-left:3px solid var(--line);padding:2px 0 2px 16px;color:var(--soft);
  font-size:15px}
.ac-idea p{font-size:17px;line-height:1.62}

/* figures -------------------------------------------------------------- */
.ac-fig{margin:18px 0 22px;padding:0}
.ac-svg{width:100%;height:auto;color:var(--ink);overflow:visible}
.ac-box{fill:none;stroke:var(--line-strong,rgba(0,0,0,.34));stroke-width:1}
.ac-box.ac-accent{stroke:var(--teal);stroke-width:1.5}
.ac-organelle{fill:rgba(163,31,52,.05);stroke:var(--line);stroke-width:1}
.ac-t{font-family:'DM Sans',-apple-system,sans-serif;font-size:12px;fill:var(--ink);
  text-anchor:middle}
.ac-t.ac-lead{font-size:17px;font-weight:700}
.ac-t.ac-sub{font-size:11px;fill:var(--soft)}
.ac-t .ac-em{font-style:italic;fill:var(--teal)}
.ac-arrow{stroke:var(--ink);stroke-width:1.2;fill:none;color:var(--ink)}
.ac-arrow.ac-thin{stroke-width:1}
.ac-inh{stroke:var(--teal);stroke-width:1.6;fill:none}
.ac-dash{stroke:var(--soft);stroke-width:1;stroke-dasharray:3 3;fill:none}

/* evidence ------------------------------------------------------------- */
.ac-ev{display:grid;gap:10px;margin:6px 0 10px}
.ac-evcard{border:1px solid var(--line);border-radius:3px;padding:13px 15px}
.ac-evcard .ac-evhead{display:flex;align-items:baseline;gap:9px;flex-wrap:wrap;margin-bottom:5px}
.ac-evcard .ac-evyear{font-family:'IBM Plex Mono',monospace;font-size:12px;color:var(--soft)}
.ac-evcard .ac-evtitle{font-size:15px;font-weight:600;text-decoration:none;color:var(--ink)}
.ac-evcard .ac-evtitle:hover{color:var(--teal)}
.ac-evcard .ac-evfind{font-size:14px;color:var(--soft);line-height:1.55;margin:0}
.ac-evcard .ac-evlink{font-family:'IBM Plex Mono',monospace;font-size:11.5px;
  display:inline-flex;align-items:center;min-height:32px}

/* think ---------------------------------------------------------------- */
.ac-think{border:1px solid var(--line);border-left:3px solid var(--teal);border-radius:3px;
  padding:16px 18px;margin:0 0 12px}
.ac-think .ac-prompt{font-size:16px;line-height:1.55;margin:0 0 8px}
.ac-think .ac-hint{font-size:13.5px;color:var(--soft);margin:0 0 10px}
.ac-think details>summary{cursor:pointer;font-family:'IBM Plex Mono',monospace;font-size:12px;
  font-weight:600;letter-spacing:.05em;text-transform:uppercase;color:var(--teal);
  list-style:none;display:inline-flex;align-items:center;min-height:44px}
.ac-think details>summary::-webkit-details-marker{display:none}
.ac-think details>summary::after{content:" \\2192"}
.ac-think details[open]>summary::after{content:""}
.ac-think .ac-reveal{font-size:14.5px;line-height:1.6;margin:2px 0 0}

.ac-deeper{display:flex;flex-wrap:wrap;gap:6px;margin:4px 0 14px}
.ac-deeper a{display:inline-flex;align-items:center;min-height:36px;font-size:13.5px;
  border:1px solid var(--line);border-radius:3px;padding:5px 11px;text-decoration:none}
.ac-deeper a:hover{border-color:var(--teal)}
.ac-routes{list-style:none;padding:0;margin:6px 0 16px}
.ac-routes li{margin:0 0 9px}
.ac-routes a{font-size:15px;font-weight:600;text-decoration:none}
.ac-routes span{display:block;font-size:13.5px;color:var(--soft);line-height:1.5}
.ac-nextbar{display:flex;justify-content:space-between;gap:14px;flex-wrap:wrap;
  border-top:1px solid var(--line);padding-top:18px;margin-top:34px}

@media (max-width:1000px){
  /* Spec §10: the right rail collapses into horizontal navigation above the
     text (order:-1 on a grid item), and the page must not overflow sideways --
     so the strip itself scrolls, the page does not. The "where this fits"
     block is dropped here rather than stacked: the same information is carried
     by the prev/next bar and the curriculum link, so nothing lives only in the
     rail. No JS, no <details> quirks. */
  .ac-lesson{grid-template-columns:minmax(0,1fr);gap:0}
  .ac-main{max-width:none}
  .ac-rail{position:static;order:-1;margin:0 0 26px;padding:0 0 4px;
    border-bottom:1px solid var(--line)}
  .ac-rail h4{margin:0 0 6px}
  .ac-rail ol{display:flex;gap:0;margin:0;border-left:none;overflow-x:auto;
    -webkit-overflow-scrolling:touch;scrollbar-width:none}
  .ac-rail ol::-webkit-scrollbar{display:none}
  .ac-rail ol li{flex:0 0 auto}
  .ac-rail ol a{white-space:nowrap;padding:8px 14px 8px 0;border-left:none;margin-left:0;
    min-height:40px;display:flex;align-items:center}
  .ac-ctx{display:none}
}
@media (max-width:560px){
  .ac-hero .ac-lede{font-size:16px}
  .ac-list a,.ac-list .ac-row{flex-wrap:wrap;gap:8px}
  .ac-list .ac-meta{width:100%}
}
"""

PROGRESS_JS = """
<script>
/* Academy progress. One localStorage key, same defensive pattern as the SPA's
   atlas-theme / atlas-level switches: every read and write is wrapped, and the
   page renders correctly when storage is unavailable or empty. No accounts, no
   XP, no streaks -- a tick next to what you have read (spec §2, §18). */
(function(){
  var KEY='atlas-academy-progress';
  function read(){try{return JSON.parse(localStorage.getItem(KEY)||'{}')||{};}catch(e){return {};}}
  function save(o){try{localStorage.setItem(KEY,JSON.stringify(o));}catch(e){}}
  var p=read();
  document.querySelectorAll('[data-ac-lesson]').forEach(function(el){
    if(p[el.getAttribute('data-ac-lesson')]==='done'){
      var g=el.querySelector('.ac-state'); if(g){g.textContent='\\u2713';g.setAttribute('data-done','1');}
    }
  });
  var here=document.body.getAttribute('data-ac-current');
  var btn=document.getElementById('acDone');
  if(here&&btn){
    function paint(){
      var d=read()[here]==='done';
      btn.textContent=d?'\\u2713 Marked as read':'Mark as read';
      btn.setAttribute('aria-pressed',String(d));
    }
    btn.addEventListener('click',function(){
      var o=read(); if(o[here]==='done'){delete o[here];}else{o[here]='done';} save(o); paint();
    });
    paint();
  }
})();
</script>
"""


# ------------------------------------------------------------ components ---

def evidence_cards(sids, by_sid):
    out = []
    for sid in sids:
        s = by_sid.get(sid)
        if not s:
            raise SystemExit("build_academy: lekce odkazuje na neexistujici SID %r" % sid)
        code, label, colour = tier_bits(s.get("tier"))
        finding = (s.get("finding") or "").strip()
        # Jedna veta, ne cely finding -- karta ma pozvat ke kliknuti, ne
        # nahradit stranku studie (spec §11: "Do not duplicate study records").
        first = re.split(r"(?<=[.!?])\s+", finding)[0] if finding else ""
        if len(first) > 240:
            first = first[:237].rstrip() + "…"
        out.append(
            '<div class="ac-evcard"><div class="ac-evhead">'
            '<span class="tier" style="background:%s">%s</span>'
            '<a class="ac-evtitle" href="%s/study/%s/">%s</a>'
            '<span class="ac-evyear">%s</span></div>'
            '<p class="ac-evfind">%s</p>'
            '<a class="ac-evlink" href="%s/study/%s/">Study page &rarr;</a></div>'
            % (colour, e(code), SITE, e(sid), e(s.get("title") or sid),
               e(s.get("year") or ""), e(first), SITE, e(sid)))
    return '<div class="ac-ev">%s</div>' % "".join(out)


def deeper_links(les, ent_url, gaps):
    """Chipy "Go deeper". VZDY jen na entity, ktere maji vlastni stranku --
    jmeno bez stranky se tise preskoci a nahlasi do konzole, nikdy nevznikne
    mrtvy odkaz."""
    chips, missing = [], []
    for key in ("proteins", "pathways", "processes", "organelles", "nutrients"):
        for name in les.get(key) or []:
            hit = ent_url.get(name.lower())
            if not hit:
                missing.append(name)
                continue
            chips.append('<a href="%s">%s</a>' % (hit[0], e(hit[1])))
    for slug in les.get("openQuestions") or []:
        if slug not in gaps:
            raise SystemExit("build_academy: neznamy open-question slug %r" % slug)
        chips.append('<a href="%s/question/%s/">Open question: %s</a>'
                     % (SITE, slug, e(gaps[slug])))
    return "".join(chips), missing


def route_links(les, routes):
    out = []
    for r in les.get("guidedRoutes") or []:
        rid = r["id"]
        if rid not in routes:
            raise SystemExit("build_academy: neznama guided route %r" % rid)
        out.append('<li><a href="%s/#view=map&amp;pw=guided&amp;route=%s">%s</a>'
                   '<span>%s</span></li>'
                   % (SITE, e(rid), e(routes[rid]["name"]), prose(r.get("why") or "")))
    return '<ul class="ac-routes">%s</ul>' % "".join(out) if out else ""


def chain_rail(module, lessons_by_slug, current):
    """Kompaktni kontextova cesta modulem -- spec §11 "compact contextual
    pathway, highlight current concept". Zamerne NE obri graf."""
    items = []
    for row in module["lessons"]:
        slug = row["lesson"]
        title = lessons_by_slug[slug]["title"] if slug in lessons_by_slug else row.get("title", slug)
        here = ' class="ac-here"' if slug == current else ""
        if row["status"] == "published":
            body = '<a href="%s/academy/%s/%s/">%s</a>' % (SITE, module["slug"], slug, e(title))
        else:
            body = e(title)
        items.append("<li%s>%s&nbsp;%s</li>" % (here, row["n"], body))
    return '<ul class="ac-chain">%s</ul>' % "".join(items)


# ----------------------------------------------------------------- pages ---

def lesson_page(les, module, lessons_by_slug, by_sid, ent_url, routes, gaps):
    slug = les["slug"]
    url = "%s/academy/%s/%s/" % (SITE, module["slug"], slug)
    title = les["title"]
    desc = ("%s %s" % (les["question"], TAG_RE.sub("", les["coreIdea"][0])))[:300]

    # --- section anchors for the rail
    secs = [("question", "The question"), ("idea", "The core idea")]
    for i, s in enumerate(les["sections"]):
        secs.append(("s%d" % i, s["heading"]))
    secs += [("evidence", "What does the evidence say?"), ("think", "Think"),
             ("deeper", "Go deeper")]

    body = [SVG_DEFS, '<div class="ac-lesson"><article class="ac-main">']
    body.append('<p class="ac-eyebrow">%s &middot; Lesson %s &middot; %s &middot; %d min</p>'
                % (e(module["title"]), e(les["id"][1:]), e(les["level"]), les["estimatedTime"]))
    body.append("<h1>%s</h1>" % e(title))
    body.append('<p class="meta">%s</p>' % e(les["subtitle"]))
    body.append('<h2 id="question" class="ac-vh">The question</h2>'
                '<p class="ac-q">%s</p>' % e(les["question"]))

    body.append('<section class="ac-section ac-idea"><h2 id="idea">The core idea</h2>%s</section>'
                % paras(les["coreIdea"]))

    for i, s in enumerate(les["sections"]):
        cls = "ac-section" + (" ac-cautionsec" if s["kind"] == "caution" else "")
        inner = ""
        if s.get("figure"):
            if s["figure"] not in FIGURES:
                raise SystemExit("build_academy: neznamy figure %r" % s["figure"])
            inner += FIGURES[s["figure"]]()
        inner += paras(s["body"], "ac-note" if s["kind"] == "caution" else None)
        body.append('<section class="%s"><h2 id="s%d">%s</h2>%s</section>'
                    % (cls, i, e(s["heading"]), inner))

    body.append('<section class="ac-section"><h2 id="evidence">What does the evidence say?</h2>')
    body.append("<p>These are Atlas studies, with the Atlas's own evidence tier. "
                "Each card links to the full record — nothing here restates it.</p>")
    body.append(evidence_cards(les["studies"], by_sid))
    if les.get("uncertainty"):
        body.append('<p class="ac-note">%s</p>' % prose(les["uncertainty"]))
    body.append("</section>")

    body.append('<section class="ac-section"><h2 id="think">Think</h2>')
    for j, t in enumerate(les["thinkQuestions"]):
        body.append('<div class="ac-think"><p class="ac-prompt">%s</p>' % prose(t["prompt"]))
        if t.get("hint"):
            body.append('<p class="ac-hint">%s</p>' % prose(t["hint"]))
        body.append('<details><summary>Think first, then reveal</summary>'
                    '<p class="ac-reveal">%s</p></details></div>' % prose(t["reveal"]))
    body.append("</section>")

    chips, missing = deeper_links(les, ent_url, gaps)
    body.append('<section class="ac-section"><h2 id="deeper">Go deeper</h2>')
    if chips:
        body.append('<div class="ac-deeper">%s</div>' % chips)
    rl = route_links(les, routes)
    if rl:
        body.append("<p><strong>Follow a guided route through the mechanism:</strong></p>" + rl)
    if les.get("concepts"):
        body.append('<p class="ac-conceptlbl">Concepts introduced in this lesson</p>'
                    '<p class="ac-concepts">%s</p>'
                    % " &middot; ".join(e(c) for c in les["concepts"]))
    body.append("</section>")

    nxt, prv = les.get("nextLesson"), les.get("previousLesson")
    nav = []
    if prv:
        nav.append('<a class="ac-cta ac-quiet" href="%s/academy/%s/%s/">&larr; %s</a>'
                   % (SITE, module["slug"], prv, e(lessons_by_slug[prv]["title"])))
    else:
        nav.append('<a class="ac-cta ac-quiet" href="%s/academy/%s/">&larr; Curriculum</a>'
                   % (SITE, module["slug"]))
    nav.append('<button type="button" class="ac-cta ac-quiet" id="acDone">Mark as read</button>')
    if nxt:
        nav.append('<a class="ac-cta" href="%s/academy/%s/%s/">Next: %s &rarr;</a>'
                   % (SITE, module["slug"], nxt, e(lessons_by_slug[nxt]["title"])))
    else:
        nav.append('<a class="ac-cta" href="%s/academy/%s/">Back to the curriculum &rarr;</a>'
                   % (SITE, module["slug"]))
    body.append('<div class="ac-nextbar">%s</div>' % "".join(nav))
    body.append("</article>")

    # Right rail. Two blocks with deliberately different responsive fates:
    #   .ac-toc  -- section anchors; becomes a horizontal strip on narrow screens
    #   .ac-ctx  -- "where this fits" in the module; hidden on narrow screens,
    #               where the same information is carried by the prev/next bar
    #               and the curriculum link. Nothing is only in the rail.
    rail = ['<nav class="ac-toc" aria-label="In this lesson"><h4>In this lesson</h4><ol>']
    for aid, label in secs:
        rail.append('<li><a href="#%s">%s</a></li>' % (aid, e(label)))
    rail.append("</ol></nav>")
    rail.append('<div class="ac-ctx"><h4>Where this fits</h4>%s</div>'
                % chain_rail(module, lessons_by_slug, slug))
    body.append('<aside class="ac-rail">%s</aside>' % "".join(rail))
    body.append("</div>")

    crumb = ('<a href="%s/">Oliver\'s mTOR Atlas</a> › <a href="%s/academy/">Academy</a> › '
             '<a href="%s/academy/%s/">%s</a> › %s'
             % (SITE, SITE, SITE, module["slug"], e(module["title"]), e(title)))

    ld = {
        "@context": "https://schema.org", "@type": "LearningResource",
        "name": title, "headline": title, "url": url, "inLanguage": "en",
        "educationalLevel": les["level"],
        "learningResourceType": "lesson",
        "timeRequired": "PT%dM" % les["estimatedTime"],
        "teaches": les.get("concepts") or [],
        "isPartOf": {"@type": "Course", "name": "%s — mTOR Academy" % module["title"],
                     "url": "%s/academy/%s/" % (SITE, module["slug"])},
        "about": dict(DATASET_REF),
        "author": {"@type": "Person", "name": "Oliver Barton"},
        "license": "https://creativecommons.org/licenses/by/4.0/",
    }
    faq = {"@context": "https://schema.org", "@type": "FAQPage",
           "mainEntity": [{"@type": "Question", "name": TAG_RE.sub("", t["prompt"]),
                           "acceptedAnswer": {"@type": "Answer",
                                              "text": TAG_RE.sub("", t["reveal"])}}
                          for t in les["thinkQuestions"]]}
    bc = breadcrumb_ld([("Oliver's mTOR Atlas", SITE + "/"),
                        ("Academy", SITE + "/academy/"),
                        (module["title"], "%s/academy/%s/" % (SITE, module["slug"])),
                        (title, None)])

    page = shell("%s | mTOR Academy | Oliver's mTOR Atlas" % title, desc, url,
                 [ld, faq, bc], "".join(body), crumb, active_tab="learn",
                 extra_css=ACADEMY_CSS + "\n.ac-vh{position:absolute;width:1px;height:1px;"
                                         "overflow:hidden;clip:rect(0,0,0,0);white-space:nowrap;"
                                         "border:0;padding:0;margin:-1px}",
                 extra_body=PROGRESS_JS)
    page = page.replace("<body>", '<body data-ac-current="%s">' % e(slug), 1)
    return url, page, missing


def curriculum_page(module, lessons_by_slug):
    url = "%s/academy/%s/" % (SITE, module["slug"])
    rows = []
    for row in module["lessons"]:
        slug = row["lesson"]
        pub = row["status"] == "published"
        title = lessons_by_slug[slug]["title"] if pub else row.get("title", slug)
        meta = "%s · %d min" % (row["level"], row["minutes"])
        if pub:
            rows.append('<li data-ac-lesson="%s"><a href="%s/academy/%s/%s/">'
                        '<span class="ac-state">○</span><span class="ac-n">%s</span>'
                        '<span class="ac-ttl">%s</span><span class="ac-meta">%s</span></a></li>'
                        % (e(slug), SITE, module["slug"], e(slug), row["n"], e(title), e(meta)))
        else:
            rows.append('<li class="ac-planned"><span class="ac-row">'
                        '<span class="ac-state">·</span><span class="ac-n">%s</span>'
                        '<span class="ac-ttl">%s</span>'
                        '<span class="ac-meta">%s · in preparation</span></span></li>'
                        % (row["n"], e(title), e(meta)))
    body = ['<div class="ac-hero"><p class="ac-eyebrow">mTOR Academy</p>'
            '<h1>%s</h1><p class="ac-lede">%s</p></div>' % (e(module["title"]),
                                                            e(module["description"]))]
    body.append('<ul class="ac-list">%s</ul>' % "".join(rows))
    body.append('<p class="ac-note">Lessons marked <em>in preparation</em> are listed so the '
                'shape of the course is visible. They are not written yet, and this page will '
                'not pretend otherwise.</p>')
    body.append('<p><a class="ac-cta ac-quiet" href="%s/browse/">Explore the Atlas &rarr;</a></p>'
                % SITE)

    published = [r for r in module["lessons"] if r["status"] == "published"]
    ld = {"@context": "https://schema.org", "@type": "Course",
          "name": "%s — mTOR Academy" % module["title"], "url": url,
          "description": module["description"], "inLanguage": "en",
          "provider": {"@type": "Organization", "name": "Oliver's mTOR Atlas",
                       "url": SITE + "/"},
          "isAccessibleForFree": True,
          "hasCourseInstance": [{
              "@type": "CourseInstance", "courseMode": "online",
              "name": lessons_by_slug[r["lesson"]]["title"],
              "url": "%s/academy/%s/%s/" % (SITE, module["slug"], r["lesson"])}
              for r in published]}
    bc = breadcrumb_ld([("Oliver's mTOR Atlas", SITE + "/"),
                        ("Academy", SITE + "/academy/"),
                        (module["title"], None)])
    crumb = ('<a href="%s/">Oliver\'s mTOR Atlas</a> › <a href="%s/academy/">Academy</a> › %s'
             % (SITE, SITE, e(module["title"])))
    return url, shell("%s | mTOR Academy | Oliver's mTOR Atlas" % module["title"],
                      module["description"][:300], url, [ld, bc], "".join(body), crumb,
                      active_tab="learn", extra_css=ACADEMY_CSS, extra_body=PROGRESS_JS)


def academy_home(modules, lessons_by_slug):
    url = SITE + "/academy/"
    mod = modules["modules"][0]
    first = mod["lessons"][0]["lesson"]
    published = [r for r in mod["lessons"] if r["status"] == "published"]

    body = ['<div class="ac-hero"><p class="ac-eyebrow">mTOR Academy</p>'
            '<h1>From understanding mTOR to thinking like a researcher.</h1>'
            '<p class="ac-lede">Learn the mechanisms. Explore the evidence. Follow the '
            'questions that drive mTOR research.</p>'
            '<a class="ac-cta" href="%s/academy/%s/%s/">Start learning &rarr;</a></div>'
            % (SITE, mod["slug"], first)]

    # "Your path" -- the spec's §9 progress strip. It is a map of the course,
    # not a score: numbers, titles, and a tick for what this browser has marked
    # as read. Nothing is locked, nothing is counted.
    steps = []
    for row in mod["lessons"]:
        pub = row["status"] == "published"
        ttl = lessons_by_slug[row["lesson"]]["title"] if pub else row.get("title", row["lesson"])
        inner = ('<a href="%s/academy/%s/%s/"><span class="ac-state">○</span>%s'
                 '<span class="ac-pathttl">%s</span></a>'
                 % (SITE, mod["slug"], e(row["lesson"]), row["n"], e(ttl))) if pub else (
            '<span class="ac-row"><span class="ac-state">·</span>%s'
            '<span class="ac-pathttl">%s</span></span>' % (row["n"], e(ttl)))
        steps.append('<li%s data-ac-lesson="%s">%s</li>'
                     % ("" if pub else ' class="ac-planned"', e(row["lesson"]), inner))
    body.append('<h2>Your path</h2><ol class="ac-path">%s</ol>' % "".join(steps))

    body.append('<h2>Start here</h2><div class="ac-cards">')
    body.append('<div class="ac-card"><h3>Learn</h3><p>Build your understanding one '
                'mechanism at a time, from what mTOR integrates to why the field still '
                'argues about it.</p>'
                '<a class="ac-go" href="%s/academy/%s/">Start &rarr;</a></div>'
                % (SITE, mod["slug"]))
    body.append('<div class="ac-card"><h3>Guided Routes</h3><p>Follow one question all the '
                'way through the pathway map, step by step, in the interactive Atlas.</p>'
                '<a class="ac-go" href="%s/#view=map&amp;pw=guided">Explore &rarr;</a></div>'
                % SITE)
    for cs in modules.get("comingSoon", []):
        body.append('<div class="ac-card ac-soon"><h3>%s</h3><p>%s</p>'
                    '<span class="ac-go">Coming soon</span></div>'
                    % (e(cs["title"]), e(cs["blurb"])))
    body.append("</div>")

    body.append('<h2>%s</h2><p>%s</p>' % (e(mod["title"]), e(mod["subtitle"])))
    rows = []
    for row in published[:3]:
        les = lessons_by_slug[row["lesson"]]
        rows.append('<li data-ac-lesson="%s"><a href="%s/academy/%s/%s/">'
                    '<span class="ac-state">○</span><span class="ac-n">%s</span>'
                    '<span class="ac-ttl">%s</span><span class="ac-meta">%s · %d min</span>'
                    '</a></li>' % (e(row["lesson"]), SITE, mod["slug"], e(row["lesson"]),
                                   row["n"], e(les["title"]), e(row["level"]), row["minutes"]))
    body.append('<ul class="ac-list">%s</ul>' % "".join(rows))
    body.append('<p><a class="ac-cta ac-quiet" href="%s/academy/%s/">View all lessons &rarr;</a></p>'
                % (SITE, mod["slug"]))

    body.append('<h2>Explore the Atlas</h2>'
                '<p>Every lesson points back into the database it was written from.</p>'
                '<div class="ac-deeper">'
                '<a href="%s/browse/">Studies</a>'
                '<a href="%s/complex/mtorc1/">Pathways</a>'
                '<a href="%s/#view=authors">Authors</a>'
                '<a href="%s/gene/mtor/">Proteins</a>'
                '<a href="%s/#view=questions">Open questions</a></div>'
                % (SITE, SITE, SITE, SITE, SITE))

    ld = {"@context": "https://schema.org", "@type": "CollectionPage",
          "name": "mTOR Academy", "url": url, "inLanguage": "en",
          "description": "A short course in mTOR biology built on the Atlas's own "
                         "evidence-graded literature: mechanisms first, evidence attached, "
                         "open questions kept visible.",
          "isPartOf": dict(DATASET_REF),
          "license": "https://creativecommons.org/licenses/by/4.0/"}
    bc = breadcrumb_ld([("Oliver's mTOR Atlas", SITE + "/"), ("Academy", None)])
    crumb = '<a href="%s/">Oliver\'s mTOR Atlas</a> › Academy' % SITE
    return url, shell("mTOR Academy | Oliver's mTOR Atlas",
                      "Learn the mechanisms of mTOR biology from the Atlas's own "
                      "evidence-graded studies: what mTOR integrates, why there are two "
                      "complexes, and how Rheb and the TSC complex control mTORC1.",
                      url, [ld, bc], "".join(body), crumb, active_tab="learn",
                      extra_css=ACADEMY_CSS, extra_body=PROGRESS_JS)


# ------------------------------------------------------------------ main ---

def purge():
    n = 0
    if not os.path.isdir(ACADEMY_DIR):
        return 0
    for root, _, files in os.walk(ACADEMY_DIR):
        for fn in files:
            fp = os.path.join(root, fn)
            try:
                if GENERATED_MARKER in open(fp, encoding="utf-8").read(400):
                    os.remove(fp)
                    n += 1
            except Exception:
                pass
    for root, dirs, files in os.walk(ACADEMY_DIR, topdown=False):
        if not os.listdir(root):
            os.rmdir(root)
    return n


def main():
    lessons, modules, by_sid, ent_url, routes, gaps = load()
    lessons_by_slug = {l["slug"]: l for l in lessons}

    if CLEAN and not DRY:
        print("smazano drive vygenerovanych academy stranek:", purge())

    urls = []
    all_missing = []

    url, page = academy_home(modules, lessons_by_slug)
    write(os.path.join(ACADEMY_DIR, "index.html"), page)
    urls.append((url, "1.0"))

    sid_to_lesson = {}
    for mod in modules["modules"]:
        url, page = curriculum_page(mod, lessons_by_slug)
        write(os.path.join(ACADEMY_DIR, mod["slug"], "index.html"), page)
        urls.append((url, "0.9"))

        for row in mod["lessons"]:
            if row["status"] != "published":
                continue
            les = lessons_by_slug[row["lesson"]]
            url, page, missing = lesson_page(les, mod, lessons_by_slug, by_sid,
                                             ent_url, routes, gaps)
            write(os.path.join(ACADEMY_DIR, mod["slug"], les["slug"], "index.html"), page)
            urls.append((url, "0.8"))
            all_missing += [(les["slug"], m) for m in missing]
            for sid in les["studies"]:
                sid_to_lesson.setdefault(sid, []).append(
                    {"title": les["title"],
                     "url": "/academy/%s/%s/" % (mod["slug"], les["slug"])})

    write(os.path.join(ADATA, "_sid_to_lesson.json"),
          json.dumps(sid_to_lesson, ensure_ascii=False, indent=1, sort_keys=True) + "\n")

    sm = ['<?xml version="1.0" encoding="UTF-8"?>',
          '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    for u, prio in urls:
        sm.append("  <url><loc>%s</loc><changefreq>monthly</changefreq>"
                  "<priority>%s</priority></url>" % (u, prio))
    sm.append("</urlset>")
    write(os.path.join(HERE, "sitemap-academy.xml"), "\n".join(sm) + "\n")

    for slug, name in all_missing:
        print("  ! %s: entita %r nema vlastni stranku (<%d studii) -- chip preskocen"
              % (slug, name, BP.PAGE_THRESHOLD))
    print("""
%s
  stranek Academy : %d
  studii v lekcich: %d unikatnich SID
  zapsano         : %d   (beze zmeny: %d)

Kontrola:  py verify_academy.py
POZOR: build_pages.py se musi spustit PO tomhle skriptu, jinak stranky studii
nedostanou aktualni blok "Learn the biology".""" % (
        "DRY RUN — nic nezapsano" if DRY else "Hotovo.",
        len(urls), len(sid_to_lesson), BP.STATS["written"], BP.STATS["unchanged"]))


if __name__ == "__main__":
    main()
