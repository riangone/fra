"""Sentence-level Citation Extraction and Parsing."""

import re
from typing import List, Tuple

# Maps a substring found in a live macro indicator's `indicator` label to a
# stable citation-id slug. Used by the synthesizer (to tag the sentence) and
# the citation verifier (to register the matching virtual chunk) so macro
# citations point at the *live* MCP value, never at a static news article
# (previously all three macro indicators were hardcoded to cite
# `doc_nikkei_boj_01`, a real 2024-07-31 Nikkei article indexed in
# data/sample_articles.json, which silently routed "Live" macro cards to
# stale 2024 evidence when clicked).
_MACRO_INDICATOR_SLUGS = (
    ("日銀政策金利", "boj_rate"),
    ("日経平均", "nikkei225"),
    ("USD/JPY", "usdjpy"),
)


def macro_citation_id(indicator: str) -> str:
    """Derives a `mcp_macro_*` citation id for a live macro indicator label."""
    for needle, slug in _MACRO_INDICATOR_SLUGS:
        if needle in (indicator or ""):
            return f"mcp_macro_{slug}"
    return "mcp_macro_other"


def split_sentences_japanese(text: str) -> List[str]:
    """
    Split text into distinct sentences handling Japanese periods ('。'), 
    newlines, and English punctuation without breaking numbers.
    """
    # Normalize newlines
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    paragraphs = [p.strip() for p in normalized.split("\n") if p.strip()]
    
    sentences = []
    for p in paragraphs:
        # Split by Japanese full stop while keeping delimiters
        parts = re.split(r"(。|\. |\!|\?|！|？)", p)
        current = ""
        for i in range(0, len(parts), 2):
            seg = parts[i]
            delim = parts[i + 1] if i + 1 < len(parts) else ""
            current += seg + delim
            if current.strip():
                sentences.append(current.strip())
                current = ""
        if current.strip():
            sentences.append(current.strip())
            
    return sentences


def extract_citation_tags(sentence: str) -> Tuple[str, List[str]]:
    """
    Extract citation markers such as `[doc_nikkei_7203_01]` or `[7203]` from a sentence.
    Returns: (cleaned_sentence, list_of_cited_ids)
    """
    pattern = r"\[([a-zA-Z0-9_\-]+)\]"
    matches = re.findall(pattern, sentence)
    cleaned = re.sub(pattern, "", sentence).strip()
    return cleaned, list(set(matches))
