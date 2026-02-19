from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class JobPost:
    source: str
    source_post_id: str
    title: str
    url: str
    posted_at_raw: str | None
    content_snippet: str
    fetched_at_utc: str


@dataclass(frozen=True)
class SiteResult:
    source: str
    posts: list[JobPost]
    error: str | None = None


@dataclass(frozen=True)
class PipelineResult:
    total_collected: int
    keyword_matched: int
    new_count: int
    success_site_count: int
    failed_site_count: int
    error_messages: list[str]
    message_sent: bool
    summary_text: str | None
