#!/usr/bin/env python3
"""
extract_facts.py -- Phase 4, Step 4 at scale: deep fact-extraction from full text.

For each target study it: fetches the full text, sends it to a free LLM (Gemini) with a
strict JSON prompt, and writes AI_Dose / AI_SampleSize / AI_EffectSize / AI_Limitations /
AI_FullText_Extracted to Airtable. Only DERIVED FACTS are stored; the article text is
discarded, so this path is fine for all full-text studies regardless of license.

Default target: tier-C animal studies with full text (the 40). Change TIERS to widen.

Setup (both free-tier friendly):
    export AIRTABLE_TOKEN=patXXXX        # write scope on this base
    export GEMINI_API_KEY=...            # https://aistudio.google.com/apikey
    # optional: export GEMINI_MODEL=gemini-2.0-flash   (else a current model is auto-picked)
Run:
    python3 atlas_gaps/extract_facts.py --limit 3   # try a few first
    python3 atlas_gaps/extract_facts.py             # then the rest
Resumable via extract_manifest.csv. Standard library only.
"""
import os, sys, csv, json, time, urllib.request, urllib.parse, urllib.error
import xml.etree.ElementTree as ET

HERE  = os.path.dirname(os.path.abspath(__file__))
SRC   = os.path.join(HERE, "..", "atlas_data", "studies_enriched.jsonl")
MANIF = os.path.join(HERE, "extract_manifest.csv")
BASE, TABLE = "appt2U6ObDHUcRlrj", "Studies"
TIERS = ("C",)                     # which evidence tiers to deep-extract (widen if desired)
MODEL = os.environ.get("GEMINI_MODEL", "")   # optional manual override; else auto-discovered
MODEL_FALLBACK = "gemini-2.0-flash"
MAXCHARS = 14000                   # truncate full text sent to the LLM

AIR = os.environ.get("AIRTABLE_TOKEN")
GEM = os.environ.get("GEMINI_API_KEY")
EPMC = "https://www.ebi.ac.uk/europepmc/webservices/rest/{}/fullTextXML"
NCBI = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi?db=pmc&id={}&rettype=xml&retmode=xml&tool=OpenMTORAtlas"

def _get(url, data=None, headers=None, timeout=90):
    req = urllib.request.Request(url, data=data, headers=headers or {}, method="POST" if data else "GET")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"HTTP {e.code}: {e.read().decode('utf-8','replace')[:300]}")

def fetch_text(pmcid):
    for url in (EPMC.format(pmcid), NCBI.format(pmcid.replace("PMC", ""))):
        try:
            x = _get(url, headers={"User-Agent": "OpenMTORAtlas/1.0"})
            if "<body" in x or "<sec" in x:
                body = ET.fromstring(x).find(".//{*}body")
                if body is not None:
                    txt = " ".join(t.strip() for t in body.itertext() if t.strip())
                    if len(txt) > 400:
                        return txt[:MAXCHARS]
        except Exception:
            pass
        time.sleep(0.5)
    return None

PROMPT = """You are extracting structured facts from a biomedical full-text article. Return ONLY a JSON object with these keys:
  "dose"        : intervention dose / schedule / route (quantitative), or "not stated"
  "sample_size" : n / cohort / groups, or "not stated"
  "effect_size" : main quantitative result with magnitude and statistics (%, p, CI), or "not stated"
  "limitations" : stated limitations / caveats, or "not stated"
Be concise (one line each), faithful to the text, and prefer numbers. Do not add other keys or prose.

TITLE: {title}
MODEL: {model}
FULL TEXT (truncated):
{text}
"""

def pick_model():
    """Find a current model that supports generateContent (avoids hard-coded, renamed models)."""
    global MODEL
    if MODEL:
        return MODEL
    try:
        out = _get(f"https://generativelanguage.googleapis.com/v1beta/models?key={GEM}")
        avail = [m["name"].split("/")[-1] for m in json.loads(out).get("models", [])
                 if "generateContent" in m.get("supportedGenerationMethods", [])]
        flash = [m for m in avail if "flash" in m and "exp" not in m and "thinking" not in m]
        MODEL = (flash or avail or [MODEL_FALLBACK])[0]
    except Exception:
        MODEL = MODEL_FALLBACK
    return MODEL

def llm_extract(title, model, text):
    body = json.dumps({"contents": [{"parts": [{"text": PROMPT.format(title=title, model=model, text=text)}]}],
                       "generationConfig": {"temperature": 0, "responseMimeType": "application/json"}}).encode()
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{pick_model()}:generateContent?key={GEM}"
    out = _get(url, data=body, headers={"Content-Type": "application/json"})
    txt = json.loads(out)["candidates"][0]["content"]["parts"][0]["text"]
    return json.loads(txt)

def airtable_patch(rec_id, fields):
    url = f"https://api.airtable.com/v0/{BASE}/{urllib.parse.quote(TABLE)}/{rec_id}"
    req = urllib.request.Request(url, data=json.dumps({"fields": fields}).encode(), method="PATCH",
                                 headers={"Authorization": f"Bearer {AIR}", "Content-Type": "application/json"})
    urllib.request.urlopen(req, timeout=30)

def main():
    if not (AIR and GEM):
        sys.exit("Set AIRTABLE_TOKEN and GEMINI_API_KEY.")
    limit = int(sys.argv[sys.argv.index("--limit")+1]) if "--limit" in sys.argv else None
    print(f"[extract] using Gemini model: {pick_model()}")

    recs = [json.loads(l) for l in open(SRC, encoding="utf-8")]
    targets = [r for r in recs if r.get("fulltext_pmc_available") and r.get("PMCID")
               and (r.get("Evidence_Tier") or "?")[0] in TIERS]
    done = set()
    if os.path.exists(MANIF):
        done = {row["sid"] for row in csv.DictReader(open(MANIF)) if row.get("status") == "ok"}
    todo = [r for r in targets if r["Study_ID"] not in done]
    if limit:
        todo = todo[:limit]
    print(f"[extract] {len(targets)} tier-{'/'.join(TIERS)} full-text studies | {len(done)} done | {len(todo)} to do")

    man = list(csv.reader(open(MANIF))) if os.path.exists(MANIF) else [["sid", "status", "note"]]
    for r in todo:
        sid, pmcid = r["Study_ID"], r["PMCID"]
        text = fetch_text(pmcid)
        if not text:
            man.append([sid, "no-fulltext", ""]); print(f"  {sid}: no full text"); continue
        try:
            f = llm_extract(r["Title"], r.get("Model", ""), text)
            airtable_patch(r["airtable_id"], {
                "AI_Dose": f.get("dose", ""), "AI_SampleSize": f.get("sample_size", ""),
                "AI_EffectSize": f.get("effect_size", ""), "AI_Limitations": f.get("limitations", ""),
                "AI_FullText_Extracted": True})
            man.append([sid, "ok", ""]); print(f"  {sid}: extracted -> Airtable")
        except Exception as e:
            man.append([sid, "error", str(e)[:120]]); print(f"  {sid}: ERROR {e}")
        time.sleep(1.5)

    with open(MANIF, "w", newline="", encoding="utf-8") as fh:
        csv.writer(fh).writerows(man)
    ok = sum(1 for row in man[1:] if row[1] == "ok")
    print(f"\n[extract] total ok: {ok} -> Airtable AI_* fields (re-run to continue)")

if __name__ == "__main__":
    main()
