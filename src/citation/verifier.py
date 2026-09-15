"""Sentence-level Citation Attribution and Consistency Verification Engine (引用一致率監査エンジン)."""

import re
from typing import List, Dict, Any, Set
from src.models.document import CitationMarker, CitationAuditReport
from src.citation.extractor import split_sentences_japanese, extract_citation_tags
from src.retrieval.hybrid_retriever import tokenize_japanese_text


def extract_factual_entities(sentence: str) -> Set[str]:
    """Extract key factual tokens: financial figures, percentages, dates, and technical keywords."""
    facts = set()

    # Financial figures with units (e.g., 5兆3529億円, 2兆円, 150円, 0.25%, 350万台, 1.0倍)
    figures = re.findall(r"\d+(?:\.\d+)?(?:兆|億|万)?(?:円|台|%|倍)?", sentence)
    for fig in figures:
        if len(fig) > 1 or fig.isdigit():
            facts.add(fig)

    # Kanji words / technical terms (length >= 2)
    kanji_words = re.findall(r"[\u4e00-\u9fff]{2,}", sentence)
    facts.update(kanji_words)

    # Katakana terms (length >= 3)
    katakana_words = re.findall(r"[\u30a0-\u30ff]{3,}", sentence)
    facts.update(katakana_words)

    return facts


class CitationConsistencyVerifier:
    """
    Audits the generated response sentence-by-sentence against retrieved source chunks
    and financial metrics to ensure strict grounding, eliminate hallucinations,
    and measure Citation Consistency Rate (引用一致率).
    """

    def __init__(self, min_confidence_threshold: float = 0.65):
        self.min_confidence_threshold = min_confidence_threshold

    def audit_text(
        self,
        text: str,
        retrieved_chunks: List[Dict[str, Any]],
        financial_metrics: List[Dict[str, Any]],
    ) -> CitationAuditReport:
        # Build chunk lookup index
        chunk_map = {c["id"]: c for c in retrieved_chunks}

        # Also register financial metrics as virtual chunks for validation
        for fm in financial_metrics:
            ticker = fm.get("ticker", "")
            comp = fm.get("company_name", "")
            if "per" in fm and "pbr" in fm:
                chunk_map[f"mcp_val_{ticker}"] = {
                    "id": f"mcp_val_{ticker}",
                    "title": f"{comp} 財務指標・バリュエーション (PER/PBR/ROE/TSR)",
                    "content": f"{comp}（{ticker}）予想PER: {fm.get('per')}倍、PBR: {fm.get('pbr')}倍、ROE（自己資本利益率）: {fm.get('roe_percent')}%、TSR（株主総利回り）: {fm.get('tsr_percent')}%、評価ステータス: {fm.get('valuation_status')}",
                }
            if "revenue_billion_jpy" in fm:
                chunk_map[f"mcp_disc_{ticker}"] = {
                    "id": f"mcp_disc_{ticker}",
                    "title": f"{comp} 決算開示情報",
                    "content": f"{comp}（{ticker}）売上高: {fm.get('revenue_billion_jpy')}億円、営業利益: {fm.get('operating_income_billion_jpy')}億円、純利益: {fm.get('net_income_billion_jpy')}億円、開示修正: {fm.get('guidance_revision')}",
                }

        raw_sentences = split_sentences_japanese(text)
        markers: List[CitationMarker] = []

        total_sentences = len(raw_sentences)
        cited_sentences = 0
        verified_citations = 0
        unverified_citations = 0

        for idx, s in enumerate(raw_sentences):
            cleaned_s, cited_ids = extract_citation_tags(s)
            if not cleaned_s:
                continue

            facts = extract_factual_entities(cleaned_s)
            
            # Check if this sentence contains claims that require citations
            needs_citation = len(facts) >= 2 or any(char.isdigit() for char in cleaned_s)

            if cited_ids:
                cited_sentences += 1
                supported_ids = []
                evidence_snippets = []
                hallucinated = False

                for cid in cited_ids:
                    chunk = chunk_map.get(cid)
                    if not chunk:
                        hallucinated = True
                        continue

                    chunk_content = chunk.get("content", "") + " " + chunk.get("title", "")
                    
                    # Verify overlap of factual entities
                    matched_facts = [f for f in facts if f in chunk_content]
                    
                    # Also compute token overlap
                    sentence_tokens = set(tokenize_japanese_text(cleaned_s))
                    chunk_tokens = set(tokenize_japanese_text(chunk_content))
                    overlap_ratio = len(sentence_tokens & chunk_tokens) / max(1, len(sentence_tokens))

                    # Number verification: if sentence contains numbers, at least one must be in chunk
                    sentence_numbers = re.findall(r"\d+(?:\.\d+)?", cleaned_s)
                    number_verified = True
                    if sentence_numbers:
                        number_verified = any(num in chunk_content for num in sentence_numbers)

                    if (overlap_ratio >= 0.25 or len(matched_facts) >= 1) and number_verified:
                        supported_ids.append(cid)
                        # Extract evidence snippet
                        evidence_snippets.append(chunk_content[:120] + "...")
                    else:
                        hallucinated = True

                confidence = len(supported_ids) / len(cited_ids) if cited_ids else 0.0

                if confidence >= self.min_confidence_threshold and not hallucinated:
                    verified_citations += 1
                else:
                    unverified_citations += 1

                markers.append(
                    CitationMarker(
                        sentence_idx=idx,
                        sentence_text=s,
                        cited_chunk_ids=cited_ids,
                        supporting_chunk_ids=supported_ids,
                        confidence=confidence,
                        is_hallucination=hallucinated,
                        evidence_snippets=evidence_snippets,
                    )
                )
            else:
                # Sentence has no citation tags
                if needs_citation:
                    # Check if there is an uncredited matching chunk
                    matching_chunks = []
                    for cid, chunk in chunk_map.items():
                        chunk_content = chunk.get("content", "")
                        matched_facts = [f for f in facts if f in chunk_content]
                        if len(matched_facts) >= 2:
                            matching_chunks.append(cid)

                    markers.append(
                        CitationMarker(
                            sentence_idx=idx,
                            sentence_text=s,
                            cited_chunk_ids=[],
                            supporting_chunk_ids=matching_chunks,
                            confidence=0.0,
                            is_hallucination=False,
                            evidence_snippets=[],
                        )
                    )

        precision = (verified_citations / cited_sentences) if cited_sentences > 0 else 1.0
        # Recall: verified citations out of total factual sentences
        factual_sentences_count = max(1, sum(1 for m in markers if len(m.cited_chunk_ids) > 0 or len(m.supporting_chunk_ids) > 0))
        recall = verified_citations / factual_sentences_count

        consistency_rate = (verified_citations / cited_sentences) if cited_sentences > 0 else 0.0

        verdict = "PASS"
        if consistency_rate < 0.7 or unverified_citations > 1:
            verdict = "REVISE"
        if consistency_rate < 0.4:
            verdict = "FAIL"

        return CitationAuditReport(
            total_sentences=total_sentences,
            cited_sentences=cited_sentences,
            verified_citations=verified_citations,
            unverified_citations=unverified_citations,
            citation_precision=round(precision, 3),
            citation_recall=round(recall, 3),
            attribution_consistency_rate=round(consistency_rate, 3),
            markers=markers,
            verdict=verdict,
        )
