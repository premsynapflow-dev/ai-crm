# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**SynapFlow** is an AI-powered complaint intelligence platform that ingests customer feedback from multiple channels (API, Email, WhatsApp, Voice), classifies and analyzes complaints, generates AI-suggested replies, and automates routing and escalation workflows. The system is optimized for simplicity and speed, with all processing occurring in a single FastAPI process using PostgreSQL-backed job queues (no Redis required, but optionally supported).

**Stack:**
- Backend: FastAPI + SQLAlchemy ORM + PostgreSQL (Supabase)
- Frontend: **Vite 6 + React 18** with Tailwind CSS v4, static export served by FastAPI. Router: react-router v7. Component library: Radix UI + shadcn/ui. Charts: Recharts. Toasts: Sonner. Icons: lucide-react. HTTP: native `fetch` via custom `request()` wrapper in `frontend/src/app/lib/api.ts` (NOT Axios, NOT Next.js).
- AI: Google Gemini API for classification and reply generation — called via direct **httpx** HTTP (NOT the `google-generativeai` SDK, which is intentionally absent from requirements.txt)
- Voice: Deepgram (transcription) + ElevenLabs (synthesis) — lazy-imported only when `DEEPGRAM_API_KEY` / `ELEVENLABS_API_KEY` are set
- Billing: Razorpay for payments; Resend for transactional email (fallback: SMTP)
- Deployment: Railway (primary) or Render

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
python worker_standalone.py   # respects WORKER_INTERVAL env (default: 10s)
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
cd frontend && npm install && npm run build   # Build static export (Vite → frontend/out/)
cd frontend && npm run dev                   # Dev server at http://localhost:5173
```

**Important:** The frontend uses **Vite 6**, **React 18**, and **react-router v7**. There is no Next.js, no `pages/` directory, and no `next export`. The build output is `frontend/out/` (static HTML/JS/CSS), served by FastAPI's catch-all route.

## High-Level Architecture

### 1. Data Flow: Complaint Ingestion to Resolution

```
Customer Input (API/Email/WhatsApp/Voice)
    ↓
[Webhook Router] - Validates API key, sanitizes input, deduplicates via external ID hash
    ↓
[Unified Ingestion] - Normalizes to UnifiedMessage + Conversation thread grouping
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
[Workflow Engine] - Evaluates automation rules, dispatches actions
    ↓
[Job Queue] - Enqueues send_email, send_slack, sync_integration, process_workflow_action tasks
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

**Unified Message Ingestion (`app/services/unified_ingestion.py`)**
- Normalizes messages from all channels into `UnifiedMessage` + `Conversation` tables
- Groups by `external_thread_id` + channel + `client_id` for conversation threading
- Uses PostgreSQL upsert (`on_conflict_do_update`) to prevent duplicates
- `conversation_threads.py` resolves which `Complaint` a conversation thread belongs to

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
- `ReplyConfidenceScorer` (`app/services/reply_confidence_scorer.py`) — multi-factor scoring: semantic similarity, sentiment alignment, length
- `reply_ab_tests` table supports A/B testing AI replies against templates
- Agent feedback stored in `reply_feedback` table for future fine-tuning
- **Auto AI Reply toggle** — per-client setting in `client.custom_prompt_config["notification_preferences"]["auto_ai_reply"]` (default: `true`). When `true`, reply is generated automatically on complaint arrival; if confidence ≥ 0.90 the reply is auto-sent without human review. When `false`, AI reply is not generated until an agent manually clicks "Generate AI Reply".
- **Manual Generate AI Reply** — `POST /api/v1/complaints/{id}/generate-reply` bypasses all eligibility checks (including legal/escalation blocks) and always queues the reply for human review (`force_human_review=True`). Implemented in `app/api/v1/complaints.py`.

**Job Queue (`app/queue/worker.py`)**
- Backend auto-selected by QUEUE_BACKEND: `auto` (postgres), `postgres`, or `redis`
- Job types: `send_email`, `send_slack`, `process_workflow_action`, `sync_inbox`, `retry_outbound`
- Worker thread starts on FastAPI startup, processes every 30 seconds
- Retry logic in `RetryService`; failed jobs land in `status='failed'` (dead letter)
- Disable with `DISABLE_BACKGROUND_WORKERS=1`

**Escalation (`app/services/escalation_engine.py`)**
- Levels: L0 (none), L1 (4h), L2 (24h), IO (legal/compliance)
- Triggers: SLA breach, sentiment spike, manual escalation rules

**Workflow & Automation (`app/workflow/`)**
- DSL-based automation rules evaluated per complaint event
- `workflow_dsl.py` — defines conditions/actions/delays
- `rule_engine.py` — evaluates rules against complaint state
- `dispatcher.py` — executes actions: send_email, escalate, tag, assign, webhook
- `workflow_queue.py` — enqueues matched workflows as async jobs
- `AutomationSettings` model stores per-client rules as JSON; `WorkflowExecution` table is the audit trail

**Inboxes (`app/inboxes/`, `app/services/inbox_poller.py`)**
- Connects Gmail/IMAP accounts as shared inboxes
- OAuth via `GOOGLE_INBOXES_OAUTH_REDIRECT_URI`; credentials encrypted with `CHANNEL_CRYPTO_KEY` (AES-256)
- Gmail Watch via Google Cloud Pub/Sub (`GMAIL_PUBSUB_TOPIC`) for push notifications
- `/inboxes/{inbox_id}/poll` — manual debug endpoint: triggers immediate poll + returns diagnostics
- Inbound email routed as complaints via the standard pipeline

**Customer Intelligence (`app/services/customer_profile.py`)**
- `CustomerProfileService` — 360° customer view across all channels (email, phone, WhatsApp, API)
- Tracks `customer_lifetime_value`, `churn_risk`, `interaction_count`
- `customer_deduplication.py` — fuzzy-matches email/phone to detect duplicate identities
- `customer_merge_history` table tracks identity consolidation
- `CustomerEvent` table logs lifecycle events: signup, login, complaint_filed, response_received, churn
- `app/analytics/customer_pulse.py` — spike detection (`detect_complaint_spikes()`) for escalation triggers

**Chatbot (`app/intelligence/chatbot.py`, `app/api/chatbot.py`)**
- Customer-facing AI chat powered by Gemini; endpoint: `POST /api/chat`
- Resolves queries via complaint history + knowledge base; suggests FAQs before escalating

**Knowledge Base (`app/api/v1/knowledge.py`)**
- `knowledge_snippets` table — FAQ-style responses linked to categories
- CRUD at `/api/v1/knowledge`; used by reply engine and chatbot for grounding

**Model Auditing (`app/api/v1/model_audit.py`)**
- Every Gemini API call logged to `model_audit_logs`: model_name, prompt/completion tokens, latency_ms, cost estimate, tags
- Query at `/api/v1/model-audit`

**Voice (`app/integrations/voice.py`, `app/services/voice_agent.py`)**
- Standalone REST endpoints (require `x-api-key`), NOT part of the complaint webhook pipeline:
  - `POST /integrations/voice/transcribe` — upload audio → transcript (Deepgram `nova-2`)
  - `POST /integrations/voice/synthesize` — text → speech (ElevenLabs `eleven_turbo_v2`)
  - `GET /integrations/voice/status` — which capabilities are active
- Lazy-loaded: unavailable if env keys are absent

### 3. Key Patterns & Conventions

**API Structure**
- `/webhook/*` — Complaint ingestion (no JWT; API key in `x-api-key` header)
- `/api/v1/*` — Client-facing REST API (JWT required)
- `/api/admin/*` — Admin endpoints (HTTP Basic Auth: ADMIN_USERNAME / ADMIN_PASSWORD)
- `/integrations/*` — Third-party webhooks (Gmail, WhatsApp, Email, Voice)
- `/auth/*` — Session auth and OAuth callbacks (`app/api/session_auth.py`)
- `/inboxes/*` — Inbox management (JWT required)

**Middleware Stack** (in `app/main.py`, applied in this order)
1. `RLSContextMiddleware` — Multi-tenant identity resolution; skips static paths; 5-min TTL cache for api_key→client_id and user_id→client_id to avoid per-request DB queries
2. `FeatureGateMiddleware` — Feature flagging per plan tier (Starter/Pro/Max/Scale/Enterprise); checks static plan definitions then `PlanFeature` DB overrides
3. `SecurityHeadersMiddleware` — CSP, X-Frame-Options, etc.
4. `DatabaseRateLimitMiddleware` — In-memory sliding window rate limiting
5. `RequestAuditMiddleware` — Fire-and-forget audit writes via thread executor; skips static paths; stores to `RequestAudit` table
6. `GZipMiddleware` — Compresses responses ≥512 bytes
7. `request_logging` — Request/response timing; skips metric recording for static paths

**Performance notes (middleware)**
- `record_metric()` is non-blocking — buffers in memory (max 2,000 items), background worker flushes to `MonitoringMetric` table every 30s
- `pool_pre_ping=False` — stale connections handled by `pool_recycle=300` instead
- DB pool: `pool_size=15, max_overflow=20` — sized for 3 middleware sessions + 1 handler + overhead
- Never add synchronous DB writes (`.commit()`) inside middleware before returning the response

**Startup Behavior**
- `app/security_check.py` runs first: verifies DATABASE_URL uses direct PostgreSQL (not Supabase HTTP API), raises RuntimeError if SSL mode not configured
- `app/db/schema_guard.py` (`ensure_schema()`) verifies DB schema unless `DISABLE_SCHEMA_GUARD=1`
- Background worker thread starts unless `DISABLE_BACKGROUND_WORKERS=1`
- Sentry initialized automatically if `SENTRY_DSN` is set and `ENVIRONMENT != dev`

**Plan Tiers & Feature Gating (`app/billing/plans.py`)**
- Static tiers: Starter → Pro → Max → Scale → Enterprise; each defines `feature_flags`, `tickets_per_month`, `api_calls_per_day`, `team_seats`
- `rbi_compliance` requires Scale+; `sla_management` requires Pro+
- `PlanFeature` table allows per-tenant feature overrides on top of static tiers
- `TenantUsageTracking` table tracks real-time monthly tickets + API calls per client
- `get_plan_configuration()` merges static + DB overrides at runtime

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
- `app/billing/router.py` (not `app/api/billing.py`) — manages payment methods, plan changes, invoices
- `Invoice` model stores GST, amount, status, razorpay_order_id

**Auth: Three Parallel Systems**
- API key (`x-api-key` header): `require_api_key()` / `get_client_from_api_key()` in `app/dependencies/auth.py` — used for webhooks and integrations
- JWT tokens (`app/api/v1/auth.py`): `JWT_SECRET_KEY` (defaults to SECRET_KEY), `ACCESS_TOKEN_EXPIRE_MINUTES` (60), `REFRESH_TOKEN_EXPIRE_DAYS` (30). The React SPA stores these in **localStorage** (`synapflow_token`, `synapflow_user`) — not in memory.
- Session cookies (`app/api/session_auth.py`): `itsdangerous`-signed session for Portal UI; `create_session()` / `decode_session()`

**Frontend Auth (React SPA)**
- `frontend/src/app/lib/auth-context.tsx` — `AuthProvider` reads token + user from `localStorage` on mount; `login()` calls `/api/v1/auth/login` then `/api/settings` to build the `User` object; `logout()` clears localStorage.
- User display name: `ClientUser` has **no `name` column** — the backend derives it from the email local part via `_display_name_from_email()` in `app/auth.py`. The sidebar shows `user.companyName` (the `Client.name` field set at signup) as the primary identifier.
- `/api/usage` returns `current_usage` and `monthly_limit` (not `tickets_used`/`tickets_quota` — those field names are wrong and must not be used).

**Dark Mode**
- Implemented via `frontend/src/app/lib/theme-context.tsx` (`ThemeProvider` + `useTheme` hook). Persists to `localStorage("theme")`. Applies/removes `.dark` class on `<html>`.
- CSS variables for dark mode defined in `frontend/src/styles/theme.css` under `.dark {}`.
- Tailwind uses `@custom-variant dark (&:is(.dark *))` — so `dark:*` utility classes respond to the `.dark` ancestor class.
- Toggle button rendered in `DashboardLayout` header (Moon/Sun icon) and `LandingPage` header.

**Testing Setup (`tests/conftest.py`)**
- `conftest.py` automatically sets `DISABLE_BACKGROUND_WORKERS=1` and `DISABLE_SCHEMA_GUARD=1`
- SQLite in-memory DB; session overrides patch all middleware that hold their own `SessionLocal`
- Adding new middleware that caches `SessionLocal` at import time requires a conftest patch
- Key test files: `test_webhook_intake.py`, `test_unified_ingestion_pipeline.py`, `test_inbox_poller.py`, `test_event_intelligence.py`, `test_no_new_platform_features.py` (regression guard)

### 4. Database Schema Highlights

**Complaints** — core fields: `id`, `client_id`, `summary`, `source` (api/email/whatsapp/voice)
- Classification: `category`, `intent`, `sentiment`, `urgency_score`, `priority`, `confidence`
- Assignment: `team_id`, `assigned_user_id`
- State machine: `status`, `state` (NEW → ASSIGNED → IN_PROGRESS → RESOLVED/REOPENED); transitions logged in `ticket_state_transitions` via `TicketStateMachine` (`app/services/ticket_state_machine.py`)
- SLA: `sla_due_at`, `sla_status` (on_track/breached)
- RBI: `rbi_category_code`, `tat_due_at`, `tat_status`
- Reply: `ai_reply`, `ai_reply_confidence`, `ai_reply_status` (pending/approved/rejected/sent)

**Multi-tenancy** — `Client` is the root tenant (UUID PK). RLS not enforced by default; set `ENABLE_RLS=true` for strict SQL-level isolation.

**Escalation** — `EscalationLevelDefinition` per client; `EscalationRule` defines triggers; `escalation_level_definitions` relationship on `Client`.

**AIReplyQueue** — HITL queue: pending → approved → sent OR rejected. Agents review in Portal. Email notification triggered when draft enters HITL queue.

**RBIComplaint** — Regulatory tracking: `rbi_category_code`, `tat_due_at`, `tat_breached_at`. MIS aggregation via `app/services/rbi_compliance.py`. Monthly MIS generated on `RBI_MIS_REPORT_DAY` (default: 1st), stored in `rbi_mis_reports`. RBI taxonomy mapping in `rbi_taxonomy_classifier.py`.

**Unified Messaging** — `UnifiedMessage` (normalized cross-channel messages), `Conversation` (thread groups by external_thread_id + channel + client_id), `message_events` (per-message events: received/sent/failed)

**Customer Intelligence** — `CustomerProfile`, `customer_interactions`, `customer_notes`, `customer_relationships`, `customer_merge_history`, `CustomerEvent`, `churn_outcomes`

**Workflow** — `automation_settings` (JSON rules per client), `workflow_executions` (audit trail)

**Compliance** — `ConsentRecord` (DPDP/GDPR consent: marketing/communications, timestamp, channel), `PasswordResetOTP`

**Analytics & Quality** — `MonitoringMetric`, `RequestAudit`, `model_audit_logs`, `reply_feedback`, `reply_ab_tests`, `reply_quality_metrics`, `knowledge_snippets`, `agent_corrections`

**Plan/Billing** — `PlanFeature` (per-tenant overrides), `TenantUsageTracking` (monthly aggregates), `Invoice`, `channel_connections` (OAuth tokens for integrations)

## Environment Variables

**Required:**
- `DATABASE_URL` — PostgreSQL connection (Supabase format)
- `SECRET_KEY` — JWT/session secret (min 32 chars)
- `GEMINI_API_KEY` — Google Gemini API key

**Auth & Security:**
- `ADMIN_USERNAME` / `ADMIN_PASSWORD` — Admin API HTTP Basic Auth (min 8 chars)
- `JWT_SECRET_KEY` — Separate JWT secret (defaults to SECRET_KEY)
- `ACCESS_TOKEN_EXPIRE_MINUTES` (default: 60), `REFRESH_TOKEN_EXPIRE_DAYS` (default: 30)
- `CHANNEL_CRYPTO_KEY` — AES-256 encryption for stored OAuth tokens (Gmail inboxes)

**Infrastructure:**
- `ENVIRONMENT` — dev/staging/prod (default: dev)
- `APP_BASE_URL` — Base URL for OAuth redirects (default: http://127.0.0.1:8000)
- `QUEUE_BACKEND` — auto/postgres/redis (default: auto → postgres)
- `REDIS_URL` — Redis connection, used when QUEUE_BACKEND=redis
- `WEB_CONCURRENCY` — uvicorn worker count (Railway/Render)
- `WORKER_INTERVAL` — standalone worker poll interval in seconds (default: 10)
- `SENTRY_DSN` — Sentry error tracking (auto-enabled when set and ENVIRONMENT != dev)

**Integrations:**
- `SLACK_WEBHOOK_URL` — Slack notifications
- `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, `SMTP_FROM` — Email sending (SMTP)
- `RESEND_API_KEY`, `RESEND_FROM` — Resend email service (alternative to SMTP; default from: "SynapFlow <onboarding@resend.dev>")
- `INBOUND_EMAIL_DOMAIN`, `INBOUND_EMAIL_WEBHOOK_SECRET` — Inbound email routing + HMAC validation
- `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET` — Gmail OAuth
- `GOOGLE_INBOXES_OAUTH_REDIRECT_URI`, `GOOGLE_INTEGRATIONS_OAUTH_REDIRECT_URI` — Gmail OAuth callbacks
- `GMAIL_PUBSUB_TOPIC`, `GMAIL_WATCH_LABEL_IDS` — Gmail Push Notifications
- `WHATSAPP_APP_SECRET`, `WHATSAPP_VERIFY_TOKEN`, `WHATSAPP_DEFAULT_API_VERSION` (default: v22.0)
- `RAZORPAY_KEY_ID`, `RAZORPAY_KEY_SECRET`, `RAZORPAY_WEBHOOK_SECRET`
- `RAZORPAY_PLAN_STARTER_MONTHLY`, `RAZORPAY_PLAN_STARTER_ANNUAL`, etc. — Razorpay subscription plan IDs per tier
- `DEEPGRAM_API_KEY` — Deepgram transcription (voice endpoints inactive without this)
- `ELEVENLABS_API_KEY`, `ELEVENLABS_VOICE_ID` — ElevenLabs TTS (voice endpoints inactive without these)

**Tuning:**
- `ENABLE_RLS` — Row-level security enforcement (default: false)
- `REPLY_AUTO_APPROVE_THRESHOLD` — Min confidence for auto-send (default: 0.85)
- `REPLY_HUMAN_REVIEW_THRESHOLD` — Min confidence for HITL queue (default: 0.60)
- `SLA_MONITOR_INTERVAL_MINUTES` — SLA breach check frequency (default: 10)
- `RBI_TAT_DEFAULT_DAYS` — Default TAT for RBI complaints (default: 30)
- `RBI_MIS_REPORT_DAY` — Day of month to generate MIS report (default: 1)
- `REQUEST_LOG_RETENTION_DAYS` — Audit log cleanup (default: 30)
- `DISABLE_BACKGROUND_WORKERS=1` — Disable worker thread (auto-set in tests)
- `DISABLE_SCHEMA_GUARD=1` — Skip schema validation on startup (auto-set in tests)

## Deployment

**Railway:** `railway.json` + `nixpacks.toml` — start command `bash start.sh`. Health check path: `/health` (300s timeout). Set all env vars in Railway dashboard.

**Render:** `render.yaml` included.

**Health Checks:**
```bash
curl http://localhost:8000/health       # DB connection
curl http://localhost:8000/health/db    # DB-specific
curl http://localhost:8000/health/ai    # Gemini API
```

**Common Railway 502 causes:**
- `frontend/out/` missing at runtime (nixpacks build command bug — fixed; `npm run build` was only running when `npm ci` failed)
- Migrations taking >300s (unlikely but add `DISABLE_SCHEMA_GUARD=1` to speed up startup if schema is stable)
- Missing required env vars (`DATABASE_URL`, `SECRET_KEY`) cause immediate crash at module import time
- `sslmode=require` is enforced in `app/db/session.py` — if Supabase URL doesn't support direct SSL, the connection pool creation fails

## Important Notes

- **Queue backend:** PostgreSQL by default; Redis available via `QUEUE_BACKEND=redis`. The worker runs as a thread inside FastAPI — move to dedicated process (`worker_standalone.py`) for scale.
- **Schema evolution:** Use Alembic for all new migrations. The `migrate_*.py` scripts are legacy.
- **Frontend:** Next.js static export. Built by `start.sh` if `frontend/out/` is missing. FastAPI serves it via catch-all route; JS/CSS assets get 1-year immutable cache headers; HTML gets no-cache.
- **Test DB:** SQLite in-memory — not PostgreSQL. Any middleware caching `SessionLocal` at module level must be patched in conftest.
- **Email modes:** `app/integrations/email.py` supports three modes — forwarding (customers forward to dedicated inbox), IMAP (direct server connection), and Resend API (transactional sends). Webhook signatures validated via HMAC in `app/utils/webhook_security.py`.

## Key File Organization

- `app/main.py` — FastAPI app: middleware, router includes, startup hooks
- `app/config.py` — All settings with Pydantic validation (`get_settings()`)
- `app/security_check.py` — Startup SSL + isolation verification (runs before schema guard)
- `app/db/models.py` — All SQLAlchemy ORM models
- `app/db/schema_guard.py` — Startup schema verification
- `app/intake/webhook.py` — Complaint ingestion, validation, dispatch
- `app/services/unified_ingestion.py` — Cross-channel message normalization + conversation threading
- `app/intelligence/classifier.py` — Gemini 2.5 Flash Lite classification via httpx
- `app/intelligence/reply_engine.py` — Gemini 2.0 Flash reply drafting via httpx
- `app/intelligence/chatbot.py` — Customer-facing AI chat
- `app/services/model_orchestration.py` — Central Gemini orchestration layer (multi-step AI calls, audit logging, timed_ms)
- `app/services/ticket_state_machine.py` — Formal NEW→ASSIGNED→IN_PROGRESS→RESOLVED state machine with transition audit
- `app/services/voice_agent.py` — Deepgram/ElevenLabs transcription + synthesis (lazy-loaded)
- `app/services/customer_profile.py` — 360° customer view, deduplication, churn risk
- `app/services/reply_confidence_scorer.py` — Multi-factor reply confidence scoring
- `app/workflow/` — DSL-based automation: `workflow_dsl.py`, `rule_engine.py`, `dispatcher.py`, `workflow_queue.py`
- `app/services/` — Core business logic (routing, SLA, escalation, replies, RBI)
- `app/api/v1/` — REST API endpoints (tickets, complaints, teams, reply_queue, knowledge, model_audit, etc.)
- `app/api/v1/knowledge.py` — Knowledge base CRUD (`/api/v1/knowledge`)
- `app/api/v1/model_audit.py` — AI observability (`/api/v1/model-audit`)
- `app/queue/worker.py` — Job queue + background worker
- `app/queue/backends.py` — PostgreSQL vs Redis backend abstraction
- `app/monitoring/metrics.py` — Non-blocking in-memory metrics buffer; flush to `MonitoringMetric` table
- `app/middleware/` — Request/response middleware
- `app/integrations/` — Third-party webhooks (Gmail, WhatsApp, Email, Voice)
- `app/inboxes/` — Managed inbox connections (Gmail/IMAP OAuth)
- `app/billing/` — Plan enforcement, Razorpay, usage tracking
- `app/billing/plans.py` — Static plan tier definitions
- `app/analytics/` — Customer pulse and performance analytics
- `tests/conftest.py` — Test fixtures, SQLite override, middleware patching
- `alembic/` — Database migrations
- `frontend/` — Next.js frontend (static export to `frontend/out/`)

## Product Documentation

Full product context lives in `about synapflow/`:
- `PRD.md` — Product Requirements Document (features, billing tiers, roadmap gaps)
- `TRD.md` — Technical Requirements Document (architecture, API reference, schema, constants)
- `APP_FLOW.md` — Step-by-step flow for every feature (ingestion, classification, routing, billing, etc.)
- `Legal_Requirements_Document.md` — DPDP, GDPR, CCPA, IT Act, CAN-SPAM compliance details

## Railway Deployment Crash/Error or Error related to Database Schema
- Use the Railway CLI and Supabase CLI to pull build/deployment logs.
- After finding the error, fix it and redeploy.
- After every commit + deployment, verify `/health` returns `{"status":"healthy"}`.
- Known Railway 502 root cause: if `frontend/out/` doesn't exist at startup, `start.sh` runs a 2-min frontend build before uvicorn starts — this was fixed by correcting the nixpacks.toml build command operator precedence.
