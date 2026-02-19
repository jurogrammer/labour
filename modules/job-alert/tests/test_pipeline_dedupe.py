from datetime import datetime, timedelta, timezone

from job_alert.config import Settings
from job_alert.models import JobPost, SiteResult
from job_alert.pipeline import run_pipeline
from job_alert.storage import StateStore


def _base_settings(tmp_path) -> Settings:
    return Settings(
        slack_webhook_url="https://hooks.slack.test/services/mock",
        woorimel_id="user",
        woorimel_pw="pw",
        melbsky_id="user",
        melbsky_pw="pw",
        hojubada_id="user",
        hojubada_pw="pw",
        sent_db_path=tmp_path / "sent.sqlite",
        hojubada_storage_path=tmp_path / "storage_state.json",
        tz="Australia/Melbourne",
    )


def _post(source_post_id: str = "55") -> JobPost:
    return JobPost(
        source="woorimel",
        source_post_id=source_post_id,
        title="멜번 건설 잡부 단기",
        url=f"https://example.com/{source_post_id}",
        posted_at_raw=None,
        content_snippet="demolition labour",
        fetched_at_utc=datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
    )


def test_pipeline_deduplicates_same_post_across_runs(tmp_path) -> None:
    settings = _base_settings(tmp_path)
    sent_messages: list[str] = []

    def fake_sender(_: str, message: str, __: float) -> None:
        sent_messages.append(message)

    def scraper(_: Settings) -> SiteResult:
        return SiteResult(source="woorimel", posts=[_post("1")], error=None)

    now = datetime(2026, 2, 19, 0, 0, tzinfo=timezone.utc)
    first = run_pipeline(settings, scrapers=(scraper,), send_message=fake_sender, now_utc=now)
    second = run_pipeline(
        settings,
        scrapers=(scraper,),
        send_message=fake_sender,
        now_utc=now + timedelta(minutes=10),
    )

    assert first.new_count == 1
    assert second.new_count == 0

    with StateStore(settings.sent_db_path) as store:
        assert store.count_sent_posts() == 1


def test_pipeline_reports_partial_failure_and_keeps_success(tmp_path) -> None:
    settings = _base_settings(tmp_path)

    def fake_sender(_: str, message: str, __: float) -> None:
        assert "일시 실패(자동 재시도 중)" in message

    def good_scraper(_: Settings) -> SiteResult:
        return SiteResult(source="woorimel", posts=[_post("10")], error=None)

    def failing_scraper(_: Settings) -> SiteResult:
        return SiteResult(source="melbsky", posts=[], error="timeout")

    result = run_pipeline(
        settings,
        scrapers=(good_scraper, failing_scraper),
        send_message=fake_sender,
        now_utc=datetime(2026, 2, 19, 0, 0, tzinfo=timezone.utc),
    )

    assert result.new_count == 1
    assert result.success_site_count == 1
    assert result.failed_site_count == 1
    assert result.error_messages == ["melbsky: timeout"]
    assert result.message_sent


def test_pipeline_suppresses_single_failure_when_no_new_posts(tmp_path) -> None:
    settings = _base_settings(tmp_path)
    sent_messages: list[str] = []

    def fake_sender(_: str, message: str, __: float) -> None:
        sent_messages.append(message)

    def failing_scraper(_: Settings) -> SiteResult:
        return SiteResult(source="melbsky", posts=[], error="timeout")

    result = run_pipeline(
        settings,
        scrapers=(failing_scraper,),
        send_message=fake_sender,
        now_utc=datetime(2026, 2, 19, 0, 0, tzinfo=timezone.utc),
    )

    assert result.failed_site_count == 1
    assert result.error_messages == ["melbsky: timeout"]
    assert not result.message_sent
    assert sent_messages == []


def test_pipeline_alerts_after_consecutive_failures(tmp_path) -> None:
    settings = _base_settings(tmp_path)
    sent_messages: list[str] = []

    def fake_sender(_: str, message: str, __: float) -> None:
        sent_messages.append(message)

    def failing_scraper(_: Settings) -> SiteResult:
        return SiteResult(source="melbsky", posts=[], error="timeout")

    first = run_pipeline(
        settings,
        scrapers=(failing_scraper,),
        send_message=fake_sender,
        now_utc=datetime(2026, 2, 19, 0, 0, tzinfo=timezone.utc),
    )
    second = run_pipeline(
        settings,
        scrapers=(failing_scraper,),
        send_message=fake_sender,
        now_utc=datetime(2026, 2, 19, 0, 10, tzinfo=timezone.utc),
    )

    assert not first.message_sent
    assert second.message_sent
    assert len(sent_messages) == 1
    assert "오류" in sent_messages[0]
    assert "연속 실패 2회" in sent_messages[0]


def test_pipeline_retries_scraper_before_marking_failure(tmp_path) -> None:
    settings = _base_settings(tmp_path)
    settings = settings.model_copy(update={"site_retry_attempts": 2, "site_retry_delay_seconds": 0.0})
    sent_messages: list[str] = []
    attempts = {"count": 0}

    def fake_sender(_: str, message: str, __: float) -> None:
        sent_messages.append(message)

    def flaky_scraper(_: Settings) -> SiteResult:
        attempts["count"] += 1
        if attempts["count"] == 1:
            return SiteResult(source="melbsky", posts=[], error="temporary timeout")
        return SiteResult(source="melbsky", posts=[_post("200")], error=None)

    result = run_pipeline(
        settings,
        scrapers=(flaky_scraper,),
        send_message=fake_sender,
        now_utc=datetime(2026, 2, 19, 1, 0, tzinfo=timezone.utc),
    )

    assert attempts["count"] == 2
    assert result.failed_site_count == 0
    assert result.new_count == 1
    assert result.message_sent


def test_pipeline_excludes_blacklisted_posts(tmp_path) -> None:
    settings = _base_settings(tmp_path)
    sent_messages: list[str] = []

    def fake_sender(_: str, message: str, __: float) -> None:
        sent_messages.append(message)

    def scraper(_: Settings) -> SiteResult:
        return SiteResult(
            source="woorimel",
            posts=[
                _post("301"),
                JobPost(
                    source="woorimel",
                    source_post_id="302",
                    title="키친핸드 단기 구인",
                    url="https://example.com/302",
                    posted_at_raw=None,
                    content_snippet="kitchen hand",
                    fetched_at_utc=datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
                ),
            ],
            error=None,
        )

    result = run_pipeline(
        settings,
        scrapers=(scraper,),
        send_message=fake_sender,
        now_utc=datetime(2026, 2, 19, 2, 0, tzinfo=timezone.utc),
    )

    assert result.keyword_matched == 1
    assert result.new_count == 1
    assert result.message_sent
    assert "키친핸드" not in sent_messages[0]
