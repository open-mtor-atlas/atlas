#!/usr/bin/env python3
"""
build_timing_page.py -- /pathway/timing/ (bod 7.5, 13. 9. 2026).

PROČ TOHLE EXISTUJE
-------------------
Žádná dráhová databáze nemá čas. Reactome, KEGG i SIGNOR popisují vazbu jako
statický fakt: A fosforyluje B, tečka. Přitom u mTOR je jedna z otevřených
otázek oboru právě časová -- jestli o výsledku rozhoduje průměrná úroveň
aktivace, nebo její vzorec v čase. Rapamycin podaný jednou týdně a tentýž
rapamycin podávaný denně nejsou tatáž intervence, a RAPA-MTORC2 je vazba,
která při akutním podání neexistuje a po dlouhé expozici ano.

Atlas ty studie držel celou dobu -- ARR2015 srovnává čtyři dávkovací režimy
proti sobě -- ale nešlo se na ně dotázat jinak než fulltextovým hledáním.
Tahle stránka z toho dělá osu.

DVĚ RŮZNÉ VĚCI, KTERÉ SE NESMÍ SLÉVAT
  Studies.Regimen         -- jak byla intervence podávána v čase (experiment)
  Relations.Time_Dependence -- jestli vazba na čase závisí (tvrzení)

ZDROJE
  atlas_data/studies_baked.json   -- pole regimen, regimen_evidence,
                                     exposure, washout
  index.html -> const ATLAS_EDGES -- pole timedep

SPUŠTĚNÍ
    py build_timing_page.py            # zapíše pathway/timing/index.html
    py build_timing_page.py --dry-run  # jen čísla
"""
import collections
import datetime
import io
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from build_pages import SITE, shell, e  # noqa: E402

CFG = {
    "name": "mTOR",
    "out": "pathway/timing",
    "url": SITE + "/pathway/timing/",
    "studies": "atlas_data/studies_baked.json",
    "edges_from_index": "index.html",
}

# Pořadí = od nejkratší expozice po trvalou změnu; poslední dvě stojí mimo.
REGIMENS = ["Acute", "Time-windowed", "Intermittent", "Chronic continuous",
            "Withdrawal tested", "Constitutive (genetic)"]
REGIMEN_BLURB = {
    "Acute": "a single dose, or exposure under 24 hours",
    "Time-windowed": "given only during one phase of the process, not throughout",
    "Intermittent": "cycled with a deliberate gap between doses",
    "Chronic continuous": "given without a break for as long as the animal or person was followed",
    "Withdrawal tested": "the protocol included stopping, and watching what happened next",
    "Constitutive (genetic)": "a permanent genetic change, where time is not a variable",
}
UNKNOWN = ["Not stated", "Not applicable"]

TIMEDEP = ["Time-invariant (tested)", "Acute only", "Chronic only",
           "Diverges with time", "Reversible on withdrawal", "Not tested"]
TIMEDEP_BLURB = {
    "Time-invariant (tested)": "tested both acutely and chronically; the link holds either way",
    "Acute only": "shown only under short exposure",
    "Chronic only": "appears only after prolonged exposure",
    "Diverges with time": "the sign or the strength changes with duration",
    "Reversible on withdrawal": "the effect goes away when the intervention stops",
    "Not tested": "nobody has measured this link across time",
}


def load_studies():
    d = json.load(io.open(os.path.join(HERE, CFG["studies"]), encoding="utf-8"))
    return d["studies"] if isinstance(d, dict) and "studies" in d else d


def load_edges():
    s = io.open(os.path.join(HERE, CFG["edges_from_index"]), encoding="utf-8").read()
    m = re.search(r"const ATLAS_EDGES\s*=\s*(\[.*?\]);\s*\n", s, re.S)
    if not m:
        raise SystemExit("build_timing_page: ATLAS_EDGES nenalezeny")
    return json.loads(m.group(1))


def compute():
    st, ed = load_studies(), load_edges()

    # Pojistka proti tichému selhání. Kdyby sync_airtable.py neproběhl (chybějící
    # AIRTABLE_TOKEN, starý bake), pole `regimen` by v datech nebylo vůbec a
    # stránka by se postavila bez chyby -- jen by tvrdila, že korpus nemá ani
    # jednu klasifikovanou studii. To je horší než pád: nepravda, které si nikdo
    # nevšimne. Rozlišuje se CHYBĚJÍCÍ KLÍČ (sync neproběhl) od prázdné hodnoty
    # (studie zatím neklasifikovaná) -- sync klíč zapisuje vždy, i prázdný.
    # Stejná třída chyby jako entities_baked.json zamrzlé na 120/146 nebo
    # AI_Dose, které se do bake nikdy nestahovalo.
    if st and not any("regimen" in s for s in st):
        raise SystemExit(
            "build_timing_page: v %s není pole `regimen` ani u jedné z %d studií.\n"
            "  Data neprošla sync_airtable.py -- stránka by tvrdila, že korpus\n"
            "  nemá žádné klasifikované studie. Spusť sync_airtable.py (vyžaduje\n"
            "  AIRTABLE_TOKEN) a teprve pak tenhle skript." % (CFG["studies"], len(st)))

    classified = [s for s in st if (s.get("regimen") or "").strip()]
    by_reg = collections.defaultdict(list)
    for s in classified:
        by_reg[s["regimen"]].append(s)

    # Studie, která srovnávala REŽIM proti REŽIMU, ne jen dávku proti dávce.
    # Odvozeno, ne vypsáno ručně: intermitentní rameno, jehož doklad zároveň
    # zmiňuje denní podávání, znamená, že obě varianty běžely vedle sebe.
    sched = [s for s in by_reg.get("Intermittent", [])
             if re.search(r"\bdaily\b|\b1x/day\b|once a day", s.get("regimen_evidence") or "", re.I)]

    stops = [s for s in classified if s.get("washout")]

    td = collections.Counter((x.get("timedep") or "Not tested") for x in ed)
    td_edges = collections.defaultdict(list)
    for x in ed:
        td_edges[x.get("timedep") or "Not tested"].append(x)

    return {"studies": st, "classified": classified, "by_reg": by_reg,
            "sched": sched, "stops": stops, "edges": ed, "td": td,
            "td_edges": td_edges,
            "n_unclassified": len(st) - len(classified)}


CSS = """
.tm-lead{font-size:1.05rem;line-height:1.65;max-width:62ch}
.tm-figure{display:flex;flex-wrap:wrap;gap:18px;margin:22px 0}
.tm-fig{flex:1 1 170px;min-width:150px;border:1px solid var(--line);
  border-radius:10px;padding:14px 16px;background:var(--card)}
.tm-fig .n{font-size:2rem;font-weight:700;line-height:1.1;color:var(--teal-deep)}
.tm-fig .l{font-size:.86rem;line-height:1.4;margin-top:4px;opacity:.85}
table.tm{border-collapse:collapse;width:100%;margin:16px 0;font-size:.93rem}
table.tm th,table.tm td{border-bottom:1px solid var(--line);padding:8px 10px;
  text-align:left;vertical-align:top}
table.tm th{font-weight:600;background:var(--card)}
table.tm td.num,table.tm th.num{text-align:right;font-variant-numeric:tabular-nums}
.tm-reg{font-weight:600}
.tm-blurb{font-size:.88rem;opacity:.8;display:block;margin-top:2px}
.tm-card{border:1px solid var(--line);border-left:3px solid var(--teal);
  border-radius:8px;padding:14px 16px;margin:16px 0;background:var(--card)}
.tm-card h3{margin:0 0 6px;font-size:1.02rem}
.tm-quote{font-size:.9rem;line-height:1.55;opacity:.9;margin:8px 0 0;
  padding-left:12px;border-left:2px solid var(--line)}
.tm-meta{font-size:.83rem;opacity:.75;margin-top:6px}
.tm-caveat{border-left:3px solid var(--amber,#c8892a);padding:10px 0 10px 14px;margin:20px 0}
.tm-caveat b{display:block;margin-bottom:4px}
.tm-ids{font-family:ui-monospace,SFMono-Regular,Menlo,monospace;font-size:.82rem;
  line-height:1.7;word-break:break-word;opacity:.9}
"""


def _fig(n, label):
    return '<div class="tm-fig"><div class="n">%s</div><div class="l">%s</div></div>' % (n, label)


def study_link(s):
    return '<a href="%s/study/%s/">%s</a>' % (SITE, e(s["sid"]), e(s["sid"]))


def render(m):
    cls, by_reg, td = m["classified"], m["by_reg"], m["td"]
    n_all = len(m["studies"])
    n_edges = len(m["edges"])
    tested = n_edges - td.get("Not tested", 0)
    P = []
    A = P.append

    A('<h1>Timing: the axis the pathway maps leave out</h1>')
    A('<p class="tm-lead">Every pathway map treats a link as a fact that either '
      'holds or does not. None of them record <em>when</em>. Yet rapamycin given '
      'once a week and the same rapamycin given every day are not the same '
      'intervention, and at least one link in this map does not exist at all '
      'under short exposure and appears after a long one.</p>')
    A('<p class="tm-lead">This page separates two questions that get confused. '
      'For a <strong>study</strong>: how was the intervention delivered over time? '
      'For a <strong>link in the pathway</strong>: does the relationship itself '
      'depend on time? The first is a property of an experiment, the second a '
      'property of a claim.</p>')

    A('<div class="tm-figure">')
    A(_fig(len(cls), "studies with a recorded regimen, each quoting the sentence that shows it"))
    A(_fig(len(by_reg.get("Intermittent", [])), "tested an intermittent schedule rather than continuous dosing"))
    A(_fig(len(m["stops"]), "watched what happened after the intervention stopped"))
    A(_fig("%d of %d" % (td.get("Not tested", 0), n_edges), "pathway links have never been measured across time"))
    A('</div>')

    # --- 1. regimes -------------------------------------------------------
    A('<h2 id="regimes">How the interventions were delivered</h2>')
    A('<p>A regimen is recorded only where a sentence in the source says so, and '
      'that sentence is stored next to it. Where the paper does not say, the '
      'record says <em>not stated</em> rather than guessing a plausible schedule.</p>')
    A('<table class="tm"><thead><tr><th>Regimen</th><th class="num">Studies</th>'
      '<th>Examples</th></tr></thead><tbody>')
    for r in REGIMENS:
        rows = by_reg.get(r, [])
        if not rows:
            continue
        ex = ", ".join(study_link(s) for s in sorted(rows, key=lambda x: x["sid"])[:6])
        if len(rows) > 6:
            ex += " and %d more" % (len(rows) - 6)
        A('<tr><td><span class="tm-reg">%s</span><span class="tm-blurb">%s</span></td>'
          '<td class="num">%d</td><td>%s</td></tr>'
          % (e(r), e(REGIMEN_BLURB[r]), len(rows), ex))
    A('</tbody></table>')
    nk = sum(len(by_reg.get(k, [])) for k in UNKNOWN)
    A('<p>A further %d records sit outside that ladder: %d where an intervention '
      'was given but the schedule is not stated, and %d where the study '
      'administers nothing over time at all (reviews and syntheses). '
      '%d of the %d studies in the corpus have not been classified yet.</p>'
      % (nk, len(by_reg.get("Not stated", [])), len(by_reg.get("Not applicable", [])),
         m["n_unclassified"], n_all))

    # --- 2. dose vs schedule ---------------------------------------------
    A('<h2 id="dose-versus-schedule">Dose versus schedule</h2>')
    A('<p>Almost every dose-response study asks <em>how much</em>. Far fewer ask '
      '<em>how often</em> while holding the amount fixed &mdash; and that is the '
      'question behind intermittent dosing protocols. Studies in this corpus that '
      'ran schedules against each other:</p>')
    if m["sched"]:
        for s in m["sched"]:
            A('<div class="tm-card"><h3>%s &mdash; %s (%s)</h3>'
              % (study_link(s), e(s.get("title") or "")[:120], e(str(s.get("year") or ""))))
            A('<p class="tm-quote">%s</p>' % e(s.get("regimen_evidence") or ""))
            if s.get("exposure"):
                A('<p class="tm-meta">Exposure window: %s</p>' % e(s["exposure"]))
            A('</div>')
    else:
        A('<p>None &mdash; which would itself be the finding.</p>')
    A('<p>The rest of the intermittent arm tested a single spaced schedule without '
      'a continuous comparator, which answers whether the schedule works, not '
      'whether it works <em>better</em>.</p>')

    # --- 3. what happens when you stop ------------------------------------
    A('<h2 id="stopping">What happens when you stop</h2>')
    A('<p>A benefit that disappears on withdrawal is suppression, not repair. That '
      'distinction decides whether an intervention is a course of treatment or a '
      'commitment, and it is visible only in protocols that included stopping.</p>')
    if m["stops"]:
        A('<table class="tm"><thead><tr><th>Study</th><th>What the protocol did</th>'
          '<th>Window</th></tr></thead><tbody>')
        for s in sorted(m["stops"], key=lambda x: x["sid"]):
            A('<tr><td>%s</td><td>%s</td><td>%s</td></tr>'
              % (study_link(s), e((s.get("regimen_evidence") or "")[:200]),
                 e(s.get("exposure") or "&mdash;")))
        A('</tbody></table>')
    rev = m["td_edges"].get("Reversible on withdrawal", [])
    if rev:
        A('<p>On the pathway map, %d link%s carr%s the same finding:</p>'
          % (len(rev), "s" if len(rev) > 1 else "", "y" if len(rev) > 1 else "ies"))
        A('<table class="tm"><thead><tr><th>Link</th><th>Boundary recorded</th>'
          '</tr></thead><tbody>')
        for x in sorted(rev, key=lambda y: y["id"]):
            A('<tr><td><code>%s</code></td><td>%s</td></tr>'
              % (e(x["id"]), e(x.get("ctx") or "")))
        A('</tbody></table>')

    # --- 4. time dependence of links --------------------------------------
    A('<h2 id="link-timing">Which links depend on time</h2>')
    A('<p>Each link in the pathway map cites at least one study. Where those '
      'studies establish that the relationship changes with exposure, the link '
      'says so. Where nobody has looked, it says that too &mdash; and that is the '
      'majority.</p>')
    A('<table class="tm"><thead><tr><th>Time dependence</th><th class="num">Links</th>'
      '<th>Which</th></tr></thead><tbody>')
    for t in TIMEDEP:
        rows = m["td_edges"].get(t, [])
        if not rows:
            continue
        if t == "Not tested":
            which = "<em>the rest of the map</em>"
        else:
            which = ", ".join("<code>%s</code>" % e(x["id"]) for x in sorted(rows, key=lambda y: y["id"]))
        A('<tr><td><span class="tm-reg">%s</span><span class="tm-blurb">%s</span></td>'
          '<td class="num">%d</td><td>%s</td></tr>'
          % (e(t), e(TIMEDEP_BLURB[t]), len(rows), which))
    A('</tbody></table>')
    A('<p><strong>%d of %d links have any time dimension recorded.</strong> The '
      'other %d are not thereby time-invariant &mdash; they are links where the '
      'question was never asked. Treating an untested link as unconditional is '
      'the error this column exists to prevent.</p>'
      % (tested, n_edges, td.get("Not tested", 0)))

    # --- 5. why it matters -------------------------------------------------
    A('<h2 id="why">Why this is a separate axis</h2>')
    A('<p>The clearest case in the corpus is the link between rapamycin and '
      'mTORC2. Rapamycin was described for years as an mTORC1-selective '
      'inhibitor. That is true of a short exposure and false of a long one: in '
      'some cell types prolonged treatment also disrupts mTORC2. The direction of '
      'the arrow does not change &mdash; its existence does.</p>')
    A('<p>A map without a time column cannot represent that. It has to either '
      'draw the link and overstate it, or leave it out and understate it. The '
      'same applies to every claim that a compound "works": the schedule is part '
      'of the claim, and dropping it is how a finding quietly becomes a general '
      'statement it was never entitled to be.</p>')

    # --- 6. limits ---------------------------------------------------------
    A('<div class="tm-caveat"><b>What this does not tell you.</b> A regimen is '
      'recorded from what the paper reports, so a study that ran a careful '
      'schedule and described it loosely will read as <em>not stated</em>. The '
      'classification says how the intervention was delivered, never whether the '
      'schedule was a good one. And the links marked <em>not tested</em> are the '
      'honest majority: this axis is at its most useful as a map of what has not '
      'been done.</div>')

    # --- 7. method ---------------------------------------------------------
    A('<h2 id="method">Method</h2>')
    A('<p>Figures are recomputed on every build by <code>build_timing_page.py</code> '
      'from the study corpus and the pathway links. A regimen is only recorded '
      'when a sentence in the source states it, and that sentence is stored '
      'verbatim alongside the classification, so every entry on this page can be '
      'checked against the paper rather than taken on trust. Studies where the '
      'evidence did not settle the question were left blank rather than assigned '
      'a plausible value.</p>')
    A('<p>The schedule comparison above is derived, not curated: it lists studies '
      'whose intermittent arm ran alongside a daily one in the same experiment.</p>')
    A('<p>Data are CC&nbsp;BY&nbsp;4.0 &mdash; see <a href="%s/data/">Data &amp; '
      'Citation</a>. The same corpus is measured from a different angle on the '
      '<a href="%s/evidence/audit/">evidence audit</a>.</p>' % (SITE, SITE))

    return "\n".join(P)


def build(dry_run=False):
    m = compute()
    body = render(m)
    td = m["td"]
    n_edges = len(m["edges"])

    desc = ("How mTOR interventions were delivered over time, and which pathway links "
            "depend on it: %d studies with a recorded regimen, %d that tested an "
            "intermittent schedule, and %d of %d links never measured across time."
            % (len(m["classified"]), len(m["by_reg"].get("Intermittent", [])),
               td.get("Not tested", 0), n_edges))

    today = datetime.date.today().isoformat()
    ld = [{
        "@context": "https://schema.org", "@type": "Report",
        "name": "Timing in the %s pathway" % CFG["name"],
        "url": CFG["url"], "description": desc, "dateModified": today,
        "isBasedOn": SITE + "/data/",
        "author": {"@type": "Person", "name": "Oliver Barton"},
        "license": "https://creativecommons.org/licenses/by/4.0/",
        "inLanguage": "en",
    }, {
        "@context": "https://schema.org", "@type": "BreadcrumbList",
        "itemListElement": [
            {"@type": "ListItem", "position": 1, "name": "Oliver's mTOR Atlas",
             "item": SITE + "/"},
            {"@type": "ListItem", "position": 2, "name": "Pathway",
             "item": SITE + "/pathway/"},
            {"@type": "ListItem", "position": 3, "name": "Timing",
             "item": CFG["url"]},
        ],
    }]

    html = shell(
        title="Timing in the %s pathway — Oliver's mTOR Atlas" % CFG["name"],
        desc=desc, canonical=CFG["url"], jsonld=ld, body=body,
        breadcrumb="Oliver's mTOR Atlas · Pathway · <b>Timing</b>",
        active_tab="map", extra_css=CSS,
    )

    # Stejná pojistka jako u /evidence/audit/: nová stránka bez měřicího tagu
    # je chyba, která se jinak pozná až z chybějících dat za tři týdny.
    bad = []
    if "G-420TPC8J46" not in html:
        bad.append("chybí GA4 tag")
    if 'rel="canonical"' not in html:
        bad.append("chybí canonical")
    if CFG["url"] not in html:
        bad.append("canonical neukazuje na " + CFG["url"])
    if bad:
        raise SystemExit("build_timing_page: " + "; ".join(bad))

    _report(m)
    if dry_run:
        print("\n(dry-run: nic nezapsáno; %d znaků HTML)" % len(html))
        return m, html

    out_dir = os.path.join(HERE, *CFG["out"].split("/"))
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, "index.html")
    tmp = path + ".tmp"
    with io.open(tmp, "w", encoding="utf-8", newline="\n") as f:
        f.write(html)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)
    print("\nzapsáno: %s (%d znaků)" % (path, len(html)))
    return m, html


def _report(m):
    print("klasifikováno:     %d z %d studií" % (len(m["classified"]), len(m["studies"])))
    for r in REGIMENS + UNKNOWN:
        n = len(m["by_reg"].get(r, []))
        if n:
            print("   %-24s %d" % (r, n))
    print("srovnání režimů:   %d studií" % len(m["sched"]))
    print("s vysazením:       %d studií" % len(m["stops"]))
    print("hrany:")
    for t in TIMEDEP:
        n = m["td"].get(t, 0)
        if n:
            print("   %-26s %d" % (t, n))


if __name__ == "__main__":
    build(dry_run="--dry-run" in sys.argv)
