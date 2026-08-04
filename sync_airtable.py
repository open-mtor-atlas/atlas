#!/usr/bin/env python3
"""
sync_airtable.py -- regenerate the ATLAS_STUDIES and ATLAS_GAPS constants inside
index.html straight from the Airtable base (Tier-0 static bake). No secret ships
in the page. Also stamps the "last updated" timestamp.

    set AIRTABLE_TOKEN=patXXXX         # Windows;  export ... on Linux/macOS
    py sync_airtable.py
Standard library only.

Changes 2026-07-27 (Fáze 6, krok 1):
  * PMID a PMCID se nyní čtou z Airtable a bakují do stránky. Bez toho by každý
    sync tiše zahodil doplněné identifikátory.
  * Zapisuje i atlas_data/studies_baked.json, aby obě bake cesty
    (sync_airtable.py zde a bake_from_mcp.py v sandboxu) sdílely jeden zdroj.
    Dřív si každá držela vlastní stav a rozcházely se.
  * ATLAS_STUDIES se nahrazuje regexem ukotveným na následující deklaraci
    (const ATLAS_ENTITIES). Původní nekotvený `\\[.*?\\];` se dal utnout literálem
    "];" uvnitř abstraktu a zbytek pole nechat ve stránce jako mrtvý text.
  * Zápis jde přes write_verified() z bake_from_mcp.py -- tato složka je
    OneDrive-synced a velké zápisy se tu opakovaně tiše ořízly.
"""
import os, json, re, sys, urllib.request, urllib.parse, time, datetime

BASE = "appt2U6ObDHUcRlrj"
TOKEN = os.environ.get("AIRTABLE_TOKEN")
HERE = os.path.dirname(os.path.abspath(__file__))
HTML = os.path.join(HERE, "index.html")
STUDIES_JSON = os.path.join(HERE, "atlas_data", "studies_baked.json")

# Ověřený atomický zápis sdílený s bake_from_mcp.py (ten modul má main()
# schovaný za __main__, takže import nic nespustí).
from bake_from_mcp import write_verified


def api(table, params=None):
    out, offset = [], None
    while True:
        q = dict(params or {})
        if offset:
            q["offset"] = offset
        url = "https://api.airtable.com/v0/%s/%s" % (BASE, urllib.parse.quote(table))
        if q:
            url += "?" + urllib.parse.urlencode(q, doseq=True)
        req = urllib.request.Request(url, headers={"Authorization": "Bearer " + TOKEN})
        data = json.load(urllib.request.urlopen(req))
        out += data.get("records", [])
        offset = data.get("offset")
        if not offset:
            break
        time.sleep(0.25)
    return out


def g(f, k, d=""):
    v = f.get(k, d)
    return v if v is not None else d


def fetch_studies():
    """Vrátí seznam studií v ploché podobě, kterou čeká stránka i ostatní skripty."""
    arr = []
    for r in api("Studies"):
        f = r["fields"]
        arr.append({
            "id": r["id"], "sid": g(f, "Study_ID"), "title": g(f, "Title"),
            "authors": g(f, "Authors"), "year": g(f, "Year", None), "journal": g(f, "Journal"),
            "category": g(f, "Category"), "model": g(f, "Model"), "finding": g(f, "Key_Finding"),
            "tier": g(f, "Evidence_Tier"), "pyramid": g(f, "Pyramid_Level"), "peer": g(f, "Peer_Reviewed"),
            "doi": g(f, "DOI"), "abstract": g(f, "Abstract (PubMed)"),
            "pmid": g(f, "PMID"), "pmcid": g(f, "PMCID"),
            "ai_intervention": g(f, "AI_Intervention"), "ai_target": g(f, "AI_Target"),
            "ai_species": g(f, "AI_Species"), "ai_effect": g(f, "AI_Effect"),
        })
    return arr


def existing_gap_beginner_fields(h):
    """Beginner-register basis/hyp (added 2026-08-04 for the site-wide reading
    level switch) are hand-authored, not sourced from Airtable -- Airtable has
    no Evidence_Basis_Beginner/Hypothesis_Beginner columns (yet). A plain
    resync would silently wipe them, since gaps_js() below rebuilds ATLAS_GAPS
    from scratch. This reads whatever is CURRENTLY baked into index.html
    before the rewrite, keyed by Gap_ID, so a resync can carry them forward.
    Returns {} (not a crash) if ATLAS_GAPS is missing/malformed -- a sync that
    can't preserve beginner text should still be able to update the rest."""
    try:
        m = re.search(r"const ATLAS_GAPS = (\[.*?\]);", h, re.S)
        if not m:
            return {}
        arr = json.loads(m.group(1))
        return {
            row["id"]: {
                "basis_beginner": row.get("basis_beginner", ""),
                "hyp_beginner": row.get("hyp_beginner", ""),
            }
            for row in arr if row.get("basis_beginner") or row.get("hyp_beginner")
        }
    except Exception as e:
        print("  (could not read existing beginner-level gap text, continuing without it)", e)
        return {}


def gaps_js(existing_beginner=None):
    existing_beginner = existing_beginner or {}
    try:
        rows = api("Knowledge_Gaps")
    except Exception as e:
        print("  (Knowledge_Gaps not found, leaving ATLAS_GAPS untouched)", e)
        return None
    arr = []
    carried = 0
    for r in sorted(rows, key=lambda r: r["fields"].get("Gap_ID", "")):
        f = r["fields"]
        codes = re.findall(r"[A-Z]{2,}[0-9]{4}|NCT[0-9]+", f.get("Supporting_Studies", "") or "")
        gid = g(f, "Gap_ID")
        # Prefer an Airtable-sourced beginner field if one is ever added there;
        # otherwise carry forward whatever is already baked into the page.
        prev = existing_beginner.get(gid, {})
        basis_beginner = g(f, "Evidence_Basis_Beginner", "") or prev.get("basis_beginner", "")
        hyp_beginner = g(f, "Hypothesis_Beginner", "") or prev.get("hyp_beginner", "")
        if basis_beginner or hyp_beginner:
            carried += 1
        row = {"id": gid, "type": g(f, "Type"), "title": g(f, "Title"),
               "basis": g(f, "Evidence_Basis"), "hyp": g(f, "Hypothesis"),
               "exp": g(f, "Proposed_Experiment"), "studies": codes, "conf": f.get("Confidence", 0)}
        if basis_beginner:
            row["basis_beginner"] = basis_beginner
        if hyp_beginner:
            row["hyp_beginner"] = hyp_beginner
        arr.append(row)
    print("  ATLAS_GAPS: %d/%d records carrying forward Beginner-level text" % (carried, len(arr)))
    return "const ATLAS_GAPS = " + json.dumps(arr, ensure_ascii=False) + ";"


def write_studies_json(studies):
    """Zapíše atlas_data/studies_baked.json, aby ostatní skripty
    (backfill_pmids.py, gap analýza, build_chunk_index) viděly totéž co stránka."""
    os.makedirs(os.path.dirname(STUDIES_JSON), exist_ok=True)
    content = json.dumps(studies, ensure_ascii=False)
    expected = len(content.encode("utf-8"))
    for attempt in range(1, 6):
        tmp = STUDIES_JSON + ".tmp%d" % os.getpid()
        try:
            with open(tmp, "w", encoding="utf-8") as f:
                f.write(content)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp, STUDIES_JSON)
            with open(STUDIES_JSON, encoding="utf-8") as f:
                if len(f.read().encode("utf-8")) != expected:
                    raise RuntimeError("write verification failed")
            return True
        except Exception as e:
            print("  studies_baked.json attempt %d/5 failed: %s" % (attempt, e))
            time.sleep(1)
    return False


def main():
    if not TOKEN:
        sys.exit("Set AIRTABLE_TOKEN (read-only PAT scoped to this base).")
    h = open(HTML, encoding="utf-8").read()
    existing_beginner = existing_gap_beginner_fields(h)

    studies = fetch_studies()
    n_pmid = sum(1 for s in studies if s.get("pmid"))
    n_pmcid = sum(1 for s in studies if s.get("pmcid"))
    print("Airtable: %d studies (%d s PMID, %d s PMCID)" % (len(studies), n_pmid, n_pmcid))

    if not write_studies_json(studies):
        sys.exit("ABORT: nepodařilo se zapsat studies_baked.json -- nepokračuji na bake.")
    print("atlas_data/studies_baked.json zapsán")

    js = "const ATLAS_STUDIES = " + json.dumps(studies, ensure_ascii=False) + ";"
    # Ukotveno na následující deklaraci. Callable replacement -- re.sub jinak
    # v řetězci dekóduje zpětná lomítka a rozbije JSON uvnitř abstraktů.
    h, c1 = re.subn(
        r"const ATLAS_STUDIES = \[.*?\];\n\nconst ATLAS_ENTITIES",
        lambda m: js + "\n\nconst ATLAS_ENTITIES",
        h, count=1, flags=re.S,
    )
    if not c1:
        sys.exit("ABORT: ATLAS_STUDIES nenalezen v index.html (pattern mismatch) -- "
                 "nic jsem nezapsal, index.html je beze změny.")
    print("ATLAS_STUDIES: updated (%d records)" % len(studies))

    gjs = gaps_js(existing_beginner)
    if gjs:
        h, c2 = re.subn(r"const ATLAS_GAPS = \[.*?\];", lambda m: gjs, h, count=1, flags=re.S)
        print("ATLAS_GAPS:", "updated" if c2 else "NOT FOUND")

    ts = datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
    h = re.sub(r'ATLAS_UPDATED = "[^"]*"', 'ATLAS_UPDATED = "' + ts + '"', h, count=1)

    try:
        from stamp_updated import refresh_counts
        h = refresh_counts(h)
    except Exception as e:
        print("  refresh_counts skipped: %s" % e)

    write_verified(HTML, h, expect_suffix="</html>")
    print("index.html rewritten and verified (%d bytes, last updated %s)."
          % (len(h.encode("utf-8")), ts))


if __name__ == "__main__":
    main()
