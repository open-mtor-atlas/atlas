#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
tools/seo/build_linkout.py -- Ukol 7 (SEO P0 brief 2026-09-02).

Builds the NCBI LinkOut submission package (UNSENT -- prepared only, per
the brief's hard rule: no accounts, no emails, no FTP from this session).

Outputs (all under outreach/linkout/):
- providerinfo.xml  -- one <Provider> block (LinkOut requires exactly one
  per resource; ProviderId is an NCBI-assigned placeholder until they
  approve the application).
- resources.csv      -- one row per study that has a PMID (from
  atlas_data/studies_baked.json's own "pmid" field, not the DOI->PMID
  map, which only covers a 267-entry subset used elsewhere). Format:
  PrId,DB,UID,url,IconUrl,UrlName,SubjectType,Attribute (columns fixed
  by NCBI's documented resource-file spec, recalled from memory since
  this VM has no network egress to https://www.ncbi.nlm.nih.gov/books/NBK3812/
  to check live -- flagged NEVEROVERENO below where a value could not be
  cross-checked against an enum NCBI publishes).
- application-email.md -- text for linkout@ncbi.nlm.nih.gov. UNSENT.
- icon-16x16.png, icon-100x20.png -- generated from the site's live
  favicon.png (the actual production mark, not an unshipped concept
  from brand/logo-concepts/).

NEVEROVERENO: NCBI's exact current list of allowed SubjectType and
Attribute enum values could not be checked against live docs (no network
egress). "SubjectType" is set to "Data resource" (an LinkOut-documented,
long-stable value for database/resource providers, from memory) and
"Attribute" is left blank (optional field; NCBI's docs list attributes
like "nonPubmedArticleTitle" that don't apply here). Petr/Oliver should
verify both against https://www.ncbi.nlm.nih.gov/books/NBK3812/ before
submitting -- if either has changed, only resources.csv needs a re-run
of this script after editing the two constants below.
"""
import csv
import json
import os

HERE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
OUT_DIR = os.path.join(HERE, "outreach", "linkout")
SITE = "https://mtor-atlas.org"

# NEVEROVERENO -- see module docstring.
SUBJECT_TYPE = "Data resource"
ATTRIBUTE = ""


def write_verified(path, content_bytes, mode="wb"):
    tmp = path + ".tmp"
    with open(tmp, mode) as f:
        f.write(content_bytes)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)
    with open(path, "rb") as f:
        check = f.read()
    if mode == "wb":
        assert check == content_bytes, "write verify failed for %s" % path
    return len(check)


def build_provider_info():
    xml = """<?xml version="1.0"?>
<!DOCTYPE Provider PUBLIC "-//NLM//DTD LinkOut 1.0//EN"
  "https://www.ncbi.nlm.nih.gov/projects/linkout/doc/LinkOut.dtd">
<!--
  outreach/linkout/providerinfo.xml -- UNSENT DRAFT (SEO P0 Ukol 7)
  ProviderId below is a placeholder ("00000") -- NCBI assigns the real
  ProviderId only after reviewing and approving the application emailed
  to linkout@ncbi.nlm.nih.gov (see application-email.md in this same
  folder). Do not submit resources.csv referencing "00000" as a final
  ProviderId; NCBI will supply the real one in their approval reply,
  and it must be substituted into both this file and resources.csv's
  PrId column before the resource file is uploaded via FTP.
-->
<Provider>
  <ProviderId>00000</ProviderId>
  <Name>Oliver's mTOR Atlas</Name>
  <NameAbbr>mTORAtlas</NameAbbr>
  <SubjectType>%s</SubjectType>
  <Url>%s/</Url>
  <Brief>Evidence-graded, open-access database of curated primary studies
on mTOR (mechanistic target of rapamycin) signaling. Each record links
the primary study to its evidence tier (A = systematic review/meta-
analysis through D = mechanistic/in-vitro), extracted findings, and the
pathway entities it involves. Free, no login, CC BY 4.0.</Brief>
</Provider>
""" % (SUBJECT_TYPE, SITE)
    path = os.path.join(OUT_DIR, "providerinfo.xml")
    n = write_verified(path, xml.encode("utf-8"))
    print("Wrote %s (%d bytes)" % (path, n))


def build_resources_csv():
    studies = json.load(open(os.path.join(HERE, "atlas_data", "studies_baked.json"),
                              encoding="utf-8"))
    with_pmid = [s for s in studies if s.get("pmid")]
    rows = []
    for s in with_pmid:
        sid = s["sid"]
        pmid = s["pmid"]
        rows.append({
            "PrId": "00000",
            "DB": "PubMed",
            "UID": pmid,
            "url": "%s/study/%s/" % (SITE, sid),
            "IconUrl": "%s/outreach-assets/linkout-icon-16x16.png" % SITE,
            "UrlName": "Evidence-graded record in Oliver's mTOR Atlas",
            "SubjectType": SUBJECT_TYPE,
            "Attribute": ATTRIBUTE,
        })
    assert len(rows) >= 300, "expected >=300 rows, got %d" % len(rows)

    path = os.path.join(OUT_DIR, "resources.csv")
    tmp = path + ".tmp"
    fieldnames = ["PrId", "DB", "UID", "url", "IconUrl", "UrlName", "SubjectType", "Attribute"]
    with open(tmp, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(rows)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)
    with open(path, encoding="utf-8", newline="") as f:
        check = list(csv.DictReader(f))
    assert len(check) == len(rows), "post-write row count mismatch: %d != %d" % (len(check), len(rows))
    print("Wrote %s (%d data rows, %d studies had no PMID and were skipped)"
          % (path, len(rows), len(studies) - len(with_pmid)))
    return rows


def build_application_email(sample_rows):
    sample = sample_rows[:5]
    sample_lines = "\n".join(
        "  - PMID %s -> %s" % (r["UID"], r["url"]) for r in sample
    )
    text = """<!--
outreach/linkout/application-email.md -- UNSENT DRAFT (SEO P0 Ukol 7)
To: linkout@ncbi.nlm.nih.gov
Do not send from this session -- Petr/Oliver sends manually.
-->

Subject: LinkOut provider application -- Oliver's mTOR Atlas

To the NCBI LinkOut team,

I would like to apply to become a LinkOut provider for Oliver's mTOR
Atlas (%s), a free, non-commercial, evidence-graded database of curated
primary research studies on mTOR (mechanistic target of rapamycin)
signaling.

About the resource:
- Non-commercial, no login required, no advertising.
- Content license: CC BY 4.0.
- Each record links a PubMed-indexed primary study to an evidence tier
  (A = systematic review/meta-analysis through D = mechanistic/in-vitro
  study), extracted findings, and the pathway entities/processes it
  involves -- adding structured, freely reusable context on top of the
  PubMed record, not duplicating it.
- Registered with FAIRsharing (FAIRsharing ID: 8905) and bio.tools
  (ID: olivers_mtor_atlas).
- Dataset DOI: 10.5281/zenodo.22059963.

We would like to link out from PubMed records to the corresponding
record on our site wherever we hold a PMID match. Five example
PMID -> URL pairs (of %d currently mapped; full list in the attached
resources.csv):
%s

Attached:
- providerinfo.xml
- resources.csv (%d rows)
- icon-16x16.png / icon-100x20.png

Please let us know if any field needs adjustment, and the ProviderId to
use once approved.

Contact: Oliver Barton (ORCID 0009-0008-2025-2148)
""" % (SITE, len(sample_rows), sample_lines, len(sample_rows))
    path = os.path.join(OUT_DIR, "application-email.md")
    n = write_verified(path, text.encode("utf-8"))
    print("Wrote %s (%d bytes)" % (path, n))


def build_icons():
    from PIL import Image, ImageDraw, ImageFont

    src_path = os.path.join(HERE, "favicon.png")
    src = Image.open(src_path).convert("RGBA")

    icon16 = src.resize((16, 16), Image.LANCZOS)
    path16 = os.path.join(OUT_DIR, "icon-16x16.png")
    icon16.save(path16, "PNG")
    im_check = Image.open(path16)
    assert im_check.size == (16, 16)
    print("Wrote %s (16x16)" % path16)

    canvas = Image.new("RGBA", (100, 20), (255, 255, 255, 0))
    mark = src.resize((20, 20), Image.LANCZOS)
    canvas.paste(mark, (0, 0), mark)
    draw = ImageDraw.Draw(canvas)
    font_path = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
    font = ImageFont.truetype(font_path, 9)
    draw.text((23, 5), "mTOR Atlas", font=font, fill=(30, 30, 30, 255))
    path100 = os.path.join(OUT_DIR, "icon-100x20.png")
    canvas.save(path100, "PNG")
    im_check2 = Image.open(path100)
    assert im_check2.size == (100, 20)
    print("Wrote %s (100x20)" % path100)


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    build_provider_info()
    rows = build_resources_csv()
    build_application_email(rows)
    build_icons()
    print("Done. Ukol 7 hotovo, kdyz: 3 soubory + ikona existuji (OK), "
          "CSV >= 300 radku (OK, %d)." % len(rows))


if __name__ == "__main__":
    main()
