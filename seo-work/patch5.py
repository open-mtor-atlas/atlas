#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""patch5.py -- Ukol 11.3: /changelog/ page + About corrections-log link
+ llms.txt Machine-readable section gets /data/exports/ and /changelog/."""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))


def read(name):
    with open(os.path.join(HERE, name), encoding="utf-8") as f:
        return f.read()


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else "build_pages.py"
    with open(path, encoding="utf-8") as f:
        src = f.read()

    MARKER = "# --- SEO P0 Ukol 11.3 (2026-09-02): /changelog/"
    if MARKER in src:
        sys.exit("Already patched (marker found) -- aborting.")

    orig_len = len(src)

    # 1) insert changelog_page() right before about_page() (needs no new
    # module-level state -- reads the two changelog JSONs itself, same
    # files _load_record_dates() already reads for a different purpose).
    anchor1 = "def about_page(studies, entities):"
    assert src.count(anchor1) == 1, "about_page anchor not found/unique"
    fn = read("new_changelog_page.txt")
    src = src.replace(anchor1, f"{MARKER} ---\n{fn}{anchor1}", 1)

    # 2) About page: add a "Corrections log" paragraph right before its
    # "License & reuse" h2 (unique anchor -- data_page() has its own,
    # separate "License & reuse" h2 that must NOT be touched).
    anchor2 = ('typed in by hand.</p>\n\n<h2>License &amp; reuse</h2>')
    assert src.count(anchor2) == 1, "about_page License anchor not found/unique"
    new2 = (
        'typed in by hand.</p>\n\n'
        '<h2>Corrections log</h2>\n'
        '<p>Every recorded correction to a study record -- what changed and '
        'why, going back to the first external review -- is public at '
        f'<a href="{{SITE}}/changelog/">/changelog/</a>. This is what "all '
        'were addressed rather than quietly dropped" above actually means: '
        'a checkable list, not a claim to take on faith.</p>\n\n'
        '<h2>License &amp; reuse</h2>'
    )
    src = src.replace(anchor2, new2, 1)

    # 3) main(): write changelog/index.html, add to urls + sitemap-home.xml.
    anchor3 = (
        '    durl, dpage = data_page(studies, entities)\n'
        '    write(os.path.join(HERE, "data", "index.html"), dpage)\n'
        '    urls.append(("about", durl))\n'
    )
    assert src.count(anchor3) == 1, "data_page call-site anchor not found/unique"
    new3 = anchor3 + (
        '\n'
        '    changelog_url, changelog_page_html = changelog_page(studies)\n'
        '    write(os.path.join(HERE, "changelog", "index.html"), changelog_page_html)\n'
        '    urls.append(("about", changelog_url))\n'
    )
    src = src.replace(anchor3, new3, 1)

    anchor4 = (
        '          f\'  <url><loc>{durl}</loc><changefreq>monthly</changefreq><priority>0.6</priority></url>\\n\'\n'
        '          \'</urlset>\\n\')\n'
    )
    assert src.count(anchor4) == 1, "sitemap-home.xml anchor not found/unique"
    new4 = (
        '          f\'  <url><loc>{durl}</loc><changefreq>monthly</changefreq><priority>0.6</priority></url>\\n\'\n'
        '          f\'  <url><loc>{changelog_url}</loc><changefreq>monthly</changefreq><priority>0.4</priority></url>\\n\'\n'
        '          \'</urlset>\\n\')\n'
    )
    src = src.replace(anchor4, new4, 1)

    # 4) llms.txt "Machine-readable" section: add data/exports + changelog.
    anchor5 = (
        '## Machine-readable\n'
        '- [Data & Citation](https://mtor-atlas.org/data/): DOI, ORCID, license, bio.tools/FAIRsharing registration, citation string\n'
        '- [Sitemap index](https://mtor-atlas.org/sitemap.xml)\n'
        '- [robots.txt](https://mtor-atlas.org/robots.txt)\n'
    )
    assert src.count(anchor5) == 1, "llms.txt Machine-readable anchor not found/unique"
    new5 = (
        '## Machine-readable\n'
        '- [Data & Citation](https://mtor-atlas.org/data/): DOI, ORCID, license, bio.tools/FAIRsharing registration, citation string\n'
        '- [Data exports (CSV/JSON)](https://mtor-atlas.org/data/exports/): the full corpus as flat files, regenerated on every deploy\n'
        '- [Corrections log](https://mtor-atlas.org/changelog/): every recorded correction to a study record, with reason\n'
        '- [Sitemap index](https://mtor-atlas.org/sitemap.xml)\n'
        '- [robots.txt](https://mtor-atlas.org/robots.txt)\n'
    )
    src = src.replace(anchor5, new5, 1)

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
