#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
tools/seo/build_data_exports.py -- Ukol 3 (SEO P0 brief 2026-09-02).

Vygeneruje skutecne stahovatelne CSV/JSON exporty z atlas_data/*.json do
data/exports/ -- pro Google Dataset Search, Hugging Face / Kaggle
outreach, a pro kohokoliv, kdo chce data mimo web scraping. Nejde o nove
HTML stranky (pravidlo "nikdy nezvysovat pocet stranek" se tyka thin-
content HTML, ne skutecnych datovych souboru) -- data/exports/*.csv a
*.json nejsou v sitemap.xml a nemaji svuj vlastni <title>/H1.

Vstup:  atlas_data/studies_baked.json, atlas_data/entities_baked.json
Vystup: data/exports/studies.csv, data/exports/studies.json,
        data/exports/entities.csv, data/exports/entities.json,
        data/exports/README.md,
        data/exports/manifest.json (name/format/bytes/sha256 -- pro
        build_pages.py, aby DATASET_REF.distribution a /data/ stranka
        vzdy sedely na skutecne existujici soubory, ne na rucne psany
        seznam, ktery se rozejde pri prvni zmene).

Nezasahuje do atlas_data/*.json (jen cte) ani do pathway/model.json.

Pouziti:
    python3 tools/seo/build_data_exports.py
"""
import csv
import datetime
import hashlib
import json
import os
import re
import sys
import unicodedata

HERE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DATA = os.path.join(HERE, "atlas_data")
OUT = os.path.join(HERE, "data", "exports")
SITE = "https://mtor-atlas.org"
PAGE_THRESHOLD = 3  # musi sedet s build_pages.py -- viz README.md v OUT

# Musi sedet s build_pages.py's TYPE_DIR. Duplikovano zamerne (mala,
# stabilni mapa) misto importu z build_pages.py, aby tenhle skript zustal
# spustitelny nezavisle a bez vedlejsich efektu velkeho build modulu.
TYPE_DIR = {
    "Gene/Protein": "gene",
    "Pathway/Complex": "complex",
    "Drug": "drug",
    "Intervention": "intervention",
    "Biological process": "process",
    "Disease": "disease",
    "Outcome": "outcome",
    "Organelle": "organelle",
    "Nutrient/Metabolite": "nutrient",
    "Condition": "condition",
}

STUDY_FIELDS = [
    ("sid", "sid"), ("title", "title"), ("authors", "authors"),
    ("year", "year"), ("journal", "journal"), ("legacy_tier", "tier"),
    ("pyramid", "pyramid"), ("category", "category"), ("model", "model"),
    ("peer_reviewed", "peer"), ("doi", "doi"), ("pmid", "pmid"),
    ("pmcid", "pmcid"), ("finding", "finding"), ("abstract", "abstract"),
    ("ai_intervention", "ai_intervention"), ("ai_target", "ai_target"),
    ("ai_species", "ai_species"), ("ai_effect", "ai_effect"),
    ("ai_dose", "ai_dose"), ("ai_samplesize", "ai_samplesize"),
    ("ai_effectsize", "ai_effectsize"), ("ai_limitations", "ai_limitations"),
]


def slugify(s):
    """Kopie build_pages.py's slugify() -- musi zustat bit-identicka, jinak
    se atlas_url ve datech rozejde se skutecnymi URL na webu."""
    s = unicodedata.normalize("NFKD", s)
    s = s.replace("α", "alpha").replace("β", "beta").replace("γ", "gamma")
    s = re.sub(r"['’ʼ`]", "", s)
    s = s.encode("ascii", "ignore").decode()
    s = s.lower()
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    return s or "unnamed"


def load(name):
    p = os.path.join(DATA, name)
    if not os.path.exists(p):
        sys.exit(f"Chybi {p} -- spust nejdriv sync_airtable.py / build_pages.py.")
    return json.load(open(p, encoding="utf-8"))


def write_verified_text(path, text):
    """Stejny bezpecny-zapis vzor jako measure_study_pages.py's
    write_verified: tmp + fsync + os.replace + nezavisle overeni delky."""
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8", newline="") as f:
        f.write(text)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)
    # newline="" on both sides: no newline translation on write or read, so
    # the verified length is the exact length that lands on disk.
    check = open(path, encoding="utf-8", newline="").read()
    assert len(check) == len(text), f"write verify failed for {path}: {len(check)} != {len(text)}"


def sha256_of(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _tier_bits():
    sys.path.insert(0, HERE)
    from chrome_shared import tier_bits
    return tier_bits


def build_studies_export(studies):
    tier_bits = _tier_bits()
    rows = []
    for s in studies:
        row = {out_key: (s.get(in_key) or "") for out_key, in_key in STUDY_FIELDS}
        # Zobrazovany evidencni kod (S/H/A/M/R/PP/RT) -- stejna funkce jako web
        # a API (chrome_shared.tier_bits); `legacy_tier` je jen puvodni ulozene
        # pismeno A-D a NEODPOVIDA zobrazenym kodum (A-D: B = H, C = A, D = M/R).
        code, label, _c, _o = tier_bits(s.get("tier"), s.get("pyramid"))
        row["evidence_code"] = code
        row["evidence_label"] = label
        row["atlas_url"] = f"{SITE}/study/{s['sid']}/"
        rows.append(row)
    fieldnames = ["sid", "evidence_code", "evidence_label"] + \
        [k for k, _ in STUDY_FIELDS if k != "sid"] + ["atlas_url"]
    return rows, fieldnames


def _pathway_nodes():
    """Uzly mapy drahy (pathway/model.json), male pismena. Stejny zdroj jako
    build_pages.py::gets_page -- entita pod prahem 3 studii dostane stranku,
    pokud je uzlem mapy."""
    nodes = set()
    pm = os.path.join(HERE, "pathway", "model.json")
    if os.path.exists(pm):
        with open(pm, encoding="utf-8") as fh:
            for i in json.load(fh).get("interactions", []):
                nodes.add(i["source"].lower())
                nodes.add(i["target"].lower())
    return nodes


def _name_to_node():
    # Jediny zdroj mapovani jmeno entity -> uzel mapy je chrome_shared.py.
    sys.path.insert(0, HERE)
    from chrome_shared import ENTITY_NAME_TO_NODE_ID
    return ENTITY_NAME_TO_NODE_ID


def entity_gets_page(x, nodes, name_to_node):
    """Stejne pravidlo jako build_pages.py::gets_page (studii >= prah NEBO
    uzel mapy). Drive export pouzival jen prah, takze 23 entit, ktere stranku
    maji diky mape, melo atlas_url prazdne."""
    if len(x.get("studies") or []) >= PAGE_THRESHOLD:
        return True
    node = name_to_node.get(x["name"], x["name"])
    return node.lower() in nodes


def build_entities_export(entities):
    rows = []
    nodes = _pathway_nodes()
    name_to_node = _name_to_node()
    for x in entities:
        n = len(x.get("studies") or [])
        d = TYPE_DIR.get(x["type"], "entity")
        slug = slugify(x["name"])
        has_page = entity_gets_page(x, nodes, name_to_node)
        row = {
            # Stabilni identifikator = stejne id jako v API (slugify(name)).
            "id": slug,
            "name": x.get("name") or "",
            "type": x.get("type") or "",
            "description": x.get("desc") or "",
            "description_beginner": x.get("desc_beginner") or "",
            "synonyms": x.get("synonyms") or "",
            "n_linked_studies": n,
            "has_page": "true" if has_page else "false",
            "atlas_url": f"{SITE}/{d}/{slug}/" if has_page else "",
        }
        rows.append(row)
    fieldnames = ["id", "name", "type", "description", "description_beginner",
                  "synonyms", "n_linked_studies", "has_page", "atlas_url"]
    return rows, fieldnames


def build_relations_export():
    """Hrany drahy (jen publikovane) ze stejneho zdroje jako web:
    atlas_data/relations_baked.json. Spojitelne se studiemi pres SID a
    s entitami pres source_id / target_id (= slugify(nazvu), jako v API)."""
    edges = load("relations_baked.json")["edges"]
    # Uzel mapy se muze jmenovat jinak nez entita (FOXO1/3 vs FoxO); id entity
    # bereme pres stejne mapovani, jake pouziva build_pages.py.
    node_to_entity = {v: k for k, v in _name_to_node().items()}
    ent = lambda n: slugify(node_to_entity.get(n, n))
    rows = []
    for e in edges:
        if not e.get("published", True):
            continue
        rows.append({
            "id": e["id"],
            "source": e.get("s") or "",
            "source_id": ent(e.get("s") or ""),
            "target": e.get("t") or "",
            "target_id": ent(e.get("t") or ""),
            "effect": e.get("sign") or "",
            "type": e.get("type") or "",
            "directness": e.get("directness") or "",
            "timescale": e.get("ts") or "",
            "compartment": e.get("comp") or "",
            "species": e.get("sp") or "",
            "mechanism": e.get("mech") or "",
            "mechanism_beginner": e.get("mech_beginner") or "",
            "boundary": e.get("ctx") or "",
            "supporting_studies": ";".join(e.get("st") or []),
            "conflicting_studies": ";".join(e.get("cf") or []),
            "human_relevance": e.get("hr") or "",
            "consensus": e.get("cons") or "",
            "curation_status": e.get("status") or "",
            "review_status": "reviewed" if e.get("reviewed_by") else "unreviewed",
            "atlas_url": f"{SITE}/relation/{e['id']}/",
        })
    fieldnames = ["id", "source", "source_id", "target", "target_id", "effect",
                  "type", "directness", "timescale", "compartment", "species",
                  "mechanism", "mechanism_beginner", "boundary",
                  "supporting_studies", "conflicting_studies",
                  "human_relevance", "consensus", "curation_status",
                  "review_status", "atlas_url"]
    return rows, fieldnames


def write_csv(path, rows, fieldnames):
    lines = []
    import io
    buf = io.StringIO()
    # 25. 9. 2026: LF, ne CRLF. .gitattributes drzi *.csv jako eol=lf, takze
    # git pri commitu CRLF prepsal na LF a web (V2 bere exporty z gitu) servi-
    # roval jiny soubor, nez pro jaky manifest.json spocital velikost a sha256.
    # S lineterminator="\n" a bez \r v hodnotach je soubor bajtove stejny na
    # disku, v gitu i na webu.
    w = csv.DictWriter(buf, fieldnames=fieldnames, lineterminator="\n")
    w.writeheader()
    for r in rows:
        w.writerow({k: (v.replace("\r\n", "\n").replace("\r", "\n")
                        if isinstance(v, str) else v) for k, v in r.items()})
    write_verified_text(path, buf.getvalue())


def write_json(path, rows):
    write_verified_text(path, json.dumps(rows, indent=2, ensure_ascii=False) + "\n")


def main():
    os.makedirs(OUT, exist_ok=True)

    studies = load("studies_baked.json")
    entities = load("entities_baked.json")

    study_rows, study_fields = build_studies_export(studies)
    entity_rows, entity_fields = build_entities_export(entities)

    write_csv(os.path.join(OUT, "studies.csv"), study_rows, study_fields)
    write_json(os.path.join(OUT, "studies.json"), study_rows)
    write_csv(os.path.join(OUT, "entities.csv"), entity_rows, entity_fields)
    write_json(os.path.join(OUT, "entities.json"), entity_rows)
    rel_rows, rel_fields = build_relations_export()
    write_csv(os.path.join(OUT, "relations.csv"), rel_rows, rel_fields)
    write_json(os.path.join(OUT, "relations.json"), rel_rows)

    readme = f"""# Oliver's mTOR Atlas -- data exports

Machine-readable exports of the curated corpus behind
[Oliver's mTOR Atlas]({SITE}/), generated from the same source data as
the live site. Regenerated on every deploy by
`tools/seo/build_data_exports.py` -- if you're reading this from a
downloaded copy, check {SITE}/data/ for the current version.

## Files

- **studies.csv / studies.json** -- {len(study_rows)} hand-curated
  primary studies on the mTOR signaling pathway. Each row: Atlas ID
  (`sid`), `evidence_code` and `evidence_label` (the displayed study
  type: S synthesis of human data, H human study, A animal model, M
  molecular/in vitro, R narrative review, PP preprint, RT registered
  trial -- the code names the KIND of study, not its quality), title,
  authors, year, journal, `legacy_tier` (the letter stored until September 2026, kept
  only for backward compatibility; it does NOT match the displayed codes:
  B = H, C = A, D = M or R, A = S -- use `evidence_code`), `pyramid`.
  Then study category and model system, DOI/PMID/PMCID, the
  curated one-line finding, the PubMed abstract, and (where extracted)
  AI-assisted deep-extraction fields: intervention, target, species,
  effect, dose, sample size, effect size, and limitations. `atlas_url`
  links back to the full record page.
- **relations.csv / relations.json** -- {len(rel_rows)} signed pathway
  links (source, effect, target) with mechanism, boundary conditions,
  supporting and conflicting study IDs (`sid`, semicolon-separated),
  `source_id` / `target_id` (the entity `id` from entities.csv),
  evidence grades, `curation_status` and `review_status`. A
  `review_status` of `unreviewed` means no named curator has signed the
  link off yet.
- **entities.csv / entities.json** -- {len(entity_rows)} pathway
  entities (genes/proteins, complexes, drugs, interventions, biological
  processes, diseases, outcomes, organelles, nutrients/metabolites,
  conditions) referenced across the corpus, with a technical and a
  plain-language description, synonyms, how many studies link to each,
  a stable `id` (the same identifier the Atlas API uses), `has_page`
  and `atlas_url`. An entity has its own page when at least
  {PAGE_THRESHOLD} studies link to it or when it is a node of the
  pathway map; the other entities are catalogue entries only, with
  `has_page` false and an empty `atlas_url`.

## Data dictionary (studies)

| Column | Meaning |
|---|---|
| `sid` | Atlas study ID, stable key (joins to `supporting_studies` / `conflicting_studies` in relations) |
| `evidence_code`, `evidence_label` | Displayed study type (S, H, A, M, R, PP, RT); design, not quality |
| `legacy_tier` | Letter stored until September 2026 (plus Preprint, Registered trial); superseded by `evidence_code` |
| `pyramid` | Finer study-design label; splits narrative reviews out of M |
| `category`, `model` | Curated topic and model system |
| `peer_reviewed` | Peer-review flag of the source record |
| `finding` | Curated one-line finding |
| `abstract` | PubMed abstract |
| `ai_*` | AI-assisted extraction fields (may be empty; not independently verified) |
| `atlas_url` | Record page on the Atlas |

`snapshot.json` (next to the data files) records the dataset version, the
export date, record counts, the evidence-code distribution and the sha256 of
every file, so a result computed from these files can be tied to one snapshot.

## License & citation

CC BY 4.0 -- free to use, share and adapt, including commercially, with
attribution. Cite as:

Barton, O. ({datetime.date.today().year}). *Oliver's mTOR Atlas* [Data set]. Zenodo.
https://doi.org/10.5281/zenodo.22059963

Full details: {SITE}/data/ and {SITE}/CITATION.cff.

## Caveats

- The code is a study-DESIGN classification, not a quality grade
  (a well-run animal study, A, is not "worse" than a poorly-run human
  one, H, on every axis -- the code just says what kind of evidence it
  is). This is why the displayed codes stopped being the letters A-D in
  September 2026: a lettered ladder reads as a school grade however it
  is captioned.
- "Record last updated" dates on individual study pages (not included
  in this export) are approximate for older records -- see
  {SITE}/study/ pages for the caveat, or the site's changelog files.
- This is a living dataset; corpus size and content change as new
  studies are curated. The formally versioned, permanently citable
  snapshot is the Zenodo archive (DOI above), not this export.
"""
    write_verified_text(os.path.join(OUT, "README.md"), readme)

    # Kontrola: rozdeleni evidencnich kodu v exportu = nezavisly vypocet nad
    # studies_baked.json (stejny zdroj, jako pocita web a API). Jinak build padne.
    from collections import Counter
    tb = _tier_bits()
    dist_src = Counter(tb(s.get("tier"), s.get("pyramid"))[0] for s in studies)
    dist_exp = Counter(r["evidence_code"] for r in study_rows)
    assert dist_src == dist_exp and sum(dist_exp.values()) == len(studies), \
        f"evidence distribution mismatch: {dist_src} vs {dist_exp}"
    assert all(r["evidence_code"] in ("S", "H", "A", "M", "R", "PP", "RT")
               for r in study_rows), "unknown evidence_code in studies export"

    manifest = []
    for fn, fmt in [("studies.csv", "text/csv"), ("studies.json", "application/json"),
                    ("entities.csv", "text/csv"), ("entities.json", "application/json"),
                    ("relations.csv", "text/csv"), ("relations.json", "application/json")]:
        p = os.path.join(OUT, fn)
        manifest.append({
            "name": fn,
            "encodingFormat": fmt,
            "contentUrl": f"{SITE}/data/exports/{fn}",
            "contentSize": os.path.getsize(p),
            "sha256": sha256_of(p),
        })
    write_verified_text(os.path.join(OUT, "manifest.json"),
                         json.dumps(manifest, indent=2) + "\n")

    # 17. 10. 2026 (externi audit, BLOCKING): dataset_version uz neni holy
    # `version:` z CITATION.cff. Ten jmenuje posledni archivovanou release,
    # ale tyhle exporty jsou zive data. release_status.py rozhodne podle
    # otisku obsahu: "2.0.1" jen pri shode s archivem, jinak "2.0.1+unreleased".
    sys.path.insert(0, HERE)
    import release_status
    rs = release_status.load_status()
    snapshot = {
        "dataset_version": rs["dataset_version"],
        "live_matches_release": rs["live_matches_release"],
        "latest_release": rs["latest_release"],
        "data_fingerprint": rs["live"]["data_fingerprint"],
        "generated": datetime.date.today().isoformat(),
        "doi_concept": "10.5281/zenodo.22059963",
        "counts": {"studies": len(study_rows), "entities": len(entity_rows),
                   "relations": len(rel_rows)},
        "studies_by_evidence_code": {k: dist_exp[k] for k in
                                     ("S", "H", "A", "M", "R", "PP", "RT")},
        "files": {m["name"]: {"bytes": m["contentSize"], "sha256": m["sha256"]}
                  for m in manifest},
        "note": "Source commit is reported by the Atlas API meta (source_commit); "
                "it is not known when this file is generated.",
    }
    write_verified_text(os.path.join(OUT, "snapshot.json"),
                        json.dumps(snapshot, indent=2) + "\n")

    print(f"Wrote {len(study_rows)} studies + {len(entity_rows)} entities + {len(rel_rows)} relations to {OUT}")
    for m in manifest:
        print(f"  {m['name']:16s} {m['contentSize']:>8d} bytes  {m['sha256'][:12]}...")


if __name__ == "__main__":
    main()
