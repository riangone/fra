"""Unit tests for Hybrid Retriever (BM25 + Vector + RRF)."""

import pytest
from pathlib import Path
from src.retrieval.hybrid_retriever import HybridRetriever, tokenize_japanese_text
from src.retrieval.reranker import compute_rrf_fusion
from src.models.document import Document


def test_tokenize_japanese():
    text = "トヨタ自動車の2024年3月期営業利益は5兆3529億円を達成した"
    tokens = tokenize_japanese_text(text)
    assert len(tokens) > 5
    assert any("5兆3529億円" in t for t in tokens)
    assert any("トヨ" in t or "トヨタ" in t for t in tokens)


def test_rrf_fusion_logic():
    bm25_ranks = ["doc_A", "doc_B", "doc_C"]
    dense_ranks = ["doc_B", "doc_A", "doc_D"]
    scores = compute_rrf_fusion(bm25_ranks, dense_ranks, k=60)
    assert "doc_A" in scores
    assert "doc_B" in scores
    # doc_B is rank 2 in BM25 and rank 1 in Dense, doc_A is rank 1 in BM25 and rank 2 in Dense
    assert scores["doc_A"] == scores["doc_B"]
    assert scores["doc_A"] > scores["doc_C"]


def test_hybrid_retriever_search():
    retriever = HybridRetriever()
    docs = [
        Document(
            id="doc_1",
            title="トヨタ決算速報",
            ticker="7203",
            company_name="トヨタ自動車",
            source="日経",
            date="2024-05-08",
            category="決算",
            content="トヨタ自動車の営業利益が5兆3529億円を記録しました。",
        ),
        Document(
            id="doc_2",
            title="ソニー半導体",
            ticker="6758",
            company_name="ソニーグループ",
            source="日経",
            date="2024-05-14",
            category="決算",
            content="ソニーのイメージセンサー事業が好調で増益に寄与しました。",
        ),
    ]
    retriever.index_documents(docs)

    results = retriever.search("トヨタの5兆円営業利益", top_k=2)
    assert len(results) == 2
    assert results[0].id == "doc_1"
    assert results[0].rrf_score > 0
