#!/usr/bin/env python3
"""
Atlas RAG - build_index.py
Builds a local vector index from the corpus of studies (free, offline).

Input:  studies_enriched.jsonl  (from Phase 0)
Output: index/  (tfidf_vectorizer.pkl, doc_matrix.npz, meta.jsonl)

Retrieval is TF-IDF cosine. The interface is deliberately decoupled, so in
production you only replace the embed step with a neural model
(sentence-transformers) or an API (Voyage/OpenAI/Gemini) - the rest of the
pipeline stays the same.
"""
import json, pickle, sys, os
import numpy as np
from scipy import sparse  # ships with sklearn
from sklearn.feature_extraction.text import TfidfVectorizer

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "studies_enriched.jsonl")
IDX  = os.path.join(HERE, "index")

def load_docs(path):
    docs=[]
    for line in open(path, encoding="utf-8"):
        line=line.strip()
        if line: docs.append(json.loads(line))
    return docs

def main():
    docs = load_docs(DATA)
    texts = [d.get("embedding_text") or d.get("Title","") for d in docs]
    print(f"[build] loaded {len(docs)} studies")

    vec = TfidfVectorizer(
        lowercase=True, stop_words="english",
        ngram_range=(1,2), sublinear_tf=True,
        min_df=1, max_df=0.9, max_features=50000,
    )
    X = vec.fit_transform(texts)   # (n_docs, n_terms), L2-normalized by default
    print(f"[build] TF-IDF matrix: {X.shape[0]} x {X.shape[1]}")

    os.makedirs(IDX, exist_ok=True)
    with open(os.path.join(IDX,"tfidf_vectorizer.pkl"),"wb") as f:
        pickle.dump(vec, f)
    sparse.save_npz(os.path.join(IDX,"doc_matrix.npz"), X)

    # metadata (drop the long embedding_text to keep the file small; keep abstract)
    keep = ["airtable_id","Study_ID","Title","Authors","Year","Journal","Category",
            "Model","Related_Entities","Evidence_Tier","Pyramid_Level","Peer_Reviewed",
            "DOI","PMID","PMCID","fulltext_pmc_available","Abstract_PubMed","Key_Finding"]
    with open(os.path.join(IDX,"meta.jsonl"),"w",encoding="utf-8") as f:
        for d in docs:
            f.write(json.dumps({k:d.get(k,"") for k in keep}, ensure_ascii=False)+"\n")
    print(f"[build] done -> {IDX}")

if __name__=="__main__":
    main()
