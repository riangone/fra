"""Unit tests for Hybrid Retriever (BM25 + Vector + RRF)."""

import json
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


def test_load_merged_corpus_combines_sample_and_edinet_files(tmp_path):
    """get_shared_retriever's merge helper should combine
    sample_articles.json with an optional edinet_articles.json (Tier 1
    EDINET-sourced expansion), deduping by id with the later file winning.
    """
    from src.graph.nodes.hybrid_search import _load_merged_corpus

    sample = [
        {
            "id": "doc_a",
            "title": "Sample A",
            "ticker": "1111",
            "company_name": "Sample Co",
            "source": "test",
            "date": "2024-01-01",
            "category": "test",
            "content": "sample content",
        }
    ]
    edinet = [
        {
            "id": "doc_edinet_9999_S100X",
            "title": "EDINET Filing",
            "ticker": "9999",
            "company_name": "EDINET Co",
            "source": "EDINET（金融庁）",
            "date": "2024-06-27",
            "category": "有価証券報告書",
            "content": "edinet content",
        }
    ]
    (tmp_path / "sample_articles.json").write_text(json.dumps(sample, ensure_ascii=False), encoding="utf-8")
    (tmp_path / "edinet_articles.json").write_text(json.dumps(edinet, ensure_ascii=False), encoding="utf-8")

    merged = _load_merged_corpus(tmp_path)

    assert set(merged.keys()) == {"doc_a", "doc_edinet_9999_S100X"}
    assert merged["doc_edinet_9999_S100X"].company_name == "EDINET Co"


def test_load_merged_corpus_missing_edinet_file_is_fine(tmp_path):
    """edinet_articles.json is optional -- its absence must not break loading."""
    from src.graph.nodes.hybrid_search import _load_merged_corpus

    sample = [
        {
            "id": "doc_a",
            "title": "Sample A",
            "ticker": "1111",
            "company_name": "Sample Co",
            "source": "test",
            "date": "2024-01-01",
            "category": "test",
            "content": "sample content",
        }
    ]
    (tmp_path / "sample_articles.json").write_text(json.dumps(sample, ensure_ascii=False), encoding="utf-8")

    merged = _load_merged_corpus(tmp_path)

    assert set(merged.keys()) == {"doc_a"}
