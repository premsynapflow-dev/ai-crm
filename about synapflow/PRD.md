# SynapFlow — Product Requirements Document
**Updated from codebase analysis · June 2026 (rev 3)**

---

## 1. Product Overview

**SynapFlow** is a multi-tenant, AI-powered complaint intelligence SaaS platform targeting Indian fintechs, NBFCs, D2C brands, and e-commerce SMBs. It automates complaint ingestion, classification, routing, and resolution, with a gated RBI compliance module as the primary enterprise upsell.

**Core Value Proposition:** Reduce complaint resolution time by 60–80% through AI-assisted classification, automated routing, human-in-the-loop reply approval, and regulatory compliance automation.

**Stack:** FastAPI (Python) · Vite 6 + React 18 + Tailwind CSS v4 · PostgreSQL via Supabase · Google Gemini AI · Razorpay · Resend

---

## 2. Target Users

| Persona | Role | Primary Pain |
|---|---|---|
| **Support Manager** | Oversees complaint inbox & team | Volume overload, SLA breaches |
| **Support Agent** | Resolves individual complaints | Manual triage, copy-paste replies |
| **Compliance Officer** | RBI/GDPR reporting | Manual TAT tracking, missed escalations |
| **CTO / Tech Lead** | Integrates via API | Multi-channel ingestion complexity |
| **Business Owner** | Monitors CSAT trends | No visibility into complaint patterns |

---

## 3. Subscription Tiers

| Plan | Price/mo | Annual | Tickets/mo | Seats | Overage | Key Gates |
|---|---|---|---|---|---|---|
| **Free** | ₹0 | ₹0 | 50 | 1 | ₹0 | AI Classification, Basic Analytics, Email only |
| **Starter** | ₹2,999 | ₹29,990 | 500 | 3 | ₹4/ticket | +SLA Tracking, Customer History, 30-day trial (no card) |
| **Pro** | ₹4,999 | ₹49,990 | 2,000 | 10 | ₹3/ticket | +Sentiment, Pattern Detection, WhatsApp, Website |
| **Max** | ₹9,999 | ₹99,990 | 10,000 | 25 | ₹2/ticket | +AI Auto-Reply, Churn Risk, Root Cause, API, Instagram, Google Reviews |
| **Scale** | ₹99,999 | ₹9,99,990 | 1,00,000 | 100 | ₹1/ticket | +RBI Compliance, Custom Branding, Webhooks, Custom Channels |
| **Enterprise** | Custom | Custom | Unlimited | Unlimited | ₹0 | +White-label, Custom AI Training, Dedicated Infra, SLA guarantee |

Overage billing is handled automatically via Razorpay. Trials: Starter gets 30 days (no card); Pro gets 14 days (card required).

---

## 4. Features Live on Frontend

### 4.1 Complaints Inbox (`/complaints`)
- List view with filter/sort by status, priority, sentiment, category
- Complaint detail modal: message history, sentiment badge, category, urgency score, AI reply draft
- Status transitions: New → Open → Resolved with audit trail
- Manual reply sending from modal
- Bulk actions: assign, close, export

### 4.2 Dashboard (`/dashboard`)
- KPI cards: total tickets, open, resolved, CSAT trend
- Volume trend chart, priority breakdown, category distribution
- Quick-action links to inbox and reply queue
- Dark mode support

### 4.3 Customer 360 (`/customers`, `/customers/[id]`)
- Customer list with search and filter by risk/status
- Individual profile: full complaint history, sentiment label, churn risk badge
- Health indicators: VIP, risky, billing-watch, renewal-ready
- Aggregated interaction timeline per customer

### 4.4 Assignments (`/assignments`)
- Team & agent workload view: open ticket count per member
- Manual ticket reassignment via dropdown
- Capacity tracking table (agent → load vs. capacity)

### 4.5 Teams (`/settings/teams`)
- Create and manage teams and members
- Assign roles: agent, manager, supervisor
- View team routing configuration

### 4.6 AI Reply Queue (`/reply-queue`)
- Pending AI-generated draft replies waiting for human approval
- Approve / Edit / Reject workflow (HITL)
- Confidence score display per draft
- Tabbed view: pending, approved, rejected
- Reply expires after 24 hours if unreviewed
- **Generate AI Reply button** — visible in complaint detail reply card when no draft exists; calls `POST /api/v1/complaints/{id}/generate-reply`; bypasses all eligibility blocks (including escalated status) and always creates a HITL-pending draft
- **Auto AI Reply toggle** — iOS-style switch in Settings → Automations. When ON (default): reply generated automatically on complaint arrival; if confidence ≥ 90% the reply is sent immediately without human review. When OFF: agents must click "Generate AI Reply" manually.

### 4.7 RBI Compliance (`/compliance`) — *Scale/Enterprise only*
- TAT status per complaint: within_tat / approaching_breach / breached
- RBI category taxonomy display
- MIS report generation trigger (auto-runs monthly on configured day)
- Escalation level view (L1 → L2 → IO)
- Upgrade prompt for lower-tier plans

### 4.8 Analytics (`/analytics`) — *plan-gated*
- Volume trend (area chart), priority breakdown (bar chart), category distribution (pie chart)
- Churn risk customer list — Max+
- Root cause analysis summary — Max+
- Team performance table — Max+
- Upgrade prompts for locked sections

### 4.9 Billing & Plans (`/billing`)
- Plan comparison table with current plan indicator and "Current" badge
- Upgrade flow via Razorpay checkout (order mode) or hosted payment link
- Monthly / Annual toggle — annual prices are 10× monthly (2 months free); displayed price updates instantly on toggle; effective monthly rate shown below annual price
- Live ticket usage count sourced from `/api/usage` (`current_usage` / `monthly_limit`) — updates on page load and in sidebar

### 4.10 Usage & Limits (`/usage`)
- Tickets used vs. quota this month
- Overage indicator with cost estimate
- Billing cycle dates

### 4.11 Settings (`/settings`)
- **Profile:** name, email, password change (OTP-based reset)
- **Company:** company name, business type (used for RBI eligibility)
- **API:** API key display & copy
- **Connections:** 13 channel connectors (see 4.12) — pill-style tab navigation
- **Webhooks:** outbound webhook config
- **Notifications:** Slack webhook URL, email alert toggles (SLA breach, new escalation, daily digest, ticket assigned, AI draft expired)
- **Automations:** AI Settings card with **Auto AI Reply** toggle (iOS-style switch) — controls whether AI replies are generated automatically on complaint arrival
- Sidebar user menu shows **company name** (from `Client.name`) not email-derived display name

### 4.12 Inbox Connections (`/settings/connections`)
- Pill-style tab navigation (7 tabs: Gmail, Email IMAP, WhatsApp, Live Chat, Instagram, Google Reviews, REST API) — styled to match the Billing page monthly/annual toggle
- Gmail OAuth: connect/disconnect, manual sync ("Sync Now" button), status badge
- Email (IMAP): any IMAP mailbox (Outlook, Yahoo, Zoho, custom SMTP)
- WhatsApp (Meta Business API): connect/disconnect, webhook config reference
- Live Chat Widget: API key + embed code generator
- Instagram DMs: connect UI (Max+ plans; integration coming soon)
- Google Reviews: connect UI (Max+ plans; integration coming soon)
- REST API: API key display + webhook endpoint reference

### 4.13 Live Chat Widget (`/settings/widget`)
- Widget embed code generator (iframe snippet with `apiKey` param)
- Company name configuration for widget branding

### 4.14 Admin Panel (`/admin`) — *Internal only*
- Overview: total tenants, active tenants, total tickets, active subscriptions
- Tenant list with plan status
- Manual plan override capability

### 4.15 Auth (`/login`, `/signup`)
- Email/password signup with business type field (RBI eligibility detection)
- Session-based auth (cookie) + JWT tokens for API clients
- OTP-based password reset (6-digit, 10-minute TTL)

### 4.16 Public Landing Page (`/`)
- Marketing copy, feature highlights, pricing section, CTA
- Signup / Login links
- Dark mode toggle button in header

### 4.17 Dark Mode
- Toggle button in dashboard header (Moon/Sun icon) and landing page header
- Preference persisted to `localStorage("theme")`; applied as `.dark` class on `<html>`
- All shadcn/ui components (Card, Button, Input, Badge, Table, etc.) auto-respond via CSS variables
- Structural layout elements (sidebar, header bar, page backgrounds, auth pages) have explicit `dark:` Tailwind classes
- SynapFlow logo (`/logo.png`) used as favicon, sidebar brand mark, and on all auth/landing pages — replaces the generic Bot icon at all brand identity locations

---

## 5. Features Built but NOT Visible on Frontend

These are fully implemented in the backend with working API endpoints but have no dedicated React UI yet.

| Feature | Backend Location | Notes |
|---|---|---|
| **Knowledge Base / Snippets** | `services/knowledge.py`, `api/v1/knowledge.py` | Full CRUD API; no frontend page |
| **Feedback Learning** | `services/feedback_learning.py` | Records agent corrections & churn outcomes; no UI |
| **Model Audit Log** | `api/v1/model_audit.py` | AI decision audit trail API; not in admin panel |
| **Workflow DSL / Automation Rules** | `services/workflow_dsl.py`, `services/action_executor.py` | Rule engine built; no frontend rule builder |
| **Custom Prompts (per-tenant)** | `api/admin/admin_prompts.py` | Per-tenant AI prompt override; API-only |
| **Compliance Escalation** | `api/v1/compliance_escalation.py` | L1/L2/IO escalation path; no separate UI flow |
| **Queue Health** | `api/v1/queue_health.py` | Background job health check; no dashboard widget |
| **Conversation Threads** | `services/conversation_threads.py` | Groups messages by thread; not surfaced in inbox |
| **Response Tracking** | `services/response_tracking.py` | Reply SLA per message; no timeline view |
| **Retry Service** | `services/retry_service.py` | Failed job retry logic; no admin visibility |
| **Client Portal (server-rendered)** | `app/client_portal.py` + `app/templates/portal_*.html` | Jinja2 HTML portal separate from the React SPA; includes login, tickets, analytics, billing, inbox, leads, automation, settings, usage |
| **Root Cause Report (standalone)** | `services/root_cause.py` | Full report generation; only summary shown in Analytics |
| **Notifications API** | `api/v1/notifications.py` | Push/in-app system built; no notification bell/drawer |

---

## 6. Features Partially Visible (Backend Richer Than UI)

| Feature | What's Built | What's Shown |
|---|---|---|
| **SLA Tracking** | Full state machine with breach timestamps and business-hours-aware calculation | Only shown in RBI Compliance page (Scale+); no SLA column in inbox |
| **Escalation Engine** | L1/L2/IO auto-escalation with configurable time triggers | Escalation status not visible in complaint detail modal |
| **Sentiment Analysis** | 1–5 intensity score + label + 6 emotion dimensions (frustration, urgency, confusion, satisfaction, aggression, loyalty) | Only label badge shown; numeric score not displayed |
| **Urgency Score** | Dynamic 0.0–1.0 floating score | Shown as priority badge; score rationale not exposed |
| **Churn Risk** | Full score + recommendation text + lifetime value | Risk badge shown in Customer 360; recommendation text not rendered |
| **Team Performance** | Per-agent stats table (Max+) | Shown in Analytics without drill-down |
| **Inbox Poller** | Gmail + WhatsApp polling with retry and exponential backoff | Connected status shown; polling logs not visible |
| **Auto-Reply Hardening** | Hallucination check + toxicity filter + factual consistency score | Shown as confidence score only; individual flags not surfaced |
| **Ticket State Machine** | 10-state machine (new → assigned → in_progress → waiting_customer → waiting_internal → on_hold → escalated → resolved → closed → spam/invalid) | UI shows simplified 3-state view (New / Open / Resolved) |

---

## 7. AI Pipeline

| Component | Model | Role |
|---|---|---|
| `intelligence/classifier.py` | Gemini 2.5 Flash Lite | Category, intent, sentiment, urgency, priority, confidence |
| `intelligence/sentiment.py` | Gemini | Sentiment label + intensity score (1–5) + 6 emotion dimensions |
| `intelligence/urgency.py` | — | Priority scoring (1–5) |
| `intelligence/reply_engine.py` | Gemini 2.0 Flash | Draft reply generation with confidence scoring |
| `services/auto_reply_hardened.py` | — | Hallucination check + toxicity filter before queue entry |
| `services/reply_confidence_scorer.py` | — | Routes to auto-approve (≥0.85) or human review (≥0.60) or discard (<0.60) |
| `services/model_orchestration.py` | — | Multi-step AI call orchestration |
| `services/churn_risk.py` | — | Churn risk scoring from complaint history + sentiment |
| `services/root_cause.py` | — | Root cause report (30-day rolling window) |
| `services/rbi_taxonomy_classifier.py` | — | Maps complaints to official RBI category codes |
| `intelligence/prompt_builder.py` | — | Per-tenant prompt customisation layer |

**Quality thresholds:**
- Auto-approve reply: confidence ≥ 0.85
- Queue for human review: confidence 0.60–0.85
- Discard: confidence < 0.60
- Toxicity flag threshold: score > 0.3

---

## 8. Ingestion Channels

| Channel | Built | UI Visible | Auth |
|---|---|---|---|
| **REST API Webhook** | ✅ Full | ✅ Connections tab | API key |
| **Gmail (OAuth polling)** | ✅ Full | ✅ Connection UI | Google OAuth 2.0 |
| **WhatsApp (Meta Business API)** | ✅ Full (webhook + HMAC signature verify) | ✅ Connection UI | App secret |
| **Email Forwarding (SMTP inbound)** | ✅ | ✅ Forwarding address shown | Webhook secret |
| **Live Chat Widget** | ✅ (`/embed` iframe + chatbot) | ✅ Widget settings page | API key (embed) |
| **Slack** | ⚠️ Outbound alerts only; no inbound | ✅ Webhook URL field | Webhook URL |
| **Instagram** | ✅ (Max+) | ❌ No connection UI | Meta API |
| **Google Reviews** | ✅ (Max+) | ❌ No connection UI | Google API |
| **Voice/Call Transcription** | ⚠️ Partial — `app/integrations/voice.py` + `app/services/voice_agent.py` built; Deepgram (STT) + ElevenLabs (TTS) lazy-loaded when keys set | ❌ No UI | `DEEPGRAM_API_KEY` / `ELEVENLABS_API_KEY` |

---

## 9. Data Architecture Highlights

- **Multi-tenant:** All queries scoped by `client_id`; Row-Level Security (RLS) optional via env flag
- **Audit log:** Every ticket state change and AI interaction logged (`AuditLog`, `TicketStateTransition`, `CustomerEvent`)
- **Alembic migrations:** DB version-controlled with 10 major migrations since March 2026
- **Background jobs:** In-process SQL-backed worker thread (no Redis/Celery required); Redis supported as optional backend
- **JSONB:** Used for flexible per-tenant config, feature flags, audit metadata, emotion dimensions
- **Customer deduplication:** Email-based identity merge with confidence scoring

---

## 10. Compliance & Regulatory

### RBI Compliance (Scale/Enterprise)
- Auto-generate RBI reference numbers per complaint
- TAT tracking configurable per category and per client
- Three-level escalation: L1 (Regional Manager, 24h) → L2 (Ombudsman Staff, 48h) → IO (Internal Ombudsman, 30 days)
- Monthly MIS report auto-generation
- Immutable audit log per complaint

### Data Privacy (All Plans)
- DPDP Act (India) compliance hooks
- GDPR/CCPA data deletion support
- IT Act 2000 alignment
- CAN-SPAM for email communications
- Data stored in Mumbai Supabase region (`kyljtdjvnmaffmdhhzzw`)

---

## 11. Known Gaps & Roadmap Signals

| Gap | Evidence | Priority |
|---|---|---|
| Voice/call transcription ingestion | Routes + service built; no API key UI; no connection page | Medium |
| Salesforce / Zendesk connectors | No code; noted as roadmap | Medium |
| Workflow rule builder UI | Rules engine built; no frontend | High |
| Knowledge base UI | Service + API built; no frontend | High |
| Notification centre (bell/drawer) | API built; no React component | Medium |
| Model audit UI | API built; not in admin panel | Low |
| Client portal linked to SPA | Two separate auth systems; cookie vs JWT | Medium |
| Escalation status in inbox | Backend built; UI not surfaced | Medium |
| SLA column in complaint inbox | Backend full; UI simplified | Medium |
| `frontend_verify_20260427/` cleanup | Snapshot artifact in repo root | Low |
| Voice channel connection UI | Routes/service built; no `/settings/connections` card for voice | Low |
| Deepgram/ElevenLabs env var UI | Keys must be set manually in Railway; no settings page | Low |

---

## 12. Test Coverage

35 test files covering: complaint API, ticket state machine, escalation engine, RBI compliance, auto-reply drafts, AI services, billing/usage, routing, customer profile, inboxes, team assignment, unified ingestion, public signup, rate limiting, security, webhooks, and load testing.

Test infrastructure: SQLite in-memory DB, background workers disabled, schema guard disabled.
