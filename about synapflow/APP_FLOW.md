# SynapFlow — Feature App Flow Reference
**Complete step-by-step flow for every feature · June 2026 (rev 3)**

This document traces the exact code path for every major feature — from HTTP request to database write to background job. File paths are relative to the repo root.

---

## 1. Complaint Ingestion (REST API)

**Endpoint:** `POST /webhook/complaints`  
**Auth:** `x-api-key` header  
**File:** `app/intake/webhook.py`

```
HTTP Request
  ↓
1. API key validation
   → db.query(Client).filter(Client.api_key == x_api_key)
   → 401 if not found
   ↓
2. Usage quota check (app/billing/usage.py)
   → can_process_ticket(client) — checks monthly_ticket_limit vs UsageRecord.tickets_processed
   → Trial check: if trial_ends_at < now → hard block (402)
   → Pro overage: continue, accrue cost
   ↓
3. Input sanitisation (app/utils/sanitize.py)
   → bleach.clean() strips HTML/scripts
   → max 10,000 chars enforced by Pydantic model
   ↓
4. Deduplication
   → thread_id = sha256(client_id + customer_email + message[:100])
   → ticket_id = stable hash for idempotency
   ↓
5. AI Classification (app/intelligence/classifier.py)
   → build_classification_prompt(message, client.custom_prompt_config)
   → POST https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash-lite:generateContent
   → parse_json_model_output() extracts: intent, category, sentiment, urgency_score, priority, confidence, emotion_dimensions
   → Circuit breaker (app/utils/circuit_breaker.py) with 3 retries + exponential backoff
   → Falls back to { intent:"complaint", category:"general", confidence:0.0 } on failure
   ↓
6. Summarisation
   → If message > 40 words: Gemini call to generate a 1-sentence summary
   ↓
7. Sentiment Analysis (app/services/sentiment.py) — if plan.sentiment_analysis = true
   → Gemini call for 1–5 sentiment_score + label + 6 emotion dimensions
   ↓
8. Routing (app/services/routing_service.py)
   → RoutingRule lookup by (client_id, category)
   → TeamMember sort by active_tasks/capacity (lowest utilisation first)
   → Priority ≥ 3 prefers manager/supervisor roles
   → Increments TeamMember.active_tasks
   → Writes TicketAssignment record
   ↓
9. Customer Profile Sync (app/services/customer_deduplication.py)
   → Lookup by primary_email (unique per client)
   → Create new Customer or merge into existing master
   → Update total_tickets, last_interaction_at, sentiment_score
   ↓
10. SLA Deadline (app/services/sla_manager.py)
    → Fetch SLAPolicy for (client_id, priority_level)
    → Business-hours-aware calculation (iterates calendar days, accumulates minutes in configured windows)
    → Sets complaint.sla_due_at
    ↓
11. Ticket State Initialisation (app/services/ticket_state_machine.py)
    → complaint.state = "new"
    → Writes TicketStateTransition record
    ↓
12. RBI Registration (app/services/rbi_compliance.py) — if client.is_rbi_regulated
    → rbi_taxonomy_classifier maps category → rbi_category_code
    → Creates RBIComplaint with rbi_reference_number = "{category}:{unix_ts}:{8-char-hash}"
    → Sets tat_due_at from rbi_tat_rules or category default or RBI_TAT_DEFAULT_DAYS
    ↓
13. Automation Rules (app/workflow/rule_engine.py)
    → Match complaint attributes against client AutomationRules
    → If matched: WorkflowExecution enqueued (idempotent via idempotency_key)
    ↓
14. AI Reply Generation (app/services/auto_reply_hardened.py)
    → Fetch similar resolved complaints from knowledge base
    → POST Gemini 2.0 Flash with complaint + examples
    → Hallucination check: verify reply references complaint facts
    → Toxicity score: < 0.3 required to proceed
    → Confidence routing:
      ≥ 0.85 → complaint.ai_reply_status = "approved", send immediately
      0.60–0.85 → insert into AIReplyQueue (status=pending, expires_at=+24h)
      < 0.60 → discard, ai_reply_status = "discarded"
    ↓
15. Usage Tracking (app/billing/usage.py)
    → UsageRecord.tickets_processed += 1
    → overage_cost calculated if over limit
    ↓
16. Audit Log (app/services/audit_logs.py)
    → AuditLog + CustomerEvent + ModelAuditLog written
    ↓
Response: { ticket_id, id, status: "received" }
```

---

## 2. Email Ingestion (Gmail OAuth Inbox)

**Files:** `app/integrations/gmail.py`, `app/inboxes/service.py`, `app/services/inbox_poller.py`

```
Two paths:

Path A — Push (Pub/Sub):
  POST /integrations/gmail
    ↓
  Verify Google Pub/Sub HMAC signature
    ↓
  Decode base64 message data → extract email headers/body
    ↓
  Create complaint via same pipeline as §1 (source="gmail")

Path B — Polling (fallback):
  Background worker (every 15 min) → process_inbox_polling()
    ↓
  Fetch ChannelConnection records (type="gmail", status="active")
    ↓
  Decrypt OAuth tokens (AES via CHANNEL_CRYPTO_KEY)
    ↓
  Gmail API: users.messages.list (label filter)
    ↓
  For each new message: parse body → complaint pipeline (§1)
    ↓
  Update ChannelConnection.last_polled_at

Gmail OAuth Connect Flow:
  GET /auth/gmail/connect → redirect to Google OAuth consent
    ↓
  GET /auth/gmail/callback → exchange code for tokens
    ↓
  Encrypt tokens with CHANNEL_CRYPTO_KEY → store in ChannelConnection
    ↓
  Subscribe to Gmail Push (if GMAIL_PUBSUB_TOPIC is set)
```

---

## 3. WhatsApp Ingestion

**File:** `app/integrations/whatsapp.py`

```
Webhook verification:
  GET /integrations/whatsapp
    → verify hub.verify_token == WHATSAPP_VERIFY_TOKEN
    → return hub.challenge

Inbound message:
  POST /integrations/whatsapp
    ↓
  Verify X-Hub-Signature-256 (HMAC-SHA256 with WHATSAPP_APP_SECRET)
    ↓
  Extract: message body, sender phone, message ID
    ↓
  Deduplication check (message ID stored in UnifiedMessage.external_message_id)
    ↓
  Complaint pipeline (§1, source="whatsapp")
    ↓
  Send acknowledgement reply via Meta API (POST /{version}/messages)
```

---

## 4. Live Chat Widget (Chatbot)

**Files:** `app/api/chatbot.py`, `app/intelligence/chatbot.py`

```
Embed render:
  GET /embed?apiKey={key}
    → validate API key
    → serve iframe HTML with company name + API key pre-filled

Customer sends message:
  POST /api/chatbot/message
  Body: { message, session_id?, api_key }
    ↓
  API key → client lookup
    ↓
  Session ID → fetch recent conversation context (last 10 messages from ReplyCache)
    ↓
  Build Gemini prompt:
    - System: company persona + tone from custom_prompt_config
    - Context: last N complaint resolutions (similar queries from knowledge base)
    - History: conversation thread
    - User message
    ↓
  POST Gemini 2.5 Flash Lite
    ↓
  Cache response in ReplyCache (hash(session_id + message) → reply)
    ↓
  Return: { reply, session_id }
    ↓
  If message classified as complaint → route to complaint pipeline (§1)
```

---

## 5. AI Classification

**File:** `app/intelligence/classifier.py`

```
Input: message text + client config

1. build_classification_prompt(message, client.custom_prompt_config)
   → Merges DEFAULT_CONFIG with client overrides (tone, focus_areas, industry, classification_rules)
   → Returns structured prompt with JSON output schema

2. POST generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash-lite:generateContent
   → Headers: { "x-goog-api-key": GEMINI_API_KEY }
   → retry(stop_after_attempt=3, wait_exponential(min=1, max=10))
   → circuit_breaker (half-open after 60s, threshold 5 failures)

3. parse_json_model_output()
   → Strips markdown code fences if present
   → JSON decode
   → Validate fields: clip sentiment to [-1,1], urgency to [0,1], priority to [1,5]
   → Fill missing fields with fallback defaults

4. audit_model_call() → ModelAuditLog row

Output: ClassificationResult(intent, category, sentiment, urgency_score, priority, confidence, emotion_dimensions, summary)
```

---

## 6. AI Reply Generation (HITL Queue)

**Files:** `app/services/auto_reply_hardened.py`, `app/intelligence/reply_engine.py`, `app/services/reply_confidence_scorer.py`

```
Trigger: end of complaint ingestion (§1 step 14) — only if auto_ai_reply setting is enabled

0. Auto AI Reply gate (app/queue/simple_queue.py):
   auto_ai_reply = client.custom_prompt_config["notification_preferences"]["auto_ai_reply"]
   → Default: True (preserves existing behaviour for all clients)
   → If False: skip steps 1–5 entirely; complaint lands without any AI draft

1. Fetch up to 5 similar resolved complaints (vector/keyword similarity on summary)

2. build_reply_prompt(complaint, similar_resolved)
   → Includes: company tone, complaint text, similar resolutions, instruction to be concise + empathetic

3. POST generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent
   → temperature=0.7, maxOutputTokens=500, timeout=15s

4. Hardening checks:
   a. Hallucination check: key complaint entities (names, amounts, dates) present in reply
   b. Toxicity score: if score > 0.3 → discard
   c. Factual consistency: default score 0.8 if check passes

5. Confidence scoring (reply_confidence_scorer.py):
   → ≥ 0.85 → auto-approve: complaint.ai_reply = reply, ai_reply_status = "approved"
              → enqueue send_email job (if source=email)
   → 0.60–0.85 → insert AIReplyQueue(status=pending, expires_at=now+24h, hallucination_check_passed, toxicity_score)
   → < 0.60 → discard

6. Auto-send at 90%+ confidence (only for automatic ingestion path):
   After commit, if queue_entry.confidence_score ≥ 0.90:
   → HardenedAutoReplyService.approve_reply(entry_id, reviewer_email="system:auto")
   → Reply sent without any human review
   → Failure is caught and logged; complaint draft remains pending

HITL Review (frontend /app/reply-queue):
  GET /api/v1/reply-queue → lists pending drafts
  POST /api/v1/reply-queue/{id}/approve
    → { edited_reply? } — if edited, store edited version
    → AIReplyQueue.status = "approved"
    → Enqueue send_email/send_whatsapp job
  POST /api/v1/reply-queue/{id}/reject
    → { reason }
    → AIReplyQueue.status = "rejected"
    → complaint.ai_reply_status = "rejected"

Expiry: Background worker marks expired (status=pending, expires_at < now) → status = "expired"
```

---

## 7. SLA Tracking

**File:** `app/services/sla_manager.py`

```
SLA deadline set at ingestion (§1 step 10):
  priority → SLAPolicy lookup (client_id, priority_level, enabled=true)
  → Business hours calculation:
     iterate days from now, accumulate minutes within (start_time, end_time) per day_of_week
     stop when accumulated minutes ≥ resolution_minutes
  → complaint.sla_due_at = calculated deadline

Background monitor (every 10 min via worker):
  process_sla_monitor():
    → Fetch open complaints with sla_due_at IS NOT NULL, batch 500
    → For each:
       time_remaining = sla_due_at - now
       if time_remaining ≤ 0 → sla_status = "breached" → Slack alert
       elif time_remaining ≤ 4h → sla_status = "at_risk"
       else → sla_status = "on_track"
    → Batch update

SLA refresh (on state change / assignment):
  SLAManager.refresh_ticket_deadline(complaint)
  → Re-calculates if priority changed
```

---

## 8. Escalation Engine

**File:** `app/services/escalation_engine.py`

```
Standard RBI ladder auto-created per client:
  L1 → regional_manager@rbi, after 24h
  L2 → ombudsman_staff@rbi, after 48h
  IO → system@io, after 720h (30 days)

Triggers (background worker every 30s — process_escalation_checks()):
  → Fetch Escalation records where next_escalation_at ≤ now AND status = "pending"
  → For each:
     1. Look up next EscalationLevelDefinition for current level
     2. complaint.escalation_level += 1
     3. complaint.escalated_to = level.escalate_to_email
     4. complaint.escalated_at = now
     5. complaint.state = "escalated"
     6. TicketStateTransition written
     7. Send Slack alert (if SLACK_WEBHOOK_URL set)
     8. Send email to escalated_to (if SMTP/Resend configured)
     9. Schedule next Escalation record (next_escalation_at = now + next_level.threshold_hours)

Manual escalation:
  POST /api/v1/compliance-escalation/escalate/{ticket_id}
    → Immediately advances to next level
```

---

## 9. Routing & Assignment

**File:** `app/services/routing_service.py`

```
Auto-route at ingestion (§1 step 8):
  1. RoutingRule.query(client_id=client.id, category=classification.category)
     → If found: team = rule.team
     → If not found: fallback heuristic assign_team(category, intent)

  2. TeamMember query:
     → filter(team_id=team.id, is_active=True)
     → sort by active_tasks/capacity ASC
     → If priority ≥ 3: filter role IN ("manager", "supervisor") first
     → Pick first result

  3. complaint.team_id = team.id
     complaint.assigned_user_id = member.user_id
     complaint.assigned_to = member.user.email
     member.active_tasks += 1

  4. TicketAssignment record written
  5. AuditLog written

Manual reassign (frontend /assignments):
  POST /api/v1/dashboard-assignments/reassign
    Body: { ticket_id, new_user_id }
    → Decrement old member.active_tasks
    → Assign to new member
    → TicketStateTransition (ASSIGNED → ASSIGNED with new actor)
```

---

## 10. Ticket State Machine

**File:** `app/services/ticket_state_machine.py`

```
10 states:
  new → assigned → in_progress → waiting_customer | waiting_internal | on_hold
      → escalated → resolved → closed
      → spam | invalid (terminal)

State transition:
  POST /api/v1/tickets/{id}/transition
  Body: { to_state, reason, actor, metadata }
    ↓
  TicketStateMachine.transition(complaint, to_state, actor)
    ↓
  Validates allowed transitions (adjacency matrix)
    ↓
  complaint.state = to_state
  complaint.state_changed_at = now
    ↓
  TicketStateTransition written (from_state, to_state, actor, reason, metadata)
    ↓
  AuditLog written
    ↓
  Side effects per transition:
    → resolved: complaint.resolved_at = now; response_time_seconds calculated; TeamMember.active_tasks -= 1
    → assigned: complaint.state = "assigned"
    → escalated: escalation_engine triggered
```

---

## 11. Customer 360

**Files:** `app/api/v1/customers.py`, `app/services/customer_deduplication.py`, `app/analytics/customer_pulse.py`

```
Customer creation / merge at ingestion (§1 step 9):
  CustomerProfileService.sync_customer_for_complaint(complaint)
    ↓
  Lookup by primary_email (unique per client)
    ↓
  Not found → create new Customer (is_master=True, confidence_score=1.0)
  Found → update: total_tickets++, last_interaction_at, sentiment_score (rolling avg)

Deduplication merge:
  If two customers have same email but different IDs → merge
    → Set merged_customer.is_master = False
    → merged_customer.merged_into = master_customer.id
    → CustomerMergeHistory written

Customer list (GET /api/v1/customers):
  → filter by client_id, risk level, status
  → paginate, return churn_risk_score, total_tickets, sentiment_label

Customer 360 profile (GET /api/v1/customers/{id}):
  → All complaints for customer
  → CustomerInteraction events
  → CustomerNote records
  → Aggregated: avg_satisfaction_score, lifetime_value, churn_risk
  → Health indicators: VIP (lifetime_value > threshold), risky (churn_risk=high)

Churn risk scoring (app/services/churn_risk.py):
  → Input: complaint history, sentiment scores, resolution time, open ticket count
  → Score 0–1; label: low/medium/high
  → Updated on each complaint resolution or sentiment change
```

---

## 12. RBI Compliance

**Files:** `app/services/rbi_compliance.py`, `app/api/v1/rbi_compliance.py`, `app/services/rbi_taxonomy_classifier.py`

```
RBI registration at ingestion (§1 step 12) — if client.is_rbi_regulated:
  1. rbi_taxonomy_classifier.classify(category, intent)
     → Maps to rbi_category_code (ATM, CC, LOAN, DEP, NB, MOBILE, BRANCH, OTHER)
  2. complaint.rbi_category_code = code
  3. TAT lookup:
     a. RBITATRule for (client_id, category_code)
     b. RBIComplaintCategory.tat_days for category
     c. RBI_TAT_DEFAULT_DAYS env (default: 30)
  4. complaint.tat_due_at = now + tat_days
  5. RBIComplaint created:
     rbi_reference_number = "{code}:{unix_ts}:{sha256[:8]}"
     audit_log = [] (immutable JSON array)

TAT monitoring (background worker every 30 min — process_rbi_tat_monitor()):
  → Fetch unresolved complaints with tat_due_at IS NOT NULL
  → For each:
     if resolved_at > tat_due_at OR now > tat_due_at → tat_status = "breached"
     elif (tat_due_at - now) < 5 days → tat_status = "approaching_breach"
     else → tat_status = "within_tat"
  → Trigger L1/L2/IO escalation if breached

MIS Report generation:
  POST /api/v1/rbi-compliance/mis-report?month=2026-05
    ↓
  Aggregate complaints for the given month:
    - total_complaints, by_category breakdown
    - resolved_within_tat count, tat_breach_count
    - avg_resolution_days, escalated_to_regional/nodal/ombudsman
    - satisfaction_rate
    ↓
  RBIMISReport record created
  ↓
  Auto-run: Background worker on day RBI_MIS_REPORT_DAY at 1am
```

---

## 13. Auth — Signup & Login

**Files:** `app/api/session_auth.py`, `app/api/v1/auth.py`

```
Signup:
  POST /auth/signup (session auth) OR POST /api/v1/auth/register (JWT)
  Body: { name, email, password, business_type }
    ↓
  Validate email uniqueness (ClientUser table)
    ↓
  bcrypt.hash(password)
    ↓
  Create ClientUser
    ↓
  Create Client (tenant root):
    - api_key = secrets.token_urlsafe(32)
    - plan = "free", monthly_ticket_limit = 50
    - is_rbi_regulated = (business_type IN {"nbfc", "bank", "fintech"})
    ↓
  Start free trial (if applicable)
    ↓
  Session cookie set (httpOnly, samesite=lax, max_age=7d)
  OR: return { access_token, refresh_token }

Login (session):
  POST /auth/login (form data)
    ↓
  ClientUser lookup by email
    ↓
  passlib.verify(password, hashed_password)
    ↓
  request.session["user_id"] = user.id
  request.session["client_id"] = client.id
    ↓
  Redirect to /dashboard

Login (JWT):
  POST /api/v1/auth/login
  Body: { email, password }
    ↓
  Same verification
    ↓
  URLSafeTimedSerializer(JWT_SECRET_KEY, salt="access").dumps(user_id)
  → access_token (60 min TTL)
  → refresh_token (30 day TTL, salt="refresh")
    ↓
  Return { access_token, refresh_token, expires_in: 3600 }

Password Reset (OTP):
  POST /api/v1/auth/forgot-password { email }
    ↓
  Generate 6-digit OTP
    ↓
  otp_hash = HMAC-SHA256(SECRET_KEY, otp)
    ↓
  PasswordResetOTP(otp_hash, expires_at=+10min, attempts=0)
    ↓
  Send via Resend API (primary) or SMTP (fallback)

  POST /api/v1/auth/reset-password { email, otp, new_password }
    ↓
  Verify HMAC hash, check expiry, check attempts < 5
    ↓
  bcrypt.hash(new_password) → ClientUser.password_hash
    ↓
  otp.used_at = now
```

---

## 14. Billing & Plan Upgrade

**Files:** `app/billing/plans.py`, `app/billing/usage.py`, `app/billing/razorpay_service.py`, `app/billing/router.py`

```
Plan data source: app/billing/plans.py (static dict, no DB required for reads)
  Plans: free, starter, pro, max, scale, enterprise
  Feature flags: per-plan dict (ai_auto_reply, sentiment_analysis, rbi_compliance, etc.)

Usage tracking (per ticket processed):
  app/billing/usage.py → track_ticket_usage(client)
    → Get or create UsageRecord for current calendar month
    → UsageRecord.tickets_processed += 1
    → If tickets_processed > monthly_ticket_limit:
       Pro+: overage_cost += plan.overage_rate (soft limit)
       Trial/Free: raise QuotaExceeded (hard block)

Upgrade flow:
  GET /api/plans → returns all plans with current plan marked
    ↓
  User selects plan on /pricing page → clicks Upgrade
    ↓
  POST /api/billing/create-order
  Body: { plan_id, billing_cycle: "monthly"|"annual" }
    ↓
  razorpay.order.create({ amount, currency: "INR", receipt })
    ↓
  Return { order_id, key_id } → frontend opens Razorpay Checkout

  Payment success → Razorpay fires webhook:
  POST /integrations/razorpay
    ↓
  Verify X-Razorpay-Signature (HMAC-SHA256 with RAZORPAY_WEBHOOK_SECRET)
    ↓
  Event "subscription.charged" or "payment.captured":
    → Update Client.plan = new_plan_id
    → Client.monthly_ticket_limit = plan.tickets_per_month
    → Subscription record created/updated
    → Invoice record created
    ↓
  Return 200

Overage billing:
  End of month: calculate total_overage = max(tickets_processed - limit, 0)
  overage_cost = total_overage × plan.overage_rate
  → Razorpay charge for overage_cost
  → Invoice record
```

---

## 15. Team Management

**File:** `app/api/v1/teams.py`

```
Create team:
  POST /api/v1/teams
  Body: { name }
    ↓
  Team(client_id, name) created
    ↓
  Return team with id

Add member:
  POST /api/v1/teams/{team_id}/members
  Body: { user_id, role, capacity }
    ↓
  TeamMember(client_id, team_id, user_id, role, capacity=10, active_tasks=0)
    ↓
  Unique constraint prevents duplicates

Configure routing rule:
  POST /api/v1/teams/{team_id}/routing-rules
  Body: { category }
    ↓
  RoutingRule(client_id, category, team_id) upserted
    ↓
  Future complaints of this category route to this team

Workload view:
  GET /api/v1/teams/{team_id}/workload
    → Return TeamMember list with active_tasks, capacity, utilisation %
```

---

## 16. Background Worker Jobs

**File:** `app/queue/worker.py`

```
Startup: start_worker_thread(interval_seconds=30) in FastAPI on_startup hook
  → daemon Thread runs _worker_loop() every 30s

Job queue backends:
  QUEUE_BACKEND=auto → postgres (JobQueue table)
  QUEUE_BACKEND=redis → Redis list (SYNAPFLOW:JOBS:QUEUED key)
  Fallback: SQLite at SQLITE_QUEUE_PATH

Recurring jobs run on schedule (not via job queue):
  Every 30s:   process_follow_up_automation() — follow-up after 24h, auto-close after 48h
               process_escalation_checks()    — advance escalations past next_escalation_at
  Every 10min: process_sla_monitor()          — batch-update SLA statuses (max 500)
  Every 15min: process_inbox_polling()        — poll Gmail/WhatsApp inboxes
  Every 30min: process_rbi_tat_monitor()      — check RBI TAT breaches
  Every 1h:    process_spike_detection()      — detect complaint volume spikes → Slack alert
  Monthly:     process_rbi_mis_report_generation() — auto-generate MIS on RBI_MIS_REPORT_DAY

Queued one-shot jobs (enqueued by ingestion pipeline):
  send_email     — sends reply email via Resend/SMTP
  send_slack     — posts Slack alert
  sync_integration — pushes data to third-party (Salesforce, etc.)
  workflow_action  — executes automation rule action (assign, notify, close)
```

---

## 17. Knowledge Base

**Files:** `app/api/v1/knowledge.py`, `app/services/knowledge.py`

```
Create snippet:
  POST /api/v1/knowledge
  Body: { title, content, tags[], category }
    ↓
  KnowledgeSnippet(client_id, title, content, tags, status="active")
    ↓
  Used by reply engine (§6) as context for Gemini prompt

List:
  GET /api/v1/knowledge?category=&status=
    → filter by client_id, category, status

Feedback learning integration:
  When agent edits an AI reply (HITL approval with edit):
    → AgentCorrection record created (original_reply, corrected_reply, correction_type)
    → Future training signal for prompt tuning
```

---

## 18. Analytics

**Files:** `app/api/analytics.py`, `app/analytics/customer_pulse.py`, `app/services/team_performance.py`, `app/services/root_cause.py`

```
Dashboard KPIs (GET /api/analytics/summary):
  → Count complaints by status, priority, category
  → CSAT trend (avg satisfaction_score per day, 30-day window)
  → Volume chart (complaints per day)

Churn risk (GET /api/analytics/churn-risk) — Max+ plans:
  → Customers with churn_risk=high, sorted by churn_risk_score DESC

Team performance (GET /api/analytics/team-performance) — Max+ plans:
  → Per-agent: tickets_handled, avg_resolution_time, CSAT, SLA_breach_rate
  → Aggregated per team

Root cause (GET /api/analytics/root-cause) — Max+ plans:
  → RootCauseAnalysis(30-day rolling):
     cluster complaints by category + emotion_dimensions
     identify top recurring themes + their frequency
     return summary text (Gemini call for narrative)

Customer pulse (app/analytics/customer_pulse.py):
  → CustomerEvent stream aggregation
  → Tracks: churn triggers, escalations, positive resolutions, CSAT submissions
  → Input to churn_risk_score model
```

---

## 19. Workflow Automation (DSL)

**Files:** `app/workflow/rule_engine.py`, `app/workflow/dispatcher.py`, `app/services/workflow_dsl.py`, `app/services/action_executor.py`

```
Rule definition (API-only, no UI):
  POST /api/v1/workflows
  Body: {
    trigger_definition: { event: "complaint.created", conditions: [...] },
    condition_definition: { all: [{ field: "priority", op: "gte", value: 3 }] },
    action_definition: { type: "assign_team", team_id: "..." }
  }
    ↓
  AutomationRule(client_id, trigger_definition, condition_definition, action_definition)

Rule evaluation at ingestion (§1 step 13):
  rule_engine.evaluate(complaint, classification)
    ↓
  For each AutomationRule with trigger=complaint.created:
    → Evaluate condition DSL against complaint attributes
    → If match: enqueue WorkflowExecution(idempotency_key=sha256(rule_id+ticket_id))
    ↓
  dispatcher.dispatch(execution)
    ↓
  action_executor.execute(action_definition, complaint)
    → assign_team: route to specified team
    → send_email: enqueue email job
    → close_ticket: transition to resolved
    → add_tag: update complaint tags
    ↓
  execution.status = "succeeded" | "failed" (with retry up to max_retries=3)
```

---

## 20. Admin Panel

**Files:** `app/api/admin/overview.py`, `app/dashboard.py`, `app/dependencies/auth.py`

```
Auth: Bearer {ADMIN_PASSWORD} on all /api/admin/* routes
  → get_current_admin_user() validates token == settings.admin_password

GET /api/admin/dashboard/overview:
  → Total clients (all tenants)
  → Active tenants (complaint in last 30 days)
  → Total complaints (all time)
  → Active subscriptions (Subscription.status=active count)
  → Recent complaints (last 20, all clients)

Tenant management:
  GET /api/admin/clients → list all Client records with plan + usage
  POST /legacy-admin/create-client → create new tenant (admin-only)
    Body: { name, email, password, plan }
    → Requires get_current_admin_user dependency
    → Creates ClientUser + Client with api_key

Plan override:
  PATCH /api/admin/clients/{id}/plan
    → Client.plan = new_plan
    → Client.monthly_ticket_limit = PLANS[new_plan].tickets_per_month
```

---

## 21. Settings

**File:** `app/api/settings.py`

```
Profile:
  GET/PATCH /api/v1/me → ClientUser name, email

Company:
  GET/PATCH /api/settings/company → Client name, business_sector, is_rbi_regulated

API Key:
  GET /api/settings/api-key → Client.api_key (read-only)
  POST /api/settings/api-key/rotate → generate new UUID-based key

Outbound Webhooks:
  POST /api/settings/webhooks → store webhook URL for event delivery

Slack Notifications:
  PATCH /api/settings/notifications → Client.slack_webhook_url

Live Chat Widget:
  GET /api/settings/widget → { embed_snippet, api_key, company_name }
  → Embed snippet: <iframe src="/embed?apiKey={key}" />
```

---

## 22. Inboxes (Gmail/IMAP Connection Management)

**Files:** `app/inboxes/router.py`, `app/inboxes/service.py`

```
Connect Gmail inbox:
  POST /api/inboxes/connect/gmail
    → Redirect to Google OAuth
  GET /api/inboxes/oauth/callback/gmail
    → Exchange code for tokens
    → Encrypt with CHANNEL_CRYPTO_KEY (AES)
    → ChannelConnection(type="gmail", status="active", credentials_encrypted=...)
    → Subscribe to Gmail Pub/Sub if GMAIL_PUBSUB_TOPIC set

List inboxes:
  GET /api/inboxes → ChannelConnection list per client

Disconnect:
  DELETE /api/inboxes/{id}
    → Revoke Google OAuth token
    → ChannelConnection.status = "disconnected"
```

---

## 23. Voice Channel

**Files:** `app/integrations/voice.py`, `app/services/voice_agent.py`

```
Transcription:
  POST /integrations/voice/transcribe
  Body: multipart file upload (audio/wav, audio/mp3, etc.)
    ↓
  validate x-api-key → client
    ↓
  transcribe_audio(audio_bytes, mime_type)
    → if DEEPGRAM_API_KEY not set → return ""
    → DeepgramClient(DEEPGRAM_API_KEY).listen.asyncprerecorded.transcribe_file()
    → model="nova-2", smart_format=True
    ↓
  Return: { transcript: "..." }
    ↓
  Optionally: inject transcript into complaint pipeline (§1)

Synthesis:
  POST /integrations/voice/synthesize
  Body: { text, voice_id? }
    ↓
  synthesize_speech(text, voice_id)
    → if ELEVENLABS_API_KEY not set → return b""
    → ElevenLabs(api_key).text_to_speech.convert(voice_id, text, model="eleven_turbo_v2")
    ↓
  Return: MP3 bytes (Content-Type: audio/mpeg)

Status:
  GET /integrations/voice/status → { transcription: bool, synthesis: bool }
```

---

## 24. Security Architecture Flow

```
Every request passes through middleware stack (in order):

1. CORSMiddleware — origin whitelist check
2. SessionMiddleware — loads/stores Starlette session cookie
3. RLSContextMiddleware — reads JWT/session → sets ContextVar(current_client_id)
4. FeatureGateMiddleware — if route has plan gate → 403 if plan doesn't include feature
5. SecurityHeadersMiddleware — appends OWASP headers; rejects body > 2 MB
6. DatabaseRateLimitMiddleware — per-client request count check (DB-backed)
7. RequestAuditMiddleware — writes AuditLog(path, method, ip, status, user_agent)
8. request_logging — assigns request_id UUID; logs latency_ms; records metrics
9. Route handler

Multi-tenant isolation:
  Every DB query in services: .filter(Model.client_id == current_client_id)
  ENABLE_RLS=true: set_config('app.current_client_id', ...) in Postgres session → RLS policies enforce row filtering at DB level
```

---

## 25. Manual AI Reply Generation ("Generate AI Reply" Button)

**Files:** `app/api/v1/complaints.py`, `app/services/auto_reply_hardened.py`, `app/services/auto_reply_drafts.py`  
**Frontend:** `frontend/src/app/pages/ComplaintDetail.tsx`

```
User clicks "Generate AI Reply" button in complaint detail reply card:

Frontend:
  Button only shown when no AI draft exists (aiDraftExists = false)
  onClick → api.complaints.generateReply(complaint.id)
    → POST /api/v1/complaints/{id}/generate-reply

Backend:
  1. Authenticate user via JWT
  2. Scope complaint to user's client_id (404 if not found or wrong client)
  3. HardenedAutoReplyService(db).generate_and_queue_reply(
       complaint,
       force_human_review=True,   ← always queue for HITL, never auto-send
       commit=True
     )
  
  Inside generate_and_queue_reply (allow_disabled=True path):
    a. _is_eligible_for_generation(ticket, allow_disabled=True):
       → Skips spam check: proceeds even if complaint is spam
       → Skips auto_reply_disabled check: proceeds even if toggle is OFF
       → Skips legal/escalation check: proceeds even for escalated tickets
       → Only blocks: complaint already has a sent reply
    b. Gemini call → draft reply
    c. Hardening: hallucination + toxicity checks
    d. Confidence scoring
    e. force_human_review=True → always insert into AIReplyQueue (status=pending)
       regardless of confidence score; never auto-send
    f. complaint.ai_reply = draft, complaint.ai_reply_status = "pending"
    g. commit

  4. If queue_entry is None → 422 Unprocessable Entity
  5. db.refresh(complaint)
  6. Return _serialize_complaint_detail(db, complaint)
     → Includes ai_reply_status field (required for frontend to detect draft)

Frontend (on success):
  setComplaint(updated)
  setReplyText(updated.ai_reply || "")
  setEditing(false)
  toast.success("AI reply generated")
  → Reply card now shows "AI-Drafted Reply" heading + draft text in textarea
```

---

## 26. Auto AI Reply Toggle

**Files:** `app/api/settings.py`, `frontend/src/app/pages/Automations.tsx`

```
Toggle state stored in:
  client.custom_prompt_config["notification_preferences"]["auto_ai_reply"]
  → Default: true (preserves existing auto-generate behaviour)
  → Affects: app/queue/simple_queue.py at step 14 of complaint ingestion

Toggle UI (Settings → Automations → AI Settings card):
  1. On page mount:
     GET /api/settings
       → response.notification_preferences.auto_ai_reply
       → setAllPrefs({ ...defaults, ...response.notification_preferences })

  2. User toggles switch:
     PUT /api/settings/notifications
     Body: {
       sla_breach, new_escalation, daily_digest,
       ticket_assigned, ai_draft_expired,
       auto_ai_reply: <new value>   ← the changed field
     }
     → Backend: client.custom_prompt_config["notification_preferences"] = payload dict
     → commit
     → toast.success / toast.error

Effect on complaint pipeline:
  auto_ai_reply = True:
    → AI reply generated automatically on every new complaint
    → If confidence ≥ 0.90 → auto-sent (no human review)
    → If 0.60–0.85 → queued in HITL reply queue
  
  auto_ai_reply = False:
    → No AI reply generated on ingestion
    → Agent must click "Generate AI Reply" button in complaint detail
    → Manual generation always goes to HITL queue (never auto-sent)
```

---

## 27. Dark Mode Toggle

**Files:** `frontend/src/app/lib/theme-context.tsx`, `frontend/src/app/layouts/DashboardLayout.tsx`, `frontend/src/app/pages/LandingPage.tsx`

```
Initialization (on app load):
  ThemeProvider mounts:
    → Read localStorage.getItem("theme") → "light" | "dark" | null
    → Default: "light" if not set
    → Immediately apply: document.documentElement.classList.toggle("dark", theme === "dark")

Toggle (user clicks Moon/Sun button):
  toggleTheme():
    → setTheme(t => t === "light" ? "dark" : "light")
    → useEffect fires:
       document.documentElement.classList.toggle("dark", theme === "dark")
       localStorage.setItem("theme", theme)

CSS application:
  @custom-variant dark (&:is(.dark *))  ← in tailwind.css
  .dark { --background: ...; --card: ...; --foreground: ...; ... }  ← in theme.css
  
  shadcn/ui components: auto-respond to .dark via CSS variables (no class changes needed)
  Layout structural elements: explicit dark: Tailwind utility classes
    - Sidebar: dark:bg-gray-900 dark:border-gray-800
    - Header bar: dark:bg-gray-900 dark:border-gray-800
    - Page bg: dark:bg-gray-950
    - Nav items: dark:text-gray-300 dark:hover:bg-gray-800
    - Progress bar track: dark:bg-gray-700
  Auth pages: dark:bg-gray-950 on outer wrapper
  Landing page: dark:bg-gray-950, dark:bg-gray-900 on feature/pricing sections

Toggle locations:
  - DashboardLayout header (right of Bell notification icon): Moon → switches to dark; Sun → switches to light
  - LandingPage header (right of Log in / Sign up buttons)
  - Preference persists across all pages and browser sessions
```
