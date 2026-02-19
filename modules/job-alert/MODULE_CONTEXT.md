# Module Overview
- Module name: job-alert
- Responsibility: Scrape job boards, filter construction/short-term jobs, dedupe, and send Slack alerts.
- Dependencies (internal + external): Internal package submodules; external libraries include Playwright, httpx, BeautifulSoup, pydantic, and sqlite3.

# Internal Architecture
- Package structure:
  - `src/job_alert/config.py`
  - `src/job_alert/models.py`
  - `src/job_alert/keywords.py`
  - `src/job_alert/storage.py`
  - `src/job_alert/notifier_slack.py`
  - `src/job_alert/scrapers/*`
  - `src/job_alert/auth/kakao_session_bootstrap.py`
  - `src/job_alert/pipeline.py`
  - `src/job_alert/cli.py`
- Key classes/components:
  - `Settings` for validated runtime config.
  - `JobPost`, `SiteResult`, `PipelineResult` models.
  - `StateStore` for SQLite dedupe and run metadata.
  - Scraper functions per source site.
- Domain model summary: A source post is uniquely keyed by `(source, source_post_id)` and notified once.

# APIs (If applicable)
- Endpoints: N/A (CLI module).
- DTO contracts:
  - `JobPost(source, source_post_id, title, url, posted_at_raw, content_snippet, fetched_at_utc)`.
  - `SiteResult(source, posts, error)`.
  - `PipelineResult(...)` run summary payload.
- External integrations:
  - Target sites: Woorimel, Melbsky, Hojubada.
  - Slack Incoming Webhook.

# Data
- Tables / Collections owned:
  - `sent_posts`
  - `run_logs`
  - `meta`
- Schema notes: Primary key on `(source, source_post_id)` guarantees dedupe.
- Migration strategy: Idempotent `CREATE TABLE IF NOT EXISTS` on startup.

# Configuration
- Required env vars:
  - `SLACK_WEBHOOK_URL`
  - `WOORIMEL_ID`, `WOORIMEL_PW`
  - `MELBSKY_ID`, `MELBSKY_PW`
  - `HOJUBADA_ID`, `HOJUBADA_PW`
- Module-specific configs:
  - `HOJUBADA_STORAGE_STATE_B64` (optional local optimization; GitHub workflow does not require it)
  - `KEYWORDS_CSV` (optional keyword override)
  - `KEYWORD_BLACKLIST_CSV` (optional keyword exclusion override; kitchen-related exclusions enabled by default)
  - `TZ` (default `Australia/Melbourne`)
  - `SITE_RETRY_ATTEMPTS` (default `2`)
  - `SITE_RETRY_DELAY_SECONDS` (default `1`)
  - `ERROR_ALERT_THRESHOLD` (default `2`)

# Runtime
- How to run this module locally:
  - `python -m job_alert.cli healthcheck`
  - `python -m job_alert.cli bootstrap-kakao-session --headed`
  - `python -m job_alert.cli run`
- Ports: N/A.
- Profiles: Local/manual and GitHub Actions scheduled profile (minute offsets `7,17,27,37,47,57` UTC).

# Module Conventions
- Module-specific patterns: Each scraper returns `SiteResult`; errors are captured per site.
- Error boundaries: Pipeline proceeds with partial failures and reports them to Slack.
- Validation rules: Required env vars validated before `run`; webhook URL must use HTTPS.
- Failure handling rules: Scrapers retry automatically; Slack alert delivery is only triggered when at least one new posting is found.
- Filtering rules: Posts must match include keywords and must not match blacklist keywords.

# Assumptions / Decisions
- Hojubada scraper attempts automatic Kakao login with credentials and refreshes storage state.
- No alert is sent on runs with zero newly matched jobs, including repeated site-failure cases.
- Workflow cron avoids `:00` to reduce scheduler delay/drop probability in GitHub Actions.

# Known Issues
- Site markup differences can reduce extraction quality without parser updates.
- Some boards may require extra selectors for better timestamp/snippet capture.
- Kakao additional verification (2FA/captcha/device check) can still require manual intervention.
- Hojubada integration currently depends on HTTP endpoint availability (HTTPS is unreliable).
- Raw Playwright errors can include verbose multi-line call logs in Slack alerts.

# Change Log (Last 10)
- 2026-02-20: Shifted GitHub Actions cron to offset minutes (`7,17,27,37,47,57`) to improve scheduled-run reliability.
- 2026-02-20: Stopped Slack delivery when no new postings are found, even if site-failure thresholds are reached.
- 2026-02-20: Added blacklist keyword filtering (default `키친/키친핸드/kitchen/kitchen hand`) and `KEYWORD_BLACKLIST_CSV` config.
- 2026-02-20: Performed live delivery verification after state reset; pipeline sent Slack alert with 9 new posts and zero site failures.
- 2026-02-20: Added explicit default keyword phrase `단기 알바` and regression test coverage for Korean short-term variants.
- 2026-02-20: Implemented retry + consecutive failure threshold policy (single transient failures suppressed, escalated on repeated failures).
- 2026-02-20: Reverted Hojubada error sanitization; Slack now receives raw Playwright error text again.
- 2026-02-20: Added Hojubada error sanitization (https->http rewrite and call-log trimming) for cleaner Slack alerts.
- 2026-02-20: Updated Hojubada board/login URLs to HTTP, resolving connection-refused and restoring 3-site collection.
- 2026-02-19: Executed local integration test via `.env`; dedupe worked and hojubada path failed with connection-refused in this runtime.
- 2026-02-19: Removed workflow dependency on `HOJUBADA_STORAGE_STATE_B64`; CI runs with automatic Kakao login via credentials.
