from __future__ import annotations

import re
import unicodedata

DEFAULT_KEYWORDS = (
    "건설",
    "잡부",
    "데몰리션",
    "현장",
    "컨스트럭션",
    "construction",
    "demolition",
    "labour",
    "labor",
    "casual",
    "short term",
    "day job",
    "단기",
    "단기 알바",
    "단기알바",
    "캐주얼",
)


def normalize_text(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value or "").casefold()
    normalized = re.sub(r"[\W_]+", " ", normalized)
    normalized = re.sub(r"\s+", " ", normalized).strip()
    return normalized


def parse_keywords_csv(value: str | None) -> list[str]:
    if not value:
        return []
    return [item.strip() for item in value.split(",") if item.strip()]


def build_keyword_set(extra_csv: str | None = None) -> list[str]:
    combined = list(DEFAULT_KEYWORDS) + parse_keywords_csv(extra_csv)
    normalized = {normalize_text(word) for word in combined if normalize_text(word)}
    return sorted(normalized)


def matches_keywords(title: str, snippet: str, keywords: list[str]) -> bool:
    haystack = normalize_text(f"{title} {snippet}")
    return any(keyword in haystack for keyword in keywords)
