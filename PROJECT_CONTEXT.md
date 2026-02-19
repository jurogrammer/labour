# System Overview
- One-line summary: Monorepo for a scheduled Melbourne Korean-community job alert bot.
- System purpose: Collect construction and short-term labor job posts and send Slack notifications.
- Target users: Korean-speaking workers in Melbourne looking for short-term construction jobs.
- Current system stage/version: MVP implemented (v0.1.0).

# Global Architecture
- High-level architecture (text diagram):
  `GitHub Actions (10m schedule) -> job-alert pipeline -> site scrapers -> keyword filter -> SQLite dedupe -> Slack webhook`
- Communication patterns: HTTP scraping + Slack webhook POST.
- Cross-module dependencies: Root workflow depends on `modules/job-alert` executable package.
- Shared libraries: None yet.

# Modules Registry
- job-alert: Scrape target communities, filter relevant posts, deduplicate, and notify Slack.

# Global Conventions
- Coding standards: Python 3.12, type hints, ruff linting, clear function boundaries.
- Error handling standard: Site-level isolation; one scraper failure must not break whole run.
- Logging / tracing strategy: Structured stdout logs with run summary and per-site errors.
- Security policy: Credentials and webhook must stay in CI secrets; no plaintext secrets in repo.
- Naming conventions: snake_case for Python modules/functions, kebab-case for module folder names.
- Failure alert policy: Retry per site and notify Slack only after consecutive failure threshold.

# Infrastructure
- Deployment topology: GitHub Actions scheduled workflow on private repository.
- CI/CD strategy: Scheduled run plus manual dispatch; state DB auto-committed when changed.
- CI auth mode: Workflow uses Hojubada ID/PW automatic login and no longer depends on `HOJUBADA_STORAGE_STATE_B64` secret.
- Environments: Local dev and GitHub-hosted runner.
- Monitoring stack: Slack alerts and workflow run status.

# Data Strategy
- Database separation strategy: Single SQLite state file owned by job-alert module.
- Transaction boundaries: Per-run insert of new posts and run log entries.
- Event consistency model: At-least-once scrape with exactly-once notification per source post key.

# Cross-Cutting Concerns
- Authentication: Env-based account credentials + automatic Kakao login with optional session-state restore.
- Authorization: GitHub repository permissions and Slack webhook access control.
- Caching: SQLite dedupe state acts as durable cache of sent items.
- Rate limiting: Conservative run schedule and per-site request throttling/timeouts.
- Observability: Run summaries, site error details, and weekly no-new heartbeat message.
- Content filtering: Include keyword set with blacklist exclusions (kitchen-related posts excluded by default).

# Assumptions / Decisions
- Melbourne timezone (`Australia/Melbourne`) is the business clock.
- Slack webhook integration is sufficient for current notification needs.
- Hojubada login uses credentials first and can reuse Playwright storage state when available.
- Transient single-run site failures are suppressed to reduce Slack alert noise.

# Known Issues
- Scraper selectors may require updates when site DOM changes.
- Kakao can enforce additional verification that may block full headless login.
- Hojubada HTTPS endpoint is not reliably available; scraper uses HTTP endpoint.
- Raw scraper errors may include multi-line Playwright call logs when a site fails.

# Change Log (Last 10)
- 2026-02-20: Added keyword blacklist filtering (default kitchen exclusions + `KEYWORD_BLACKLIST_CSV` override support).
- 2026-02-20: Cleared runtime state tables (`sent_posts`, `run_logs`, `meta`) and verified live Slack delivery with a fresh run (`new_count=9`, `failed_sites=0`).
- 2026-02-20: Expanded Korean short-term keyword coverage by adding explicit `단기 알바` phrase while keeping existing `단기`.
- 2026-02-20: Added site retry + consecutive-failure threshold handling so one-off scraper failures are suppressed from Slack error alerts.
- 2026-02-20: Reverted Hojubada error text sanitization so Slack receives original Playwright error strings.
- 2026-02-20: Normalized Hojubada error reporting to one-line HTTP URL format in Slack (removed noisy Playwright call logs).
- 2026-02-20: Fixed Hojubada connectivity by switching scraper/auth URLs from HTTPS to HTTP; 3-site scrape succeeded in integration run.
- 2026-02-19: Ran local integration test with `.env`; woorimel/melbsky succeeded and hojubada returned connection refused in current environment.
- 2026-02-19: Removed `HOJUBADA_STORAGE_STATE_B64` usage from GitHub Actions workflow; CI now runs with credential-based automatic login.
- 2026-02-19: Updated architecture to support automatic Hojubada Kakao login with optional storage-state secret.
- 2026-02-19: Initialized monorepo architecture context and added `job-alert` module registry.
