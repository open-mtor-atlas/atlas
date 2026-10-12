#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Pre-flight pro deploy.bat -- chytne dve chyby DRIV, nez se udela prace.

PROC VZNIKL (11. 10. 2026)
Audit toho dne nasel, ze deploy padal na dve veci, ktere obe byly poznatelne
hned na zacatku, ale hlasily se az po deseti az dvaceti minutach prace:

  1. "node not curated: Insulin" -- hrana v Airtable ukazuje na uzel, ktery
     neni v tabulce NODES v build_pathway_model.py. Deploy se o tom dozvedel
     az u build_pathway_model.py, tedy po build_academy.py, obou verifikacich
     a build_data_exports.py. Vsechna ta prace sla do kose.

  2. Novy pomocny modul (konkretne atlas_wording.py) existoval na disku,
     validate_claims.py i check_consistency.py ho importovaly, ale NEBYL
     v seznamu pro `git add` v deploy.bat ani tracked v gitu. Deploy by
     tedy pushnul obe brany, ktere importuji modul, co na origin neni --
     a na cistem klonu by spadly na ImportError. Zadna brana tohle
     nekontrolovala, protoze lokalne vsechno fungovalo.

Obe chyby jsou stejna trida: jedna vec musi byt na dvou mistech a nic
nehlasi, kdyz je jen na jednom.

SPOUSTENI
    py preflight_deploy.py            # vypis, exit 0
    py preflight_deploy.py --strict   # exit 1, kdyz je nalez (tak to ma deploy.bat)

Kontrola 1 chce uz synchronizovane ATLAS_EDGES, takze v deploy.bat bezi
AZ ZA sync_relations.py --write -- ale pred build_academy.py.

ZADNA DUPLIKACE: tabulka uzlu se importuje z build_pathway_model.py
(je import-safe, vse je pod __name__ == "__main__"), ne kopiruje. Jinak by
tenhle skript byl tretim mistem, kde se ta vec musi udrzovat.
"""
import ast
import io
import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
problems = []
notes = []


def read(path):
    return io.open(path, encoding="utf-8", errors="replace").read()


# ---------------------------------------------------------------------------
# 1) Hrany ukazuji jen na kurovane uzly
# ---------------------------------------------------------------------------
def check_curated_nodes():
    try:
        sys.path.insert(0, ROOT)
        from build_pathway_model import NODES, read_atlas_array
    except Exception as exc:
        problems.append("nelze importovat build_pathway_model (NODES): %s" % exc)
        return
    index = os.path.join(ROOT, "index.html")
    if not os.path.exists(index):
        problems.append("index.html chybi -- kontrola uzlu neprobehla")
        return
    try:
        edges = read_atlas_array(read(index), "ATLAS_EDGES")
    except SystemExit as exc:
        problems.append("ATLAS_EDGES se necte z index.html: %s" % exc)
        return
    endpoints = set()
    for e in edges:
        endpoints.add(e.get("s"))
        endpoints.add(e.get("t"))
    endpoints.discard(None)
    missing = sorted(n for n in endpoints if n not in NODES)
    for name in missing:
        problems.append(
            "uzel neni kurovany: %r -- build_pathway_model.py by spadl. "
            "Pridej do NODES radek:  %r: (\"<kompartment>\", \"<class>\", "
            "\"<beginner>\", \"<student>\", \"<research>\")," % (name, name))
    notes.append("uzly: %d endpointu ve %d hranach, %d nekurovanych"
                 % (len(endpoints), len(edges), len(missing)))


# ---------------------------------------------------------------------------
# 2) Vsechno, co deploy spousti, se taky nasazuje
# ---------------------------------------------------------------------------
RUN_RE = re.compile(r"^\s*(?:py|python|node)\s+([A-Za-z0-9_\\/.-]+\.(?:py|js))", re.M)


def staged_names(bat_text):
    """Jmena souboru, ktere deploy.bat realne stage-uje.

    Dve formy: `git add X` a `for %%F in (A B C) do ... git add "%%F"`.
    Bere se jen basename, protoze seznamy mixuji `pathway\\pathway.js`
    a `validate_claims.py`.
    """
    names = set()
    for m in re.finditer(r"git add\s+\"?([A-Za-z0-9_\\/.%-]+)\"?", bat_text):
        tok = m.group(1)
        if "%" not in tok:
            names.add(os.path.basename(tok.replace("\\", "/")))
    for m in re.finditer(r"for\s+%%[A-Za-z]\s+in\s+\(([^)]*)\)", bat_text, re.S):
        for tok in m.group(1).split():
            names.add(os.path.basename(tok.strip('"').replace("\\", "/")))
    return names


def tracked_files():
    try:
        out = subprocess.check_output(["git", "ls-files"], cwd=ROOT).decode("utf-8", "replace")
    except Exception as exc:
        notes.append("git ls-files nedostupne (%s) -- kontrola manifestu jen proti deploy.bat" % exc)
        return None
    return {os.path.basename(l.strip()) for l in out.splitlines() if l.strip()}


def first_party_imports(entry_paths):
    """Tranzitivni uzavera lokalnich .py modulu, ktere entry skripty importuji."""
    seen, queue, needed = set(), list(entry_paths), set()
    while queue:
        path = queue.pop()
        if path in seen or not os.path.exists(path):
            continue
        seen.add(path)
        if not path.endswith(".py"):
            continue
        try:
            tree = ast.parse(read(path), filename=path)
        except SyntaxError as exc:
            problems.append("%s se neda naparsovat: %s" % (os.path.basename(path), exc))
            continue
        mods = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                mods.update(a.name.split(".")[0] for a in node.names)
            elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                mods.add(node.module.split(".")[0])
        for mod in mods:
            cand = os.path.join(ROOT, mod + ".py")
            if os.path.exists(cand):
                needed.add(mod + ".py")
                queue.append(cand)
    return needed


def check_manifest():
    bat = os.path.join(ROOT, "deploy.bat")
    if not os.path.exists(bat):
        problems.append("deploy.bat chybi -- kontrola manifestu neprobehla")
        return
    text = read(bat)
    entries = []
    for rel in RUN_RE.findall(text):
        p = os.path.join(ROOT, rel.replace("\\", os.sep))
        if os.path.exists(p):
            entries.append(p)
    staged = staged_names(text)
    tracked = tracked_files()
    needed = first_party_imports(entries)
    needed.update(os.path.basename(p) for p in entries)

    for name in sorted(needed):
        in_bat = name in staged
        in_git = tracked is None or name in tracked
        if in_bat or in_git:
            continue
        problems.append(
            "%s deploy spousti nebo importuje, ale nikdo ho nenasazuje -- "
            "neni tracked v gitu ani v seznamu pro `git add` v deploy.bat. "
            "Na cistem klonu spadne skript, ktery ho importuje." % name)

    stale = sorted(n for n in staged
                   if n.endswith((".py", ".js"))
                   and not os.path.exists(os.path.join(ROOT, n))
                   and not any(os.path.exists(os.path.join(ROOT, d, n))
                               for d in ("pathway", "tools", "tools/seo",
                                           "atlas_fulltext", "atlas_gaps")))
    for name in stale:
        notes.append("deploy.bat stage-uje %s, ale na disku neni (prejmenovany? smazany?)" % name)

    notes.append("manifest: %d entry skriptu, %d lokalnich modulu v uzavere"
                 % (len(entries), len(needed)))


# ---------------------------------------------------------------------------
# 3) Kategorie studie a vrstva dukazu se nesmi rozchazet (audit 2026-10-12,
#    KAL2026: kategorie Animal, ale vrstva "Mechanistic/Review")
# ---------------------------------------------------------------------------
def check_category_tier():
    import json
    path = os.path.join(ROOT, "atlas_data", "studies_baked.json")
    if not os.path.exists(path):
        return
    for st in json.load(io.open(path, encoding="utf-8")):
        cat, tier = st.get("category"), (st.get("tier") or "")
        if cat == "Animal" and not tier.startswith("C"):
            problems.append("%s: kategorie Animal, ale vrstva '%s' (ma byt C - Animal)" % (st.get("sid"), tier))
        if cat == "Human" and tier[:1] not in ("A", "B"):
            problems.append("%s: kategorie Human, ale vrstva '%s' (ma byt A nebo B)" % (st.get("sid"), tier))


def main():
    check_curated_nodes()
    check_manifest()
    check_category_tier()
    for n in notes:
        print("  " + n)
    if problems:
        print("")
        print("PREFLIGHT: %d nalezu" % len(problems))
        for p in problems:
            print("  - " + p)
        if "--strict" in sys.argv:
            return 1
    else:
        print("PREFLIGHT OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
