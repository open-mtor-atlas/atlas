#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
tools/seo/build_tess_dump.py -- Ukol 6.2 (SEO P0 brief 2026-09-02).

Generates outreach/tess/atlas-academy.json: one entry per published mTOR
Academy lesson + the course itself, in a Bioschemas-TrainingMaterial-
shaped JSON that mirrors the JSON-LD already emitted on each lesson page
(see build_academy.py's lesson_page(), patched 2026-09-02) -- built from
academy_data/lessons.json + modules.json directly, not retyped by hand,
so it can never silently drift from what the live pages actually say.

NEVEROVERENO: this session has no network egress to elixir-europe.org /
tess.elixir-europe.org, so the exact field names TeSS's own submission
API or web form expects could not be checked against their live
documentation. The field names below follow the Bioschemas
TrainingMaterial profile, which TeSS is publicly known to be built on --
but Petr/Oliver should sanity-check field names against
https://tess.elixir-europe.org/ (or its API docs) before using this file,
and treat this as a strong starting draft, not a guaranteed-correct
submission payload.

Usage:
    python3 tools/seo/build_tess_dump.py
"""
import json
import os

HERE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SITE = "https://mtor-atlas.org"
ORCID = "https://orcid.org/0009-0008-2025-2148"


def main():
    lessons = json.load(open(os.path.join(HERE, "academy_data", "lessons.json"),
                              encoding="utf-8"))["lessons"]
    modules = json.load(open(os.path.join(HERE, "academy_data", "modules.json"),
                              encoding="utf-8"))
    mod = modules["modules"][0]
    by_slug = {l["slug"]: l for l in lessons}
    published = [by_slug[r["lesson"]] for r in mod["lessons"]
                 if r["status"] == "published" and r["lesson"] in by_slug]

    entries = []
    entries.append({
        "_neoverene": "field names follow Bioschemas TrainingMaterial/Course; "
                       "verify against tess.elixir-europe.org before submitting",
        "type": "Course",
        "title": "%s — mTOR Academy" % mod["title"],
        "description": mod["description"],
        "url": "%s/academy/%s/" % (SITE, mod["slug"]),
        "resourceType": ["e-learning"],
        "licence": "CC-BY-4.0",
        "difficultyLevel": "Beginner to intermediate",
        "cost": "Free",
        "targetAudience": ["Students", "Life scientists", "General public with "
                                                          "interest in molecular biology"],
        "authors": ["Oliver Barton"],
        "authorOrcids": [ORCID],
        "keywords": ["mTOR", "mTORC1", "mTORC2", "signal transduction", "aging biology"],
        "language": "en",
        "isAccessibleForFree": True,
    })
    for l in published:
        entries.append({
            "type": "Material",
            "title": l["title"],
            "description": l.get("subtitle") or l.get("coreIdea") or l["title"],
            "url": "%s/academy/%s/%s/" % (SITE, mod["slug"], l["slug"]),
            "resourceType": ["e-learning"],
            "licence": "CC-BY-4.0",
            "difficultyLevel": l["level"],
            "cost": "Free",
            "targetAudience": ["Students", "Life scientists", "General public with "
                                                              "interest in molecular biology"],
            "authors": ["Oliver Barton"],
            "authorOrcids": [ORCID],
            "keywords": l.get("concepts") or [],
            "timeEstimate": "PT%dM" % l["estimatedTime"],
            "language": "en",
            "isAccessibleForFree": True,
            "isPartOf": "%s/academy/%s/" % (SITE, mod["slug"]),
        })

    out_dir = os.path.join(HERE, "outreach", "tess")
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, "atlas-academy.json")
    tmp = out_path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(entries, f, indent=2, ensure_ascii=False)
        f.write("\n")
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, out_path)
    check = json.load(open(out_path, encoding="utf-8"))
    assert len(check) == len(entries)
    print(f"Wrote {len(entries)} entries (1 course + {len(entries)-1} lessons) to {out_path}")


if __name__ == "__main__":
    main()
