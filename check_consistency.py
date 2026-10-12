#!/usr/bin/env python3
"""check_consistency.py -- hlidac rozjeti mezi vrstvami Atlasu (audit 2026-09-29).

Vedecke audity opakovane nachazely stejny vzorec: hrana nebo karta se opravi
a kvalifikuje, ale uzel, entita, beginner text nebo Academy si nechaji starou,
silnejsi verzi. Tenhle skript to hleda strojove. Je to VAROVANI, ne brana:
deploy nezastavuje, jen vypise, co ma kurator precist.

Kontroluje:
  A  zakazane absolutni formulace (pravidlo "zadny marketingovy absolutismus")
  B  beginner text, kteremu chybi kvalifikator, ktery ma student/research text
     (pohlavi, druh, bunecna linie) -- pravidlo 14: caution se v beginner
     registru nezkracuje
  C  stejna studie v supporting i conflicting jedne hrany
  D  kod studie zminovany v textu, ktery v korpusu neexistuje
  E  osirela studie: neni na zadne hrane, u zadne entity ani v zadne otazce
     (pridano 2026-10-03 -- 91 ze 126 studii pridanych od srpna takhle zustalo)
  F  odkaz na studii v datovych polich (hrana, entita, otazka), ktera v korpusu
     neni -- web, API i MCP ho tise zahodi (2026-10-03: NCT0583 u H2/H5)
  G  odborny text nese vyhradu a beginner text nema ani jednu (2026-10-11).
     Blok B hlida jen slova o druhu a pohlavi, takze propustil entitu
     Alzheimer's disease, kde odborny text dostal celou klinickou vyhradu
     a beginner verze zustala bez ni.

    py check_consistency.py            # vypis
    py check_consistency.py --strict   # exit 1, kdyz zustane nalez mimo vyjimky

Od 2026-10-03 je --strict BRANA v deploy.bat. Vedome prijaty nalez (typicky
falesny poplach kontroly B) patri do consistency_allow.json: kod, misto, kus
textu nalezu a DUVOD. Vyjimka, ktera uz nic nezachyti, se hlasi jako "stale"
a v --strict take shodi deploy, aby se seznam nezanasel.
"""
import json, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
def load(p):
    return json.load(open(os.path.join(HERE, p), encoding="utf-8"))

# 2026-10-11: oba seznamy zakazanych formulaci zily zvlast a jejich prekryv
# byl nulovy. Jeden zdroj je atlas_wording.py; tahle brana ho pouziva jako
# seznam vzoru (nazvy nahrad nepotrebuje, jen hlasi nalez).
from atlas_wording import scan as scan_wording

QUALIFIERS = [  # (v odbornem textu, co musi byt i v beginner textu)
    (r"\bfemales?\b", r"\bfemales?\b|\bwomen\b|\bgirls?\b"),
    # 2026-10-11: pridano \bmales?\b. Pohlavne specificky vysledek se nesmi
    # zobecnit v zadnem smeru -- RAPA-LONGEVITY je samci, S6K1-LONGEVITY samice.
    (r"\bmales?\b", r"\bmales?\b|\bmen\b|\bboys?\b"),
    (r"\b(?:Drosophila|flies)\b", r"\bfl(?:y|ies)\b|\binsects?\b"),
    # 2026-10-11: vzor \bin mice\b minul "in mouse models", "in a mouse model"
    # i "in mouse skeletal muscle" -- presne formulace, ktere v korpusu jsou.
    (r"\bmice\b|\bin (?:a |the )?mouse\b|\bmurine\b",
     r"\bmice\b|\bmouse\b|\banimals?\b|\brodents?\b"),
    (r"\brats?\b", r"\brats?\b|\banimals?\b|\brodents?\b"),
    (r"\bC\.\s?elegans\b|\bnematodes?\b", r"\bworms?\b|\bC\.\s?elegans\b|\bnematodes?\b"),
    (r"\byeast\b|\bS\.\s?cerevisiae\b|\bS\.\s?pombe\b", r"\byeast\b|\bfungus\b|\bsingle-celled\b"),
    (r"\bzebrafish\b", r"\bzebrafish\b|\bfish\b"),
    (r"\bmacaques?\b|\bmarmosets?\b|\bnon-human primates?\b",
     r"\bmonkeys?\b|\bmacaques?\b|\bmarmosets?\b|\bprimates?\b|\banimals?\b"),
    (r"\bcell line\b|\bcultured cells\b|\bin vitro\b",
     r"\bcell line\b|\bcells? in a dish\b|\bcultured\b|\bin cells\b|\blab dish\b|\bin the lab\b"),
]

# Kontrola G (2026-10-11): VYHRADA SE V BEGINNER REGISTRU NEZKRACUJE.
#
# Blok B hlida jen to, ze se do beginner textu prenesou slova o druhu a
# pohlavi. Nestaci to: 10. 10. 2026 dostala entita Alzheimer's disease do
# odborneho textu celou klinickou vyhradu ("clinically unproven in people...
# not shown to help patients") a beginner verze zustala bez ni -- a blok B
# to propustil, protoze slovo "mice" v obou bylo. Presne ten nalez, kvuli
# kteremu se ten text opravoval (DIS-02), tedy prezil v beginner vrstve.
#
# Pravidlo je stejne jako pravidlo 14 v verify_academy.py: zkratit
# zacatecnikovi vyklad je v poradku, zkratit mu vyhrady ne. Tahle kontrola
# nemuze overit, ze beginner text rika spravnou vec -- zadna regule to
# neumi. Dela jen jednu vec: kdyz odborny text nese vyhradu a beginner
# NEMA ANI JEDNU, oznaci ten par k precteni.
HEDGES = [
    # Zamerne UZKE. Prvni verze 11. 10. 2026 brala i \bdependent\b a \bdepends on\b
    # a vystrelila 20x na slozeninach typu "cap-dependent translation" nebo
    # "mTORC1-dependent" -- to nejsou vyhrady, to jsou technicke termity.
    # Brana, ktera pri prvnim spusteni vyda 20 falesnych poplachu, se umlci,
    # takze tady plati presnost pred zachytem. Rozsah platnosti (druh, pohlavi,
    # bunecna linie) uz hlida blok B, tady jde jen o VYSLOVNE NE-TVRZENI.
    r"\bnot shown\b|\bunproven\b|\bnot proven\b|\bnot established\b|\bnot settled\b",
    r"\buntested\b|\bnot tested\b|\bnever (?:been )?(?:measured|tested|shown)\b",
    r"\bno (?:human|clinical|direct|published|survival) (?:data|evidence|trial|endpoint)\b",
    r"\bno evidence\b|\bnot measured\b|\bnot resolved\b|\bnot addressed\b",
    r"\bcontested\b|\bdisputed\b|\bunsettled\b|\bcontradict",
    r"\bpoints the other way\b|\bthe other direction\b",
    r"\bphase 1\b|\bphase 2\b|\bopen-label\b|\buncontrolled\b",
    r"\bsingle study\b|\bone study\b|\bsingle (?:mouse|human|trial)\b|\bn\s?=\s?\d",
    r"\bdoes not (?:mean|establish|show|prove)\b|\bcaution\b|\bcaveat\b",
]
# Beginner protihodnoty: prosta rec pro totez, zamerne siroke. Cilem je
# zachytit par, ktery vyhradu NEMA VUBEC, ne vnucovat formulaci -- karta H4
# rika "that's only been directly shown in flies and worms" a to je platna
# vyhrada, jen jinymi slovy.
HEDGES_BEGINNER = HEDGES + [
    r"\bnot\b|\bno one\b|\bnobody\b|\bnever\b|\bn't\b|\bwithout\b",
    r"\bdon't know\b|\bstill\b|\bso far\b|\byet\b|\bassumed?\b|\bthought\b",
    r"\bjust one\b|\bonly\b|\bsmall\b|\bearly\b|\bquestion\b|\bargu|\bdebat",
    r"\bmay\b|\bmight\b|\bwhether\b|\bunclear\b|\bunknown\b|\bseems?\b",
]
SID_RE = re.compile(r"\b[A-Z][A-Z]{1,7}20\d\d[A-Z]?\b|\b[A-Z][A-Z]{1,7}19\d\d[A-Z]?\b")

out = []
def warn(code, where, msg): out.append("%s  %-38s %s" % (code, where[:38], msg))

studies = {s["sid"] for s in load("atlas_data/studies_baked.json")}
model = load("pathway/model.json")
ents = load("atlas_data/entities_baked.json")
gaps = load("atlas_data/gaps_baked.json")

texts = []  # (misto, text)
for n in model["nodes"]:
    for k, v in (n.get("explain") or {}).items():
        texts.append(("node %s.%s" % (n["id"], k), v))
    for role in n.get("context_roles") or []:
        texts.append(("node %s.role" % n["id"], role[1]))
for c in model.get("compartments", []):
    texts.append(("band %s" % c["id"], c.get("blurb") or ""))
for i in model["interactions"]:
    for k in ("mechanism", "mechanism_beginner", "teaching_note", "boundary"):
        texts.append(("edge %s.%s" % (i["id"], k), i.get(k) or ""))
for e in ents:
    texts.append(("entity %s" % e["name"], e.get("desc") or ""))
    texts.append(("entity %s.beginner" % e["name"], e.get("desc_beginner") or ""))
for g in gaps:
    for k in ("title", "basis", "basis_beginner", "hyp", "hyp_beginner", "changed", "open_now"):
        texts.append(("gap %s.%s" % (g["id"], k), g.get(k) or ""))

# A
for where, t in texts:
    for word, fix, _ in scan_wording(t):
        warn("A", where, "absolutni formulace: '%s' -- misto toho: %s" % (word, fix))
# B
pairs = [("edge " + i["id"], i.get("mechanism") or "", i.get("mechanism_beginner") or "") for i in model["interactions"]]
pairs += [("entity " + e["name"], e.get("desc") or "", e.get("desc_beginner") or "") for e in ents]
pairs += [("gap %s.basis" % g["id"], g.get("basis") or "", g.get("basis_beginner") or "") for g in gaps]
for where, full, beg in pairs:
    if not beg:
        continue
    for need, ok in QUALIFIERS:
        if re.search(need, full, re.I) and not re.search(ok, beg, re.I):
            warn("B", where, "beginner nema kvalifikator odpovidajici /%s/" % need)
# G -- vyhrada se v beginner registru nezkracuje (2026-10-11)
def _hedges(text, pats):
    return sum(1 for pat in pats if re.search(pat, text, re.I))
for where, full, beg in pairs:
    if not beg:
        continue
    n_full = _hedges(full, HEDGES)
    if n_full and not _hedges(beg, HEDGES_BEGINNER):
        warn("G", where, "odborny text nese %d vyhrad, beginner ani jednu" % n_full)

# C
for i in model["interactions"]:
    both = set(i["evidence"]["supporting"]) & set(i["evidence"]["conflicting"])
    if both:
        warn("C", "edge " + i["id"], "studie zaroven supporting i conflicting: %s" % ", ".join(sorted(both)))
# D
for where, t in texts:
    for sid in set(SID_RE.findall(t)):
        if sid not in studies and not sid.startswith(("NCT", "PMID", "ATP", "ADP", "AMP")):
            warn("D", where, "kod %s neni v korpusu" % sid)

# E
linked = set()
for i in model["interactions"]:
    linked.update(i["evidence"]["supporting"]); linked.update(i["evidence"]["conflicting"])
for e in ents:
    linked.update(e.get("studies") or [])
for g in gaps:
    linked.update(g.get("studies") or [])
orphans = sorted(studies - linked)
for sid in orphans:
    warn("E", "study " + sid, "osirela: zadna hrana, entita ani otazka")
# F
refs = []
for i in model["interactions"]:
    for k in ("supporting", "conflicting"):
        refs += [("edge %s.%s" % (i["id"], k), x) for x in i["evidence"][k]]
try:
    for r in load("atlas_data/relations_baked.json")["edges"]:
        refs += [("relation %s.st" % r["id"], x) for x in r.get("st") or []]
        refs += [("relation %s.cf" % r["id"], x) for x in r.get("cf") or []]
except (OSError, KeyError):
    pass
for e in ents:
    refs += [("entity " + e["name"], x) for x in e.get("studies") or []]
for g in gaps:
    refs += [("gap %s.studies" % g["id"], x) for x in g.get("studies") or []]
for where, sid in refs:
    if sid not in studies:
        warn("F", where, "odkaz na %s, ktera neni v korpusu (web/API ji zahodi)" % sid)

# Vyjimky: vedome prijate nalezy s duvodem (consistency_allow.json)
allow_path = os.path.join(HERE, "consistency_allow.json")
allow = load("consistency_allow.json") if os.path.exists(allow_path) else []
for a in allow:
    if not (a.get("code") and a.get("where") and a.get("reason")):
        sys.exit("consistency_allow.json: kazda vyjimka potrebuje code, where a reason: %r" % a)
used, allowed, remaining = set(), [], []
for line in out:
    code, where = line[:1], line[3:41].strip()
    hit = next((i for i, a in enumerate(allow)
                if a["code"] == code and a["where"] == where and a.get("match", "") in line), None)
    if hit is None:
        remaining.append(line)
    else:
        used.add(hit); allowed.append((line, allow[hit]["reason"]))
stale = [a for i, a in enumerate(allow) if i not in used]

print("check_consistency: %d nalezu, %d v povolenych vyjimkach, %d neplatnych vyjimek"
      % (len(remaining), len(allowed), len(stale)))
for line in sorted(remaining):
    print("  " + line)
for line, why in sorted(allowed):
    print("  [povoleno] " + line + "  -- " + why)
for a in stale:
    print("  [stale] vyjimka %s %s uz nic nezachytava -- smaz ji z consistency_allow.json"
          % (a["code"], a["where"]))
if "--strict" in sys.argv and (remaining or stale):
    sys.exit(1)
