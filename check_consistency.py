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

ABSOLUTE = [r"\bthe single most\b", r"\bthe one thing\b", r"\bthe entire (?:mTOR )?field\b",
            r"\bthe whole story of\b", r"\bonly at the lysosome\b", r"\bis only switched on here\b",
            r"(?<!one of )(?<!among )\bthe most (?:conserved|reliable|important|precise|drug-friendly|pharmacologically)\b",
            r"\bpioneer(?:ed)? of\b", r"\bthe leading longevity\b", r"\bthe best-known way\b",
            r"\bfounding paper\b", r"\bbirth of the field\b"]
QUALIFIERS = [  # (v odbornem textu, co musi byt i v beginner textu)
    (r"\bfemales?\b", r"\bfemales?\b|\bwomen\b|\bgirls?\b"),
    (r"\b(?:Drosophila|flies)\b", r"\bfl(?:y|ies)\b|\binsects?\b"),
    (r"\bin mice\b", r"\bmice\b|\bmouse\b|\banimals?\b|\brodents?\b"),
    (r"\bcell line\b|\bcultured cells\b", r"\bcell line\b|\bcells? in a dish\b|\bcultured\b|\bin cells\b"),
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
    for pat in ABSOLUTE:
        m = re.search(pat, t, re.I)
        if m:
            warn("A", where, "absolutni formulace: '%s'" % m.group(0))
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
