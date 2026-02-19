from __future__ import annotations

import httpx
from tenacity import retry, stop_after_attempt, wait_fixed

from job_alert.config import Settings
from job_alert.models import SiteResult
from job_alert.scrapers.common import dedupe_posts, parse_board_posts

SOURCE_NAME = "woorimel"
BOARD_URLS = (
    "https://woorimel.com/board/melbourne-jobs",
    "https://woorimel.com/board/melbourne-jobs?category_id=&findex=post_datetime+desc&page=2",
)


@retry(stop=stop_after_attempt(3), wait=wait_fixed(1), reraise=True)
def _fetch_html(client: httpx.Client, url: str) -> str:
    response = client.get(url)
    response.raise_for_status()
    return response.text


def fetch_woorimel_posts(settings: Settings) -> SiteResult:
    posts = []
    errors: list[str] = []
    headers = {"User-Agent": settings.user_agent}

    with httpx.Client(timeout=settings.request_timeout_seconds, headers=headers) as client:
        for url in BOARD_URLS:
            try:
                html = _fetch_html(client, url)
                posts.extend(
                    parse_board_posts(
                        html,
                        base_url=url,
                        source=SOURCE_NAME,
                        allow_url_tokens=("melbourne-jobs", "wr_id=", "document_srl="),
                    )
                )
            except Exception as exc:  # pragma: no cover - depends on network
                errors.append(f"{url}: {exc}")

    return SiteResult(
        source=SOURCE_NAME,
        posts=dedupe_posts(posts),
        error="; ".join(errors) if errors else None,
    )
