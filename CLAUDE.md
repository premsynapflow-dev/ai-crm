# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**SynapFlow** is an AI-powered complaint intelligence platform that ingests customer feedback from multiple channels (API, Email, WhatsApp), classifies and analyzes complaints, generates AI-suggested replies, and automates routing and escalation workflows. The system is optimized for simplicity and speed, with all processing occurring in a single FastAPI process using PostgreSQL-backed job queues (no Redis/Celery by design).

**Stack:**
- Backend: FastAPI + SQLAlchemy ORM + PostgreSQL (Supabase)
- Frontend: Next.js 16 with Tailwind CSS, static export
- AI: Google Gemini API for classification and reply generation
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
# Edit .env with:
# - DATABASE_URL (Supabase PostgreSQL)
# - GEMINI_API_KEY (Google AI Studio)
# - SECRET_KEY (32+ chars)
# - SMTP credentials for email
# - RAZORPAY credentials
# - SLACK_WEBHOOK_URL (optional)
```

### Run Migrations
```bash
python migrate_add_slack_url.py
python migrate_add_summary.py
python migrate_add_event_logs.py
python migrate_replace_message_with_summary.py
python migrate_revenue_ready.py
alembic upgrade head  # For newer migrations
```

### Start Development Server
```bash
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

**OR** use the production wrapper:
```bash
bash start.sh
```
This builds the Next.js frontend, runs migrations, and starts uvicorn with concurrency settings based on `WEB_CONCURRENCY` env var (default: 1).

### Start Background Worker (Standalone)
```bash
SERVICE_TYPE=worker bash start.sh
# OR
python worker_standalone.py
```

## Testing Commands

### Run All Tests
```bash
python -m unittest discover -s tests
```

### Run Tests with Coverage
```bash
python -m pytest tests/ --cov=app --cov-report=html
```

### Run a Single Test File
```bash
python -m unittest tests.test_ai_reply_flow
```

### Run a Specific Test Method
```bash
python -m unittest tests.test_ai_reply_flow.TestAIReplyFlow.test_method_name
```

### Run Tests with Pytest
```bash
python -m pytest tests/test_ai_reply_flow.py -v
python -m pytest tests/test_ai_reply_flow.py::test_specific_function -v
```

## Code Quality Commands

### Lint with Flake8
```bash
flake8 app/ --max-line-length=120 --extend-ignore=E203
```

### Format with Black
```bash
black app/ tests/
```

### Sort Imports with isort
```bash
isort app/ tests/ --profile=black
```

### Run Pre-commit Hooks
```bash
pre-commit run --all-files
```

## Frontend Development

### Build Frontend
```bash
cd frontend
npm install
npm run build
cd ..
```

### Frontend Development Server
```bash
cd frontend
npm run dev
# Runs on http://localhost:3000
```

### Lint Frontend
```bash
cd frontend
npm run lint
```

## High-Level Architecture

### 1. Data Flow: Complaint Ingestion to Resolution

```
Customer Input (API/Email/WhatsApp)
    ↓
[Webhook Router] - Validates API key, sanitizes input
    ↓
[Classifier] - Gemini AI: intent, category, sentiment, urgency
    ↓
[Sentiment Analyzer] - 1-5 score + emotional indicators
    ↓
[Routing Service] - Assigns to team/user based on capacity & rules
    ↓
[SLA Manager] - Sets TAT deadline (RBI compliance)
    ↓
[Escalation Engine] - Monitors for breach, applies escalation rules
    ↓
[Reply Generator] - Drafts AI response (human review or auto-approve)
    ↓
[Job Queue] - Enqueues send_email, send_slack, sync_integration tasks
    ↓
[Background Worker] - Processes queue every 30 seconds
    ↓
Customer Response
```

### 2. Core Services & Responsibilities

**Complaint Ingestion (`app/intake/webhook.py`)**
- Validates x-api-key authentication
- Parses email/WhatsApp webhooks via integration routers
- Generates stable ticket_id and thread_id
- Tracks usage against billing plan
- Dispatches to classification

**Classification (`app/intelligence/classifier.py`)**
- Uses Gemini API with client-specific prompts (per `app/intelligence/prompt_builder.py`)
- Returns: intent, category, sentiment, urgency_score, priority, recommended_action, confidence
- Normalizes output to prevent hallucination
- Falls back to defaults on API failure

**Sentiment Analysis (`app/services/sentiment.py`)**
- Analyzes 1-5 emotional intensity (1=calm, 5=furious)
- Extracts emotional indicators (e.g., "frustrated with delays")
- Used for escalation priority and tone matching

**Routing (`app/services/routing_service.py`)**
- Loads routing rules per client (RoutingRule model)
- Assigns to team based on category + priority
- Rebalances workload within team (assigns to user with fewest active tasks)
- Respects existing assignments unless force_rebalance=True

**SLA & TAT Management (`app/services/sla_manager.py`)**
- Sets sla_due_at based on priority (high: 4h, medium: 24h, low: 72h)
- Sets tat_due_at for RBI-regulated clients (default: 30 days, configurable)
- Background worker monitors for breaches and triggers escalations

**Reply Generation (`app/services/reply_generator.py`, `app/intelligence/reply_engine.py`)**
- Fetches similar resolved complaints from history
- Generates draft via Gemini with context
- Confidence threshold: auto-approve if > REPLY_AUTO_APPROVE_THRESHOLD (0.85)
- Otherwise: human review required via Portal
- Enqueues send job on approval

**Job Queue (`app/queue/simple_queue.py`, `app/queue/worker.py`)**
- Simple PostgreSQL-backed queue (no Redis)
- Job types: send_email, send_slack, sync_integration
- Worker thread starts on FastAPI startup, processes every 30 seconds
- Can be disabled with DISABLE_BACKGROUND_WORKERS=1

**Escalation (`app/services/escalation_engine.py`)**
- Multi-level escalation: Level 0 (no escalation), L1 (4h), L2 (24h), IO (legal/compliance)
- Triggers on SLA breach, sentiment spike, or manual escalation rules
- Routes to escalation_level_definitions per client
- Sends Slack notifications

### 3. Database Schema Highlights

**Clients**
- Multi-tenant: id (UUID primary key)
- Plan tracking: plan_id, monthly_ticket_limit
- Custom prompts: custom_prompt_enabled, custom_prompt_config (JSON)
- Compliance: is_rbi_regulated, business_sector
- Trial tracking: trial_ends_at

**Complaints**
- Core fields: id, client_id, summary, source (api/email/whatsapp)
- Classification: category, intent, sentiment, urgency_score, priority
- Assignment: team_id, assigned_user_id
- State machine: status, state (NEW → ASSIGNED → IN_PROGRESS → RESOLVED)
- SLA: sla_due_at, sla_status (on_track/breached)
- RBI: rbi_category_code, tat_due_at, tat_status
- Reply: ai_reply, ai_reply_confidence, ai_reply_status (pending/approved/rejected/sent)

**Teams & Members**
- Team: per-client team grouping
- TeamMember: membership with role (agent, supervisor, manager)
- Tracks workload: active_task_count, capacity

**RoutingRules**
- Per-client rules: condition (category/intent/priority), target_team_id
- Category-based or priority-based routing
- Fallback to default team if no match

**Escalation Rules**
- Per-client: trigger_condition, escalation_level, escalate_to_email/escalate_to_team
- Can have category_code for RBI-specific escalations

**AutomationRules & Workflows**
- Event-driven: trigger on complaint state/status change
- Actions: send_email, send_slack, change_status, escalate
- Support time-based delays (follow-up after 24h)

**AIReplyQueue**
- Human-in-the-loop (HITL): stores pending AI drafts
- Status: pending → approved → sent OR rejected
- Agent reviews and approves before sending

**RBIComplaint**
- RBI regulatory compliance tracking
- rbi_category_code, tat_due_at, tat_breached_at
- MIS reporting aggregation

### 4. Key Patterns & Conventions

**API Structure**
- /webhook/* - Complaint ingestion (no auth required, API key validated separately)
- /api/v1/* - Client-facing REST API (JWT required)
- /api/admin/* - Admin endpoints (X-Admin-Password header)
- /portal/* - Web UI routes (served by frontend, FastAPI proxies)
- /integrations/* - Third-party webhooks (Gmail, WhatsApp, Email)

**Middleware Stack** (in `app/main.py`)
1. RLSContextMiddleware - Multi-tenant Row-Level Security context
2. FeatureGateMiddleware - Feature flagging per client
3. SecurityHeadersMiddleware - CSP, X-Frame-Options, etc.
4. DatabaseRateLimitMiddleware - Rate limiting stored in DB
5. RequestAuditMiddleware - Audit logs of all requests
6. RequestLoggingMiddleware - Request/response timing

**Service Locator Pattern**
- Dependencies injected via Depends(get_db) from app/dependencies/auth.py
- Services instantiated per-request to maintain session isolation
- Example: RoutingService(db).route_ticket(complaint, classification)

**Classification Config Per Client**
- Default config in app/intelligence/prompt_builder.DEFAULT_CONFIG
- Client override stored in Client.custom_prompt_config (JSON)
- Merged at runtime: base defaults + client overrides
- Supports tone, focus_areas, industry, classification_rules, escalation_rules

**Billing & Usage Tracking** (`app/billing/usage.py`)
- Trial: free, 50 tickets, 7-day expiry
- Pro: Rs 4,999/mo, 1,000 tickets, Rs 8/overage
- Business: Rs 14,999/mo, 5,000 tickets, Rs 4/overage
- Soft limits: paid plans continue processing and accrue overage
- Hard limits: trial stops on expiry or limit breach

**Error Handling & Resilience**
- Circuit breaker for Gemini API (app/utils/circuit_breaker.py)
- Retry logic with exponential backoff (tenacity library)
- Fallback classifications on API failure
- Webhook idempotency via stable external ID hash

**Testing Setup** (`tests/conftest.py`)
- SQLite in-memory DB for tests (fast isolation)
- Session overrides for middleware (rate limiter, audit, RLS)
- Test fixtures: client (FastAPI TestClient), test_db, test_client_record
- CI/CD: GitHub Actions with Python 3.12, runs on push/PR

### 5. Important Implementation Details

**Complaint State Machine** (`app/services/ticket_state_machine.py`)
- States: NEW → ASSIGNED → IN_PROGRESS → RESOLVED (with REOPENED transitions)
- state_changed_at tracks transition timestamp
- All transitions logged to EventLog for audit
- RLS: ensure client_id matches request context

**Customer Deduplication** (`app/services/customer_deduplication.py`)
- Merges customer records by email/phone
- Prevents duplicate profiles
- Aggregates complaint history

**Conversation Threading** (`app/services/conversation_threads.py`)
- Groups replies into threads
- Tracks parent/child relationships
- Used for email reply chains and WhatsApp conversations

**RBI Compliance** (`app/services/rbi_compliance.py`)
- TAT (Turn Around Time) enforcement: default 30 days
- MIS (Management Information System) reporting: aggregates per category per month
- Category codes: standard RBI complaint taxonomy (e.g., "ATM", "LOAN", "DEPOSIT")
- Auto-escalation for TAT breaches

**Custom Prompts** (`app/api/admin_prompts.py`)
- Admin API: GET/PUT/DELETE per client
- Config validation: tone, industry, focus_areas, rules
- Applied at classification time via build_classification_prompt

**Reply Draft Approval** (`app/services/auto_reply_hardened.py`)
- Confidence-based: high confidence (>0.85) → auto-approve + send
- Medium confidence (0.60–0.85) → queue for human review
- Low confidence (<0.60) → discard, escalate for manual reply
- Agent reviews in Portal before send

**Job Queue Processing**
- Queue jobs table: job_type, payload, status, created_at, retry_count
- Worker picks up status='pending', processes, updates to status='done' or status='failed'
- Exponential backoff retry on failure
- Disable with DISABLE_BACKGROUND_WORKERS=1 for testing

### 6. Common Development Tasks

**Adding a New Classification Feature**
1. Update app/intelligence/classifier.py prompt
2. Add field to Complaint model (alembic migration)
3. Update classification response in webhook handler
4. Add test in tests/test_ai_services.py

**Adding a New Webhook Source**
1. Create router in app/integrations/{source}.py
2. Define request schema (email, WhatsApp, custom, etc.)
3. Map to common complaint format
4. Register router in app/main.py with app.include_router
5. Document endpoint in README.md

**Adding a Routing Rule Type**
1. Add condition builder to app/services/routing_service.py
2. Create RoutingRule config entry
3. Add API endpoint in app/api/v1/workflows.py or admin section
4. Test in tests/test_routing_service.py

**Implementing a New Automation**
1. Define trigger event and action in AutomationRule model
2. Create handler function in app/services/workflow_queue.py
3. Add job enqueue in webhook/complaint processing
4. Implement job processor in app/queue/worker.py
5. Test with load test: python -m pytest tests/load_test.py

## Environment Variables

**Required:**
- DATABASE_URL - PostgreSQL connection (Supabase format)
- SECRET_KEY - JWT/session secret (min 32 chars)
- GEMINI_API_KEY - Google Gemini API key

**Optional but Important:**
- ENVIRONMENT - dev/staging/prod (default: dev)
- APP_BASE_URL - Base URL for OAuth redirects (default: http://127.0.0.1:8000)
- SLACK_WEBHOOK_URL - Slack integration
- RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET - Billing
- SMTP_* - Email sending
- GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET - Gmail OAuth
- WHATSAPP_APP_SECRET, WHATSAPP_VERIFY_TOKEN - WhatsApp
- ENABLE_RLS - Row-level security enforcement (default: false)
- REPLY_AUTO_APPROVE_THRESHOLD - Min confidence for auto-send (default: 0.85)
- REQUEST_LOG_RETENTION_DAYS - Audit log cleanup (default: 30)

## Deployment

**Railway:**
- railway.json included
- Set start command: bash start.sh
- Add all .env variables in dashboard

**Render:**
- render.yaml included
- Set environment variables in Render dashboard

**Health Checks:**
```bash
curl http://localhost:8000/health          # Overall health
curl http://localhost:8000/health/db       # DB connection
curl http://localhost:8000/health/ai       # AI/Gemini API
```

## Important Notes

- **No Redis/Celery:** Job queue is PostgreSQL-backed for simplicity. Upgrade path exists.
- **Single Process Worker:** Background worker runs as thread inside FastAPI. For scale, move to dedicated process.
- **Schema Evolution:** Use Alembic for migrations. Manual scripts (migrate_*.py) are legacy.
- **RLS Not Enforced by Default:** Set ENABLE_RLS=true for strict tenant isolation in SQL queries.
- **Frontend Build:** Next.js static export (no server-side rendering). Built on startup if missing.
- **Concurrency:** Set WEB_CONCURRENCY for uvicorn workers (Railway/Render auto-scales).
- **Test DB:** Uses SQLite in-memory, not PostgreSQL. Middleware overrides required.

## Key File Organization

- app/main.py - FastAPI app setup, middleware, router includes
- app/config.py - Settings validation (Pydantic)
- app/db/models.py - SQLAlchemy ORM models
- app/intake/webhook.py - Complaint ingestion, validation, dispatch
- app/intelligence/classifier.py - Gemini classification
- app/services/ - Core business logic (routing, SLA, escalation, replies)
- app/api/v1/ - REST API endpoints (tickets, complaints, teams, etc.)
- app/queue/ - Job queue and background worker
- app/middleware/ - Request/response middleware
- app/integrations/ - Third-party webhooks (Gmail, WhatsApp, Email)
- tests/ - Unit tests (unittest + pytest)
- frontend/ - Next.js frontend
- alembic/ - Database migrations
