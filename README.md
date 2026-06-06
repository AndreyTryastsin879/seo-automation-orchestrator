# SEO Automation Orchestrator

Modular platform for technical SEO automation: crawling, sitemap processing, indexing workflows, audits, and reporting through API, background workers, and Telegram-based orchestration.

## What It Is

SEO Automation Orchestrator is a task-driven backend platform for running technical SEO operations in a controlled way.

The project is built around a simple idea:

- SEO actions are modeled as tasks
- tasks are executed asynchronously by workers
- orchestration happens through Telegram and API
- new tools are added as modules, not as one-off scripts

This repository is not just a crawler. Crawling is the first substantial workflow already implemented, but the architecture is designed to support a broader SEO operations stack.

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
- Yandex API workflows
- Google API workflows
- technical audits based on collected crawl and indexing data
- reporting pipelines
- more operational tooling exposed through Telegram and API

## Architecture

The codebase follows a modular monolith approach with clear boundaries between business logic and interfaces.

Core direction of dependencies:

```text
interfaces -> application -> domain
```

Principles:

- business logic lives inside modules
- Telegram, API, and workers orchestrate flows but do not own domain rules
- long-running operations are executed as tasks
- infrastructure is replaceable and isolated from domain logic

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

## Configuration Notes

Two crawl modes are supported:

- standard mode for ordinary websites
- heavy mode for large or sensitive websites

Heavy mode is intended for slower, safer execution with independent queue isolation.

## Why Telegram

Telegram is used as an operator console, not as a place for business logic.

That gives the project:

- fast operational control
- simple launch and status workflows
- a practical interface for non-technical execution scenarios

The system itself remains backend-first and can be extended through API and workers independently of Telegram.

## Open Source Direction

This repository is being prepared as a public open-source project focused on practical technical SEO automation workflows.

The goal is to provide a modular foundation for:

- crawl orchestration
- SEO task execution
- indexing workflows
- audits
- reporting

## License

MIT. See [LICENSE](./LICENSE).
