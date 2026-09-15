"""Hybrid Retriever combining BM25 Keyword Search and Dense Vector Search via RRF."""

import json
import re
from pathlib import Path
from typing import List, Dict, Any, Optional
import numpy as np
from rank_bm25 import BM25Okapi

from src.models.document import Document, RetrievedChunk
from src.retrieval.embeddings import get_embedder, BaseEmbedder
from src.retrieval.reranker import compute_rrf_fusion
from config.settings import settings


def tokenize_japanese_text(text: str) -> List[str]:
    """
    Robust tokenizer for Japanese and alphanumeric financial text.
    Combines alphanumeric tokens, kanji/hiragana/katakana bi-grams, and numbers with units.
    Does not require external C++ dictionary dependencies like MeCab.
    """
    text_clean = text.lower().strip()
    tokens = []

    # 1. Alphanumeric / English words / Tickers
    words = re.findall(r"[a-z0-9]+", text_clean)
    tokens.extend(words)

    # 2. Financial numbers with units and composite expressions (e.g., 5兆3529億円, 2兆円, 150円, 0.25%, 350万台)
    num_units = re.findall(r"\d+(?:[兆億万円台%倍]|\d)*(?:\.\d+)?(?:[兆億万円台%倍])?", text_clean)
    tokens.extend([n for n in num_units if len(n) > 0])

    # 3. Japanese character bi-grams (2-grams) for robust substring matching
    cjk_chars = [c for c in text_clean if '\u3040' <= c <= '\u9fff']
    for i in range(len(cjk_chars) - 1):
        tokens.append(cjk_chars[i] + cjk_chars[i + 1])
    # Single kanji tokens
    for c in cjk_chars:
        if '\u4e00' <= c <= '\u9fff':  # Kanji
            tokens.append(c)

    return tokens if tokens else [text_clean]


class HybridRetriever:
    """
    Production-grade Hybrid Retriever:
    1. Sparse index: BM25 Okapi with CJK bi-gram tokenization
    2. Dense index: Cosine similarity over normalized embeddings
    3. Fusion: Reciprocal Rank Fusion (RRF)
    """

    def __init__(self, embedder: Optional[BaseEmbedder] = None):
        self.embedder = embedder or get_embedder()
        self.documents: Dict[str, Document] = {}
        self.doc_ids: List[str] = []
        self.bm25_index: Optional[BM25Okapi] = None
        self.dense_vectors: Optional[np.ndarray] = None

    def load_documents_from_file(self, file_path: Path):
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        docs = [Document(**item) for item in data]
        self.index_documents(docs)

    def index_documents(self, docs: List[Document]):
        self.documents = {d.id: d for d in docs}
        self.doc_ids = [d.id for d in docs]

        # 1. Build BM25 Index
        corpus = [f"{d.title} {d.company_name or ''} {d.content}" for d in docs]
        tokenized_corpus = [tokenize_japanese_text(text) for text in corpus]
        self.bm25_index = BM25Okapi(tokenized_corpus)

        # 2. Build Dense Vectors
        vectors = [self.embedder.embed_text(text) for text in corpus]
        self.dense_vectors = np.array(vectors, dtype=np.float32)

    def search(
        self,
        query: str,
        top_k: int = 5,
        filter_ticker: Optional[str] = None,
        rrf_k: int = 60,
    ) -> List[RetrievedChunk]:
        if not self.documents or not self.doc_ids:
            return []

        # Step 1: BM25 Search
        query_tokens = tokenize_japanese_text(query)
        bm25_scores = self.bm25_index.get_scores(query_tokens)
        bm25_ranked_indices = np.argsort(-bm25_scores)
        bm25_ranked_ids = [self.doc_ids[idx] for idx in bm25_ranked_indices]

        # Step 2: Dense Vector Search (Cosine Similarity)
        query_vec = np.array(self.embedder.embed_text(query), dtype=np.float32)
        dense_scores = np.dot(self.dense_vectors, query_vec)
        dense_ranked_indices = np.argsort(-dense_scores)
        dense_ranked_ids = [self.doc_ids[idx] for idx in dense_ranked_indices]

        # Step 3: Reciprocal Rank Fusion (RRF)
        rrf_scores = compute_rrf_fusion(
            bm25_ranked_ids=bm25_ranked_ids,
            dense_ranked_ids=dense_ranked_ids,
            k=rrf_k,
            bm25_weight=settings.hybrid_bm25_weight,
            dense_weight=settings.hybrid_vector_weight,
        )

        # Rank all documents by RRF score
        sorted_doc_ids = sorted(self.doc_ids, key=lambda did: rrf_scores.get(did, 0.0), reverse=True)

        # Filter by ticker if specified
        if filter_ticker:
            sorted_doc_ids = [
                did for did in sorted_doc_ids
                if self.documents[did].ticker == filter_ticker or filter_ticker in self.documents[did].content
            ]

        # Map to RetrievedChunk
        results = []
        for rank, did in enumerate(sorted_doc_ids[:top_k], start=1):
            doc = self.documents[did]
            idx = self.doc_ids.index(did)
            results.append(
                RetrievedChunk(
                    id=doc.id,
                    title=doc.title,
                    ticker=doc.ticker,
                    company_name=doc.company_name,
                    source=doc.source,
                    content=doc.content,
                    bm25_score=float(bm25_scores[idx]),
                    dense_score=float(dense_scores[idx]),
                    rrf_score=float(rrf_scores.get(did, 0.0)),
                    rank=rank,
                )
            )

        return results
