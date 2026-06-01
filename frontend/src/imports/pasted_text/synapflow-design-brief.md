
SynapFlow — UI/UX Design Brief
What this is
You are designing the complete UI/UX for SynapFlow — an AI-powered complaint intelligence platform for Indian fintechs, NBFCs, D2C brands, and e-commerce businesses. The product is a B2B SaaS tool used by support managers, support agents, compliance officers, and business owners to handle customer complaints at scale with AI assistance.

The backend is fully built. Every feature described below has working API endpoints. Your job is to design the interface that sits on top of it. You have complete creative freedom over visual design, layout, navigation structure, component patterns, typography, color, motion, and interaction model. The only constraints are functional: each screen must expose the data and actions listed.

Users and what they care about
Support Manager — Wants to know: Is my team keeping up? Are SLAs being breached? Which issues are escalating? Main view is the dashboard and assignments page.

Support Agent — Wants to know: What tickets are assigned to me? What should I reply? Can I approve this AI draft quickly? Main view is the complaints inbox and reply queue.

Compliance Officer — Wants to know: Are any RBI complaints approaching TAT breach? Has the monthly MIS report been generated? Main view is the compliance page.

Business Owner — Wants to know: Is CSAT trending up or down? Which complaint categories keep recurring? Are we at risk of losing any customers? Main view is analytics.

Tech lead integrating via API — Wants to know: API key, webhook URL, how to connect Gmail/WhatsApp. Main view is settings/connections.

Screens — what each one does
Every screen listed below must exist. Design them however you want.

1. Landing / Marketing Page (/)
Purpose: Convert visitors to signups.

Must convey:

What SynapFlow does: ingests complaints from multiple channels (API, email, WhatsApp, chat widget), classifies them with AI, routes to the right team, generates draft replies, and tracks SLA + RBI compliance.
Who it's for: Indian fintechs, NBFCs, D2C brands.
Pricing tiers (see §Billing section below).
Actions: Sign up, Log in.

2. Signup (/signup)
Fields to collect:

Name
Email
Password
Business type (dropdown: Fintech, NBFC, Bank, D2C Brand, E-commerce, Other) — this determines whether RBI compliance is auto-enabled
Post-signup: User lands on dashboard. Free plan auto-applied (50 tickets/month). No credit card required for Free/Starter trial.

3. Login (/login)
Fields: Email, password.

Also needed: "Forgot password" link → OTP flow (6-digit code sent to email, 10-minute TTL) → password reset form.

4. Dashboard (/dashboard)
Purpose: At-a-glance health of the complaint operation.

Data available to display:

Total tickets (all time / this month)
Open tickets right now
Resolved tickets this month
CSAT trend (avg satisfaction score, 1–5, over last 30 days)
Ticket volume over time (by day/week)
Priority breakdown: critical / high / medium / low counts
Category distribution: what complaint types are most common
AI reply queue size (pending drafts waiting for review)
SLA breach count (tickets where sla_status = "breached")
Quick links to: Inbox, Reply Queue, Assignments
Note: This is the first screen users see after login. Make it high-signal.

5. Complaints Inbox (/complaints)
Purpose: The core workspace. Where agents review and act on complaints.

Data per complaint:

Subject / summary (first meaningful line of the complaint)
Customer name and email
Source: api | email | gmail | whatsapp | chat
Status: new | in-progress | escalated | resolved
Full ticket state (10 states): new → assigned → in_progress → waiting_customer → waiting_internal → on_hold → escalated → resolved → closed → spam/invalid
Priority: critical | high | medium | low
Sentiment: positive | neutral | negative (+ numeric score 1–5 and 6 emotion dimensions: frustration, urgency, confusion, satisfaction, aggression, loyalty)
Category (AI-classified: e.g. "Billing", "Delivery", "Technical Support")
SLA deadline (sla_due_at) and SLA status: on_track | at_risk | breached
Assigned agent and team
Created at, resolved at
AI reply draft (if generated): text + confidence score (0–1)
AI reply status: pending | approved | sent | rejected | discarded
Escalation level: 0 (none), 1 (L1), 2 (L2), 3 (IO/Internal Ombudsman)
Conversation thread: all messages in the thread (inbound + outbound), each with timestamp, channel, direction
Filters available:

Status, priority, sentiment, category, source channel, SLA status, date range, assigned team/agent, search
Actions:

Open complaint detail
Change status (New → In Progress → Resolved; also mark as spam/invalid)
Manual reply (free-text) — delivered via the same channel it arrived on
Approve / reject AI reply draft from within the detail view
Reassign to another agent or team
Escalate manually (advances escalation level)
Bulk: assign, close, export
Complaint detail should show:

The full conversation thread (messages in chronological order, with direction indicators)
Sentiment badge + all 6 emotion dimension scores
AI reply draft with confidence score, hallucination check status, toxicity score
Edit-and-approve or reject the AI draft
SLA countdown (time remaining or time breached by)
Escalation status and history
Full state transition history (who changed what, when, why)
Linked customer profile card (churn risk, lifetime value, total tickets)
RBI reference number (if regulated)
6. AI Reply Queue (/reply-queue)
Purpose: Human-in-the-loop review of AI-generated draft replies that scored between 0.60 and 0.85 confidence (below 0.85 = auto-sent, below 0.60 = discarded).

Data per queued draft:

Complaint summary and customer info
The AI-generated reply text
Confidence score (0.60–0.85)
Hallucination check: passed/failed
Toxicity score (0–1, must be < 0.3 to reach this queue)
Time until expiry (expires 24h after creation — after that, no reply is sent)
Status: pending | approved | rejected | expired
Tabs: Pending / Approved / Rejected

Actions on each pending draft:

Approve — sends the reply as-is
Edit then approve — modify the text, then approve
Reject — reject with optional reason; complaint stays open for manual handling
Time pressure is real: Drafts expire in 24h. The UI should communicate this clearly.

7. Customer 360 (/customers)
Purpose: Understand each customer — not just individual complaints but the full relationship.

Customer list data:

Name, email
Total tickets (all time)
Open tickets right now
Sentiment label (positive / neutral / negative)
Churn risk badge: low | medium | high
Last interaction date
Health tags: VIP, Risky, Billing-watch, Renewal-ready
Filters: Risk level, status, search by name/email.

Customer profile page (/customers/[id]):

Identity: name, email, phone, company, customer type (individual / business)
Stats: total tickets, open tickets, avg satisfaction score, lifetime value, churn risk score (0–1) + recommendation text
Churn risk explanation (what drove the score)
Full complaint history (all tickets for this customer, sortable)
Interaction timeline: all events (ticket opened, reply sent, status changed, escalated)
Sentiment trend over time
Notes (agent-added free text)
8. Assignments (/assignments)
Purpose: Workload visibility and manual ticket redistribution.

Data:

All agents across all teams, with:
Active ticket count
Capacity (configured max)
Load % (active/capacity)
Role: agent / manager / supervisor
Per-agent: list of currently assigned open tickets
Actions:

Reassign a ticket from one agent to another (drag or dropdown)
Quick filters by team
9. Analytics (/analytics)
Plan gates: Some sections are locked on lower plans (see §Billing).

Always visible (all plans):

Ticket volume trend (area/line chart, last 30 days)
Priority breakdown (bar or donut)
Category distribution (which complaint types are most frequent)
Max plan and above:

Churn risk list: customers with high/medium churn risk, with scores and last interaction
Root cause summary: AI-generated analysis of the top complaint root causes over the last 30 days (available from GET /api/v1/root-cause/report)
Team performance table: per-agent stats (tickets resolved, avg response time, CSAT, SLA breach rate)
For locked sections: show a preview/blur with an upgrade prompt.

10. RBI Compliance (/compliance) — Scale/Enterprise plans only
Purpose: Track regulatory TAT deadlines, escalation levels, and generate MIS reports. Lower-plan users see an upgrade prompt.

Data:

List of all RBI-registered complaints with:
RBI reference number (e.g. LOAN:1717500000:a3b4c5d6)
RBI category code: ATM / CC / LOAN / DEP / NB / MOBILE / BRANCH / OTHER
TAT status: within_tat | approaching_breach | breached
Days remaining / days overdue
Escalation level: L0 → L1 (Regional Manager, 24h) → L2 (Ombudsman, 48h) → IO (Internal Ombudsman, 30 days)
Current escalated_to email
Summary bar: count within TAT / approaching / breached
Actions:

Filter by TAT status, category, escalation level
Manual escalate (advances to next level immediately)
Generate MIS report for a given month
View generated MIS reports (list with download link)
Report contains: total complaints, by-category breakdown, resolved within TAT, TAT breach count, avg resolution days, escalation statistics, satisfaction rate
11. Settings — Profile (/settings)
Name (editable)
Email (display only)
Password change: current password → new password, OR trigger OTP-based reset (code sent to email, 6 digits, 10-min TTL)
Company name (editable)
Business type (drives RBI eligibility — changing to fintech/NBFC/bank enables RBI mode)
12. Settings — API & Connections (/settings/connections)
Inbound channels to connect:

Channel	What's needed
REST API	Display API key + copy button. Show webhook endpoint URL.
Gmail	OAuth connect button → Google OAuth consent → connected email shown + disconnect.
WhatsApp	Connect via Meta Business API: app secret field + verify token field + webhook URL to configure in Meta dashboard.
Email forwarding	Display inbound forwarding address. Any email forwarded here becomes a ticket.
Live chat widget	Show embed <iframe> snippet with the API key pre-filled. Also: company name field for widget branding.
Instagram	Connect button (Max+ only).
Google Reviews	Connect button (Max+ only).
Voice / Call transcription	Connect button (keys required: DEEPGRAM_API_KEY + ELEVENLABS_API_KEY).
Each channel card: connected status, connected account/identifier, disconnect button, last synced timestamp.

13. Settings — Notifications (/settings/notifications)
Slack webhook URL (field + test button)
Email alert toggles: SLA breach, new escalation, daily digest
In-app notifications (bell icon in nav) — notification types: new ticket assigned, SLA breached, AI draft expired, escalation advanced
14. Settings — Webhooks (/settings/webhooks)
Outbound webhooks: configure a URL to receive POST events when tickets are created, resolved, or escalated.

Add / remove / test webhook endpoints
Event type selector (ticket.created, ticket.resolved, ticket.escalated, reply.sent)
15. Teams (/settings/teams)
List of teams (name, member count, routing categories)
Create team (name)
Add members: search users by email → assign role (agent / manager / supervisor) + capacity (max concurrent tickets)
Routing rules per team: which complaint categories route to this team
Remove member / change role / adjust capacity
16. Knowledge Base (/knowledge)
Backend fully built — GET/POST/PUT/DELETE /api/v1/knowledge/snippets — no frontend exists yet. This screen needs to be designed from scratch.

Purpose: Store pre-approved reply templates and resolution snippets. The AI uses these as few-shot examples when generating replies.

Data per snippet:

Title
Category (maps to complaint category)
Content (the reply template)
Usage count (how many times the AI has used it)
Created by / created at
Actions: Create, edit, delete snippets. Search by title or category.

17. Automation Rules (/settings/automations)
Backend fully built — rule engine + action executor — no frontend exists yet.

Purpose: Create "if this, then that" rules that fire automatically when a complaint matches conditions.

Rule structure:

Trigger: complaint.created | complaint.escalated | sla_status = breached | etc.
Conditions: category = "Billing", priority >= 3, sentiment = "negative", source = "whatsapp", etc. (AND/OR combinator)
Actions: assign_to_team, send_slack_alert, send_email, set_priority, escalate, add_tag
Actions: Create/edit/delete rules. Enable/disable toggle per rule. Last triggered timestamp.

18. Billing & Plans (/pricing / /billing)
Plans (with prices):

Plan	Price	Tickets/mo	Seats
Free	₹0	50	1
Starter	₹2,999/mo	500	3
Pro	₹4,999/mo	2,000	10
Max	₹9,999/mo	10,000	25
Scale	₹99,999/mo	1,00,000	100
Enterprise	Custom	Unlimited	Unlimited
Annual pricing = ~2 months free. Monthly / Annual toggle.

Upgrade flow: Click upgrade → Razorpay checkout → confirmation.

Current plan display: What plan they're on, ticket usage this month vs. quota, overage indicator with cost estimate, billing cycle dates, invoice history.

19. Admin Panel (/admin) — Internal only
Separate from the main app — only accessible with ADMIN_USERNAME / ADMIN_PASSWORD credentials.

Overview: total tenants, active tenants, total tickets across all tenants, active subscriptions
Tenant list: name, plan, ticket usage, signup date, last active
Per-tenant actions: override plan, view usage, reset API key
AI prompt override: per-tenant custom Gemini system prompt configuration
User journeys to optimise for
These are the flows that happen dozens of times per day. They must be as fast as possible — minimal clicks, minimal page loads.

1. Agent morning review:
Open inbox → sort by "new" → pick a ticket → read complaint → read AI draft → approve or edit → next ticket. This entire loop should take under 30 seconds per ticket.

2. Manager SLA check:
Open dashboard → see breach count → click through to filtered inbox showing breached tickets → reassign overloaded agents. Should take under 2 minutes.

3. Reply queue sweep:
Open reply queue → 8 pending drafts → read each, approve/edit/reject → queue is clear. 10 seconds per draft.

4. Compliance officer TAT check:
Open compliance page → filter by "approaching_breach" → review the list → manually escalate if needed → generate this month's MIS report.

5. New channel connection:
Settings → Connections → click Gmail → OAuth flow → return to confirmed connected state.

6. New team member:
Settings → Teams → select team → Add member → search by email → set role → done.

Data fields available globally
These are the fields that exist in the system and can be shown anywhere:

Complaint / Ticket:
id, ticket_id, ticket_number, summary, source, status, state, state_changed_at, priority (1–5), category, sentiment (float -1 to 1), sentiment_score (1–5), sentiment_label, sentiment_indicators (array of 6 emotion dimensions), urgency_score (0–1), confidence (AI classification confidence, 0–1), ai_reply, ai_reply_confidence, ai_reply_status, sla_due_at, sla_status, escalation_level, escalated_at, escalated_to, team_id, assigned_user_id, assigned_to, customer_email, customer_phone, created_at, resolved_at, resolution_status, response_time_seconds, rbi_category_code, tat_due_at, tat_status, thread_messages (full conversation)

Customer:
name, email, phone, company_name, customer_type, churn_risk (low/medium/high), churn_risk_score (0–1), lifetime_value, total_tickets, open_tickets, sentiment_label, avg_satisfaction_score, tags, last_interaction_at

Team / Agent:
name, role (agent/manager/supervisor), active_tasks, capacity, is_active

Screens that need to be built from scratch (no UI exists yet)
These features are fully implemented in the backend but have zero frontend pages:

Knowledge Base (/knowledge) — snippet CRUD
Automation Rules (/settings/automations) — visual rule builder
Notification Centre — bell icon + drawer showing recent events (new assignment, SLA breach, draft expired, escalation)
Voice / Call channel connection UI
Instagram / Google Reviews connection UI
Model Audit Log — visible in admin panel: per-ticket AI decision trail (what was sent to Gemini, what came back, confidence, which checks ran)
Screens that exist but show less than what's available
These are currently undershooting the data the backend provides:

Complaint inbox: currently shows simplified 3-state view (New/Open/Resolved). Full 10-state machine is available. SLA column is missing from the list. Escalation status is not shown in the detail modal. Sentiment shows only the label — not the score or the 6 emotion dimensions.
Customer profile: churn risk shows only a badge. The score (0–1), recommendation text, and lifetime value are available but not shown.
Analytics: team performance exists but has no drill-down per agent. Root cause report exists but only shows a summary.
Dashboard: queue health (background job status) is available via API but not shown.
Constraints
Frontend is Next.js 16 (React 19), static export, served by FastAPI.
All data comes from REST API endpoints under /api/v1/.
Auth is JWT (Bearer token) for the SPA.
Plan gating: some features are locked by plan. Show upgrade prompts for locked sections rather than hiding them entirely.
The app must work on desktop. Mobile is a bonus.
No third-party analytics SDK (privacy requirement).
What you have complete freedom over
Everything not listed as a functional constraint is yours to decide:

Visual language, color palette, typography
Navigation structure (sidebar, top nav, command palette, tabs — whatever fits)
Layout density (compact table-heavy vs. spacious card-heavy)
Dark mode, light mode, or both
Component patterns (how filters work, how modals vs. drawers vs. inline panels work)
Onboarding experience (first-time empty states for each screen)
Motion and transitions
Mobile responsiveness approach
How plan gates are communicated (blur, lock icon, modal, banner — your call)
How AI confidence is visualised (progress bar, number, color coding, badge — your call)
How the 6 emotion dimensions are displayed
What the SLA countdown looks like
How the conversation thread is rendered in the complaint detail
The product works like Freshdesk meets Stripe meets an AI layer — but it doesn't need to look like either of them. Make it yours.

That's the full brief. Output as many screens, flows, components, and states as you need. If anything is ambiguous, make the best design decision and note your assumption.