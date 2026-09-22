#!/usr/bin/env python3
"""
build_evidence_audit.py -- Evidence audit stránky (bod 7.1, 13. 9. 2026).

PROČ TOHLE EXISTUJE
-------------------
Atlas o sobě tvrdí, že drží nejen literaturu, ale i to, co literatura
neukazuje. Dokud to ale bylo jen slovy v próze, nešlo to ověřit ani citovat.
Tahle stránka z korpusu počítá, jak jeho důkazní základna doopravdy vypadá:
jaký podíl stojí na lidských datech, které části dráhy nikdo v člověku
neproměřil, kolik vazeb visí na jediné práci a kolik tvrzení má zapsané
hranice platnosti.

Výstupem je číslo, které lze citovat -- ne popis webu. To je rozdíl mezi
statistikou provozu ("máme N studií") a tvrzením o oboru ("desetina toho,
co o téhle dráze víme, stojí na lidských datech").

PARAMETRIZACE
-------------
Celá stránka se generuje z PATHWAY níž. Pro druhou dráhu (AMPK, autofagie)
stačí druhý PATHWAY dict a druhý zdroj dat -- žádná z funkcí níž neví, že
jde o mTOR. To je záměr: cílem není další stránka o mTOR, ale přenositelná
metoda hodnocení důkazní základny dráhy.

ZDROJE DAT
----------
  atlas_data/studies_baked.json  -- korpus (pole tier, pyramid, year, ...)
  index.html -> const ATLAS_EDGES -- hrany dráhy (pole tiers, st, ctx, status)

Hrany se čtou z index.html, protože relations_baked.json neexistuje --
sync_relations.py peče ATLAS_EDGES rovnou do index.html. Kdyby vznikl
samostatný JSON, změní se jen _load_edges().

SPUŠTĚNÍ
--------
    py build_evidence_audit.py            # zapíše evidence/audit/index.html
    py build_evidence_audit.py --dry-run  # jen vypíše čísla, nic nezapisuje
"""
import collections
import io
import json
import os
import re
import sys
import datetime

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from build_pages import SITE, shell, e  # noqa: E402

# --------------------------------------------------------------------------
# Konfigurace dráhy. Druhá dráha = druhý dict, nic jiného.
# --------------------------------------------------------------------------
PATHWAY = {
    "key": "mtor",
    "name": "mTOR",
    "out": "evidence/audit",
    "url": SITE + "/evidence/audit/",
    "studies": "atlas_data/studies_baked.json",
    "edges_from_index": "index.html",
}

# Evidence kódy, jak je vidí čtenář. Pořadí = síla pro tvrzení o člověku.
TIER_ORDER = ["A", "B", "C", "D"]
TIER_LABEL = {
    "A": "S &mdash; synthesis of human data",
    "B": "H &mdash; human study",
    "C": "A &mdash; animal model",
    "D": "M &mdash; molecular / in vitro / review",
}
HUMAN_TIERS = ("A", "B")
BUCKET = 5  # šířka časového okna v letech


# --------------------------------------------------------------------------
# Načtení
# --------------------------------------------------------------------------
def _load_studies(path):
    d = json.load(io.open(os.path.join(HERE, path), encoding="utf-8"))
    return d["studies"] if isinstance(d, dict) and "studies" in d else d


def _load_edges(path):
    """ATLAS_EDGES je JS literál uvnitř index.html, ne samostatný soubor."""
    s = io.open(os.path.join(HERE, path), encoding="utf-8").read()
    m = re.search(r"const ATLAS_EDGES\s*=\s*(\[.*?\]);\s*\n", s, re.S)
    if not m:
        raise SystemExit("build_evidence_audit: ATLAS_EDGES nenalezeny v " + path)
    return json.loads(m.group(1))


def tier_of(rec):
    return (rec.get("tier") or "")[:1]


def best_tier(edge):
    """Nejlepší evidence tier mezi studiemi, které tu hranu citují."""
    have = {t[:1] for t in (edge.get("tiers") or []) if t}
    for t in TIER_ORDER:
        if t in have:
            return t
    return None


# --------------------------------------------------------------------------
# Metriky. Každá vrací dict; žádná netiskne ani nic nevymýšlí.
# --------------------------------------------------------------------------
def corpus_mix(studies):
    c = collections.Counter(tier_of(s) or "?" for s in studies)
    n = len(studies)
    rows = [(t, TIER_LABEL[t], c.get(t, 0), 100.0 * c.get(t, 0) / n)
            for t in TIER_ORDER]
    off = n - sum(c.get(t, 0) for t in TIER_ORDER)
    human = sum(c.get(t, 0) for t in HUMAN_TIERS)
    return {"n": n, "rows": rows, "off_ladder": off,
            "human": human, "human_pct": 100.0 * human / n}


def human_over_time(studies):
    b = collections.defaultdict(lambda: [0, 0])
    undated = 0
    for s in studies:
        try:
            y = int(s.get("year"))
        except (TypeError, ValueError):
            undated += 1
            continue
        k = (y // BUCKET) * BUCKET
        b[k][0] += 1
        if tier_of(s) in HUMAN_TIERS:
            b[k][1] += 1
    rows = [(k, k + BUCKET - 1, n, h, 100.0 * h / n) for k, (n, h) in sorted(b.items())]
    return {"rows": rows, "undated": undated}


def pathway_coverage(edges):
    c = collections.Counter(best_tier(x) or "?" for x in edges)
    n = len(edges)
    human = sum(c.get(t, 0) for t in HUMAN_TIERS)
    mech_only = c.get("D", 0)
    desert = sorted(x["id"] for x in edges if best_tier(x) not in HUMAN_TIERS)
    return {"n": n, "counts": dict(c), "human": human,
            "human_pct": 100.0 * human / n,
            "mech_only": mech_only, "mech_pct": 100.0 * mech_only / n,
            "desert": desert}


def single_study_edges(edges):
    one = sorted(x["id"] for x in edges if len(x.get("st") or []) == 1)
    return {"n": len(one), "pct": 100.0 * len(one) / len(edges), "ids": one}


# Tagy, které nejsou psané rukou, ale počítané ze stavu hrany (sync_relations.py,
# blok DERIVED_TAGS). Na stránce se oddělují, protože říkají něco jiného:
# "tahle hrana stojí na jedné práci" je fakt o korpusu, "platí jen u samic" je
# fakt o biologii.
DERIVED_TAGS = {"time-dependent", "reversible-on-withdrawal",
                "single-study", "direction-contested"}
TAG_BLURB = {
    "sex-specific": "shown in one sex only",
    "single-species": "shown in one species and not tested elsewhere",
    "cell-line-only": "the studies cited for this link used cell culture only",
    "tissue-specific": "holds in particular tissues or cell types",
    "diet-dependent": "depends on the diet the animal was on",
    "nutrient-state-dependent": "depends on whether the cell is fed or starved",
    "dose-dependent": "depends on the dose, not merely on the drug being present",
    "time-dependent": "depends on how long the exposure lasted",
    "reversible-on-withdrawal": "the effect goes away when the intervention stops",
    "single-study": "the whole link rests on one paper in this corpus",
    "direction-contested": "the Atlas records the direction, mechanism or scope of this link as disputed",
}
# Zobrazovaný název tagu tam, kde se liší od id (id zůstává kvůli datům a dotazům).
TAG_LABEL = {"direction-contested": "contested"}
# Odvozené technicky (sync_relations.py), ale ze stavu Contested, který nastavuje
# kurátor ručně. Na stránce proto nepatří do skupiny "Computed from the corpus"
# (audit 21. 9. 2026). Kontrola sirotků výš dál používá DERIVED_TAGS.
CURATED_DERIVED = {"direction-contested"}


def boundary_coverage(edges):
    with_ctx = [x for x in edges if (x.get("ctx") or "").strip()]
    by_tag = collections.defaultdict(list)
    for x in edges:
        for t in (x.get("tags") or []):
            by_tag[t].append(x["id"])
    tagged = [x for x in edges if (x.get("tags") or [])]

    # Kontrola, ne dekorace: ruční tag na hraně bez Context_Note znamená
    # tvrzení bez opory v próze -- přesně to, co pravidlo u pole zakazuje.
    # Odvozené tagy se počítají ze stavu hrany, takže prózu mít nemusí.
    orphans = sorted(x["id"] for x in edges
                     if (set(x.get("tags") or []) - DERIVED_TAGS)
                     and not (x.get("ctx") or "").strip())

    return {"n": len(with_ctx), "total": len(edges),
            "pct": 100.0 * len(with_ctx) / len(edges),
            "tagged": len(tagged), "by_tag": dict(by_tag), "orphans": orphans}


def curation_state(edges):
    c = collections.Counter(x.get("status") or "(unset)" for x in edges)
    # Contested je tvrzení o konsenzu, ne o recenzi: sporná hrana je stejně
    # nerecenzovaná jako Proposed. Recenzovaná je jen Confirmed.
    return {"counts": dict(c), "total": len(edges),
            "unreviewed": len(edges) - c.get("Confirmed", 0),
            "proposed": c.get("Proposed", 0), "contested": c.get("Contested", 0)}


def null_results(studies, edges):
    neg = [s for s in studies if s.get("category") == "Negative_result"]
    no_effect = [x for x in edges if x.get("sign") == "no-effect"]
    return {"studies": len(neg), "edges": len(no_effect),
            "study_ids": sorted(s["sid"] for s in neg if s.get("sid"))}


def compute(cfg):
    studies = _load_studies(cfg["studies"])
    edges = _load_edges(cfg["edges_from_index"])
    return {
        "mix": corpus_mix(studies),
        "time": human_over_time(studies),
        "cover": pathway_coverage(edges),
        "single": single_study_edges(edges),
        "boundary": boundary_coverage(edges),
        "curation": curation_state(edges),
        "nulls": null_results(studies, edges),
    }


# --------------------------------------------------------------------------
# Render
# --------------------------------------------------------------------------
CSS = """
.aud-lead{font-size:1.05rem;line-height:1.65;max-width:62ch}
.aud-figure{display:flex;flex-wrap:wrap;gap:18px;margin:22px 0}
.aud-fig{flex:1 1 170px;min-width:150px;border:1px solid var(--line);
  border-radius:10px;padding:14px 16px;background:var(--card)}
.aud-fig .n{font-size:2rem;font-weight:700;line-height:1.1;color:var(--teal-deep)}
.aud-fig .l{font-size:.86rem;line-height:1.4;margin-top:4px;opacity:.85}
table.aud{border-collapse:collapse;width:100%;margin:16px 0;font-size:.93rem}
table.aud th,table.aud td{border-bottom:1px solid var(--line);padding:7px 10px;
  text-align:left;vertical-align:top}
table.aud th{font-weight:600;background:var(--card)}
table.aud td.num,table.aud th.num{text-align:right;font-variant-numeric:tabular-nums}
.aud-bar{display:block;height:7px;border-radius:4px;background:var(--teal);
  min-width:2px;margin-top:4px}
.aud-caveat{border-left:3px solid var(--amber,#c8892a);padding:10px 0 10px 14px;
  margin:20px 0;background:transparent}
.aud-caveat b{display:block;margin-bottom:4px}
.aud-ids{font-family:ui-monospace,SFMono-Regular,Menlo,monospace;font-size:.82rem;
  line-height:1.7;word-break:break-word;opacity:.9}
"""


def _bar(pct, scale=1.0):
    return '<span class="aud-bar" style="width:%.1f%%"></span>' % max(0.0, min(100.0, pct * scale))


def _fig(n, label):
    return '<div class="aud-fig"><div class="n">%s</div><div class="l">%s</div></div>' % (n, label)


def render(cfg, m):
    name = cfg["name"]
    mix, tm, cov = m["mix"], m["time"], m["cover"]
    sng, bnd, cur, nul = m["single"], m["boundary"], m["curation"], m["nulls"]
    P = []
    A = P.append

    A('<h1>Evidence audit of the Atlas&rsquo;s %s corpus</h1>' % e(name))
    A('<p class="aud-lead">This page measures the Atlas against itself. Not how '
      'many studies it holds &mdash; that number says nothing about the field &mdash; '
      'but what kind of evidence this Atlas&rsquo;s %s pathway map is built on: how much of it '
      'reaches a human, which parts of the map have no human study cited behind them, how '
      'many links in the map rest on a single paper, and how much of what is claimed '
      'carries a recorded boundary.</p>' % e(name))
    A('<p class="aud-lead">Every number below is computed from the corpus at build '
      'time, never written by hand. The method is at the bottom, so anyone can '
      'recompute them or apply the same audit to a different pathway.</p>')

    # --- headline figures ---
    A('<div class="aud-figure">')
    A(_fig("%.0f&nbsp;%%" % mix["human_pct"], "of the corpus is human evidence (%d of %d studies)" % (mix["human"], mix["n"])))
    A(_fig("%.0f&nbsp;%%" % cov["mech_pct"], "of pathway links rest on mechanistic or review papers alone"))
    A(_fig("%.0f&nbsp;%%" % sng["pct"], "of pathway links are carried by a single paper"))
    A(_fig("%.0f&nbsp;%%" % bnd["pct"], "of links record the conditions they hold under"))
    A('</div>')

    # --- 1. what the corpus is made of ---
    A('<h2 id="what-the-corpus-is-made-of">What the corpus is made of</h2>')
    A('<p>Each study carries a code for the <em>kind of claim it can support</em>, '
      'not for how good it is. A mechanistic paper is not worse than a trial; it '
      'answers a different question. The distribution matters because a pathway '
      'described almost entirely by molecular work supports conclusions about '
      'molecules, not about people.</p>')
    A('<table class="aud"><thead><tr><th>Evidence code</th><th class="num">Studies</th>'
      '<th class="num">Share</th><th>&nbsp;</th></tr></thead><tbody>')
    for t, label, n, pct in mix["rows"]:
        A('<tr><td>%s</td><td class="num">%d</td><td class="num">%.1f&nbsp;%%</td>'
          '<td>%s</td></tr>' % (label, n, pct, _bar(pct)))
    if mix["off_ladder"]:
        A('<tr><td>Off the ladder (preprint, registered trial)</td>'
          '<td class="num">%d</td><td class="num">%.1f&nbsp;%%</td><td>%s</td></tr>'
          % (mix["off_ladder"], 100.0 * mix["off_ladder"] / mix["n"],
             _bar(100.0 * mix["off_ladder"] / mix["n"])))
    A('</tbody></table>')
    A('<p><strong>%d of %d studies &mdash; %.1f&nbsp;%% &mdash; are human evidence.</strong> '
      'Almost everything else is animal, cellular or theoretical%s. That is the single most '
      'important number on this page, and it is a fact about this collection, not a '
      'measurement of the field.</p>'
      % (mix["human"], mix["n"], mix["human_pct"],
         (" (the %d off-ladder records are preprints and registered trials, which can "
          "include human studies not yet reported)" % mix["off_ladder"]) if mix["off_ladder"] else ""))

    # --- 2. over time ---
    A('<h2 id="does-it-reach-people">Is this corpus&rsquo;s human share rising over time?</h2>')
    A('<p>If the pathway were maturing towards clinical use, the share of human work '
      'would rise over time. Here is what the corpus shows, by five-year window.</p>')
    A('<table class="aud"><thead><tr><th>Period</th><th class="num">Studies</th>'
      '<th class="num">Human</th><th class="num">Share</th><th>&nbsp;</th></tr></thead><tbody>')
    for lo, hi, n, h, pct in tm["rows"]:
        A('<tr><td>%d&ndash;%d</td><td class="num">%d</td><td class="num">%d</td>'
          '<td class="num">%.0f&nbsp;%%</td><td>%s</td></tr>'
          % (lo, hi, n, h, pct, _bar(pct, 2.5)))
    A('</tbody></table>')
    A('<div class="aud-caveat"><b>Read this row-count with care.</b> The number of '
      'studies per period is a fact about <em>this corpus</em>, not about the field. '
      'Curation began with landmark papers, which cluster in the years a discovery '
      'was made, and then continued with current literature as it appeared. A thin '
      'period means the Atlas has not covered it, not that the field was quiet. The '
      'human <em>share</em> within a period is the more meaningful column, and even '
      'that is only as representative as the selection behind it.</div>')

    # --- 3. pathway coverage ---
    A('<h2 id="pathway-coverage">Which parts of the pathway reach a human</h2>')
    A('<p>The map holds %d causal links, each of which must cite at least one study '
      'in the corpus. Grading every link by the strongest evidence behind it shows '
      'where the pathway is understood in people and where it is understood only in '
      'cells.</p>' % cov["n"])
    A('<table class="aud"><thead><tr><th>Strongest evidence behind the link</th>'
      '<th class="num">Links</th><th class="num">Share</th><th>&nbsp;</th></tr></thead><tbody>')
    for t in TIER_ORDER:
        n = cov["counts"].get(t, 0)
        if not n:
            continue
        pct = 100.0 * n / cov["n"]
        A('<tr><td>%s</td><td class="num">%d</td><td class="num">%.0f&nbsp;%%</td>'
          '<td>%s</td></tr>' % (TIER_LABEL[t], n, pct, _bar(pct)))
    A('</tbody></table>')
    A('<p><strong>%d of %d links (%.0f&nbsp;%%) have any human evidence behind them; '
      '%d (%.0f&nbsp;%%) rest on mechanistic or review papers alone.</strong> This is the '
      'quantified form of what the Atlas elsewhere calls the human endpoint desert.</p>'
      % (cov["human"], cov["n"], cov["human_pct"], cov["mech_only"], cov["mech_pct"]))

    # --- 4. single-study links ---
    A('<h2 id="single-study-links">How much rests on one paper</h2>')
    A('<p>A link cited by one study is not wrong. It is unreplicated, which is a '
      'different thing, and it is the first place to look when a result fails to '
      'reproduce.</p>')
    A('<p><strong>%d of %d links (%.0f&nbsp;%%) are carried by a single paper in this '
      'corpus.</strong> Some of those papers are definitive structures; others are one '
      'result nobody has repeated. The Atlas does not currently distinguish the two, '
      'and that is itself a gap.</p>' % (sng["n"], cov["n"], sng["pct"]))
    A('<p class="aud-ids">%s</p>' % e(", ".join(sng["ids"])))

    # --- 5. boundary layer ---
    A('<h2 id="boundary-layer">How much carries its boundary</h2>')
    A('<p>A claim without its conditions is a claim that has quietly been generalised. '
      'The Atlas records, for each link, the species, tissue, dose, nutrient state or '
      'duration the finding was established under &mdash; the point where it stops '
      'being universal.</p>')
    A('<p><strong>%d of %d links (%.0f&nbsp;%%) carry a recorded boundary condition.</strong> '
      'The remainder are not thereby unconditional: they are links where the boundary '
      'has not yet been written down. Treating a blank as "holds everywhere" is the '
      'exact error this layer exists to prevent.</p>'
      % (bnd["n"], bnd["total"], bnd["pct"]))

    if bnd["by_tag"]:
        A('<h3 id="boundary-kinds">What kind of boundary</h3>')
        A('<p>The sentence is for a reader; the tag is what makes it answerable. '
          '"Female mice only in SEL2009" is clear to anyone and invisible to a '
          'query, so each recorded boundary also carries a machine-readable kind. '
          'The first group below describes the biology; the second records a '
          'curator&rsquo;s judgement that the link is disputed; the third is computed '
          'from the state of the corpus rather than written by hand.</p>')
        for heading, keys in (
            ("Boundaries on the biology",
             [t for t in sorted(bnd["by_tag"]) if t not in DERIVED_TAGS]),
            ("Set by the curator",
             [t for t in sorted(bnd["by_tag"]) if t in CURATED_DERIVED]),
            ("Computed from the corpus",
             [t for t in sorted(bnd["by_tag"]) if t in DERIVED_TAGS - CURATED_DERIVED])):
            if not keys:
                continue
            A('<p><strong>%s</strong></p>' % heading)
            A('<table class="aud"><thead><tr><th>Kind</th><th class="num">Links</th>'
              '<th>Which</th></tr></thead><tbody>')
            for t in keys:
                ids = sorted(bnd["by_tag"][t])
                shown = ", ".join("<code>%s</code>" % e(i) for i in ids[:8])
                if len(ids) > 8:
                    shown += " and %d more" % (len(ids) - 8)
                A('<tr><td><strong>%s</strong><br><span style="font-size:.87rem;opacity:.8">%s</span></td>'
                  '<td class="num">%d</td><td>%s</td></tr>'
                  % (e(TAG_LABEL.get(t, t)), e(TAG_BLURB.get(t, "")), len(ids), shown))
            A('</tbody></table>')
        A('<p>This is the query no other resource can answer. Reactome, KEGG, '
          'SIGNOR and Open Targets record the interaction; none of them record '
          'that it was only ever shown in one sex, or only in cell culture, in a '
          'form you can query across a whole pathway. '
          'The two time-related kinds have a page of their own: '
          '<a href="%s/pathway/timing/">how long the exposure lasted, and what '
          'happens when it stops</a>.</p>' % SITE)

    # --- 6. null results ---
    A('<h2 id="null-results">What has been tested and failed</h2>')
    A('<p>Findings that did not replicate, and compounds that did not extend lifespan, '
      'are kept with the same visibility as positive results.</p>')
    A('<p>The corpus holds <strong>%d studies whose curated category is '
      '<code>Negative_result</code></strong>%s. The label marks studies whose headline '
      'result was null; a trial with a null pre-registered primary endpoint may carry '
      'another category (MOE2025, the PEARL trial, is filed as Human). '
      'The pathway map also has a dedicated sign for a tested-and-null link '
      '(<code>no-effect</code>), and it is currently used <strong>%d times</strong>. '
      'That gap is real: null relationships are being recorded at the level of the '
      'study but not yet at the level of the map.</p>'
      % (nul["studies"],
         (" (" + e(", ".join(nul["study_ids"])) + ")") if nul["study_ids"] else "",
         nul["edges"]))

    # --- 7. curation state ---
    A('<h2 id="curation-state">Who has checked this</h2>')
    A('<p>Each link in the map has a curation state. <em>Proposed</em> means it was '
      'drafted and cited but has not been signed off by a second reader; '
      '<em>Contested</em> means the Atlas records the direction, mechanism or scope of '
      'the link as disputed, which is a statement about the literature, not about '
      'review; <em>Confirmed</em> means a reviewer has checked the claim against the '
      'cited papers.</p>')
    A('<table class="aud"><thead><tr><th>State</th><th class="num">Links</th>'
      '<th class="num">Share</th></tr></thead><tbody>')
    for k in sorted(cur["counts"], key=lambda x: -cur["counts"][x]):
        A('<tr><td>%s</td><td class="num">%d</td><td class="num">%.0f&nbsp;%%</td></tr>'
          % (e(k), cur["counts"][k], 100.0 * cur["counts"][k] / cur["total"]))
    A('</tbody></table>')
    A('<div class="aud-caveat"><b>%d of %d links have not been reviewed by a second '
      'reader &mdash; and they are displayed anyway.</b> That count includes the %d '
      '<em>Contested</em> links as well as the %d <em>Proposed</em> ones. There is no '
      'second reader on this project, so both states here mean drafted and cited by the '
      'curator, not independently verified. The map does not hide those links behind their status, because hiding '
      'most of the pathway would be a worse answer than labelling it. Every link, '
      'reviewed or not, names the studies it stands on, so the claim can be checked '
      'against the papers rather than taken on trust.</div>'
      % (cur["unreviewed"], cur["total"], cur["contested"], cur["proposed"]))

    # --- 8. what this does not measure ---
    A('<h2 id="limits">What this audit does not measure</h2>')
    A('<ul>')
    A('<li><strong>It measures the corpus, not the literature.</strong> The Atlas is a '
      'hand-picked subset. Every proportion here is conditional on what one curator '
      'selected, and selection is the largest uncertainty on this page.</li>')
    A('<li><strong>It says nothing about quality.</strong> An evidence code is a '
      'statement about the kind of claim a study can support. A badly run trial still '
      'codes as human evidence; an excellent structure still codes as molecular.</li>')
    A('<li><strong>It does not weight by size or replication.</strong> A trial of '
      'twenty people and one of a thousand count the same here.</li>')
    A('<li><strong>It cannot see what was never published.</strong> Negative results '
      'that never reached a journal are invisible to any audit of the published '
      'record, including this one.</li>')
    A('</ul>')

    # --- 9. method ---
    A('<h2 id="method">Method</h2>')
    A('<p>Figures are recomputed on every build by <code>build_evidence_audit.py</code> '
      'from two sources: the study corpus (<code>atlas_data/studies_baked.json</code>) '
      'and the pathway links baked into the map. No number on this page is typed by '
      'hand, so a change in the data changes the page and nothing else has to be '
      'remembered.</p>')
    A('<p>Link grading takes the strongest evidence code among the studies citing that '
      'link. Human evidence means codes S and H. Period counts use five-year windows '
      'by publication year; undated records (%d) are excluded from that table only.</p>'
      % tm["undated"])
    A('<p>The audit is written to be pathway-agnostic: the same script, pointed at a '
      'different corpus and map, produces the same measurements for any signalling '
      'pathway. The interesting comparison is not this page in isolation but two of '
      'them side by side.</p>')
    A('<p>Data and code are CC&nbsp;BY&nbsp;4.0 &mdash; see <a href="%s/data/">Data &amp; '
      'Citation</a>. Corrections are welcome and are logged; see '
      '<a href="%s/about/">About &amp; Methodology</a>.</p>' % (SITE, SITE))

    return "\n".join(P)


# --------------------------------------------------------------------------
# Zápis
# --------------------------------------------------------------------------
def build(cfg, dry_run=False):
    m = compute(cfg)
    body = render(cfg, m)

    desc = ("What this Atlas's %s corpus is built on: %.0f%% of the corpus is human "
            "evidence, %.0f%% of pathway links rest on mechanistic or review papers alone, and "
            "%.0f%% are carried by a single paper. Recomputed from the corpus on every "
            "build." % (cfg["name"], m["mix"]["human_pct"], m["cover"]["mech_pct"],
                        m["single"]["pct"]))

    today = datetime.date.today().isoformat()
    ld = [{
        "@context": "https://schema.org",
        "@type": "Report",
        "name": "Evidence audit of the Atlas's %s corpus" % cfg["name"],
        "url": cfg["url"],
        "description": desc,
        "dateModified": today,
        "isBasedOn": SITE + "/data/",
        "author": {"@type": "Person", "name": "Oliver Barton"},
        "license": "https://creativecommons.org/licenses/by/4.0/",
        "inLanguage": "en",
    }, {
        "@context": "https://schema.org",
        "@type": "BreadcrumbList",
        "itemListElement": [
            {"@type": "ListItem", "position": 1, "name": "Oliver's mTOR Atlas",
             "item": SITE + "/"},
            {"@type": "ListItem", "position": 2, "name": "Evidence",
             "item": SITE + "/evidence/"},
            {"@type": "ListItem", "position": 3, "name": "Audit",
             "item": cfg["url"]},
        ],
    }]

    html = shell(
        title="Evidence audit of the Atlas's %s corpus — Oliver's mTOR Atlas" % cfg["name"],
        desc=desc,
        canonical=cfg["url"],
        jsonld=ld,
        body=body,
        breadcrumb="Oliver's mTOR Atlas · Evidence · <b>Audit</b>",
        active_tab="about",
        extra_css=CSS,
    )

    # Sanity: shell() vkládá GA4 i canonical. Kdyby to někdo z šablony vyndal,
    # nová stránka by tiše přestala měřit -- proto to kontrolujeme tady, ne až
    # v analytice za měsíc.
    problems = []
    if m["boundary"]["orphans"]:
        problems.append(
            "ruční boundary tag bez věty v Context_Note u hran: %s -- pravidlo u "
            "pole Boundary_Tags říká, že tag smí stát jen tam, kde ho próza nese"
            % ", ".join(m["boundary"]["orphans"]))
    if "G-420TPC8J46" not in html:
        problems.append("chybí GA4 tag")
    if 'rel="canonical"' not in html:
        problems.append("chybí canonical")
    if cfg["url"] not in html:
        problems.append("canonical neukazuje na %s" % cfg["url"])
    if problems:
        raise SystemExit("build_evidence_audit: " + "; ".join(problems))

    if dry_run:
        _report(m)
        print("\n(dry-run: nic nezapsáno; %d znaků HTML by šlo do %s/index.html)"
              % (len(html), cfg["out"]))
        return m, html

    out_dir = os.path.join(HERE, *cfg["out"].split("/"))
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, "index.html")
    tmp = path + ".tmp"
    with io.open(tmp, "w", encoding="utf-8", newline="\n") as f:
        f.write(html)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)
    _report(m)
    print("\nzapsáno: %s (%d znaků)" % (path, len(html)))
    return m, html


def _report(m):
    mix, cov, sng, bnd, cur = m["mix"], m["cover"], m["single"], m["boundary"], m["curation"]
    print("korpus:            %d studií, %d lidských (%.1f %%)"
          % (mix["n"], mix["human"], mix["human_pct"]))
    print("hrany dráhy:       %d, s lidskou oporou %d (%.0f %%), jen mechanistické %d (%.0f %%)"
          % (cov["n"], cov["human"], cov["human_pct"], cov["mech_only"], cov["mech_pct"]))
    print("na jediné studii:  %d (%.0f %%)" % (sng["n"], sng["pct"]))
    print("s hranicí platnosti: %d (%.0f %%)" % (bnd["n"], bnd["pct"]))
    print("nerecenzováno:     %d z %d" % (cur["unreviewed"], cur["total"]))
    print("null results:      %d studií, %d hran se znaménkem no-effect"
          % (m["nulls"]["studies"], m["nulls"]["edges"]))


if __name__ == "__main__":
    build(PATHWAY, dry_run="--dry-run" in sys.argv)
