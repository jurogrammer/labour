from __future__ import annotations

import argparse
from pathlib import Path

from job_alert.auth.kakao_session_bootstrap import bootstrap_kakao_session, encode_storage_state_b64
from job_alert.config import (
    RUN_REQUIRED_ENVS,
    assert_required_envs,
    ensure_hojubada_storage_state,
    load_settings,
    missing_envs,
)
from job_alert.pipeline import run_pipeline
from job_alert.storage import StateStore


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="job-alert")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("run", help="Run scraping + filtering + Slack notification pipeline")
    subparsers.add_parser("healthcheck", help="Validate config and local runtime readiness")

    bootstrap_parser = subparsers.add_parser(
        "bootstrap-kakao-session",
        help="Open browser, complete Kakao login, and save Playwright storage state",
    )
    bootstrap_parser.add_argument("--headed", action="store_true", default=True)
    bootstrap_parser.add_argument("--headless", action="store_true", default=False)
    bootstrap_parser.add_argument(
        "--login-url",
        default="http://hojubada.com/bbs/login.php",
        help="Login URL to open for manual Kakao authentication",
    )
    bootstrap_parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Override storage state output path",
    )

    return parser


def _cmd_run() -> int:
    settings = load_settings()
    assert_required_envs(RUN_REQUIRED_ENVS)
    result = run_pipeline(settings)

    print(
        "run summary:",
        f"total_collected={result.total_collected}",
        f"keyword_matched={result.keyword_matched}",
        f"new_count={result.new_count}",
        f"failed_sites={result.failed_site_count}",
        f"message_sent={result.message_sent}",
    )

    if result.failed_site_count > 0 and result.success_site_count == 0:
        return 1
    return 0


def _cmd_healthcheck() -> int:
    settings = load_settings()
    missing = missing_envs(RUN_REQUIRED_ENVS)
    if missing:
        print("missing required env vars:", ", ".join(missing))
        return 1

    try:
        with StateStore(settings.sent_db_path):
            pass
    except Exception as exc:
        print(f"state db check failed: {exc}")
        return 1

    try:
        state_path = ensure_hojubada_storage_state(settings)
    except Exception as exc:
        state_path = None
        print(f"hojubada storage state decode failed, fallback to automatic login: {exc}")

    if state_path is None:
        print("hojubada storage state not provided; automatic login will be used")
    else:
        print(f"hojubada storage state ready: {state_path}")
    print("healthcheck passed")
    return 0


def _cmd_bootstrap(args: argparse.Namespace) -> int:
    settings = load_settings()
    output_path = args.output or settings.hojubada_storage_path
    headed = not args.headless if args.headless else args.headed

    saved_path = bootstrap_kakao_session(
        output_path,
        login_url=args.login_url,
        headed=headed,
    )
    encoded = encode_storage_state_b64(saved_path)

    print(f"saved storage state to: {saved_path}")
    print("optional: set this value as HOJUBADA_STORAGE_STATE_B64 secret for faster startup:")
    print(encoded)
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    try:
        if args.command == "run":
            return _cmd_run()
        if args.command == "healthcheck":
            return _cmd_healthcheck()
        if args.command == "bootstrap-kakao-session":
            return _cmd_bootstrap(args)
    except ValueError as exc:
        print(exc)
        return 1

    parser.print_help()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
