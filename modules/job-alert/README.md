# job-alert

Scheduled scraper pipeline that collects construction and short-term labor job posts from Korean
community sites in Melbourne and sends Slack notifications.

## Commands

```bash
python -m job_alert.cli healthcheck
python -m job_alert.cli bootstrap-kakao-session --headed
python -m job_alert.cli run
```

## Required environment variables

- `SLACK_WEBHOOK_URL`
- `WOORIMEL_ID`, `WOORIMEL_PW`
- `MELBSKY_ID`, `MELBSKY_PW`
- `HOJUBADA_ID`, `HOJUBADA_PW`

Optional:

- `HOJUBADA_STORAGE_STATE_B64` (restores cached session; if missing, automatic Kakao login is attempted)
- `KEYWORDS_CSV`
- `TZ` (default: `Australia/Melbourne`)
- `SITE_RETRY_ATTEMPTS` (default: `2`)
- `SITE_RETRY_DELAY_SECONDS` (default: `1`)
- `ERROR_ALERT_THRESHOLD` (default: `2`, consecutive failures required before Slack error alert)

## Kakao session bootstrap

1. Run `python -m job_alert.cli bootstrap-kakao-session --headed` locally.
2. Complete Kakao login in browser.
3. Press Enter in terminal to save storage state.
4. Optional: copy emitted base64 string into `HOJUBADA_STORAGE_STATE_B64` secret.

## GitHub Actions

Workflow file: `.github/workflows/job-alert.yml`

- Runs every 10 minutes.
- Executes `python -m job_alert.cli run`.
- Commits updated `modules/job-alert/data/sent_posts.sqlite` when changed.

## Failure handling policy

- Each site scraper is retried automatically (`SITE_RETRY_ATTEMPTS`).
- A one-off site failure is treated as transient and does not trigger a standalone Slack error alert.
- Slack error section is sent only when the same site fails consecutively and reaches `ERROR_ALERT_THRESHOLD`.
