#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
check_tier_palette.py — branka pro paletu evidence tierů.

PROČ TOHLE EXISTUJE
-------------------
Recenzent (2026-07-29, bod 9) namítl, že tier badge vypadají jako známkování
kvality, ne jako typ studie. Původní paleta šla zelená → modrá → jantarová →
šedá, tedy od "živé" k "mdlé" — a čtenář z toho čte pořadí. Tier D pak vypadá
jako špatná věda, přitom znamená jen "mechanistická práce v buňkách".

Oprava není jen jiná čtyři barvy. Je to PRAVIDLO, které musí platit dál:

  1. Čtyři typy studií (A–D) mají STEJNOU relativní luminanci. Když mají
     stejnou světlost, nemůže jedna vypadat "lepší" než druhá — liší se jen
     odstín, a odstín kóduje zkoumaný systém, ne kvalitu.
  2. Každá dvojice musí být rozlišitelná (jinak je paleta k ničemu).
  3. Kontrast textu na chipu >= 4.5:1 v obou tématech.
  4. Žádný tier nesmí kolidovat s brandovými barvami.
  5. PP a RT nejsou typ studie, ale STAV úplnosti — kreslí se obtaženě, ne
     vyplněně, takže mají jiný tvar, ne jen jinou barvu.
  6. Barvy hran v pathway modulu NESMÍ sdílet proměnné s tiery. Když je
     sdílely, přebarvení tierů potichu změnilo význam šipek v dráze.

Bez téhle branky se paleta při první "malé úpravě" vrátí do rampy.

POUŽITÍ
    py check_tier_palette.py            # report
    py check_tier_palette.py --strict   # nenulový exit při chybě (deploy)
"""

import io
import os
import re
import sys
import itertools

ROOT = os.path.dirname(os.path.abspath(__file__))
BRAND = {"crimson": "#A31F34", "amber": "#C17A2E", "danger": "#B4442E"}
TIERS = ["a", "b", "c", "d"]
STATUS = ["pp", "rt"]


def lum(h):
    h = h.lstrip("#")
    r, g, b = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    f = lambda c: c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b)


def contrast(a, b):
    l1, l2 = sorted([lum(a), lum(b)], reverse=True)
    return (l1 + 0.05) / (l2 + 0.05)


def dist(a, b):
    a, b = a.lstrip("#"), b.lstrip("#")
    return sum(abs(int(a[i:i + 2], 16) - int(b[i:i + 2], 16)) for i in (0, 2, 4))


def grab(block, name):
    m = re.search(r"--tier-%s\s*:\s*(#[0-9A-Fa-f]{6})" % name, block)
    return m.group(1) if m else None


def main():
    strict = "--strict" in sys.argv
    html = io.open(os.path.join(ROOT, "index.html"), encoding="utf-8").read()
    errs, warns = [], []

    # Read the EFFECTIVE value, not the first one.
    #
    # The first version of this gate parsed only the first `:root{` block and
    # therefore validated values that were not what the browser painted: a
    # later `html:not([data-theme="dark"])` rule -- added months earlier to fix
    # the contrast of the OLD amber/grey tiers -- still overrode --tier-c and
    # --tier-d. The gate reported a clean equal-luminance palette while the live
    # site showed the ramp. Same blind-spot class as an unscoped querySelector:
    # checking a value that is not the one in force is not a check.
    i = html.find(":root{")
    light_block = html[i:html.find("}", i)]
    j = html.find('[data-theme="dark"]{')
    dark_block = html[j:html.find("}", j)]

    light = {k: grab(light_block, k) for k in TIERS + STATUS}
    dark = {k: grab(dark_block, k) for k in TIERS + STATUS}

    # Any tier variable redefined outside those two blocks wins in the cascade
    # and must be treated as an error, not silently ignored.
    for k in TIERS + STATUS:
        hits = [m.start() for m in re.finditer(r"--tier-%s\s*:" % k, html)]
        outside = [h for h in hits
                   if not (i <= h < html.find("}", i) or j <= h < html.find("}", j))]
        if outside:
            errs.append("--tier-%s is redefined outside :root and the dark theme (at %s). "
                        "That override is what the browser actually paints, so this gate "
                        "would be validating a value nobody sees."
                        % (k, ", ".join(str(o) for o in outside)))
        if len(hits) > 2:
            errs.append("--tier-%s has %d definitions; expected exactly 2 (light + dark)"
                        % (k, len(hits)))
    for k in TIERS + STATUS:
        if not light[k]:
            errs.append("--tier-%s missing from :root" % k)
        if not dark[k]:
            errs.append("--tier-%s missing from the dark theme" % k)
    if errs:
        print("\n".join("  X " + e for e in errs))
        return 1 if strict else 0

    # 1. equal luminance across the four study types = no quality ramp
    ls = [lum(light[k]) for k in TIERS]
    spread = max(ls) - min(ls)
    if spread > 0.02:
        errs.append("evidence tiers span %.4f in luminance — that reads as a quality ramp. "
                    "The four study types must sit at equal luminance; only hue may differ." % spread)
    ld = [lum(dark[k]) for k in TIERS]
    if max(ld) - min(ld) > 0.03:
        errs.append("dark-theme tiers span %.4f in luminance — same ramp problem" % (max(ld) - min(ld)))

    # 2. mutual distinguishability
    for a, b in itertools.combinations(TIERS, 2):
        d = dist(light[a], light[b])
        if d < 100:
            errs.append("tiers %s and %s are only %d apart — not tellable apart"
                        % (a.upper(), b.upper(), d))

    # 3. text contrast on the chip
    for k in TIERS:
        c = contrast(light[k], "#FFFFFF")
        if c < 4.5:
            errs.append("tier %s: white badge text on %s is %.2f:1, below 4.5"
                        % (k.upper(), light[k], c))
        c = contrast(dark[k], "#0e1219")
        if c < 4.5:
            errs.append("tier %s (dark): text on %s is %.2f:1, below 4.5" % (k.upper(), dark[k], c))
    for k in STATUS:
        c = contrast(light[k], "#FFFFFF")
        if c < 4.5:
            errs.append("%s: outlined chip text %s on white is %.2f:1, below 4.5"
                        % (k.upper(), light[k], c))

    # 4. no collision with brand colours
    for k in TIERS + STATUS:
        for bk, bv in BRAND.items():
            d = dist(light[k], bv)
            if d < 110:
                errs.append("tier %s collides with the %s brand colour (%d apart)"
                            % (k.upper(), bk, d))

    # 4b. a tier letter must never appear without its meaning, and must never be
    #     described as a "strength". The live badges carried title="Evidence
    #     strength" — the exact framing the review objected to, baked into the
    #     markup while TIER_LABELS sat unused one call site away.
    if 'title="Evidence strength"' in html:
        errs.append('a tier badge is still labelled "Evidence strength". A tier records the '
                    "KIND of study, not its strength; that title is the misreading itself.")
    if "function tierTitle(" not in html:
        errs.append("tierTitle() is gone — tier letters would render without their meaning")
    if html.count("tierTitle(") < 4:
        errs.append("tierTitle() has only %d call sites; every badge emitter must use it, "
                    "or some letters stand alone again" % html.count("tierTitle("))

    # 5. status tiers must render outlined, not filled
    if "status:true" not in html:
        errs.append("tierMeta no longer marks PP/RT as status — they would render as if "
                    "they were a kind of study rather than a completeness state")
    css = io.open(os.path.join(ROOT, "pathway", "pathway.css"), encoding="utf-8").read()
    if ".pw-dot.st" not in css:
        errs.append("pathway.css lost the outlined-status chip rule")

    # 6. pathway edge colours must NOT borrow tier variables
    for m in re.finditer(r"\.pw-e\.f-[a-z-]+\{([^}]*)\}", css):
        if "--tier-" in m.group(1):
            errs.append("a pathway edge effect is coloured from a --tier-* variable. "
                        "Edge meaning and study tier are unrelated vocabularies; recolouring "
                        "tiers would silently change what the arrows mean.")
    for tok in ["--pw-act", "--pw-inh", "--pw-req", "--pw-bind"]:
        if tok not in css:
            errs.append("pathway.css is missing the dedicated edge token %s" % tok)

    print("evidence tier palette")
    for k in TIERS:
        print("  %s  %s / %s   lum %.4f   white-contrast %.2f   %s"
              % (k.upper(), light[k], dark[k], lum(light[k]),
                 contrast(light[k], "#FFFFFF"), "filled"))
    for k in STATUS:
        print("  %s %s / %s   outlined (completeness status, not a study type)"
              % (k.upper(), light[k], dark[k]))
    print("  luminance spread across A-D: %.4f (must stay under 0.02)" % spread)
    print("  closest tier pair: %d (must stay above 100)"
          % min(dist(light[a], light[b]) for a, b in itertools.combinations(TIERS, 2)))
    print("ERRORS   %d" % len(errs))
    for e in errs:
        print("  X", e)
    print("WARNINGS %d" % len(warns))
    for w in warns:
        print("  !", w)
    if errs and strict:
        print("\nABORT: the tier palette would reintroduce a quality ramp.")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
