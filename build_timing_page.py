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
        context="only after a drug",
        note="Time appears here only as recovery from a drug: ROD2011 saw AKT dip and then come back as "
             "mTOR kinase inhibition released the brake on receptor tyrosine kinases. How this arm behaves "
             "in an unperturbed cell is not recorded in this atlas."),
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
        arm_rows.append(dict(key=k, cycles=cycles, sids=sids,
                             status=arm_status(sids, by_sid), **a))
    return {"with_rd": with_rd, "by_rd": by_rd, "measured": measured,
            "loops": loops, "arms": arm_rows, "by_sid": by_sid}


def _loop_text(c):
    return " &rarr; ".join([e(c[0]["s"])] + [e(x["t"]) for x in c])


def render_dynamics(m):
    d = m["dyn"]
    n_follow = sum(1 for a in d["arms"] if a["status"] == "Followed in time")
    P = []
    A = P.append
    A('<h2 id="signal">How the signal itself moves</h2>')
    A('<p>Everything above is time imposed from outside: how long and how often an '
      'intervention was given. There is a second kind of time, inside the cell. '
      'mTORC1 activity is not a fixed setting; it can rise and fall on its own, '
      'with the cell cycle and with the time of day. Whether that pattern, and not '
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
    ("WANG2026C", "A live-cell recording platform built independently of JOS2024 recorded mTOR activity "
                  "oscillating with the cell cycle."),
    ("RAM2018", "Starts from mTOR activity oscillating over 24 hours in many tissues, then shows that mTOR "
                "in turn sets the period and amplitude of the clock in cells, ex vivo tissue and mice."),
    ("OKA2013", "In mouse kidney tumours, phosphorylated mTOR followed a 24-hour rhythm, driven by the clock "
                "through the ubiquitin ligase Fbxw7."),
    ("LIP2015", "S6K1, downstream of mTORC1, phosphorylated the clock protein BMAL1 rhythmically, and protein "
                "synthesis rates oscillated over the day in a BMAL1-dependent way."),
]
TOOLS = [
    ("ZHO2015", "TORCAR, the first genetically encoded reporter of mTORC1 activity (FRET)."),
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
     "None of the feedback arms on the map has been followed in living cells. The one arm with timing "
     "evidence (S6K1 &rarr; IRS1) was reconstructed from fixed images."),
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
    A('<h1>Does the pattern matter more than the average?</h1>')
    A('<p class="tm-lead">Most experiments on mTOR measure how much of it is active: '
      'more after a meal, less after rapamycin. But inside a single cell, mTORC1 '
      'activity is not a fixed level. It rises and falls with the cell cycle and with '
      'the time of day. The open question is whether that pattern over time &mdash; '
      'not just the average &mdash; is what decides outcomes like autophagy or growth.</p>')
    A('<p class="tm-lead">This page sorts the evidence in this atlas into three piles: '
      'what has been measured, what has only been modelled, and what nobody has done yet.</p>')

    A('<div class="tm-caveat"><b>The short answer.</b> mTORC1 activity does move on its own, '
      'and in a few cases the timing of a signal changes what the cell does. Whether the '
      'pattern matters <em>more</em> than the average has not been tested directly by any '
      'study in this atlas.</div>')

    A('<h2 id="moves">Measured: mTORC1 activity moves on its own</h2>')
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

    A('<h2 id="missing">Missing</h2>')
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
        active_tab="map", extra_css=CSS,
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


if __name__ == "__main__":
    build(dry_run="--dry-run" in sys.argv)
