#!/usr/bin/env python3
"""
fetch_fulltext.py -- Phase 4, Steps 2-3: fetch open-access full text and chunk it,
for the CC-licensed (Chunkable) studies ONLY.

LICENSE GUARD: only studies whose license is CC and NOT No-Derivatives are stored.
Text for non-open studies is NEVER written here (they use the fact-extraction path).

RESUMABLE: re-running only retries studies that aren't already "ok" in manifest.csv,
and appends to chunks.jsonl. Use --force to rebuild from scratch, --limit N to try a few.

Full-text source: Europe PMC JATS XML, with an NCBI E-utilities (PMC) fallback.
Input:  ../atlas_gaps/licenses.csv     Output: raw/<sid>_<PMCID>.xml, chunks.jsonl, manifest.csv
Standard library only.
"""
import os, sys, csv, json, time, urllib.request
import xml.etree.ElementTree as ET

HERE   = os.path.dirname(os.path.abspath(__file__))
CSV    = os.path.join(HERE, "..", "atlas_gaps", "licenses.csv")
RAW    = os.path.join(HERE, "raw")
CHUNKS = os.path.join(HERE, "chunks.jsonl")
MANIF  = os.path.join(HERE, "manifest.csv")
EPMC   = "https://www.ebi.ac.uk/europepmc/webservices/rest/{}/fullTextXML"
NCBI   = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi?db=pmc&id={}&rettype=xml&retmode=xml&tool=OpenMTORAtlas"
FIELDS = ["sid","pmcid","license","sections","chunks","status"]

CC_OK = lambda lic: lic.startswith("cc") and "nd" not in lic
WORDS_PER_CHUNK, OVERLAP = 240, 40

def guard(row): return CC_OK(row.get("license", "").lower())

def _get(url):
    req = urllib.request.Request(url, headers={"User-Agent": "OpenMTORAtlas/1.0"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read().decode("utf-8", "replace")

def fetch_fulltext_xml(pmcid):
    """Try Europe PMC JATS, then NCBI PMC efetch. Return XML string with a <body>, or None."""
    for url in (EPMC.format(pmcid), NCBI.format(pmcid.replace("PMC", ""))):
        try:
            x = _get(url)
            if "<body" in x or "<sec" in x:
                return x
        except Exception:
            pass
        time.sleep(0.5)
    return None

def sections_from_jats(xml):
    try:
        root = ET.fromstring(xml)
    except ET.ParseError:
        return []
    body = root.find(".//{*}body")
    if body is None:
        return []
    secs = body.findall("{*}sec")
    if not secs:
        txt = " ".join(t.strip() for t in body.itertext() if t.strip())
        return [("Body", txt)] if txt else []
    out = []
    for sec in secs:
        te = sec.find("{*}title")
        title = (te.text or "").strip() if te is not None else "Section"
        txt = " ".join(t.strip() for t in sec.itertext() if t.strip())
        if title and txt.startswith(title):
            txt = txt[len(title):].strip()
        if txt:
            out.append((title[:60] or "Section", txt))
    return out

def chunk_words(text, size=WORDS_PER_CHUNK, overlap=OVERLAP):
    w = text.split(); i = 0
    while i < len(w):
        yield " ".join(w[i:i+size]); i += size - overlap

def main():
    force = "--force" in sys.argv
    limit = int(sys.argv[sys.argv.index("--limit")+1]) if "--limit" in sys.argv else None

    rows = [r for r in csv.DictReader(open(CSV, encoding="utf-8")) if guard(r)]
    if limit: rows = rows[:limit]

    man = {}
    if os.path.exists(MANIF) and not force:
        for r in csv.DictReader(open(MANIF, encoding="utf-8")):
            man[r["sid"]] = r
    done_ok = {sid for sid, r in man.items() if r.get("status") == "ok"}

    os.makedirs(RAW, exist_ok=True)
    if force or not os.path.exists(CHUNKS):
        open(CHUNKS, "w").close()

    todo = [r for r in rows if r["sid"] not in done_ok]
    print(f"[fulltext] {len(rows)} eligible | {len(done_ok)} already ok | {len(todo)} to fetch")

    for row in todo:
        sid, pmcid, lic = row["sid"], row["PMCID"], row["license"].lower()
        if not CC_OK(lic):
            print(f"  REFUSED {sid} ({lic})"); continue
        if not pmcid:
            man[sid] = dict(sid=sid, pmcid="", license=lic, sections=0, chunks=0, status="no-pmcid"); continue
        xml = fetch_fulltext_xml(pmcid)
        if not xml:
            man[sid] = dict(sid=sid, pmcid=pmcid, license=lic, sections=0, chunks=0, status="no-fulltext")
            print(f"  {sid}: no full-text XML (Europe PMC + NCBI)"); time.sleep(1); continue
        secs = sections_from_jats(xml)
        if not secs:
            man[sid] = dict(sid=sid, pmcid=pmcid, license=lic, sections=0, chunks=0, status="no-xml-body")
            time.sleep(1); continue
        with open(os.path.join(RAW, f"{sid}_{pmcid}.xml"), "w", encoding="utf-8") as f:
            f.write(xml)
        n = 0
        with open(CHUNKS, "a", encoding="utf-8") as f:
            for st, stext in secs:
                for j, ch in enumerate(chunk_words(stext)):
                    if len(ch.split()) < 20:
                        continue
                    f.write(json.dumps({"sid": sid, "airtable_id": row["airtable_id"], "pmcid": pmcid,
                                        "license": lic, "section": st,
                                        "chunk_id": f"{sid}:{st[:20]}:{j}", "text": ch}, ensure_ascii=False) + "\n")
                    n += 1
        man[sid] = dict(sid=sid, pmcid=pmcid, license=lic, sections=len(secs), chunks=n, status="ok")
        print(f"  {sid}: {len(secs)} sections -> {n} chunks"); time.sleep(1)

    with open(MANIF, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS); w.writeheader()
        for sid in sorted(man):
            w.writerow({k: man[sid].get(k, "") for k in FIELDS})
    ok = sum(1 for r in man.values() if r.get("status") == "ok")
    print(f"\n[fulltext] total stored: {ok}/{len(rows)} | chunks -> {CHUNKS}")
    print("  re-run to retry failures; --force to rebuild from scratch.")

if __name__ == "__main__":
    main()
