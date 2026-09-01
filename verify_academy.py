#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
verify_academy.py -- integritni brana pro /academy/.

PROC TOHLE EXISTUJE
-------------------
Academy je jedina cast webu, ktera odkazuje NAPRIC vsemi ostatnimi vrstvami
najednou: na stranky studii (build_pages.py), na stranky entit (jen ty nad
prahem 3 studii!), na open questions (gaps_baked.json) a na guided routes
(pathway/model.json). Kazda z techto vrstev se meni nezavisle. Bez teto brany
staci, aby se entita propadla pod prah nebo se prejmenovala trasa, a lekce
tise odkazuje do prazdna -- presne ten druh chyby, kterou nikdo neuvidi, dokud
na ni nekdo neklikne.

Kontroluje se:
  1  kazdy SID v lessons.json existuje v studies_baked.json
  2  kazda entita (proteins/pathways/processes/organelles/nutrients) existuje
     A MA vlastni stranku (>= PAGE_THRESHOLD studii)
  3  kazda guided route existuje v pathway/model.json
  4  kazdy open-question slug existuje v gaps_baked.json
  5  previousLesson / nextLesson ukazuji na existujici lekci, retez je
     konzistentni s poradim v modules.json
  6  kazdy publikovany lesson slug ma vygenerovanou stranku na disku
  7  vsechny interni odkazy z vygenerovanych academy stranek ukazuji na soubor,
     ktery existuje (mimo hash-routy do SPA)
  8  kazda stranka nese svuj <h1> a sekci Evidence PRIMO V HTML (bez JS)
  9  redakcni minima: >=3 studie na lekci, >=1 think question, neprazdne
     uncertainty nebo openQuestions
 10  proza pouziva jen povolenou inline sadu znacek
 11  minikviz: presne 3 otazky easy/medium/hard, 3-4 moznosti, jedna platna
     spravna odpoved, neprazdne vysvetleni
 12  interaktivni cviceni (Faze 2): learning objectives aktivnimi slovesy,
     research skill ze slovniku, kazdy uzel/hrana modelu existuje
     v pathway/model.json, kazda kombinace prepinacu ma vyjmenovany stav,
     kazde Predict cviceni ma skutecnou studii jako Observe
 13  kazde interaktivni cviceni ma na vygenerovane strance bez-JS ekvivalent
 15  Research Challenges (challenges.json): kazdy SID/uzel/hrana/lekce/route
     existuje, model ma vyjmenovany kazdy stav, soucet nakladu experimentu
     PREVYSUJE rozpocet (jinak by student spustil vsechno) a kazdy vysledek
     je bud odvozeny ze skutecne studie, nebo oznaceny jako hypoteticky
 16  stranka vyzvy ma bez-JS ekvivalent rozpoctu i modelu
 14  beginner uroven: kdyz ma lekce zkracenou verzi core idea, MUSI ji mit
     i kazda ne-caution sekce -- jinak by ctenar na urovni beginner videl
     misto sekce prazdno; caution sekce beginner verzi mit NESMI

Usage: python verify_academy.py     (exit 0 = OK, 1 = nalezy)
"""

import os
import re
import sys
import json

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import build_pages as BP  # noqa: E402

ADATA = os.path.join(HERE, "academy_data")
DATA = os.path.join(HERE, "atlas_data")
ACADEMY = os.path.join(HERE, "academy")

ALLOWED = re.compile(r"</?(?:strong|em|code|sub|sup)>|<a href=\"[^\"<>]*\">|</a>")
TAG = re.compile(r"<[^>]+>")

# Faze 2. Aktivni slovesa, ktera jde zkontrolovat i naucit (spec §12).
# "Understand" a "know" nejsou vysledky, jsou to pocity -- proto ban-list.
OBJ_VERBS = {
    "explain", "distinguish", "predict", "interpret", "evaluate", "compare",
    "propose", "identify", "trace", "justify", "design", "critique", "apply",
    "relate", "recognise", "recognize", "read", "state", "name", "derive",
    "rank", "place", "separate", "choose", "decide", "spot", "tell", "work",
    "describe", "translate", "estimate", "reconstruct", "defend",
}
OBJ_BANNED = {"understand", "know", "learn", "appreciate", "grasp", "be", "have",
              "get", "realise", "realize", "feel"}
# Jedna primarni dovednost na lekci, slovnik z §13 spec Faze 2.
RESEARCH_SKILLS = {
    "Building a biological model", "Comparing mechanisms", "Causal reasoning",
    "Signal integration", "Spatial reasoning", "Competing hypotheses",
    "Pathway reasoning", "Systems thinking", "Mechanistic interpretation",
    "Evidence evaluation",
}
# Research Challenges. Dovednosti ze spec §26 -- sirsi seznam nez u lekci,
# protoze vyzva jich zamerne trenuje vic najednou.
RC_SKILLS = {
    "Causal reasoning", "Experimental design", "Evidence evaluation",
    "Hypothesis formation", "Alternative explanations", "Control selection",
    "Mechanistic reasoning", "Systems thinking", "Spatial reasoning",
    "Scientific uncertainty",
}
# Sloupce vysledku nesou uroven, nikdy cislo -- presne cislo by bylo vymyslene.
RC_LEVELS = {"none", "low", "mid", "high"}
LADDER = ("recall", "explain", "predict", "interpret", "critique", "synthesize", "design")
EX_KINDS = ("model", "predict", "compare", "caution", "openq", "design")

problems = []


def bad(where, msg):
    problems.append("%-34s %s" % (where, msg))


def entity_pages():
    out = {}
    for x in json.load(open(os.path.join(DATA, "entities_baked.json"), encoding="utf-8")):
        st = x.get("studies")
        if isinstance(st, str):
            try:
                st = json.loads(st.replace("'", '"'))
            except Exception:
                st = [t.strip(" '\"") for t in st.strip("[]").split(",") if t.strip()]
        out[x["name"].lower()] = len(st or [])
    return out


def check_challenges(routes, pw_nodes, pw_edges, studies, gaps, ents, lesson_slugs):
    """15 -- Research Challenges (2026-09-01).

    Vyzva je jedina cast webu, kde student utraci rozpocet a cte "vysledek".
    Dve veci se proto hlidaji tvrdeji nez u lekci:

      * ROZPOCET MUSI SKRTIT. Kdyby soucet nakladu byl <= rozpoctu, student
        spusti vsechno a cela pointa (§4: prioritizace) tise zmizi -- a nikdo
        by si toho nevsiml, protoze stranka by vypadala uplne stejne.
      * VYSLEDEK NENI NIKDY VYMYSLENY. Bud odkazuje na skutecnou studii
        v korpusu, nebo je oznaceny jako hypoteticky a nese vysvetleni proc.
        Treti moznost tahle brana nepusti (§29).
    """
    p = os.path.join(ADATA, "challenges.json")
    if not os.path.exists(p):
        return 0
    doc = json.load(open(p, encoding="utf-8"))
    chs = doc["challenges"]
    seen = set()
    prose_blobs = []

    for c in chs:
        w = "challenge:" + (c.get("slug") or "?")
        for f in ("id", "n", "slug", "title", "subtitle", "type", "level",
                  "researchQuestion", "status"):
            if not (c.get(f) or "").strip():
                bad(w, "chybi povinne pole %r" % f)
        if c.get("slug") in seen:
            bad(w, "duplicitni slug")
        seen.add(c.get("slug"))
        if c.get("status") not in ("published", "planned"):
            bad(w, "status=%r, povoleno published/planned" % c.get("status"))
        if c.get("status") != "published":
            continue
        if not isinstance(c.get("estimatedTime"), int) or c["estimatedTime"] <= 0:
            bad(w, "estimatedTime musi byt kladne cislo")

        objs = c.get("learningObjectives") or []
        if not 3 <= len(objs) <= 5:
            bad(w, "ma %d learning objectives, chce se 3-5" % len(objs))
        for o in objs:
            first = re.sub(r"[^a-z]", "", (o.split() or [""])[0].lower())
            if first in OBJ_BANNED:
                bad(w, "objective zacina slovesem %r -- to nejde zkontrolovat: %r"
                    % (first, o[:70]))
            elif first not in OBJ_VERBS:
                bad(w, "objective nezacina znamym aktivnim slovesem (%r): %r"
                    % (first, o[:70]))
        for s in c.get("researchSkills") or []:
            if s not in RC_SKILLS:
                bad(w, "neznama research skill %r (slovnik spec §26)" % s)
        if not c.get("researchSkills"):
            bad(w, "nepojmenovava zadnou research skill (§26)")

        for pr in c.get("prerequisites") or []:
            if pr.get("lesson") not in lesson_slugs:
                bad(w, "prerequisite ukazuje na neexistujici lekci %r" % pr.get("lesson"))
            if not (pr.get("why") or "").strip():
                bad(w, "prerequisite %r nerika proc" % pr.get("lesson"))

        # -- what we know / uncertainty
        if len(c.get("whatWeKnow") or []) < 3:
            bad(w, "whatWeKnow ma min nez tri polozky -- vyzva zacina tim, co uz plati")
        for k in c.get("whatWeKnow") or []:
            if not (k.get("claim") or "").strip():
                bad(w, "whatWeKnow polozka bez claim")
            if not k.get("sids"):
                bad(w, "whatWeKnow polozka bez studie: %r" % (k.get("claim") or "")[:60])
            for sid in k.get("sids") or []:
                if sid not in studies:
                    bad(w, "whatWeKnow odkazuje na neznamy SID %r" % sid)
            prose_blobs.append(k.get("claim") or "")
        if not c.get("uncertainty"):
            bad(w, "nepojmenovava zadnou nejistotu (§29)")
        prose_blobs += list(c.get("uncertainty") or [])
        for sid in c.get("studies") or []:
            if sid not in studies:
                bad(w, "studies obsahuje neznamy SID %r" % sid)

        # -- model: stejny kontrakt jako u cviceni typu model v lekci
        md = c.get("model") or {}
        ids = [n for col in md.get("layout") or [] for n in col]
        if not ids:
            bad(w, "model nema layout")
        for nid in ids:
            if nid not in pw_nodes:
                bad(w, "uzel %r neni v pathway/model.json -- vyukovy model by se "
                       "rozesel s vedeckym" % nid)
        for eid in md.get("edges") or []:
            if eid not in pw_edges:
                bad(w, "hrana %r neni v pathway/model.json" % eid)
        ctrls = md.get("controls") or []
        if len(ctrls) < 2:
            bad(w, "model ma min nez dva ovladace -- pak neni s cim experimentovat")
        combos = [[]]
        for ct in ctrls:
            if len(ct.get("options") or []) < 2:
                bad(w, "ovladac %r ma min nez dve moznosti" % ct.get("id"))
            combos = [q + [v] for q in combos for v in (ct.get("options") or [])]
            if (md.get("start") or {}).get(ct["id"]) not in (ct.get("options") or []):
                bad(w, "start[%r] neni mezi moznostmi ovladace" % ct.get("id"))
        states = md.get("states") or {}
        need = {"|".join(q) for q in combos}
        for miss in sorted(need - set(states)):
            bad(w, "chybi vyjmenovany stav %r (zadny simulator = vsechny kombinace "
                   "musi byt napsane)" % miss)
        for extra in sorted(set(states) - need):
            bad(w, "stav %r neodpovida zadne kombinaci prepinacu" % extra)
        for sk, st in states.items():
            if not (st.get("readout") or "").strip():
                bad(w, "stav %r nema readout" % sk)
            if not (st.get("note") or "").strip():
                bad(w, "stav %r nema note" % sk)
            for nid in st.get("flow") or []:
                if nid not in ids:
                    bad(w, "stav %r sviti uzel %r, ktery v modelu neni" % (sk, nid))
            for eid in st.get("cut") or []:
                if eid not in pw_edges:
                    bad(w, "stav %r pretina neznamou hranu %r" % (sk, eid))
            prose_blobs.append(st.get("note") or "")
        prose_blobs.append(md.get("caption") or "")

        # -- break the model
        for b in c.get("break") or []:
            bw = "%s break:%s" % (w, b.get("id"))
            opts = b.get("options") or []
            if not 3 <= len(opts) <= 4:
                bad(bw, "ma %d moznosti, povoleny jsou 3 nebo 4" % len(opts))
            if not isinstance(b.get("answer"), int) or not 0 <= b["answer"] < len(opts):
                bad(bw, "answer=%r neukazuje na zadnou moznost" % (b.get("answer"),))
            if len((b.get("explain") or "").split()) < 12:
                bad(bw, "explain je kratsi nez 12 slov -- to neni vysvetleni")
            prose_blobs += [b.get("prompt") or "", b.get("explain") or ""] + list(opts)

        # -- hypotezy + revize
        hyp = (c.get("hypotheses") or {}).get("options") or []
        if len(hyp) < 3:
            bad(w, "ma %d hypotez, chce se aspon tri konkurencni (§9)" % len(hyp))
        hyp_ids = set()
        for o in hyp:
            if not o.get("id") or not (o.get("label") or "").strip():
                bad(w, "hypoteza bez id/label")
            if not (o.get("note") or "").strip():
                bad(w, "hypoteza %r nema napsany komentar -- staticky web ho nevygeneruje"
                    % o.get("id"))
            hyp_ids.add(o.get("id"))
            prose_blobs += [o.get("label") or "", o.get("note") or ""]
        prose_blobs.append((c.get("hypotheses") or {}).get("prompt") or "")
        rv = c.get("revise")
        if not rv:
            bad(w, "chybi krok revize hypotezy -- §16 ho zada jako povinny")
        else:
            for hid in sorted(hyp_ids):
                if not (rv.get("feedback") or {}).get(hid):
                    bad(w, "revize nema zpetnou vazbu pro hypotezu %r" % hid)
            prose_blobs += [rv.get("prompt") or "", rv.get("note") or ""]
            prose_blobs += list((rv.get("feedback") or {}).values())

        # -- rozpocet a experimenty
        exps = c.get("experiments") or []
        if len(exps) < 3:
            bad(w, "ma %d experimentu, na volbu je to malo" % len(exps))
        budget = (c.get("budget") or {}).get("total")
        if not isinstance(budget, int) or budget <= 0:
            bad(w, "budget.total musi byt kladne cislo")
        else:
            tot = sum(x.get("cost") or 0 for x in exps)
            if tot <= budget:
                bad(w, "soucet nakladu (%d) neprevysuje rozpocet (%d) -- student by "
                       "spustil vsechno a §4 (prioritizace) by tise zmizela" % (tot, budget))
            if min([x.get("cost") or 0 for x in exps] or [0]) > budget:
                bad(w, "ani nejlevnejsi experiment se do rozpoctu nevejde")
        prose_blobs.append((c.get("budget") or {}).get("note") or "")

        exp_ids, exp_by_id = set(), {}
        for x in exps:
            exp_by_id[x.get("id")] = x
        for x in exps:
            xw = "%s exp:%s" % (w, x.get("id"))
            if not x.get("id") or x["id"] in exp_ids:
                bad(xw, "experiment bez id nebo s duplicitnim id")
            exp_ids.add(x.get("id"))
            if not isinstance(x.get("cost"), int) or x["cost"] <= 0:
                bad(xw, "cost=%r musi byt kladne cislo" % (x.get("cost"),))
            if not (x.get("addresses") or "").strip():
                bad(xw, "chybi addresses -- bez toho student pred zaplacenim nevi, na "
                        "kterou otazku experiment miri, a vyber neni rozhodnuti")
            prose_blobs.append(x.get("addresses") or "")
            disc = x.get("discriminates")
            if disc is None:
                bad(xw, "chybi discriminates (klidne prazdne pole -- to je legitimni "
                        "a poucne, znamena 'vsechny hypotezy cekaji totez')")
            else:
                for hid in disc:
                    if hid not in hyp_ids:
                        bad(xw, "discriminates jmenuje neexistujici hypotezu %r" % hid)
                if len(set(disc)) != len(disc):
                    bad(xw, "discriminates ma duplicity")
            d = x.get("design") or {}
            for f in ("model", "perturbation", "readout", "control"):
                if not (d.get(f) or "").strip():
                    bad(xw, "design nema %s -- §10 chce vsechny ctyri dimenze" % f)
                prose_blobs.append(d.get(f) or "")
            ev = x.get("evidence") or {}
            if ev.get("hypothetical"):
                if not (ev.get("basis") or "").strip():
                    bad(xw, "hypoteticky vysledek nerika, proc je hypoteticky (§29)")
                prose_blobs.append(ev.get("basis") or "")
            elif ev.get("sids"):
                for sid in ev["sids"]:
                    if sid not in studies:
                        bad(xw, "vysledek odkazuje na neznamy SID %r" % sid)
            else:
                bad(xw, "vysledek neni ani odvozeny ze studie, ani oznaceny jako "
                        "hypoteticky -- vymyslet data se nesmi (§29)")
            res = x.get("result") or {}
            if not (res.get("unit") or "").strip():
                bad(xw, "vysledek nema unit")
            if not (res.get("caption") or "").strip():
                bad(xw, "vysledek nema popisek -- zjednodusena vizualizace se musi "
                        "oznacit (§13)")
            if len(res.get("bars") or []) < 2:
                bad(xw, "vysledek ma min nez dva sloupce, neni co porovnat")
            for bar in res.get("bars") or []:
                if bar.get("level") not in RC_LEVELS:
                    bad(xw, "sloupec %r ma uroven %r mimo slovnik %s -- presna cisla "
                            "by byla vymyslena" % (bar.get("label"), bar.get("level"),
                                                   sorted(RC_LEVELS)))
                if not (bar.get("label") or "").strip():
                    bad(xw, "sloupec bez popisku")
            prose_blobs.append(res.get("caption") or "")
            if not x.get("conclude"):
                bad(xw, "chybi conclude -- §14 se pta, co vysledek dovoluje uzavrit")
            if not x.get("cannotConclude"):
                bad(xw, "chybi cannotConclude -- druha polovina §14 je povinna")
            if not (x.get("informative") or "").strip():
                bad(xw, "chybi informative -- §17 chce rict, jestli experiment rozlisuje")
            interp = x.get("interpret") or []
            if not 3 <= len(interp) <= 4:
                bad(xw, "ma %d interpretaci, povoleny jsou 3 nebo 4" % len(interp))
            for o in interp:
                if not (o.get("note") or "").strip():
                    bad(xw, "interpretace %r nema napsany komentar" % o.get("label"))
                prose_blobs += [o.get("label") or "", o.get("note") or ""]
            prose_blobs += [x.get("label") or "", x.get("informative") or ""]
            prose_blobs += list(x.get("conclude") or []) + list(x.get("cannotConclude") or [])

        # -- debrief: co ta sada dohromady koupila
        #
        # Bez tohohle bloku vyzva nikdy neodpovi na otazku "utratil jsem to
        # spravne?" -- student utrati rozpocet, uvidi sest samostatnych
        # vysledku a nema jak zjistit, jestli ta KOMBINACE k necemu byla.
        db = c.get("debrief") or {}
        if not db:
            bad(w, "chybi debrief -- bez nej se student nedozvi, co jeho sada koupila")
        else:
            for key, need in (("minimalPortfolio", True), ("fullerPortfolio", False)):
                p = db.get(key)
                if not p:
                    if need:
                        bad(w, "debrief nema %s -- 'utratil jsem to spravne' pak nema "
                               "s cim se porovnat" % key)
                    continue
                ids = p.get("experiments") or []
                if not ids:
                    bad(w, "%s je prazdne" % key)
                for i in ids:
                    if i not in exp_ids:
                        bad(w, "%s odkazuje na neznamy experiment %r" % (key, i))
                cost = sum((exp_by_id.get(i) or {}).get("cost") or 0 for i in ids)
                if isinstance(budget, int) and cost > budget:
                    bad(w, "%s stoji %d, coz se do rozpoctu %d nevejde -- referencni "
                           "sada musi byt dosazitelna" % (key, cost, budget))
                if key == "minimalPortfolio" and not any(
                        len((exp_by_id.get(i) or {}).get("discriminates") or []) >= 2
                        for i in ids):
                    bad(w, "minimalPortfolio neobsahuje ani jeden rozlisujici experiment "
                           "-- pak to neni dostacujici sada")
                if not (p.get("why") or "").strip():
                    bad(w, "%s nerika proc" % key)
                prose_blobs.append(p.get("why") or "")
            for k in ("none", "one", "many"):
                if not ((db.get("coverage") or {}).get(k) or "").strip():
                    bad(w, "debrief.coverage nema variantu %r" % k)
                prose_blobs.append((db.get("coverage") or {}).get(k) or "")
            if not db.get("rules"):
                bad(w, "debrief nema zadne pravidlo pro kombinace")
            for j, r in enumerate(db.get("rules") or []):
                rw = "%s debrief.rule[%d]" % (w, j)
                for key in ("ran", "notRan"):
                    for i in r.get(key) or []:
                        if i not in exp_ids:
                            bad(rw, "%s odkazuje na neznamy experiment %r" % (key, i))
                both = set(r.get("ran") or []) & set(r.get("notRan") or [])
                if both:
                    bad(rw, "experiment je v ran i notRan zaroven: %s" % sorted(both))
                if not (r.get("note") or "").strip():
                    bad(rw, "pravidlo bez textu")
                prose_blobs.append(r.get("note") or "")

        # -- answer: vyzva musi na svou vlastni otazku odpovedet
        #
        # Ne znamkou studenta (§3 to zakazuje), ale vedou: co bylo zmereno,
        # jak se to cte a co nikdo neudelal -- tri vrstvy §29 oddelene nahlas.
        ans = c.get("answer") or {}
        if not ans:
            bad(w, "chybi answer -- vyzva se studenta zepta a nikdy mu neodpovi")
        else:
            if not (ans.get("short") or "").strip():
                bad(w, "answer nema kratkou primou odpoved")
            if len(ans.get("observation") or []) < 3:
                bad(w, "answer.observation ma min nez tri zmerene veci")
            for row in ans.get("observation") or []:
                if not (row.get("text") or "").strip():
                    bad(w, "answer.observation polozka bez textu")
                if not row.get("sids"):
                    bad(w, "answer.observation polozka bez studie -- vrstva Observation "
                           "musi ukazovat na mereni")
                for sid in row.get("sids") or []:
                    if sid not in studies:
                        bad(w, "answer.observation ma neznamy SID %r" % sid)
                prose_blobs.append(row.get("text") or "")
            for key in ("interpretation", "stillOpen"):
                if not ans.get(key):
                    bad(w, "answer nema vrstvu %r (§29 chce vsechny tri)" % key)
                prose_blobs += list(ans.get(key) or [])
            verd = ans.get("hypothesisVerdicts") or {}
            for hid in sorted(hyp_ids):
                if not (verd.get(hid) or "").strip():
                    bad(w, "answer nerika, jak vychazi hypoteza %r -- student, ktery si ji "
                           "vybral, by odpoved nedostal" % hid)
            for hid in sorted(set(verd) - hyp_ids):
                bad(w, "answer ma verdikt k neexistujici hypoteze %r" % hid)
            prose_blobs += [ans.get("short") or ""] + list(verd.values())

        # Aspon jeden rozlisujici experiment se MUSI vejit do rozpoctu -- jinak
        # je vyzva nereseitelna a debrief by studentovi vycital neco, co si
        # koupit nemohl.
        afford = [x for x in exps
                  if len(x.get("discriminates") or []) >= 2
                  and isinstance(budget, int) and (x.get("cost") or 0) <= budget]
        if not afford:
            bad(w, "zadny rozlisujici experiment (discriminates >= 2) se nevejde do "
                   "rozpoctu -- otazku by neslo posunout za zadnou cenu")

        # -- confounder
        cf = c.get("confounder")
        if cf:
            if cf.get("after") and cf["after"] not in exp_ids:
                bad(w, "confounder.after=%r neni id zadneho experimentu" % cf["after"])
            for sid in cf.get("sids") or []:
                if sid not in studies:
                    bad(w, "confounder odkazuje na neznamy SID %r" % sid)
            for f in ("info", "prompt", "explain", "control"):
                if not (cf.get(f) or "").strip():
                    bad(w, "confounder nema %s" % f)
                prose_blobs.append(cf.get(f) or "")
            if len(cf.get("options") or []) < 3:
                bad(w, "confounder ma min nez tri moznosti (§15)")
            for o in cf.get("options") or []:
                if not (o.get("note") or "").strip():
                    bad(w, "moznost %r confounderu nema komentar" % o.get("label"))
                prose_blobs += [o.get("label") or "", o.get("note") or ""]

        # -- srovnani s publikovanou praci
        cp = c.get("compare") or {}
        if cp.get("sid") not in studies:
            bad(w, "compare odkazuje na neznamy SID %r" % cp.get("sid"))
        if not cp.get("whatItAnswered") or not cp.get("whatItDidNot"):
            bad(w, "compare musi rict, co studie odpovedela I co neodpovedela (§18)")
        for f in ("whatTheyTested", "howToRead"):
            if not (cp.get(f) or "").strip():
                bad(w, "compare nema %s" % f)
            prose_blobs.append(cp.get(f) or "")
        prose_blobs += list(cp.get("whatItAnswered") or []) + list(cp.get("whatItDidNot") or [])

        # -- reflexe a dalsi otazka
        if not c.get("reflection"):
            bad(w, "chybi zaverecna reflexe (§19)")
        for r in c.get("reflection") or []:
            if len(r.get("options") or []) < 2:
                bad(w, "reflexe %r ma min nez dve moznosti" % r.get("id"))
            prose_blobs += [r.get("prompt") or ""] + list(r.get("options") or [])
        nq = c.get("nextQuestion") or {}
        for f in ("text", "prompt"):
            if not (nq.get(f) or "").strip():
                bad(w, "nextQuestion nema %s -- §5 konci otazkou 'co dal'" % f)
            prose_blobs.append(nq.get(f) or "")
        if len(nq.get("options") or []) < 3:
            bad(w, "nextQuestion ma min nez tri moznosti")
        for o in nq.get("options") or []:
            if not (o.get("note") or "").strip():
                bad(w, "moznost %r v nextQuestion nema komentar" % o.get("label"))
            prose_blobs += [o.get("label") or "", o.get("note") or ""]

        # -- odkazy ven (§27, §28): nikdy do prazdna
        for s in c.get("relatedLessons") or []:
            if s not in lesson_slugs:
                bad(w, "relatedLessons ukazuje na neexistujici lekci %r" % s)
        for r in c.get("relatedRoutes") or []:
            if r.get("id") not in routes:
                bad(w, "neznama guided route %r" % r.get("id"))
        for key, names in (c.get("relatedEntities") or {}).items():
            for name in names:
                n = ents.get(name.lower())
                if n is None:
                    bad(w, "entita %r neni v entities_baked.json" % name)
                elif n < BP.PAGE_THRESHOLD:
                    bad(w, "entita %r ma jen %d studii -> nema stranku, odkaz by byl 404"
                        % (name, n))
        for s in c.get("openQuestions") or []:
            if s not in gaps:
                bad(w, "neznamy open-question slug %r" % s)
        prose_blobs += [c.get("subtitle") or "", c.get("researchQuestion") or ""]

    # 10 -- stejny whitelist inline znacek jako u lekci
    for b in prose_blobs:
        for m in TAG.finditer(b or ""):
            if not ALLOWED.fullmatch(m.group(0)):
                bad("challenges.json", "nepovolena znacka %r v proze" % m.group(0))
    return len([c for c in chs if c["status"] == "published"])


def main():
    lessons = json.load(open(os.path.join(ADATA, "lessons.json"), encoding="utf-8"))["lessons"]
    modules = json.load(open(os.path.join(ADATA, "modules.json"), encoding="utf-8"))
    studies = {s["sid"] for s in json.load(open(os.path.join(DATA, "studies_baked.json"),
                                               encoding="utf-8")) if s.get("sid")}
    ents = entity_pages()
    routes = set()
    mp = os.path.join(HERE, "pathway", "model.json")
    if os.path.exists(mp):
        routes = {r["id"] for r in json.load(open(mp, encoding="utf-8")).get("routes", [])}
    pw_nodes, pw_edges = set(), set()
    if os.path.exists(mp):
        _doc = json.load(open(mp, encoding="utf-8"))
        pw_nodes = {n["id"] for n in _doc.get("nodes", [])}
        pw_edges = {i["id"] for i in _doc.get("interactions", [])}

    gaps = set()
    gp = os.path.join(DATA, "gaps_baked.json")
    if os.path.exists(gp):
        gaps = {BP.slugify(g["title"]) for g in json.load(open(gp, encoding="utf-8"))}

    by_slug = {l["slug"]: l for l in lessons}

    for l in lessons:
        w = "lesson:" + l["slug"]

        # 1 studie
        for sid in l.get("studies") or []:
            if sid not in studies:
                bad(w, "neznamy SID %r" % sid)
        # 9 redakcni minima
        if len(l.get("studies") or []) < 3:
            bad(w, "ma jen %d studii, minimum jsou 3 (spec §11)" % len(l.get("studies") or []))
        if not (l.get("thinkQuestions") or []):
            bad(w, "chybi Think question (spec §11)")
        if not (l.get("uncertainty") or l.get("openQuestions")):
            bad(w, "nepojmenovava zadnou nejistotu ani open question (spec §17)")

        # 11 minikviz -- 3 otazky, lehka -> tezka, prave jedna spravna odpoved.
        # Poradi obtiznosti je soucast zadani, ne kosmetika: prvni otazka ma
        # projit kazdemu, kdo lekci precetl, treti ma nutit spojit dve veci.
        qz = l.get("quiz") or []
        if len(qz) != 3:
            bad(w, "kviz ma %d otazek, maji byt presne 3" % len(qz))
        for i, q in enumerate(qz):
            qw = "%s q%d" % (w, i + 1)
            exp = ("easy", "medium", "hard")[i] if i < 3 else None
            if exp and q.get("level") != exp:
                bad(qw, "level=%r, podle poradi ma byt %r" % (q.get("level"), exp))
            opts = q.get("options") or []
            if not 3 <= len(opts) <= 4:
                bad(qw, "ma %d moznosti, povoleny jsou 3 nebo 4" % len(opts))
            if len({o.strip().lower() for o in opts}) != len(opts):
                bad(qw, "dve moznosti jsou stejne")
            a = q.get("answer")
            if not isinstance(a, int) or not 0 <= a < len(opts):
                bad(qw, "answer=%r neukazuje na zadnou moznost" % (a,))
            if not (q.get("explain") or "").strip():
                bad(qw, "chybi explain -- vysvetleni je smysl kvizu, ne znamka")
            elif len(q["explain"].split()) < 12:
                bad(qw, "explain ma jen %d slov, to neni vysvetleni"
                    % len(q["explain"].split()))
            for o in opts:
                if len(o) > 180:
                    bad(qw, "moznost je delsi nez 180 znaku: %r" % o[:60])

        # 12 Faze 2 -- metadata lekce
        objs = l.get("learningObjectives") or []
        if objs and not 3 <= len(objs) <= 5:
            bad(w, "ma %d learning objectives, spec §12 chce 3-5" % len(objs))
        for o in objs:
            first = re.sub(r"[^a-z]", "", (o.split() or [""])[0].lower())
            if first in OBJ_BANNED:
                bad(w, "objective zacina slovesem %r -- to nejde zkontrolovat (§12): %r"
                    % (first, o[:70]))
            elif first not in OBJ_VERBS:
                bad(w, "objective nezacina znamym aktivnim slovesem (%r): %r"
                    % (first, o[:70]))
        if l.get("researchSkill") and l["researchSkill"] not in RESEARCH_SKILLS:
            bad(w, "neznama research skill %r (slovnik §13)" % l["researchSkill"])
        if l.get("ladder") and l["ladder"] not in LADDER:
            bad(w, "neznama ladder uroven %r" % l["ladder"])

        ex_ids = set()
        for x in l.get("exercises") or []:
            xw = "%s ex:%s" % (w, x.get("id"))
            if not x.get("id"):
                bad(w, "cviceni bez id")
                continue
            if x["id"] in ex_ids:
                bad(xw, "duplicitni id cviceni")
            ex_ids.add(x["id"])
            if x.get("kind") not in EX_KINDS:
                bad(xw, "neznamy kind %r" % x.get("kind"))
                continue
            if not (x.get("title") or "").strip():
                bad(xw, "cviceni nema title")
            k = x["kind"]

            if k == "model":
                ids = [n for col in x.get("layout") or [] for n in col]
                if not ids:
                    bad(xw, "model nema layout")
                for nid in ids:
                    if nid not in pw_nodes:
                        bad(xw, "uzel %r neni v pathway/model.json -- vyukovy model by "
                                "se rozesel s vedeckym" % nid)
                for eid in x.get("edges") or []:
                    if eid not in pw_edges:
                        bad(xw, "hrana %r neni v pathway/model.json" % eid)
                ctrls = x.get("controls") or []
                if not ctrls:
                    bad(xw, "model nema zadny ovladac -- pak to neni interaktivni model")
                combos = [[]]
                for c in ctrls:
                    if len(c.get("options") or []) < 2:
                        bad(xw, "ovladac %r ma min nez dve moznosti" % c.get("id"))
                    combos = [p + [v] for p in combos for v in (c.get("options") or [])]
                start = x.get("start") or {}
                for c in ctrls:
                    if start.get(c["id"]) not in (c.get("options") or []):
                        bad(xw, "start[%r]=%r neni mezi moznostmi" % (c["id"], start.get(c["id"])))
                states = x.get("states") or {}
                need = {"|".join(p) for p in combos}
                for miss in sorted(need - set(states)):
                    bad(xw, "chybi vyjmenovany stav %r (zadny simulator = vsechny "
                            "kombinace musi byt napsane)" % miss)
                for extra in sorted(set(states) - need):
                    bad(xw, "stav %r neodpovida zadne kombinaci prepinacu" % extra)
                for sk, st in states.items():
                    if not (st.get("readout") or "").strip():
                        bad(xw, "stav %r nema readout" % sk)
                    if not (st.get("note") or "").strip():
                        bad(xw, "stav %r nema note" % sk)
                    for nid in st.get("flow") or []:
                        if nid not in ids:
                            bad(xw, "stav %r zmiňuje uzel %r, ktery v modelu neni" % (sk, nid))
                    for eid in st.get("cut") or []:
                        if eid not in pw_edges:
                            bad(xw, "stav %r zmiňuje neznamou hranu %r" % (sk, eid))

            elif k == "predict":
                opts = x.get("options") or []
                if not 3 <= len(opts) <= 4:
                    bad(xw, "ma %d moznosti, povoleny jsou 3 nebo 4" % len(opts))
                if not isinstance(x.get("answer"), int) or not 0 <= x["answer"] < len(opts):
                    bad(xw, "answer=%r neukazuje na zadnou moznost" % (x.get("answer"),))
                obs = x.get("observe") or {}
                if obs.get("sid") not in studies:
                    bad(xw, "Observe odkazuje na SID %r, ktery v korpusu neni -- vysledek "
                            "se nesmi vymyslet (§5)" % obs.get("sid"))
                for f in ("method", "readout"):
                    if not (obs.get(f) or "").strip():
                        bad(xw, "Observe nema %s" % f)
                if not (x.get("explain") or "").strip():
                    bad(xw, "chybi Explain")
                if not (x.get("shows") and x.get("doesNotShow")):
                    bad(xw, "chybi shows/doesNotShow -- §7 je povinna cast tohohle cviceni")

            elif k == "compare":
                for side in ("a", "b"):
                    d = x.get(side) or {}
                    if d.get("sid") not in studies:
                        bad(xw, "strana %s odkazuje na neznamy SID %r" % (side, d.get("sid")))
                    for f in ("perturbation", "readout"):
                        if not (d.get(f) or "").strip():
                            bad(xw, "strana %s nema %s" % (side, f))
                for f in ("bothSupport", "differ", "nextExperiment"):
                    if not (x.get(f) or "").strip():
                        bad(xw, "chybi %s" % f)

            elif k == "caution":
                if not (x.get("shows") and x.get("doesNotShow")):
                    bad(xw, "Scientific Caution potrebuje obe strany (§7)")

            elif k == "openq":
                if x.get("slug") not in gaps:
                    bad(xw, "neznamy open-question slug %r" % x.get("slug"))
                have = [f for f in ("whatWeKnow", "whatWeDont", "competing", "wouldResolve")
                        if x.get(f)]
                if len(have) < 3:
                    bad(xw, "ma jen %d ze ctyr casti explorer (§8)" % len(have))
                for sid in x.get("sids") or []:
                    if sid not in studies:
                        bad(xw, "neznamy SID %r" % sid)

            elif k == "design":
                dims = x.get("dimensions") or []
                if len(dims) < 3:
                    bad(xw, "ma %d dimenzi, §9 chce aspon model/perturbation/readout/control"
                        % len(dims))
                for d in dims:
                    if len(d.get("options") or []) < 2:
                        bad(xw, "dimenze %r ma min nez dve moznosti" % d.get("id"))
                    for o in d.get("options") or []:
                        if not (o.get("note") or "").strip():
                            bad(xw, "moznost %r nema napsanou zpetnou vazbu -- staticky web "
                                    "ji nemuze vygenerovat" % o.get("label"))
                if not x.get("limitations"):
                    bad(xw, "chybi limitations -- §9 chce rict, co navrh NEMUZE ukazat")
                for sid in x.get("sids") or []:
                    if sid not in studies:
                        bad(xw, "neznamy SID %r" % sid)

        for sec in l.get("sections") or []:
            iid = sec.get("interactive")
            if iid and iid not in ex_ids:
                bad(w, "sekce odkazuje na neexistujici cviceni %r" % iid)

        # 14 beginner uroven
        if l.get("coreIdeaBeginner"):
            for i, sec in enumerate(l.get("sections") or []):
                if sec["kind"] == "caution":
                    if sec.get("bodyBeginner"):
                        bad(w, "caution sekce %d ma beginner verzi -- vyhrady se "
                               "zadne urovni nezkracuji" % i)
                elif not sec.get("bodyBeginner"):
                    bad(w, "sekce %d (%r) nema beginner verzi, ale lekce beginner "
                           "uroven ma -- na te urovni by byla prazdna"
                        % (i, sec.get("heading")))
        else:
            for i, sec in enumerate(l.get("sections") or []):
                if sec.get("bodyBeginner"):
                    bad(w, "sekce %d ma beginner verzi, ale lekce nema "
                           "coreIdeaBeginner -- prepinac se nezapne" % i)

        # 2 entity
        for key in ("proteins", "pathways", "processes", "organelles", "nutrients",
                    "drugs", "diseases", "outcomes"):
            for name in l.get(key) or []:
                n = ents.get(name.lower())
                if n is None:
                    bad(w, "entita %r neni v entities_baked.json" % name)
                elif n < BP.PAGE_THRESHOLD:
                    bad(w, "entita %r ma jen %d studii -> nema stranku, odkaz by byl 404"
                        % (name, n))
        # 3 routes
        for r in l.get("guidedRoutes") or []:
            if r["id"] not in routes:
                bad(w, "neznama guided route %r" % r["id"])
        # 4 open questions
        for s in l.get("openQuestions") or []:
            if s not in gaps:
                bad(w, "neznamy open-question slug %r" % s)
        # 5 retez
        for key in ("previousLesson", "nextLesson"):
            v = l.get(key)
            if v and v not in by_slug:
                bad(w, "%s ukazuje na neexistujici lekci %r" % (key, v))
        # 10 proza
        blobs = list(l.get("coreIdea") or []) + [l.get("uncertainty") or ""]
        for sec in l.get("sections") or []:
            blobs += list(sec.get("body") or [])
        for t in l.get("thinkQuestions") or []:
            blobs += [t.get("prompt") or "", t.get("hint") or "", t.get("reveal") or ""]
        for q in l.get("quiz") or []:
            blobs += [q.get("prompt") or "", q.get("explain") or ""]
            blobs += list(q.get("options") or [])
        blobs += list(l.get("learningObjectives") or [])
        blobs += list(l.get("coreIdeaBeginner") or [])
        for sec in l.get("sections") or []:
            blobs += list(sec.get("bodyBeginner") or [])
        for x in l.get("exercises") or []:
            for f in ("prompt", "explain", "why", "bothSupport", "differ",
                      "nextExperiment", "question", "wouldResolve"):
                blobs.append(x.get(f) or "")
            for f in ("options", "shows", "doesNotShow", "limitations",
                      "whatWeKnow", "whatWeDont", "competing"):
                v = x.get(f)
                if isinstance(v, list):
                    blobs += [str(i) for i in v]
            for st in (x.get("states") or {}).values():
                blobs.append(st.get("note") or "")
            for d in x.get("dimensions") or []:
                blobs += [o.get("note") or "" for o in d.get("options") or []]
            for side in ("a", "b"):
                if isinstance(x.get(side), dict):
                    blobs += [x[side].get("perturbation") or "", x[side].get("readout") or ""]
            if isinstance(x.get("observe"), dict):
                blobs += [x["observe"].get("method") or "", x["observe"].get("readout") or ""]
        for b in blobs:
            for m in TAG.finditer(b):
                if not ALLOWED.fullmatch(m.group(0)):
                    bad(w, "nepovolena znacka %r v proze" % m.group(0))

    # 15 Research Challenges
    n_ch = check_challenges(routes, pw_nodes, pw_edges, studies, gaps, ents,
                            set(by_slug))

    # 5b poradi v modules.json vs prev/next
    for mod in modules["modules"]:
        pub = [r["lesson"] for r in mod["lessons"] if r["status"] == "published"]
        for r in mod["lessons"]:
            if r["status"] == "published" and r["lesson"] not in by_slug:
                bad("module:" + mod["slug"], "publikovana lekce %r chybi v lessons.json"
                    % r["lesson"])
            if r["status"] != "published" and not r.get("title"):
                bad("module:" + mod["slug"], "planovana lekce %r nema title" % r["lesson"])
        for i, slug in enumerate(pub):
            if slug not in by_slug:
                continue
            exp_prev = pub[i - 1] if i > 0 else None
            exp_next = pub[i + 1] if i + 1 < len(pub) else None
            if by_slug[slug].get("previousLesson") != exp_prev:
                bad("module:" + mod["slug"],
                    "%s.previousLesson=%r, podle poradi ma byt %r"
                    % (slug, by_slug[slug].get("previousLesson"), exp_prev))
            if by_slug[slug].get("nextLesson") != exp_next:
                bad("module:" + mod["slug"],
                    "%s.nextLesson=%r, podle poradi ma byt %r"
                    % (slug, by_slug[slug].get("nextLesson"), exp_next))

    # 6/7/8 vygenerovane stranky
    pages = []
    for root, _, files in os.walk(ACADEMY):
        for fn in files:
            if fn == "index.html":
                pages.append(os.path.join(root, fn))
    if not pages:
        bad("academy/", "zadne vygenerovane stranky -- spust nejdriv build_academy.py")

    for mod in modules["modules"]:
        for r in mod["lessons"]:
            if r["status"] != "published":
                continue
            p = os.path.join(ACADEMY, mod["slug"], r["lesson"], "index.html")
            if not os.path.exists(p):
                bad("academy/", "chybi vygenerovana stranka %s" % p)

    href = re.compile(r'href="([^"#][^"]*)"')
    for p in pages:
        rel = os.path.relpath(p, HERE)
        h = open(p, encoding="utf-8").read()
        if "<h1>" not in h:
            bad(rel, "stranka nema <h1> primo v HTML")
        parts = rel.split(os.sep)
        # academy/<module>/<lesson>/index.html -- ale NE academy/research-challenges/*,
        # ktere ma stejnou hloubku a jinou stavbu (zadna sekce Evidence, zadny kviz).
        is_challenge = len(parts) >= 3 and parts[1] == "research-challenges"
        is_lesson = len(parts) >= 4 and not is_challenge
        # Hleda se markup, ne jmeno tridy: ".ac-model{" je i ve stylopisu na
        # KAZDE strance, takze holy retezec "ac-model" by hlasil vsude.
        for cls, fallback, what in (('class="ac-model"', "ac-mdfall", "interaktivni model"),
                                    ('class="ac-pd"', "ac-pdfall", "Predict cviceni"),
                                    ('class="ac-design"', "ac-dsfall", "Experiment Builder")):
            if is_lesson and cls in h and fallback not in h:
                bad(rel, "%s nema bez-JS ekvivalent (%s chybi)" % (what, fallback))
        # 16 parita na strance vyzvy: rozpocet i model musi byt citelne bez JS
        if is_challenge:
            for cls, fallback, what in (('class="ac-rcexp"', "ac-rcfall", "rozpocet"),
                                        ('class="ac-model"', "ac-mdfall", "interaktivni model"),
                                        ('class="ac-rcpd"', "ac-rcfall", "break-the-model")):
                if cls in h and fallback not in h:
                    bad(rel, "%s nema bez-JS ekvivalent (%s chybi)" % (what, fallback))
            if 'data-rc-budget' in h and 'data-rc-step="answer"' not in h:
                bad(rel, "stranka vyzvy nema krok s odpovedi -- vyzva by se zeptala "
                         "a neodpovedela")
            if 'data-rc-budget' in h and 'class="ac-rcdata"' not in h:
                bad(rel, "chybi payload debriefu -- rozpocet by se utratil bez zaveru")
            if 'data-rc-notes' in h and 'data-rc-note="0"' not in h:
                bad(rel, "napsana zpetna vazba k volbam neni v HTML -- bez JS by "
                         "stranka byla prazdny seznam tlacitek")
        if is_lesson and "Check yourself" in h and "ac-qzfall" not in h:
            bad(rel, "kviz nema bez-JS fallback -- bez JS by to byl slepy seznam moznosti")
        if is_lesson and "What does the evidence say?" not in h:
            bad(rel, "lekce nema sekci Evidence primo v HTML (crawler bez JS by ji nevidel)")
        if "mtor-atlas.org" not in h:
            bad(rel, "stranka neobsahuje kanonickou domenu -- poskozena sablona?")
        for u in set(href.findall(h)):
            if u.startswith("http") and not u.startswith(BP.SITE):
                continue          # externi odkaz, neresime
            path = u[len(BP.SITE):] if u.startswith(BP.SITE) else u
            path = path.split("#")[0].split("?")[0]
            if not path.startswith("/") or path in ("/",):
                continue
            target = os.path.join(HERE, path.strip("/"))
            if os.path.isdir(target):
                target = os.path.join(target, "index.html")
            if not os.path.exists(target):
                bad(rel, "odkaz na neexistujici cil %s" % u)

    if problems:
        print("verify_academy: %d NALEZU\n" % len(problems))
        for x in problems:
            print("  " + x)
        return 1
    print("verify_academy: OK -- %d lekci, %d vyzev, %d stranek, vsechny odkazy sedi"
          % (len(lessons), n_ch, len(pages)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
