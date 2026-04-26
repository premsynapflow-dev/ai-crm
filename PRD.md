# Product Requirements Document (PRD): SynapFlow

## 1. Executive Summary
**SynapFlow** is an AI-powered complaint intelligence platform designed to transform raw customer feedback into structured, actionable insights. By leveraging Large Language Models (Gemini AI), SynapFlow automates the ingestion, classification, and routing of complaints while ensuring strict adherence to regulatory compliance frameworks (such as RBI mandates for FinTech).

---

## 2. Product Objectives
- **Automated Intelligence:** Reduce manual effort in categorizing and prioritizing customer complaints.
- **Regulatory Compliance:** Provide specialized tools for businesses (e.g., Banks, NBFCs) to track TAT (Turn Around Time) and meet RBI reporting requirements.
- **Faster Resolution:** Enable automated AI reply drafting with human-in-the-loop (HITL) validation to speed up response times.
- **Churn Mitigation:** Identify high-risk customers through sentiment analysis and proactive alerting.

---

## 3. Core Features

### 3.1. AI-Driven Ingestion & Analysis
- **Omnichannel Support:** Ingestion via API webhooks, Email (Gmail Integration), and WhatsApp.
- **Classification:** Automatic categorization of complaints into predefined business categories.
- **Sentiment Analysis:** 1-5 emotional intensity scoring to identify "furious" vs. "calm" tickets.
- **Urgency Scoring:** Dynamic priority assignment (Low, Medium, High, Critical) based on content analysis.

### 3.2. Complaint Management & Workflow
- **Assignment Engine:** Rule-based routing to specific teams or individual agents.
- **Capacity Management:** Tracking agent workloads to ensure balanced distribution.
- **Ticket Lifecycle:** Full state tracking from "New" to "Resolved," with transition audit logs.
- **SLA & Escalation:** Automated L1/L2/IO escalation paths based on time-on-page or breach of SLA.

### 3.3. RBI Compliance Framework (FinTech Specialized)
- **Regulatory Categorization:** Support for official RBI complaint category codes.
- **TAT Tracking:** Precise monitoring of resolution windows with automated breach warnings.
- **MIS Reporting:** Generation of monthly regulatory reports for banking compliance officers.

### 3.4. AI Auto-Replies (HITL)
- **Draft Generation:** AI suggests the best response based on historical successful resolutions.
- **Hallucination Protection:** Integrated checks for consistency and toxicity before a draft reaches an agent.
- **Review Dashboard:** Agents can approve, edit, or reject AI-generated drafts.

### 3.5. Customer 360 & Analytics
- **Unified Profile:** Aggregated history of all interactions for a single customer.
- **Churn Risk Scoring:** AI-driven prediction of users likely to churn based on complaint frequency and sentiment.
- **Operational Dashboard:** Live charts for volume trends, priority breakdowns, and customer satisfaction (CSAT) trends.

---

## 4. Technical Architecture

### 4.1. Stack
- **Backend:** Python (FastAPI) for high-performance async API interactions.
- **Frontend:** Next.js (Static Export) with Tailwind CSS for a premium, responsive dashboard experience.
- **Database:** PostgreSQL (via Supabase) utilizing JSONB for flexible configuration and audit logs.
- **AI Engine:** Google Gemini AI for classification and text generation.
- **Payments:** Razorpay integration for SaaS subscriptions and overage billing.

### 4.2. Background Processing
- **In-Process Worker:** A lightweight, SQL-backed background thread handles Email/Slack notifications and sync tasks without the overhead of Redis/Celery.
- **Audit Logging:** Every state change and AI interaction is captured for security and accountability.

---

## 5. Business Logic & Monetization

### 5.1. Subscription Tiers
- **Trial:** 7-day access with a 50-ticket limit.
- **Pro:** Tiered pricing (e.g., ₹4,999/mo) with 1,000 tickets and standard AI features.
- **Business/Max:** Higher ticket volumes, specialized compliance reporting, and advanced churn prediction.

### 5.2. Overage Management
- Paid plans support "soft limits" where processing continues, and clients are billed per additional ticket processed beyond their monthly quota.

---

## 6. Development Roadmap (Features Pending)

### 6.1. Short Term (Scalability & Polish)
- [ ] **Infrastructure Upgrade:** Move search/cache to Redis and background jobs to a dedicated worker process.
- [ ] **Alembic Migrations:** Implement standard database version control.
- [ ] **Deep Integrations:** Native connectors for Salesforce, Zendesk, and Intercom.

### 6.2. Medium Term (Advanced AI)
- [ ] **Voice Intelligence:** Transcription and analysis of customer support calls.
- [ ] **Custom Model Fine-tuning:** Allow clients to train the AI on their specific historical resolution data.
- [ ] **Real-time Chat:** Integrated live-chat widget with AI-agent handoff.

### 6.3. Long Term (Ecosystem)
- [ ] **Mobile Agent App:** Dedicated iOS/Android app for support managers on the move.
- [ ] **White-Labeling:** Custom domains and full branding suite for enterprise partners.
