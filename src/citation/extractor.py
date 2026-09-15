"""Sentence-level Citation Extraction and Parsing."""

import re
from typing import List, Tuple


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
