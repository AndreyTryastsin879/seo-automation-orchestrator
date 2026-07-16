# Changelog

This file records notable user-facing and architectural progress in SEO Automation Orchestrator.

## Unreleased

### Added

- Telegram project management, phone-based bot access control, and root-admin tools.
- Async task execution through Redis and RQ with launch tracking, task status, cancellation, and structured logs.
- Standard and heavy SEO crawler modes with checkpoints, partial exports, CSV/XLSX results, and relative-link diagnostics.
- Sitemap parsing from projects, direct URLs, and `robots.txt`, including optional server-status checks.
- Sitemap-to-Yandex-queue transfer for saved projects.
- Yandex Webmaster recrawl queues stored as CSV, manual queue insertion, 24-hour task timeout, cancellation, and live progress.
- Encrypted manually issued Yandex OAuth token storage and aggregate `indexing_report.xlsx` exports.
- IndexNow project queues with encrypted keys, 10,000-URL batches, cancellation, and aggregate XLSX reporting.
- One-time replacement of IndexNow queues from completed project sitemap CSV exports.
- Local and production deployment configuration for the API, Telegram bot, Redis, PostgreSQL, workers, and Caddy.

### Changed

- The public roadmap now separates completed sitemap and Yandex Webmaster workflows from planned integrations.
