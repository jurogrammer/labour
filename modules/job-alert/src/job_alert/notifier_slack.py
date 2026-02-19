from __future__ import annotations

import httpx


def send_slack_message(webhook_url: str, message_text: str, timeout_seconds: float = 20.0) -> None:
    response = httpx.post(
        webhook_url,
        json={"text": message_text},
        timeout=timeout_seconds,
        follow_redirects=True,
    )
    response.raise_for_status()
