from __future__ import annotations

import base64
from pathlib import Path


def bootstrap_kakao_session(
    storage_path: Path,
    *,
    login_url: str = "http://hojubada.com/bbs/login.php",
    headed: bool = True,
) -> Path:
    from playwright.sync_api import sync_playwright

    storage_path.parent.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=not headed, slow_mo=50 if headed else 0)
        context = browser.new_context()
        page = context.new_page()
        page.goto(login_url, wait_until="domcontentloaded", timeout=60_000)

        print("Finish Kakao login in the browser, then press Enter here to save the session.")
        input("Press Enter after successful login: ")

        context.storage_state(path=str(storage_path))
        context.close()
        browser.close()

    return storage_path


def encode_storage_state_b64(storage_path: Path) -> str:
    return base64.b64encode(storage_path.read_bytes()).decode("utf-8")
