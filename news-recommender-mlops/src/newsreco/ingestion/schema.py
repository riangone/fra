"""Data schemas shared across the pipeline (kept dependency-free: plain dataclasses)."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Article:
    id: str
    title: str
    content: str
    category: str
    ticker: str = ""
    company_name: str = ""
    source: str = "日本経済新聞"
    date: str = ""

    def text(self) -> str:
        """Concatenated text used for content-based featurization."""
        return f"{self.title}\n{self.content}"


@dataclass(frozen=True)
class Interaction:
    user_id: int
    article_id: str
    event_type: str  # "view" | "click" | "read_long" | "like"
    timestamp: float
    weight: float = field(default=1.0)


EVENT_WEIGHTS = {
    "view": 1.0,
    "click": 2.0,
    "read_long": 3.0,
    "like": 4.0,
}
