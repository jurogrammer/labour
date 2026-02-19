from __future__ import annotations

from job_alert.config import Settings
from job_alert.models import SiteResult
from job_alert.scrapers.common import dedupe_posts, parse_board_posts

SOURCE_NAME = "hojubada"
BOARD_URL = "http://hojubada.com/bbs/board.php?bo_table=genguin"
LOGIN_URL = "http://hojubada.com/bbs/login.php"

_KAKAO_LOGIN_TRIGGER_SELECTORS = (
    "a[href*='kakao']",
    "button:has-text('카카오')",
    "a:has-text('카카오')",
    "button:has-text('Kakao')",
    "a:has-text('Kakao')",
)
_KAKAO_ID_SELECTORS = (
    "input[name='loginId']",
    "input#loginId--1",
    "input[name='email']",
    "input[type='email']",
    "input[name='id']",
)
_KAKAO_PW_SELECTORS = (
    "input[name='password']",
    "input[type='password']",
)
_KAKAO_SUBMIT_SELECTORS = (
    "button[type='submit']",
    "button:has-text('로그인')",
    "button:has-text('Login')",
    "input[type='submit']",
)


def _first_click(page, selectors: tuple[str, ...], timeout_ms: int = 5_000) -> bool:
    for selector in selectors:
        locator = page.locator(selector)
        if locator.count() > 0:
            locator.first.click(timeout=timeout_ms)
            return True
    return False


def _first_fill(page, selectors: tuple[str, ...], value: str, timeout_ms: int = 5_000) -> bool:
    for selector in selectors:
        locator = page.locator(selector)
        if locator.count() > 0:
            locator.first.fill(value, timeout=timeout_ms)
            return True
    return False


def _needs_authentication(current_url: str, html: str, posts_count: int) -> bool:
    if posts_count > 0:
        return False

    url_lower = current_url.casefold()
    html_lower = html.casefold()
    return (
        "accounts.kakao.com" in url_lower
        or "login" in url_lower
        or "카카오" in html_lower
        or "로그인" in html_lower
    )


def _login_with_kakao(page, settings: Settings) -> str | None:
    if "accounts.kakao.com" not in page.url.casefold():
        if not _first_click(page, _KAKAO_LOGIN_TRIGGER_SELECTORS):
            page.goto(LOGIN_URL, wait_until="domcontentloaded", timeout=45_000)
            if not _first_click(page, _KAKAO_LOGIN_TRIGGER_SELECTORS):
                return "kakao login button/link not found"

    page.wait_for_load_state("domcontentloaded", timeout=45_000)

    if not _first_fill(page, _KAKAO_ID_SELECTORS, settings.hojubada_id):
        return "kakao id input not found"
    if not _first_fill(page, _KAKAO_PW_SELECTORS, settings.hojubada_pw):
        return "kakao password input not found"
    if not _first_click(page, _KAKAO_SUBMIT_SELECTORS):
        return "kakao submit button not found"

    try:
        page.wait_for_load_state("networkidle", timeout=30_000)
    except Exception:
        page.wait_for_timeout(3_000)

    page.goto(BOARD_URL, wait_until="domcontentloaded", timeout=45_000)
    page.wait_for_timeout(2_000)
    if "accounts.kakao.com" in page.url.casefold():
        return "kakao login did not complete (extra verification may be required)"
    return None


def fetch_hojubada_posts(settings: Settings) -> SiteResult:
    context_kwargs = {"user_agent": settings.user_agent}
    if settings.hojubada_storage_path.exists():
        context_kwargs["storage_state"] = str(settings.hojubada_storage_path)

    try:
        from playwright.sync_api import sync_playwright
    except Exception as exc:  # pragma: no cover - import depends on env
        return SiteResult(source=SOURCE_NAME, posts=[], error=f"playwright import failed: {exc}")

    html = ""
    current_url = ""
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            context = browser.new_context(**context_kwargs)
            page = context.new_page()
            page.goto(BOARD_URL, wait_until="domcontentloaded", timeout=45_000)
            page.wait_for_timeout(2_000)
            html = page.content()
            current_url = page.url

            existing_posts = parse_board_posts(
                html,
                base_url=BOARD_URL,
                source=SOURCE_NAME,
                allow_url_tokens=("bo_table=genguin", "wr_id=", "board.php"),
            )
            if _needs_authentication(current_url, html, len(existing_posts)):
                login_error = _login_with_kakao(page, settings)
                if login_error:
                    context.close()
                    browser.close()
                    return SiteResult(source=SOURCE_NAME, posts=[], error=login_error)
                html = page.content()
                current_url = page.url

            settings.hojubada_storage_path.parent.mkdir(parents=True, exist_ok=True)
            context.storage_state(path=str(settings.hojubada_storage_path))
            context.close()
            browser.close()
    except Exception as exc:  # pragma: no cover - depends on network/browser
        return SiteResult(source=SOURCE_NAME, posts=[], error=str(exc))

    posts = parse_board_posts(
        html,
        base_url=BOARD_URL,
        source=SOURCE_NAME,
        allow_url_tokens=("bo_table=genguin", "wr_id=", "board.php"),
    )
    posts = dedupe_posts(posts)

    if _needs_authentication(current_url, html, len(posts)):
        return SiteResult(
            source=SOURCE_NAME,
            posts=[],
            error="authentication required; verify HOJUBADA_ID/HOJUBADA_PW",
        )

    return SiteResult(source=SOURCE_NAME, posts=posts, error=None)
