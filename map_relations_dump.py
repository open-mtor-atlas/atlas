#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
map_relations_dump.py -- MCP dump tabulky Relations -> atlas_data/relations_baked.json

Druhá vstupní cesta vedle sync_relations.py (REST). Je pro prostředí, kde
AIRTABLE_TOKEN ani síť na api.airtable.com nejsou (Cowork sandbox, denní
kontrola): dump se udělá Airtable MCP konektorem (list_records_for_table nad
tblT4hOU9HrTFe4Ik, všechna pole) a uloží jako JSON {"records": [...]}.

    python map_relations_dump.py <dump.json>            # dry run: počty a problémy
    python map_relations_dump.py <dump.json> --write    # zapíše relations_baked.json
                                                        # + ATLAS_EDGES v index.html

Převod dělá relations_bake.normalize() -- týž kód jako REST cesta, takže se
obě cesty nemůžou rozejít v mapování polí (poučení z PMID/PMCID 15. 8.).
"""
import json
import os
import sys

import relations_bake as rb


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if not args:
        sys.exit(__doc__)
    dump = json.load(open(args[0], encoding="utf-8"))
    edges, problems = rb.normalize(dump["records"])
    pub = [e for e in edges if e["published"]]
    print("%d relations in dump, %d published" % (len(edges), len(pub)))
    for p in problems:
        print("  PROBLEM: " + p)
    if problems and any("published" in p for p in problems):
        sys.exit("ABORT: a published edge is incomplete; fix it in Airtable first.")
    if "--write" not in sys.argv:
        print("Dry run. Re-run with --write.")
        return
    rb.write(edges, "MCP dump (map_relations_dump.py)")
    changed = rb.write_atlas_edges_into_index(os.path.join(rb.HERE, "index.html"))
    print("relations_baked.json written; ATLAS_EDGES %s." % ("updated" if changed else "unchanged"))


if __name__ == "__main__":
    main()
