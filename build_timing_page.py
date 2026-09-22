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

ÚROVEŇ B (21. 9. 2026)
  Druhá sekce "How the signal itself moves" (Studies.Signal_Readout a smyčky
  negativní zpětné vazby odvozené z ATLAS_EDGES) a samostatná stránka
  /pathway/timing/pattern/ ("Does the pattern matter more than the average?").
  Obě staví tenhle skript; deploy.bat se proto neměnil.

INTERAKTIVNÍ VRSTVA (21. 9. 2026)
  Pět vizualizací (vlna "same average", žebřík evidence, dvoje hodiny,
  matice systémů, květ smyček). CSS a JS jsou uvnitř obsahu kvůli V2 --
  viz blok INTERAKTIVNÍ VRSTVA na konci souboru.

SPUŠTĚNÍ
    py build_timing_page.py            # zapíše pathway/timing/index.html
                                       # a pathway/timing/pattern/index.html
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
    "Not tested": "no study cited for this link, in this corpus, establishes whether the relationship changes with exposure time",
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
            "n_unclassified": len(st) - len(classified),
            "dyn": compute_dynamics(st, ed)}


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

    A(pv_style())  # uvnitř .wrap kvůli V2 (sync_prose), viz INTERAKTIVNÍ VRSTVA
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
    A(_fig(len(m["stops"]), "included stopping the intervention and watching what happened next"))
    A(_fig("%d of %d" % (td.get("Not tested", 0), n_edges), "pathway links carry no recorded time dependence in this Atlas"))
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
    # Hero a sekce "What happens when you stop" počítají podle washout; řádek
    # "Withdrawal tested" podle hlavního režimu. Rozdíl se tu vysvětluje, aby
    # čísla na stránce nesouhlasila jen zdánlivě (audit 21. 9. 2026).
    wd = {s["sid"] for s in by_reg.get("Withdrawal tested", [])}
    extra_stops = sorted(s["sid"] for s in m["stops"] if s["sid"] not in wd)
    if extra_stops:
        A('<p>The <em>withdrawal tested</em> row counts studies whose main design is '
          'stopping. %d more (%s) included a recovery period after a different main '
          'regimen, so the stopping section below lists %d studies in all.</p>'
          % (len(extra_stops), ", ".join(e(x) for x in extra_stops), len(m["stops"])))

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
      'says so. Where no cited study in this corpus settles it, it says that too '
      '&mdash; and that is the majority.</p>')
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
      'other %d are not thereby time-invariant &mdash; they are links where no time '
      'dependence is recorded in this Atlas. Treating an untested link as unconditional is '
      'the error this column exists to prevent.</p>'
      % (tested, n_edges, td.get("Not tested", 0)))

    # --- 4b. time inside the cell (úroveň B, 21. 9. 2026) ------------------
    A(render_dynamics(m))

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
      'honest majority: this axis is at its most useful as a map of what this '
      'Atlas has not yet recorded.</div>')

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

    A(pv_script(dict(arms=loops_viz_data(m["dyn"]))))
    return "\n".join(P)


# ===========================================================================
# ÚROVEŇ B (21. 9. 2026): ČAS UVNITŘ BUŇKY
# ---------------------------------------------------------------------------
# Všechno výš je čas VNUCENÝ zvenku: jak dlouho a jak často se podávala
# intervence. Oliverova otázka je jiná -- jestli se aktivita mTORC1 sama od
# sebe v čase mění, a jestli o výsledku rozhoduje ten vzorec, nebo jen průměr.
# Dvě věci, které se tu počítají:
#   Studies.Signal_Readout  -- jak studie signál v čase čte (snapshot, časová
#                              řada, živé buňky, buněčný cyklus, cirkadiánní
#                              rytmus, model), vždy s dokladem v Signal_Readout_
#                              Evidence.
#   smyčky negativní zpětné vazby -- ODVOZENÉ z ATLAS_EDGES při každém buildu,
#                              ne zapsané ručně. Ručně je jen to, přes kterou
#                              "zpětnou větev" (ARMS) se smyčka vrací, a
#                              poznámka k ní. Nová smyčka, kterou nejde
#                              přiřadit žádné větvi, build shodí -- jinak by
#                              stránka tiše tvrdila neúplný výčet.
# VĚDECKÁ OPATRNOST: negativní zpětná vazba je strukturní předpoklad oscilace,
# ne její důkaz (potřebuje zpoždění, nelinearitu a dost zesílení). Proto se
# všude píše "a structure that could oscillate", nikdy "an oscillator".
# ===========================================================================

READOUTS = ["Live single-cell", "Cell-cycle resolved", "Population time course",
            "Circadian", "Model", "Snapshot"]
READOUT_BLURB = {
    "Live single-cell": "the same living cells watched as the signal changes",
    "Cell-cycle resolved": "signal read separately for each phase of the cell cycle",
    "Population time course": "many cells sampled at several time points and averaged",
    "Circadian": "signal or its consequences measured across the 24-hour clock",
    "Model": "a mathematical model of how the signal changes; a prediction, not a measurement",
    "Snapshot": "conditions compared at fixed points; no time series in the abstract",
}
# Co se počítá jako "sledováno v čase" (měření, ne model, ne snapshot).
TIME_MEASURED = {"Live single-cell", "Cell-cycle resolved", "Population time course", "Circadian"}

# Zpětné větve. Klíč = id hrany v ATLAS_EDGES, přes kterou se smyčka vrací
# nahoru. `extra` = studie, které tu větev sledovaly v čase, i když nejsou
# citované přímo na hraně (každá musí v korpusu existovat, jinak build spadne).
ARMS = {
    "S6K1-IRS1": dict(
        label="S6K1 &rarr; IRS1",
        what="the insulin brake: mTORC1's output kinase S6K1 switches off IRS1, so insulin signalling weakens the more mTORC1 is on",
        extra=["GIN2026", "DAL2012"],
        context="unperturbed cells",
        note="GIN2026 found feedback on AKT acting only in a narrow window around G1/S of the cell cycle, "
             "reconstructed from fixed single-cell images; the authors attribute it to this arm but say "
             "their data do not establish it uniquely. DAL2012 fitted the loop as a dynamical model. "
             "No study in this atlas has watched this arm live."),
    "GRB10-IGF1": dict(
        label="Grb10 &rarr; IGF-1 / PI3K",
        what="a second brake: mTORC1 stabilises Grb10, which damps growth-factor receptor signalling",
        extra=[],
        # Citované na hraně, ale Grb10 samy neměří: ROD2011 = uvolnění RTK zpětné
        # vazby obecně, ORE2006 = indukce IRS-1 (větev S6K1 -> IRS1). Do statusu
        # větve se proto nepočítají (audit 21. 9. 2026).
        not_arm=["ROD2011", "ORE2006"],
        context="not followed in time",
        note="The Grb10 papers are snapshot biochemistry. The time course usually cited here (ROD2011) "
             "shows AKT rebound after mTOR kinase inhibition through relief of receptor tyrosine kinase "
             "feedback, without measuring Grb10, so it is evidence that a brake exists, not that this is "
             "the brake."),
    "ULK1-AMPK": dict(
        label="ULK1 &rarr; AMPK",
        what="the energy loop: ULK1, which mTORC1 restrains, phosphorylates AMPK and turns it down",
        extra=[],
        context="not followed in time",
        note="LOF2011 showed the phosphorylation and proposed the loop from biochemistry. DAL2016 followed "
             "AMPK and mTOR over time after amino acids came back and found them switching on together, "
             "which complicates the simple picture of two opposites, but it did not follow the loop itself."),
    "MTORC1-MAPK": dict(
        label="mTORC1 &rarr; ERK (MAPK)",
        what="the escape route: blocking mTORC1 releases ERK signalling through S6K1, PI3K and Ras",
        extra=[],
        context="only after a drug",
        note="Seen in patient biopsies and in cells as MAPK activation after rapamycin analogues (CAR2008). "
             "The authors noted a dependence on the dosing schedule; this atlas holds no time series of it."),
}

_SIGN = {"activates": 1, "inhibits": -1}


def negative_loops(edges, max_len=8):
    """Všechny jednoduché cykly se součinem znamének -1 (jen activates/inhibits).
    Každý cyklus se najde jednou: začíná v lexikograficky nejmenším uzlu."""
    adj = collections.defaultdict(list)
    for x in edges:
        if x.get("sign") in _SIGN:
            adj[x["s"]].append(x)
    seen, out = set(), []

    def dfs(start, node, path, chain):
        for x in adj.get(node, []):
            t = x["t"]
            if t == start:
                cyc = chain + [x]
                key = frozenset(y["id"] for y in cyc)
                if key not in seen:
                    seen.add(key)
                    out.append(cyc)
            elif t not in path and t > start and len(chain) + 1 < max_len:
                dfs(start, t, path | {t}, chain + [x])

    for n in sorted(adj):
        dfs(n, n, {n}, [])
    neg = []
    for c in out:
        p = 1
        for x in c:
            p *= _SIGN[x["sign"]]
        if p < 0:
            neg.append(c)
    return neg


def arm_status(sids, by_sid):
    rd = set()
    for sid in sids:
        rd.update(by_sid.get(sid, {}).get("readout") or [])
    if rd & TIME_MEASURED:
        return "Followed in time"
    if "Model" in rd:
        return "Modelled only"
    return "Snapshots only"


def compute_dynamics(st, ed):
    # Stejná pojistka jako u `regimen`: chybějící klíč = sync neproběhl.
    if st and not any("readout" in s for s in st):
        raise SystemExit(
            "build_timing_page: v %s není pole `readout` ani u jedné studie.\n"
            "  sync_airtable.py je starší než úroveň B (Signal_Readout) nebo\n"
            "  neproběhl. Stránka by tvrdila, že žádná studie signál v čase nečte."
            % CFG["studies"])
    by_sid = {s["sid"]: s for s in st}
    for a in ARMS.values():
        for sid in a["extra"]:
            if sid not in by_sid:
                raise SystemExit("build_timing_page: ARMS odkazuje na %s, který v korpusu není" % sid)

    with_rd = [s for s in st if s.get("readout")]
    by_rd = collections.defaultdict(list)
    for s in with_rd:
        for r in s["readout"]:
            by_rd[r].append(s)
    measured = [s for s in with_rd if set(s["readout"]) & TIME_MEASURED]

    loops = negative_loops(ed)
    eid = {x["id"]: x for x in ed}
    arms = collections.OrderedDict((k, []) for k in ARMS)
    for c in loops:
        ids = [x["id"] for x in c]
        hit = [k for k in ARMS if k in ids]
        if len(hit) != 1:
            raise SystemExit(
                "build_timing_page: smyčka %s se vrací přes %d známých větví (%s).\n"
                "  Přidej její zpětnou hranu do ARMS, nebo oprav znaménko v Airtable."
                % (" -> ".join([c[0]["s"]] + [x["t"] for x in c]), len(hit), hit))
        arms[hit[0]].append(c)
    arm_rows = []
    for k, cycles in arms.items():
        a = ARMS[k]
        edge = eid.get(k)
        if edge is None:
            raise SystemExit("build_timing_page: hrana %s z ARMS v ATLAS_EDGES chybí" % k)
        sids = list(dict.fromkeys(list(edge.get("st") or []) + a["extra"]))
        # Status větve jen ze studií, které tu větev skutečně měří (not_arm vyřazuje
        # studie citované na hraně kvůli jinému mechanismu).
        arm_sids = [s for s in sids if s not in a.get("not_arm", [])]
        arm_rows.append(dict(key=k, cycles=cycles, sids=sids,
                             status=arm_status(arm_sids, by_sid), **a))
    return {"with_rd": with_rd, "by_rd": by_rd, "measured": measured,
            "loops": loops, "arms": arm_rows, "by_sid": by_sid}


def _loop_text(c):
    return " &rarr; ".join([e(c[0]["s"])] + [e(x["t"]) for x in c])


def render_dynamics(m):
    d = m["dyn"]
    n_follow = sum(1 for a in d["arms"] if a["status"] == "Followed in time")
    # Ne každá smyčka prochází mTORC1 (např. AMPK -> ULK1 -> AMPK), proto zvlášť.
    n_via = sum(1 for c in d["loops"] if "mTORC1" in [x["s"] for x in c])
    P = []
    A = P.append
    A('<h2 id="signal">How the signal itself moves</h2>')
    A('<p>Everything above is time imposed from outside: how long and how often an '
      'intervention was given. There is a second kind of time, inside the cell. '
      'mTORC1 activity is not a fixed setting: it rises and falls without any change in '
      'the external stimulus, driven by the cell cycle and by the daily clock. Whether that pattern, and not '
      'only the average level, decides what the cell does is an open question '
      '&mdash; it has <a href="%s/pathway/timing/pattern/">its own page</a>.</p>' % SITE)
    A('<div class="tm-figure">')
    A(_fig(len(d["with_rd"]), "studies with a recorded readout type, each with the sentence that shows it"))
    A(_fig(len(d["measured"]), "actually follow a signal over time rather than comparing fixed points"))
    A(_fig(len(d["by_rd"].get("Live single-cell", [])), "watch the same living cells as the signal changes"))
    A(_fig("%d of %d" % (n_follow, len(d["arms"])), "feedback arms on the map have been followed in time at all"))
    A('</div>')

    A('<h3>How each study reads the signal</h3>')
    A('<table class="tm"><thead><tr><th>Readout</th><th class="num">Studies</th>'
      '<th>Which</th></tr></thead><tbody>')
    for r in READOUTS:
        rows = sorted(d["by_rd"].get(r, []), key=lambda x: x["sid"])
        if not rows:
            continue
        A('<tr><td><span class="tm-reg">%s</span><span class="tm-blurb">%s</span></td>'
          '<td class="num">%d</td><td>%s</td></tr>'
          % (e(r), e(READOUT_BLURB[r]), len(rows), ", ".join(study_link(s) for s in rows)))
    A('</tbody></table>')
    A('<p>A study can carry more than one readout. Only studies that bear on signal '
      'dynamics or on the feedback loops below have been classified so far; a '
      'blank is not a snapshot, it is a study nobody has checked yet.</p>')

    A('<h3>Feedback loops on the map</h3>')
    A('<p>Walking the arrows of this map, %d closed routes come back to where they '
      'started with a net inhibitory sign: when mTORC1 goes up, something it '
      'triggers eventually pushes it back down. They all return through one of '
      '%d feedback arms. A loop like this is a structure that <em>could</em> '
      'produce pulses or oscillation. It is not proof that it does: that also '
      'needs a delay, a steep enough response and enough gain, and none of those '
      'can be read off a diagram.</p>' % (len(d["loops"]), len(d["arms"])))
    A(pv_box("loops", "%s ways mTORC1 turns itself down" % _NUM.get(len(d["arms"]), str(len(d["arms"]))),
             sub="%d closed routes on the map carry a net inhibitory sign, %d of them through "
                 "mTORC1. They all return through one of these arms. Line thickness shows the "
                 "number of routes; click an arm." % (len(d["loops"]), n_via),
             schem="A loop is a structure that could oscillate. It is not evidence that it does."))
    A('<div data-pv-fallback="loops">')
    A('<table class="tm"><thead><tr><th>Feedback arm</th><th class="num">Routes</th>'
      '<th>Evidence in time</th><th>Studies</th></tr></thead><tbody>')
    for a in d["arms"]:
        A('<tr><td><span class="tm-reg">%s</span><span class="tm-blurb">%s</span></td>'
          '<td class="num">%d</td><td><b>%s</b><span class="tm-blurb">%s</span></td><td>%s</td></tr>'
          % (a["label"], e(a["what"]), len(a["cycles"]), e(a["status"]), e(a["context"]),
             ", ".join(study_link(d["by_sid"][s]) for s in a["sids"] if s in d["by_sid"])))
    A('</tbody></table>')
    for a in d["arms"]:
        A('<div class="tm-card"><h3>%s &mdash; %s</h3><p>%s</p>'
          % (a["label"], e(a["status"].lower()), e(a["note"])))
        A('<p class="tm-meta">Routes through this arm:</p><p class="tm-ids">%s</p></div>'
          % "<br>".join(_loop_text(c) for c in a["cycles"]))
    A('</div>')
    A('<p>&ldquo;Followed in time&rdquo; means at least one study linked to the arm '
      'reports a time series, a cell-cycle-resolved or a 24-hour measurement. It '
      'says nothing about whether the arm oscillates.</p>')
    return "\n".join(P)


# ===========================================================================
# /pathway/timing/pattern/ -- otevřená otázka "pattern vs average"
# ---------------------------------------------------------------------------
# Kurátorované věty (co studie ukázala) jsou tu ručně, protože jde o výklad,
# ne o číslo. Všechno ostatní se počítá: seznam modelů bere Signal_Readout,
# průnik s Oliverovým seznamem bere oliver_bio_baked.json. Každé sid musí v
# korpusu existovat, jinak build spadne -- stránka nesmí odkazovat do prázdna.
# ===========================================================================

PATTERN_CFG = {
    "out": "pathway/timing/pattern",
    "url": SITE + "/pathway/timing/pattern/",
    "oliver": "atlas_data/oliver_bio_baked.json",
}

MOVES = [
    ("JOS2024", "In human and mouse cell lines, mTORC1 activity was lowest in mitosis and G1 and "
                "highest in S and G2, set through the TSC complex and independently of Akt and Mek/Erk."),
    ("WANG2026C", "WANG2026C, a live recording platform reporting mTOR-driven transcription rather than "
                  "mTORC1 kinase activity, saw the same cell-cycle pattern in synchronised HEK293T cells, "
                  "with a different method from JOS2024 but explicitly following it up."),
    ("RAM2018", "Starts from mTOR activity oscillating over 24 hours in many tissues, then shows that mTOR "
                "in turn sets the period and amplitude of the clock in cells, ex vivo tissue and mice."),
    ("OKA2013", "In mouse kidney tumours, phosphorylated mTOR followed a 24-hour rhythm, driven by the clock "
                "through the ubiquitin ligase Fbxw7."),
    ("LIP2015", "S6K1, downstream of mTORC1, phosphorylated the clock protein BMAL1 rhythmically, and protein "
                "synthesis rates oscillated over the day in a BMAL1-dependent way."),
]
TOOLS = [
    ("ZHO2015", "TORCAR, the first genetically encoded reporter of mTORC1 kinase activity (FRET)."),
    ("BOU2020", "AIMTOR, a bioluminescence reporter with versions for separate compartments."),
    ("GIN2026", "A way to read how a signal changes over time from still images of many cells."),
]
OUTCOME = [
    ("KUB2012", "A pulse of insulin and a sustained dose became transient and sustained AKT signals, and S6K "
                "answered only the transient one. Same molecules, different pattern, different output. One step "
                "upstream of mTORC1, in a rat liver cell line."),
    ("KUB2018", "The same selective decoding held in rat liver in vivo, with insulin delivered in different "
                "time patterns."),
    ("JOS2024", "Cells in G1, when mTORC1 is lowest, were more sensitive to autophagy induction from the same "
                "partial inhibition or nutrient drop. When in the cycle it happened changed the outcome."),
    ("GIN2026", "Feedback on AKT acted only in a narrow window around G1/S rather than all the time."),
    ("OKA2013", "Everolimus given when tumour mTOR was at its daily peak improved survival of tumour-bearing mice."),
    ("ARR2015", "Weekly or every-fifth-day rapamycin spared glucose tolerance and immune function that daily "
                "dosing impaired, while still inhibiting mTORC1. A schedule imposed from outside, and side "
                "effects rather than benefit."),
    ("LIP2017", "In tuberous sclerosis mice, where mTOR is constantly on, the circadian clock kept time poorly; "
                "lowering BMAL1 rescued the behavioural rhythm."),
]
MODELS = {
    "DAL2012": "fits the insulin-mTORC1 feedback loop onto PI3K as a dynamical system, tested against cell data",
    "DAL2016": "models the first minutes after amino acids return, when AMPK and mTOR switch on together",
    "GUE2020": "proposes how mTORC1 could set the period and amplitude of the circadian clock",
    "LU2026": "treats mTORC1 as a rhythm driven by the timing and quality of amino acid intake",
    "GOR2026": "simulates rapamycin among other drugs in a whole-body ageing model; it is not about mTORC1 dynamics",
}
MISSING = [
    ("The decisive experiment",
     "No study in this atlas holds the average mTORC1 activity constant while changing only its pattern "
     "&mdash; pulses against a steady level with the same time-average &mdash; and then measures autophagy "
     "or growth. Until that is done, every result above is compatible with the average still being what "
     "counts."),
    ("The loops, watched live",
     "None of the feedback arms on the map has been followed in living cells. The only arm with "
     "time-resolved evidence in unperturbed cells is S6K1 to IRS1, and it comes from fixed-cell "
     "reconstruction (GIN2026) and from population time courses fitted as a model (DAL2012), not "
     "from live imaging."),
    ("Humans",
     "Every measurement of mTORC1's own rhythm in this atlas comes from cell lines or mice. No human study "
     "here follows mTORC1 activity over the cell cycle or the day."),
    ("From cell to organism",
     "Whether cell-level oscillation connects to ageing or lifespan is untested in this atlas. The nearest "
     "link is indirect: KHA2014 found higher mTORC1 activity in mice lacking the clock protein BMAL1, and "
     "rapamycin extended their lifespan."),
]


def _need(sid, by_sid):
    if sid not in by_sid:
        raise SystemExit("build_timing_page (pattern): %s není v korpusu" % sid)
    return by_sid[sid]


def _short(t, n=110):
    t = (t or "").strip()
    if len(t) <= n:
        return t
    return t[:n].rsplit(" ", 1)[0].rstrip(",;:") + "\u2026"


def _card(sid, text, by_sid):
    s = _need(sid, by_sid)
    return ('<div class="tm-card"><h3>%s &mdash; %s (%s)</h3><p>%s</p>'
            '<p class="tm-meta">%s &middot; %s</p></div>'
            % (study_link(s), e(_short(s.get("title"))), e(str(s.get("year") or "")),
               text, e(s.get("model") or ""), e(s.get("tier") or "")))


def load_oliver_sids():
    p = os.path.join(HERE, PATTERN_CFG["oliver"])
    if not os.path.exists(p):
        return []
    d = json.load(io.open(p, encoding="utf-8-sig"))
    return [f.get("sid") for f in d.get("focus_studies", []) if f.get("sid")]


def render_pattern(m):
    d = m["dyn"]
    by_sid = d["by_sid"]
    cited = set()
    P = []
    A = P.append
    A(pv_style())  # uvnitř .wrap kvůli V2 (sync_prose), viz INTERAKTIVNÍ VRSTVA
    A('<h1>Does the pattern matter more than the average?</h1>')
    A('<p class="tm-lead">Most experiments on mTOR measure how much of it is active: '
      'more after a meal, less after rapamycin. But inside a single cell, mTORC1 '
      'activity is not a fixed level. It rises and falls with the cell cycle and with '
      'the time of day. The open question is whether that pattern over time &mdash; '
      'not just the average &mdash; is what decides outcomes like autophagy or growth.</p>')
    A('<p class="tm-lead">This page sorts the evidence in this atlas into three piles: '
      'what has been measured, what has only been modelled, and what nobody has done yet.</p>')

    A('<div class="tm-caveat"><b>The short answer.</b> mTORC1 activity is patterned in time, '
      'driven by the cell cycle and by the daily clock, and in a few cases the timing of a signal changes what the cell does. Whether the '
      'pattern matters <em>more</em> than the average has not been tested directly by any '
      'study in this atlas.</div>')

    A(pv_box("wave", "Same average. Different pattern.", hidden=False, inner=pv_verdict_html(),
             schem="Schematic, not data"))
    A(pv_box("ladder", "How far up the evidence goes",
             sub="Each rung needs the one below it. Click a rung to see the studies."))

    A('<h2 id="moves">Measured: mTORC1 activity is patterned in time</h2>')
    A(pv_box("clocks", "Two clocks mTORC1 keeps time with", sub="Click a phase or a study.",
             schem="Shading shows low versus high only (JOS2024). Phase lengths are not to scale, "
                   "and the daily peak differs between tissues."))
    for sid, t in MOVES:
        A(_card(sid, t, by_sid)); cited.add(sid)
    A('<p>What made this measurable is a small set of reporters:</p><ul>')
    for sid, t in TOOLS:
        _need(sid, by_sid); cited.add(sid)
        A('<li>%s &mdash; %s</li>' % (study_link(by_sid[sid]), t))
    A('</ul>')

    A('<h2 id="outcome">Measured: timing changes the outcome</h2>')
    A('<p>These are the results closest to the question. None of them isolates pattern '
      'from average, and several are one step removed from mTORC1 itself &mdash; each '
      'card says how.</p>')
    for sid, t in OUTCOME:
        A(_card(sid, t, by_sid)); cited.add(sid)

    A('<h2 id="modelled">Modelled, not measured</h2>')
    A('<p>Studies whose readout is a mathematical model. They propose mechanisms and make '
      'predictions; they do not show that a cell behaves that way.</p><ul>')
    models = sorted((s for s in d["with_rd"] if "Model" in s["readout"]), key=lambda x: x["sid"])
    pure = [s for s in models if not set(s["readout"]) & TIME_MEASURED]
    mixed = [s for s in models if set(s["readout"]) & TIME_MEASURED]
    for s in pure:
        note = MODELS.get(s["sid"], "")
        A('<li>%s%s</li>' % (study_link(s), (" &mdash; " + e(note)) if note else ""))
        cited.add(s["sid"])
    A('</ul>')
    if mixed:
        A('<p>%d more pair a model with their own time-course data, so they count as measured: %s.</p>'
          % (len(mixed), ", ".join(study_link(s) for s in mixed)))
        cited.update(s["sid"] for s in mixed)

    A(pv_box("matrix", "Where the evidence sits",
             sub="Studies on this page by what they show and in what system. An empty column is "
                 "a finding, not a gap in the drawing."))

    A('<h2 id="missing">Missing</h2>')
    # Věta v MISSING[1] jmenuje jedinou větev sledovanou v čase; musí souhlasit
    # s tím, co spočítá /timing/ (audit 21. 9. 2026: stránky si odporovaly).
    followed = [a["key"] for a in d["arms"] if a["status"] == "Followed in time"]
    if followed != ["S6K1-IRS1"]:
        raise SystemExit("build_timing_page (pattern): věty v MISSING tvrdí, že v čase je "
                         "sledovaná jen větev S6K1-IRS1, ale výpočet dává %s. Oprav MISSING." % followed)
    for head, text in MISSING:
        A('<div class="tm-card"><h3>%s</h3><p>%s</p></div>' % (head, text))
    _need("KHA2014", by_sid); cited.add("KHA2014")
    A('<p>The feedback loops that could make mTORC1 pulse are laid out, arm by arm, on the '
      '<a href="%s/pathway/timing/#signal">timing page</a>.</p>' % SITE)

    oliver = [x for x in load_oliver_sids() if x in by_sid]
    if oliver:
        on = [x for x in oliver if x in cited]
        A('<h2 id="reading-list">On Oliver&rsquo;s reading list</h2>')
        A('<p>This is the question behind the curator&rsquo;s own <a href="%s/author/oliver-barton/">reading '
          'list</a>. %d of its %d studies appear on this page: %s.</p>'
          % (SITE, len(on), len(oliver), ", ".join(study_link(by_sid[x]) for x in on)))

    A('<h2 id="method">Method</h2>')
    A('<p>Every study cited here is in the atlas corpus and links to its record, where the '
      'abstract and evidence grade can be checked. Which pile a study sits in comes from its '
      'recorded readout type (Signal_Readout), which is set only where the abstract or methods '
      'show it. The one-line summaries are the curator&rsquo;s reading of each abstract. '
      'The build fails if any cited study leaves the corpus.</p>')
    A('<p>Data are CC&nbsp;BY&nbsp;4.0 &mdash; see <a href="%s/data/">Data &amp; Citation</a>.</p>' % SITE)
    A(pv_script(pattern_viz_data(d, pure, load_oliver_sids())))
    return "\n".join(P), cited


def build_pattern(m, dry_run=False):
    body, cited = render_pattern(m)
    desc = ("Does the pattern of mTORC1 activity over time matter more than its average level? "
            "What has been measured, what has only been modelled, and what is missing, from %d "
            "studies in Oliver's mTOR Atlas." % len(cited))
    today = datetime.date.today().isoformat()
    url = PATTERN_CFG["url"]
    ld = [{
        "@context": "https://schema.org", "@type": "Report",
        "name": "Does the pattern of mTORC1 activity matter more than the average?",
        "url": url, "description": desc, "dateModified": today,
        "isBasedOn": SITE + "/data/",
        "author": {"@type": "Person", "name": "Oliver Barton"},
        "license": "https://creativecommons.org/licenses/by/4.0/",
        "inLanguage": "en",
    }, {
        "@context": "https://schema.org", "@type": "BreadcrumbList",
        "itemListElement": [
            {"@type": "ListItem", "position": 1, "name": "Oliver's mTOR Atlas", "item": SITE + "/"},
            {"@type": "ListItem", "position": 2, "name": "Pathway", "item": SITE + "/pathway/"},
            {"@type": "ListItem", "position": 3, "name": "Timing", "item": CFG["url"]},
            {"@type": "ListItem", "position": 4, "name": "Pattern vs average", "item": url},
        ],
    }]
    html = shell(
        title="Does the pattern of mTORC1 activity matter more than the average? — Oliver's mTOR Atlas",
        desc=desc, canonical=url, jsonld=ld, body=body,
        breadcrumb="Oliver's mTOR Atlas · Pathway · Timing · <b>Pattern vs average</b>",
        active_tab="map", extra_css="",
    )
    _check_tags(html, url)
    print("pattern: %d citovaných studií" % len(cited))
    if not dry_run:
        _write(PATTERN_CFG["out"], html)
    return html


def _check_tags(html, url):
    bad = []
    if "G-420TPC8J46" not in html:
        bad.append("chybí GA4 tag")
    if 'rel="canonical"' not in html:
        bad.append("chybí canonical")
    if url not in html:
        bad.append("canonical neukazuje na " + url)
    if bad:
        raise SystemExit("build_timing_page: " + "; ".join(bad) + " (" + url + ")")


def _write(rel, html):
    out_dir = os.path.join(HERE, *rel.split("/"))
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, "index.html")
    tmp = path + ".tmp"
    with io.open(tmp, "w", encoding="utf-8", newline="\n") as f:
        f.write(html)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)
    print("zapsáno: %s (%d znaků)" % (path, len(html)))


def build(dry_run=False):
    m = compute()
    body = render(m)
    td = m["td"]
    n_edges = len(m["edges"])

    desc = ("How mTOR interventions were delivered over time, and which pathway links "
            "depend on it: %d studies with a recorded regimen, %d that tested an "
            "intermittent schedule, and %d of %d links with no recorded time dependence in this Atlas."
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
        active_tab="map", extra_css="",
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
    build_pattern(m, dry_run=dry_run)
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
    d = m["dyn"]
    print("čtení signálu:     %d studií (%d sleduje signál v čase)" % (len(d["with_rd"]), len(d["measured"])))
    print("negativní smyčky:  %d cest přes %d větví" % (len(d["loops"]), len(d["arms"])))
    for a in d["arms"]:
        print("   %-12s %2d cest  %s" % (a["key"], len(a["cycles"]), a["status"]))
    print("hrany:")
    for t in TIMEDEP:
        n = m["td"].get(t, 0)
        if n:
            print("   %-26s %d" % (t, n))



# ===========================================================================
# INTERAKTIVNÍ VRSTVA (21. 9. 2026, "pět prvků", návrh
# claude/timing-pattern-vizualizace-navrh-2026-09-21.md)
# ---------------------------------------------------------------------------
#   /pattern/: 1 same average / different pattern, 2 evidence ladder,
#              3 two clocks, 4 evidence matrix
#   /timing/#signal: 5 feedback loop flower
# PRAVIDLA
#  - Bez JS se nic neztratí: karty a tabulky zůstávají v HTML (SEO, llms.txt,
#    čtečky). Grafika je vrstva nad nimi. Jediná výjimka: tabulka větví a
#    karty tras na /timing/ se po vykreslení květu schovají (hidden) -- květ
#    nese totéž včetně tras. Bez JS zůstanou vidět.
#  - JS nic nepočítá. Všechna čísla a texty jdou z Pythonu v JSON bloku
#    #pv-data, stejnými funkcemi jako zbytek stránky.
#  - CSS a JS jsou UVNITŘ obsahu (.wrap), ne v <head>: Atlas_v2
#    scripts/sync_prose.py přebírá jen .wrap. Dřív CSS šlo přes
#    shell(extra_css=) a ve V2 proto tm-* třídy neměly styl vůbec.
#  - Barvy jen přes --teal/--amber/--soft (brand), nikdy --tier-*/--t-*
#    (check_tier_palette.py pravidlo 6).
#  - Schéma není data: vlna i stínování hodin nesou štítek "Schematic".
# ===========================================================================

# Studie, které drží průměrnou aktivitu mTORC1 stejnou a mění jen vzorec
# (pulzy vs. ustálená hladina) a měří autofagii/růst. Dnes žádná. Až
# přibude, patří sem -- verdikt "Not tested" i žebřík se otočí samy.
DECISIVE = []

# V jakém systému studie měřila. Ruční kurátorské přiřazení (pole Model je
# volný text); build spadne, když citovaná studie v mapě chybí, místo aby
# ji tiše zařadil do buněk.
SYSTEM = {
    "JOS2024": "Cell lines", "WANG2026C": "Cell lines", "GIN2026": "Cell lines",
    "KUB2012": "Cell lines",
    "RAM2018": "Animals", "OKA2013": "Animals", "LIP2015": "Animals",
    "KUB2018": "Animals", "ARR2015": "Animals", "LIP2017": "Animals",
    "KHA2014": "Animals",
}
SYSTEM_COLS = ["Cell lines", "Animals", "Humans", "In silico"]

KHA_TEXT = ("Indirect only: mice lacking the clock protein BMAL1 had higher mTORC1 activity, "
            "and rapamycin extended their lifespan.")

# Buněčný cyklus: (fáze, podíl kruhu -- jen schéma, mTORC1 vysoko?, text, studie)
CC_PHASES = [
    ("G1", 0.40, False, "<b>G1: mTORC1 low.</b> Cells here were more sensitive to autophagy "
     "induction from the same partial inhibition or nutrient drop.", ["JOS2024"]),
    ("S", 0.30, True, "<b>S: mTORC1 high.</b> Activity rises through S, set through the TSC "
     "complex and independently of Akt and Mek/Erk.", ["JOS2024"]),
    ("G2", 0.20, True, "<b>G2: mTORC1 high.</b> High activity here promotes entry into mitosis.",
     ["JOS2024"]),
    ("M", 0.10, False, "<b>Mitosis: mTORC1 lowest.</b> Also seen with a different method, a "
     "readout of mTOR-driven transcription (WANG2026C, a follow-up of JOS2024).", ["JOS2024", "WANG2026C"]),
]
CC_BOUNDARY = ("G1/S", "<b>The G1/S window.</b> Feedback on AKT acted only in a narrow window "
               "here, reconstructed from fixed single-cell images.", ["GIN2026"])

_NUM = {2: "Two", 3: "Three", 4: "Four", 5: "Five", 6: "Six"}

PV_CSS = r""".pv{--pv-acc:var(--teal,#A31F34);--pv-mod:var(--amber,#A56827);--pv-miss:var(--soft,#8A857E);
  --pv-soft:var(--soft,#55524C);--pv-ink:var(--ink,#0A0A0A);--pv-bg:var(--paper,#fff);
  --pv-line:var(--line,rgba(0,0,0,.13));--pv-mono:var(--font-mono,'IBM Plex Mono',ui-monospace,SFMono-Regular,Menlo,monospace);
  --pv-grid:color-mix(in srgb,var(--pv-ink) 8%,transparent);
  --pv-wash:color-mix(in srgb,var(--pv-ink) 4%,transparent);
  --pv-acc-wash:color-mix(in srgb,var(--pv-acc) 16%,transparent);
  border:1px solid var(--pv-line);border-radius:10px;padding:20px;margin:24px 0;color:var(--pv-ink)}
.pv-title{font-size:1.15rem;font-weight:700;line-height:1.3;margin:0 0 4px}
.pv-sub{font-size:.9rem;opacity:.85;margin:0 0 12px;max-width:62ch}
.pv-schem{font-family:var(--pv-mono);font-size:10.5px;letter-spacing:.05em;text-transform:uppercase;color:var(--pv-soft);margin:12px 0 0}
.pv svg{display:block;max-width:100%;height:auto}
.pv-scroll{overflow-x:auto}
.pv-ctrl{display:flex;flex-wrap:wrap;align-items:center;gap:10px 16px;margin:10px 0 4px}
.pv-ctrl label{font-size:.85rem;color:var(--pv-soft)}
.pv-ctrl input[type=range]{accent-color:var(--pv-acc);width:220px;max-width:100%}
.pv button.pv-btn,.pv button.pv-pill,.pv button.pv-rung{font:inherit;color:var(--pv-ink);cursor:pointer;background:var(--pv-bg)}
.pv button.pv-btn{border:1px solid var(--pv-line);background:var(--pv-wash);border-radius:4px;padding:5px 12px;font-size:.85rem}
.pv button.pv-btn:hover{border-color:var(--pv-acc)}
.pv :focus-visible{outline:2px solid var(--pv-acc);outline-offset:2px}
.pv-stats{display:flex;gap:26px;flex-wrap:wrap;font-variant-numeric:tabular-nums;margin-top:6px}
.pv-stat .n{font-size:1.5rem;font-weight:700;line-height:1.1}
.pv-stat .l{font-size:.78rem;color:var(--pv-soft)}
.pv-verdict{margin:16px 0 0;padding:12px 14px;border:1.5px dashed var(--pv-miss);border-radius:6px;font-size:.93rem;max-width:none}
.pv-verdict b{color:var(--pv-acc)}
.pv-ladder{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:10px}
@media (max-width:640px){.pv-ladder{grid-template-columns:1fr 1fr}}
.pv button.pv-rung{text-align:left;border:1.5px solid var(--pv-line);border-radius:6px;padding:12px;display:flex;flex-direction:column;gap:6px;min-height:118px}
.pv-rung .st{font-family:var(--pv-mono);font-size:10px;letter-spacing:.06em;text-transform:uppercase}
.pv-rung .q{font-weight:700;font-size:.95rem;line-height:1.25}
.pv-rung .c{font-size:.8rem;color:var(--pv-soft);margin-top:auto}
.pv button.pv-rung.m{border-color:var(--pv-acc);background:var(--pv-acc-wash)}
.pv button.pv-rung.p{border-color:var(--pv-acc)}
.pv-rung.m .st,.pv-rung.p .st{color:var(--pv-acc)}
.pv button.pv-rung.x{border-style:dashed;border-color:var(--pv-miss)}
.pv-rung.x .st{color:var(--pv-miss)}
.pv button.pv-rung[aria-pressed="true"]{box-shadow:0 0 0 2px var(--pv-ink) inset}
.pv-panel{margin-top:14px;border-top:1px solid var(--pv-line);padding-top:12px;font-size:.9rem}
.pv-row{display:grid;grid-template-columns:96px minmax(0,1fr);gap:12px;padding:7px 0;border-bottom:1px solid var(--pv-grid)}
.pv a.pv-sid,.pv-more a{color:var(--pv-acc)}
.pv-sid{font-family:var(--pv-mono);font-weight:600;font-size:.8rem}
.pv-sys{display:block;font-family:var(--pv-mono);font-size:10px;color:var(--pv-soft)}
.pv-more,.pv-side{font-size:.83rem;color:var(--pv-soft);margin:10px 0 0}
.pv-mod-t{color:var(--pv-mod)}
.pv-clocks{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:20px}
@media (max-width:640px){.pv-clocks{grid-template-columns:1fr}}
.pv-clock svg{max-width:300px;margin:6px auto 0}
.pv-h{display:block;font-size:.98rem;margin-bottom:4px}
.pv-seg{cursor:pointer}
.pv-seg:hover{opacity:.8}
.pv-cap{min-height:5em;font-size:.87rem;border-top:1px solid var(--pv-line);padding-top:10px;margin-top:8px}
.pv-pills{display:flex;flex-wrap:wrap;gap:6px;justify-content:center;margin-top:6px}
.pv button.pv-pill{border:1px solid var(--pv-line);border-radius:999px;padding:2px 10px;font-family:var(--pv-mono);font-size:11px}
.pv button.pv-pill[aria-pressed="true"]{border-color:var(--pv-acc);color:var(--pv-acc)}
.pv table.pv-mx{border-collapse:separate;border-spacing:6px;width:100%;min-width:560px;margin:0;font-size:.85rem}
.pv table.pv-mx th,.pv table.pv-mx td{border-bottom:0;background:none}
.pv table.pv-mx th{font-family:var(--pv-mono);font-size:10.5px;letter-spacing:.05em;text-transform:uppercase;color:var(--pv-soft);font-weight:500;text-align:left;padding:0 4px}
.pv table.pv-mx th.rh{font-family:inherit;text-transform:none;letter-spacing:0;font-size:.85rem;color:var(--pv-ink);font-weight:600;width:150px;vertical-align:middle}
.pv table.pv-mx td{vertical-align:top;border-radius:4px;padding:8px;background:var(--pv-wash);height:60px}
.pv table.pv-mx td.none{background:none;border:1.5px dashed var(--pv-miss);color:var(--pv-miss);font-size:.78rem;font-style:italic}
.pv a.pv-chip{display:inline-block;margin:2px;padding:2px 7px;border-radius:3px;font-family:var(--pv-mono);font-size:10.5px;font-weight:600;color:var(--pv-bg);background:var(--pv-acc);text-decoration:none;transition:opacity .2s,box-shadow .2s}
.pv a.pv-chip.mo{background:var(--pv-mod)}
.pv .dim a.pv-chip{opacity:.22}
.pv .dim a.pv-chip.ol{opacity:1;box-shadow:0 0 0 2px var(--pv-bg),0 0 0 3.5px var(--pv-ink)}
.pv-toggle{display:inline-flex;align-items:center;gap:8px;font-size:.87rem;cursor:pointer;margin-bottom:8px}
.pv-loops{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:20px;align-items:start}
@media (max-width:640px){.pv-loops{grid-template-columns:1fr}}
.pv-loops>svg{max-width:380px;margin:0 auto}
.pv-hit{cursor:pointer}
.pv-lp{font-size:.88rem}
.pv-lp .st{font-family:var(--pv-mono);font-size:10.5px;text-transform:uppercase;letter-spacing:.06em;margin-bottom:6px}
.pv-lp .pv-solid,.pv-lp .pv-dash{color:var(--pv-acc)}
.pv-lp .pv-model{color:var(--pv-mod)}
.pv-lp .pv-grey{color:var(--pv-miss)}
.pv-n{font-weight:400;color:var(--pv-soft);font-size:.85rem}
.pv-note{color:var(--pv-soft)}
.pv-routes{margin-top:10px}
.pv-routes summary{cursor:pointer;font-size:.85rem}
.pv-lkey{display:flex;flex-direction:column;gap:5px;font-size:.8rem;color:var(--pv-soft);margin-top:12px}
.pv-lkey span{display:flex;align-items:center;gap:8px}
.pv-lkey svg{flex:none;width:28px;height:6px;margin:0}
@media (prefers-reduced-motion: reduce){.pv *{transition:none!important}}
"""

PV_JS = r"""(function(){
var src=document.getElementById('pv-data');if(!src)return;
var D;try{D=JSON.parse(src.textContent);}catch(err){return;}
var NS='http://www.w3.org/2000/svg',XL='http://www.w3.org/1999/xlink',TAU=Math.PI*2;
var reduce=!!(window.matchMedia&&window.matchMedia('(prefers-reduced-motion: reduce)').matches);
function el(t,a,p){var n=document.createElementNS(NS,t);for(var k in a){if(k==='fill'||k==='stroke')n.style[k]=a[k];else n.setAttribute(k,a[k]);}if(p)p.appendChild(n);return n;}
function txt(p,x,y,s,a){a=a||{};a.x=x;a.y=y;if(!a.fill)a.fill='var(--pv-ink)';var n=el('text',a,p);n.textContent=s;return n;}
function h(t,c,html){var n=document.createElement(t);if(c)n.className=c;if(html!=null)n.innerHTML=html;return n;}
function sid(s){return '<a class="pv-sid" href="/study/'+s+'/">'+s+'</a>';}
function box(k){return document.querySelector('.pv[data-pv="'+k+'"]');}
function act(n,fn){n.addEventListener('click',fn);n.addEventListener('keydown',function(e){if(e.key==='Enter'||e.key===' '){e.preventDefault();fn();}});}
function role(n,label){n.setAttribute('tabindex','0');n.setAttribute('role','button');n.setAttribute('aria-label',label);}
function press(on,list){for(var j=0;j<list.length;j++)list[j].setAttribute('aria-pressed',j===on?'true':'false');}
function safe(f){try{f();}catch(err){if(window.console)console.warn('pv:',err);}}

/* 1. Same average, different pattern */
safe(function(){var b=box('wave');if(!b)return;
 var L=40,R=620,T=20,B=180,AVG=.28,DUTY=.35,E=.06,PER=4;
 var svg=el('svg',{viewBox:'0 0 640 220',role:'img','aria-label':'Schematic: a steady signal turning into pulses with the same average'});
 function y(v){return B-(B-T)*v;}
 el('line',{x1:L,y1:B,x2:R,y2:B,stroke:'var(--pv-line)'},svg);
 el('line',{x1:L,y1:T,x2:R,y2:T,stroke:'var(--pv-grid)'},svg);
 txt(svg,L-6,B+4,'0',{'text-anchor':'end','font-size':11,fill:'var(--pv-soft)'});
 txt(svg,L-6,T+4,'max',{'text-anchor':'end','font-size':11,fill:'var(--pv-soft)'});
 var area=el('path',{fill:'var(--pv-acc-wash)',stroke:'none'},svg);
 var line=el('path',{fill:'none',stroke:'var(--pv-acc)','stroke-width':2.2,'stroke-linejoin':'round'},svg);
 el('line',{x1:L,y1:y(AVG),x2:R,y2:y(AVG),stroke:'var(--pv-ink)','stroke-dasharray':'6 5','stroke-width':1.4},svg);
 txt(svg,R,y(AVG)-7,'average',{'text-anchor':'end','font-size':11.5,'font-weight':600});
 txt(svg,(L+R)/2,B+30,'time →',{'text-anchor':'middle','font-size':11,fill:'var(--pv-soft)'});
 var sc=h('div','pv-scroll');sc.appendChild(svg);
 var ctrl=h('div','pv-ctrl','<label for="pv-morph">steady</label><input type="range" id="pv-morph" min="0" max="100" value="70"><label for="pv-morph">pulsed</label><button class="pv-btn" type="button">Play</button>');
 var stats=h('div','pv-stats','<div class="pv-stat"><div class="n">'+Math.round(AVG*100)+' %</div><div class="l">time-average</div></div><div class="pv-stat"><div class="n pv-peak"></div><div class="l">peak</div></div><div class="pv-stat"><div class="n pv-low"></div><div class="l">lowest</div></div>');
 var sub=h('p','pv-sub','Drag the slider. The dashed line, the time-averaged mTORC1 activity, never moves. Only the shape does.');
 var v=b.querySelector('.pv-verdict');[sub,sc,ctrl,stats].forEach(function(n){b.insertBefore(n,v);});
 function pulse(t){var ph=(t*PER)%1;if(ph<E)return ph/E;if(ph<DUTY-E)return 1;if(ph<DUTY)return (DUTY-ph)/E;return 0;}
 var pk=stats.querySelector('.pv-peak'),lo=stats.querySelector('.pv-low');
 function draw(m){var pts=[];for(var i=0;i<=320;i++){var t=i/320,val=(1-m)*AVG+m*pulse(t)*AVG/(DUTY-E);pts.push((L+(R-L)*t).toFixed(1)+','+y(val).toFixed(1));}
  var d='M'+pts.join('L');line.setAttribute('d',d);area.setAttribute('d',d+'L'+R+','+B+'L'+L+','+B+'Z');
  pk.textContent=Math.round(((1-m)*AVG+m*AVG/(DUTY-E))*100)+' %';lo.textContent=Math.round((1-m)*AVG*100)+' %';}
 var sl=ctrl.querySelector('input'),btn=ctrl.querySelector('button'),playing=false,raf=0;
 sl.addEventListener('input',function(){draw(sl.value/100);});
 btn.addEventListener('click',function(){
  if(reduce){sl.value=sl.value>50?0:100;draw(sl.value/100);return;}
  if(playing){playing=false;cancelAnimationFrame(raf);btn.textContent='Play';return;}
  playing=true;btn.textContent='Pause';var t0=null,ph0=Math.acos(1-2*(sl.value/100));
  function step(ts){if(t0===null)t0=ts;var m=(1-Math.cos(ph0+(ts-t0)/2200*Math.PI))/2;sl.value=Math.round(m*100);draw(m);if(playing)raf=requestAnimationFrame(step);}
  raf=requestAnimationFrame(step);});
 draw(.7);});

/* 2. Evidence ladder */
safe(function(){var b=box('ladder');if(!b||!D.ladder)return;
 var lad=h('div','pv-ladder'),pan=h('div','pv-panel'),btns=[];b.appendChild(lad);b.appendChild(pan);
 function open(i){press(i,btns);var r=D.ladder[i],s='';
  if(r.empty)s+='<p>'+r.empty+'</p>';
  r.rows.forEach(function(x){s+='<div class="pv-row"><div>'+sid(x[0])+'<span class="pv-sys">'+x[1]+'</span></div><div>'+x[2]+'</div></div>';});
  if(r.anchor)s+='<p class="pv-more"><a href="#'+r.anchor+'">Full cards below &darr;</a></p>';
  if(D.models&&D.models.length)s+='<p class="pv-side">Side pile, <b class="pv-mod-t">modelled only</b>: '+D.models.map(sid).join(', ')+'. They propose mechanisms; they do not show a cell doing it.</p>';
  pan.innerHTML=s;}
 D.ladder.forEach(function(r,i){var x=h('button','pv-rung '+r.k,'<span class="st">'+(i+1)+' &middot; '+r.st+'</span><span class="q">'+r.q+'</span><span class="c">'+r.c+'</span>');
  x.type='button';x.setAttribute('aria-pressed','false');x.addEventListener('click',function(){open(i);});lad.appendChild(x);btns.push(x);});
 open(Math.min(1,D.ladder.length-1));b.hidden=false;});

/* 3. Two clocks */
safe(function(){var b=box('clocks');if(!b||!D.clocks)return;
 var C=D.clocks,g=h('div','pv-clocks');b.insertBefore(g,b.querySelector('.pv-schem'));
 function arc(cx,cy,r0,r1,a0,a1){function p(r,a){return (cx+r*Math.sin(a)).toFixed(1)+','+(cy-r*Math.cos(a)).toFixed(1);}
  var l=(a1-a0)>Math.PI?1:0;return 'M'+p(r1,a0)+'A'+r1+','+r1+' 0 '+l+' 1 '+p(r1,a1)+'L'+p(r0,a1)+'A'+r0+','+r0+' 0 '+l+' 0 '+p(r0,a0)+'Z';}
 function cite(t,ids){return t+' '+ids.map(sid).join(', ');}
 var c1=h('div','pv-clock','<b class="pv-h">Cell cycle</b>'),cc=el('svg',{viewBox:'0 0 300 300',role:'img','aria-label':'Cell cycle ring shaded by low or high mTORC1 activity'}),cap=h('div','pv-cap');
 c1.appendChild(cc);c1.appendChild(cap);g.appendChild(c1);
 var a=0;C.phases.forEach(function(p){var a1=a+p.f*TAU,mid=(a+a1)/2;
  var seg=el('path',{d:arc(150,150,78,124,a+.012,a1-.012),fill:p.hi?'var(--pv-acc)':'var(--pv-acc-wash)',stroke:p.hi?'none':'var(--pv-acc)','stroke-width':1.2,'class':'pv-seg'},cc);
  role(seg,p.n);
  txt(cc,150+101*Math.sin(mid),150-101*Math.cos(mid)+5,p.n,{'text-anchor':'middle','font-size':15,'font-weight':700,fill:p.hi?'var(--pv-bg)':'var(--pv-acc)','pointer-events':'none'});
  act(seg,function(){cap.innerHTML=cite(p.t,p.ids);});a=a1;});
 var bd=C.boundary;if(bd){var ga=bd.at*TAU;
  el('line',{x1:150+70*Math.sin(ga),y1:150-70*Math.cos(ga),x2:150+136*Math.sin(ga),y2:150-136*Math.cos(ga),stroke:'var(--pv-ink)','stroke-width':2.5},cc);
  var bl=txt(cc,150+146*Math.sin(ga)+2,150-146*Math.cos(ga)+14,bd.n,{'font-size':10.5,'font-weight':600,'class':'pv-seg'});role(bl,bd.n);
  act(bl,function(){cap.innerHTML=cite(bd.t,bd.ids);});}
 txt(cc,150,146,'mTORC1',{'text-anchor':'middle','font-size':13,'font-weight':700});
 txt(cc,150,163,'through one cycle',{'text-anchor':'middle','font-size':10.5,fill:'var(--pv-soft)'});
 cap.innerHTML=cite(C.phases[0].t,C.phases[0].ids);
 if(C.day&&C.day.length){
  var c2=h('div','pv-clock','<b class="pv-h">24-hour day</b>'),dr=el('svg',{viewBox:'0 0 300 300',role:'img','aria-label':'24-hour ring with a daily rhythm; the peak time depends on the tissue'});c2.appendChild(dr);
  for(var k=0;k<24;k++){var an=k/24*TAU,r1=k%6===0?128:124;el('line',{x1:150+118*Math.sin(an),y1:150-118*Math.cos(an),x2:150+r1*Math.sin(an),y2:150-r1*Math.cos(an),stroke:'var(--pv-soft)','stroke-width':k%6===0?1.5:.8},dr);}
  [0,6,12,18].forEach(function(k){var an=k/24*TAU;txt(dr,150+141*Math.sin(an),150-141*Math.cos(an)+4,k+' h',{'text-anchor':'middle','font-size':10,fill:'var(--pv-soft)'});});
  var rg=el('g',{},dr),NS48=48;for(var i=0;i<NS48;i++){var a0=i/NS48*TAU,a1=(i+1)/NS48*TAU,lv=.5+.5*Math.cos((a0+a1)/2);el('path',{d:arc(150,150,78,112,a0,a1+.004),fill:'var(--pv-acc)','fill-opacity':(.08+.82*lv).toFixed(2),stroke:'none'},rg);}
  if(!reduce)el('animateTransform',{attributeName:'transform',type:'rotate',from:'0 150 150',to:'360 150 150',dur:'40s',repeatCount:'indefinite'},rg);
  txt(dr,150,146,'one cycle a day',{'text-anchor':'middle','font-size':13,'font-weight':700});
  txt(dr,150,163,'peak time varies by tissue',{'text-anchor':'middle','font-size':10.5,fill:'var(--pv-soft)'});
  var pills=h('div','pv-pills'),dc=h('div','pv-cap'),pb=[];c2.appendChild(pills);c2.appendChild(dc);g.appendChild(c2);
  C.day.forEach(function(d,i){var x=h('button','pv-pill',d[0]);x.type='button';x.setAttribute('aria-pressed','false');
   x.addEventListener('click',function(){press(i,pb);dc.innerHTML=sid(d[0])+' '+d[1];});pills.appendChild(x);pb.push(x);});
  pb[0].click();}
 b.hidden=false;});

/* 4. Where the evidence sits */
safe(function(){var b=box('matrix');if(!b||!D.matrix)return;
 var M=D.matrix,ol=D.oliver||[],s='<thead><tr><th></th>'+M.cols.map(function(c){return '<th>'+c+'</th>';}).join('')+'</tr></thead><tbody>';
 M.rows.forEach(function(r){s+='<tr><th class="rh">'+r.label+'</th>';r.cells.forEach(function(c){
  if(c===null){s+='<td class="none">none</td>';return;}
  s+='<td>'+c.map(function(x){return '<a href="/study/'+x+'/" class="pv-chip'+(r.model?' mo':'')+(ol.indexOf(x)>-1?' ol':'')+'">'+x+'</a>';}).join('')+'</td>';});s+='</tr>';});
 var t=h('table','pv-mx',s+'</tbody>'),sc=h('div','pv-scroll');sc.appendChild(t);
 if(ol.length){var lab=h('label','pv-toggle','<input type="checkbox" id="pv-ol"> Highlight Oliver&rsquo;s reading list');b.appendChild(lab);
  lab.querySelector('input').addEventListener('change',function(){t.classList.toggle('dim',this.checked);});}
 b.appendChild(sc);b.hidden=false;});

/* 5. Feedback loop flower */
safe(function(){var b=box('loops');if(!b||!D.arms||!D.arms.length)return;
 var A=D.arms,C=190,wrap=h('div','pv-loops'),svg=el('svg',{viewBox:'0 0 380 380',role:'img','aria-label':'Feedback arms around mTORC1'}),panel=h('div','pv-lp'),paths=[],opens=[];
 wrap.appendChild(svg);wrap.appendChild(panel);b.insertBefore(wrap,b.querySelector('.pv-schem'));
 function rad(d){return d*Math.PI/180;}
 function pt(r,d){return (C+r*Math.sin(rad(d))).toFixed(1)+','+(C-r*Math.cos(rad(d))).toFixed(1);}
 var COL={solid:'var(--pv-acc)',dash:'var(--pv-acc)',model:'var(--pv-mod)',grey:'var(--pv-miss)'};
 var KEYTXT={solid:'followed in unperturbed cells',dash:'followed only after a drug',model:'modelled only',grey:'snapshots only'},seen={},key='<div class="pv-lkey">';
 A.forEach(function(a){if(seen[a.style])return;seen[a.style]=1;key+='<span><svg viewBox="0 0 28 6"><line x1="0" y1="3" x2="28" y2="3" stroke-width="3" style="stroke:'+COL[a.style]+'"'+(a.style==='dash'?' stroke-dasharray="6 4"':'')+'></line></svg>'+KEYTXT[a.style]+'</span>';});
 key+='</div>';
 A.forEach(function(a,i){var ang=-45+i*360/A.length,d='M'+C+','+C+' C'+pt(190,ang-30)+' '+pt(190,ang+30)+' '+C+','+C;
  var p=el('path',{d:d,id:'pv-petal'+i,fill:'none',stroke:COL[a.style],'stroke-width':1.5+a.n*.9,'stroke-linecap':'round'},svg);
  if(a.style==='dash')p.setAttribute('stroke-dasharray','9 6');
  var hit=el('path',{d:d,fill:'none',stroke:'transparent','stroke-width':22,'class':'pv-hit'},svg);role(hit,a.label);
  txt(svg,C+150*Math.sin(rad(ang)),C-150*Math.cos(rad(ang))+(Math.cos(rad(ang))>0?-6:14),a.label,{'text-anchor':'middle','font-size':12,'font-weight':700,'pointer-events':'none'});
  if(!reduce){var dot=el('circle',{r:4.5,fill:COL[a.style]},svg),am=el('animateMotion',{dur:(3.2+i*.5)+'s',repeatCount:'indefinite'},dot),mp=el('mpath',{},am);
   mp.setAttributeNS(XL,'xlink:href','#pv-petal'+i);mp.setAttribute('href','#pv-petal'+i);}
  function open(){for(var j=0;j<paths.length;j++)paths[j].style.opacity=j===i?1:.35;
   panel.innerHTML='<div class="st pv-'+a.style+'">'+a.status+'</div><b class="pv-h">'+a.label_html+' <span class="pv-n">&middot; '+a.n+' route'+(a.n===1?'':'s')+'</span></b><p>'+a.what+'</p><p class="pv-note">'+a.note+'</p><div>'+a.sids.map(sid).join(' &middot; ')+'</div><details class="pv-routes"><summary>Routes through this arm</summary><p class="tm-ids">'+a.routes.join('<br>')+'</p></details>'+key;}
  act(hit,open);paths.push(p);opens.push(open);});
 el('circle',{cx:C,cy:C,r:30,fill:'var(--pv-bg)',stroke:'var(--pv-ink)','stroke-width':1.5},svg);
 txt(svg,C,C+4,'mTORC1',{'text-anchor':'middle','font-size':12,'font-weight':700});
 opens[0]();b.hidden=false;
 var fb=document.querySelectorAll('[data-pv-fallback="loops"]');for(var k=0;k<fb.length;k++)fb[k].hidden=true;});
})();
"""


def pv_style():
    return "<style>\n%s%s</style>" % (CSS, PV_CSS)


def pv_script(data):
    blob = json.dumps(data, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    return ('<script type="application/json" id="pv-data">%s</script>\n<script>%s</script>'
            % (blob, PV_JS))


def _sys(sid):
    if sid not in SYSTEM:
        raise SystemExit("build_timing_page (viz): %s nemá záznam v SYSTEM.\n"
                         "  Doplň, v jakém systému studie měřila (Cell lines / Animals / Humans)." % sid)
    return SYSTEM[sid]


def pv_verdict_html():
    if not DECISIVE:
        return ('<p class="pv-verdict"><b>Not tested.</b> The experiment that would settle the '
                'question holds the average fixed, changes only the shape, and measures autophagy '
                'or growth. No study in this atlas has done it.</p>')
    return ('<p class="pv-verdict"><b>Tested in %d stud%s.</b> See the cards under '
            '<a href="#missing">Missing</a> for what they found and how far it goes.</p>'
            % (len(DECISIVE), "y" if len(DECISIVE) == 1 else "ies"))


def pattern_viz_data(d, pure_models, oliver):
    by_sid = d["by_sid"]
    for sid in DECISIVE:
        _need(sid, by_sid)
    moves = [[s, _sys(s), t] for s, t in MOVES]
    tools = [[s, "Method", t] for s, t in TOOLS]
    outc = [[s, _sys(s), t] for s, t in OUTCOME]
    dec = [[s, _sys(s), ""] for s in DECISIVE]
    humans = any(r[1] == "Humans" for r in moves + outc)
    ladder = [
        dict(k="m", st="Measured", q="mTORC1 activity is patterned in time",
             c="%d studies &middot; %d reporters" % (len(moves), len(tools)),
             rows=moves + tools, anchor="moves"),
        dict(k="p", st="Measured, partly", q="Timing changes the outcome",
             c="%d studies &middot; %s" % (len(outc), "none isolates pattern" if not DECISIVE
                                             else "see rung 3"),
             rows=outc, anchor="outcome"),
        dict(k="m" if DECISIVE else "x", st="Measured" if DECISIVE else "Not tested",
             q="The pattern beats the average", c="%d studies" % len(DECISIVE), rows=dec,
             empty="" if DECISIVE else MISSING[0][1], anchor="missing"),
        dict(k="p" if humans else "x", st="Measured" if humans else "Missing",
             q="It matters in humans and ageing",
             c="%d human studies &middot; 1 indirect" % (1 if humans else 0),
             rows=[["KHA2014", _sys("KHA2014"), KHA_TEXT]],
             empty="" if humans else MISSING[2][1], anchor="missing"),
    ]
    # Dvoje hodiny: fáze kurátorsky, denní rytmus odvozený ze Signal_Readout.
    at, phases = 0.0, []
    for n, f, hi, t, ids in CC_PHASES:
        for s in ids:
            _need(s, by_sid)
        phases.append(dict(n=n, f=f, hi=hi, t=t, ids=ids))
        if n == "G1":
            at = f
    for s in CC_BOUNDARY[2]:
        _need(s, by_sid)
    day, seen = [], set()
    for s, t in MOVES + OUTCOME:
        if s not in seen and "Circadian" in (by_sid[s].get("readout") or []):
            seen.add(s)
            day.append([s, t])
    clocks = dict(phases=phases, day=day,
                  boundary=dict(n=CC_BOUNDARY[0], t=CC_BOUNDARY[1], ids=CC_BOUNDARY[2], at=at))

    def cells(rows, empty_none=False, model=False):
        out = []
        for col in SYSTEM_COLS:
            if model:
                hit = [s["sid"] for s in pure_models] if col == "In silico" else []
            else:
                hit = list(dict.fromkeys(r[0] for r in rows if r[1] == col))
            out.append(None if (not hit and (empty_none or col == "Humans")) else hit)
        return out
    matrix = dict(cols=SYSTEM_COLS, rows=[
        dict(label="Activity is patterned in time", cells=cells(moves)),
        dict(label="Timing changes the outcome", cells=cells(outc)),
        dict(label="Pattern beats average", cells=cells(dec, empty_none=True)),
        dict(label="Modelled only", cells=cells([], model=True), model=True),
    ])
    return dict(ladder=ladder, clocks=clocks, matrix=matrix,
                models=[s["sid"] for s in pure_models],
                oliver=[s for s in oliver if s in by_sid])


def loops_viz_data(d):
    import html as _html
    out = []
    for a in d["arms"]:
        st, ctx = a["status"], a["context"]
        if st == "Followed in time":
            style = "dash" if "drug" in ctx else "solid"
        elif st == "Modelled only":
            style = "model"
        else:
            style = "grey"
        status = e(st) if ctx == "not followed in time" else "%s &middot; %s" % (e(st), e(ctx))
        out.append(dict(label=_html.unescape(a["label"]), label_html=a["label"], n=len(a["cycles"]),
                        style=style, status=status, what=e(a["what"]), note=e(a["note"]),
                        sids=[s for s in a["sids"] if s in d["by_sid"]],
                        routes=[_loop_text(c) for c in a["cycles"]]))
    return out


def pv_box(key, title, sub="", schem="", hidden=True, inner=""):
    return ('<div class="pv" data-pv="%s"%s><p class="pv-title">%s</p>%s%s%s</div>'
            % (key, " hidden" if hidden else "", title,
               ('<p class="pv-sub">%s</p>' % sub) if sub else "", inner,
               ('<p class="pv-schem">%s</p>' % schem) if schem else ""))


if __name__ == "__main__":
    build(dry_run="--dry-run" in sys.argv)
