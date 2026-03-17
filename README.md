# AI Complaint Engine

Neuronyx is a multi-tenant FastAPI SaaS for complaint intelligence, customer support automation, and lightweight billing on a solo-founder budget.

## What This Repo Now Includes

- Multi-channel complaint ingestion:
  - `POST /webhook/complaint`
  - `POST /webhook/email`
  - `POST /webhook/whatsapp`
  - embedded widget from `public/widget.js`
- Gemini classification and summarization
- Ticketing with `ticket_id` and `thread_id`
- Client-specific Slack alerts with global fallback
- Automation rules and execution engine
- Client portal with:
  - inbox
  - complaint dashboard
  - ticket thread view
  - leads CRM view
  - analytics
  - billing and usage screens
  - Slack settings
- Trial, plan, usage, overage, invoice, and subscription foundations
- Background job queue running inside the API process
- Health and metrics endpoints
- Versioned API routes under `/api/v1`

## Stack

- FastAPI
- PostgreSQL / Supabase
- Gemini 2.0 Flash
- SQLAlchemy sync engine
- Jinja templates
- Razorpay
- Railway or Render

## Local Setup

### 1. Create and activate a virtual environment

PowerShell:

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
```

### 2. Install dependencies

```powershell
pip install -r requirements.txt
```

### 3. Create `.env`

Start from `.env.example`:

```powershell
Copy-Item .env.example .env
```

Minimum variables you must set:

- `DATABASE_URL`
- `SECRET_KEY`
- `GEMINI_API_KEY`
- `ADMIN_PASSWORD`

Recommended for full product flow:

- `SLACK_WEBHOOK_URL`
- `RAZORPAY_KEY_ID`
- `RAZORPAY_KEY_SECRET`
- `RAZORPAY_WEBHOOK_SECRET`
- `SMTP_HOST`
- `SMTP_PORT`
- `SMTP_USER`
- `SMTP_PASSWORD`
- `SMTP_FROM`

Notes:

- Use the direct Supabase Postgres URL on port `5432`
- Do not append `?sslmode=require` to `DATABASE_URL`; the app passes SSL through SQLAlchemy `connect_args`
- `SECRET_KEY` must be at least 32 characters

### 4. Run migrations

Run the older migrations if you are upgrading an existing project, then run the consolidated migration:

```powershell
python migrate_add_slack_url.py
python migrate_add_summary.py
python migrate_add_event_logs.py
python migrate_replace_message_with_summary.py
python migrate_revenue_ready.py
```

If you are using ticketing and automation, also apply:

```powershell
# Run these in Supabase SQL editor or psql
# migrate_ticket_system.sql
# migrate_automation_rules.sql
# migrate_add_assigned_team.sql
```

### 5. Start the app

```powershell
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Or:

```bash
bash start.sh
```

The internal worker thread starts automatically on FastAPI startup.

## Core Endpoints

### Complaint Ingestion

```http
POST /webhook/complaint
x-api-key: <client_api_key>
Content-Type: application/json
```

```json
{
  "message": "I want a refund for the duplicate charge.",
  "source": "api",
  "customer_email": "customer@example.com",
  "customer_phone": "+919876543210"
}
```

### Email Webhook

```json
{
  "from": "customer@example.com",
  "subject": "Refund needed",
  "text": "I was billed twice this month"
}
```

### WhatsApp Webhook

```json
{
  "From": "+919876543210",
  "Body": "Where is my order?"
}
```

### Public Signup

```http
POST /api/signup
```

```json
{
  "company_name": "Acme Labs",
  "email": "founder@acme.com",
  "password": "strongpassword123"
}
```

### Billing

- `POST /billing/checkout`
- `POST /billing/webhook/razorpay`
- `GET /billing/usage`
- `POST /billing/upgrade`
- `POST /billing/cancel`

### Monitoring

- `GET /health`
- `GET /health/db`
- `GET /health/ai`
- `GET /metrics`

## Portal Routes

- `/portal`
- `/portal/inbox`
- `/portal/ticket/{ticket_id}`
- `/portal/leads`
- `/portal/analytics`
- `/portal/automation`
- `/portal/billing`
- `/portal/usage`
- `/portal/upgrade`
- `/portal/settings`

## Billing Model

Defined in `app/billing/plans.py`:

- `trial`: free, 50 tickets, 7-day trial
- `pro`: Rs 4,999/month, 1000 tickets, Rs 8 overage
- `business`: Rs 14,999/month, 5000 tickets, Rs 4 overage

Behavior:

- Trials stop processing after ticket limit or trial expiry
- Paid plans continue processing and accrue overage for billing

## Background Worker

The queue is deliberately simple:

- jobs are stored in PostgreSQL in `job_queue`
- worker runs in a background thread inside the API process
- supported job types:
  - `send_email`
  - `send_slack`
  - `sync_integration`

This keeps the system Redis-free and Celery-free for now.

## Tests

Run the included unit tests with:

```powershell
python -m unittest discover -s tests
```

Current test coverage focuses on:

- usage tracking
- trial expiry logic
- Razorpay signature verification
- rate limiting behavior

## Deployment

### Railway

- `railway.json` is included
- set start command to `bash start.sh` if needed
- set environment variables from `.env.example`

### Render

- `render.yaml` is included
- add the required env vars in the Render dashboard

## Backups

Linux/macOS:

```bash
bash scripts/backup_db.sh
```

Windows PowerShell:

```powershell
.\scripts\backup_db.ps1
```

Both use `pg_dump` and require `DATABASE_URL` to be set.

## Manual Tasks Checklist

### Accounts and external setup

1. Create a Supabase project and copy the direct Postgres connection string
2. Create a Gemini API key in Google AI Studio
3. Create a Slack app with Incoming Webhooks enabled
4. Create a Razorpay account and get:
   - Key ID
   - Key Secret
   - Webhook Secret
5. Set up an SMTP provider for outbound emails

### Database and deployment

1. Run the migration scripts against Supabase
2. Push the repo to GitHub
3. Deploy to Railway or Render
4. Add all environment variables from `.env.example`
5. Verify `/health`, `/health/db`, and `/health/ai`

### Product onboarding

1. Create an admin login
2. Create your first client from admin dashboard or `/api/signup`
3. Add client Slack webhook under `/portal/settings`
4. Test the widget and webhook endpoints
5. Add at least one automation rule in `/portal/automation`
6. Test Razorpay checkout and webhook handling in sandbox mode

## Important Solo-Developer Notes

- This codebase is optimized for simplicity and speed, not distributed scale
- There is no Redis and no Celery yet by design
- Queue processing, rate limiting, caching, and monitoring all use the database
- As volume grows, the next likely upgrades are:
  - dedicated worker process
  - Redis-backed throttling/cache
  - real JWT service
  - proper migration tooling with Alembic
  - background job isolation
