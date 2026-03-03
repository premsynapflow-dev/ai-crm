# AI Complaint Engine

FastAPI backend for a multi-tenant AI complaint intelligence system.

## Local Setup

1. Create and activate virtual environment.

```bash
python -m venv venv
source venv/bin/activate
```

Windows PowerShell:

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
```

2. Install dependencies.

```bash
pip install -r requirements.txt
```

3. Create `.env` in project root.

```env
DATABASE_URL=postgresql://postgres:YOUR_PASSWORD@db.YOUR_PROJECT_REF.supabase.co:5432/postgres
OPENAI_API_KEY=your_openai_api_key
SLACK_WEBHOOK_URL=your_slack_webhook_url
SECRET_KEY=your_secret_key
```

Notes:
- Use direct Supabase Postgres URL on port `5432`.
- SSL is enforced by SQLAlchemy `connect_args` in code.

4. Run API.

```bash
python -m uvicorn app.main:app
```

## Push to GitHub

```bash
git init
git add .
git commit -m "Initial commit"
git branch -M main
git remote add origin https://github.com/<your-user>/<your-repo>.git
git push -u origin main
```

## Deploy to Railway

1. Push this repo to GitHub.
2. In Railway, create a new project from the GitHub repo.
3. Set environment variables:
- `DATABASE_URL`
- `OPENAI_API_KEY`
- `SLACK_WEBHOOK_URL`
- `SECRET_KEY`
4. Start command:

```bash
python -m uvicorn app.main:app --host 0.0.0.0 --port $PORT
```

Alternatively use script:

```bash
bash start.sh
```

## Endpoint Example

### POST `/webhook/complaint`

Headers:

```http
x-api-key: <client_api_key>
Content-Type: application/json
```

Body:

```json
{
  "message": "I need a refund immediately."
}
```

Response:

```json
{
  "status": "processed",
  "action": "ESCALATE_HIGH"
}
```
