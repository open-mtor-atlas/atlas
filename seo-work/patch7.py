#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""patch7.py -- Ukol 6.1 (SEO P0 brief 2026-09-02): Bioschemas TrainingMaterial
profile on every Academy lesson + Research Challenge page. Course/
CourseInstance markup already existed (curriculum_page(), pre-dates this
session) and already satisfies the brief's "hasCourseInstance with
courseMode" requirement for a Google Course rich result -- nothing to add
there. This patch only touches the per-lesson/per-challenge LearningResource
blocks: adds the TrainingMaterial type, a Bioschemas-recognized
learningResourceType value, keywords, an audience, and the curator's ORCID
on the author field (previously name-only)."""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else "build_academy.py"
    with open(path, encoding="utf-8") as f:
        src = f.read()

    MARKER = "# --- SEO P0 Ukol 6.1 (2026-09-02): Bioschemas TrainingMaterial"
    if MARKER in src:
        sys.exit("Already patched (marker found) -- aborting.")

    orig_len = len(src)
    ORCID = "https://orcid.org/0009-0008-2025-2148"
    AUTHOR = ('{"@type": "Person", "name": "Oliver Barton", '
              f'"url": "{ORCID}", "sameAs": ["{ORCID}"]}}')

    # --- lesson_page() ld block ---
    old_lesson = (
        '    ld = {\n'
        '        "@context": "https://schema.org", "@type": "LearningResource",\n'
        '        "name": title, "headline": title, "url": url, "inLanguage": "en",\n'
        '        "educationalLevel": les["level"],\n'
        '        "learningResourceType": "lesson",\n'
        '        "timeRequired": "PT%dM" % les["estimatedTime"],\n'
        '        "teaches": les.get("concepts") or [],\n'
        '        "isPartOf": {"@type": "Course", "name": "%s — mTOR Academy" % module["title"],\n'
        '                     "url": "%s/academy/%s/" % (SITE, module["slug"])},\n'
        '        "about": dict(DATASET_REF),\n'
        '        "author": {"@type": "Person", "name": "Oliver Barton"},\n'
        '        "license": "https://creativecommons.org/licenses/by/4.0/",\n'
        '    }\n'
    )
    assert src.count(old_lesson) == 1, "lesson_page ld anchor not found/unique"
    new_lesson = (
        f'    {MARKER} ---\n'
        '    ld = {\n'
        '        "@context": "https://schema.org",\n'
        '        "@type": ["LearningResource", "TrainingMaterial"],\n'
        '        "name": title, "headline": title, "url": url, "inLanguage": "en",\n'
        '        "educationalLevel": les["level"],\n'
        '        "learningResourceType": "e-learning",\n'
        '        "timeRequired": "PT%dM" % les["estimatedTime"],\n'
        '        "teaches": les.get("concepts") or [],\n'
        '        "keywords": les.get("concepts") or [],\n'
        '        "audience": {"@type": "Audience",\n'
        '                     "audienceType": "students and self-directed learners with a "\n'
        '                                     "basic biology background"},\n'
        '        "isPartOf": {"@type": "Course", "name": "%s — mTOR Academy" % module["title"],\n'
        '                     "url": "%s/academy/%s/" % (SITE, module["slug"])},\n'
        '        "about": dict(DATASET_REF),\n'
        f'        "author": {AUTHOR},\n'
        '        "license": "https://creativecommons.org/licenses/by/4.0/",\n'
        '    }\n'
    )
    src = src.replace(old_lesson, new_lesson, 1)

    # --- Research Challenge page ld block ---
    old_challenge = (
        '    ld = {"@context": "https://schema.org", "@type": "LearningResource",\n'
        '          "name": ch["title"], "headline": ch["title"], "url": url, "inLanguage": "en",\n'
        '          "educationalLevel": ch["level"], "learningResourceType": "activity",\n'
        '          "timeRequired": "PT%dM" % ch["estimatedTime"],\n'
        '          "teaches": ch["researchSkills"],\n'
        '          "isPartOf": {"@type": "Course", "name": "Research Challenges — mTOR Academy",\n'
        '                       "url": "%s/academy/research-challenges/" % SITE},\n'
        '          "about": dict(DATASET_REF),\n'
        '          "author": {"@type": "Person", "name": "Oliver Barton"},\n'
        '          "license": "https://creativecommons.org/licenses/by/4.0/"}\n'
    )
    assert src.count(old_challenge) == 1, "challenge ld anchor not found/unique"
    new_challenge = (
        f'    {MARKER} (challenge pages) ---\n'
        '    ld = {"@context": "https://schema.org",\n'
        '          "@type": ["LearningResource", "TrainingMaterial"],\n'
        '          "name": ch["title"], "headline": ch["title"], "url": url, "inLanguage": "en",\n'
        '          "educationalLevel": ch["level"], "learningResourceType": "e-learning",\n'
        '          "timeRequired": "PT%dM" % ch["estimatedTime"],\n'
        '          "teaches": ch["researchSkills"],\n'
        '          "keywords": ch["researchSkills"],\n'
        '          "audience": {"@type": "Audience",\n'
        '                       "audienceType": "students and self-directed learners with a "\n'
        '                                       "basic biology background"},\n'
        '          "isPartOf": {"@type": "Course", "name": "Research Challenges — mTOR Academy",\n'
        '                       "url": "%s/academy/research-challenges/" % SITE},\n'
        '          "about": dict(DATASET_REF),\n'
        f'          "author": {AUTHOR},\n'
        '          "license": "https://creativecommons.org/licenses/by/4.0/"}\n'
    )
    src = src.replace(old_challenge, new_challenge, 1)

    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(src)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)

    check = open(path, encoding="utf-8").read()
    assert len(check) == len(src), "post-write length mismatch: %d != %d" % (len(check), len(src))
    print(f"Patched {path}: {orig_len} -> {len(src)} bytes.")


if __name__ == "__main__":
    main()
