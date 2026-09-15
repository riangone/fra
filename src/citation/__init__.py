"""Citation and Attribution Engine package."""

from src.citation.extractor import split_sentences_japanese, extract_citation_tags
from src.citation.verifier import CitationConsistencyVerifier

__all__ = [
    "split_sentences_japanese",
    "extract_citation_tags",
    "CitationConsistencyVerifier",
]
