# Roadmap

This roadmap reflects the current intended direction of SEO Automation Orchestrator.

The project is being built as a modular SEO operations platform, so each release is meant to add a practical workflow that can be used on its own and later combined with other modules.

## Current Foundation

Already implemented:

- project management through API and Telegram bot
- asynchronous task execution with Redis and RQ
- standard and heavy crawl modes
- launch tracking and task status reporting
- partial crawl checkpoints
- CSV and XLSX export for crawl results
- production deployment stack for API, webhook bot, and workers

## Next Release

### Sitemap parsing in the interface

The next release is focused on sitemap parsing exposed through the existing interface layer.

Expected scope:

- run sitemap parsing as an operator workflow
- return results through the Telegram interface
- support practical sitemap inspection and validation tasks
- prepare sitemap data for later audit and indexing workflows

## Planned Module Sequence

The current planned order of upcoming modules is:

1. Sitemap parsing in the interface
2. Yandex Webmaster API integration
3. Google Indexing API integration
4. IndexNow API integration
5. Audit workflows based on collected data
6. Yandex Metrica API integration

## Planned Capabilities By Module

### 1. Sitemap parsing

Goals:

- parse sitemap files and sitemap indexes
- expose sitemap workflows through Telegram
- prepare URL sets for audits and indexing operations
- support sitemap QA and coverage checks

### 2. Yandex Webmaster API

Goals:

- retrieve index-related data for pages
- submit URLs when needed
- use Yandex data later in audit workflows

### 3. Google Indexing API

Goals:

- submit URLs for indexing
- request URL removal when relevant
- support operational indexing workflows from the same platform

### 4. IndexNow API

Goals:

- submit URL updates to supported engines
- reduce the need for separate one-off scripts
- keep indexing workflows unified inside the platform

### 5. Audit workflows

Goals:

- combine crawl, sitemap, and indexing data
- surface practical technical SEO issues
- prepare reusable datasets for analysis and reporting

### 6. Yandex Metrica API

Goals:

- retrieve traffic and behavior data needed for SEO analysis
- connect performance metrics with crawl and indexing data
- support later reporting and dashboard workflows

## Direction

The long-term direction of the project is to move from a crawler-centered foundation toward a broader operational SEO platform where crawl, sitemap, indexing, audit, and reporting workflows can be run from one system.
