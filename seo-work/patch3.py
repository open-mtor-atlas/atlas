#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""patch3.py -- Ukol 3: wires data/exports/manifest.json into DATASET_REF's
distribution list and adds a "Download the data" section to /data/.
Same anchor-based str.replace splicing pattern as patch2.py (Ukol 2) --
no inline meta-programming escaping games."""
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

    MARKER = "# --- SEO P0 Ukol 3 (2026-09-02): data exports"
    if MARKER in src:
        sys.exit("Already patched (marker found) -- aborting.")

    orig_len = len(src)

    # 1) helper: load data/exports/manifest.json -> list of DataDownload dicts.
    anchor1 = '    return m.group(1) if m else "unknown"\n'
    assert src.count(anchor1) == 1, "anchor1 not found/unique"
    helper = read("new_export_helper.txt")
    assert MARKER in helper
    src = src.replace(anchor1, anchor1 + "\n\n" + helper, 1)

    # 2) distribution: single dict -> list (Zenodo entry + live export files).
    old_dist = (
        '    "distribution": {\n'
        '        "@type": "DataDownload",\n'
        '        "name": "Archived snapshot (Zenodo)",\n'
        '        "encodingFormat": "text/html",\n'
        '        "contentUrl": "https://doi.org/10.5281/zenodo.22059963",\n'
        '    },\n'
    )
    assert src.count(old_dist) == 1, "distribution anchor not found/unique"
    new_dist = (
        '    "distribution": [\n'
        '        {\n'
        '            "@type": "DataDownload",\n'
        '            "name": "Archived snapshot (Zenodo)",\n'
        '            "encodingFormat": "text/html",\n'
        '            "contentUrl": "https://doi.org/10.5281/zenodo.22059963",\n'
        '        },\n'
        '    ] + _load_export_distribution(),\n'
    )
    src = src.replace(old_dist, new_dist, 1)

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
