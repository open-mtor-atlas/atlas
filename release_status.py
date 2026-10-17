"""Release status: does the live dataset match the archived release it claims?

Externi audit 17. 10. 2026 (BLOCKING): API hlasilo `dataset_version: 2.0.1`,
prestoze zivy obsah (450 studii) uz neodpovidal nemennemu archivu v2.0.1 na
Zenodu (428 studii). Vyzkumnik by citoval verzi, kterou neanalyzoval.

Pravidlo od teto chvile:
  * `dataset_version` je ciste cislo release (napr. "2.0.1") JEN tehdy, kdyz
    otisk zivych dat je shodny s otiskem ulozenym u te release v
    `atlas_data/releases.json`.
  * Jinak je to "<posledni release>+unreleased" a `live_matches_release`
    je false. Pro citaci presneho stavu plati corpus_snapshot + source_commit;
    version DOI posledni release popisuje jiny (starsi) stav.

Otisk (data_fingerprint) je sha256 kanonickeho JSON nad obsahem, ktery API
servíruje: studie, entity, otevrene a frontier otazky, hrany drahy
(relations_baked + model.json). Casova razitka generatoru (`generated`,
`_about`, model.meta.generated) se vynechavaji, aby stejny obsah dal
stejny otisk i po dalsim deployi bez zmeny dat.

Pouziti:
  python release_status.py                 # zapise atlas_data/release_status.json
  python release_status.py --ref v2.0.1    # vypise otisk a pocty stavu v gitu (pro releases.json)
  python release_status.py --check         # exit 1, kdyz CITATION.cff a releases.json nesouhlasi
  python release_status.py --dir <slozka>  # overi rozbaleny Zenodo archiv proti releases.json

Nova release (postup v RELEASE_CHECKLIST.md): po tagu spustit `--ref vX.Y.Z`
a vystup pridat do atlas_data/releases.json SPOLU s version DOI ze Zenoda.
"""
import argparse, hashlib, json, os, re, subprocess, sys, time

ROOT = os.path.dirname(os.path.abspath(__file__))
FILES = {
    "studies": "atlas_data/studies_baked.json",
    "entities": "atlas_data/entities_baked.json",
    "questions": "atlas_data/gaps_baked.json",
    "frontier": "atlas_data/frontier_baked.json",
    "relations": "atlas_data/relations_baked.json",
    "model": "pathway/model.json",
}
VOLATILE = {"generated", "_about"}
RELEASES = os.path.join(ROOT, "atlas_data", "releases.json")
OUT = os.path.join(ROOT, "atlas_data", "release_status.json")
ALGO = "sha256/canonical-json/v1"


def _strip(x):
    if isinstance(x, dict):
        return {k: _strip(v) for k, v in x.items() if k not in VOLATILE}
    if isinstance(x, list):
        return [_strip(v) for v in x]
    return x


def _load(rel, ref=None, root=None):
    if ref is None:
        p = os.path.join(root or ROOT, rel)
        if not os.path.isfile(p):
            return None
        with open(p, encoding="utf-8") as f:
            return json.load(f)
    r = subprocess.run(["git", "-C", ROOT, "show", "%s:%s" % (ref, rel)],
                       capture_output=True)
    if r.returncode != 0:
        return None
    return json.loads(r.stdout.decode("utf-8"))


def measure(ref=None, root=None):
    data = {k: _load(v, ref, root) for k, v in FILES.items()}
    canon = json.dumps(_strip(data), sort_keys=True, ensure_ascii=False,
                       separators=(",", ":"))
    rel = data.get("relations") or {}
    edges = rel.get("edges", []) if isinstance(rel, dict) else []
    counts = {
        "studies": len(data["studies"] or []),
        "entities": len(data["entities"] or []),
        "questions": len(data["questions"] or []) + len(data["frontier"] or []),
        # None = v tom stavu hrany jeste nebyly v relations_baked.json (pred 30. 9.)
        "relations_published": sum(1 for e in edges if e.get("published", True)) if data.get("relations") else None,
        "relations_raw": len(edges) if data.get("relations") else None,
    }
    files = {k: hashlib.sha256(json.dumps(_strip(v), sort_keys=True, ensure_ascii=False,
                                          separators=(",", ":")).encode("utf-8")).hexdigest()
             for k, v in data.items()}
    return {"algorithm": ALGO,
            "data_fingerprint": hashlib.sha256(canon.encode("utf-8")).hexdigest(),
            "file_fingerprints": files, "counts": counts}


def cff_version():
    with open(os.path.join(ROOT, "CITATION.cff"), encoding="utf-8") as f:
        m = re.search(r'^version:\s*"?([^"\n]+)"?', f.read(), re.M)
    return m.group(1).strip() if m else None


def releases():
    with open(RELEASES, encoding="utf-8") as f:
        return json.load(f)["releases"]


def check():
    rs = releases()
    latest = rs[-1]
    v = cff_version()
    bad = []
    if v != latest["version"]:
        bad.append("CITATION.cff version %r != posledni release v releases.json %r" % (v, latest["version"]))
    for r in rs:
        for k in ("version", "tag", "commit", "date", "version_doi", "data_fingerprint", "algorithm", "counts"):
            if not r.get(k):
                bad.append("releases.json: %s nema %s" % (r.get("version"), k))
        if r.get("algorithm") and r["algorithm"] != ALGO:
            bad.append("releases.json: %s ma otisk %s, skript pocita %s (prepocitat --ref)" % (r["version"], r["algorithm"], ALGO))
        if r.get("version_doi"):
            with open(os.path.join(ROOT, "CITATION.cff"), encoding="utf-8") as f:
                if r["version_doi"] not in f.read():
                    bad.append("CITATION.cff neobsahuje version DOI %s release %s" % (r["version_doi"], r["version"]))
    return bad


def load_status():
    """Pro build_pages.py / build_data_exports.py: stav z posledniho behu.
    Kdyz soubor chybi, spocita ho na miste (nikdy si nevymysli cislo)."""
    try:
        with open(OUT, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        latest = releases()[-1]
        live = measure()
        same = live["data_fingerprint"] == latest["data_fingerprint"]
        return {"dataset_version": latest["version"] if same else latest["version"] + "+unreleased",
                "live_matches_release": same,
                "latest_release": {k: latest[k] for k in ("version", "tag", "commit", "date", "version_doi", "counts")},
                "live": {"data_fingerprint": live["data_fingerprint"], "algorithm": ALGO, "counts": live["counts"]}}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ref")
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--dir", help="rozbaleny archiv (Zenodo zip): otisk jeho dat")
    a = ap.parse_args()
    if a.dir:
        m = measure(root=a.dir)
        hit = [r["version"] for r in releases() if r["data_fingerprint"] == m["data_fingerprint"]]
        m["matches_release"] = hit[0] if hit else None
        print(json.dumps(m, indent=2))
        return 0 if hit else 1
    if a.ref:
        m = measure(a.ref)
        c = subprocess.run(["git", "-C", ROOT, "rev-list", "-n", "1", a.ref],
                           capture_output=True, text=True).stdout.strip()
        m["commit"] = c
        print(json.dumps(m, indent=2))
        return 0
    bad = check()
    if bad:
        for b in bad:
            print("  release_status: CHYBA:", b)
        return 1
    if a.check:
        print("  release_status: CITATION.cff a releases.json souhlasi")
        return 0
    latest = releases()[-1]
    live = measure()
    same = live["data_fingerprint"] == latest["data_fingerprint"]
    status = {
        "_about": "Generated by release_status.py on every deploy. Do not edit by hand.",
        "dataset_version": latest["version"] if same else latest["version"] + "+unreleased",
        "live_matches_release": same,
        "latest_release": {k: latest[k] for k in ("version", "tag", "commit", "date", "version_doi", "counts")},
        "live": {"data_fingerprint": live["data_fingerprint"], "algorithm": ALGO,
                 "counts": live["counts"], "measured": time.strftime("%Y-%m-%dT%H:%M:%S%z")},
    }
    tmp = OUT + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(status, f, ensure_ascii=False, indent=1)
    os.replace(tmp, OUT)
    lc, rc = live["counts"], latest["counts"]
    print("  release_status: dataset_version=%s (zive %d studii / %d hran, release %s: %d / %d)"
          % (status["dataset_version"], lc["studies"], lc["relations_published"],
             latest["version"], rc["studies"], rc["relations_published"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
