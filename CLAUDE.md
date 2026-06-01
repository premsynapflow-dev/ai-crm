# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**SynapFlow** is an AI-powered complaint intelligence platform that ingests customer feedback from multiple channels (API, Email, WhatsApp, Voice), classifies and analyzes complaints, generates AI-suggested replies, and automates routing and escalation workflows. The system is optimized for simplicity and speed, with all processing occurring in a single FastAPI process using PostgreSQL-backed job queues (no Redis required, but optionally supported).

**Stack:**
- Backend: FastAPI + SQLAlchemy ORM + PostgreSQL (Supabase)
- Frontend: Next.js 16 with Tailwind CSS, static export
- AI: Google Gemini API for classification and reply generation (OpenAI key accepted but Gemini is primary)
- Billing: Razorpay for payments
- Deployment: Railway or Render

## Build & Setup Commands

### Install Dependencies
```bash
pip install -r requirements.txt
```

### Environment Setup
```bash
cp .env.example .env
# Edit .env — required: DATABASE_URL, SECRET_KEY, GEMINI_API_KEY
```

### Run Migrations
```bash
alembic upgrade head  # Preferred — for all newer migrations
# Legacy scripts (migrate_*.py) are preserved for historical reference only
```

### Start Development Server
```bash
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

**OR** use the production wrapper (builds frontend, runs migrations, starts uvicorn):
```bash
bash start.sh
```

### Start Background Worker (Standalone)
```bash
SERVICE_TYPE=worker bash start.sh
# OR
python worker_standalone.py
```

## Testing Commands

```bash
python -m unittest discover -s tests           # All tests
python -m pytest tests/ --cov=app --cov-report=html   # With coverage
python -m unittest tests.test_ai_reply_flow    # Single file
python -m unittest tests.test_ai_reply_flow.TestAIReplyFlow.test_method_name  # Single method
python -m pytest tests/test_ai_reply_flow.py -v       # Via pytest
```

## Code Quality

```bash
flake8 app/ --max-line-length=120 --extend-ignore=E203
black app/ tests/
isort app/ tests/ --profile=black
pre-commit run --all-files
```

## Frontend Development

```bash
cd frontend && npm install && npm run build   # Build static export
cd frontend && npm run dev                   # Dev server at http://localhost:3000
cd frontend && npm run lint
```

## High-Level Architecture

### 1. Data Flow: Complaint Ingestion to Resolution

```
Customer Input (API/Email/WhatsApp/Voice)
    ↓
[Webhook Router] - Validates API key, sanitizes input, deduplicates via external ID hash
    ↓
[Classifier] - Gemini AI: intent, category, sentiment, urgency, priority, confidence
    ↓
[Sentiment Analyzer] - 1-5 score + emotional indicators (used for escalation priority)
    ↓
[Routing Service] - Assigns to team/user based on capacity & per-client rules
    ↓
[SLA Manager] - Sets sla_due_at and tat_due_at (RBI compliance)
    ↓
[Escalation Engine] - Monitors for breach, applies escalation rules
    ↓
[Reply Generator] - Drafts AI response: auto-approve (>0.85), HITL review (0.60–0.85), discard (<0.60)
    ↓
[Job Queue] - Enqueues send_email, send_slack, sync_integration tasks
    ↓
[Background Worker] - Processes queue every 30 seconds
    ↓
Customer Response
```

### 2. Core Services & Responsibilities

**Complaint Ingestion (`app/intake/webhook.py`)**
- Validates `x-api-key`, sanitizes input, generates stable `ticket_id` and `thread_id`
- Tracks usage against billing plan; enforces hard/soft limits
- Dispatches to classification pipeline

**Classification (`app/intelligence/classifier.py`)**
- Uses Gemini API with per-client prompts built by `app/intelligence/prompt_builder.py`
- Returns: intent, category, sentiment, urgency_score, priority, recommended_action, confidence
- Normalizes output to prevent hallucination; falls back to defaults on API failure
- Circuit breaker at `app/utils/circuit_breaker.py` with exponential backoff (tenacity)

**Routing (`app/services/routing_service.py`)**
- Loads RoutingRule per client; assigns to team by category + priority
- Rebalances workload (assigns to user with fewest active tasks)
- Respects existing assignments unless `force_rebalance=True`

**SLA & TAT Management (`app/services/sla_manager.py`)**
- SLA: high=4h, medium=24h, low=72h
- TAT: default 30 days for RBI-regulated clients (configurable via RBI_TAT_DEFAULT_DAYS)
- Background worker polls for breaches every `SLA_MONITOR_INTERVAL_MINUTES` (default: 10)

**Reply Generation (`app/services/reply_generator.py`, `app/intelligence/reply_engine.py`)**
- Fetches similar resolved complaints, generates draft via Gemini
- Auto-approve > REPLY_AUTO_APPROVE_THRESHOLD (0.85), human review 0.60–0.85, discard below
- Hardened flow at `app/services/auto_reply_hardened.py`

**Job Queue (`app/queue/worker.py`)**
- Backend auto-selected by QUEUE_BACKEND: `auto` (postgres), `postgres`, or `redis`
- Worker thread starts on FastAPI startup, processes every 30 seconds
- Disable with `DISABLE_BACKGROUND_WORKERS=1`

**Escalation (`app/services/escalation_engine.py`)**
- Levels: L0 (none), L1 (4h), L2 (24h), IO (legal/compliance)
- Triggers: SLA breach, sentiment spike, manual escalation rules

**Inboxes (`app/inboxes/`, `app/services/inbox_poller.py`)**
- Connects Gmail/IMAP accounts as shared inboxes
- OAuth via `GOOGLE_INBOXES_OAUTH_REDIRECT_URI`; credentials encrypted with `CHANNEL_CRYPTO_KEY`
- Inbound email routed as complaints via the standard pipeline

**Chatbot (`app/intelligence/chatbot.py`, `app/api/chatbot.py`)**
- Customer-facing AI chat interface powered by Gemini
- Resolves queries using complaint history and knowledge base

### 3. Key Patterns & Conventions

**API Structure**
- `/webhook/*` — Complaint ingestion (no JWT; API key in `x-api-key` header)
- `/api/v1/*` — Client-facing REST API (JWT required)
- `/api/admin/*` — Admin endpoints (HTTP Basic Auth: ADMIN_USERNAME / ADMIN_PASSWORD)
- `/integrations/*` — Third-party webhooks (Gmail, WhatsApp, Email, Voice)
- `/auth/*` — Session auth and OAuth callbacks (`app/api/session_auth.py`)

**Middleware Stack** (in `app/main.py`, applied in this order)
1. `RLSContextMiddleware` — Multi-tenant Row-Level Security context
2. `FeatureGateMiddleware` — Feature flagging per client
3. `SecurityHeadersMiddleware` — CSP, X-Frame-Options, etc.
4. `DatabaseRateLimitMiddleware` — Rate limiting stored in DB
5. `RequestAuditMiddleware` — Audit logs for all requests
6. `request_logging` — Request/response timing + metrics

**Startup Behavior**
- `app/db/schema_guard.py` (`ensure_schema()`) runs on startup to verify DB schema unless `DISABLE_SCHEMA_GUARD=1`
- Background worker thread starts unless `DISABLE_BACKGROUND_WORKERS=1`
- Sentry initialized automatically if `SENTRY_DSN` is set and `ENVIRONMENT != dev`

**Service Locator Pattern**
- DB session injected via `Depends(get_db)` from `app/dependencies/auth.py`
- Services instantiated per-request: `RoutingService(db).route_ticket(complaint, classification)`

**Classification Config Per Client**
- Default config in `app/intelligence/prompt_builder.DEFAULT_CONFIG`
- Client override stored in `Client.custom_prompt_config` (JSON), merged at runtime
- Supports: tone, focus_areas, industry, classification_rules, escalation_rules

**Billing & Usage (`app/billing/usage.py`)**
- Trial: free, 50 tickets, 7-day expiry — hard limit on breach
- Pro: ₹4,999/mo, 1,000 tickets, ₹8/overage — soft limit, accrues overage
- Business: ₹14,999/mo, 5,000 tickets, ₹4/overage

**Auth: Two Parallel Systems**
- JWT tokens (`app/api/v1/auth.py`): `JWT_SECRET_KEY` (defaults to SECRET_KEY), `ACCESS_TOKEN_EXPIRE_MINUTES` (60), `REFRESH_TOKEN_EXPIRE_DAYS` (30)
- Session cookies (`app/api/session_auth.py`): used by the Portal UI

**Testing Setup (`tests/conftest.py`)**
- `conftest.py` automatically sets `DISABLE_BACKGROUND_WORKERS=1` and `DISABLE_SCHEMA_GUARD=1`
- SQLite in-memory DB; session overrides patch all middleware that hold their own `SessionLocal`
- Adding new middleware that caches `SessionLocal` at import time requires a conftest patch

### 4. Database Schema Highlights

**Complaints** — core fields: `id`, `client_id`, `summary`, `source` (api/email/whatsapp/voice)
- Classification: `category`, `intent`, `sentiment`, `urgency_score`, `priority`, `confidence`
- Assignment: `team_id`, `assigned_user_id`
- State machine: `status`, `state` (NEW → ASSIGNED → IN_PROGRESS → RESOLVED/REOPENED)
- SLA: `sla_due_at`, `sla_status` (on_track/breached)
- RBI: `rbi_category_code`, `tat_due_at`, `tat_status`
- Reply: `ai_reply`, `ai_reply_confidence`, `ai_reply_status` (pending/approved/rejected/sent)

**Multi-tenancy** — `Client` is the root tenant (UUID PK). RLS not enforced by default; set `ENABLE_RLS=true` for strict SQL-level isolation.

**Escalation** — `EscalationLevelDefinition` per client; `EscalationRule` defines triggers; `escalation_level_definitions` relationship on `Client`.

**AIReplyQueue** — HITL queue: pending → approved → sent OR rejected. Agents review in Portal.

**RBIComplaint** — Regulatory tracking: `rbi_category_code`, `tat_due_at`, `tat_breached_at`. MIS aggregation via `app/services/rbi_compliance.py`.

## Environment Variables

**Required:**
- `DATABASE_URL` — PostgreSQL connection (Supabase format)
- `SECRET_KEY` — JWT/session secret (min 32 chars)
- `GEMINI_API_KEY` — Google Gemini API key

**Auth & Security:**
- `ADMIN_USERNAME` / `ADMIN_PASSWORD` — Admin API HTTP Basic Auth (min 8 chars)
- `JWT_SECRET_KEY` — Separate JWT secret (defaults to SECRET_KEY)
- `ACCESS_TOKEN_EXPIRE_MINUTES` (default: 60), `REFRESH_TOKEN_EXPIRE_DAYS` (default: 30)
- `CHANNEL_CRYPTO_KEY` — Encrypts stored OAuth tokens for Gmail inboxes

**Infrastructure:**
- `ENVIRONMENT` — dev/staging/prod (default: dev)
- `APP_BASE_URL` — Base URL for OAuth redirects (default: http://127.0.0.1:8000)
- `QUEUE_BACKEND` — auto/postgres/redis (default: auto → postgres)
- `REDIS_URL` — Redis connection, used when QUEUE_BACKEND=redis
- `WEB_CONCURRENCY` — uvicorn worker count (Railway/Render)
- `SENTRY_DSN` — Sentry error tracking (auto-enabled when set and ENVIRONMENT != dev)

**Integrations:**
- `SLACK_WEBHOOK_URL` — Slack notifications
- `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, `SMTP_FROM` — Email sending
- `INBOUND_EMAIL_DOMAIN`, `INBOUND_EMAIL_WEBHOOK_SECRET` — Inbound email routing
- `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET` — Gmail OAuth
- `GOOGLE_INBOXES_OAUTH_REDIRECT_URI`, `GOOGLE_INTEGRATIONS_OAUTH_REDIRECT_URI` — Gmail OAuth callbacks
- `GMAIL_PUBSUB_TOPIC`, `GMAIL_WATCH_LABEL_IDS` — Gmail Push Notifications
- `WHATSAPP_APP_SECRET`, `WHATSAPP_VERIFY_TOKEN`, `WHATSAPP_DEFAULT_API_VERSION` (default: v22.0)
- `RAZORPAY_KEY_ID`, `RAZORPAY_KEY_SECRET`, `RAZORPAY_WEBHOOK_SECRET`

**Tuning:**
- `ENABLE_RLS` — Row-level security enforcement (default: false)
- `REPLY_AUTO_APPROVE_THRESHOLD` — Min confidence for auto-send (default: 0.85)
- `REPLY_HUMAN_REVIEW_THRESHOLD` — Min confidence for HITL queue (default: 0.60)
- `SLA_MONITOR_INTERVAL_MINUTES` — SLA breach check frequency (default: 10)
- `RBI_TAT_DEFAULT_DAYS` — Default TAT for RBI complaints (default: 30)
- `REQUEST_LOG_RETENTION_DAYS` — Audit log cleanup (default: 30)
- `DISABLE_BACKGROUND_WORKERS=1` — Disable worker thread (auto-set in tests)
- `DISABLE_SCHEMA_GUARD=1` — Skip schema validation on startup (auto-set in tests)

## Deployment

**Railway:** `railway.json` included. Start command: `bash start.sh`. Set all env vars in dashboard.

**Render:** `render.yaml` included.

**Health Checks:**
```bash
curl http://localhost:8000/health       # DB connection
curl http://localhost:8000/health/db    # DB-specific
curl http://localhost:8000/health/ai    # Gemini API
```

## Important Notes

- **Queue backend:** PostgreSQL by default; Redis available via `QUEUE_BACKEND=redis`. The worker runs as a thread inside FastAPI — move to dedicated process (`worker_standalone.py`) for scale.
- **Schema evolution:** Use Alembic for all new migrations. The `migrate_*.py` scripts are legacy.
- **Frontend:** Next.js static export. Built by `start.sh` if `frontend/out/` is missing. FastAPI serves it via catch-all route.
- **Test DB:** SQLite in-memory — not PostgreSQL. Any middleware caching `SessionLocal` at module level must be patched in conftest.

## Key File Organization

- `app/main.py` — FastAPI app: middleware, router includes, startup hooks
- `app/config.py` — All settings with Pydantic validation (`get_settings()`)
- `app/db/models.py` — All SQLAlchemy ORM models
- `app/db/schema_guard.py` — Startup schema verification
- `app/intake/webhook.py` — Complaint ingestion, validation, dispatch
- `app/intelligence/classifier.py` — Gemini classification
- `app/intelligence/chatbot.py` — Customer-facing AI chat
- `app/services/` — Core business logic (routing, SLA, escalation, replies, RBI)
- `app/api/v1/` — REST API endpoints (tickets, complaints, teams, reply_queue, etc.)
- `app/queue/worker.py` — Job queue + background worker
- `app/middleware/` — Request/response middleware
- `app/integrations/` — Third-party webhooks (Gmail, WhatsApp, Email, Voice)
- `app/inboxes/` — Managed inbox connections (Gmail/IMAP OAuth)
- `app/billing/` — Plan enforcement, Razorpay, usage tracking
- `app/analytics/` — Customer pulse and performance analytics
- `tests/conftest.py` — Test fixtures, SQLite override, middleware patching
- `alembic/` — Database migrations
- `frontend/` — Next.js frontend (static export to `frontend/out/`)
