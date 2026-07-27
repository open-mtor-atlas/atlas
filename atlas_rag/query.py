#!/usr/bin/env python3
"""
Atlas RAG - query.py
Retrieval over the local index + assembly of an LLM prompt (4 sections + citations).

Usage:
  python3 query.py "your question" [-k 12]
  python3 query.py "your question" --prompt   # print the ready-made LLM prompt

In production: replace the TF-IDF query embedding / doc matrix with a neural
embedder; the rest of the API stays the same.
"""
import json, pickle, os, argparse, re
import numpy as np
from scipy import sparse

HERE = os.path.dirname(os.path.abspath(__file__))
IDX  = os.path.join(HERE, "index")

_vec=None; _X=None; _meta=None
def _load():
    global _vec,_X,_meta
    if _vec is None:
        _vec=pickle.load(open(os.path.join(IDX,"tfidf_vectorizer.pkl"),"rb"))
        _X=sparse.load_npz(os.path.join(IDX,"doc_matrix.npz"))
        _meta=[json.loads(l) for l in open(os.path.join(IDX,"meta.jsonl"),encoding="utf-8")]
    return _vec,_X,_meta

def search(query, k=12):
    vec,X,meta=_load()
    q=vec.transform([query])              # (1,terms), L2-normalized
    sims=(X @ q.T).toarray().ravel()      # cosine (both L2-normalized)
    order=np.argsort(-sims)[:k]
    out=[]
    for rank,i in enumerate(order,1):
        m=dict(meta[i]); m["_score"]=round(float(sims[i]),4); m["_rank"]=rank
        out.append(m)
    return out

def _cite(m):
    a=(m.get("Authors") or "").split(";")[0].strip()
    y=m.get("Year","") or "?"
    pmid=m.get("PMID","")
    tag=f"PMID:{pmid}" if pmid else (f"DOI:{m.get('DOI')}" if m.get("DOI") else "no-id")
    return f"{a} et al. ({y}) [{tag}]"

def format_hits(hits):
    lines=[]
    for m in hits:
        ft = "full-text" if m.get("fulltext_pmc_available") else "abstract-only"
        lines.append(
            f"[{m['_rank']}] score={m['_score']} | {m.get('Evidence_Tier','?')} | {ft}\n"
            f"    {m.get('Title','')}\n"
            f"    {_cite(m)} | model: {m.get('Model','') or '-'}\n"
            f"    Key finding: {m.get('Key_Finding','').strip()}"
        )
    return "\n".join(lines)

PROMPT_TEMPLATE = """You are Atlas, an mTOR research assistant. Answer the question using ONLY the retrieved studies below. Every claim must cite a study by its [n] number and PMID. Grade each claim by its Evidence_Tier (A=systematic review > B=human > C=animal > D=mechanistic/in-vitro/review). Do not invent facts not in the context.

Return EXACTLY four sections:
1. **Answer** - short, direct answer (2-4 sentences).
2. **Evidence** - how strong is the evidence, by tier; note if it rests mostly on animal/in-vitro (C/D).
3. **Key Papers** - 3-5 most relevant studies, each: citation + one-line why it matters.
4. **Knowledge Gaps** - what is NOT answered by these studies; contradictions; 1-2 testable hypotheses/experiments.

QUESTION:
{question}

RETRIEVED STUDIES:
{context}
"""

def build_prompt(question,k=12):
    hits=search(question,k)
    ctx=[]
    for m in hits:
        ctx.append(
            f"[{m['_rank']}] ({m.get('Evidence_Tier','?')}) {m.get('Title','')} — "
            f"{_cite(m)}; model: {m.get('Model','') or '-'}. "
            f"Abstract: {m.get('Abstract_PubMed','').strip()}"
        )
    return PROMPT_TEMPLATE.format(question=question, context="\n\n".join(ctx)), hits

if __name__=="__main__":
    ap=argparse.ArgumentParser()
    ap.add_argument("question")
    ap.add_argument("-k",type=int,default=12)
    ap.add_argument("--prompt",action="store_true",help="print the ready-made LLM prompt")
    a=ap.parse_args()
    if a.prompt:
        p,_=build_prompt(a.question,a.k); print(p)
    else:
        print(f"QUERY: {a.question}\n"+"="*70)
        print(format_hits(search(a.question,a.k)))
