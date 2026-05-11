# CAPTCHA Automation Control Platform

Centralized Django platform for managing CAPTCHA-solving accounts, defining solving jobs, running async automation, and monitoring usage, earnings, and operational health.

## Purpose of Project

The purpose of this project is to build a centralized operational platform for CAPTCHA-solving automation. Instead of relying on fragile scripts, disconnected credentials, and manual monitoring, the platform provides one control layer for account management, job execution, observability, and earnings tracking.

The system is designed as a production-oriented foundation that can evolve into an internal enterprise tool or a commercial SaaS product.

## Product Overview

This product is a Django-based control platform backed by asynchronous workers. It allows operators to:

- manage multiple CAPTCHA provider accounts
- register target websites and CAPTCHA metadata
- create and control solving jobs
- run tasks asynchronously with Celery
- monitor solve results, balance changes, and estimated earnings
- track operational logs and withdrawal records

The current codebase is organized into modular Django apps such as `accounts`, `targets`, `captcha_jobs`, `automation`, `solver_engine`, `earnings`, `logs`, `withdrawals`, and `dashboard`.

## The Problem We Solve

Teams that rely on CAPTCHA-solving operations usually face the same problems:

- credentials are stored in scattered places and handled insecurely
- operators must manually switch between multiple provider accounts
- job execution is difficult to monitor and restart safely
- there is little visibility into balances, costs, failures, and solve performance
- scaling from one-off scripts to a reliable system is difficult
- operational risk increases when rate limits, proxies, and retries are not centrally managed

In short, traditional approaches behave like scripts, not platforms.

## Our Solution

This project provides a centralized control plane with a worker-based execution engine.

It combines:

- secure account and credential management
- structured target website configuration
- independent job lifecycle control
- async task execution with Celery
- provider integration through a solver service
- earnings and balance tracking
- structured logs and API call records
- optional withdrawal management

The goal is to make CAPTCHA automation manageable like a real operations platform instead of an ad hoc bot system.

## Business Architecture

The business architecture centers on three layers:

1. Control Layer
   Admin users configure providers, accounts, targets, jobs, and withdrawals.
2. Execution Layer
   Celery workers execute solve tasks asynchronously and independently from the web request cycle.
3. Observability Layer
   Logs, executions, earnings, and balance snapshots provide visibility into performance and risk.

High-level flow:

`Operator` -> `Django control panel / API` -> `PostgreSQL + Redis + Celery workers` -> `2Captcha / target websites / proxy infrastructure`

## Platform Structure

The active Django apps are:

- `core`: shared middleware and exception handling
- `common`: encryption, pagination, and CAPTCHA client utilities
- `accounts`: provider accounts and audit logging
- `targets`: target website and proxy configuration
- `captcha_jobs`: job definitions and execution records
- `solver_engine`: provider-facing solve orchestration
- `automation`: background tasks and job execution control
- `earnings`: earnings, transaction, and balance tracking
- `logs`: platform logs and external API call logs
- `withdrawals`: withdrawal methods and withdrawal records
- `dashboard`: metrics view and dashboard endpoints

Key entry points:

- [config/urls.py](/home/mostasim/python/captcha_platform/config/urls.py)
- [config/settings/base.py](/home/mostasim/python/captcha_platform/config/settings/base.py)
- [automation/tasks.py](/home/mostasim/python/captcha_platform/automation/tasks.py)
- [solver_engine/services.py](/home/mostasim/python/captcha_platform/solver_engine/services.py)

## Core Features

- encrypted credential storage for CAPTCHA provider accounts
- support for multiple service providers with 2Captcha currently wired
- target website storage including CAPTCHA type, site key, selectors, and browser metadata
- proxy configuration with single or rotating proxy lists
- continuous or one-time job execution modes
- async solve execution with Celery task orchestration
- job start, pause, stop, and restart actions
- execution-level result tracking through `JobExecution`
- earnings aggregation through daily earnings and transaction records
- structured platform and API call logging
- withdrawal tracking for payout operations
- dashboard summary endpoint for operations visibility

## Business Model

This project can support multiple business models depending on how it is deployed:

- Internal Operations Platform
  Used by a single company to manage solving operations efficiently.
- Managed Service
  A team operates the platform on behalf of clients and bills based on usage.
- SaaS Platform
  Multiple customers manage accounts, jobs, and reporting through a hosted product.

Potential revenue levers include:

- subscription plans
- usage-based billing by solve volume
- premium monitoring and analytics
- multi-account orchestration and proxy management features

## Business Roadmap

Suggested roadmap:

1. Foundation
   Stabilize models, migrations, admin workflows, and core APIs.
2. Operations Readiness
   Improve worker reliability, proxy rotation, retries, alerting, and runtime metrics.
3. Product Readiness
   Expand dashboards, user permissions, and reporting workflows.
4. SaaS Readiness
   Introduce tenant isolation, billing, customer-facing APIs, and subscription logic.

## Technology Architecture

Current and intended architecture:

- Backend: Django
- API Layer: Django REST Framework
- Queue/Workers: Celery
- Broker/Backend: Redis
- Database: PostgreSQL in production, SQLite fallback for local development
- Browser Automation: Playwright
- CAPTCHA Provider Integration: 2Captcha via client abstraction
- Logging: Django logging plus structured log models
- Admin/Dashboard: Django admin and dashboard views

Important settings and environment-driven behavior are defined in [config/settings/base.py](/home/mostasim/python/captcha_platform/config/settings/base.py).

## Database Schema

The main domain models currently include:

### Accounts

Defined in [accounts/models.py](/home/mostasim/python/captcha_platform/accounts/models.py):

- `CaptchaServiceProvider`
- `CaptchaAccount`
- `AccountAuditLog`

### Targets

Defined in [targets/models.py](/home/mostasim/python/captcha_platform/targets/models.py):

- `TargetWebsite`
- `ProxyConfiguration`

### Jobs

Defined in [captcha_jobs/models.py](/home/mostasim/python/captcha_platform/captcha_jobs/models.py):

- `CaptchaJob`
- `JobExecution`

### Earnings

Defined in [earnings/models.py](/home/mostasim/python/captcha_platform/earnings/models.py):

- `DailyEarning`
- `EarningTransaction`
- `BalanceSnapshot`

### Logs

Defined in [logs/models.py](/home/mostasim/python/captcha_platform/logs/models.py):

- `LogEntry`
- `ApiCallLog`

### Withdrawals

Defined in [withdrawals/models.py](/home/mostasim/python/captcha_platform/withdrawals/models.py):

- `WithdrawalMethod`
- `Withdrawal`

## MVP Development Plan

Recommended MVP milestones:

1. Complete migrations for the normalized model layer.
2. Validate all CRUD flows for accounts, targets, jobs, earnings, logs, and withdrawals.
3. Finalize Celery worker execution with real Redis connectivity.
4. Add authenticated API tests for critical job lifecycle actions.
5. Improve dashboard summaries and operational charting.
6. Harden 2Captcha error handling, balance refresh, and retry logic.
7. Add production deployment configuration for worker and web services.

## User Journeys

### Operator Journey

1. Create a CAPTCHA provider entry.
2. Add one or more encrypted CAPTCHA accounts.
3. Register a target website and optional proxy configuration.
4. Create a solving job and select its execution mode.
5. Start the job from the API or dashboard.
6. Monitor solve executions, logs, balances, and earnings.
7. Pause, stop, or restart the job when required.

### Admin Journey

1. Review account health and provider balances.
2. Inspect failed executions and API error logs.
3. Audit credential and operational changes.
4. Review earnings and withdrawal activity.

## Competitive Advantages

- modular Django app architecture that is easier to evolve than script-based tooling
- encrypted sensitive credentials at rest
- separation between control plane and execution layer
- extensible provider abstraction for future CAPTCHA vendors
- built-in operational tracking for logs, earnings, balances, and job executions
- clearer path toward multi-tenant SaaS evolution than a typical automation script stack

## Investment Requirements

To move this project from baseline platform to production-grade offering, the main investments are:

- backend engineering for migrations, testing, and worker hardening
- infrastructure for PostgreSQL, Redis, worker hosting, and observability
- QA and staging environments
- product design for dashboard and user-facing workflows
- security review for credentials, secrets handling, and access control

## Risk Management

Key risks and mitigations:

- Dependency Risk
  Missing runtime packages can block startup locally.
  Mitigation: enforce locked dependencies and reproducible environments.
- Execution Risk
  Long-running jobs may fail if worker orchestration is weak.
  Mitigation: improve retries, heartbeats, task monitoring, and graceful stop logic.
- Provider Risk
  External CAPTCHA APIs may change or fail.
  Mitigation: use provider abstraction and structured API logging.
- Security Risk
  Sensitive credentials require strong handling.
  Mitigation: keep encryption keys in environment variables and minimize plaintext exposure.
- Scaling Risk
  Single-node assumptions may break under load.
  Mitigation: keep job execution async and design for horizontal worker scaling.

## Long-term Vision

The long-term vision is to turn this into a full automation operations platform with:

- multiple provider integrations
- tenant-aware access control
- richer dashboards and alerting
- billing and subscriptions
- customer-facing APIs
- stronger analytics on solve performance and cost efficiency

The platform should eventually support both internal operations teams and hosted customer environments.

## Contributing

Recommended contribution flow:

1. Create or update the virtual environment.
2. Install dependencies from `requirements.txt`.
3. Keep settings driven by `.env`.
4. Run migrations after model changes.
5. Validate syntax and Django checks before opening changes.

Useful commands:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python3 manage.py makemigrations
python3 manage.py migrate
python3 manage.py runserver
celery -A config worker -l info
python3 -m compileall accounts automation captcha_jobs common config core dashboard earnings logs solver_engine targets withdrawals manage.py
```

Note: `python3 manage.py check` requires the Django dependencies to be installed in the active environment.

## Product Manager Notes

- This repository should be treated as a platform foundation, not a finished SaaS.
- The README should stay aligned with the actual code structure, not only the target vision.
- The highest-value next deliverables are migrations, automated tests, runtime validation, and production deployment hardening.
- Future product documentation can be split into technical docs, operator docs, and commercial/product strategy docs once the platform matures.
