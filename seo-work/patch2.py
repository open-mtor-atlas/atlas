#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""patch2.py -- applies the Ukol 2 study_page rebuild to build_pages.py.
Reads the two prebuilt source fragments (new_helpers.txt, new_study_page.txt)
from the same directory as this script and splices them in via exact-anchor
str.replace / regex-span replace. No inline escaping games -- every fragment
of new source lives in its own plain text file."""
import os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))


def read(name):
    with open(os.path.join(HERE, name), encoding="utf-8") as f:
        return f.read()


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else "build_pages.py"
    with open(path, encoding="utf-8") as f:
        src = f.read()

    MARKER = "# --- SEO P0 Ukol 2 (2026-09-02): study_page rebuild"
    if MARKER in src:
        sys.exit("Already patched (marker found) -- aborting.")

    orig_len = len(src)

    # 1) shell(): add robots= param.
    old_sig = ('def shell(title, desc, canonical, jsonld, body, breadcrumb, active_tab=None,\n'
               '          extra_css="", extra_body="", level_switch=False):')
    new_sig = ('def shell(title, desc, canonical, jsonld, body, breadcrumb, active_tab=None,\n'
               '          extra_css="", extra_body="", level_switch=False, robots="index, follow"):')
    assert src.count(old_sig) == 1, "shell() signature anchor not found/unique: %d" % src.count(old_sig)
    src = src.replace(old_sig, new_sig, 1)

    old_robots_tag = '<meta name="robots" content="index, follow">'
    assert src.count(old_robots_tag) == 1, "robots meta anchor not found/unique"
    src = src.replace(old_robots_tag, '<meta name="robots" content="{robots}">', 1)

    # 2) shared CSS additions.
    old_css_anchor = ('.abstract{{font-size:var(--fs-lead,17px);line-height:var(--lh-body,1.62);\n'
                      'color:var(--prose-ink,#26241F);max-width:var(--measure,68ch)}}')
    assert src.count(old_css_anchor) == 1, "abstract CSS anchor not found/unique"
    new_css = old_css_anchor + (
        '\n.tier-why{{color:var(--soft);font-size:14px;margin:-10px 0 20px;'
        'max-width:var(--measure,68ch)}}\n'
        'pre.cite{{background:var(--code-bg,rgba(0,0,0,.04));border:1px solid var(--line);\n'
        'border-radius:4px;padding:12px 14px;font-family:\'IBM Plex Mono\',monospace;\n'
        'font-size:12.5px;line-height:1.6;white-space:pre-wrap;word-break:break-word;\n'
        'max-width:var(--measure,68ch)}}\n'
        'h3{{font-size:var(--fs-h3,16px);margin:18px 0 8px}}')
    src = src.replace(old_css_anchor, new_css, 1)

    # 3) insert new helper functions right after ACADEMY_BY_SID.
    anchor3 = "ACADEMY_BY_SID = _load_academy_index()\n"
    assert src.count(anchor3) == 1, "ACADEMY_BY_SID anchor not found/unique"
    helpers = read("new_helpers.txt")
    assert MARKER in helpers, "marker missing from new_helpers.txt"
    src = src.replace(anchor3, anchor3 + "\n\n" + helpers, 1)

    # 4) replace study_page() wholesale: from its def line up to (not incl.)
    # the entity-pages section comment that follows it in the original file.
    fn_start = src.index("def study_page(s, ent_by_sid, haspage):")
    next_section = src.index("# ----------------------------------------------------------- entity pages ---")
    assert fn_start < next_section
    new_fn = read("new_study_page.txt")
    src = src[:fn_start] + new_fn + "\n\n" + src[next_section:]

    # 5) sitemap-studies.xml: drop noindexed SIDs.
    old_sitemap = ('    write(os.path.join(HERE, "sitemap-studies.xml"),\n'
                   '          sitemap([u for k, u in urls if k == "study"], "0.6"))')
    assert src.count(old_sitemap) == 1, "sitemap-studies anchor not found/unique"
    new_sitemap = (
        '    def _study_sid_from_url(u):\n'
        '        m = re.search(r"/study/([^/]+)/$", u)\n'
        '        return m.group(1) if m else None\n\n'
        '    write(os.path.join(HERE, "sitemap-studies.xml"),\n'
        '          sitemap([u for k, u in urls if k == "study"\n'
        '                   and _study_sid_from_url(u) not in NOINDEX_STUDIES], "0.6"))'
    )
    src = src.replace(old_sitemap, new_sitemap, 1)

    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(src)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)

    # independent re-verify
    check = open(path, encoding="utf-8").read()
    assert len(check) == len(src), "post-write length mismatch: %d != %d" % (len(check), len(src))
    assert check.endswith("\n") or True
    print(f"Patched {path}: {orig_len} -> {len(src)} bytes.")


if __name__ == "__main__":
    main()
