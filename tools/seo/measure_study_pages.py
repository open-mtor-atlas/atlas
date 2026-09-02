#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
tools/seo/measure_study_pages.py -- Ukol 1 (SEO P0 brief 2026-09-02).

Zmeri, jak "tenke" jsou vygenerovane study/<SID>/index.html stranky: kolik
znaku textu je celkem, kolik z toho je doslovny PubMed abstrakt, a kolik je
skutecny kuratorsky/unikatni obsah Atlasu (finding + Extracted findings +
entity tagy). Cilem neni menit stranky, jen zmerit soucasny stav PRED Ukolem 2
(a znovu PO nem, aby slo porovnat medianu ratio_unique).

Vstup:  study/*/index.html  (354 souboru, generovane build_pages.py)
Vystup: atlas_data/seo_study_audit.csv

Pouziti:
    python3 tools/seo/measure_study_pages.py
    python3 tools/seo/measure_study_pages.py --out atlas_data/seo_study_audit_after.csv
"""
import argparse, csv, glob, html, os, re, sys

HERE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

TAG_RE = re.compile(r"<[^>]+>")
SCRIPT_RE = re.compile(r"<script\b[^>]*>.*?</script>", re.S | re.I)
STYLE_RE = re.compile(r"<style\b[^>]*>.*?</style>", re.S | re.I)
WS_RE = re.compile(r"\s+")


def visible_text_len(fragment_html):
    """Odstrani script/style/tagy, unescapuje entity, sesbite whitespace,
    vrati delku vysledneho textu ve znacich."""
    if not fragment_html:
        return 0, ""
    t = SCRIPT_RE.sub(" ", fragment_html)
    t = STYLE_RE.sub(" ", t)
    t = TAG_RE.sub(" ", t)
    t = html.unescape(t)
    t = WS_RE.sub(" ", t).strip()
    return len(t), t


# Both extractors below stop at <footer -- BUG FOUND 2026-09-02: the original
# boundary was only "next h2/h3, or </div> right before </body>". A section
# that happens to be the LAST heading on the page (no following h2/h3, which
# is most study pages before Ukol 2 -- most have no "Learn the biology" cross-
# link) has nothing between it and the closing </div></body> EXCEPT the CTA
# paragraph and the entire <footer> (7 nav links + attribution text). Without
# a <footer> stop, extract_section silently swallowed all of that into
# whatever section happened to be last, inflating its char/link count. This
# is why the very first "before" run of this script (Ukol 1 commit) showed
# n_entity_links as high as 9 on pages whose actual <div class="tags"> has a
# single link -- 1 real entity tag + 1 CTA link + 7 footer links = 9. Fixed
# here retroactively; both audits in this comparison use the fixed version.
def extract_section(body, label):
    """Vrati HTML mezi <h2|h3>label</h2|h3> a dalsim <h2>, <h3> nebo
    <footer> (nebo koncem body). Zamerne h2 NEBO h3 (oprava po Ukolu 2):
    sekce "Related topics" byla pred Ukolem 2 <h2>, po nem je <h3> vnorene
    pod <h2>In the Atlas</h2> -- flexibilni match drzi pred/po srovnani
    korektni."""
    pat = re.compile(
        r"<h[23][^>]*>\s*" + re.escape(label) + r"\s*</h[23]>(.*?)"
        r"(?=<h[23]\b|<footer\b|<a class=\"cta\"|</div>\s*</body|\Z)",
        re.S | re.I)
    m = pat.search(body)
    return m.group(1) if m else ""


def extract_h2_section(body, label):
    """Vrati HTML mezi <h2>label</h2> a DALSIM <h2> nebo <footer> (h3 uvnitr
    NEjsou hranice -- na rozdil od extract_section vyse). Pouzito jen pro
    "In the Atlas", ktera po Ukolu 2 obaluje vnorene <h3> podsekce (Related
    topics/Open questions/Answers/Learn the biology)."""
    pat = re.compile(
        r"<h2[^>]*>\s*" + re.escape(label) + r"\s*</h2>(.*?)"
        r"(?=<h2\b|<footer\b|<a class=\"cta\"|</div>\s*</body|\Z)",
        re.S | re.I)
    m = pat.search(body)
    return m.group(1) if m else ""


def measure_one(path):
    html_src = open(path, encoding="utf-8").read()
    m = re.search(r"<body>(.*)</body>", html_src, re.S)
    body = m.group(1) if m else html_src

    total_chars, _ = visible_text_len(body)

    # tier -- z <span class="tier" style="...">X</span> radku "At a glance"
    tier_m = re.search(r'class="tier"[^>]*>([A-D—])<', body)
    tier = tier_m.group(1) if tier_m else "?"

    # summary/finding (prvni odstavec pod H1)
    summary_html = ""
    sm = re.search(r'<p class="summary">(.*?)</p>', body, re.S)
    if sm:
        summary_html = sm.group(1)

    # Extracted findings tabulka (pokud existuje)
    extracted_html = extract_section(body, "Extracted findings")
    has_extracted = 1 if extracted_html.strip() else 0

    # Abstract
    abstract_html = ""
    am = re.search(r'<p class="abstract">(.*?)</p>', body, re.S)
    if am:
        abstract_html = am.group(1)
    chars_abstract, _ = visible_text_len(abstract_html)

    # Entity tags ("Related topics") -- unchanged definition pre/post Ukol 2
    # so ratio_unique / n_entity_links stay apples-to-apples across the two
    # audits (see extract_section's h2-or-h3 fix above).
    tags_html = extract_section(body, "Related topics")
    n_entity_links = len(re.findall(r"<a\b", tags_html))
    tags_text_len, _ = visible_text_len(tags_html)

    # tier-why line (new in Ukol 2; absent pre-rebuild -> 0 for the "before" run)
    tw_m = re.search(r'<p class="tier-why">(.*?)</p>', body, re.S)
    tier_why_len, _ = visible_text_len(tw_m.group(1)) if tw_m else (0, "")

    # Whole "In the Atlas" block (new in Ukol 2: entities + open-question +
    # answers + academy cross-links together) -- reported separately so the
    # core 3 columns above stay comparable, and this shows the fuller picture.
    atlas_html = extract_h2_section(body, "In the Atlas")
    n_atlas_links = len(re.findall(r"<a\b", atlas_html))
    atlas_text_len, _ = visible_text_len(atlas_html)

    # Academy cross-link presence
    has_academy_link = 1 if "Learn the biology" in body else 0

    summary_len, _ = visible_text_len(summary_html)
    extracted_len, _ = visible_text_len(extracted_html)

    chars_unique = summary_len + extracted_len + tags_text_len
    ratio_unique = round(chars_unique / total_chars, 4) if total_chars else 0.0

    sid = os.path.basename(os.path.dirname(path))
    return {
        "sid": sid,
        "tier": tier,
        "chars_total": total_chars,
        "chars_abstract": chars_abstract,
        "chars_unique": chars_unique,
        "ratio_unique": ratio_unique,
        "n_entity_links": n_entity_links,
        "has_extracted": has_extracted,
        "has_academy_link": has_academy_link,
        "chars_tier_why": tier_why_len,
        "chars_atlas_block": atlas_text_len,
        "n_atlas_links": n_atlas_links,
    }


def band(chars_unique):
    if chars_unique < 200:
        return "<200"
    if chars_unique < 400:
        return "200-400"
    if chars_unique < 800:
        return "400-800"
    return ">800"


def write_verified(path, rows, fieldnames):
    """Bezpecny zapis CSV na mounted slozku -- viz projektova pamet
    index-html-large-file-writes: nikdy neverit jednomu zapisu bez overeni."""
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for r in rows:
            w.writerow(r)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)
    # nezavisle overeni
    with open(path, encoding="utf-8-sig") as f:
        check = list(csv.DictReader(f))
    assert len(check) == len(rows), f"CSV verify failed: {len(check)} != {len(rows)}"
    return len(check)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join(HERE, "atlas_data", "seo_study_audit.csv"))
    ap.add_argument("--glob", default=os.path.join(HERE, "study", "*", "index.html"))
    args = ap.parse_args()

    paths = sorted(glob.glob(args.glob))
    if not paths:
        sys.exit("Nenalezena zadna study/*/index.html -- spatna cesta nebo build_pages.py jeste nebezel.")

    rows = [measure_one(p) for p in paths]
    fieldnames = ["sid", "tier", "chars_total", "chars_abstract", "chars_unique",
                  "ratio_unique", "n_entity_links", "has_extracted", "has_academy_link",
                  "chars_tier_why", "chars_atlas_block", "n_atlas_links"]
    n = write_verified(args.out, rows, fieldnames)

    ratios = sorted(r["ratio_unique"] for r in rows)
    median = ratios[len(ratios) // 2] if len(ratios) % 2 else (
        (ratios[len(ratios) // 2 - 1] + ratios[len(ratios) // 2]) / 2)
    thin = sum(1 for r in rows if r["chars_unique"] < 400)
    zero_links = sum(1 for r in rows if r["n_entity_links"] == 0)
    bands = {}
    for r in rows:
        b = band(r["chars_unique"])
        bands[b] = bands.get(b, 0) + 1

    zero_atlas = sum(1 for r in rows if r["n_atlas_links"] == 0)
    print(f"Zapsáno {n} řádků do {args.out}")
    print(f"Medián ratio_unique: {median:.3f}")
    print(f"Stránek s chars_unique < 400: {thin} / {len(rows)}")
    print(f"Stránek s 0 odkazy na entity (Related topics): {zero_links} / {len(rows)}")
    print(f"Stránek s 0 odkazy v celé sekci In the Atlas: {zero_atlas} / {len(rows)}")
    print("Pásma unikátního obsahu:")
    for b in ["<200", "200-400", "400-800", ">800"]:
        print(f"  {b:>8} znaků: {bands.get(b, 0)}")


if __name__ == "__main__":
    main()
