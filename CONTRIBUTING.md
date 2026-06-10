# Contributing

Thanks for your interest in contributing to SEO Automation Orchestrator.

## What to contribute

Useful contributions include:

- crawler improvements and bug fixes
- new SEO workflow modules
- Telegram bot UX improvements
- API and background task improvements
- tests, docs, and deployment improvements

## Before you start

Please open an issue first for:

- large feature additions
- architectural changes
- new external integrations

This helps keep the project direction consistent and avoids duplicated work.

## Local setup

1. Clone the repository.
2. Create and activate a virtual environment.
3. Install dependencies:

```bash
pip install -e .
```

4. Copy environment variables:

```bash
cp .env.example .env
```

5. Start local infrastructure if needed:

```bash
docker compose up -d
```

## Development notes

- Use ASCII by default unless the file already uses Unicode.
- Keep changes focused and small when possible.
- Prefer clear naming and straightforward code over clever abstractions.
- Update docs when behavior changes.

## Pull requests

Please make sure your pull request:

- explains the problem being solved
- describes the approach briefly
- mentions any user-facing changes
- includes tests or manual verification notes when relevant

If your change affects bot behavior, crawler output, or deployment, include a short testing note.
