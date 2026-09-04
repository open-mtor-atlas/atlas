#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""patch4.py -- Ukol 3 part 2: adds a "Download the data" section to the
/data/ page body, listing the live exports from data/exports/manifest.json
(same source of truth as DATASET_REF.distribution from patch3.py -- one
manifest, two consumers, never two hand-typed lists to keep in sync)."""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else "build_pages.py"
    with open(path, encoding="utf-8") as f:
        src = f.read()

    MARKER = "# --- SEO P0 Ukol 3 (2026-09-02): /data/ download section"
    if MARKER in src:
        sys.exit("Already patched (marker found) -- aborting.")

    orig_len = len(src)

    old_anchor = (
        '<p>A machine-readable citation file is also available:\n'
        '<a href="{SITE}/CITATION.cff">CITATION.cff</a>.</p>\n'
        '\n'
        '<h2>What\'s in the corpus right now</h2>'
    )
    assert src.count(old_anchor) == 1, "data_page anchor not found/unique: %d" % src.count(old_anchor)

    new_block = (
        '<p>A machine-readable citation file is also available:\n'
        '<a href="{SITE}/CITATION.cff">CITATION.cff</a>.</p>\n'
        '\n'
        f'{MARKER} ---\n'
        '<h2>Download the data</h2>\n'
        '<p>The full corpus as flat CSV/JSON files -- the same data behind every\n'
        'page on this site, without scraping HTML. Regenerated on every deploy,\n'
        'so file sizes below reflect the current corpus, not a stale snapshot.</p>\n'
        '{export_files_html}'
        '<p>These exports are living data, not a permanent citable snapshot -- for a\n'
        'DOI-versioned copy, use the Zenodo archive above.</p>\n'
        '\n'
        '<h2>What\'s in the corpus right now</h2>'
    )
    src = src.replace(old_anchor, new_block, 1)

    # data_page() builds `body` as an f-string -- {export_files_html} needs a
    # real value in scope before that f-string executes. Insert the variable
    # right before the `body = f"""..."""` assignment inside data_page().
    body_anchor = '    body = f"""<h1>Data &amp; Citation</h1>'
    assert src.count(body_anchor) == 1, "body= anchor not found/unique"
    var_setup = (
        '    export_files_html = _export_files_html()\n'
        '    body = f"""<h1>Data &amp; Citation</h1>'
    )
    src = src.replace(body_anchor, var_setup, 1)

    # Helper: renders the manifest as an HTML <ul>, or a plain sentence if
    # the exports haven't been built yet (never a broken/empty section).
    helper_anchor = "def data_page(studies, entities):"
    assert src.count(helper_anchor) == 1, "data_page def anchor not found/unique"
    helper = f'''{MARKER} -- html fragment ---
def _export_files_html():
    """<ul> of data/exports/*.csv|json from manifest.json (same file
    _load_export_distribution() reads for DATASET_REF) -- human-readable
    counterpart to that machine-readable JSON-LD list, one source of
    truth for both."""
    p = os.path.join(HERE, "data", "exports", "manifest.json")
    if not os.path.exists(p):
        return ("<p><em>Exports are generated at build time and were not "
                "present in this build.</em></p>\\n")
    try:
        manifest = json.load(open(p, encoding="utf-8"))
    except Exception:
        return ""
    items = []
    for m in manifest:
        kb = m["contentSize"] / 1024
        items.append(f'<li><a href="{{m["contentUrl"]}}">{{m["name"]}}</a> '
                     f'({{m["encodingFormat"]}}, {{kb:.0f}} KB)</li>')
    return "<ul>" + "".join(items) + "</ul>\\n"


{helper_anchor}'''
    src = src.replace(helper_anchor, helper, 1)

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
