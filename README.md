# SEO Automation Orchestrator

Modular platform for technical SEO automation: crawling, sitemap processing, indexing workflows, audits, and reporting through API, background workers, and Telegram-based orchestration.

## Why This Exists

This project comes out of more than 10 years of practical SEO work.

Over that time, I developed a specific approach to running, analyzing, and maintaining websites from a technical SEO perspective. I wrote many separate Python automations for individual tasks, but eventually the real need became obvious: an all-in-one platform with a minimal interface and an architecture that makes new tools easy to add.

I postponed this work for a long time because of its scope. Building a platform like this used to feel too large to start. With Codex, creating and expanding larger applications is far more realistic.

## What It Is

SEO Automation Orchestrator is a task-driven backend platform for running technical SEO operations in a controlled way.

The project is built around a simple idea:

- SEO actions are modeled as tasks
- tasks are executed asynchronously by workers
- orchestration happens through Telegram and API
- new tools are added as modules, not as one-off scripts

This repository is not just a crawler. Crawling is the first substantial workflow already implemented, but the architecture is designed to support a broader SEO operations stack.

At its core, the application is a combination of tools exposed through a Telegram bot interface. You can use the toolset that ships with the project, or extend the platform with your own workflows and modules.

## Who This Is For

SEO Automation Orchestrator is intended for people and teams who treat technical SEO as an operational discipline rather than a set of isolated checks.

It is especially relevant for:

- technical SEO specialists who need repeatable workflows for crawl, indexing, and audit tasks
- in-house SEO teams managing medium and large websites
- agencies working with multiple client projects and recurring technical checks
- operators who want lightweight task control through Telegram instead of a complex internal panel
- developers who want to extend a modular SEO backend with their own tools and workflows

The project is designed for practical use in real environments where SEO work includes recurring operations, long-running tasks, partial results, and the need to combine multiple data sources.

## Current Capabilities

The project already includes:

- project management through API and Telegram bot
- task creation and queue-based execution
- site crawling with configurable depth, concurrency, page limits, and robots handling
- separate crawl queues for standard and heavy websites
- sitemap-oriented project setup
- launch tracking and task status reporting in Telegram
- partial result checkpoints for long-running crawl tasks
- CSV and XLSX export for crawl results

## Planned Capabilities

The platform is intended to grow into a broader SEO automation system, including:

- sitemap parsing and sitemap QA
- interaction with the Yandex Webmaster API, including index status retrieval and URL submission
- URL submission and removal flows through the Google Indexing API
- interaction with Google Search Console
- technical audits based on collected crawl and indexing data
- export pipelines for reporting data
- chart generation for reports
- more operational tooling exposed through Telegram and API

## SEO Crawler

The existing SEO crawler in this project is built on Python `asyncio`.

This matters because crawling is one of the most common technical SEO workflows, yet many tools on the market are still distributed as desktop applications with inconvenient interfaces and limited platform support.

The crawler currently supports two execution modes:

### Standard Mode

Standard mode is intended for smaller websites that are not heavily loaded.

It uses the following settings:

- crawl depth
- concurrency
- maximum page limit
- whether to follow `robots.txt` rules

### Heavy Mode

Heavy mode is intended for large catalogs and websites that operate under meaningful load, where crawling should avoid negatively affecting production behavior.

In addition to the core crawl settings, heavy mode includes:

- delay between requests
- request timeout
- retry on `5xx` responses
- stop threshold for `5xx` responses
- retry delay

Heavy mode also runs in a separate queue so large crawls do not block smaller routine tasks.

At the moment, the crawler collects:

- HTTP status code
- page URL
- page title
- meta description
- source URL
- final URL after redirects
- canonical URL
- meta robots
- content type

The data model can be extended without much difficulty, especially if you are using Codex to accelerate implementation.

## Why Telegram

Telegram is a familiar and widely used platform. It provides a practical interface layer without forcing the project into a custom frontend too early.

This choice solves several problems common in SEO tooling:

- no separate application has to be purchased, installed, or maintained
- many SEO crawlers on the market are tied to a single operating system, often Windows
- desktop-only tools are inconvenient or unusable on mobile devices
- SaaS interfaces are often overloaded and awkward to use on mobile

Telegram helps avoid these issues:

- it provides a straightforward API surface for implementing operational features
- it removes the need to design, build, and maintain a dedicated frontend
- it is built to handle significant scale
- a bot interface keeps common workflows simple
- it works well on both desktop and mobile devices

## Architecture Overview

The codebase follows a modular monolith approach with clear boundaries between business logic and interfaces.

This architecture was chosen to keep the platform easy to extend without turning every new SEO workflow into a separate service too early. The goal is to support many tools inside one coherent backend while preserving clear module boundaries.

Core direction of dependencies:

```text
interfaces -> application -> domain
```

Principles:

- business logic lives inside modules
- Telegram, API, and workers orchestrate flows but do not own domain rules
- long-running operations are executed as tasks
- infrastructure is replaceable and isolated from domain logic

## Execution Flow

Most workflows follow the same execution pattern:

1. a user triggers an operation through Telegram or API
2. the platform creates a task with the required payload
3. the task is placed into the appropriate queue
4. a worker executes the task asynchronously
5. progress and results are stored
6. the operator receives status updates and exported files

## Project Structure

```text
app/
  core/           # config, db, redis, storage, shared infrastructure
  interfaces/     # API, Telegram bot, worker entrypoints
  modules/        # business modules
    projects/
    tasks/
    crawl/
    sitemap/
    audit/
    indexing/
    reports/
  bootstrap/      # wiring and import utilities

migrations/       # Alembic migrations
tests/            # test suite
```

## Main Components

### API

FastAPI application for project and task operations.

### Telegram Bot

Primary operator interface for:

- launching crawl tasks
- configuring standard and heavy crawl modes
- checking task and launch status
- managing projects

### Worker

RQ worker processes asynchronous tasks from Redis-backed queues.

Current queue split:

- `crawl_default` for regular crawl tasks
- `crawl_heavy` for large or sensitive websites

## Running Locally

### 1. Prepare environment

```bash
cp .env.example .env
```

Fill in at least:

- `DATABASE_URL`
- `REDIS_URL`
- `BOT_TOKEN`

### 2. Start infrastructure

With Docker:

```bash
docker compose up -d
```

### 3. Install dependencies

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .
```

### 4. Apply migrations

```bash
alembic upgrade head
```

### 5. Run API

```bash
uvicorn app.main:app --reload
```

### 6. Run bot

```bash
python -m app.bot
```

### 7. Run workers

Standard crawl worker:

```bash
export RQ_QUEUE=crawl_default
python -m app.worker
```

Heavy crawl worker:

```bash
export RQ_QUEUE=crawl_heavy
python -m app.worker
```

## Open Source Direction

This repository is being developed as a public open-source platform for practical technical SEO automation workflows.

Its direction is to provide a modular foundation for crawling, indexing workflows, audits, and reporting without reducing the platform to a collection of disconnected scripts.

## License

MIT. See [LICENSE](./LICENSE).
