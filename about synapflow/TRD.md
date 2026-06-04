# SynapFlow — Technical Requirements Document
**Updated from codebase analysis · June 2026 (rev 3)**

---

## 1. System Overview

SynapFlow is a multi-tenant SaaS backend built on FastAPI + PostgreSQL. All core processing occurs in a single FastAPI process with a background thread for job queuing. The system ingests complaint data from multiple channels, classifies it via Google Gemini AI, routes it to the appropriate team, and manages the full resolution lifecycle including SLA tracking, escalation, and regulatory compliance.

**Runtime:** Python 3.11+ · FastAPI 0.109+ · SQLAlchemy 2.x ORM · Alembic · PostgreSQL (Supabase, Mumbai region `kyljtdjvnmaffmdhhzzw`)

**Frontend:** **Vite 6 + React 18** · react-router v7 · Tailwind CSS **v4** · Radix UI + shadcn/ui · Recharts · Sonner (toasts) · lucide-react. Static build output (`frontend/out/`) served by FastAPI catch-all route. **Not Next.js** — no pages/ directory, no `next export`, no next-themes. HTTP: native `fetch` via `request()` in `frontend/src/app/lib/api.ts` (no Axios).

**AI:** All Gemini calls made via direct **httpx** REST (no `google-generativeai` SDK). Classifier: Gemini 2.5 Flash Lite. Reply engine: Gemini 2.0 Flash. Voice: Deepgram + ElevenLabs (lazy-loaded).

---

## 2. Application Entry Point

**File:** `app/main.py`

**FastAPI app metadata:**
- Title: `AI Complaint Intelligence API`
- Version: `2.0.0`

### 2.1 Middleware Stack (applied in order)

| # | Middleware | Purpose |
|---|---|---|
| 1 | `CORSMiddleware` | Configurable origins; credentials enabled; `allow_methods=["*"]`, `allow_headers=["*"]` |
| 2 | `SessionMiddleware` | Starlette session cookie; keyed by `SECRET_KEY` |
| 3 | `RLSContextMiddleware` | Injects `client_id` / `user_id` into request state for multi-tenant isolation |
| 4 | `FeatureGateMiddleware` | Enforces per-plan feature flags; returns 403 if feature not enabled |
| 5 | `SecurityHeadersMiddleware` | OWASP security headers + 2 MB request size limit |
| 6 | `DatabaseRateLimitMiddleware` | Per-client rate limiting stored in DB |
| 7 | `RequestAuditMiddleware` | Logs all HTTP requests (path, method, IP, status, user_agent) |
| 8 | `RequestLoggingMiddleware` | UUID request_id + latency metrics |
| 9 | `ErrorHandlingMiddleware` | Global exception handler; normalises 500 responses |

### 2.2 Security Headers (applied by SecurityHeadersMiddleware)

```
X-Frame-Options: DENY
X-Content-Type-Options: nosniff
Referrer-Policy: strict-origin-when-cross-origin
Permissions-Policy: camera=(), microphone=(), geolocation=()
X-XSS-Protection: 1; mode=block
Strict-Transport-Security: max-age=31536000  (HTTPS environments only)
Content-Security-Policy: [configured per environment]
```

Request body size limit: **2 MB** (enforced in middleware before handler).

### 2.3 Startup Hooks

1. `ensure_schema()` — validates DB schema matches expected tables (skip with `DISABLE_SCHEMA_GUARD=1`)
2. `start_worker_thread()` — spawns background job thread every 30 seconds (skip with `DISABLE_BACKGROUND_WORKERS=1`)
3. Sentry SDK initialisation — enabled when `SENTRY_DSN` is set and `ENVIRONMENT != dev`

### 2.4 Static Frontend Serving

FastAPI serves the Next.js static export from `frontend/out/`:
- `/_next/**` — `Cache-Control: public, max-age=31536000, immutable`
- `/images/**` — `Cache-Control: public, max-age=3600`
- HTML / catch-all — `Cache-Control: no-cache, no-store, must-revalidate`

---

## 3. Configuration

**File:** `app/config.py` — Pydantic `BaseSettings`, loaded via `get_settings()` (cached singleton).

### 3.1 Required Variables

| Variable | Type | Description |
|---|---|---|
| `DATABASE_URL` | str | PostgreSQL connection string (min length validated) |
| `SECRET_KEY` | str | HMAC + session secret (min 32 chars) |
| `GEMINI_API_KEY` | str | Google Gemini API key |

### 3.2 Auth & Security

| Variable | Default | Description |
|---|---|---|
| `JWT_SECRET_KEY` | `SECRET_KEY` | Separate JWT secret (falls back to SECRET_KEY) |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | 60 | JWT access token TTL |
| `REFRESH_TOKEN_EXPIRE_DAYS` | 30 | JWT refresh token TTL |
| `ADMIN_USERNAME` | `"admin"` | Admin basic auth username |
| `ADMIN_PASSWORD` | — | Admin bearer token (min 8 chars when set) |
| `CHANNEL_CRYPTO_KEY` | — | AES key for encrypting stored OAuth tokens |
| `ALLOWED_ORIGINS` | localhost:3000/8000, Railway domains | CORS origins |

### 3.3 AI & Integrations

| Variable | Default | Description |
|---|---|---|
| `OPENAI_API_KEY` | — | Optional; Gemini is primary |
| `SLACK_WEBHOOK_URL` | — | Outbound Slack alerts |
| `SMTP_HOST/PORT/USER/PASSWORD/FROM` | — | Email sending (SMTP fallback) |
| `RESEND_API_KEY` / `RESEND_FROM` | `onboarding@resend.dev` | Primary transactional email |
| `INBOUND_EMAIL_DOMAIN` | `inbound.synapflow.com` | Inbound email routing domain |
| `INBOUND_EMAIL_WEBHOOK_SECRET` | — | Inbound email HMAC verification |
| `GOOGLE_CLIENT_ID/SECRET` | — | Gmail OAuth |
| `GOOGLE_INBOXES_OAUTH_REDIRECT_URI` | — | Gmail inbox OAuth callback |
| `GOOGLE_INTEGRATIONS_OAUTH_REDIRECT_URI` | — | Gmail integrations OAuth callback |
| `GMAIL_PUBSUB_TOPIC` / `GMAIL_WATCH_LABEL_IDS` | — | Gmail push notifications |
| `WHATSAPP_APP_SECRET` / `VERIFY_TOKEN` | — | WhatsApp webhook auth |
| `WHATSAPP_DEFAULT_API_VERSION` | `v22.0` | Meta Business API version |
| `RAZORPAY_KEY_ID/SECRET/WEBHOOK_SECRET` | — | Razorpay payment gateway |

### 3.4 Tuning & Feature Flags

| Variable | Default | Description |
|---|---|---|
| `ENVIRONMENT` | `dev` | `dev` / `staging` / `prod` |
| `APP_BASE_URL` | `http://127.0.0.1:8000` | OAuth redirect base |
| `QUEUE_BACKEND` | `auto` | `auto` (postgres) / `postgres` / `redis` |
| `REDIS_URL` | — | Redis connection (when backend=redis) |
| `ENABLE_RLS` | `false` | SQL row-level security enforcement |
| `REPLY_AUTO_APPROVE_THRESHOLD` | `0.85` | Min confidence for auto-send |
| `REPLY_HUMAN_REVIEW_THRESHOLD` | `0.60` | Min confidence for HITL queue |
| `SLA_MONITOR_INTERVAL_MINUTES` | `10` | SLA breach check frequency |
| `RBI_TAT_DEFAULT_DAYS` | `30` | Default TAT for RBI complaints |
| `RBI_MIS_REPORT_DAY` | `1` | Day of month to auto-generate MIS report |
| `REQUEST_LOG_RETENTION_DAYS` | `30` | Audit log cleanup window |
| `DISABLE_BACKGROUND_WORKERS` | — | Set to `1` to disable worker thread |
| `DISABLE_SCHEMA_GUARD` | — | Set to `1` to skip schema validation |
| `SENTRY_DSN` | — | Sentry (auto-enabled in non-dev) |
| `DEFAULT_TIMEZONE` | `UTC` | System default timezone |

---

## 4. Database Schema

**ORM:** SQLAlchemy 2.x · **Migrations:** Alembic · **DB:** PostgreSQL (Supabase, Mumbai region)

### 4.1 Core Tables

#### `clients` (Multi-tenant Root)
| Column | Type | Notes |
|---|---|---|
| `id` | UUID PK | |
| `name` | String(255) | |
| `api_key` | String(255) | UNIQUE, indexed |
| `plan` | String(50) | free\|starter\|pro\|max\|scale\|enterprise |
| `plan_id` | String(50) | |
| `monthly_ticket_limit` | Integer | Default: 50 |
| `business_sector` | String(50) | Default: `not_rbi_regulated` |
| `is_rbi_regulated` | Boolean | Default: False |
| `trial_ends_at` | DateTime | Nullable |
| `custom_prompt_enabled` | Boolean | |
| `custom_prompt_config` | JSON | Per-tenant AI config overrides |
| `slack_webhook_url` | String(500) | |
| `created_at` | DateTime | |

#### `complaints` (Core Ticket Entity)
| Column Group | Columns |
|---|---|
| **Identity** | `id` (UUID PK), `client_id` (FK), `customer_id` (FK), `ticket_id` (String, unique), `ticket_number` (unique), `thread_id`, `source` |
| **Classification** | `intent`, `category`, `recommended_action`, `confidence` (Float), `priority` (1–5) |
| **Sentiment** | `sentiment` (Float -1–1), `sentiment_score` (1–5), `sentiment_label`, `sentiment_indicators` (JSON), `urgency_score` (Float 0–1) |
| **Routing** | `team_id` (FK), `assigned_team`, `assigned_user_id` (FK), `assigned_to` |
| **State Machine** | `status`, `state` (10-state), `state_changed_at`, `resolution_status`, `follow_up_status` |
| **SLA** | `sla_due_at`, `sla_status` (on_track\|at_risk\|breached) |
| **RBI / TAT** | `rbi_category_code`, `tat_due_at`, `tat_status`, `tat_breached_at` |
| **Escalation** | `escalation_level` (0–3), `escalated_at`, `escalated_to` |
| **AI Reply** | `ai_reply` (Text), `ai_reply_confidence`, `ai_reply_status`, `ai_reply_sent_at` |
| **Timing** | `first_response_at`, `response_time_seconds`, `last_replied_at`, `resolved_at` |
| **Satisfaction** | `customer_satisfaction_score` (1–5), `satisfaction_score` |
| **Reopen** | `reopened_count`, `last_reopened_at` |

**Ticket state machine:** `new → assigned → in_progress → waiting_customer / waiting_internal / on_hold → escalated → resolved → closed`; also `spam` / `invalid`.

**Source enum:** `api`, `email`, `whatsapp`, `gmail`, `instagram`, `google_reviews`

#### `customers` (CRM Profile)
Key fields: `primary_email` (unique per client), `churn_risk` (low\|medium\|high), `churn_risk_score` (0–1), `lifetime_value`, `sentiment_score`, `total_tickets`, `merged_into` (self-referencing UUID for deduplication), `is_master` (Boolean).

#### `ai_reply_queue` (HITL Approval Queue)
| Column | Notes |
|---|---|
| `status` | pending\|approved\|edited\|rejected\|sent\|expired |
| `confidence_score` | Float |
| `hallucination_check_passed` | Boolean, default True |
| `toxicity_score` | Float, default 0.0 |
| `factual_consistency_score` | Float, default 0.8 |
| `expires_at` | now + 24 hours |
| `reviewed_by` | Agent email |

#### `reply_drafts` (Versioned Drafts)
Unique per `(client_id, ticket_id)`. Status: `pending\|approved\|rejected\|sent`. Stores `prompt_version` (`auto_reply_with_hitl_v1`).

#### `sla_policies`
Per-client, per-priority SLA definition. Fields: `first_response_minutes`, `resolution_minutes`, `escalation_threshold_minutes`, `business_hours_only`, `timezone`.

#### `business_hours`
Per-client, per-day (0–6). Fields: `start_time`, `end_time`, `timezone`, `enabled`.

#### `escalation_level_definitions`
Standard RBI escalation ladder per client:
- L1 (Regional Manager): trigger after 24h
- L2 (Ombudsman Staff): trigger after 48h
- IO (Internal Ombudsman): trigger after 720h (30 days)

#### `escalations` (Per-Ticket Events)
Indexed on `(ticket_id, created_at)` and `next_escalation_at`.

#### `rbi_complaints`
One-to-one with `complaints`. Stores `category_code`, `subcategory_code`, `rbi_reference_number` (unique), `tat_due_date`, `audit_log` (JSON array).

#### `rbi_tat_rules`
Client-specific TAT overrides. Unique on `(client_id, category_code)`.

#### `routing_rules`
Category → Team mapping. Unique on `(client_id, category)`.

#### `teams` / `team_members`
`team_members` tracks `capacity` (default 10), `active_tasks`, `role` (agent\|manager\|supervisor). Index on `(team_id, is_active, role, active_tasks, updated_at)` for routing queries.

#### `unified_messages`
Multi-channel message store. Unique on `(channel, external_message_id)`. Fields: `channel`, `direction` (inbound\|outbound), `status` (sent\|delivered\|failed\|pending), `retry_count`, `next_retry_at`.

#### `usage_records`
Monthly billing tracker. Calculates `overage = max(tickets_processed - limit, 0)` and `overage_cost`.

#### `client_users` / `password_reset_otps`
`password_reset_otps`: `otp_hash` (HMAC-SHA256), `expires_at` (+10 minutes), `attempts` (max 5), `used_at`.

**Note:** `ClientUser` has **no `name` column** — only `id`, `client_id`, `email`, `password_hash`, `created_at`. Display name is derived at runtime from the email local part by `_display_name_from_email()` in `app/auth.py`.

#### `clients.custom_prompt_config` (JSONB) — known sub-keys

```json
{
  "notification_preferences": {
    "sla_breach": false,
    "new_escalation": false,
    "daily_digest": false,
    "ticket_assigned": false,
    "ai_draft_expired": false,
    "auto_ai_reply": true
  },
  "tone": "professional",
  "focus_areas": [],
  "industry": "fintech",
  "classification_rules": {},
  "escalation_rules": {}
}
```

`auto_ai_reply` (default: `true`) — controls whether `HardenedAutoReplyService` runs on every new complaint. When `false`, AI reply is only generated when an agent manually calls `POST /api/v1/complaints/{id}/generate-reply`. When `true` and the generated reply has confidence ≥ 0.90, it is auto-sent without HITL review.

#### `audit_logs` / `ticket_state_transitions` / `model_audit_logs`
Immutable event streams. `model_audit_logs` tracks every Gemini/OpenAI call: provider, model, task_type, prompt_hash, confidence_score, latency_ms, status.

#### `workflow_executions`
Idempotent job tracking. Unique on `idempotency_key`. Fields: `execution_status` (pending\|succeeded\|failed\|retrying), `retry_count`, `max_retries` (3), `error_json` (JSONB).

### 4.2 Migration Timeline

| Date | Key Changes |
|---|---|
| 2026-03-17 | Response time tracking columns |
| 2026-03-18 | Analytics & queue columns |
| 2026-03-22 | SynapFlow feature columns |
| 2026-03-29 | Ticketing v2, Customer 360, AI reply queue, RBI compliance, multi-tenant RLS |
| 2026-04-01 | Multi-level escalation, RBI TAT rules |
| 2026-04-08 | Unified inbox email ingestion |
| 2026-04-10 | Team routing & workload balancing |
| 2026-04-12 | Reply drafts HITL, customer identity merge |
| 2026-05-22 | Event intelligence, async workflow execution queue |
| 2026-06-01 | Job queue, unified messages fix, consent records, invoice GSTIN, password reset OTPs |
| 2026-06-02 | Gmail ingestion fixes: 5 DB schema mismatches resolved (inbox polling, unified messages) |
| 2026-06-03 | Drop `customer_events_complaint_id_fkey` FK constraint (was blocking bulk complaint deletion) |

---

## 5. API Reference

### 5.1 Route Namespacing

| Prefix | Auth | Purpose |
|---|---|---|
| `/webhook/*` | `x-api-key` header | Complaint ingestion (no JWT) |
| `/api/v1/*` | Bearer JWT | Client-facing REST API |
| `/api/admin/*` | Bearer = ADMIN_PASSWORD | Internal admin endpoints |
| `/integrations/*` | Webhook secret / HMAC | Third-party webhooks (Gmail, WhatsApp, Email, Voice) |
| `/auth/*` | Session cookie | Login, logout, OAuth callbacks |
| `/embed/*` | API key (query param) | Chatbot iframe embed |

### 5.2 Key Endpoints

#### Complaint Ingestion
```
POST /webhook/complaints
  Auth: x-api-key header
  Body: { message: str, source: str, customer_email: str?, customer_phone: str?, ticket_id: str? }
  Limits: message max 10,000 chars
  Response: { ticket_id, id, status }
```

#### Auth (JWT)
```
POST /api/v1/auth/login           { email, password } → { access_token, refresh_token, expires_in }
POST /api/v1/auth/refresh         { refresh_token } → { access_token }
POST /api/v1/auth/forgot-password { email } → 200 OK (sends OTP)
POST /api/v1/auth/reset-password  { email, otp, new_password } → 200 OK
```

#### Complaint Management
```
GET  /api/v1/complaints           List (filterable by status, priority, category, sentiment)
POST /api/v1/complaints           Create new complaint
GET  /api/v1/complaints/{id}      Complaint detail
PATCH /api/v1/complaints/{id}     Update fields (status, assignment, notes)
```

#### Ticket State Machine
```
GET  /api/v1/tickets/{id}
POST /api/v1/tickets/{id}/transition  { to_state, reason, actor, metadata }
```

#### AI Reply Queue
```
GET  /api/v1/reply-queue                           List (filter by status)
POST /api/v1/reply-queue/{id}/approve              { edited_reply?, edited_subject? }
POST /api/v1/reply-queue/{id}/reject               { reason }
POST /api/v1/complaints/{id}/generate-reply        Manual AI reply generation (no body required)
  → Auth: Bearer JWT
  → Bypasses all eligibility checks (spam, escalated, legal flags)
  → Always creates a HITL-pending draft (force_human_review=True)
  → Returns full serialized complaint including ai_reply_status
  → 422 if Gemini fails to generate a draft
```

#### RBI Compliance
```
GET  /api/v1/rbi-compliance/complaints             List with TAT status
GET  /api/v1/rbi-compliance/mis-report             Generate MIS report
POST /api/v1/rbi-compliance/escalate/{id}          Manual escalation trigger
```

#### Teams & Routing
```
GET  /api/v1/teams                                 List teams
POST /api/v1/teams                                 Create team
POST /api/v1/teams/{id}/members                    Add member
GET  /api/v1/teams/{id}/workload                   Capacity view
```

#### Customers
```
GET  /api/v1/customers                             List with risk/status filter
GET  /api/v1/customers/{id}                        360 profile + complaint history
```

---

## 6. Core Service Specifications

### 6.1 Complaint Ingestion (`app/intake/webhook.py`)

Processing order:
1. API key validation → client lookup
2. Usage quota check (`can_process_ticket`)
3. Input sanitisation + deduplication via `thread_id` hash
4. `classify_message_async()` → Gemini 2.5 Flash Lite
5. Summarisation (messages > 40 words)
6. `analyze_sentiment()` if plan has `sentiment_analysis` feature
7. `RoutingService.route_ticket()` → team + agent assignment
8. `CustomerProfileService.sync_customer_for_complaint()` → create/merge customer
9. `SLAManager.refresh_ticket_deadline()` → set `sla_due_at`
10. `TicketStateMachine.sync_from_legacy()` → initialise state = `new`
11. RBI registration if `client.is_rbi_regulated`
12. Automation rule matching + `HardenedAutoReplyService.generate_and_queue_reply()`
13. Usage tracking (`track_ticket_usage`)
14. Audit log append

### 6.2 AI Classification (`app/intelligence/classifier.py`)

**Model:** Gemini 2.5 Flash Lite  
**Endpoint:** `https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash-lite:generateContent`

Output fields and allowed values:
```
intent:             complaint | refund_request | sales_lead | support | order_status | feature_request
category:           refund | billing | technical | abuse | general | sales | spam
recommended_action: escalate | notify_sales | support_ticket | auto_reply | product_feedback
sentiment:          Float [-1.0, 1.0]
urgency_score:      Float [0.0, 1.0]
priority:           Integer [1, 5]
confidence:         Float [0.0, 1.0]
emotion_dimensions: { frustration, urgency, confusion, satisfaction, aggression, loyalty } each [0.0, 1.0]
```

Fallback on API failure / low confidence:
```json
{ "intent": "complaint", "category": "general", "sentiment": 0.0,
  "urgency_score": 0.3, "priority": 2, "recommended_action": "support_ticket", "confidence": 0.0 }
```

Retry: 3 attempts, exponential backoff (1–10s), circuit breaker via `utils/circuit_breaker.py`.

### 6.3 Reply Generation (`app/intelligence/reply_engine.py`)

**Model:** Gemini 2.0 Flash  
**Endpoint:** `https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent`

Parameters: `temperature=0.7`, `maxOutputTokens=500`, `timeout=15s`

Confidence scoring:
- ≥ 0.85 → auto-approve and send
- 0.60–0.85 → enqueue for HITL review (`ai_reply_queue`)
- < 0.60 → discard

`AIReplyQueue` record: `expires_at = now + 24 hours`. Queue entry includes `hallucination_check_passed`, `toxicity_score` (< 0.3 required), `factual_consistency_score`.

### 6.4 Routing Service (`app/services/routing_service.py`)

Algorithm:
1. Look up `RoutingRule` by `(client_id, category)`
2. Fetch active `TeamMember` records for matched team
3. Sort by `active_tasks / capacity` (lowest utilisation first)
4. For priority ≥ 3: prefer manager/supervisor roles
5. Increment `active_tasks` on selected member
6. Record `TicketAssignment`, log audit

Falls back to legacy heuristic `assign_team(category, intent)` if no routing rule configured.

### 6.5 SLA Manager (`app/services/sla_manager.py`)

Lookup: `SLAPolicy` by `(client_id, priority_level, enabled=true)`

Business hours calculation: iterates calendar days (max 365), accumulates minutes within configured `(start_time, end_time)` per `day_of_week`. Skips non-business days.

Status transitions:
- `time_remaining ≤ 0` → `breached`
- `time_remaining ≤ 4 hours` → `at_risk`
- else → `on_track`

### 6.6 Escalation Engine (`app/services/escalation_engine.py`)

Standard RBI escalation ladder:

| Level | Trigger After | Escalate To |
|---|---|---|
| L1 | 24 hours | `regional_manager@rbi` |
| L2 | 48 hours | `ombudsman_staff@rbi` |
| IO | 720 hours (30 days) | `system@io` (Internal Ombudsman) |

Auto-creates `EscalationLevelDefinition` records if missing for new clients.
Triggers: SLA breach, TAT breach, time threshold, manual.
Prevents duplicate escalation via `next_escalation_at` check.

### 6.7 Model Orchestration (`app/services/model_orchestration.py`)

Central layer for all Gemini API calls. Provides:
- `get_model_orchestrator()` — returns singleton orchestrator
- `parse_json_model_output()` — extracts JSON from Gemini markdown-wrapped responses
- `audit_model_call()` — writes to `model_audit_logs` (provider, model, task_type, prompt_hash, confidence, latency_ms, status)
- `timed_ms()` — context manager that measures call duration

### 6.8 Voice Agent (`app/services/voice_agent.py`)

Lazy-loaded transcription + synthesis:
- `transcribe_audio(audio_bytes, mime_type)` — Deepgram Nova-2; returns transcript string or `""` if `DEEPGRAM_API_KEY` not set
- `synthesize_speech(text, voice_id)` — ElevenLabs turbo v2; returns MP3 bytes or `b""` if `ELEVENLABS_API_KEY` not set
- Both functions import deepgram-sdk / elevenlabs inline (not at module level) to avoid crash when keys are absent

### 6.9 RBI Compliance (`app/services/rbi_compliance.py`)

TAT resolution priority:
1. Client-specific rule in `rbi_tat_rules` for that category
2. Category default (`RBIComplaintCategory.tat_days`)
3. System default: `RBI_TAT_DEFAULT_DAYS` (30 days)

TAT states:
- `resolved_at > tat_due_at` or `now > tat_due_at` → `breached`
- `(tat_due_at - now) < 5 days` → `approaching_breach`
- else → `within_tat`

RBI reference number format: `{category}:{unix_timestamp}:{8-char-hash}`

Monthly MIS report aggregates: total_complaints, by_category, resolved_within_tat, tat_breach_count, avg_resolution_days, escalated_to_regional, escalated_to_nodal, escalated_to_ombudsman, satisfaction_rate.

---

## 7. Background Worker (`app/queue/worker.py`)

Thread started at FastAPI startup. Main loop interval: **30 seconds**.

| Job | Interval | Description |
|---|---|---|
| `process_follow_up_automation` | 30s | Send follow-up after 24h; auto-resolve after 48h no response |
| `process_sla_monitor` | 10 min (`SLA_MONITOR_INTERVAL_MINUTES`) | Batch update sla_status; max 500 tickets |
| `process_spike_detection` | 1 hour | Detect complaint volume spikes; alert via Slack |
| `process_rbi_tat_monitor` | 30 min | Check TAT breaches; trigger escalation |
| `process_rbi_mis_report_generation` | Monthly (day `RBI_MIS_REPORT_DAY`, 1am) | Auto-generate previous month's MIS report |
| `process_escalation_checks` | 30s | Advance escalations where `next_escalation_at ≤ now` |
| `process_inbox_polling` | 15 min | Poll Gmail, WhatsApp inboxes for new messages |

Job queue backends: PostgreSQL (default), Redis (optional), SQLite (fallback path `data/jobs.db`).
For scale, move to `worker_standalone.py` (separate process).

---

## 8. Authentication & Session Management

### 8.1 Session Auth (Portal / Web)
- Endpoint: `POST /auth/login` (form data)
- Session cookie: `session_token` (httpOnly, secure, samesite=lax, max_age=7 days)
- Serialiser: `itsdangerous.URLSafeTimedSerializer` keyed by `SECRET_KEY`
- Logout: `POST /auth/logout` (clears session)

### 8.2 JWT Auth (API / React SPA)
- Endpoint: `POST /api/v1/auth/login`
- Serialiser: `itsdangerous.URLSafeTimedSerializer` with salts (`"access"` / `"refresh"`)
- Access token: 60-minute TTL
- Refresh token: 30-day TTL
- Validation dependency: `Depends(get_current_user)` on all `/api/v1/*` routes

### 8.3 API Key Auth
- Header: `x-api-key`
- Lookup: `Client.api_key` (UNIQUE index)
- Dependency: `Depends(require_api_key)` on webhook routes

### 8.4 Admin Auth
- Bearer token = `ADMIN_PASSWORD` environment variable
- Dependency: `Depends(get_current_admin_user)` — used on all `/api/admin/*` and `/legacy-admin/create-client` routes
- Comparison: direct string equality (plain bearer token, not bcrypt — admin password is an env-var secret, not a user credential)

### 8.5 Password Reset (OTP)
- Flow: `POST /forgot-password` → generate 6-digit OTP → hash with HMAC-SHA256 → store in `password_reset_otps`
- OTP TTL: 10 minutes; max 5 attempts; single-use (`used_at` set on consume)
- Delivery: Resend API (primary) or SMTP (fallback)
- Reset: `POST /reset-password` validates OTP hash, sets new bcrypt password

---

## 9. Billing & Usage

### 9.1 Plan Definitions (`app/billing/plans.py`)

| Plan | Monthly | Annual | Tickets/mo | Seats | Overage Rate |
|---|---|---|---|---|---|
| Free | ₹0 | ₹0 | 50 | 1 | ₹0 |
| Starter | ₹2,999 | ₹29,990 | 500 | 3 | ₹4/ticket |
| Pro | ₹4,999 | ₹49,990 | 2,000 | 10 | ₹3/ticket |
| Max | ₹9,999 | ₹99,990 | 10,000 | 25 | ₹2/ticket |
| Scale | ₹99,999 | ₹9,99,990 | 1,00,000 | 100 | ₹1/ticket |
| Enterprise | Custom | Custom | 9,99,999 | 999 | ₹0 |

### 9.2 Usage Tracking

- `UsageRecord` per client per calendar month (1st–last day)
- `overage = max(tickets_processed − monthly_ticket_limit, 0)`
- `overage_cost = overage × plan.overage_rate`
- Trial check: Starter plan — hard-block after `trial_ends_at`
- Quota enforcement: `QuotaEnforcer` middleware increments and checks on every ticket

**`GET /api/usage` response** (correct field names — the frontend must use these):
```json
{
  "current_usage": 42,
  "monthly_limit": 2000,
  "tickets_processed": 42,
  "period_end": "2026-06-30T23:59:59",
  "usage_percentage": 2.1,
  "remaining_tickets": 1958,
  "history": [...],
  "category_breakdown": [...]
}
```
⚠️ The fields `tickets_used` and `tickets_quota` do **not** exist in this response. Any frontend code that references them will get `undefined`.

### 9.3 Razorpay Integration

- Checkout: `POST /api/billing/create-order`
- Webhook: `POST /integrations/razorpay` (HMAC-SHA256 signature verification)
- Plan IDs per tier stored as env vars (`RAZORPAY_PLAN_PRO_MONTHLY`, etc.)

---

## 10. Multi-Channel Ingestion

### 10.1 REST API Webhook
`POST /webhook/complaints` — any `source` value, authenticated by `x-api-key`.

### 10.2 Gmail
- OAuth 2.0 flow; credentials encrypted with `CHANNEL_CRYPTO_KEY` (AES)
- Pub/Sub push notifications (`GMAIL_PUBSUB_TOPIC`)
- Webhook handler: `POST /integrations/gmail`
- Poller fallback: `process_inbox_polling()` every 15 minutes

### 10.3 WhatsApp (Meta Business API)
- Webhook: `POST /integrations/whatsapp`
- Signature verification: `X-Hub-Signature-256` (HMAC-SHA256 with `WHATSAPP_APP_SECRET`)
- Verify challenge: `GET /integrations/whatsapp` (token check)
- API version: `v22.0` (configurable via `WHATSAPP_DEFAULT_API_VERSION`)

### 10.4 Email Forwarding (SMTP Inbound)
- Webhook: `POST /integrations/email`
- Verification: `INBOUND_EMAIL_WEBHOOK_SECRET`
- Routes parsed email bodies as complaints via standard pipeline

### 10.5 Live Chat Widget
- Endpoint: `GET /embed` → serves iframe HTML
- Chatbot: `POST /api/chatbot/message` — Gemini-powered; uses complaint history as context
- Auth: API key passed as query param in embed URL

---

## 11. Frontend

**Framework:** Vite 6 + React 18 — single-page application, static build to `frontend/out/`  
**Router:** react-router v7  
**Styling:** Tailwind CSS **v4** (uses `@import 'tailwindcss'` syntax; no `tailwind.config.js`)  
**Component library:** Radix UI + shadcn/ui (CSS variable-driven tokens; all components dark-mode aware)  
**Charts:** Recharts  
**HTTP client:** Native `fetch` via custom `request()` wrapper in `frontend/src/app/lib/api.ts` — no Axios  
**Dark mode:** Custom `ThemeProvider` in `frontend/src/app/lib/theme-context.tsx` — persists to `localStorage("theme")`; toggles `.dark` class on `<html>`; CSS vars defined in `frontend/src/styles/theme.css`  
**Toasts:** Sonner  
**Icons:** lucide-react  

### 11.1 Key Routes (react-router v7)

| Route | Feature |
|---|---|
| `/` | Public landing page |
| `/login` · `/signup` · `/forgot-password` | Auth (unauthenticated) |
| `/app/dashboard` | KPI summary |
| `/app/complaints` | Inbox with filters + bulk actions |
| `/app/complaints/:id` | Complaint detail + reply card |
| `/app/customers` · `/app/customers/:id` | Customer 360 |
| `/app/assignments` | Agent workload |
| `/app/analytics` | Charts + root cause |
| `/app/reply-queue` | HITL approval queue |
| `/app/compliance` | RBI tracking (Scale+) |
| `/app/knowledge` | Knowledge base |
| `/app/billing` | Plan comparison + upgrade |
| `/app/settings` | Profile settings |
| `/app/settings/connections` | Channel connectors (13 connectors, pill tabs) |
| `/app/settings/notifications` | Alert preferences |
| `/app/settings/webhooks` | Outbound webhooks |
| `/app/settings/teams` | Team management |
| `/app/settings/automations` | Automation rules + Auto AI Reply toggle |
| `/app/admin` | Internal admin panel |

### 11.2 Auth Architecture

React SPA stores JWT token and user object in **localStorage** (`synapflow_token`, `synapflow_user`). On mount, `AuthProvider` hydrates from localStorage. On `login()`, calls `/api/v1/auth/login` for the token then `/api/settings` to build the `User` object, then writes both to localStorage and React state. `logout()` clears all three localStorage keys.

**User display name:** The `ClientUser` DB table has no `name` column. The sidebar shows `user.companyName` (the `Client.name` field, set at signup as "company name"). The backend derives an email-based display name via `_display_name_from_email()` in `app/auth.py` (e.g. `prem.synapflow@gmail.com` → `Prem Synapflow`) — this is used as a fallback only.

The server-rendered Client Portal (`app/client_portal.py` + Jinja2 templates) uses session cookies — a separate auth system that does not share state with the React SPA.

---

## 12. Security Architecture

### 12.1 Multi-Tenancy
All DB queries include `client_id` filter derived from authenticated user. Optional SQL-level Row-Level Security via `ENABLE_RLS=true`.

### 12.2 Encryption
| Asset | Method |
|---|---|
| User passwords | bcrypt (via `passlib`) |
| OTP codes | HMAC-SHA256 stored hash |
| Session tokens | `itsdangerous.URLSafeTimedSerializer` |
| JWT tokens | `itsdangerous.URLSafeTimedSerializer` (salted) |
| Gmail OAuth tokens | AES encryption via `CHANNEL_CRYPTO_KEY` |

### 12.3 Audit Trail
- `audit_logs` — entity state changes (before/after JSON)
- `ticket_state_transitions` — ticket lifecycle
- `model_audit_logs` — every Gemini/OpenAI call
- `customer_events` — event stream (churn triggers, reply sent, escalations)
- `request_audit` — every HTTP request (IP, path, status)

### 12.4 Rate Limiting
- `DatabaseRateLimitMiddleware` — per-client limits stored in DB
- Request size cap: 2 MB (SecurityHeadersMiddleware)

---

## 13. Monitoring & Observability

### 13.1 Sentry
- Enabled when `SENTRY_DSN` set and `ENVIRONMENT != dev`
- Transaction sampling: 10%
- Profiling sampling: 10%
- Integrations: FastAPI, SQLAlchemy

### 13.2 Health Endpoints
```
GET /health         DB connectivity check; returns { status, database, timestamp }
GET /health/db      DB-specific check
GET /health/ai      Gemini API reachability check
```

### 13.3 Metrics (stored in `monitoring_metrics`)
- `request_duration_ms` — per endpoint / method
- `error_count` — by status code + path
- `ai_classification_latency` — Gemini call timings
- `queue_processing_time` — background job duration
- `sla_breach_rate` — compliance KPI
- `reply_approval_time` — HITL turnaround

---

## 14. Deployment

### 14.1 Railway (Primary)
Config files: `railway.json` + `nixpacks.toml`  
Start command: `bash start.sh`  
Health check: `GET /health` · timeout: 300s  

`start.sh` flow:
1. Check `frontend/out/` — if missing, run `npm install && npm run build` (safety net; should be skipped after proper build)
2. `alembic upgrade head`
3. `python -m app.db.schema_guard` (additive column sync + index creation)
4. `uvicorn app.main:app --host 0.0.0.0 --port $PORT --workers $WEB_CONCURRENCY`

**nixpacks.toml build phase** installs Node 20 + runs `pip install -r requirements.txt` then `(npm ci --prefer-offline || npm install) && npm run build`. The parenthesis grouping is critical — earlier versions without it caused `npm run build` to be skipped when `npm ci` succeeded, leaving `frontend/out/` missing at runtime and triggering a slow runtime rebuild → 502.

### 14.2 Render (Secondary)
Config file: `render.yaml`

### 14.3 Background Worker (Standalone)
```bash
SERVICE_TYPE=worker bash start.sh
# or
python worker_standalone.py
```

### 14.4 Environment Requirements
- PostgreSQL 14+ (Supabase Mumbai)
- Python 3.11+
- Node 18+ (frontend build only)
- Redis optional (PostgreSQL queue is default)
- Minimum 512 MB RAM (single-process mode)

---

## 15. Key Constants & Thresholds Summary

| Constant | Value | Location |
|---|---|---|
| Reply auto-approve threshold | 0.85 | `REPLY_AUTO_APPROVE_THRESHOLD` env |
| Reply human review threshold | 0.60 | `REPLY_HUMAN_REVIEW_THRESHOLD` env |
| Reply queue expiry | 24 hours | hardcoded in `auto_reply_hardened.py` |
| Toxicity flag threshold | 0.3 | hardcoded in `reply_confidence_scorer.py` |
| Factual consistency default | 0.8 | hardcoded |
| SLA monitor interval | 10 min | `SLA_MONITOR_INTERVAL_MINUTES` env |
| SLA at-risk threshold | 4 hours remaining | `sla_manager.py` |
| L1 escalation trigger | 24 hours | `escalation_engine.py` |
| L2 escalation trigger | 48 hours | `escalation_engine.py` |
| IO escalation trigger | 720 hours (30 days) | `escalation_engine.py` |
| RBI TAT default | 30 days | `RBI_TAT_DEFAULT_DAYS` env |
| RBI approaching breach | 5 days before due | `rbi_compliance.py` |
| Worker loop interval | 30 seconds | `queue/worker.py` |
| Inbox poll interval | 15 minutes | `queue/worker.py` |
| OTP TTL | 10 minutes | `PasswordResetOTP` model |
| OTP max attempts | 5 | `PasswordResetOTP` model |
| Access token TTL | 60 minutes | `ACCESS_TOKEN_EXPIRE_MINUTES` env |
| Refresh token TTL | 30 days | `REFRESH_TOKEN_EXPIRE_DAYS` env |
| Session cookie TTL | 7 days | `session_auth.py` |
| Request size limit | 2 MB | `SecurityHeadersMiddleware` |
| Message max length | 10,000 chars | `ComplaintRequest` Pydantic model |
| Workflow max retries | 3 | `WorkflowExecution` model |
| Routing load-balance metric | `active_tasks / capacity` | `routing_service.py` |
| Business hours max iterations | 365 days | `sla_manager.py` |
| Sentry transaction sample rate | 10% | `main.py` |
| Sentry profiling sample rate | 10% | `main.py` |
