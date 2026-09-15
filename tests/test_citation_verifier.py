"""Unit tests for Citation Extraction and Attribution Consistency Verifier."""

import pytest
from src.citation.extractor import split_sentences_japanese, extract_citation_tags
from src.citation.verifier import CitationConsistencyVerifier


def test_split_sentences():
    text = "第一文です。第二文はこれです！第三文はどうでしょう？最後の文。"
    sentences = split_sentences_japanese(text)
    assert len(sentences) == 4
    assert sentences[0] == "第一文です。"
    assert sentences[1] == "第二文はこれです！"


def test_extract_citation_tags():
    sentence = "トヨタの営業利益は5兆円を超えた [doc_7203] [mcp_val_7203]。"
    cleaned, tags = extract_citation_tags(sentence)
    assert "doc_7203" in tags
    assert "mcp_val_7203" in tags
    assert "[" not in cleaned


def test_citation_verifier_valid():
    verifier = CitationConsistencyVerifier()
    chunks = [{
        "id": "chunk_01",
        "title": "トヨタ決算",
        "content": "トヨタ自動車の2024年3月期通期営業利益は5兆3529億円となりました。",
    }]
    metrics = []
    text = "トヨタ自動車の通期営業利益は5兆3529億円となりました [chunk_01]。"

    report = verifier.audit_text(text, chunks, metrics)
    assert report.verdict == "PASS"
    assert report.attribution_consistency_rate == 1.0
    assert report.verified_citations == 1


def test_citation_verifier_hallucination():
    verifier = CitationConsistencyVerifier()
    chunks = [{
        "id": "chunk_01",
        "title": "トヨタ決算",
        "content": "トヨタ自動車の2024年3月期通期営業利益は5兆3529億円となりました。",
    }]
    metrics = []
    # False claim: 99兆円 is not in chunk
    text = "トヨタ自動車の営業利益は99兆円を突破しました [chunk_01]。"

    report = verifier.audit_text(text, chunks, metrics)
    assert report.attribution_consistency_rate < 0.5
    assert report.unverified_citations >= 1
    assert report.markers[0].is_hallucination is True
