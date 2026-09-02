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
    ("year", "year"), ("journal", "journal"), ("tier", "tier"),
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
    # newline="" on both sides: csv.writer emits \r\n line terminators, and
    # verifying with universal-newline read (default) would silently strip
    # the \r on every line and produce a false length mismatch.
    check = open(path, encoding="utf-8", newline="").read()
    assert len(check) == len(text), f"write verify failed for {path}: {len(check)} != {len(text)}"


def sha256_of(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def build_studies_export(studies):
    rows = []
    for s in studies:
        row = {out_key: (s.get(in_key) or "") for out_key, in_key in STUDY_FIELDS}
        row["atlas_url"] = f"{SITE}/study/{s['sid']}/"
        rows.append(row)
    fieldnames = [k for k, _ in STUDY_FIELDS] + ["atlas_url"]
    return rows, fieldnames


def build_entities_export(entities):
    rows = []
    for x in entities:
        n = len(x.get("studies") or [])
        d = TYPE_DIR.get(x["type"], "entity")
        slug = slugify(x["name"])
        has_page = n >= PAGE_THRESHOLD
        row = {
            "name": x.get("name") or "",
            "type": x.get("type") or "",
            "description": x.get("desc") or "",
            "description_beginner": x.get("desc_beginner") or "",
            "synonyms": x.get("synonyms") or "",
            "n_linked_studies": n,
            "atlas_url": f"{SITE}/{d}/{slug}/" if has_page else "",
        }
        rows.append(row)
    fieldnames = ["name", "type", "description", "description_beginner",
                  "synonyms", "n_linked_studies", "atlas_url"]
    return rows, fieldnames


def write_csv(path, rows, fieldnames):
    lines = []
    import io
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=fieldnames)
    w.writeheader()
    for r in rows:
        w.writerow(r)
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

    readme = f"""# Oliver's mTOR Atlas -- data exports

Machine-readable exports of the curated corpus behind
[Oliver's mTOR Atlas]({SITE}/), generated from the same source data as
the live site. Regenerated on every deploy by
`tools/seo/build_data_exports.py` -- if you're reading this from a
downloaded copy, check {SITE}/data/ for the current version.

## Files

- **studies.csv / studies.json** -- {len(study_rows)} hand-curated
  primary studies on the mTOR signaling pathway. Each row: Atlas ID
  (`sid`), title, authors, year, journal, evidence tier (A = systematic
  review/meta-analysis, B = human trial, C = animal model, D =
  mechanistic/in-vitro/review -- tier describes study design, not
  quality), study category and model system, DOI/PMID/PMCID, the
  curated one-line finding, the PubMed abstract, and (where extracted)
  AI-assisted deep-extraction fields: intervention, target, species,
  effect, dose, sample size, effect size, and limitations. `atlas_url`
  links back to the full record page.
- **entities.csv / entities.json** -- {len(entity_rows)} pathway
  entities (genes/proteins, complexes, drugs, interventions, biological
  processes, diseases, outcomes, organelles, nutrients/metabolites,
  conditions) referenced across the corpus, with a technical and a
  plain-language description, synonyms, how many studies link to each,
  and `atlas_url` when the entity has its own page (entities linked
  from fewer than {PAGE_THRESHOLD} studies don't get a standalone page
  on the live site and so have no `atlas_url` here).

## License & citation

CC BY 4.0 -- free to use, share and adapt, including commercially, with
attribution. Cite as:

Barton, O. ({{year}}). *Oliver's mTOR Atlas* [Data set]. Zenodo.
https://doi.org/10.5281/zenodo.22059963

Full details: {SITE}/data/ and {SITE}/CITATION.cff.

## Caveats

- Evidence tier is a study-DESIGN classification, not a quality grade
  (a well-run tier-C animal study is not "worse" than a poorly-run
  tier-B human one on every axis -- tier just says what kind of
  evidence it is).
- "Record last updated" dates on individual study pages (not included
  in this export) are approximate for older records -- see
  {SITE}/study/ pages for the caveat, or the site's changelog files.
- This is a living dataset; corpus size and content change as new
  studies are curated. The formally versioned, permanently citable
  snapshot is the Zenodo archive (DOI above), not this export.
"""
    write_verified_text(os.path.join(OUT, "README.md"), readme)

    manifest = []
    for fn, fmt in [("studies.csv", "text/csv"), ("studies.json", "application/json"),
                    ("entities.csv", "text/csv"), ("entities.json", "application/json")]:
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

    print(f"Wrote {len(study_rows)} studies + {len(entity_rows)} entities to {OUT}")
    for m in manifest:
        print(f"  {m['name']:16s} {m['contentSize']:>8d} bytes  {m['sha256'][:12]}...")


if __name__ == "__main__":
    main()
