from job_alert.keywords import build_keyword_set, matches_keywords, normalize_text


def test_normalize_text_collapses_spacing_and_case() -> None:
    assert normalize_text("  CONSTRUCTION   Day-Job ") == "construction day job"


def test_matches_keywords_with_korean_and_english() -> None:
    keywords = build_keyword_set(None)
    assert matches_keywords("멜번 건설 데몰리션 구인", "", keywords)
    assert matches_keywords("Casual labour shift", "day job available", keywords)


def test_keyword_csv_override_adds_new_terms() -> None:
    keywords = build_keyword_set("forklift, warehouse")
    assert "forklift" in keywords
    assert "warehouse" in keywords


def test_default_keywords_include_short_term_korean_variants() -> None:
    keywords = build_keyword_set(None)
    assert "단기" in keywords
    assert "단기 알바" in keywords
    assert matches_keywords("주말 단기 알바 구함", "", keywords)
