# Roadmap

This roadmap reflects the current direction of SEO Automation Orchestrator. Each module should provide a usable workflow on its own and become a reusable source of data for later modules.

## Current Foundation

Already implemented:

- project management through API and Telegram bot
- phone-based bot access control and root-admin tools
- asynchronous task execution with Redis and RQ
- standard and heavy crawl modes with checkpoints and partial results
- CSV and XLSX crawl exports, including relative-link diagnostics
- sitemap parsing from projects, direct URLs, and `robots.txt`
- sitemap CSV and XLSX exports with optional status-code checks
- sitemap-to-Yandex-queue transfer for saved projects
- Yandex Webmaster recrawl queues, cancellation, live progress, and aggregate XLSX reporting
- encrypted storage for a manually issued shared Yandex OAuth token
- IndexNow queues with encrypted per-project keys, batched submission, cancellation, and aggregate XLSX reporting
- structured logs and a production deployment stack for API, webhook bot, workers, Redis, PostgreSQL, and Caddy

## Next Release

### Google Indexing API

The next release is focused on a policy-aware Google Indexing API workflow.

Expected scope:

- service-account connection and credential handling
- URL submission and removal workflows allowed by Google's API policy
- queue-based execution, status tracking, and XLSX reporting
- clear interface messaging about the limited eligible content types

## Planned Module Sequence

1. Google Indexing API integration
2. Audit workflows based on collected data
3. Yandex Metrica API integration
4. Extended Yandex Webmaster and Google Search Console workflows

## Completed Modules

### Sitemap Parsing

Delivered:

- parse sitemap files and sitemap indexes
- launch sitemap workflows through Telegram
- export URL sets as CSV and XLSX
- prepare project sitemap URLs for Yandex recrawl queues

### Yandex Webmaster Recrawl

Delivered:

- submit project URL queues for recrawl
- preserve unsubmitted URLs after quota or API errors
- provide live progress and aggregate XLSX reports
- use an encrypted manually issued OAuth token

### IndexNow

Delivered:

- store an encrypted key and optional key-file URL for each project
- submit file-backed CSV queues with manual priority insertion
- send batches of up to 10,000 URLs through Yandex's IndexNow endpoint
- preserve failed batches and provide cancellation and aggregate XLSX reports

Next improvement:

- keep a sitemap snapshot per project and add only new or materially changed URLs to IndexNow queues after later sitemap parses

## Planned Capabilities By Module

### 1. Google Indexing API

Goals:

- submit and remove URLs where the API policy allows it
- support operational indexing workflows from the same platform

### 2. Audit Workflows

Goals:

- combine crawl, sitemap, and indexing data
- surface practical technical SEO issues
- prepare reusable datasets for analysis and reporting

### 3. Yandex Metrica API

Goals:

- retrieve traffic and behavior data needed for SEO analysis
- connect performance metrics with crawl and indexing data
- support later reporting and dashboard workflows

### 4. Extended Webmaster And Search Console Workflows

Goals:

- retrieve index and coverage data for pages
- support additional Yandex Webmaster operations, including removals
- connect Google Search Console data to future audit workflows

## Direction

The long-term direction is to move from a crawler-centered foundation toward a broader operational SEO platform where crawl, sitemap, indexing, audit, and reporting workflows run from one system.
