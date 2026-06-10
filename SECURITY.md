# Security Policy

## Reporting a vulnerability

If you find a security issue, please do not open a public issue with exploit details.

Instead, report it privately to the maintainer first so the issue can be reviewed and fixed before public disclosure.

When reporting a vulnerability, please include:

- a short description of the issue
- affected area or file
- steps to reproduce
- potential impact
- suggested mitigation, if known

## Scope

Security-sensitive areas may include:

- Telegram bot tokens and webhook configuration
- database and Redis configuration
- production deployment files
- file export and storage behavior
- external API integrations

## Secrets

Do not commit real tokens, passwords, or production environment files to the repository.
