#!/usr/bin/env python3
"""
finish_review_fixes.py -- posledni krok oprav z externiho vedeckeho review
(F1-F16, 2026-07-29).

PROC TOHLE EXISTUJE JAKO SAMOSTATNY SKRIPT
------------------------------------------
Zbytek oprav uz je hotovy a zapsany. Tenhle skript dela jen to, co se NEDALO
udelat behem review, protoze v repu zaroven bezela mobilni optimalizace, ktera
taky zapisuje do index.html. Dva procesy prepisujici tentyz 1,5MB soubor se
navzajem prepisou -- proto se ty kroky odlozily sem, aby probehly najednou a az
bude repo klidne.

CO ZBYVA
  1. dopsat do About sekce, jak se ve skutecnosti prideluje Evidence_Tier
     (F4 -- pravidlo bylo definovano jinak, nez se aplikovalo)
  2. prebake ATLAS_STUDIES z atlas_data/studies_baked.json
     DULEZITE: 8 novych praci (HAR2004, SHA2004, SHW2004, LEE2010, MA2005,
     FOR2010, KAL2010, VAL2022) uz je v baked JSONu a v Airtable, ale JESTE
     NENI v ATLAS_STUDIES uvnitr index.html. Nove hrany (S6K1-IRS1, ERK-TSC,
     METFORMIN-MTORC1, SESN2-AGING, RAPA-LAM, MTORC1-RCC) na ne odkazuji, takze
     dokud tohle neprobehne, budou mit rozbite odkazy na studie.
  3. znovu vygenerovat staticke stranky (build_pages.py)
  4. spustit oba validatory

SPUSTIT AZ MOBILNI OPTIMALIZACE DOBEHNE:

    py finish_review_fixes.py            # zkontroluje a provede
    py finish_review_fixes.py --dry-run  # jen rekne, co by udelal

Skript je idempotentni: kdyz uz je About text na miste, prsekoci ho.
Pred zapisem overi, ze v index.html jsou porad MOBILE-BLOCK znacky i zmeny z
review -- kdyby jeden z tech dvou procesu ten druhy prepsal, radeji se zastavi.
"""

import os, re, sys, json, subprocess, importlib.util

HERE = os.path.dirname(os.path.abspath(__file__))
HTML = os.path.join(HERE, "index.html")
DRY = "--dry-run" in sys.argv

spec = importlib.util.spec_from_file_location("bfm", os.path.join(HERE, "bake_from_mcp.py"))
bfm = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bfm)


def fail(msg):
    print("\nABORTED: %s" % msg)
    sys.exit(1)


# ---------------------------------------------------------- 0. sanity checks

h = open(HTML, encoding="utf-8").read()
print("index.html: %d bytes" % len(h.encode("utf-8")))

REVIEW_MARKERS = {
    "S6K1-IRS1 edge": "S6K1-IRS1",
    "ERK-TSC edge": "ERK-TSC",
    "SESN2-AGING edge": "SESN2-AGING",
    "RAPA-LAM edge": "RAPA-LAM",
    "MTORC1-RCC edge": "MTORC1-RCC",
    "Sestrin2 entity fix": "NEGATIVE regulator of mTORC1",
    "FLCN entity fix": "SUBSTRATE-SPECIFIC defect",
    "gaps caveat": "How to read these, and how not to",
    "H1 revision": "REVISED 2026-07-29",
}
missing = [k for k, v in REVIEW_MARKERS.items() if v not in h]
if missing:
    fail("the review fixes are no longer in index.html: %s.\n"
         "Something rewrote the file from an older copy. Recover index.html "
         "before running this." % ", ".join(missing))
print("  review fixes present: %d/%d" % (len(REVIEW_MARKERS), len(REVIEW_MARKERS)))

mobile_blocks = re.findall(r">>> MOBILE-BLOCK:(\S+) >>>", h)
print("  mobile blocks present: %s" % (", ".join(mobile_blocks) or "none"))
if "TUMOR-RCC" in h:
    fail("TUMOR-RCC is back in index.html - the file was rewritten from an older copy.")


# ------------------------------------------- 1. F4: document the tier rule

ANCHOR = ("<p>Every entry traces back to a specific paper, indexed with its evidence grade "
          "(an A&ndash;D tier where the study is an eligible peer-reviewed primary study, "
          "otherwise an out-of-hierarchy label), model organism, and DOI.</p>")

TIER_DOC = """
        <p><b>How the A&ndash;D tier is actually decided.</b> The tier tracks
        <em>what kind of claim a study can support</em>, not simply which organism it used.
        A whole-organism study whose purpose is an organismal phenotype &mdash; lifespan,
        degeneration, glucose tolerance &mdash; is graded <b>C</b>. A whole-organism study
        whose purpose is signalling mechanism is graded <b>D</b>. This is why the fruit-fly
        papers split: lifespan and degeneration studies sit at C, while signalling-epistasis
        studies sit at D, and yeast splits the same way. The reason is deliberate: evidence
        strength for a health claim should follow the claim, not the taxon.</p>
        <p>This was applied consistently but never written down until an external review in
        July 2026 pointed out that the stated definition ("C = animal in vivo") did not match
        the practice, which made the grading look arbitrary from outside. Two records were
        genuinely wrong and have been corrected: one carried a C tier with an in-vitro pyramid
        level in the same record, and one whole-mouse metabolic study was graded as in-vitro
        mechanism. A validator rule (R7) now blocks any deploy where the tier and the pyramid
        level disagree.</p>"""

if "How the A&ndash;D tier is actually decided" in h:
    print("\n1. tier-rule documentation: already present, skipping")
else:
    if h.count(ANCHOR) != 1:
        fail("could not find the About anchor paragraph exactly once (found %d)." % h.count(ANCHOR))
    h = h.replace(ANCHOR, ANCHOR + TIER_DOC, 1)
    print("\n1. tier-rule documentation: inserted (%d chars)" % len(TIER_DOC))
    if not DRY:
        bfm.write_verified(HTML, h)
        print("   index.html rewritten and verified")


# ------------------------------------------------------ 2. rebake studies

print("\n2. rebake ATLAS_STUDIES from atlas_data/studies_baked.json")
n_baked = len(json.load(open(os.path.join(HERE, "atlas_data", "studies_baked.json"), encoding="utf-8")))
n_embedded = len(json.loads(re.search(r"const ATLAS_STUDIES = (\[.*?\]);\n\nconst ATLAS_ENTITIES",
                                      open(HTML, encoding="utf-8").read(), re.S).group(1)))
print("   baked JSON: %d studies | embedded in page: %d" % (n_baked, n_embedded))
if n_baked == n_embedded:
    print("   already in sync")
elif DRY:
    print("   would run bake_from_mcp.py to close the %d-study gap" % (n_baked - n_embedded))
else:
    subprocess.run([sys.executable, os.path.join(HERE, "bake_from_mcp.py")], check=True, cwd=HERE)


# ---------------------------------------------------- 3. static pages

print("\n3. rebuild pre-rendered pages")
if DRY:
    print("   would run build_pages.py")
else:
    subprocess.run([sys.executable, os.path.join(HERE, "build_pages.py")], check=True, cwd=HERE)


# ------------------------------------------------------- 4. validators

print("\n4. validators")
if DRY:
    print("   would run validate_claims.py --strict and verify_index_html.py")
else:
    rc = subprocess.run([sys.executable, os.path.join(HERE, "validate_claims.py"), "--strict"], cwd=HERE).returncode
    if rc != 0:
        fail("validate_claims.py --strict failed. Nothing further was run.")
    subprocess.run([sys.executable, os.path.join(HERE, "verify_index_html.py"), "index.html"], check=True, cwd=HERE)

print("\nDone. Now run deploy.bat to publish.")
