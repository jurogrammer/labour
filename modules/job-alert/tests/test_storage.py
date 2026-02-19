from datetime import datetime, timezone

from job_alert.models import JobPost
from job_alert.storage import StateStore


def _sample_post(post_id: str = "1") -> JobPost:
    return JobPost(
        source="woorimel",
        source_post_id=post_id,
        title="건설 단기 구인",
        url=f"https://example.com/post/{post_id}",
        posted_at_raw=None,
        content_snippet="데몰리션 경험자 우대",
        fetched_at_utc=datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
    )


def test_mark_sent_if_new_is_idempotent(tmp_path) -> None:
    db_path = tmp_path / "state.sqlite"
    post = _sample_post("123")

    with StateStore(db_path) as store:
        assert store.mark_sent_if_new(post)
        assert not store.mark_sent_if_new(post)
        assert store.count_sent_posts() == 1


def test_get_unsent_posts_and_mark_posts_sent(tmp_path) -> None:
    db_path = tmp_path / "state.sqlite"
    posts = [_sample_post("1"), _sample_post("2"), _sample_post("2")]

    with StateStore(db_path) as store:
        unsent = store.get_unsent_posts(posts)
        assert len(unsent) == 2

        store.mark_posts_sent(unsent)
        assert store.count_sent_posts() == 2

        second_unsent = store.get_unsent_posts(posts)
        assert second_unsent == []
