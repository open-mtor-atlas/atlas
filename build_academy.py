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


def levelled(full, beginner, cls=None):
    """Dve verze teze prozy. Prepina je CSS na <html data-level>, ne JS:
    `lv-hide-beginner` schova plnou verzi jen na urovni beginner (student
    i research ji vidi beze zmeny), `lv-beginner` ukaze kratkou verzi jen
    tam. Zadna treti kopie pro research -- ta by byla jen duplikat student
    verze, ktera by se pak musela udrzovat dvakrat.

    Bez beginner varianty se nic neobalu je: stranka pak vypada na vsech
    urovnich stejne, coz je spravne chovani, ne chyba."""
    if not beginner:
        return paras(full, cls)
    return ('<div class="lv-hide-beginner">%s</div><div class="lv-beginner">%s</div>'
            % (paras(full, cls), paras(beginner, cls)))


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

    # Pathway model. Fáze 2 z nej nebere jen routes, ale i uzly a interakce:
    # interaktivni model v lekci se KRESLI z nich, takze vyukovy diagram nemuze
    # odejit od vedeckeho modelu. Projektove pravidlo "biologie drahy zije jen
    # v pathway/model.json" tim plati i pro Academy.
    routes = {}
    pw = {"nodes": {}, "edges": {}, "pairs": {}}
    mp = os.path.join(HERE, "pathway", "model.json")
    if os.path.exists(mp):
        doc = json.load(open(mp, encoding="utf-8"))
        for r in doc.get("routes", []):
            routes[r["id"]] = r
        for n in doc.get("nodes", []):
            pw["nodes"][n["id"]] = n
        for it in doc.get("interactions", []):
            pw["edges"][it["id"]] = it
            pw["pairs"].setdefault((it["source"], it["target"]), it)

    # Research Challenges. Volitelny soubor -- kdyz neexistuje, Academy se
    # vygeneruje presne jako pred timhle krokem a homepage nechá kartu jako
    # "coming soon". Zadny dalsi CMS, stejny vzorec jako lessons.json.
    challenges = []
    cp = os.path.join(ADATA, "challenges.json")
    if os.path.exists(cp):
        challenges = json.load(open(cp, encoding="utf-8"))["challenges"]

    gaps = {}
    gp = os.path.join(DATA, "gaps_baked.json")
    if os.path.exists(gp):
        for g in json.load(open(gp, encoding="utf-8")):
            gaps[slugify(g["title"])] = g["title"]

    return lessons, modules, by_sid, ent_url, routes, gaps, pw, challenges


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


def fig_tsc_gap():
    """Lekce 04. Jadro je jednoduche: TSC neni prepinac, ale GAP -- urcuje,
    jak dlouho Rheb zustane v GTP stavu. Proto se kresli cyklus, ne sipka."""
    g = []
    ins = ["AKT (growth factors)", "ERK / RSK (mitogens)", "AMPK (low energy)",
           "Hypoxia, DNA damage"]
    for i, t in enumerate(ins):
        y = 14 + i * 34
        g.append('<rect class="ac-box" x="4" y="%d" width="176" height="26" rx="3"/>'
                 '<text class="ac-t" x="92" y="%d">%s</text>'
                 '<path class="ac-arrow ac-thin" d="M184 %d H226" marker-end="url(#acArrow)"/>'
                 % (y, y + 17, t, y + 13))
    g.append('<rect class="ac-box ac-accent" x="230" y="44" width="152" height="60" rx="3"/>'
             '<text class="ac-t ac-lead" x="306" y="72">TSC complex</text>'
             '<text class="ac-t ac-sub" x="306" y="91">TSC1 &middot; TSC2 &middot; TBC1D7</text>')
    # TSC -> GAP aktivita na cyklu
    g.append('<path class="ac-arrow" d="M386 74 H444" marker-end="url(#acArrow)"/>')
    g.append('<text class="ac-t ac-sub" x="415" y="66">GAP</text>')
    # cyklus Rheb-GTP <-> Rheb-GDP
    g.append('<rect class="ac-box ac-accent" x="448" y="20" width="132" height="32" rx="3"/>'
             '<text class="ac-t" x="514" y="41">Rheb-GTP (on)</text>')
    g.append('<rect class="ac-box" x="448" y="98" width="132" height="32" rx="3"/>'
             '<text class="ac-t" x="514" y="119">Rheb-GDP (off)</text>')
    g.append('<path class="ac-arrow" d="M472 56 V94" marker-end="url(#acArrow)"/>')
    g.append('<path class="ac-arrow ac-thin" d="M556 94 V56" marker-end="url(#acArrow)"/>')
    g.append('<text class="ac-t ac-sub" x="588" y="79">reload</text>')
    g.append('<path class="ac-arrow" d="M584 36 H628" marker-end="url(#acArrow)"/>')
    g.append('<rect class="ac-box ac-accent" x="632" y="20" width="98" height="32" rx="3"/>'
             '<text class="ac-t" x="681" y="41">mTORC1</text>')
    g.append('<text class="ac-t ac-sub" x="365" y="164">the complex acts as a '
             '<tspan class="ac-em">GAP</tspan>: it speeds up the hydrolysis Rheb already '
             'performs, so it sets a rate rather than flipping a switch</text>')
    return _svg("0 0 740 176", "".join(g),
                "Growth-factor, mitogen, energy and stress inputs converge on the TSC "
                "complex, which acts as a GAP that pushes Rheb from its GTP-bound on-state "
                "to its GDP-bound off-state; only Rheb-GTP activates mTORC1.")

def fig_lysosome_hub():
    """Lekce 05. Membrana jako platforma: kdo na ni sedi, kdo se na ni tahne
    a kam odchazi signal ven (TFEB do jadra)."""
    g = ['<rect class="ac-box ac-accent" x="196" y="10" width="164" height="32" rx="3"/>'
         '<text class="ac-t" x="278" y="31">mTORC1 (cytosol)</text>',
         '<path class="ac-arrow" d="M278 46 V96" marker-end="url(#acArrow)"/>',
         '<rect class="ac-organelle" x="14" y="100" width="592" height="76" rx="14"/>',
         '<text class="ac-t ac-sub" x="60" y="168">lysosome</text>']
    parts = [("v-ATPase", 26, 96), ("Ragulator", 130, 96), ("Rag A/B &middot; C/D", 234, 112),
             ("SLC38A9", 356, 96), ("Rheb", 462, 88)]
    for label, x, w in parts:
        cls = "ac-box ac-accent" if label == "Rheb" else "ac-box"
        g.append('<rect class="%s" x="%d" y="112" width="%d" height="30" rx="3"/>'
                 '<text class="ac-t" x="%d" y="132">%s</text>' % (cls, x, w, x + w // 2, label))
    g.append('<text class="ac-t ac-sub" x="130" y="74">the signal starts in the lumen</text>')
    g.append('<text class="ac-t ac-sub" x="452" y="74">amino acids decide '
             '<tspan class="ac-em">where</tspan></text>')
    # TFEB vetev -- vlastni box pod membranou, sipka ven do jadra
    g.append('<rect class="ac-box" x="234" y="196" width="112" height="30" rx="3"/>'
             '<text class="ac-t" x="290" y="216">TFEB</text>')
    g.append('<path class="ac-inh" d="M290 148 V190"/><path class="ac-inh" d="M278 190 H302"/>')
    g.append('<path class="ac-arrow" d="M350 211 H430" marker-end="url(#acArrow)"/>')
    g.append('<rect class="ac-box" x="434" y="196" width="152" height="30" rx="3"/>'
             '<text class="ac-t" x="510" y="216">nucleus</text>')
    g.append('<text class="ac-t ac-sub" x="392" y="190">when mTORC1 is off</text>')
    g.append('<text class="ac-t ac-sub" x="300" y="248">docking is not activation: being here '
             'is what lets Rheb switch mTORC1 on</text>')
    return _svg("0 0 620 258", "".join(g),
                "The lysosomal surface carries the v-ATPase, Ragulator, the Rag GTPases and "
                "SLC38A9; amino acids recruit mTORC1 there, where Rheb can activate it, and "
                "TFEB is held out of the nucleus by mTORC1 until its activity falls.")

def fig_aa_sensors():
    """Lekce 06. Dvojity zapor je cela pointa: senzor VAZE aminokyselinu a tim
    PRESTANE inhibovat. Kresli se proto jako retez kolmicek, ne sipek."""
    rows = [("Leucine", "Sestrin2"), ("Arginine", "CASTOR1"),
            ("S-adenosyl-methionine", "SAMTOR")]
    g = []
    ys = []
    for i, (aa, sensor) in enumerate(rows):
        y = 14 + i * 46
        ys.append(y + 15)
        g.append('<rect class="ac-box" x="4" y="%d" width="150" height="30" rx="3"/>'
                 '<text class="ac-t" x="79" y="%d">%s</text>' % (y, y + 20, aa))
        g.append('<path class="ac-arrow ac-thin" d="M158 %d H186" marker-end="url(#acArrow)"/>'
                 % (y + 15))
        g.append('<rect class="ac-box" x="190" y="%d" width="118" height="30" rx="3"/>'
                 '<text class="ac-t" x="249" y="%d">%s</text>' % (y, y + 20, sensor))
        g.append('<path class="ac-inh" d="M312 %d H336"/>' % (y + 15))
    # spolecna sbernice do GATOR2 -- tri kolmicky konci na jedne care
    g.append('<path class="ac-inh" d="M336 %d V%d"/>' % (ys[0], ys[2]))
    g.append('<path class="ac-inh" d="M336 %d H354"/>' % ys[1])
    g.append('<rect class="ac-box" x="358" y="%d" width="112" height="46" rx="3"/>'
             '<text class="ac-t" x="414" y="%d">GATOR2</text>'
             '<text class="ac-t ac-sub" x="414" y="%d">bound = inhibited</text>'
             % (ys[1] - 23, ys[1] - 3, ys[1] + 13))
    g.append('<path class="ac-inh" d="M474 %d H498"/><path class="ac-inh" d="M498 %d V%d"/>'
             % (ys[1], ys[1] - 9, ys[1] + 9))
    g.append('<rect class="ac-box" x="506" y="%d" width="112" height="46" rx="3"/>'
             '<text class="ac-t" x="562" y="%d">GATOR1</text>'
             '<text class="ac-t ac-sub" x="562" y="%d">GAP for RagA/B</text>'
             % (ys[1] - 23, ys[1] - 3, ys[1] + 13))
    g.append('<path class="ac-inh" d="M622 %d H646"/><path class="ac-inh" d="M646 %d V%d"/>'
             % (ys[1], ys[1] - 9, ys[1] + 9))
    g.append('<rect class="ac-box ac-accent" x="654" y="%d" width="104" height="46" rx="3"/>'
             '<text class="ac-t" x="706" y="%d">Rag</text>'
             '<text class="ac-t ac-sub" x="706" y="%d">active state</text>'
             % (ys[1] - 23, ys[1] - 3, ys[1] + 13))
    g.append('<text class="ac-t ac-sub" x="380" y="172">count the blunt ends: an amino acid '
             'present means one more inhibition released, not one more push</text>')
    return _svg("0 0 768 184", "".join(g),
                "Leucine binds Sestrin2, arginine binds CASTOR1 and S-adenosylmethionine "
                "binds SAMTOR; each bound sensor stops inhibiting GATOR2, which inhibits "
                "GATOR1, which is the GAP that switches the Rag GTPases off.")

def fig_gf_axis():
    g = []
    chain = [("Insulin / IGF-1", 4, 140), ("Receptor (RTK)", 176, 128),
             ("PI3K", 336, 84), ("PIP<tspan dy=\"3\" font-size=\"9\">3</tspan>", 452, 78),
             ("AKT", 562, 84)]
    for label, x, w in chain:
        cls = "ac-box ac-accent" if label == "AKT" else "ac-box"
        g.append('<rect class="%s" x="%d" y="34" width="%d" height="32" rx="3"/>'
                 '<text class="ac-t" x="%d" y="55">%s</text>' % (cls, x, w, x + w // 2, label))
        if label != "AKT":
            g.append('<path class="ac-arrow" d="M%d 50 H%d" marker-end="url(#acArrow)"/>'
                     % (x + w + 4, x + w + 28))
    g.append('<rect class="ac-box" x="548" y="120" width="112" height="30" rx="3"/>'
             '<text class="ac-t" x="604" y="140">mTORC2</text>')
    g.append('<path class="ac-arrow ac-thin" d="M604 116 V72" marker-end="url(#acArrow)"/>')
    g.append('<text class="ac-t ac-sub" x="646" y="98">Ser473</text>')
    g.append('<path class="ac-inh" d="M650 50 H680"/><path class="ac-inh" d="M680 40 V60"/>')
    g.append('<rect class="ac-box" x="688" y="34" width="118" height="32" rx="3"/>'
             '<text class="ac-t" x="747" y="55">TSC complex</text>')
    g.append('<path class="ac-inh" d="M810 50 H840"/><path class="ac-inh" d="M840 40 V60"/>')
    g.append('<rect class="ac-box ac-accent" x="848" y="34" width="100" height="32" rx="3"/>'
             '<text class="ac-t" x="898" y="55">mTORC1</text>')
    g.append('<text class="ac-t ac-sub" x="474" y="18">the growth-factor branch reaches '
             'mTORC1 by removing a brake, not by pushing a pedal</text>')
    g.append('<text class="ac-t ac-sub" x="330" y="140">PRAS40, a second brake, sits inside '
             'mTORC1 itself and is released by the same kinase</text>')
    return _svg("0 0 958 158", "".join(g),
                "Insulin and IGF-1 act through a receptor tyrosine kinase, PI3K and PIP3 to "
                "activate AKT, with mTORC2 phosphorylating AKT at Ser473; AKT then inhibits "
                "the TSC complex, which relieves inhibition of mTORC1.")

def fig_feedback_loops():
    g = ['<rect class="ac-box ac-accent" x="262" y="26" width="150" height="36" rx="3"/>'
         '<text class="ac-t" x="337" y="49">mTORC1</text>']
    g.append('<path class="ac-arrow" d="M337 66 V104" marker-end="url(#acArrow)"/>')
    g.append('<rect class="ac-box" x="252" y="108" width="170" height="34" rx="3"/>'
             '<text class="ac-t" x="337" y="129">S6K1 &middot; Grb10</text>')
    g.append('<path class="ac-inh" d="M248 125 H196"/><path class="ac-inh" d="M196 114 V136"/>')
    g.append('<rect class="ac-box" x="70" y="108" width="118" height="34" rx="3"/>'
             '<text class="ac-t" x="129" y="129">IRS-1</text>')
    g.append('<path class="ac-arrow ac-thin" d="M129 104 V70" marker-end="url(#acArrow)"/>')
    g.append('<rect class="ac-box" x="70" y="34" width="118" height="34" rx="3"/>'
             '<text class="ac-t" x="129" y="55">PI3K / AKT</text>')
    g.append('<path class="ac-arrow ac-thin" d="M192 51 H256" marker-end="url(#acArrow)"/>')
    g.append('<text class="ac-t ac-sub" x="224" y="26">activates</text>')
    g.append('<text class="ac-t ac-sub" x="246" y="168">the loop is negative: mTORC1 output '
             'weakens the very input that switched it on</text>')
    g.append('<rect class="ac-box" x="470" y="26" width="160" height="36" rx="3"/>'
             '<text class="ac-t" x="550" y="49">mTORC1 inhibitor</text>')
    g.append('<path class="ac-inh" d="M466 44 H424"/><path class="ac-inh" d="M424 34 V54"/>')
    g.append('<text class="ac-t ac-sub" x="546" y="84">remove mTORC1 output and</text>')
    g.append('<text class="ac-t ac-sub" x="546" y="98">the brake goes with it</text>')
    g.append('<path class="ac-dash" d="M546 106 C546 140 260 152 176 146"/>')
    return _svg("0 0 680 180", "".join(g),
                "mTORC1 drives S6K1 and Grb10, which inhibit IRS-1 and so weaken the "
                "PI3K/AKT input that activated mTORC1; inhibiting mTORC1 releases that "
                "brake and AKT signalling can rise.")

def fig_autophagy_switch():
    g = ['<rect class="ac-box ac-accent" x="20" y="14" width="146" height="46" rx="3"/>'
         '<text class="ac-t" x="93" y="42">mTORC1</text>']
    # rychla vetev: mTORC1 -| ULK1, AMPK -> ULK1
    g.append('<path class="ac-inh" d="M170 37 H222"/><path class="ac-inh" d="M226 25 V49"/>')
    g.append('<rect class="ac-box" x="234" y="14" width="186" height="50" rx="3"/>'
             '<text class="ac-t" x="327" y="34">ULK1 complex</text>'
             '<text class="ac-t ac-sub" x="327" y="52">ULK1 &middot; ATG13 &middot; FIP200</text>')
    g.append('<path class="ac-arrow" d="M424 39 H466" marker-end="url(#acArrow)"/>')
    g.append('<rect class="ac-box" x="470" y="22" width="152" height="34" rx="3"/>'
             '<text class="ac-t" x="546" y="43">Autophagosome</text>')
    g.append('<rect class="ac-box" x="58" y="96" width="128" height="34" rx="3"/>'
             '<text class="ac-t" x="122" y="117">AMPK</text>')
    g.append('<path class="ac-arrow ac-thin" d="M190 113 H300 V70" marker-end="url(#acArrow)"/>')
    g.append('<text class="ac-t ac-sub" x="252" y="106">activating site</text>')
    # pomala vetev: mTORC1 -| TFEB -> jadro
    g.append('<path class="ac-inh" d="M30 64 V186 H208"/>'
             '<path class="ac-inh" d="M212 174 V198"/>')
    g.append('<rect class="ac-box" x="234" y="168" width="186" height="36" rx="3"/>'
             '<text class="ac-t" x="327" y="191">TFEB</text>')
    g.append('<path class="ac-arrow" d="M424 186 H466" marker-end="url(#acArrow)"/>')
    g.append('<rect class="ac-box" x="470" y="168" width="152" height="36" rx="3"/>'
             '<text class="ac-t" x="546" y="191">nucleus</text>')
    g.append('<text class="ac-t ac-sub" x="300" y="228">phosphorylated TFEB stays in the '
             'cytosol</text>')
    g.append('<text class="ac-t ac-sub" x="546" y="222">lysosomal &amp; autophagy genes</text>')
    g.append('<text class="ac-t ac-sub" x="93" y="152">minutes above, hours below</text>')
    return _svg("0 0 640 240", "".join(g),
                "mTORC1 inhibits the ULK1 complex and keeps TFEB out of the nucleus, while "
                "AMPK activates ULK1; when mTORC1 activity falls, autophagosome formation "
                "and the TFEB transcriptional program are released.")

def fig_claim_anatomy():
    """Lekce 10. Neni to biologie, ale anatomie tvrzeni: co bylo skutecne
    zmereno vs. co veta rika. Mezera mezi tim se kresli jako mezera."""
    cols = [("Model system", "mouse, cell line,\nhuman cohort"),
            ("Perturbation", "knockout, drug,\ndiet, dose"),
            ("Readout", "what was actually\nmeasured"),
            ("Claim", "the sentence in\nthe abstract")]
    g = []
    for i, (head, sub) in enumerate(cols):
        x = 6 + i * 148
        cls = "ac-box ac-accent" if head == "Claim" else "ac-box"
        g.append('<rect class="%s" x="%d" y="26" width="130" height="62" rx="3"/>' % (cls, x))
        g.append('<text class="ac-t" x="%d" y="50">%s</text>' % (x + 65, head))
        for k, line in enumerate(sub.split("\n")):
            g.append('<text class="ac-t ac-sub" x="%d" y="%d">%s</text>'
                     % (x + 65, 68 + k * 13, line))
        if i < 3:
            g.append('<path class="ac-arrow ac-thin" d="M%d 57 H%d" marker-end="url(#acArrow)"/>'
                     % (x + 134, x + 148))
    g.append('<path class="ac-dash" d="M441 30 V104"/>')
    g.append('<text class="ac-t ac-sub" x="300" y="130">the distance between the readout and '
             'the claim is where most of the reading happens</text>')
    g.append('<text class="ac-t ac-sub" x="300" y="14">every result you meet has these four '
             'parts, whether or not the abstract names them</text>')
    return _svg("0 0 600 140", "".join(g),
                "Four parts of any result: the model system, the perturbation, the readout "
                "that was actually measured, and the claim made from it; the gap between "
                "readout and claim is what a reader has to judge.")


FIGURES = {
    "mtor-integrator": fig_mtor_integrator,
    "two-complexes": fig_two_complexes,
    "rheb-axis": fig_rheb_axis,
    "rheb-spatial": fig_rheb_spatial,
    "tsc-gap": fig_tsc_gap,
    "lysosome-hub": fig_lysosome_hub,
    "aa-sensors": fig_aa_sensors,
    "gf-axis": fig_gf_axis,
    "feedback-loops": fig_feedback_loops,
    "autophagy-switch": fig_autophagy_switch,
    "claim-anatomy": fig_claim_anatomy,
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
   to the existing Atlas design system).

   Faze 3 (2026-08-31): .wrap/nav.crumb no longer overridden here -- both
   now default to --measure-wide (1100px) in shell()'s own CSS, the same
   value this override used to hardcode as 1060px. Learn widens by 40px
   to line up with .oma-topbar-inner, per the typography plan §7 Faze 3. */
.ac-eyebrow{font-family:'IBM Plex Mono',monospace;font-size:11px;letter-spacing:.1em;
  text-transform:uppercase;color:var(--teal);font-weight:600;margin:0 0 10px}
.ac-hero{max-width:780px;margin:0 0 34px}
.ac-hero h1{font-size:clamp(26px,3.4vw,34px);line-height:1.18;margin:0 0 12px}
.ac-hero .ac-lede{font-size:17px;line-height:1.62;color:var(--soft);margin:0 0 20px}
.ac-cta{display:inline-flex;align-items:center;min-height:44px;background:var(--ink);
  color:var(--on-ink,#fff);text-decoration:none;padding:11px 20px;border-radius:3px;font-size:15px;
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
.ac-evhead{display:flex;align-items:baseline;gap:9px;flex-wrap:wrap;margin-bottom:5px}
.ac-evyear{font-family:'IBM Plex Mono',monospace;font-size:12px;color:var(--soft)}
.ac-evtitle{font-size:15px;font-weight:600;text-decoration:none;color:var(--ink)}
.ac-evtitle:hover{color:var(--teal)}
.ac-evcard .ac-evfind{font-size:14px;color:var(--soft);line-height:1.55;margin:0}
.ac-evlink{font-family:'IBM Plex Mono',monospace;font-size:11.5px;
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

/* quiz ------------------------------------------------------------------
   Spec §2/§18 again: this is a comprehension check, not a game. Nothing is
   stored, nothing is scored across lessons, there is no pass mark and no
   streak. Feedback is per-question and immediate, and the reason the answer
   is right is the point -- the tick is not.
   Correctness is never carried by colour alone (a glyph and a word carry it
   too), and the evidence-tier palette is deliberately NOT reused here: those
   colours mean study type, not "good/bad". */
.ac-quiz{margin:4px 0 0}
.ac-qz{border:1px solid var(--line);border-radius:3px;padding:15px 18px 12px;margin:0 0 12px}
.ac-qz .ac-qzq{font-size:16px;line-height:1.55;margin:0 0 10px}
.ac-qzn{font-family:'IBM Plex Mono',monospace;font-size:11.5px;font-weight:600;
  letter-spacing:.06em;text-transform:uppercase;color:var(--soft);display:block;margin:0 0 4px}
.ac-qzopts{list-style:none;padding:0;margin:0}
.ac-qzopts li{margin:0 0 6px}
.ac-qzopt{display:flex;gap:9px;align-items:flex-start;width:100%;text-align:left;
  min-height:44px;padding:9px 12px;font:inherit;font-size:15px;line-height:1.5;
  color:var(--ink);background:transparent;border:1px solid var(--line);border-radius:3px;
  cursor:pointer}
.ac-qzopt:hover{border-color:var(--teal)}
.ac-qzopt:focus-visible{outline:2px solid var(--teal);outline-offset:2px}
.ac-qzkey{font-family:'IBM Plex Mono',monospace;font-size:12.5px;font-weight:600;
  color:var(--soft);flex:0 0 auto;padding-top:1px}
.ac-qz[data-done] .ac-qzopt{cursor:default}
.ac-qz[data-done] .ac-qzopt:hover{border-color:var(--line)}
.ac-qzopt[data-mark="right"]{border-color:var(--teal);box-shadow:inset 3px 0 0 var(--teal)}
.ac-qzopt[data-mark="right"] .ac-qzkey{color:var(--teal)}
.ac-qzopt[data-mark="wrong"]{border-color:var(--amber);box-shadow:inset 3px 0 0 var(--amber)}
.ac-qzopt[data-mark="wrong"] .ac-qzkey{color:var(--amber)}
.ac-qzopt[data-mark] .ac-qzkey::after{content:" \\2713"}
.ac-qzopt[data-mark="wrong"] .ac-qzkey::after{content:" \\2715"}
.ac-qzwhy{font-size:14.5px;line-height:1.6;margin:10px 0 2px;
  border-left:3px solid var(--teal);padding:0 0 0 12px}
.ac-qzverdict{font-family:'IBM Plex Mono',monospace;font-size:11.5px;font-weight:600;
  letter-spacing:.06em;text-transform:uppercase;color:var(--soft);display:block;margin:0 0 4px}
.ac-qz details>summary{cursor:pointer;font-family:'IBM Plex Mono',monospace;font-size:12px;
  font-weight:600;letter-spacing:.05em;text-transform:uppercase;color:var(--teal);
  list-style:none;display:inline-flex;align-items:center;min-height:44px}
.ac-qz details>summary::-webkit-details-marker{display:none}
.ac-qz details>summary::after{content:" \\2192"}
.ac-qz details[open]>summary::after{content:""}
.ac-qz details p{font-size:14.5px;line-height:1.6;margin:2px 0 0}
.ac-qztally{font-size:14px;color:var(--soft);margin:2px 0 0}

/* learning objectives + research skill (Phase 2 §12/§13) ------------------ */
.ac-objlbl{font-family:'IBM Plex Mono',monospace;font-size:11px;font-weight:600;
  letter-spacing:.07em;text-transform:uppercase;color:var(--soft);margin:0 0 8px}
.ac-objlist{margin:0 0 10px;padding-left:20px}
.ac-objlist li{font-size:15.5px;line-height:1.6;margin:0 0 5px}
.ac-skill{font-size:14px;color:var(--soft);margin:0}
.ac-skill span{font-family:'IBM Plex Mono',monospace;font-size:11px;font-weight:600;
  letter-spacing:.06em;text-transform:uppercase;margin-right:8px}

/* interactive exercises (Phase 2) ---------------------------------------
   Tri vrstvy, stejne jako kviz: obsah je v HTML, <details> ho slozi pro
   ctenare bez JS, JS ho jen sekvencuje. Nic vedeckeho nezije jen v JS --
   verify_prerender.py a pravidlo 13 ve verify_academy.py to hlidaji.
   Barva nikdy nenese vyznam sama: stav uzlu je barva + tloustka + slovo,
   spravnost je glyf + slovo. Paleta evidence tieru se tu NEPUJCUJE. */
.ac-ex{border:1px solid var(--line);border-radius:3px;padding:16px 18px 14px;margin:0 0 16px}
.ac-exkind{font-family:'IBM Plex Mono',monospace;font-size:11px;font-weight:600;
  letter-spacing:.07em;text-transform:uppercase;color:var(--soft);display:block;margin:0 0 6px}
.ac-ex h3{font-size:17px;line-height:1.35;margin:0 0 8px}
.ac-ex p{font-size:15.5px;line-height:1.6;margin:0 0 10px}
.ac-ex details{margin:0 0 4px}
.ac-ex details>summary{cursor:pointer;font-family:'IBM Plex Mono',monospace;font-size:12px;
  font-weight:600;letter-spacing:.05em;text-transform:uppercase;color:var(--teal);
  list-style:none;display:inline-flex;align-items:center;min-height:44px}
.ac-ex details>summary::-webkit-details-marker{display:none}
.ac-ex details>summary::after{content:" \\2192"}
.ac-ex details[open]>summary::after{content:""}
.ac-ex details p,.ac-ex details li{font-size:14.5px;line-height:1.6}

/* what this shows / does not show */
.ac-shows{list-style:none;padding:0;margin:0 0 10px}
.ac-shows li{position:relative;padding-left:26px;font-size:15px;line-height:1.55;margin:0 0 6px}
.ac-shows li::before{position:absolute;left:0;top:0;font-family:'IBM Plex Mono',monospace;
  font-weight:600}
.ac-shows li.ac-yes::before{content:"\\2713";color:var(--teal)}
.ac-shows li.ac-no::before{content:"\\2715";color:var(--amber)}
.ac-showslbl{font-family:'IBM Plex Mono',monospace;font-size:11px;font-weight:600;
  letter-spacing:.06em;text-transform:uppercase;color:var(--soft);margin:0 0 6px}

/* interactive model */
.ac-model{margin:0}
/* Na uzkem displeji by se schema zmenslo tak, ze by popisky uzlu byly
   necitelne. Misto toho dostane vlastni vodorovny scroll -- stranka sama
   se nikdy neposouva do strany (stejny vzor jako .ac-cmpwrap a pravy rail). */
.ac-mdscroll{overflow-x:auto;-webkit-overflow-scrolling:touch;margin:2px 0 10px}
.ac-mdsvg{width:100%;height:auto;color:var(--ink);overflow:visible;display:block;margin:0 auto}
.ac-mdnode rect{fill:var(--paper);stroke:var(--line-strong,rgba(0,0,0,.34));stroke-width:1}
.ac-mdnode text{font-family:'DM Sans',-apple-system,sans-serif;font-size:12px;fill:var(--ink);
  text-anchor:middle}
.ac-mdnode[data-flow="on"] rect{stroke:var(--teal);stroke-width:2}
.ac-mdnode[data-flow="off"] rect{stroke-dasharray:3 3}
.ac-mdnode[data-flow="off"] text{fill:var(--soft)}
.ac-mdnode{cursor:pointer}
.ac-mdnode:focus-visible rect{outline:2px solid var(--teal);outline-offset:2px}
.ac-mdedge{fill:none;stroke:var(--ink);stroke-width:1.2;pointer-events:none}  /* hrana nikdy nesmi prekryt klikaci uzel */
.ac-mdedge[data-eff="inhibits"]{stroke:var(--teal);stroke-width:1.6}
.ac-mdedge[data-flow="off"]{stroke:var(--soft);stroke-dasharray:4 4;stroke-width:1}
.ac-mdstate{font-family:'IBM Plex Mono',monospace;font-size:11px;fill:var(--soft);
  text-anchor:middle}
.ac-mdctl{display:flex;flex-wrap:wrap;gap:14px;margin:0 0 12px}
.ac-mdgrp{display:flex;flex-direction:column;gap:4px}
.ac-mdgrp>span{font-family:'IBM Plex Mono',monospace;font-size:11px;letter-spacing:.06em;
  text-transform:uppercase;color:var(--soft)}
.ac-mdbtns{display:flex;border:1px solid var(--line);border-radius:3px;overflow:hidden}
.ac-mdbtns button{font-family:'IBM Plex Mono',monospace;font-size:12px;letter-spacing:.04em;
  text-transform:uppercase;background:none;border:none;border-right:1px solid var(--line);
  padding:0 14px;min-height:44px;cursor:pointer;color:var(--ink)}
.ac-mdbtns button:last-child{border-right:none}
.ac-mdbtns button:hover{color:var(--teal)}
.ac-mdbtns button[aria-pressed="true"]{background:var(--ink);color:var(--on-ink,#fff);font-weight:600}
.ac-mdout{border-left:3px solid var(--teal);padding:2px 0 2px 12px;margin:0 0 10px}
.ac-mdreadout{font-family:'IBM Plex Mono',monospace;font-size:13px;margin:0 0 4px}
.ac-mdnote{font-size:14.5px;line-height:1.6;margin:0}
.ac-mdkey{margin:8px 0 6px;padding:0}
.ac-mdkey div{border-top:1px solid var(--line);padding:8px 0}
.ac-mdkey dt{font-weight:600;font-size:14.5px;margin:0 0 2px}
.ac-mdkey dd{margin:0;font-size:14px;line-height:1.55;color:var(--soft)}
.ac-mdkey div[data-hi="1"]{background:rgba(163,31,52,.06)}
.ac-mdreset{background:none;border:none;padding:0;font-family:'IBM Plex Mono',monospace;
  font-size:11.5px;letter-spacing:.05em;text-transform:uppercase;color:var(--teal);
  cursor:pointer;min-height:44px}
.ac-mdcap{font-size:13.5px;color:var(--soft);line-height:1.55;margin:-4px 0 12px}
.ac-mdteach{font-size:13px;color:var(--soft);line-height:1.5;margin:6px 0 0}

/* predict -> observe -> explain */
.ac-pdstep{font-family:'IBM Plex Mono',monospace;font-size:11px;font-weight:600;
  letter-spacing:.07em;text-transform:uppercase;color:var(--soft);display:block;margin:12px 0 6px}
.ac-pdobs{border:1px solid var(--line);border-radius:3px;padding:12px 14px;margin:0 0 10px}
.ac-pdmethod{font-size:14px;color:var(--soft);line-height:1.55;margin:6px 0 6px}
.ac-pdreadout{font-size:15.5px;line-height:1.55;margin:0 0 8px}

/* evidence comparison */
.ac-cmp{width:100%;border-collapse:collapse;margin:2px 0 12px;font-size:14.5px}
.ac-cmp th,.ac-cmp td{border-bottom:1px solid var(--line);padding:8px 10px 8px 0;
  text-align:left;vertical-align:top;line-height:1.5}
.ac-cmp th{font-family:'IBM Plex Mono',monospace;font-size:11px;letter-spacing:.06em;
  text-transform:uppercase;color:var(--soft);font-weight:600}
.ac-cmpwrap{overflow-x:auto}

/* experiment builder */
.ac-dsgrid{display:grid;gap:14px;margin:0 0 12px}
@media (min-width:620px){.ac-dsgrid{grid-template-columns:1fr 1fr}}
.ac-dsgrp{border:1px solid var(--line);border-radius:3px;padding:10px 12px}
.ac-dsgrp>legend,.ac-dsgrp>.ac-dslbl{font-family:'IBM Plex Mono',monospace;font-size:11px;
  letter-spacing:.06em;text-transform:uppercase;color:var(--soft);padding:0;margin:0 0 6px}
.ac-dsopt{display:flex;gap:9px;align-items:flex-start;min-height:44px;padding:4px 0;
  font-size:14.5px;line-height:1.5;cursor:pointer}
.ac-dsopt input{margin-top:5px;flex:0 0 auto;accent-color:var(--teal)}
.ac-dsfb{border-left:3px solid var(--teal);padding:2px 0 2px 12px;margin:10px 0 0}
.ac-dsfb h4{font-family:'IBM Plex Mono',monospace;font-size:11px;letter-spacing:.06em;
  text-transform:uppercase;color:var(--soft);margin:0 0 6px;font-weight:600}
.ac-dsfb p{font-size:14.5px;line-height:1.6;margin:0 0 8px}

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


CHALLENGE_CSS = """
/* ---- Research Challenges (build_academy.py) --------------------------
   Appended AFTER ACADEMY_CSS, so it inherits every Academy token and only
   adds what a decision environment needs that a lesson does not: numbered
   steps, a budget meter, experiment cards and a qualitative result chart.
   No new palette, no new type scale, radius stays 3px. Spec §32: slightly
   more immersive than a lesson, unmistakably the same site. */
.ac-rcframe{font-size:14.5px;line-height:1.6;color:var(--soft);border-left:3px solid var(--line);
  padding:2px 0 2px 12px;margin:0 0 26px}
.ac-rcstep{border-top:1px solid var(--line);padding-top:20px;margin:0 0 34px}
.ac-rcnum{font-family:'IBM Plex Mono',monospace;font-size:10.5px;letter-spacing:.1em;
  text-transform:uppercase;color:var(--teal);font-weight:600;margin:0 0 6px}
.ac-rcstep>h2{margin:0 0 10px}
.ac-rcknow{list-style:none;padding:0;margin:4px 0 18px}
.ac-rcknow li{border-top:1px solid var(--line);padding:9px 0;font-size:15px;line-height:1.6}
.ac-rcsid{font-family:'IBM Plex Mono',monospace;font-size:11px;letter-spacing:.04em;
  border:1px solid var(--line);border-radius:3px;padding:1px 5px;text-decoration:none;
  white-space:nowrap}
.ac-rcsid:hover{border-color:var(--teal)}

/* budget meter -- a constraint, not a score. No countdown, no colour alarm. */
.ac-rcbudget{border:1px solid var(--line);border-radius:3px;padding:14px 16px;margin:0 0 18px}
.ac-rcblabel{font-family:'IBM Plex Mono',monospace;font-size:10.5px;letter-spacing:.1em;
  text-transform:uppercase;color:var(--soft);font-weight:600;margin:0 0 6px}
.ac-rcbleft{font-size:15px;margin:0 0 8px}
.ac-rcbleft strong{font-family:'IBM Plex Mono',monospace;font-size:20px;color:var(--teal)}
.ac-rcbartrack{display:block;background:var(--line);border-radius:2px;height:6px;overflow:hidden}
.ac-rcbarfill{display:block;background:var(--teal);height:100%}
.ac-rcbudgetbar{margin:0 0 8px}

.ac-rcbtns{display:flex;flex-wrap:wrap;gap:14px;align-items:center;margin:16px 0 18px}

/* laborator: panel dilcich otazek + rozpocet vedle sebe -------------------
   Panel je videt od zacatku zamerne: cil "dostat maximum odpovedi za minimum
   kreditu" se neda sledovat, kdyz clovek nevi, z ceho se ta puvodni otazka
   sklada. Neni to skore -- je to mapa otazky. */
.ac-labtop{display:grid;gap:16px;margin:0 0 18px}
@media (min-width:760px){.ac-labtop{grid-template-columns:1.25fr 1fr;align-items:start}}
.ac-labgoals{border:1px solid var(--line);border-radius:3px;padding:14px 16px}
.ac-labcount{float:right;font-family:'IBM Plex Mono',monospace;letter-spacing:0;
  text-transform:none}
.ac-labcount strong{font-size:16px;color:var(--teal)}
.ac-labgoallist{list-style:none;padding:0;margin:8px 0 0;counter-reset:g}
.ac-labgoallist li{display:flex;gap:9px;align-items:flex-start;padding:7px 0;
  border-top:1px solid var(--line);font-size:14px;line-height:1.5;color:var(--soft)}
.ac-labgoallist li[data-done="1"]{color:var(--ink)}
.ac-labtick{font-family:'IBM Plex Mono',monospace;flex:0 0 auto;width:14px}
.ac-labgoallist li[data-done="1"] .ac-labtick{color:var(--teal);font-weight:600}
.ac-labgoallist li.ac-labopenq{border-left:2px solid var(--line);padding-left:9px}
.ac-labgnote{display:block;font-size:13px;line-height:1.5;margin:3px 0 0;opacity:.85}
.ac-labtop .ac-rcbudget{margin:0}

/* trasa -- klikatelna, navrat kredity nevraci */
.ac-labpath{margin:0 0 16px}
.ac-labpath ol{list-style:none;display:flex;flex-wrap:wrap;gap:6px;padding:0;margin:6px 0 0}
.ac-labpath li{display:flex;align-items:center}
.ac-labpath li+li::before{content:"→";color:var(--soft);margin-right:6px;
  font-family:'IBM Plex Mono',monospace}
.ac-labpath button{font-size:13px;line-height:1.3;background:none;cursor:pointer;
  border:1px solid var(--line);border-radius:3px;padding:6px 10px;min-height:36px;
  color:var(--ink);text-align:left}
.ac-labpath button:hover{border-color:var(--teal);color:var(--teal)}
.ac-labpath button span{font-family:'IBM Plex Mono',monospace;font-size:11px;
  color:var(--soft);margin-left:5px}
.ac-labpath li[data-here="1"] button{background:var(--ink);color:var(--on-ink,#fff);
  border-color:var(--ink);font-weight:600}
.ac-labpath li[data-here="1"] button span{color:var(--on-ink,#fff);opacity:.7}

.ac-labnexthead{display:flex;flex-wrap:wrap;gap:6px 16px;align-items:baseline;
  justify-content:space-between;margin:18px 0 8px;border-bottom:1px solid var(--line);
  padding-bottom:7px}
.ac-labnextlbl{font-family:'IBM Plex Mono',monospace;font-size:11px;font-weight:600;
  letter-spacing:.07em;text-transform:uppercase;color:var(--soft);margin:0}
.ac-labremain{font-family:'IBM Plex Mono',monospace;font-size:11px;letter-spacing:.05em;
  text-transform:uppercase;color:var(--soft);margin:0;white-space:nowrap}
.ac-labremain strong{font-size:15px;color:var(--teal);letter-spacing:0}
.ac-labafter{font-family:'IBM Plex Mono',monospace;font-size:11px;letter-spacing:.04em;
  text-transform:uppercase;color:var(--soft);margin:0;text-align:center;width:100%}
.ac-labopenbox{margin:0 0 18px}
.ac-labopenbox>summary{font-family:'IBM Plex Mono',monospace;font-size:11.5px;
  letter-spacing:.05em;text-transform:uppercase;color:var(--teal);cursor:pointer;
  min-height:44px;display:flex;align-items:center}
.ac-labopens{font-size:14px;line-height:1.55;color:var(--soft);margin:14px 0 10px}
.ac-labpred{display:inline-block;font-family:'IBM Plex Mono',monospace;font-size:10.5px;
  letter-spacing:.05em;text-transform:uppercase;color:var(--teal);border:1px solid var(--teal);
  border-radius:3px;padding:3px 7px;margin:0 0 10px;line-height:1.4}
.ac-labfull>[data-rc-out]{border-top:none;margin-top:0}

/* debrief -- co ta sada dohromady koupila */
.ac-rcdebrief{border:1px solid var(--teal);border-radius:3px;padding:16px 18px;margin:0 0 18px}
.ac-rcdebrief h3{margin:0 0 8px;font-size:17px;display:inline-block}
.ac-rcdebrief h3:focus-visible{outline:2px solid var(--teal);outline-offset:3px}
.ac-rcdebrief p{font-size:14.5px;line-height:1.62}
.ac-rcshort{font-size:16px;line-height:1.6;margin:0 0 10px}
.ac-rcrules{list-style:none;padding:0;margin:0 0 14px}
.ac-rcrules li{border-left:3px solid var(--teal);padding:2px 0 2px 12px;margin:0 0 10px;
  font-size:14.5px;line-height:1.62}
.ac-rcport{border-top:1px solid var(--line);border-bottom:1px solid var(--line);
  padding:10px 0;margin:0 0 14px}
.ac-rcportnames{font-weight:600;margin:0 0 4px}
.ac-rcskip{list-style:none;padding:0;margin:0}
.ac-rcskip li{border-top:1px solid var(--line);padding:8px 0;display:grid;
  grid-template-columns:minmax(0,1fr) auto;gap:2px 12px;font-size:14px;line-height:1.5}
.ac-rcskipn{font-weight:600}
.ac-rcskipc{font-family:'IBM Plex Mono',monospace;font-size:12px;color:var(--soft);
  white-space:nowrap;text-align:right}
.ac-rcskipa{grid-column:1/-1;color:var(--soft)}

/* krok "Where the question stands" */
.ac-rcanswer{border-left:3px solid var(--teal);padding:2px 0 2px 14px;margin:0 0 20px}
.ac-rcshort strong{font-family:'IBM Plex Mono',monospace}
.ac-rcanswer .ac-rcshort{font-size:17.5px;line-height:1.58;margin:0}
.ac-rcinterp p{font-size:15.5px;line-height:1.65;margin:0 0 12px}
.ac-rcverdicts dt{font-size:15px}
.ac-rcverdicts dd{color:var(--ink)}

/* experiment card */
.ac-rcspent{font-family:'IBM Plex Mono',monospace;font-size:11px;letter-spacing:.06em;
  text-transform:uppercase;color:var(--teal);font-weight:600;margin:0}
.ac-rcexp{border:1px solid var(--line);border-radius:3px;padding:16px 18px;margin:0 0 16px}

/* volba kroku ------------------------------------------------------------
   Moznosti musi jit POROVNAT, jinak to neni volba. Proto grid vedle sebe a
   kompaktni hlava: cena velkym cislem (to je ten kompromis), nazev, na co
   miri, co si zada, a navrh sbaleny do <details>. Vysledek se rozbaluje az
   u kroku, na kterem clovek stoji -- pred zaplacenim by to stejne byla
   odpoved na otazku, kterou si jeste nekoupil. */
[data-lab-next],[data-lab-open]>div{display:grid;gap:14px;align-items:stretch;
  grid-template-columns:repeat(auto-fit,minmax(min(100%,224px),1fr))}
.ac-labnode[data-view="choice"]{margin:0;display:flex;flex-direction:column}
.ac-labnode[data-view="choice"] .ac-labfull{display:none}
.ac-labnode[data-view="choice"] .ac-labchoice{flex:1;display:flex;flex-direction:column}
.ac-labnode[data-view="choice"] .ac-labact{margin-top:auto;padding-top:10px}
.ac-labnode[data-view="choice"] .ac-rcrun{width:100%;justify-content:center}
.ac-labnode[data-view="result"]{border-color:var(--teal)}
.ac-labcost{font-family:'IBM Plex Mono',monospace;font-size:11px;letter-spacing:.06em;
  text-transform:uppercase;color:var(--soft);margin:0 0 4px}
.ac-labcost strong{font-size:26px;line-height:1;color:var(--teal);letter-spacing:0;
  margin-right:4px}
.ac-labchoice h3{margin:0 0 10px;font-size:16.5px;line-height:1.3}
.ac-labfield{font-size:13.5px;line-height:1.5;color:var(--soft);margin:0 0 8px}
.ac-labfield .ac-rclbl{margin:0 0 1px}
.ac-labdesign{margin:2px 0 0}
.ac-labdesign>summary{font-family:'IBM Plex Mono',monospace;font-size:11px;
  letter-spacing:.05em;text-transform:uppercase;color:var(--teal);cursor:pointer;
  min-height:36px;display:flex;align-items:center}
.ac-labdesign .ac-cmp{font-size:13.5px}
.ac-labact{display:flex;flex-wrap:wrap;gap:10px;align-items:center}
.ac-cta[hidden],.ac-rcrun[hidden]{display:none}
.ac-rcrun[disabled]{opacity:.45;cursor:not-allowed}
.ac-rcrun[disabled]:hover{background:none;color:var(--ink)}
.ac-rcdenied{font-size:14px;color:var(--soft);line-height:1.55;margin:6px 0 0}
.ac-rcexp .ac-cmp tr:last-child th,.ac-rcexp .ac-cmp tr:last-child td{border-bottom:none}
.ac-rcexp .ac-cmpwrap{margin-bottom:2px}
.ac-rcout{border-top:1px solid var(--line);margin:12px 0 0;padding-top:12px}
.ac-rcsrc,.ac-rchypo{font-size:14px;line-height:1.6;margin:0 0 10px}
.ac-rclbl{font-family:'IBM Plex Mono',monospace;font-size:10.5px;
  letter-spacing:.08em;text-transform:uppercase;color:var(--soft);font-weight:600;
  display:block;margin:0 0 3px}
.ac-rchypo{border-left:3px solid var(--soft);padding:2px 0 2px 12px;color:var(--soft)}
.ac-rchypo .ac-rclbl{color:var(--ink)}

/* qualitative result chart -- levels, never invented numbers */
.ac-rcchart{margin:0 0 8px}
.ac-rcunit{font-family:'IBM Plex Mono',monospace;font-size:10.5px;letter-spacing:.08em;
  text-transform:uppercase;color:var(--soft);margin:0 0 8px}
.ac-rcbarrow{display:grid;grid-template-columns:minmax(0,1fr) 42% auto;gap:10px;
  align-items:center;padding:4px 0;font-size:14px}
.ac-rcbarlbl{line-height:1.4}
.ac-rcbarval{font-family:'IBM Plex Mono',monospace;font-size:11px;color:var(--soft);
  white-space:nowrap}
@media (max-width:560px){
  .ac-rcbarrow{grid-template-columns:minmax(0,1fr);gap:3px}
  .ac-rcbarval{text-align:right}
}
.ac-rcinfo{font-size:14px;line-height:1.6;color:var(--soft);margin:10px 0 0}
.ac-rcnotes{border-left:3px solid var(--teal);padding:2px 0 2px 12px;margin:8px 0 12px}
.ac-rcnotes p{font-size:14.5px;line-height:1.6;margin:0 0 8px}
.ac-rcnotes p:last-child{margin-bottom:0}
.ac-rcnew{border:1px solid var(--line);border-left:3px solid var(--teal);border-radius:3px;
  padding:12px 14px;margin:0 0 14px}
.ac-rcnewlbl{font-family:'IBM Plex Mono',monospace;font-size:10.5px;letter-spacing:.1em;
  text-transform:uppercase;color:var(--teal);font-weight:600;margin:0 0 6px}
.ac-rcnew p:last-child{margin:0;font-size:15px;line-height:1.62}
.ac-rccmp{border:1px solid var(--line);border-radius:3px;padding:14px 16px}
.ac-rcrefl{margin:0 0 18px}
.ac-rccommit{font-size:14px;color:var(--teal);margin:6px 0 0;
  font-family:'IBM Plex Mono',monospace;letter-spacing:.03em}
.ac-rcnextlbl{font-family:'IBM Plex Mono',monospace;font-size:10.5px;letter-spacing:.08em;
  text-transform:uppercase;color:var(--soft);font-weight:600;margin:14px 0 5px}
.ac-rc .ac-list .ac-n{width:26px}
"""

CHALLENGE_JS = """
<script>
/* Research Challenges. Same contract as every other interactive block on this
   site: the page is complete without this script. Here it only (a) keeps the
   research budget, (b) reveals the written feedback for the option a reader
   picked instead of showing all of them at once, and (c) reports six events to
   the analytics that shell() already loads. No fetch, no storage, no score.

   Nothing scientific exists only in JS: every result, every note and every
   limitation is in the HTML above, which is why the no-JS view is the same
   page with more of it visible at once. */
(function(){
  var root=document.body.getAttribute('data-rc-challenge');
  if(!root) return;
  function track(name,extra){
    try{ if(typeof gtag==='function'){
      var p={challenge:root}; if(extra) for(var k in extra) p[k]=extra[k];
      gtag('event',name,p);
    } }catch(e){}
  }
  track('challenge_started');

  /* ---------- option groups with written feedback ---------- */
  document.querySelectorAll('[data-rc-notes]').forEach(function(box){
    var notes=box.querySelectorAll('[data-rc-note]');
    notes.forEach(function(p){p.hidden=true;});
    /* cely kontejner, ne jen odstavce: jinak zbyde 3px pahyl leveho ramecku */
    box.hidden=true;
    var group=box.previousElementSibling;
    if(!group||!group.querySelectorAll) return;
    var step=box.closest('[data-rc-step]');
    var kind=step?step.getAttribute('data-rc-step'):'';
    group.querySelectorAll('[data-rc-opt]').forEach(function(b){
      b.addEventListener('click',function(){
        var i=b.getAttribute('data-rc-opt');
        group.querySelectorAll('[data-rc-opt]').forEach(function(o){
          o.setAttribute('aria-pressed',String(o===b));
        });
        notes.forEach(function(p){p.hidden=p.getAttribute('data-rc-note')!==i;});
        box.hidden=false;
        var tag=b.textContent.trim().slice(0,60);
        if(kind==='hypothesis'){
          track('hypothesis_committed',{choice:tag});
          var c=step.querySelector('[data-rc-committed]');
          if(c){c.textContent='Committed. You can revise this later \\u2014 that is the point.';c.hidden=false;}
        }
        else if(kind==='revise') track('hypothesis_revised',{choice:tag});
        else if(kind==='confounder') track('confounder_answered',{choice:tag});
        else if(kind==='experiments') track('experiment_interpreted',{choice:tag});
        else if(kind==='reflect') track('challenge_completed',{choice:tag});
      });
    });
  });

  /* ---------- break-the-model predictions ---------- */
  document.querySelectorAll('.ac-rcpd').forEach(function(pd){
    var fall=pd.querySelector('.ac-rcfall'); if(fall) fall.hidden=true;
    var after=pd.querySelectorAll('[data-ac-after]');
    after.forEach(function(x){x.hidden=true;});
    var correct=parseInt(pd.getAttribute('data-answer'),10);
    var opts=pd.querySelectorAll('.ac-qzopt');
    opts.forEach(function(b){
      b.addEventListener('click',function(){
        if(pd.hasAttribute('data-done')) return;
        pd.setAttribute('data-done','1');
        var picked=parseInt(b.getAttribute('data-i'),10);
        opts.forEach(function(o){
          var i=parseInt(o.getAttribute('data-i'),10);
          o.setAttribute('aria-disabled','true');
          if(i===correct) o.setAttribute('data-mark','right');
          else if(i===picked) o.setAttribute('data-mark','wrong');
        });
        var v=pd.querySelector('.ac-qzverdict');
        if(v) v.textContent=(picked===correct)?'That is what the model does':'Not what the model does';
        after.forEach(function(x){x.hidden=false;});
      });
    });
  });

  /* ---------- vyzkumna cesta (lab) ----------
     Stavovy automat, ne nakupni seznam. Drzi ctyri veci: kde stojis (`cursor`),
     co uz jsi spustil (`ran`), kolik zbyva a jestli je investigace uzavrena.

     SUNK COST je tu zamerne: navrat na drivejsi krok je jen presun kurzoru,
     kredity se NEVRACEJI. Proto se da vratit a vzit jinou vetev, ale ne to
     odestat -- presne jako ve skutecnem programu.

     Karty kroku existuji v HTML od zacatku (bez JS je to cely rozpis
     vyzkumu); tenhle skript je jen presouva mezi "kde jsi", "co to otevrelo"
     a "co je jeste otevrene". Nic vedeckeho nevznika az tady. */
  var bx=document.querySelector('[data-rc-budget]');
  if(!bx) return;
  var dEl=document.querySelector('script.ac-rcdata'), D=null;
  if(dEl){try{D=JSON.parse(dEl.textContent);}catch(e){}}
  if(!D) return;
  var step=bx.closest('[data-rc-step]');
  var pool=step.querySelector('[data-lab-pool]');
  var hereBox=step.querySelector('[data-lab-here]');
  var nextBox=step.querySelector('[data-lab-next]');
  var nextLbl=step.querySelector('[data-lab-nextlbl]');
  var nextHead=step.querySelector('[data-lab-nexthead]');
  var remainEl=step.querySelector('[data-lab-remain]');
  var openBox=step.querySelector('[data-lab-open]');
  var openInner=openBox?openBox.querySelector('div'):null;
  var pathBox=step.querySelector('[data-lab-path]');
  var btns=step.querySelector('[data-lab-btns]');
  var deb=step.querySelector('[data-rc-debrief]');
  var leftEl=bx.querySelector('[data-rc-left]'), fill=bx.querySelector('[data-rc-fill]');
  var countEl=step.querySelector('[data-lab-count]');
  var cards={};
  [].forEach.call(step.querySelectorAll('[data-rc-exp]'),function(c){
    cards[c.getAttribute('data-rc-exp')]=c;});
  [].forEach.call(step.querySelectorAll('.ac-rcfall'),function(f){f.hidden=true;});
  /* zasobnik karet: bez JS je to cely rozpis vyzkumu shora dolu, s JS z nej
     karty jen berem a schovavame ho -- jinak by pod volbou visely vsechny
     kroky naraz a nebylo by poznat, mezi cim se vybira */
  if(pool) pool.hidden=true;

  var total=D.total, left=total, cursor=null, ran=[], closed=false;

  function findings(){var f={};ran.forEach(function(id){
    (D.nodes[id].yields||[]).forEach(function(y){f[y]=1;});});return f;}
  function answered(){var f=findings();
    return D.goals.filter(function(g){
      return g.need.every(function(y){return f[y];});});}
  function unlocked(){var u={};D.start.forEach(function(i){u[i]=1;});
    ran.forEach(function(id){(D.nodes[id].next||[]).forEach(function(i){u[i]=1;});});
    return u;}
  function childrenOf(id){return id===null?D.start.slice():(D.nodes[id].next||[]).slice();}
  function isRun(id){return ran.indexOf(id)>=0;}

  function place(card,box){if(card&&box&&card.parentNode!==box) box.appendChild(card);}

  function paint(){
    if(leftEl) leftEl.textContent=String(left);
    if(fill) fill.style.width=(total?Math.max(0,left)/total*100:0)+'%';

    /* dilci otazky */
    var got={};answered().forEach(function(g){got[g.id]=1;});
    if(countEl) countEl.textContent=String(answered().length);
    [].forEach.call(step.querySelectorAll('[data-goal]'),function(li){
      var on=!!got[li.getAttribute('data-goal')];
      li.setAttribute('data-done',on?'1':'0');
      var t=li.querySelector('.ac-labtick'); if(t) t.textContent=on?'✓':'○';
    });

    /* kam co patri */
    var u=unlocked(), kids=childrenOf(cursor), inKids={};
    kids.forEach(function(i){inKids[i]=1;});
    Object.keys(cards).forEach(function(id){
      var box=pool;
      if(id===cursor) box=hereBox;
      else if(inKids[id]&&(u[id]||isRun(id))) box=nextBox;
      else if(u[id]&&!isRun(id)) box=openInner;
      place(cards[id],box);
      /* volba vs. vysledek: dokud krok jen zvazujes, vidis kompaktni kartu,
         kterou jde porovnat s tou vedle. Rozbali se, az na nem stojis. */
      cards[id].setAttribute('data-view',box===hereBox?'result':'choice');

      var c=cards[id], run=c.querySelector('.ac-rcrun'), back=c.querySelector('.ac-labback');
      var sp=c.querySelector('.ac-rcspent'), no=c.querySelector('.ac-rcdenied');
      var outs=c.querySelectorAll('[data-rc-out],[data-rc-event]');
      var done=isRun(id);
      [].forEach.call(outs,function(x){x.hidden=!done;});
      if(sp) sp.hidden=!done;
      c.setAttribute('data-rc-spent',done?'1':'0');
      var after=c.querySelector('[data-lab-after]');
      if(done){
        if(run) run.hidden=true;
        if(no) no.hidden=true;
        if(after) after.hidden=true;
        if(back) back.hidden=(id===cursor);
      }else{
        if(back) back.hidden=true;
        var ok=(D.nodes[id].cost<=left)&&!closed;
        if(run){run.hidden=closed;run.disabled=!ok;run.setAttribute('aria-disabled',String(!ok));}
        if(no) no.hidden=ok||closed;
        /* co ti po tomhle kroku zbyde -- pri porovnavani dvou moznosti je to
           uzitecnejsi cislo nez jejich cena */
        if(after){
          after.hidden=!ok;
          after.textContent='leaves '+(left-D.nodes[id].cost);
        }
      }
    });

    /* nadpis nad moznostmi */
    var runnable=kids.length>0;
    if(remainEl) remainEl.textContent=String(left);
    if(nextHead) nextHead.hidden=closed||!runnable;
    if(nextLbl){
      nextLbl.textContent=((cursor===null)?'Where to start':'What this step opened up')+
                          (kids.length>1?' — pick one':'');
    }
    if(nextBox) nextBox.hidden=closed;
    if(openBox){
      var others=Object.keys(cards).filter(function(id){
        return u[id]&&!isRun(id)&&!inKids[id];});
      openBox.hidden=closed||!others.length;
      var sm=openBox.querySelector('summary');
      if(sm) sm.textContent=others.length+' other step'+(others.length===1?'':'s')+
        ' already open to you';
    }
    if(cursor!==null&&!runnable&&!closed&&nextLbl){
      if(nextHead) nextHead.hidden=false;
      nextLbl.textContent='This line is finished — go back to an earlier step to take another branch.';
    }

    /* trasa */
    if(pathBox){
      var ol=pathBox.querySelector('ol');
      var h='<li'+(cursor===null?' data-here="1"':'')+
            '><button type="button" data-lab-goto="__start__">The question</button></li>';
      ran.forEach(function(id){
        h+='<li'+(cursor===id?' data-here="1"':'')+'><button type="button" data-lab-goto="'+
           id+'">'+D.nodes[id].label+' <span>'+D.nodes[id].cost+'</span></button></li>';
      });
      if(ol) ol.innerHTML=h;
      pathBox.hidden=false;
    }
    if(btns) btns.hidden=false;
  }

  function goto_(id){
    cursor=(id==='__start__')?null:id;
    paint();
    var box=(cursor===null)?nextBox:hereBox;
    if(box&&box.scrollIntoView) box.scrollIntoView({block:'nearest'});
  }

  function run(id){
    if(closed||isRun(id)) return;
    var n=D.nodes[id];
    if(n.cost>left) return;
    var u=unlocked(); if(!u[id]) return;
    left-=n.cost; ran.push(id); cursor=id;
    paint();
    track('experiment_run',{experiment:id,cost:n.cost,remaining:left,
                            answers:answered().length});
  }

  step.addEventListener('click',function(ev){
    var t=ev.target.closest?ev.target.closest('button'):null;
    if(!t) return;
    if(t.classList.contains('ac-rcrun')){
      var c=t.closest('[data-rc-exp]'); if(c) run(c.getAttribute('data-rc-exp'));
    }else if(t.classList.contains('ac-labback')){
      var c2=t.closest('[data-rc-exp]'); if(c2) goto_(c2.getAttribute('data-rc-exp'));
    }else if(t.hasAttribute('data-lab-goto')){
      goto_(t.getAttribute('data-lab-goto'));
    }
  });

  function uniq(a){var s={},o=[];a.forEach(function(t){if(!s[t]){s[t]=1;o.push(t);}});return o;}
  function names(ids){return ids.map(function(i){return D.nodes[i].label;}).join(' → ');}

  function debrief(){
    var got=answered(), n=got.length, spent=total-left, tot=D.goals.length;
    var h='<h3 tabindex="-1">What your investigation bought</h3>';
    h+='<p class="ac-rcshort">You answered <strong>'+n+'</strong> of '+tot+
       ' sub-questions, and spent <strong>'+spent+'</strong> of '+total+' '+D.unit+'.</p>';
    var ch=D.cheapest[String(n)];
    if(n&&ch){
      h+='<p>The cheapest route to '+n+(n===1?' answer':' answers')+' is <strong>'+ch.cost+
         '</strong> '+D.unit+': '+names(ch.route)+'.'+
         (spent>ch.cost?' You spent '+(spent-ch.cost)+' more than that.':
          (spent===ch.cost?' That is exactly what you spent — you took the shortest way there.':''))+
         '</p>';
    }
    if(n<D.best.goals){
      h+='<p>This budget allows up to <strong>'+D.best.goals+'</strong> answers, for '+
         D.best.cost+' '+D.unit+': '+names(D.best.route)+'.</p>';
    }else if(n===D.best.goals){
      h+='<p>That is the most this budget allows. Everything beyond it costs more than the '+
         'budget holds, which is the ordinary condition of research rather than a failure.</p>';
    }
    var unb=D.goals.filter(function(g){return D.unbuyable.indexOf(g.id)>=0;});
    if(unb.length){
      h+='<p class="ac-showslbl">What no amount of budget would have bought</p><ul class="ac-shows">'+
         unb.map(function(g){return '<li class="ac-no">'+g.q+'</li>';}).join('')+'</ul>';
    }
    var hit=D.rules.filter(function(r){
      return r.ran.every(function(i){return ran.indexOf(i)>=0;}) &&
             r['not'].every(function(i){return ran.indexOf(i)<0;});
    }).slice(0,4);
    if(hit.length) h+='<ul class="ac-rcrules">'+
      hit.map(function(r){return '<li>'+r.note+'</li>';}).join('')+'</ul>';
    var sup=[],non=[];
    ran.forEach(function(id){sup=sup.concat(D.nodes[id].conclude);
                             non=non.concat(D.nodes[id].cannot);});
    if(sup.length) h+='<p class="ac-showslbl">What your route supports</p><ul class="ac-shows">'+
      uniq(sup).map(function(t){return '<li class="ac-yes">'+t+'</li>';}).join('')+'</ul>';
    if(non.length) h+='<p class="ac-showslbl">What it still leaves open</p><ul class="ac-shows">'+
      uniq(non).map(function(t){return '<li class="ac-no">'+t+'</li>';}).join('')+'</ul>';
    var skipped=Object.keys(D.nodes).filter(function(id){return ran.indexOf(id)<0;});
    if(skipped.length) h+='<p class="ac-showslbl">The steps you did not take</p><ul class="ac-rcskip">'+
      skipped.map(function(id){var x=D.nodes[id];
        return '<li><span class="ac-rcskipn">'+x.label+'</span><span class="ac-rcskipc">'+
               x.cost+' '+D.unit+'</span><span class="ac-rcskipa">'+x.addresses+'</span></li>';
      }).join('')+'</ul>';
    deb.innerHTML=h; deb.hidden=false;
    var hh=deb.querySelector('h3'); if(hh&&hh.focus) hh.focus();
  }

  var closeBtn=step.querySelector('[data-rc-close]');
  if(closeBtn) closeBtn.addEventListener('click',function(){
    closed=true; closeBtn.disabled=true;
    if(pathBox) pathBox.hidden=true;
    paint(); debrief();
    track('investigation_closed',{spent:total-left,steps:ran.length,
                                  answers:answered().length});
  });
  var rb=step.querySelector('[data-rc-reset]');
  if(rb) rb.addEventListener('click',function(){
    left=total; ran=[]; cursor=null; closed=false;
    if(closeBtn) closeBtn.disabled=false;
    if(deb){deb.hidden=true;deb.innerHTML='';}
    paint();
  });
  paint();
})();
</script>
"""


QUIZ_JS = """
<script>
/* Academy mini-quiz. Same rules as the progress switch above: no storage, no
   score kept anywhere, no network. Answering marks the option you picked and
   the right one, and reveals WHY -- which is the part worth reading. Without
   JS every question still works: the <details> fallback below each question
   carries the answer and the same explanation, so the page is never a dead
   list of options. */
(function(){
  var qs=document.querySelectorAll('.ac-qz');
  if(!qs.length) return;
  var total=qs.length, answered=0, right=0;
  var tally=document.getElementById('acQzTally');
  qs.forEach(function(qz){
    var fall=qz.querySelector('.ac-qzfall');
    if(fall) fall.hidden=true;               /* JS is on -> feedback is inline */
    var why=qz.querySelector('.ac-qzwhy');
    var correct=parseInt(qz.getAttribute('data-answer'),10);
    var opts=qz.querySelectorAll('.ac-qzopt');
    opts.forEach(function(b){
      b.addEventListener('click',function(){
        if(qz.hasAttribute('data-done')) return;
        qz.setAttribute('data-done','1');
        var picked=parseInt(b.getAttribute('data-i'),10);
        var ok=picked===correct;
        opts.forEach(function(o){
          var i=parseInt(o.getAttribute('data-i'),10);
          o.setAttribute('aria-disabled','true');
          if(i===correct) o.setAttribute('data-mark','right');
          else if(i===picked) o.setAttribute('data-mark','wrong');
        });
        var v=qz.querySelector('.ac-qzverdict');
        if(v) v.textContent=ok?'Correct':'Not this one';
        if(why){why.hidden=false;}
        answered++; if(ok) right++;
        if(tally&&answered===total){
          tally.textContent=right+' of '+total+' first time. Nothing here is recorded '+
            '\u2014 the explanations are the point.';
        }
      });
    });
  });
})();
</script>
"""

EXERCISE_JS = """
<script>
/* Interaktivni cviceni (Faze 2). Stejny kontrakt jako kviz vys: stranka je
   uplna i bez tohohle skriptu. JS tady jen (a) prepina stav vyukoveho modelu,
   (b) sekvencuje Predict -> Observe -> Explain a (c) po odeslani navrhu
   experimentu ukaze jen relevantni zpetnou vazbu. Vsechny tri veci maji
   v HTML <details> ekvivalent, ktery se tady schova prave proto, ze uz je
   nahrazeny necim lepsim. Zadny fetch, zadne localStorage, zadne skore. */
(function(){
  /* ---------- interaktivni model ---------- */
  document.querySelectorAll('.ac-model').forEach(function(md){
    var dataEl=md.querySelector('script.ac-mddata'); if(!dataEl) return;
    var D; try{D=JSON.parse(dataEl.textContent);}catch(e){return;}
    var fall=md.querySelector('.ac-mdfall'); if(fall) fall.hidden=true;
    var pick={}, order=D.order||[];
    order.forEach(function(c){pick[c]=D.start[c];});
    var out=md.querySelector('.ac-mdreadout'), note=md.querySelector('.ac-mdnote');
    function key(){return order.map(function(c){return pick[c];}).join('|');}
    function paint(){
      var st=D.states[key()];
      md.querySelectorAll('.ac-mdbtns button').forEach(function(b){
        b.setAttribute('aria-pressed',String(pick[b.dataset.ctl]===b.dataset.val));
      });
      if(!st) return;
      var on={}; (st.flow||[]).forEach(function(n){on[n]=1;});
      md.querySelectorAll('.ac-mdnode').forEach(function(n){
        n.setAttribute('data-flow', on[n.dataset.node]?'on':'off');
      });
      var cut={}; (st.cut||[]).forEach(function(e){cut[e]=1;});
      md.querySelectorAll('.ac-mdedge').forEach(function(e){
        e.setAttribute('data-flow', cut[e.dataset.edge]?'off':'on');
      });
      if(out) out.textContent=st.readout||'';
      if(note) note.innerHTML=st.note||'';
    }
    md.querySelectorAll('.ac-mdbtns button').forEach(function(b){
      b.addEventListener('click',function(){pick[b.dataset.ctl]=b.dataset.val;paint();});
    });
    var rst=md.querySelector('.ac-mdreset');
    if(rst) rst.addEventListener('click',function(){
      order.forEach(function(c){pick[c]=D.start[c];}); paint();
    });
    /* uzel -> zvyrazni jeho radek v legende (legenda je vzdy videt, nic se
       neschovava -- zvyrazneni je navigace, ne odhaleni) */
    /* Pozor: uzel je SVG <g>, ktere NEMA .click() -- volat ho z klavesnice
       tise spadne (stejna past uz jednou byla v Entity Browseru). Proto je
       zvyrazneni funkce a klavesnice i mys volaji ji, ne se navzajem. */
    function highlight(id){
      md.querySelectorAll('.ac-mdkey div').forEach(function(r){
        r.setAttribute('data-hi', r.dataset.node===id?'1':'0');
      });
    }
    md.querySelectorAll('.ac-mdnode').forEach(function(n){
      n.addEventListener('click',function(){highlight(n.dataset.node);});
      n.addEventListener('keydown',function(ev){
        if(ev.key==='Enter'||ev.key===' '){ev.preventDefault();highlight(n.dataset.node);}
      });
    });
    paint();
  });

  /* ---------- Predict -> Observe -> Explain ---------- */
  document.querySelectorAll('.ac-pd').forEach(function(pd){
    var fall=pd.querySelector('.ac-pdfall'); if(fall) fall.hidden=true;
    var after=pd.querySelectorAll('[data-ac-after]');
    after.forEach(function(x){x.hidden=true;});
    var correct=parseInt(pd.getAttribute('data-answer'),10);
    var opts=pd.querySelectorAll('.ac-qzopt');
    opts.forEach(function(b){
      b.addEventListener('click',function(){
        if(pd.hasAttribute('data-done')) return;
        pd.setAttribute('data-done','1');
        var picked=parseInt(b.getAttribute('data-i'),10);
        opts.forEach(function(o){
          var i=parseInt(o.getAttribute('data-i'),10);
          o.setAttribute('aria-disabled','true');
          if(i===correct) o.setAttribute('data-mark','right');
          else if(i===picked) o.setAttribute('data-mark','wrong');
        });
        var v=pd.querySelector('.ac-qzverdict');
        if(v) v.textContent=(picked===correct)?'That is the expected result':'Not the expected result';
        after.forEach(function(x){x.hidden=false;});
      });
    });
  });

  /* ---------- experiment builder ---------- */
  document.querySelectorAll('.ac-design').forEach(function(ds){
    var fall=ds.querySelector('.ac-dsfall'); if(fall) fall.hidden=true;
    var box=ds.querySelector('.ac-dsfb'); if(box) box.hidden=true;
    var btn=ds.querySelector('.ac-dssubmit');
    if(!btn||!box) return;
    var notes; try{notes=JSON.parse(ds.querySelector('script.ac-dsdata').textContent);}
    catch(e){return;}
    btn.addEventListener('click',function(){
      var chosen=[];
      ds.querySelectorAll('input[type=radio]:checked').forEach(function(r){
        chosen.push([r.name,r.value]);
      });
      if(!chosen.length) return;
      var html='';
      chosen.forEach(function(p){
        var t=notes[p[0]]&&notes[p[0]][p[1]];
        if(t) html+='<p><strong>'+p[1]+'.</strong> '+t+'</p>';
      });
      box.querySelector('.ac-dsout').innerHTML=html;
      box.hidden=false;
      box.querySelector('h4').focus&&box.querySelector('h4').focus();
    });
  });
})();
</script>
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


# Klice v lekci, ktere se resolvuji na stranky entit. Poradi urcuje poradi
# chipu v "Go deeper" -- molekuly, pak kontext (latka, nemoc, vysledek).
ENTITY_KEYS = ("proteins", "pathways", "processes", "organelles", "nutrients",
               "drugs", "diseases", "outcomes")


def deeper_links(les, ent_url, gaps):
    """Chipy "Go deeper". VZDY jen na entity, ktere maji vlastni stranku --
    jmeno bez stranky se tise preskoci a nahlasi do konzole, nikdy nevznikne
    mrtvy odkaz."""
    chips, missing = [], []
    for key in ENTITY_KEYS:
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

QZ_KEYS = "ABCD"
QZ_LEVEL = {"easy": "Warm-up", "medium": "Step up", "hard": "Harder"}


def quiz_block(les):
    """Tri otazky, lehka -> tezka. Data se validuji uz ve verify_academy.py;
    tady se jen kresli. Odpoved je v data-answer, protoze fallback <details>
    ji stejne ukazuje -- tohle neni zkouska, ale kontrola porozumeni."""
    qz = les.get("quiz") or []
    if not qz:
        return ""
    out = ['<section class="ac-section"><h2 id="quiz">Check yourself</h2>',
           "<p>Three questions, easiest first. Nothing is recorded and there is no "
           "pass mark &mdash; the explanation after each answer is the part worth "
           "reading.</p>", '<div class="ac-quiz">']
    for i, q in enumerate(qz):
        lvl = QZ_LEVEL.get(q.get("level"), "Question")
        out.append('<div class="ac-qz" data-answer="%d">' % q["answer"])
        out.append('<p class="ac-qzq"><span class="ac-qzn">Question %d &middot; %s</span>%s</p>'
                   % (i + 1, e(lvl), prose(q["prompt"])))
        out.append('<ul class="ac-qzopts" role="group" aria-label="Answer options">')
        for j, opt in enumerate(q["options"]):
            out.append('<li><button type="button" class="ac-qzopt" data-i="%d">'
                       '<span class="ac-qzkey">%s</span><span>%s</span></button></li>'
                       % (j, QZ_KEYS[j], prose(opt)))
        out.append("</ul>")
        out.append('<p class="ac-qzwhy" hidden><span class="ac-qzverdict"></span>%s</p>'
                   % prose(q["explain"]))
        # Fallback bez JS: stejna informace, jen na kliknuti do <details>.
        out.append('<details class="ac-qzfall"><summary>Show the answer</summary>'
                   '<p><strong>%s.</strong> %s</p></details>'
                   % (e("%s \u2014 %s" % (QZ_KEYS[q["answer"]], TAG_RE.sub("", q["options"][q["answer"]]))),
                      prose(q["explain"])))
        out.append("</div>")
    out.append('<p class="ac-qztally" id="acQzTally"></p></div></section>')
    return "".join(out)


# ------------------------------------------------------------- exercises ---
#
# Sest typu interaktivnich cviceni (Faze 2 spec §3). Spolecny kontrakt:
#   1. cely vedecky obsah je v HTML, i kdyz ho ctenar hned nevidi
#   2. bez JS to funguje pres <details> -- pravidlo 13 ve verify_academy.py
#   3. data drzi jen ID (SID studie, id uzlu/hrany v pathway/model.json,
#      slug open question); nazvy, znamenka a evidence se resolvuji tady
#
# Zadny simulator: stavy interaktivniho modelu jsou VYJMENOVANE v datech.
# Tri binarni prepinace = nejvys osm stavu, ktere jde precist a zrevidovat.

EX_LABEL = {
    "model": "Interactive model",
    "predict": "Predict &rarr; observe &rarr; explain",
    "compare": "Compare the evidence",
    "caution": "Scientific caution",
    "openq": "Open question",
    "design": "Design an experiment",
}


def _pw_node(pw, nid):
    n = pw["nodes"].get(nid)
    if not n:
        raise SystemExit("build_academy: uzel %r neni v pathway/model.json "
                         "-- vyukovy model se nesmi rozejit s vedeckym" % nid)
    return n


def _levels(explain):
    """Tri urovne vysvetleni z model.json -> tri bloky, prepina je CSS
    (data-level na <html>), ne JS. Student je kanonicky a jediny viditelny
    bez prepnuti -- viz chrome_shared.LEVEL_SWITCH_CSS."""
    out = []
    for cls, key in (("lv-student", "student"), ("lv-beginner", "beginner"),
                     ("lv-research", "research")):
        txt = (explain or {}).get(key) or (explain or {}).get("student") or ""
        if txt:
            out.append('<span class="%s">%s</span>' % (cls, e(txt)))
    return "".join(out)


def model_block(ex, pw, ent_url):
    """Interaktivni schema. `layout` je seznam sloupcu s ID uzlu z model.json;
    souradnice pocita generator, data zadne pixely nedrzi."""
    cols = ex["layout"]
    COLW, GAP, NH, NGAP, TOP = 132, 46, 34, 16, 30
    step = COLW + GAP
    heights = [len(c) * NH + (len(c) - 1) * NGAP for c in cols]
    tallest = max(heights)
    pos = {}
    g = []
    for i, col in enumerate(cols):
        x = 4 + i * step
        y0 = TOP + (tallest - heights[i]) / 2.0
        for j, nid in enumerate(col):
            y = y0 + j * (NH + NGAP)
            pos[nid] = (x, y, COLW, NH)
            node = _pw_node(pw, nid)
            label = ex.get("labels", {}).get(nid) or node.get("label") or nid
            g.append('<g class="ac-mdnode" data-node="%s" tabindex="0" role="button" '
                     'aria-label="%s"><rect x="%d" y="%.0f" width="%d" height="%d" rx="3"/>'
                     '<text x="%.0f" y="%.0f">%s</text></g>'
                     % (e(nid), e("%s — show explanation" % label), x, y, COLW, NH,
                        x + COLW / 2.0, y + NH / 2.0 + 4, e(label)))
    # hrany: jen ty, ktere v modelu SKUTECNE existuji
    edges = []
    listed = ex.get("edges")
    if listed:
        for eid in listed:
            it = pw["edges"].get(eid)
            if not it:
                raise SystemExit("build_academy: hrana %r neni v pathway/model.json" % eid)
            if it["source"] not in pos or it["target"] not in pos:
                raise SystemExit("build_academy: hrana %r vede mimo uzly modelu" % eid)
            edges.append(it)
    else:
        # Bez vyjmenovanych hran kresli jen mezi SOUSEDNIMI sloupci. Model zna
        # i korektni zkratky (TSC1/TSC2 -> mTORC1 je v nem jako indirect), ale
        # ve vyukovem schematu by vedly pres uzel, ktery prave vysvetlujeme.
        # Vynechana hrana je zjednoduseni, ne oprava modelu -- proto se dá
        # kdykoli doplnit vyctem `edges`.
        for i in range(len(cols) - 1):
            for a in cols[i]:
                for b in cols[i + 1]:
                    it = pw["pairs"].get((a, b))
                    if it:
                        edges.append(it)
    # Zpetna hrana (cil je vlevo od zdroje) se vede POD schematem a vraci se
    # nahoru do spodni hrany cile. Bez toho by smycka -- v lekci 08 cela pointa
    # -- vypadala jako sipka kreslena pozpatku pres pul obrazku.
    back = 0
    for it in edges:
        a, b = pos.get(it["source"]), pos.get(it["target"])
        if not a or not b:
            continue
        inhib = it.get("effect") == "inhibits"
        if b[0] < a[0]:
            back += 1
            lane = TOP + tallest + 14 + (back - 1) * 14
            xa, ya = a[0] + a[2] / 2.0, a[1] + a[3]
            xb, yb = b[0] + b[2] / 2.0, b[1] + b[3]
            d = "M%.0f %.0f V%.0f H%.0f V%.0f" % (xa, ya, lane, xb, yb + 12)
            g.append('<path class="ac-mdedge ac-mdback" data-edge="%s" data-eff="%s" d="%s"%s/>'
                     % (e(it["id"]), e(it.get("effect") or ""), d,
                        "" if inhib else ' marker-end="url(#acArrow)"'))
            if inhib:
                g.append('<path class="ac-mdedge" data-edge="%s" data-eff="inhibits" '
                         'd="M%.0f %.0f H%.0f"/>' % (e(it["id"]), xb - 9, yb + 12, xb + 9))
            continue
        x1, y1 = a[0] + a[2], a[1] + a[3] / 2.0
        x2, y2 = b[0], b[1] + b[3] / 2.0
        mid = (x1 + x2) / 2.0
        d = ("M%.0f %.0f H%.0f" % (x1, y1, x2 - 10)) if abs(y1 - y2) < 1 else \
            ("M%.0f %.0f H%.0f V%.0f H%.0f" % (x1, y1, mid, y2, x2 - 10))
        g.append('<path class="ac-mdedge" data-edge="%s" data-eff="%s" d="%s"%s/>'
                 % (e(it["id"]), e(it.get("effect") or ""), d,
                    "" if inhib else ' marker-end="url(#acArrow)"'))
        if inhib:
            g.append('<path class="ac-mdedge" data-edge="%s" data-eff="inhibits" '
                     'd="M%.0f %.0f V%.0f"/>' % (e(it["id"]), x2 - 10, y2 - 9, y2 + 9))
    height = TOP + tallest + 26 + back * 14
    width = 4 + len(cols) * step
    # Sirku resi dve cisla odvozena z viewBoxu, ne pevne CSS: maly model
    # (dva sloupce) by se jinak roztahl pres cely sloupec textu a uzly by
    # byly dvakrat vetsi nez v sousednim schematu; a min-width pro vodorovny
    # scroll na mobilu nesmi byt vetsi nez model sam, jinak by scrolloval
    # neco, co se veslo.
    svg = ('<div class="ac-mdscroll"><svg viewBox="0 0 %d %.0f" class="ac-mdsvg" '
           'style="max-width:%dpx;min-width:%dpx" role="img" aria-label="%s">%s</svg></div>'
           % (width, height, int(width * 1.4), min(560, width),
              e(TAG_RE.sub("", ex["caption"])), "".join(g)))

    # ovladace
    ctl = []
    for c in ex["controls"]:
        btns = "".join('<button type="button" data-ctl="%s" data-val="%s">%s</button>'
                       % (e(c["id"]), e(v), e(v)) for v in c["options"])
        ctl.append('<div class="ac-mdgrp"><span id="acmd-%s">%s</span>'
                   '<div class="ac-mdbtns" role="group" aria-labelledby="acmd-%s">%s</div></div>'
                   % (e(c["id"]), e(c["label"]), e(c["id"]), btns))

    order = [c["id"] for c in ex["controls"]]
    start = ex["start"]
    start_key = "|".join(start[c] for c in order)
    st0 = ex["states"][start_key]

    # legenda: vzdy viditelna, tri urovne pres CSS, odkaz do Atlasu kde existuje
    rows = []
    for nid in [n for col in cols for n in col]:
        node = _pw_node(pw, nid)
        label = ex.get("labels", {}).get(nid) or node.get("label") or nid
        hit = ent_url.get(nid.lower())
        head = ('<a href="%s">%s</a>' % (hit[0], e(label))) if hit else e(label)
        rows.append('<div data-node="%s"><dt>%s</dt><dd>%s</dd></div>'
                    % (e(nid), head, _levels(node.get("explain"))))

    # bez-JS ekvivalent: tabulka vsech stavu
    fall = ['<details class="ac-mdfall"><summary>Every state of this model</summary>'
            '<div class="ac-cmpwrap"><table class="ac-cmp"><tr>']
    for c in ex["controls"]:
        fall.append("<th>%s</th>" % e(c["label"]))
    fall.append("<th>Readout</th><th>What it means</th></tr>")
    for k, st in ex["states"].items():
        fall.append("<tr>")
        for v in k.split("|"):
            fall.append("<td>%s</td>" % e(v))
        fall.append("<td>%s</td><td>%s</td></tr>"
                    % (e(st.get("readout") or ""), prose(st.get("note") or "")))
    fall.append("</table></div></details>")

    data = {"order": order, "start": start,
            "states": {k: {"flow": v.get("flow") or [], "cut": v.get("cut") or [],
                           "readout": v.get("readout") or "",
                           # note jde do stranky jako HTML (entity + povolena
                           # inline sada) -- proto prose(), ktera whitelist
                           # vynuti uz pri buildu, a v JS innerHTML.
                           "note": prose(v.get("note") or "")}
                       for k, v in ex["states"].items()}}

    return ('<div class="ac-model">%s<div class="ac-mdctl">%s</div>%s'
            '<p class="ac-mdcap">%s</p>'
            '<div class="ac-mdout"><p class="ac-mdreadout">%s</p>'
            '<p class="ac-mdnote">%s</p></div>'
            '<button type="button" class="ac-mdreset">Reset the model</button>'
            '<dl class="ac-mdkey">%s</dl>'
            '<p class="ac-mdteach">%s</p>%s'
            '<script type="application/json" class="ac-mddata">%s</script></div>'
            % (SVG_DEFS, "".join(ctl), svg, prose(ex["caption"]),
               e(st0.get("readout") or ""), prose(st0.get("note") or ""),
               "".join(rows),
               "This is a simplified teaching model with a fixed set of states, not a "
               "simulation. It shows the direction each control pushes the pathway, not "
               "how much, how fast, or what any particular cell would do.",
               "".join(fall),
               json.dumps(data, ensure_ascii=False).replace("</", "<\\/")))


def shows_list(shows, nots):
    out = []
    if shows:
        out.append('<p class="ac-showslbl">What this evidence supports</p><ul class="ac-shows">')
        out += ['<li class="ac-yes">%s</li>' % prose(x) for x in shows]
        out.append("</ul>")
    if nots:
        out.append('<p class="ac-showslbl">What it does not establish</p><ul class="ac-shows">')
        out += ['<li class="ac-no">%s</li>' % prose(x) for x in nots]
        out.append("</ul>")
    return "".join(out)


def predict_block(ex, by_sid):
    sid = ex["observe"]["sid"]
    st = by_sid.get(sid)
    if not st:
        raise SystemExit("build_academy: predict cviceni odkazuje na neznamy SID %r" % sid)
    code, _lab, colour = tier_bits(st.get("tier"))
    opts = "".join(
        '<li><button type="button" class="ac-qzopt" data-i="%d">'
        '<span class="ac-qzkey">%s</span><span>%s</span></button></li>'
        % (i, QZ_KEYS[i], prose(o)) for i, o in enumerate(ex["options"]))
    observe = (
        '<span class="ac-pdstep">Observe &mdash; what was actually measured</span>'
        '<div class="ac-pdobs"><div class="ac-evhead">'
        '<span class="tier" style="background:%s">%s</span>'
        '<a class="ac-evtitle" href="%s/study/%s/">%s</a>'
        '<span class="ac-evyear">%s</span></div>'
        '<p class="ac-pdmethod">%s</p><p class="ac-pdreadout">%s</p>'
        '<a class="ac-evlink" href="%s/study/%s/">Study page &rarr;</a></div>'
        % (colour, e(code), SITE, e(sid), e(st.get("title") or sid), e(st.get("year") or ""),
           prose(ex["observe"]["method"]), prose(ex["observe"]["readout"]),
           SITE, e(sid)))
    explain = ('<span class="ac-pdstep">Explain</span><p>%s</p>%s'
               % (prose(ex["explain"]), shows_list(ex.get("shows"), ex.get("doesNotShow"))))
    fall = ('<details class="ac-pdfall"><summary>Show the expected answer</summary>'
            '<p><strong>%s.</strong> %s</p>%s%s</details>'
            % (e(QZ_KEYS[ex["answer"]]), prose(ex["options"][ex["answer"]]), observe, explain))
    return ('<div class="ac-pd" data-answer="%d">'
            '<span class="ac-pdstep">Predict &mdash; commit before you look</span>'
            '<p>%s</p><ul class="ac-qzopts" role="group" aria-label="Predictions">%s</ul>'
            '<p class="ac-qzwhy" hidden><span class="ac-qzverdict"></span></p>'
            '<div data-ac-after>%s%s</div>%s</div>'
            % (ex["answer"], prose(ex["prompt"]), opts, observe, explain, fall))


def compare_block(ex, by_sid):
    cells = []
    for side in ("a", "b"):
        sid = ex[side]["sid"]
        st = by_sid.get(sid)
        if not st:
            raise SystemExit("build_academy: compare cviceni odkazuje na neznamy SID %r" % sid)
        code, _l, colour = tier_bits(st.get("tier"))
        cells.append({
            "head": '<span class="tier" style="background:%s">%s</span> '
                    '<a class="ac-evtitle" href="%s/study/%s/">%s</a>'
                    % (colour, e(code), SITE, e(sid), e(st.get("title") or sid)),
            "model": e(st.get("model") or "—"),
            "pert": prose(ex[side]["perturbation"]),
            "read": prose(ex[side]["readout"])})
    rows = [("", cells[0]["head"], cells[1]["head"]),
            ("Model system", cells[0]["model"], cells[1]["model"]),
            ("Perturbation", cells[0]["pert"], cells[1]["pert"]),
            ("Readout", cells[0]["read"], cells[1]["read"])]
    tbl = "".join('<tr><th>%s</th><td>%s</td><td>%s</td></tr>' % r for r in rows)
    return ('<div class="ac-cmpwrap"><table class="ac-cmp">%s</table></div>'
            '<details><summary>What do both studies support?</summary><p>%s</p></details>'
            '<details><summary>Where do they differ?</summary><p>%s</p></details>'
            '<details><summary>What experiment would help next?</summary><p>%s</p></details>'
            % (tbl, prose(ex["bothSupport"]), prose(ex["differ"]),
               prose(ex["nextExperiment"])))


def caution_block(ex):
    why = ('<details><summary>Why?</summary><p>%s</p></details>' % prose(ex["why"])) \
        if ex.get("why") else ""
    return shows_list(ex.get("shows"), ex.get("doesNotShow")) + why


def openq_block(ex, gaps, by_sid):
    slug = ex["slug"]
    if slug not in gaps:
        raise SystemExit("build_academy: openq cviceni ma neznamy slug %r" % slug)
    parts = [('<p><a href="%s/question/%s/">%s</a></p>' % (SITE, slug, e(gaps[slug])))]
    for label, key in (("What we know", "whatWeKnow"),
                       ("What we don't know", "whatWeDont"),
                       ("Competing interpretations", "competing"),
                       ("What would resolve this?", "wouldResolve")):
        v = ex.get(key)
        if not v:
            continue
        body = ("".join("<p>%s</p>" % prose(x) for x in v) if isinstance(v, list)
                else "<p>%s</p>" % prose(v))
        parts.append('<details><summary>%s</summary>%s</details>' % (e(label), body))
    if ex.get("sids"):
        parts.append('<details><summary>Supporting studies</summary>%s</details>'
                     % evidence_cards(ex["sids"], by_sid))
    return "".join(parts)


def design_block(ex, by_sid):
    groups, notes = [], {}
    for dim in ex["dimensions"]:
        opts = []
        notes[dim["id"]] = {}
        for o in dim["options"]:
            opts.append('<label class="ac-dsopt"><input type="radio" name="%s" value="%s">'
                        '<span>%s</span></label>'
                        % (e(dim["id"]), e(o["label"]), e(o["label"])))
            notes[dim["id"]][o["label"]] = TAG_RE.sub("", o["note"])
        groups.append('<fieldset class="ac-dsgrp"><legend>%s</legend>%s</fieldset>'
                      % (e(dim["label"]), "".join(opts)))
    fall = ['<details class="ac-dsfall"><summary>See the feedback on every choice</summary>']
    for dim in ex["dimensions"]:
        fall.append('<p class="ac-showslbl">%s</p>' % e(dim["label"]))
        for o in dim["options"]:
            fall.append("<p><strong>%s.</strong> %s</p>" % (e(o["label"]), prose(o["note"])))
    fall.append("</details>")
    lim = ('<p class="ac-showslbl">What no version of this design can establish</p>'
           '<ul class="ac-shows">%s</ul>'
           % "".join('<li class="ac-no">%s</li>' % prose(x) for x in ex["limitations"]))
    studies = evidence_cards(ex["sids"], by_sid) if ex.get("sids") else ""
    return ('<div class="ac-design"><p>%s</p><div class="ac-dsgrid">%s</div>'
            '<button type="button" class="ac-cta ac-quiet ac-dssubmit">Submit design</button>'
            '<div class="ac-dsfb" hidden><h4 tabindex="-1">Feedback on your design</h4>'
            '<div class="ac-dsout"></div></div>%s%s%s'
            '<script type="application/json" class="ac-dsdata">%s</script></div>'
            % (prose(ex["question"]), "".join(groups), "".join(fall), lim, studies,
               json.dumps(notes, ensure_ascii=False).replace("</", "<\\/")))


def exercise_html(ex, ctx):
    kind = ex["kind"]
    if kind == "model":
        return model_block(ex, ctx["pw"], ctx["ent_url"])
    if kind == "predict":
        return predict_block(ex, ctx["by_sid"])
    if kind == "compare":
        return compare_block(ex, ctx["by_sid"])
    if kind == "caution":
        return caution_block(ex)
    if kind == "openq":
        return openq_block(ex, ctx["gaps"], ctx["by_sid"])
    if kind == "design":
        return design_block(ex, ctx["by_sid"])
    raise SystemExit("build_academy: neznamy typ cviceni %r" % kind)


def exercise_card(ex, ctx):
    return ('<div class="ac-ex" id="ex-%s"><span class="ac-exkind">%s</span>'
            '<h3>%s</h3>%s</div>'
            % (e(ex["id"]), EX_LABEL[ex["kind"]], e(ex["title"]), exercise_html(ex, ctx)))


def lesson_page(les, module, lessons_by_slug, by_sid, ent_url, routes, gaps, pw):
    slug = les["slug"]
    url = "%s/academy/%s/%s/" % (SITE, module["slug"], slug)
    ctx = {"by_sid": by_sid, "ent_url": ent_url, "gaps": gaps, "pw": pw}
    ex_by_id = {x["id"]: x for x in les.get("exercises") or []}
    # Cviceni citovane ze sekce (`"interactive": "<id>"`) se vykresli PRIMO
    # v te sekci -- model patri k mechanismu, ne za nej. Zbytek jde do bloku
    # "Work through it" mezi Evidence a Think, v poradi, v jakem je v datech.
    inline_ids = {sec["interactive"] for sec in les["sections"] if sec.get("interactive")}
    work = [x for x in les.get("exercises") or [] if x["id"] not in inline_ids]
    title = les["title"]
    desc = ("%s %s" % (TAG_RE.sub("", les["question"]), TAG_RE.sub("", les["coreIdea"][0])))[:300]

    # --- section anchors for the rail
    secs = [("question", "The question"), ("idea", "The core idea")]
    for i, s in enumerate(les["sections"]):
        secs.append(("s%d" % i, s["heading"]))
    secs.append(("evidence", "What does the evidence say?"))
    if work:
        secs.append(("work", "Work through it"))
    secs.append(("think", "Think"))
    if les.get("quiz"):
        secs.append(("quiz", "Check yourself"))
    secs.append(("deeper", "Go deeper"))

    body = [SVG_DEFS, '<div class="ac-lesson"><article class="ac-main">']
    body.append('<p class="ac-eyebrow">%s &middot; Lesson %s &middot; %s &middot; %d min</p>'
                % (e(module["title"]), e(les["id"][1:]), e(les["level"]), les["estimatedTime"]))
    body.append("<h1>%s</h1>" % e(title))
    body.append('<p class="meta">%s</p>' % e(les["subtitle"]))
    body.append('<h2 id="question" class="ac-vh">The question</h2>'
                '<p class="ac-q">%s</p>' % prose(les["question"]))

    if les.get("learningObjectives"):
        # Spec Faze 2 §12: konkretni vysledky, aktivnimi slovesy. Neni to
        # dekorace -- verify_academy.py kontroluje, ze zadny nezacina slovesem
        # typu "understand"/"know", ktere nejde zkontrolovat ani ucit.
        body.append('<section class="ac-section ac-obj"><h2 id="objectives" class="ac-vh">'
                    'What you should be able to do</h2>'
                    '<p class="ac-objlbl">After this lesson you should be able to</p>'
                    '<ul class="ac-objlist">%s</ul>%s</section>'
                    % ("".join("<li>%s</li>" % prose(x) for x in les["learningObjectives"]),
                       ('<p class="ac-skill"><span>Research skill</span> %s</p>'
                        % e(les["researchSkill"])) if les.get("researchSkill") else ""))
        secs.insert(1, ("objectives", "What you should be able to do"))

    body.append('<section class="ac-section ac-idea"><h2 id="idea">The core idea</h2>%s</section>'
                % levelled(les["coreIdea"], les.get("coreIdeaBeginner")))

    for i, s in enumerate(les["sections"]):
        cls = "ac-section" + (" ac-cautionsec" if s["kind"] == "caution" else "")
        inner = ""
        if s.get("figure"):
            if s["figure"] not in FIGURES:
                raise SystemExit("build_academy: neznamy figure %r" % s["figure"])
            inner += FIGURES[s["figure"]]()
        if s["kind"] == "caution":
            # Vedoma vyjimka: co evidence NEUKAZUJE, vidi kazda uroven stejne.
            # Zkratit zacatecnikovi text je v poradku; zkratit mu vyhrady ne.
            inner += paras(s["body"], "ac-note")
        else:
            inner += levelled(s["body"], s.get("bodyBeginner"))
        if s.get("interactive"):
            if s["interactive"] not in ex_by_id:
                raise SystemExit("build_academy: sekce odkazuje na neexistujici cviceni %r"
                                 % s["interactive"])
            inner += exercise_card(ex_by_id[s["interactive"]], ctx)
        body.append('<section class="%s"><h2 id="s%d">%s</h2>%s</section>'
                    % (cls, i, e(s["heading"]), inner))

    body.append('<section class="ac-section"><h2 id="evidence">What does the evidence say?</h2>')
    body.append("<p>These are Atlas studies, with the Atlas's own evidence tier. "
                "Each card links to the full record — nothing here restates it.</p>")
    body.append(evidence_cards(les["studies"], by_sid))
    if les.get("uncertainty"):
        body.append('<p class="ac-note">%s</p>' % prose(les["uncertainty"]))
    body.append("</section>")

    if work:
        body.append('<section class="ac-section"><h2 id="work">Work through it</h2>')
        body.append("<p>Each of these asks you to commit to something &mdash; a prediction, "
                    "a reading of two studies, a design &mdash; before it answers. "
                    "Everything here is in the page, so nothing is lost if you would "
                    "rather just read it.</p>")
        for x in work:
            body.append(exercise_card(x, ctx))
        body.append("</section>")

    body.append('<section class="ac-section"><h2 id="think">Think</h2>')
    for j, t in enumerate(les["thinkQuestions"]):
        body.append('<div class="ac-think"><p class="ac-prompt">%s</p>' % prose(t["prompt"]))
        if t.get("hint"):
            body.append('<p class="ac-hint">%s</p>' % prose(t["hint"]))
        body.append('<details><summary>Think first, then reveal</summary>'
                    '<p class="ac-reveal">%s</p></details></div>' % prose(t["reveal"]))
    body.append("</section>")

    body.append(quiz_block(les))

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

    crumb = ('<a href="%s/">Oliver\'s mTOR Atlas</a> · <a href="%s/academy/">Academy</a> · '
             '<a href="%s/academy/%s/">%s</a> · %s'
             % (SITE, SITE, SITE, module["slug"], e(module["title"]), e(title)))

    # --- SEO P0 Ukol 6.1 (2026-09-02): Bioschemas TrainingMaterial ---
    ld = {
        "@context": "https://schema.org",
        "@type": ["LearningResource", "TrainingMaterial"],
        "name": title, "headline": title, "url": url, "inLanguage": "en",
        "educationalLevel": les["level"],
        "learningResourceType": "e-learning",
        "timeRequired": "PT%dM" % les["estimatedTime"],
        "teaches": les.get("concepts") or [],
        "keywords": les.get("concepts") or [],
        "audience": {"@type": "Audience",
                     "audienceType": "students and self-directed learners with a "
                                     "basic biology background"},
        "isPartOf": {"@type": "Course", "name": "%s — mTOR Academy" % module["title"],
                     "url": "%s/academy/%s/" % (SITE, module["slug"])},
        "about": dict(DATASET_REF),
        "author": {"@type": "Person", "name": "Oliver Barton", "url": "https://orcid.org/0009-0008-2025-2148", "sameAs": ["https://orcid.org/0009-0008-2025-2148"]},
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
                 extra_body=PROGRESS_JS + (QUIZ_JS if les.get("quiz") else "")
                            + (EXERCISE_JS if les.get("exercises") else ""),
                 level_switch=bool(les.get("exercises") or les.get("coreIdeaBeginner")))
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
    # Poznamka o planovanych lekcich se ukaze, jen kdyz nejaka planovana je.
    # Jinak by stranka varovala pred necim, co na ni neni (od 2026-08-30 je
    # publikovanych vsech deset).
    if any(r["status"] != "published" for r in module["lessons"]):
        body.append('<p class="ac-note">Lessons marked <em>in preparation</em> are listed so '
                    'the shape of the course is visible. They are not written yet, and this '
                    'page will not pretend otherwise.</p>')
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
    crumb = ('<a href="%s/">Oliver\'s mTOR Atlas</a> · <a href="%s/academy/">Academy</a> · %s'
             % (SITE, SITE, e(module["title"])))
    return url, shell("%s | mTOR Academy | Oliver's mTOR Atlas" % module["title"],
                      module["description"][:300], url, [ld, bc], "".join(body), crumb,
                      active_tab="learn", extra_css=ACADEMY_CSS, extra_body=PROGRESS_JS)


def academy_home(modules, lessons_by_slug, challenges):
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
    # Spec Research Challenges §2: existujici polozka na homepage prestava byt
    # "coming soon" a dostane skutecny cil. Karta se ridi daty -- kdyz
    # challenges.json zmizi, vrati se puvodni chovani.
    if os.path.exists(os.path.join(ADATA, "practice.json")):
        body.append('<div class="ac-card"><h3>Practice Arena</h3><p>Short games built on the same '
                    'pathway model the lessons draw from: predict a perturbation, rebuild a '
                    'route, name what a result does not show. Your answers colour in a map of '
                    'the pathway.</p>'
                    '<a class="ac-go" href="%s/academy/practice/">Practise &rarr;</a></div>'
                    % SITE)

    pub_ch = [c for c in challenges if c["status"] == "published"]
    if pub_ch:
        body.append('<div class="ac-card"><h3>Research Challenges</h3><p>Take a question '
                    'the field has not closed, commit to a hypothesis, spend a limited '
                    'research budget on experiments, and compare your reasoning with what '
                    'was actually published.</p>'
                    '<a class="ac-go" href="%s/academy/research-challenges/">Investigate '
                    '&rarr;</a></div>' % SITE)
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
                '<a href="%s/#view=questions">Open questions</a>'
                '<a href="%s/academy/progress/">Your pathway</a></div>'
                % (SITE, SITE, SITE, SITE, SITE, SITE))

    ld = {"@context": "https://schema.org", "@type": "CollectionPage",
          "name": "mTOR Academy", "url": url, "inLanguage": "en",
          "description": "A short course in mTOR biology built on the Atlas's own "
                         "evidence-graded literature: mechanisms first, evidence attached, "
                         "open questions kept visible.",
          "isPartOf": dict(DATASET_REF),
          "license": "https://creativecommons.org/licenses/by/4.0/"}
    bc = breadcrumb_ld([("Oliver's mTOR Atlas", SITE + "/"), ("Academy", None)])
    crumb = '<a href="%s/">Oliver\'s mTOR Atlas</a> · Academy' % SITE
    return url, shell("mTOR Academy | Oliver's mTOR Atlas",
                      "Learn the mechanisms of mTOR biology from the Atlas's own "
                      "evidence-graded studies: what mTOR integrates, why there are two "
                      "complexes, and how Rheb and the TSC complex control mTORC1.",
                      url, [ld, bc], "".join(body), crumb, active_tab="learn",
                      extra_css=ACADEMY_CSS, extra_body=PROGRESS_JS)


# --------------------------------------------------- research challenges ---
#
# Treti pilir Academy (spec Research Challenges v2). Learn odpovida "co vime",
# Guided Routes "jak to spolu souvisi", Research Challenges "co bys udelal dal".
#
# ENGINE, NE STRANKA. Vsechno na strance vyzvy se vykresluje z challenges.json;
# dalsi vyzva = dalsi zaznam v datech, zadny novy kod. Proto jsou kroky
# generovane ze seznamu, ne psane rucne za sebou.
#
# Tri veci, ktere tenhle modul dela jinak nez zbytek Academy:
#   1. ROZPOCET. Soucet nakladu experimentu MUSI prevysit rozpocet (brana 15),
#      takze student nemuze spustit vsechno a musi vybirat. Neni to skore --
#      zadny leaderboard, zadne XP, resetovat jde kdykoli.
#   2. ZADNA VYMYSLENA DATA. Vysledek experimentu je bud odvozeny ze skutecne
#      studie v korpusu (evidence.sids), nebo je oznaceny jako hypoteticky
#      (evidence.hypothetical) a stranka to rekne nahlas. Treti moznost brana
#      nepusti. Sloupce nesou kvalitativni uroven, nikdy vymyslene cislo.
#   3. ZADNE ZNAMKOVANI. U interpretaci a hypotez neni spravna odpoved; ke
#      kazde volbe je napsany komentar, co si tou volbou clovek bere s sebou.
#
# Parita bez JS plati stejne jako u cviceni: cely vedecky obsah je v HTML.
# JS jen (a) hlida rozpocet, (b) odkryva to, co uz na strance je, ve chvili,
# kdy se student rozhodl. Fallbacky nesou tridu ac-rcfall (brana 16).

# Sloupce vysledku. Kvalitativni uroven, ne cislo: presna cisla by byla
# vymyslena a spec §29 je zakazuje. Sirky jsou v procentech.
RC_BAR = {"none": 4, "low": 26, "mid": 58, "high": 100}
RC_BARLABEL = {"none": "none", "low": "low", "mid": "intermediate", "high": "high"}


def rc_optnotes(opts, label):
    """Seznam voleb + napsany komentar ke kazde. Bez JS je videt vsechno
    (proto ta hlavicka), s JS se odkryje jen zvolena -- stejny kontrakt jako
    Experiment Builder ve Fazi 2."""
    btns = "".join(
        '<li><button type="button" class="ac-qzopt" data-rc-opt="%d">'
        '<span class="ac-qzkey">%s</span><span>%s</span></button></li>'
        % (i, QZ_KEYS[i] if i < len(QZ_KEYS) else str(i + 1), prose(o["label"]))
        for i, o in enumerate(opts))
    notes = "".join('<p data-rc-note="%d"><strong>%s.</strong> %s</p>'
                    % (i, e(o["label"]), prose(o.get("note") or ""))
                    for i, o in enumerate(opts))
    return ('<ul class="ac-qzopts" role="group" aria-label="%s">%s</ul>'
            '<div class="ac-rcnotes" data-rc-notes>'
            '<p class="ac-showslbl">What each choice commits you to</p>%s</div>'
            % (e(label), btns, notes))


def rc_predict(b):
    """Break-the-model: predikce s ocekavanou odpovedi. Neni to mereni --
    je to predpoved o VYUKOVEM modelu, a text to rika nahlas."""
    opts = "".join(
        '<li><button type="button" class="ac-qzopt" data-i="%d">'
        '<span class="ac-qzkey">%s</span><span>%s</span></button></li>'
        % (i, QZ_KEYS[i], prose(o)) for i, o in enumerate(b["options"]))
    fall = ('<details class="ac-rcfall"><summary>Show the expected answer</summary>'
            '<p><strong>%s.</strong> %s</p><p>%s</p></details>'
            % (e(QZ_KEYS[b["answer"]]), prose(b["options"][b["answer"]]),
               prose(b["explain"])))
    return ('<div class="ac-rcpd" data-answer="%d"><p>%s</p>'
            '<ul class="ac-qzopts" role="group" aria-label="Prediction">%s</ul>'
            '<p class="ac-qzwhy" hidden><span class="ac-qzverdict"></span></p>'
            '<div data-ac-after><p>%s</p></div>%s</div>'
            % (b["answer"], prose(b["prompt"]), opts, prose(b["explain"]), fall))


def rc_result(ex, by_sid):
    """Vysledek experimentu. Bud skutecna studie, nebo oznacena predpoved --
    treti moznost neexistuje (brana 15)."""
    ev = ex["evidence"]
    if ev.get("hypothetical"):
        head = ('<p class="ac-rchypo"><span class="ac-rclbl">Expected, not observed'
                '</span> %s</p>'
                % prose(ev["basis"]))
    else:
        cards = []
        for sid in ev["sids"]:
            st = by_sid.get(sid)
            if not st:
                raise SystemExit("build_academy: experiment %r odkazuje na neznamy "
                                 "SID %r" % (ex["id"], sid))
            code, _l, colour = tier_bits(st.get("tier"))
            cards.append('<span class="tier" style="background:%s">%s</span> '
                         '<a href="%s/study/%s/">%s</a> <span class="ac-evyear">%s</span>'
                         % (colour, e(code), SITE, e(sid), e(st.get("title") or sid),
                            e(st.get("year") or "")))
        head = ('<p class="ac-rcsrc"><span class="ac-rclbl">Derived from</span> %s</p>'
                % " &middot; ".join(cards))

    res = ex["result"]
    bars = []
    for b in res["bars"]:
        lvl = b["level"]
        bars.append('<div class="ac-rcbarrow"><span class="ac-rcbarlbl">%s</span>'
                    '<span class="ac-rcbartrack"><span class="ac-rcbarfill" '
                    'style="width:%d%%"></span></span>'
                    '<span class="ac-rcbarval">%s</span></div>'
                    % (e(b["label"]), RC_BAR[lvl], e(RC_BARLABEL[lvl])))
    chart = ('<div class="ac-rcchart" role="img" aria-label="%s: %s">'
             '<p class="ac-rcunit">%s</p>%s</div>'
             % (e(res["unit"]),
                e("; ".join("%s %s" % (b["label"], RC_BARLABEL[b["level"]])
                            for b in res["bars"])),
                e(res["unit"]), "".join(bars)))

    lists = shows_list(ex.get("conclude"), ex.get("cannotConclude"))
    interp = ('<p class="ac-pdstep">Interpret &mdash; what does this let you say?</p>'
              '%s' % rc_optnotes(ex["interpret"], "Interpretation"))
    info = ('<p class="ac-rcinfo"><span class="ac-rclbl">Information value</span> %s</p>'
            % prose(ex["informative"]))
    return ('<div class="ac-rcout" data-rc-out>%s%s<p class="ac-mdcap">%s</p>%s%s%s</div>'
            % (head, chart, prose(res["caption"]), interp, lists, info))


def rc_node(n, by_sid, unit):
    """Karta jednoho kroku vyzkumu ve DVOU podobach v jednom kusu markupu.

    Puvodne to byla jedna dlouha rozbalena karta a moznosti stály pod sebou --
    coz neni volba, ale schody: prvni karta zabrala obrazovku a clovek na ni
    proste klikl, aniz vedel, mezi cim vybira. Karta se proto deli na:

      .ac-labchoice     kompaktni hlava, ktera staci k ROZHODNUTI -- cena
                        velkym cislem, nazev, na co miri, co si zada za
                        vybaveni, a sbaleny detail navrhu
      .ac-labfull       vsechno ostatni (co to otevre, vysledek, interpretace,
                        pripadna komplikace) -- to uz je ODPOVED, ne volba

    JS nastavi na karte data-view="choice" nebo "result" a CSS podle toho
    schova druhou pulku. Bez JS zadny data-view neni, takze se vykresli obe --
    stranka zustava kompletni ctenim shora dolu."""
    d = n["design"]
    rows = "".join("<tr><th>%s</th><td>%s</td></tr>" % (e(k.title()), prose(d[k]))
                   for k in ("model", "perturbation", "readout", "control") if d.get(k))
    pred = ('<p class="ac-labpred">Returns a prediction, not a result</p>') \
        if n.get("returns") == "prediction" else ""
    opens = ""
    if n.get("opensNote"):
        opens = ('<p class="ac-labopens"><span class="ac-rclbl">What it opened up</span> %s</p>'
                 % prose(n["opensNote"]))
    ev = ""
    if n.get("event"):
        v = n["event"]
        src = " ".join('<a class="ac-rcsid" href="%s/study/%s/">%s</a>'
                       % (SITE, e(s), e(s)) for s in v.get("sids") or [])
        ev = ('<div class="ac-rcnew" data-rc-event><p class="ac-rcnewlbl">%s</p>'
              '<p>%s %s</p><p class="ac-pdstep">%s</p>%s<p>%s</p>'
              '<p class="ac-rcinfo"><span class="ac-rclbl">The control that would help'
              '</span> %s</p></div>'
              % (e(v["title"]), prose(v["info"]), src, e(v["prompt"]),
                 rc_optnotes(v["options"], "Effect on your conclusion"),
                 prose(v["explain"]), prose(v["control"])))
    choice = ('<div class="ac-labchoice">'
              '<p class="ac-labcost"><strong>%d</strong> %s</p>'
              '<h3>%s</h3>%s'
              '<p class="ac-labfield"><span class="ac-rclbl">Addresses</span> %s</p>'
              '<p class="ac-labfield"><span class="ac-rclbl">Needs</span> %s</p>'
              '<details class="ac-labdesign"><summary>The design</summary>'
              '<div class="ac-cmpwrap"><table class="ac-cmp">%s</table></div></details>'
              '<div class="ac-labact">'
              '<button type="button" class="ac-cta ac-quiet ac-rcrun">Run &middot; %d %s'
              '</button>'
              '<button type="button" class="ac-cta ac-quiet ac-labback" hidden>Go back to '
              'this step</button>'
              '<p class="ac-rcspent" hidden>Run &middot; %d %s spent</p>'
              '<p class="ac-labafter" data-lab-after hidden></p></div>'
              '<p class="ac-rcdenied" hidden>Not enough budget left for this one. What you '
              'have already spent stays spent.</p></div>'
              % (n["cost"], e(unit), e(n["label"]), pred, prose(n["addresses"]),
                 prose(n["equipment"]), rows, n["cost"], e(unit), n["cost"], e(unit)))
    return ('<div class="ac-rcexp ac-labnode" data-rc-exp="%s" data-cost="%d">%s'
            '<div class="ac-labfull">%s%s%s</div></div>'
            % (e(n["id"]), n["cost"], choice, opens, rc_result(n, by_sid), ev))


def rc_lab_solve(lab):
    """Nejlevnejsi cesty se NEPISOU RUCNE, pocitaji se tady.

    Sedm uzlu = 128 podmnozin, takze hruba sila je uplne v poradku a je
    neprustrelna: kdyz nekdo zmeni cenu jednoho kroku nebo prekresli hranu,
    cisla v debriefu se prepocitaji sama a nemuzou se rozejit s daty.

    Podmnozina je platna, jen kdyz je cela DOSAZITELNA ze `start` uvnitr sebe
    sama -- krok nejde spustit driv, nez ho neco otevre."""
    nodes = {n["id"]: n for n in lab["nodes"]}
    ids = list(nodes)
    start = set(lab["start"])
    total = lab["budget"]["total"]

    def reachable(sub):
        got = set()
        while True:
            add = {i for i in sub - got
                   if i in start or any(p in got and i in nodes[p]["next"] for p in sub)}
            if not add:
                return got
            got |= add

    def answered(sub):
        f = set()
        for i in sub:
            f |= set(nodes[i]["yields"])
        return [g["id"] for g in lab["goals"] if set(g["answeredBy"]) <= f]

    best = {"goals": 0, "cost": 0, "route": []}
    cheapest = {}
    max_any = 0
    for mask in range(1 << len(ids)):
        sub = {ids[k] for k in range(len(ids)) if mask >> k & 1}
        if reachable(sub) != sub:
            continue
        cost = sum(nodes[i]["cost"] for i in sub)
        got = len(answered(sub))
        max_any = max(max_any, got)
        if cost > total:
            continue
        if got and (got not in cheapest or cost < cheapest[got]["cost"]):
            cheapest[got] = {"cost": cost, "route": sorted(sub, key=ids.index)}
        if (got, -cost) > (best["goals"], -best["cost"]):
            best = {"goals": got, "cost": cost, "route": sorted(sub, key=ids.index)}
    # otazky, ktere nevyda zadny uzel -- ty zustanou otevrene za jakoukoli cenu
    all_yield = set()
    for n in lab["nodes"]:
        all_yield |= set(n["yields"])
    unbuyable = [g["id"] for g in lab["goals"] if not set(g["answeredBy"]) <= all_yield]
    return {"best": best, "cheapest": cheapest, "maxAnyBudget": max_any,
            "unbuyable": unbuyable, "totalCost": sum(n["cost"] for n in lab["nodes"])}


def rc_lab_data(lab, solved):
    """Payload pro stavovy automat. Proza projde prose() uz tady, protoze JS ji
    sazi pres innerHTML."""
    nodes = {}
    for n in lab["nodes"]:
        nodes[n["id"]] = {"label": e(n["label"]), "cost": n["cost"],
                          "addresses": prose(n["addresses"]),
                          "yields": n["yields"], "next": n["next"],
                          "prediction": n.get("returns") == "prediction",
                          "conclude": [prose(t) for t in n["conclude"]],
                          "cannot": [prose(t) for t in n["cannotConclude"]]}
    return {"unit": e(lab["budget"]["unit"]), "total": lab["budget"]["total"],
            "start": lab["start"], "nodes": nodes,
            "goals": [{"id": g["id"], "q": prose(g["question"]),
                       "need": g["answeredBy"], "open": bool(g.get("open"))}
                      for g in lab["goals"]],
            "best": solved["best"],
            "cheapest": {str(k): v for k, v in solved["cheapest"].items()},
            "unbuyable": solved["unbuyable"],
            "rules": [{"ran": r.get("ran") or [], "not": r.get("notRan") or [],
                       "note": prose(r["note"])} for r in lab["debrief"]["rules"]]}


def rc_lab_fallback(lab, solved):
    """Bez-JS podoba laboratore. Karty kroku jsou na strance tak jako tak (jsou
    to ty same karty, ktere JS jen presouva), takze tady dopisujeme jen to, co
    by jinak existovalo pouze ve stavu skriptu: mapu poznatku, kudy se da zacit
    a spoctene nejlevnejsi cesty."""
    nodes = {n["id"]: n for n in lab["nodes"]}
    rows = []
    for g in lab["goals"]:
        who = [nodes[i]["label"] for i in nodes
               if set(nodes[i]["yields"]) & set(g["answeredBy"])]
        rows.append("<tr><th>%s</th><td>%s</td></tr>"
                    % (e(g["question"]),
                       e(" + ".join(who)) if who
                       else "<em>nothing in this corpus answers this</em>"))
    ch = "".join("<li>%d %s &rarr; %d of %d sub-questions</li>"
                 % (v["cost"], e(lab["budget"]["unit"]), k, len(lab["goals"]))
                 for k, v in sorted(solved["cheapest"].items()))
    opens = "".join("<li><strong>%s</strong> opens %s</li>"
                    % (e(n["label"]),
                       e(", ".join(nodes[i]["label"] for i in n["next"]))
                       if n["next"] else "nothing further")
                    for n in lab["nodes"])
    return ('<details class="ac-rcfall"><summary>The research path, without JavaScript'
            '</summary><p>With scripting on, this page walks you through the steps below '
            'one decision at a time and keeps the budget. Without it, every step is on '
            'the page in full and here is the map that would otherwise live in the '
            'script.</p>'
            '<p class="ac-showslbl">Which step answers which sub-question</p>'
            '<div class="ac-cmpwrap"><table class="ac-cmp">%s</table></div>'
            '<p class="ac-showslbl">What each step opens up</p><ul>%s</ul>'
            '<p class="ac-showslbl">You can start with</p><p>%s</p>'
            '<p class="ac-showslbl">The cheapest routes</p><ul>%s</ul>'
            '<p>The best this budget allows is %d of %d sub-questions for %d %s.</p>'
            '</details>'
            % ("".join(rows), opens,
               e(", ".join(nodes[i]["label"] for i in lab["start"])), ch,
               solved["best"]["goals"], len(lab["goals"]), solved["best"]["cost"],
               e(lab["budget"]["unit"])))


def rc_lab(ch, by_sid):
    lab = ch["lab"]
    solved = rc_lab_solve(lab)
    b = lab["budget"]
    goals = "".join(
        '<li data-goal="%s"%s><span class="ac-labtick" aria-hidden="true">&#9675;</span>'
        '<span>%s%s</span></li>'
        % (e(g["id"]), ' class="ac-labopenq"' if g.get("open") else "",
           prose(g["question"]),
           ('<span class="ac-labgnote">%s</span>' % prose(g["note"])) if g.get("note") else "")
        for g in lab["goals"])
    panel = ('<div class="ac-labgoals"><p class="ac-rclbl">What you can answer so far '
             '<span class="ac-labcount"><strong data-lab-count>0</strong> of %d</span></p>'
             '<ol class="ac-labgoallist">%s</ol></div>'
             % (len(lab["goals"]), goals))
    budget = ('<div class="ac-rcbudget" data-rc-budget="%d"><p class="ac-rcblabel">'
              'Research budget</p><p class="ac-rcbleft"><strong data-rc-left>%d</strong> '
              'of %d %s remaining</p>'
              '<div class="ac-rcbartrack ac-rcbudgetbar"><span class="ac-rcbarfill" '
              'data-rc-fill style="width:100%%"></span></div>'
              '<p class="ac-mdcap">%s</p></div>'
              % (b["total"], b["total"], b["total"], e(b["unit"]), prose(b["note"])))
    cards = "".join(rc_node(n, by_sid, b["unit"]) for n in lab["nodes"])
    return ('<div class="ac-labtop">%s%s</div>'
            '<nav class="ac-labpath" data-lab-path aria-label="Your route" hidden>'
            '<p class="ac-rclbl">Your route &mdash; go back to any step to take a '
            'different branch. Credits already spent stay spent.</p><ol></ol></nav>'
            '<div data-lab-here></div>'
            '<div class="ac-labnexthead" data-lab-nexthead hidden>'
            '<p class="ac-labnextlbl" data-lab-nextlbl></p>'
            '<p class="ac-labremain"><strong data-lab-remain>%d</strong> of %d %s left</p>'
            '</div>'
            '<div data-lab-next></div>'
            '<details class="ac-labopenbox" data-lab-open hidden>'
            '<summary>Everything else currently open to you</summary><div></div></details>'
            '<div class="ac-rcbtns" data-lab-btns hidden>'
            '<button type="button" class="ac-cta ac-quiet" data-rc-close>Close the '
            'investigation &rarr;</button>'
            '<button type="button" class="ac-mdreset" data-rc-reset>Start over with a '
            'full budget</button></div>'
            '<div class="ac-rcdebrief" data-rc-debrief hidden></div>%s'
            '<div data-lab-pool>%s</div>'
            '<script type="application/json" class="ac-rcdata">%s</script>'
            % (panel, budget, b["total"], b["total"], e(b["unit"]),
               rc_lab_fallback(lab, solved), cards,
               json.dumps(rc_lab_data(lab, solved), ensure_ascii=False).replace("</", "<\\/")))


def rc_answer(ans, by_sid, hyp_options):
    """Krok, kde vyzva odpovi na svou vlastni otazku. Tri vrstvy oddelene
    NAHLAS (§29): co bylo zmereno, jak to obor cte, a co nikdo neudelal.
    Neznamkuje studenta -- mluvi o vede a pak rekne, jak z ni vychazi kazda
    z nabidnutych hypotez, vcetne te, kterou si nevybral."""
    obs = []
    for row in ans["observation"]:
        sids = " ".join('<a class="ac-rcsid" href="%s/study/%s/">%s</a>'
                        % (SITE, e(x), e(x)) for x in row["sids"])
        for x in row["sids"]:
            if x not in by_sid:
                raise SystemExit("build_academy: answer.observation ma neznamy SID %r" % x)
        obs.append("<li>%s %s</li>" % (prose(row["text"]), sids))
    interp = "".join("<p>%s</p>" % prose(x) for x in ans["interpretation"])
    open_ = "".join('<li class="ac-no">%s</li>' % prose(x) for x in ans["stillOpen"])
    verdicts = []
    for op in hyp_options:
        v = ans["hypothesisVerdicts"].get(op["id"])
        if not v:
            raise SystemExit("build_academy: chybi verdikt k hypoteze %r" % op["id"])
        verdicts.append("<div><dt>%s</dt><dd>%s</dd></div>"
                        % (e(op["label"]), prose(v)))
    return ('<div class="ac-rcanswer"><p class="ac-rclbl">The short answer</p>'
            '<p class="ac-rcshort">%s</p></div>'
            '<p class="ac-pdstep">Observation &mdash; what has actually been measured</p>'
            '<ul class="ac-rcknow">%s</ul>'
            '<p class="ac-pdstep">Interpretation &mdash; how the field reads it</p>'
            '<div class="ac-rcinterp">%s</div>'
            '<p class="ac-pdstep">Still open &mdash; what nobody has done</p>'
            '<ul class="ac-shows">%s</ul>'
            '<p class="ac-pdstep">How each hypothesis comes out</p>'
            '<dl class="ac-mdkey ac-rcverdicts">%s</dl>'
            % (prose(ans["short"]), "".join(obs), interp, open_, "".join(verdicts)))


def rc_step(n, key, title, inner, lead=""):
    return ('<section class="ac-rcstep" id="step-%d" data-rc-step="%s">'
            '<p class="ac-rcnum">Step %d</p><h2>%s</h2>%s%s</section>'
            % (n, e(key), n, e(title), ("<p>%s</p>" % prose(lead)) if lead else "", inner))


def challenge_page(ch, by_sid, ent_url, routes, gaps, pw, lessons_by_slug):
    slug = ch["slug"]
    url = "%s/academy/research-challenges/%s/" % (SITE, slug)
    steps, secs, n = [], [], 0

    # 1 brief -------------------------------------------------------------
    n += 1
    know = "".join(
        "<li>%s %s</li>" % (prose(k["claim"]),
                            " ".join('<a class="ac-rcsid" href="%s/study/%s/">%s</a>'
                                     % (SITE, e(s), e(s)) for s in k["sids"]))
        for k in ch["whatWeKnow"])
    inner = ('<p class="ac-showslbl">What the Atlas already supports</p>'
             '<ul class="ac-rcknow">%s</ul>'
             '<p class="ac-showslbl">Where that stops</p>'
             '<ul class="ac-shows">%s</ul>' % (know, "".join(
                 "<li class=\"ac-no\">%s</li>" % prose(x) for x in ch["uncertainty"])))
    steps.append(rc_step(n, "know", "What we know", inner,
                         "Every line here is carried by a study in the Atlas, linked "
                         "beside it. Read the second list as carefully as the first: it "
                         "is where your own decisions start."))
    secs.append(("step-%d" % n, "What we know"))

    # 2 model + break -----------------------------------------------------
    n += 1
    md = dict(ch["model"])
    brk = "".join('<div class="ac-ex"><span class="ac-exkind">Break the model</span>'
                  '<h3>%s</h3>%s</div>' % (e("Prediction %d" % (i + 1)), rc_predict(b))
                  for i, b in enumerate(ch["break"]))
    inner = model_block(md, pw, ent_url) + brk
    steps.append(rc_step(n, "model", "Build and break the model", inner,
                         "Switch the controls and watch which combinations produce output. "
                         "Then break it on purpose: each prediction below asks you to commit "
                         "before it answers. These are predictions about a simplified "
                         "teaching model, not measurements."))
    secs.append(("step-%d" % n, "Build and break the model"))

    # 3 hypothesis --------------------------------------------------------
    n += 1
    h = ch["hypotheses"]
    inner = ('<div class="ac-rchyp" data-rc-hyp="working">%s'
             '<p class="ac-rccommit" hidden data-rc-committed></p></div>'
             % rc_optnotes(h["options"], "Working hypothesis"))
    steps.append(rc_step(n, "hypothesis", "Commit to a working hypothesis", inner,
                         h["prompt"]))
    secs.append(("step-%d" % n, "Commit to a working hypothesis"))

    # 4 laborator: vyzkumny graf ------------------------------------------
    n += 1
    steps.append(rc_step(n, "lab", "Run the investigation", rc_lab(ch, by_sid),
                         "This is a research path, not a shopping list. Each step costs "
                         "what its equipment costs, and each one opens up different next "
                         "steps &mdash; so the order you choose decides which questions you "
                         "can still afford to answer. You can go back to any earlier step "
                         "and take another branch; what you have already spent stays spent. "
                         "The panel above tracks which parts of the research question your "
                         "results can actually answer."))
    secs.append(("step-%d" % n, "Run the investigation"))

    # 5 revise ------------------------------------------------------------
    rv = ch.get("revise")
    if rv:
        n += 1
        opts = [{"label": o["label"], "note": rv["feedback"].get(o["id"]) or o["note"]}
                for o in ch["hypotheses"]["options"]]
        inner = ('<p class="ac-note">%s</p>%s'
                 % (prose(rv["note"]), rc_optnotes(opts, "Revised hypothesis")))
        steps.append(rc_step(n, "revise", "Revise the hypothesis", inner, rv["prompt"]))
        secs.append(("step-%d" % n, "Revise the hypothesis"))

    # 6 compare -----------------------------------------------------------
    cp = ch["compare"]
    st = by_sid.get(cp["sid"])
    if not st:
        raise SystemExit("build_academy: compare odkazuje na neznamy SID %r" % cp["sid"])
    code, _l, colour = tier_bits(st.get("tier"))
    n += 1
    inner = ('<div class="ac-rccmp"><div class="ac-evhead">'
             '<span class="tier" style="background:%s">%s</span>'
             '<a class="ac-evtitle" href="%s/study/%s/">%s</a>'
             '<span class="ac-evyear">%s</span></div>'
             '<p class="ac-pdstep">What the researchers actually tested</p><p>%s</p>'
             '<p class="ac-showslbl">What it answered</p><ul class="ac-shows">%s</ul>'
             '<p class="ac-showslbl">What it did not answer</p><ul class="ac-shows">%s</ul>'
             '<p>%s</p>'
             '<a class="ac-evlink" href="%s/study/%s/">Study page &rarr;</a></div>'
             % (colour, e(code), SITE, e(cp["sid"]), e(st.get("title") or cp["sid"]),
                e(st.get("year") or ""), prose(cp["whatTheyTested"]),
                "".join('<li class="ac-yes">%s</li>' % prose(x) for x in cp["whatItAnswered"]),
                "".join('<li class="ac-no">%s</li>' % prose(x) for x in cp["whatItDidNot"]),
                prose(cp["howToRead"]), SITE, e(cp["sid"])))
    steps.append(rc_step(n, "compare", "Compare with published research", inner,
                         "Now, and not before, here is what someone actually did."))
    secs.append(("step-%d" % n, "Compare with published research"))

    # 7 kam otazka dosla ---------------------------------------------------
    n += 1
    inner = rc_answer(ch["answer"], by_sid, ch["hypotheses"]["options"])
    steps.append(rc_step(n, "answer", "Where the question stands", inner,
                         "You have committed, spent, revised and compared. Here is what "
                         "the evidence in this Atlas actually supports today &mdash; "
                         "separated into what was measured, how it is read, and what is "
                         "still nobody's answer."))
    secs.append(("step-%d" % n, "Where the question stands"))

    # 8 reflection + next question ----------------------------------------
    n += 1
    refl = "".join('<div class="ac-rcrefl"><p class="ac-pdstep">%s</p>'
                   '<ul class="ac-qzopts" role="group" aria-label="%s">%s</ul></div>'
                   % (prose(r["prompt"]), e(TAG_RE.sub("", r["prompt"])),
                      "".join('<li><button type="button" class="ac-qzopt" '
                              'data-rc-refl="%d">%s</button></li>' % (i, prose(o))
                              for i, o in enumerate(r["options"])))
                   for r in ch["reflection"])
    nq = ch["nextQuestion"]
    inner = (refl + '<p>%s</p><p class="ac-pdstep">%s</p>%s'
             % (prose(nq["text"]), e(nq["prompt"]),
                rc_optnotes(nq["options"], "What would you do next?")))
    steps.append(rc_step(n, "reflect", "What would you do next?", inner))
    secs.append(("step-%d" % n, "What would you do next?"))

    # 9 complete ----------------------------------------------------------
    n += 1
    lessons = "".join('<a href="%s/academy/core/%s/">%s</a>'
                      % (SITE, e(s), e(lessons_by_slug[s]["title"]))
                      for s in ch["relatedLessons"] if s in lessons_by_slug)
    rts = "".join('<li><a href="%s/#view=map&amp;pw=guided&amp;route=%s">%s</a>'
                  '<span>%s</span></li>'
                  % (SITE, e(r["id"]), e(routes[r["id"]]["name"]
                                         if r["id"] in routes else r["id"]), e(r["why"]))
                  for r in ch.get("relatedRoutes") or [])
    ents = []
    for key in ("proteins", "pathways", "processes", "organelles", "nutrients"):
        for name in (ch.get("relatedEntities") or {}).get(key) or []:
            hit = ent_url.get(name.lower())
            if hit:
                ents.append('<a href="%s">%s</a>' % (hit[0], e(hit[1])))
    inner = ('<p class="ac-showslbl">Research skills this challenge practised</p>'
             '<ul class="ac-shows">%s</ul>'
             '<p class="ac-showslbl">Where to go next</p>'
             '<p class="ac-rcnextlbl">Academy lessons</p><div class="ac-deeper">%s</div>'
             '%s<p class="ac-rcnextlbl">In the Atlas</p><div class="ac-deeper">%s'
             '<a href="%s/browse/">All studies</a></div>'
             % ("".join('<li class="ac-yes">%s</li>' % e(s) for s in ch["skillsPractised"]),
                lessons,
                ('<p class="ac-rcnextlbl">Guided routes</p><ul class="ac-routes">%s</ul>'
                 % rts) if rts else "",
                "".join(ents), SITE))
    steps.append(rc_step(n, "complete", "Challenge complete", inner,
                         "No score, and nothing unlocked. What you take away is a shorter "
                         "list of things you would need to find out, and a clearer sense "
                         "of which experiment would tell you."))
    secs.append(("step-%d" % n, "Challenge complete"))

    # --- page ------------------------------------------------------------
    prereq = "".join('<li><a href="%s/academy/core/%s/">%s</a><span>%s</span></li>'
                     % (SITE, e(p["lesson"]), e(lessons_by_slug[p["lesson"]]["title"]),
                        prose(p["why"]))
                     for p in ch.get("prerequisites") or [] if p["lesson"] in lessons_by_slug)
    body = [SVG_DEFS, '<div class="ac-lesson"><article class="ac-main ac-rc">']
    body.append('<p class="ac-eyebrow">Research Challenge %s &middot; %s &middot; %s '
                '&middot; %d min</p>'
                % (e(ch["n"]), e(ch["type"]), e(ch["level"]), ch["estimatedTime"]))
    body.append("<h1>%s</h1>" % e(ch["title"]))
    body.append('<p class="meta">%s</p>' % prose(ch["subtitle"]))
    body.append('<p class="ac-q">%s</p>' % prose(ch["researchQuestion"]))
    body.append('<p class="ac-rcframe">This is a decision environment, not a quiz. Several '
                'of the choices below are scientifically defensible, and the feedback tells '
                'you what each one buys and what it costs rather than marking it right or '
                'wrong.</p>')
    if ch.get("learningObjectives"):
        body.append('<section class="ac-section ac-obj"><h2 id="objectives">What you should '
                    'be able to do</h2><p class="ac-objlbl">By the end of this challenge you '
                    'should be able to</p><ul class="ac-objlist">%s</ul>'
                    '<p class="ac-skill"><span>Research skills</span> %s</p></section>'
                    % ("".join("<li>%s</li>" % prose(x) for x in ch["learningObjectives"]),
                       " &middot; ".join(e(x) for x in ch["researchSkills"])))
        secs.insert(0, ("objectives", "What you should be able to do"))
    if prereq:
        body.append('<section class="ac-section"><h2 id="prep">Recommended preparation</h2>'
                    '<ul class="ac-routes">%s</ul></section>' % prereq)
        secs.insert(1 if ch.get("learningObjectives") else 0, ("prep", "Recommended preparation"))
    body += steps
    body.append("</article>")

    rail = ['<nav class="ac-toc" aria-label="In this challenge"><h4>In this challenge</h4><ol>']
    for aid, label in secs:
        rail.append('<li><a href="#%s">%s</a></li>' % (aid, e(label)))
    rail.append("</ol></nav>")
    body.append('<aside class="ac-rail">%s</aside>' % "".join(rail))
    body.append("</div>")

    desc = ("%s %s" % (TAG_RE.sub("", ch["researchQuestion"]),
                       TAG_RE.sub("", ch["subtitle"])))[:300]
    # --- SEO P0 Ukol 6.1 (2026-09-02): Bioschemas TrainingMaterial (challenge pages) ---
    ld = {"@context": "https://schema.org",
          "@type": ["LearningResource", "TrainingMaterial"],
          "name": ch["title"], "headline": ch["title"], "url": url, "inLanguage": "en",
          "educationalLevel": ch["level"], "learningResourceType": "e-learning",
          "timeRequired": "PT%dM" % ch["estimatedTime"],
          "teaches": ch["researchSkills"],
          "keywords": ch["researchSkills"],
          "audience": {"@type": "Audience",
                       "audienceType": "students and self-directed learners with a "
                                       "basic biology background"},
          "isPartOf": {"@type": "Course", "name": "Research Challenges — mTOR Academy",
                       "url": "%s/academy/research-challenges/" % SITE},
          "about": dict(DATASET_REF),
          "author": {"@type": "Person", "name": "Oliver Barton", "url": "https://orcid.org/0009-0008-2025-2148", "sameAs": ["https://orcid.org/0009-0008-2025-2148"]},
          "license": "https://creativecommons.org/licenses/by/4.0/"}
    bc = breadcrumb_ld([("Oliver's mTOR Atlas", SITE + "/"),
                        ("Academy", SITE + "/academy/"),
                        ("Research Challenges", "%s/academy/research-challenges/" % SITE),
                        (ch["title"], None)])
    crumb = ('<a href="%s/">Oliver\'s mTOR Atlas</a> · <a href="%s/academy/">Academy</a> · '
             '<a href="%s/academy/research-challenges/">Research Challenges</a> · %s'
             % (SITE, SITE, SITE, e(ch["title"])))
    page = shell("%s | Research Challenges | Oliver's mTOR Atlas" % ch["title"], desc, url,
                 [ld, bc], "".join(body), crumb, active_tab="learn",
                 extra_css=ACADEMY_CSS + CHALLENGE_CSS,
                 extra_body=EXERCISE_JS + CHALLENGE_JS, level_switch=True)
    page = page.replace("<body>", '<body data-rc-challenge="%s">' % e(slug), 1)
    return url, page


def challenges_index(challenges, lessons_by_slug):
    url = "%s/academy/research-challenges/" % SITE
    pub = [c for c in challenges if c["status"] == "published"]
    rows = []
    for c in challenges:
        meta = "%s · %s · %d min" % (c["type"], c["level"], c["estimatedTime"])
        if c["status"] == "published":
            rows.append('<li><a href="%s/academy/research-challenges/%s/">'
                        '<span class="ac-n">%s</span><span class="ac-ttl">%s</span>'
                        '<span class="ac-meta">%s</span></a></li>'
                        % (SITE, e(c["slug"]), e(c["n"]), e(c["title"]), e(meta)))
        else:
            rows.append('<li class="ac-planned"><span class="ac-row">'
                        '<span class="ac-n">%s</span><span class="ac-ttl">%s</span>'
                        '<span class="ac-meta">%s · in preparation</span></span></li>'
                        % (e(c["n"]), e(c["title"]), e(meta)))
    body = ['<div class="ac-hero"><p class="ac-eyebrow">mTOR Academy</p>'
            '<h1>Research Challenges</h1>'
            '<p class="ac-lede">Learn answers &ldquo;what do we know?&rdquo;. Guided Routes '
            'answer &ldquo;how are these ideas connected?&rdquo;. Research Challenges ask '
            'the third question: given what we know, what would you do next?</p></div>']
    body.append('<p>Each challenge starts from a question the field has not closed. You '
                'build a model of it, commit to a hypothesis, spend a limited research '
                'budget on experiments, read what they do and do not support, meet a '
                'complication, revise, and only then see what someone actually published. '
                'There is no score and nothing to unlock.</p>')
    body.append('<ul class="ac-list">%s</ul>' % "".join(rows))
    if any(c["status"] != "published" for c in challenges):
        body.append('<p class="ac-note">Challenges marked <em>in preparation</em> are listed '
                    'so the shape of this pillar is visible. They are not written yet, and '
                    'this page will not pretend otherwise.</p>')
    body.append('<p><a class="ac-cta ac-quiet" href="%s/academy/core/">Back to the lessons '
                '&rarr;</a></p>' % SITE)
    ld = {"@context": "https://schema.org", "@type": "Course",
          "name": "Research Challenges — mTOR Academy", "url": url,
          "description": "Interactive research challenges built on the Atlas's own "
                         "evidence-graded studies: design experiments under a limited "
                         "budget, interpret what they support, and compare your reasoning "
                         "with published work.",
          "inLanguage": "en",
          "provider": {"@type": "Organization", "name": "Oliver's mTOR Atlas",
                       "url": SITE + "/"},
          "isAccessibleForFree": True,
          "hasCourseInstance": [{"@type": "CourseInstance", "courseMode": "online",
                                 "name": c["title"],
                                 "url": "%s/academy/research-challenges/%s/"
                                        % (SITE, c["slug"])} for c in pub]}
    bc = breadcrumb_ld([("Oliver's mTOR Atlas", SITE + "/"),
                        ("Academy", SITE + "/academy/"),
                        ("Research Challenges", None)])
    crumb = ('<a href="%s/">Oliver\'s mTOR Atlas</a> · <a href="%s/academy/">Academy</a> '
             '· Research Challenges' % (SITE, SITE))
    return url, shell("Research Challenges | mTOR Academy | Oliver's mTOR Atlas",
                      "Given what we know about mTOR, what would you do next? Design "
                      "experiments under a limited research budget and compare your "
                      "reasoning with published studies from the Atlas.",
                      url, [ld, bc], "".join(body), crumb, active_tab="learn",
                      extra_css=ACADEMY_CSS + CHALLENGE_CSS)


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
    lessons, modules, by_sid, ent_url, routes, gaps, pw, challenges = load()
    lessons_by_slug = {l["slug"]: l for l in lessons}

    if CLEAN and not DRY:
        print("smazano drive vygenerovanych academy stranek:", purge())

    urls = []
    all_missing = []

    url, page = academy_home(modules, lessons_by_slug, challenges)
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
                                             ent_url, routes, gaps, pw)
            write(os.path.join(ACADEMY_DIR, mod["slug"], les["slug"], "index.html"), page)
            urls.append((url, "0.8"))
            all_missing += [(les["slug"], m) for m in missing]
            for sid in les["studies"]:
                sid_to_lesson.setdefault(sid, []).append(
                    {"title": les["title"],
                     "url": "/academy/%s/%s/" % (mod["slug"], les["slug"])})

    # Research Challenges (treti pilir). Generuje se jen kdyz jsou data --
    # jinak zustane /academy/ presne takove, jake bylo.
    pub_ch = [c for c in challenges if c["status"] == "published"]
    if pub_ch:
        url, page = challenges_index(challenges, lessons_by_slug)
        write(os.path.join(ACADEMY_DIR, "research-challenges", "index.html"), page)
        urls.append((url, "0.9"))
        for ch in pub_ch:
            url, page = challenge_page(ch, by_sid, ent_url, routes, gaps, pw,
                                       lessons_by_slug)
            write(os.path.join(ACADEMY_DIR, "research-challenges", ch["slug"],
                               "index.html"), page)
            urls.append((url, "0.8"))
            for sid in ch["studies"]:
                sid_to_lesson.setdefault(sid, []).append(
                    {"title": "Challenge %s: %s" % (ch["n"], ch["title"]),
                     "url": "/academy/research-challenges/%s/" % ch["slug"]})

    # Practice Arena (ctvrty pilir, Faze A). Vlastni modul, protoze je to
    # aplikace, ne stranka -- ale generuje se odtud, aby deploy.bat nemusel znat
    # dalsi krok. Ridi se daty jako challenges: kdyz academy_data/practice.json
    # neexistuje, /academy/ zustane presne takove, jake bylo.
    if os.path.exists(os.path.join(ADATA, "practice.json")):
        import build_practice
        urls += build_practice.build()[0]

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
