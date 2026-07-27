#!/usr/bin/env python3
"""
build_chunk_index.py -- build a compact client-side search index over the stored
full-text passages, for the web page's "Deep search".

Reads the raw full text in raw/ (CC-licensed studies only, already gated by
fetch_fulltext.py), chunks it, and writes chunk_index.json:
    { "idf": {term: idf}, "chunks": [ {sid, section, text, w:{term:weight}} ] }
The page loads this on demand and does TF-IDF cosine retrieval in the browser.

Run after fetch_fulltext.py:
    python3 atlas_fulltext/build_chunk_index.py
Standard library only.
"""
import os, re, json, glob, math
import xml.etree.ElementTree as ET

HERE = os.path.dirname(os.path.abspath(__file__))
RAW  = os.path.join(HERE, "raw")
OUT  = os.path.join(HERE, "chunk_index.json")
WORDS, OVERLAP, TOPTERMS = 240, 40, 45

_STOP = set("the a an and or of to in for on with without into within is are was were be been by as at from that this these those we our it its their they can could may might also than then thus here show shows showed found finds not no yes but which who whom via using use used both between each other more most less have has had".split())
def tok(s): return [w for w in re.sub(r"[^a-z0-9\s-]", " ", (s or "").lower()).split() if len(w) >= 3 and w not in _STOP]

HEAD = re.compile(r"\b(Introduction|Results|Discussion|Materials and [Mm]ethods|Methods|Conclusions?|Abstract)\b")
def sections_txt(t):
    idx = [m.start() for m in HEAD.finditer(t)]
    if not idx: return [("Body", t)]
    idx = [0] + idx + [len(t)]; out = []
    for a, b in zip(idx, idx[1:]):
        seg = t[a:b].strip()
        if len(seg.split()) < 20: continue
        m = HEAD.search(seg[:40]); out.append((m.group(1) if m else "Body", seg))
    return out or [("Body", t)]

def sections_xml(xml):
    try: body = ET.fromstring(xml).find(".//{*}body")
    except Exception: return []
    if body is None: return []
    secs = body.findall("{*}sec")
    if not secs:
        return [("Body", " ".join(t.strip() for t in body.itertext() if t.strip()))]
    out = []
    for sec in secs:
        te = sec.find("{*}title"); title = (te.text or "").strip() if te is not None else "Section"
        txt = " ".join(t.strip() for t in sec.itertext() if t.strip())
        if title and txt.startswith(title): txt = txt[len(title):].strip()
        if txt: out.append((title[:50] or "Section", txt))
    return out

def chunkw(t):
    w = t.split(); i = 0
    while i < len(w):
        yield " ".join(w[i:i+WORDS]); i += WORDS - OVERLAP

def main():
    chunks = []   # (sid, section, text, tokens)
    for fp in sorted(glob.glob(os.path.join(RAW, "*"))):
        sid = os.path.basename(fp).split("_")[0]
        raw = open(fp, encoding="utf-8", errors="replace").read()
        secs = sections_xml(raw) if fp.endswith(".xml") else sections_txt(raw)
        for title, seg in secs:
            for ch in chunkw(seg):
                t = tok(ch)
                if len(t) >= 20:
                    chunks.append((sid, title, ch, t))
    N = len(chunks)
    print(f"[index] {N} chunks from {len(set(c[0] for c in chunks))} studies")

    df = {}
    for _, _, _, t in chunks:
        for w in set(t): df[w] = df.get(w, 0) + 1
    idf = {w: round(math.log((N+1)/(d+1)) + 1, 4) for w, d in df.items() if d >= 2}

    out_chunks = []
    for sid, section, text, t in chunks:
        tf = {}
        for w in t:
            if w in idf: tf[w] = tf.get(w, 0) + 1
        vec = {w: (1 + math.log(c)) * idf[w] for w, c in tf.items()}
        norm = math.sqrt(sum(v*v for v in vec.values())) or 1.0
        vec = {w: round(v/norm, 4) for w, v in vec.items()}
        top = dict(sorted(vec.items(), key=lambda kv: -kv[1])[:TOPTERMS])
        out_chunks.append({"sid": sid, "section": section, "text": text, "w": top})

    json.dump({"idf": idf, "chunks": out_chunks}, open(OUT, "w", encoding="utf-8"), ensure_ascii=False)
    print(f"[index] wrote {OUT} ({os.path.getsize(OUT)//1024} KB, {len(idf)} terms)")

if __name__ == "__main__":
    main()
