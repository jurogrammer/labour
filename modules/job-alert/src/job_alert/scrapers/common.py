from __future__ import annotations

import hashlib
import re
from datetime import datetime, timezone
from urllib.parse import parse_qs, urljoin, urlparse

from bs4 import BeautifulSoup

from job_alert.models import JobPost

_POST_QUERY_KEYS = ("wr_id", "document_srl", "no", "idx", "article_no", "uid")
_NAV_LINK_TEXTS = {
    "login",
    "logout",
    "register",
    "회원가입",
    "로그인",
    "공지",
    "목록",
    "이전",
    "다음",
}


def _clean_spaces(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def infer_post_id(url: str) -> str:
    parsed = urlparse(url)
    query = parse_qs(parsed.query)
    for key in _POST_QUERY_KEYS:
        values = query.get(key)
        if values and values[0].strip():
            return f"{key}:{values[0].strip()}"

    path_match = re.search(r"/(\d{3,})(?:/)?$", parsed.path)
    if path_match:
        return f"path:{path_match.group(1)}"

    digest = hashlib.sha1(url.encode("utf-8")).hexdigest()[:16]
    return f"hash:{digest}"


def _is_probable_index_link(url: str) -> bool:
    parsed = urlparse(url)
    query = parse_qs(parsed.query)
    if any(key in query for key in _POST_QUERY_KEYS):
        return False
    if "page" in query or "findex" in query:
        return True
    return parsed.path.endswith("/")


def _extract_snippet(anchor) -> str:
    container = anchor.find_parent(["tr", "li", "div", "article"])
    if container is None:
        return ""
    text = _clean_spaces(container.get_text(" ", strip=True))
    return text[:200]


def parse_board_posts(
    html: str,
    *,
    base_url: str,
    source: str,
    allow_url_tokens: tuple[str, ...],
    limit: int = 80,
) -> list[JobPost]:
    soup = BeautifulSoup(html, "html.parser")
    fetched_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    posts: list[JobPost] = []
    seen_keys: set[tuple[str, str]] = set()
    seen_urls: set[str] = set()

    for anchor in soup.select("a[href]"):
        raw_title = _clean_spaces(anchor.get_text(" ", strip=True))
        if len(raw_title) < 2 or raw_title.casefold() in _NAV_LINK_TEXTS:
            continue

        href = urljoin(base_url, anchor.get("href", ""))
        if not href.startswith(("http://", "https://")):
            continue
        if allow_url_tokens and not any(token in href for token in allow_url_tokens):
            continue
        if _is_probable_index_link(href):
            continue
        if href in seen_urls:
            continue

        source_post_id = infer_post_id(href)
        key = (source, source_post_id)
        if key in seen_keys:
            continue

        snippet = _extract_snippet(anchor)
        if snippet == raw_title:
            snippet = ""

        posts.append(
            JobPost(
                source=source,
                source_post_id=source_post_id,
                title=raw_title,
                url=href,
                posted_at_raw=None,
                content_snippet=snippet,
                fetched_at_utc=fetched_at,
            )
        )
        seen_keys.add(key)
        seen_urls.add(href)

        if len(posts) >= limit:
            break

    return posts


def dedupe_posts(posts: list[JobPost]) -> list[JobPost]:
    seen: set[tuple[str, str]] = set()
    deduped: list[JobPost] = []
    for post in posts:
        key = (post.source, post.source_post_id)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(post)
    return deduped
