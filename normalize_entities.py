#!/usr/bin/env python3
"""
normalize_entities.py -- Fáze 6, krok 2: normalizace entit.

Bere volný text z polí AI_Target / AI_Intervention / AI_Species v
atlas_data/studies_baked.json a připravuje kanonický seznam entit.

Postup odpovídá čtyřem otázkám z docs/PHASE6_discoverability_plan.md.
Kroky 1-3 dělá skript sám, krok 4 předkládá člověku:

  1. Je to vůbec entita?   -> ustřihne nominalizace ("mTOR activity" -> mTOR)
                              a metodologické hlavičky ("Biochemical/genetic (AMPK)" -> AMPK)
  2. Týž řetězec jinak?    -> case, mezery, spojovníky, řecká písmena
  3. Známé synonymum?      -> dotaz do HGNC (--hgnc), NIKDY z hlavy
  4. Je ten rozdíl reálný? -> tohle skript NEROZHODUJE, jen předloží

ZÁSADA: při pochybnosti NESLOUČIT. Chybné sloučení je nevratné a po zápisu
už nikdo nepozná, že tam byly dvě věci. Chybějící vazba je viditelná a levná.

Spuštění:
    py normalize_entities.py              # bez sítě, jen lokální pravidla
    py normalize_entities.py --hgnc       # + ověření symbolů proti HGNC

Výstupy (nic nepřepisuje v Airtable, jen zapisuje soubory):
    atlas_data/entities_review.csv        <- PRACOVNÍ SEZNAM PRO OLIVERA
    atlas_data/entities_auto.json         <- co se vyřešilo automaticky + proč
    atlas_data/relation_candidates.csv    <- návrhy hran pro tabulku Relations
    atlas_data/PHASE6_normalize_report.md <- souhrn
    atlas_data/.hgnc_cache.json           <- cache dotazů, ať se neopakují
"""

import os, sys, re, json, csv, time, unicodedata, collections
import urllib.request, urllib.parse

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "atlas_data")
STUDIES = os.path.join(DATA, "studies_baked.json")

REVIEW_CSV = os.path.join(DATA, "entities_review.csv")
AUTO_JSON = os.path.join(DATA, "entities_auto.json")
RELATIONS_CSV = os.path.join(DATA, "relation_candidates.csv")
REPORT_MD = os.path.join(DATA, "PHASE6_normalize_report.md")
HGNC_CACHE = os.path.join(DATA, ".hgnc_cache.json")

USE_HGNC = "--hgnc" in sys.argv

# Práh quality gate z plánu fáze 6: stránka vznikne jen při >=3 studiích.
# Atom pod tímto prahem nemůže stránku vyrobit, takže se odkládá bez
# rozhodování -- tím padá ~63 % položek z Oliverova stolu.
PAGE_THRESHOLD = 3


# ---------------------------------------------------------------------------
# Krok 1a -- co není entita
# ---------------------------------------------------------------------------

# Nominalizace: podstatné jméno nalepené na entitu. "mTOR activity" není jiná
# entita než mTOR. Odstřihává se ZE KONCE a vždy se zaznamená, co se ustřihlo.
TRAILING_MODIFIERS = [
    "signaling pathway", "signalling pathway", "nutrient-sensing machinery",
    "amino-acid sensors", "signaling", "signalling", "activation", "inhibition",
    "activity", "pathway", "network", "axis", "cascade", "branch", "arm",
    "core", "machinery", "module", "levels", "function", "status",
]

# Pozor: "complex" se NEodstřihává. "TSC complex" je skutečná entita
# (heterodimer TSC1/TSC2), zatímco "mTOR complex" je fráze. Rozhodnutí
# nechávám na člověku -- viz FLAG_AMBIGUOUS níže.
FLAG_AMBIGUOUS = ["complex", "family", "subunit", "isoform"]

# Metodologické hlavičky pole AI_Intervention. Gramatika toho pole je
# "<metoda> (<detail>)" -- "Biochemical/genetic (AMPK/TSC2)". Hlavička se
# zahodí, entita je uvnitř závorky. Naopak "Rapamycin (mTOR inhibition)" má
# hlavičku = látku, takže se bere hlavička a závorka je poznámka.
METHOD_HEADS = {
    "biochemical", "genetic", "biochemical/genetic", "structural",
    "cryo-em", "crystallography", "not applicable", "review", "n/a",
    "various", "observational", "in vitro", "in silico", "computational",
    "pharmacologic", "pharmacological", "dietary", "surgical", "imaging",
    "sequencing", "proteomics", "screen", "knockout", "knockdown",
}

# Věty, které se do pole entity dostaly omylem. Zahazují se úplně.
# POZOR: "vs" tu záměrně NENÍ. "Metformin (vs sulphonylurea)" je platná
# intervence a zamítnutím na "vs" by se ztratil Metformin. Porovnání se místo
# toho rozsekává jako oddělovač (SPLIT_RE) -- obě ramena jsou entity.
NOT_ENTITIES = re.compile(
    r"^(not applicable|none|unknown|n/?a|see (above|text)|multiple|misc\.?|other)\b"
    r"|^\W*$"
    r"|^\d+(\.\d+)?[-\s]?(fold|%|x)\b"          # ">25-fold selective over mTORC2"
    r"|\b(sparing|selective over)\b",
    re.I,
)

# Metodologické termíny, které projdou extrakcí ze závorky a vypadají pak jako
# entita. "Not applicable (review)" -> "review", "Structural (cryo-EM)" ->
# "cryo-EM". Ani jedno není entita; kontroluje se AŽ PO extrakci, protože
# před ní jsou schované uvnitř závorky.
REJECT_ATOMS = {
    "review", "narrative review", "cryo-em", "cryoem", "crystallography",
    "structural", "structure", "biochemical", "genetic", "biochemistry",
    "in vitro", "in vivo", "in silico", "computational", "observational",
    "epidemiology", "meta-analysis", "systematic review", "rct", "trial",
    "clinical trial", "case report", "modeling", "simulation", "assay",
    "imaging", "sequencing", "proteomics", "screen", "various", "none",
    "dietary", "pharmacologic", "pharmacological", "indirect", "unknown",
}

# Kontrolovaný slovník pro AI_Species. Tohle pole entity skoro neobsahuje --
# je to ~10 modelových systémů zapsaných 140 způsoby, takže se mapuje
# klíčovými slovy a člověka nepotřebuje skoro vůbec.
SPECIES_MAP = [
    (r"\bhuman|\bpatient|\bhek ?293|\bhela|\bclinical|\bvolunteer", "Human"),
    (r"\bmouse|\bmice|\bmurine|c57|\bknock-?in mice", "Mouse"),
    (r"\brat\b|\brats\b", "Rat"),
    (r"drosophila|\bfly\b|\bflies\b", "Drosophila"),
    (r"c\.? ?elegans|\bworm", "C. elegans"),
    (r"yeast|cerevisiae|\bs\.? ?pombe", "Yeast"),
    (r"\bdog|canine", "Dog"),
    (r"zebrafish|danio", "Zebrafish"),
    (r"cryo-?em|crystal|structure|recombinant protein", "Structure / in vitro"),
    (r"cell ?lines?|cultured cells|mammalian cells|in vitro", "Cell culture"),
    (r"\breview\b|meta-?analysis", "Review (no model)"),
]


# ---------------------------------------------------------------------------
# Krok 2 -- mechanická normalizace řetězce
# ---------------------------------------------------------------------------

GREEK = {"α": "alpha", "β": "beta", "γ": "gamma", "δ": "delta",
         "ε": "epsilon", "κ": "kappa", "λ": "lambda", "μ": "mu", "ω": "omega"}


def norm_key(s):
    """Klíč pro porovnání. Agresivní schválně -- slučuje jen zápis, ne význam."""
    s = unicodedata.normalize("NFKC", s)
    for g, r in GREEK.items():
        s = s.replace(g, r)
    s = s.lower().strip()
    s = re.sub(r"[‐-―−]", "-", s)   # sjednoť pomlčky
    s = re.sub(r"[\s_]+", " ", s)
    s = re.sub(r"\s*-\s*", "-", s)
    s = re.sub(r"[.·]+$", "", s).strip()
    s = re.sub(r"\bm-?tor\b", "mtor", s)           # m-TOR / mTOR
    s = re.sub(r"\b(mtorc|torc) ?([12])\b", r"\1\2", s)   # "mTORC 1" -> mtorc1
    return s.strip()


def strip_modifiers(s):
    """Ustřihne nominalizace z konce. Vrací (jádro, seznam_ustřižených)."""
    stripped = []
    changed = True
    while changed:
        changed = False
        low = s.lower().rstrip(" .")
        for m in TRAILING_MODIFIERS:
            if low.endswith(" " + m):
                s = s[: len(s.rstrip(" .")) - len(m) - 1].rstrip(" -/.")
                stripped.append(m)
                changed = True
                break
    return s.strip(), stripped


def slugify(s):
    s = unicodedata.normalize("NFKD", s)
    for g, r in GREEK.items():
        s = s.replace(g, r)
    s = s.lower()
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    return s or "unnamed"


# ---------------------------------------------------------------------------
# Krok 1b -- rozbití složených výrazů podle gramatiky pole
# ---------------------------------------------------------------------------

SPLIT_RE = re.compile(r"\s*(?:/|&|\+|;|,| and | vs\.? | versus )\s*", re.I)

# Řetěz signálu se pozná jen podle lomítka. "&" a "," jsou spojky -- "mTORC1 &
# mTORC2" znamená "obojí", ne "mTORC1 reguluje mTORC2". Bez tohoto rozlišení
# vznikla falešná hrana mTORC1 -> mTORC2 z 18 studií, což je nesmysl.
CHAIN_SPLIT_RE = re.compile(r"\s*/\s*")


def expand_numeric_suffix(parts):
    """'CASTOR1/2' se rozpadne na ['CASTOR1', '2']. Holé číslo za atomem
    končícím číslicí je zkratka pro sourozence -- doplní se prefix.
    GATOR1/GATOR2 je psáno plně a projde beze změny."""
    out = []
    for p in parts:
        if re.fullmatch(r"\d{1,2}[a-z]?", p, re.I) and out:
            m = re.match(r"^(.*?)(\d{1,2}[a-z]?)$", out[-1])
            if m and m.group(1):
                out.append(m.group(1) + p)
                continue
        out.append(p)
    return out


def split_target(raw):
    """AI_Target: 'AMPK / TSC / Rag / mTORC1' je řetěz signálu.
    Vrací (atomy, poznámka, je_řetěz). Pořadí se NEZAHAZUJE -- používá se
    na návrhy hran, ale JEN pokud byl oddělovačem lomítko."""
    note = " ".join(re.findall(r"\(([^)]*)\)", raw))
    body = re.sub(r"\([^)]*\)", " ", raw)
    is_chain = "/" in body and not re.search(r"[&,;]| and ", body)
    parts = [a.strip() for a in SPLIT_RE.split(body) if a.strip()]
    return expand_numeric_suffix(parts), note, is_chain


def split_intervention(raw):
    """AI_Intervention: gramatika '<metoda> (<entita>)' NEBO '<látka> (<mechanismus>)'.
    Rozhoduje se podle toho, jestli je hlavička metodologické slovo."""
    m = re.match(r"^([^(]+)\((.*)\)\s*$", raw.strip())
    if not m:
        # Závorku uprostřed ("Metformin (vs sulphonylurea) monotherapy")
        # nejdřív odstraň, ať její obsah neshodí celý řetězec.
        body = re.sub(r"\([^)]*\)", " ", raw)
        parts = [a.strip() for a in SPLIT_RE.split(body) if a.strip()]
        return expand_numeric_suffix(parts), "", False
    head, inner = m.group(1).strip(), m.group(2).strip()
    head_key = head.lower().strip(" -/")
    is_method = head_key in METHOD_HEADS or any(
        h in head_key for h in ("biochem", "genetic", "structur", "not applicable")
    )
    src = inner if is_method else head
    keep = head if is_method else inner
    parts = [a.strip() for a in SPLIT_RE.split(src) if a.strip()]
    return expand_numeric_suffix(parts), keep, False


def map_species(raw):
    hits = []
    for pat, canon in SPECIES_MAP:
        if re.search(pat, raw, re.I) and canon not in hits:
            hits.append(canon)
    return hits or ["UNMAPPED"]


# ---------------------------------------------------------------------------
# Krok 3 -- HGNC (jen když --hgnc; dotaz, nikdy odhad)
# ---------------------------------------------------------------------------

def load_cache():
    if os.path.exists(HGNC_CACHE):
        try:
            return json.load(open(HGNC_CACHE, encoding="utf-8"))
        except Exception:
            pass
    return {}


def hgnc_lookup(symbol, cache):
    """Vrátí {'hgnc_id','symbol','matched_as'} nebo None. Ptá se postupně na
    schválený symbol, alias a předchozí symbol."""
    key = symbol.lower()
    if key in cache:
        return cache[key]
    result = None
    for field in ("symbol", "alias_symbol", "prev_symbol"):
        url = "https://rest.genenames.org/search/%s/%s" % (
            field, urllib.parse.quote(symbol))
        try:
            req = urllib.request.Request(url, headers={"Accept": "application/json"})
            d = json.load(urllib.request.urlopen(req, timeout=20))
            docs = d.get("response", {}).get("docs", [])
            if docs:
                result = {"hgnc_id": docs[0].get("hgnc_id"),
                          "symbol": docs[0].get("symbol"),
                          "matched_as": field}
                break
        except Exception as e:
            print("    HGNC %s/%s: %s" % (field, symbol, e))
        time.sleep(0.2)
    cache[key] = result
    return result


# ---------------------------------------------------------------------------
# Hlavní průchod
# ---------------------------------------------------------------------------

def main():
    studies = json.load(open(STUDIES, encoding="utf-8"))
    print("Načteno %d studií\n" % len(studies))

    # atom -> {mentions, raw_variants, studies, stripped, flags}
    atoms = collections.defaultdict(
        lambda: {"mentions": 0, "raw": set(), "studies": set(),
                 "stripped": set(), "flags": set(), "fields": set(),
                 "display": None})
    rejected = collections.Counter()
    relation_rows = []
    species_rows = []

    for st in studies:
        sid = st.get("sid") or st.get("id")

        for field, splitter in (("ai_target", split_target),
                                ("ai_intervention", split_intervention)):
            raw = (st.get(field) or "").strip()
            if not raw:
                continue
            parts, note, is_chain = splitter(raw)

            chain = []
            for p in parts:
                if NOT_ENTITIES.search(p):
                    rejected[p.strip()] += 1
                    continue
                core, stripped = strip_modifiers(p)
                if not core or NOT_ENTITIES.search(core):
                    rejected[p.strip()] += 1
                    continue
                k = norm_key(core)
                if not k or len(k) < 2:
                    rejected[p.strip()] += 1
                    continue
                # Kontrola metodologických termínů AŽ TADY: před extrakcí ze
                # závorky nejsou vidět ("Not applicable (review)" -> "review").
                if k in REJECT_ATOMS:
                    rejected[p.strip()] += 1
                    continue
                a = atoms[k]
                a["mentions"] += 1
                a["raw"].add(p.strip())
                a["studies"].add(sid)
                a["fields"].add(field)
                if a["display"] is None or len(core) < len(a["display"]):
                    a["display"] = core
                for s_ in stripped:
                    a["stripped"].add(s_)
                for amb in FLAG_AMBIGUOUS:
                    if amb in k.split():
                        a["flags"].add("ambiguous:" + amb)
                chain.append(k)

            # Pořadí v AI_Target = směr signálu -> návrhy hran.
            # Jen pro řetězy oddělené lomítkem; "A & B" je spojka, ne regulace.
            if field == "ai_target" and is_chain and len(chain) >= 2:
                for i in range(len(chain) - 1):
                    if chain[i] != chain[i + 1]:
                        relation_rows.append({
                            "source_key": chain[i],
                            "target_key": chain[i + 1],
                            "study_sid": sid,
                            "raw_field": raw,
                            "note": note,
                            "status": "Proposed",
                            "confidence": "heuristic-order",
                        })

        sp = (st.get("ai_species") or "").strip()
        if sp:
            species_rows.append({"sid": sid, "raw": sp,
                                 "mapped": "; ".join(map_species(sp))})

    print("Atomů unikátních: %d" % len(atoms))
    print("Zamítnuto jako 'není entita': %d výskytů, %d unikátních"
          % (sum(rejected.values()), len(rejected)))

    # --- krok 3: HGNC ---
    cache = load_cache()
    if USE_HGNC:
        cands = [k for k, v in atoms.items()
                 if v["mentions"] >= PAGE_THRESHOLD
                 and re.fullmatch(r"[a-z0-9\-]{2,12}", k)]
        print("\nHGNC: ověřuji %d kandidátů ..." % len(cands))
        for i, k in enumerate(sorted(cands), 1):
            r = hgnc_lookup(atoms[k]["display"], cache)
            if r:
                atoms[k]["flags"].add("hgnc:%s" % r["hgnc_id"])
                atoms[k]["hgnc"] = r
            if i % 10 == 0:
                print("   %d/%d" % (i, len(cands)))
        json.dump(cache, open(HGNC_CACHE, "w", encoding="utf-8"),
                  ensure_ascii=False, indent=1)
    else:
        print("\n(HGNC přeskočeno -- spusť s --hgnc pro ověření symbolů)")

    # --- rozdělení na "k rozhodnutí" a "odloženo" ---
    ranked = sorted(atoms.items(), key=lambda kv: -kv[1]["mentions"])
    decide = [(k, v) for k, v in ranked if len(v["studies"]) >= PAGE_THRESHOLD]
    defer = [(k, v) for k, v in ranked if len(v["studies"]) < PAGE_THRESHOLD]

    # --- pracovní seznam ---
    os.makedirs(DATA, exist_ok=True)
    with open(REVIEW_CSV, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["rank", "mentions", "n_studies", "suggested_name",
                    "suggested_slug", "hgnc_id", "raw_variants", "stripped",
                    "flags", "fields", "example_studies",
                    "DECISION", "CANONICAL_NAME", "TYPE", "MERGE_INTO", "NOTE"])
        for i, (k, v) in enumerate(decide, 1):
            hg = v.get("hgnc") or {}
            w.writerow([
                i, v["mentions"], len(v["studies"]),
                v["display"], slugify(v["display"]),
                hg.get("hgnc_id", ""),
                " | ".join(sorted(v["raw"])[:6]),
                ", ".join(sorted(v["stripped"])),
                ", ".join(sorted(v["flags"])),
                ", ".join(sorted(v["fields"])),
                ", ".join(sorted(v["studies"])[:5]),
                "", "", "", "", "",
            ])
        w.writerow([])
        w.writerow(["--- ODLOŽENO: pod prahem %d studií, stránku vyrobit nemůže,"
                    " rozhodovat se nemusí ---" % PAGE_THRESHOLD])
        for i, (k, v) in enumerate(defer, 1):
            w.writerow([i, v["mentions"], len(v["studies"]), v["display"],
                        slugify(v["display"]), "", " | ".join(sorted(v["raw"])[:3]),
                        "", "defer:singleton" if v["mentions"] == 1 else "defer",
                        ", ".join(sorted(v["fields"])), "", "defer", "", "", "", ""])

    # --- co se vyřešilo samo ---
    auto = {
        "generated": time.strftime("%Y-%m-%d %H:%M"),
        "page_threshold": PAGE_THRESHOLD,
        "n_studies": len(studies),
        "n_atoms": len(atoms),
        "n_to_decide": len(decide),
        "n_deferred": len(defer),
        "rejected_not_entities": rejected.most_common(),
        "species_vocabulary": collections.Counter(
            m for r in species_rows for m in r["mapped"].split("; ")).most_common(),
        "species_unmapped": sorted({r["raw"] for r in species_rows
                                    if "UNMAPPED" in r["mapped"]}),
    }
    json.dump(auto, open(AUTO_JSON, "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)

    # --- návrhy hran ---
    seen = collections.Counter()
    for r in relation_rows:
        seen[(r["source_key"], r["target_key"])] += 1
    with open(RELATIONS_CSV, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["source", "target", "n_studies", "study_sids",
                    "status", "confidence", "example_raw", "REVIEWED", "SIGN"])
        by_pair = collections.defaultdict(list)
        for r in relation_rows:
            by_pair[(r["source_key"], r["target_key"])].append(r)
        for (a, b), rows in sorted(by_pair.items(), key=lambda kv: -len(kv[1])):
            w.writerow([
                atoms[a]["display"], atoms[b]["display"], len(rows),
                ", ".join(sorted({x["study_sid"] for x in rows})[:6]),
                "Proposed", "heuristic-order-in-AI_Target",
                rows[0]["raw_field"][:120], "", "",
            ])

    # --- report ---
    lines = [
        "# Fáze 6, krok 2 — normalizace entit", "",
        "Vygenerováno: %s · %d studií" % (auto["generated"], len(studies)), "",
        "## Kolik práce zbývá na člověka", "",
        "| | počet |", "|---|---|",
        "| Unikátních atomů po rozbití | %d |" % len(atoms),
        "| **K rozhodnutí (>= %d studií)** | **%d** |" % (PAGE_THRESHOLD, len(decide)),
        "| Odloženo (pod prahem) | %d |" % len(defer),
        "| Zamítnuto jako 'není entita' | %d unikátních |" % len(rejected), "",
        "Rozhoduje se jen o horní skupině. Položka pod prahem nemůže projít",
        "quality gate, takže na ni nemá smysl utrácet pozornost teď.", "",
        "## Návrhy hran pro tabulku Relations", "",
        "Z pořadí atomů v AI_Target (`A / B / C` = směr signálu) vzniklo",
        "**%d unikátních dvojic** z %d výskytů. Všechny jsou `Proposed` a" % (len(by_pair), len(relation_rows)),
        "`heuristic-order` — pořadí ve volném textu NENÍ důkaz směru regulace,",
        "je to jen kandidát pro tvůj existující review workflow.", "",
        "## Nejčastější atomy", "", "| # | atom | zmínek | studií | varianty |",
        "|---|---|---|---|---|",
    ]
    for i, (k, v) in enumerate(decide[:25], 1):
        lines.append("| %d | %s | %d | %d | %s |" % (
            i, v["display"], v["mentions"], len(v["studies"]),
            "; ".join(sorted(v["raw"])[:3]).replace("|", "/")))
    lines += ["", "## Zamítnuto (nejde o entity)", ""]
    for t, n in rejected.most_common(20):
        lines.append("- `%s` (%d×)" % (t, n))
    lines += ["", "## AI_Species — kontrolovaný slovník", ""]
    for name, n in auto["species_vocabulary"]:
        lines.append("- %s — %d" % (name, n))
    if auto["species_unmapped"]:
        lines += ["", "Nenamapováno (doplň pravidlo do SPECIES_MAP):", ""]
        for u in auto["species_unmapped"][:15]:
            lines.append("- `%s`" % u)
    open(REPORT_MD, "w", encoding="utf-8").write("\n".join(lines) + "\n")

    print("""
Hotovo.
  k rozhodnutí : %d
  odloženo     : %d
  zamítnuto    : %d unikátních
  návrhy hran  : %d dvojic

  %s   <- tohle vyplní Oliver (sloupce DECISION/CANONICAL_NAME/TYPE)
  %s
  %s
  %s
""" % (len(decide), len(defer), len(rejected), len(by_pair),
       os.path.relpath(REVIEW_CSV, HERE), os.path.relpath(RELATIONS_CSV, HERE),
       os.path.relpath(REPORT_MD, HERE), os.path.relpath(AUTO_JSON, HERE)))


if __name__ == "__main__":
    main()
