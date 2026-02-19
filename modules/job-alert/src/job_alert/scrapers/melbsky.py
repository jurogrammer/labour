from __future__ import annotations

import httpx
from tenacity import retry, stop_after_attempt, wait_fixed

from job_alert.config import Settings
from job_alert.models import SiteResult
from job_alert.scrapers.common import dedupe_posts, parse_board_posts

SOURCE_NAME = "melbsky"
BOARD_URL = "https://melbsky.com/bbs/main.php?gid=004"


@retry(stop=stop_after_attempt(3), wait=wait_fixed(1), reraise=True)
def _fetch_html(client: httpx.Client, url: str) -> str:
    response = client.get(url)
    response.raise_for_status()
    return response.text


def fetch_melbsky_posts(settings: Settings) -> SiteResult:
    headers = {"User-Agent": settings.user_agent}
    posts = []
    error: str | None = None

    with httpx.Client(timeout=settings.request_timeout_seconds, headers=headers) as client:
        try:
            html = _fetch_html(client, BOARD_URL)
            posts.extend(
                parse_board_posts(
                    html,
                    base_url=BOARD_URL,
                    source=SOURCE_NAME,
                    allow_url_tokens=("gid=004", "uid=", "main.php", "wr_id="),
                )
            )
        except Exception as exc:  # pragma: no cover - depends on network
            error = str(exc)

    return SiteResult(source=SOURCE_NAME, posts=dedupe_posts(posts), error=error)
