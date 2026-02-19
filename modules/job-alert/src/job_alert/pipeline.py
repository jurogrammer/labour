from __future__ import annotations

import time
from collections.abc import Callable
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from job_alert.config import Settings, ensure_hojubada_storage_state
from job_alert.keywords import build_keyword_set, matches_keywords
from job_alert.models import JobPost, PipelineResult, SiteResult
from job_alert.notifier_slack import send_slack_message
from job_alert.scrapers.hojubada import fetch_hojubada_posts
from job_alert.scrapers.melbsky import fetch_melbsky_posts
from job_alert.scrapers.woorimel import fetch_woorimel_posts
from job_alert.storage import StateStore

Scraper = Callable[[Settings], SiteResult]
Sender = Callable[[str, str, float], None]

DEFAULT_SCRAPERS: tuple[Scraper, ...] = (
    fetch_woorimel_posts,
    fetch_melbsky_posts,
    fetch_hojubada_posts,
)
NO_NEW_HEARTBEAT_META_KEY = "last_no_new_heartbeat_utc"
NO_NEW_HEARTBEAT_INTERVAL_DAYS = 7
SITE_FAILURE_STREAK_META_PREFIX = "site_failure_streak:"


def _scraper_name(scraper: Scraper) -> str:
    name = getattr(scraper, "__name__", "unknown")
    if name.startswith("fetch_") and name.endswith("_posts"):
        return name.removeprefix("fetch_").removesuffix("_posts")
    return name


def _safe_run_scraper(scraper: Scraper, settings: Settings) -> SiteResult:
    try:
        return scraper(settings)
    except Exception as exc:  # pragma: no cover - defensive boundary
        return SiteResult(source=_scraper_name(scraper), posts=[], error=f"unexpected error: {exc}")


def _run_scraper_with_retry(
    scraper: Scraper,
    settings: Settings,
    *,
    attempts: int,
    delay_seconds: float,
) -> SiteResult:
    last_result: SiteResult | None = None
    for attempt in range(attempts):
        last_result = _safe_run_scraper(scraper, settings)
        if not last_result.error:
            return last_result
        if attempt < attempts - 1 and delay_seconds > 0:
            time.sleep(delay_seconds)
    return last_result or SiteResult(source=_scraper_name(scraper), posts=[], error="unknown error")


def _build_summary_message(
    settings: Settings,
    run_at_utc: datetime,
    new_posts: list[JobPost],
    keyword_matched: int,
    site_results: list[SiteResult],
    notified_error_messages: list[str],
    transient_failures: list[str],
    *,
    heartbeat_only: bool,
) -> str:
    try:
        local_now = run_at_utc.astimezone(ZoneInfo(settings.tz))
    except Exception:
        local_now = run_at_utc

    success_count = sum(1 for result in site_results if not result.error)
    failed_count = len(site_results) - success_count

    lines = [
        f"[건설/단기 알바 알림] {local_now:%Y-%m-%d %H:%M} ({settings.tz})",
        (
            f"신규 {len(new_posts)}건 | 키워드 일치 {keyword_matched}건 "
            f"| 사이트 성공 {success_count} / 실패 {failed_count}"
        ),
    ]

    if new_posts:
        lines.append("")
        lines.append("신규 공고")
        for post in new_posts[:30]:
            lines.append(f"- [{post.source}] {post.title} - {post.url}")
        if len(new_posts) > 30:
            lines.append(f"- ... and {len(new_posts) - 30} more")
    elif heartbeat_only:
        lines.append("")
        lines.append("주간 상태 확인: 신규 공고 없음")

    if notified_error_messages:
        lines.append("")
        lines.append("오류")
        for error in notified_error_messages:
            lines.append(f"- {error}")
    elif transient_failures:
        lines.append("")
        lines.append("일시 실패(자동 재시도 중)")
        for warning in transient_failures:
            lines.append(f"- {warning}")

    return "\n".join(lines)


def _should_send_no_new_heartbeat(store: StateStore, now_utc: datetime) -> bool:
    previous = store.get_meta(NO_NEW_HEARTBEAT_META_KEY)
    if not previous:
        return True

    try:
        previous_dt = datetime.fromisoformat(previous)
    except ValueError:
        return True

    if previous_dt.tzinfo is None:
        previous_dt = previous_dt.replace(tzinfo=timezone.utc)

    return now_utc - previous_dt >= timedelta(days=NO_NEW_HEARTBEAT_INTERVAL_DAYS)


def _site_failure_streak_key(source: str) -> str:
    return f"{SITE_FAILURE_STREAK_META_PREFIX}{source}"


def _parse_int_or_zero(raw: str | None) -> int:
    if not raw:
        return 0
    try:
        return int(raw)
    except ValueError:
        return 0


def _update_failure_streaks(store: StateStore, site_results: list[SiteResult]) -> dict[str, int]:
    streaks: dict[str, int] = {}
    for result in site_results:
        key = _site_failure_streak_key(result.source)
        previous = _parse_int_or_zero(store.get_meta(key))
        current = previous + 1 if result.error else 0
        store.set_meta(key, str(current))
        streaks[result.source] = current
    return streaks


def run_pipeline(
    settings: Settings,
    *,
    scrapers: tuple[Scraper, ...] = DEFAULT_SCRAPERS,
    send_message: Sender = send_slack_message,
    now_utc: datetime | None = None,
) -> PipelineResult:
    run_at_utc = now_utc or datetime.now(timezone.utc)
    run_at_iso = run_at_utc.replace(microsecond=0).isoformat()

    try:
        ensure_hojubada_storage_state(settings)
    except Exception:
        # Invalid/missing base64 state is non-fatal; scraper will attempt credential login.
        pass

    site_results: list[SiteResult] = []
    for scraper in scrapers:
        site_results.append(
            _run_scraper_with_retry(
                scraper,
                settings,
                attempts=settings.site_retry_attempts,
                delay_seconds=settings.site_retry_delay_seconds,
            )
        )

    all_posts = [post for result in site_results for post in result.posts]
    keyword_set = build_keyword_set(settings.keywords_csv)
    keyword_matched_posts = [
        post for post in all_posts if matches_keywords(post.title, post.content_snippet, keyword_set)
    ]

    error_messages = [f"{result.source}: {result.error}" for result in site_results if result.error]
    success_site_count = sum(1 for result in site_results if not result.error)
    failed_site_count = len(site_results) - success_site_count

    with StateStore(settings.sent_db_path) as store:
        unsent_posts = store.get_unsent_posts(keyword_matched_posts)
        failure_streaks = _update_failure_streaks(store, site_results)

        notified_error_messages: list[str] = []
        transient_failures: list[str] = []
        for result in site_results:
            if not result.error:
                continue
            streak = failure_streaks.get(result.source, 1)
            if streak >= settings.error_alert_threshold:
                notified_error_messages.append(
                    f"{result.source}: {result.error} (연속 실패 {streak}회)"
                )
            else:
                transient_failures.append(
                    f"{result.source}: 연속 실패 {streak}회 (임계치 {settings.error_alert_threshold}회 미만)"
                )

        send_heartbeat = not unsent_posts and not error_messages and _should_send_no_new_heartbeat(
            store, run_at_utc
        )
        should_send = bool(unsent_posts or notified_error_messages or send_heartbeat)
        summary_text: str | None = None

        if should_send:
            summary_text = _build_summary_message(
                settings,
                run_at_utc,
                unsent_posts,
                len(keyword_matched_posts),
                site_results,
                notified_error_messages,
                transient_failures,
                heartbeat_only=send_heartbeat,
            )
            send_message(
                settings.slack_webhook_url,
                summary_text,
                settings.request_timeout_seconds,
            )
            if unsent_posts:
                store.mark_posts_sent(unsent_posts, sent_at_utc=run_at_iso)
            if send_heartbeat:
                store.set_meta(NO_NEW_HEARTBEAT_META_KEY, run_at_iso)

        store.log_run(run_at_iso, new_count=len(unsent_posts), error_count=len(error_messages))

    return PipelineResult(
        total_collected=len(all_posts),
        keyword_matched=len(keyword_matched_posts),
        new_count=len(unsent_posts),
        success_site_count=success_site_count,
        failed_site_count=failed_site_count,
        error_messages=error_messages,
        message_sent=should_send,
        summary_text=summary_text,
    )
