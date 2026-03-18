# Custom AI Prompts - Admin Guide

## Overview

You can customize AI behavior per client using template-based prompts.

## Admin API Endpoints

**Base URL:** `/api/admin/prompts`

**Authentication:** Add header `X-Admin-Password: <your_admin_password>`

---

### 1. View Client's Current Prompt

```bash
GET /api/admin/prompts/{client_id}
X-Admin-Password: your_admin_password
```

**Response:**
```json
{
  "client_id": "...",
  "client_name": "Acme Corp",
  "custom_prompt_enabled": true,
  "custom_prompt_config": { ... },
  "updated_at": "2026-03-18T10:30:00Z"
}
```

---

### 2. Set Custom Prompt

```bash
PUT /api/admin/prompts/{client_id}
X-Admin-Password: your_admin_password
Content-Type: application/json

{
  "tone": "friendly",
  "focus_areas": ["shipping", "refunds", "product quality"],
  "classification_rules": {
    "prioritize_refunds": true,
    "auto_escalate_legal": true
  },
  "reply_guidelines": {
    "max_length": "medium",
    "include_policy_links": true,
    "signature": "Happy to help!\nThe Acme Team"
  },
  "industry": "ecommerce"
}
```

**Response:**
```json
{
  "status": "updated",
  "client_id": "...",
  "client_name": "Acme Corp",
  "config": { ... }
}
```

---

### 3. Remove Custom Prompt

```bash
DELETE /api/admin/prompts/{client_id}
X-Admin-Password: your_admin_password
```

Reverts client to default prompt.

---

### 4. List All Customized Clients

```bash
GET /api/admin/prompts
X-Admin-Password: your_admin_password
```

**Response:**
```json
{
  "count": 3,
  "clients": [
    {
      "client_id": "...",
      "name": "Acme Corp",
      "industry": "ecommerce",
      "updated_at": "2026-03-18T10:30:00Z"
    }
  ]
}
```

---

## Configuration Options

### Tone
- `professional` - Formal and professional
- `friendly` - Warm and conversational
- `empathetic` - Understanding and compassionate
- `formal` - Strictly formal language

### Industry
- `ecommerce` - Online retail
- `saas` - Software as a service
- `healthcare` - Medical/health services
- `finance` - Financial services
- `education` - Educational institutions
- `general` - Generic business

### Focus Areas
Array of strings (1-10 items):
```json
["shipping", "refunds", "billing", "technical support", "product quality"]
```

### Classification Rules
```json
{
  "prioritize_refunds": true,     // Always high priority for refunds
  "auto_escalate_legal": true,    // Auto-escalate legal threats
  "prioritize_bugs": true         // High priority for technical bugs
}
```

### Reply Guidelines
```json
{
  "max_length": "short|medium|long",
  "include_policy_links": true,
  "signature": "Custom signature text"
}
```

---

## Example Configurations

### E-Commerce Store
```json
{
  "tone": "friendly",
  "focus_areas": ["shipping", "returns", "product quality", "order tracking"],
  "classification_rules": {
    "prioritize_refunds": true,
    "auto_escalate_legal": false
  },
  "reply_guidelines": {
    "max_length": "medium",
    "include_policy_links": true,
    "signature": "Happy shopping!\nThe [StoreName] Team"
  },
  "industry": "ecommerce"
}
```

### SaaS Company
```json
{
  "tone": "professional",
  "focus_areas": ["bugs", "feature requests", "integrations", "API", "billing"],
  "classification_rules": {
    "prioritize_bugs": true,
    "auto_escalate_legal": true
  },
  "reply_guidelines": {
    "max_length": "medium",
    "include_policy_links": true,
    "signature": "Best regards,\nThe [CompanyName] Support Team"
  },
  "industry": "saas"
}
```

### Healthcare Provider
```json
{
  "tone": "empathetic",
  "focus_areas": ["appointments", "billing", "insurance", "medical records"],
  "classification_rules": {
    "auto_escalate_legal": true
  },
  "reply_guidelines": {
    "max_length": "long",
    "include_policy_links": false,
    "signature": "With care,\n[ProviderName] Patient Services"
  },
  "industry": "healthcare"
}
```

---

## Workflow

1. **Client requests customization** → Contact you via support
2. **You create config** → Use admin API to set custom prompt
3. **Test** → Client sends test complaints, you verify results
4. **Iterate** → Adjust config based on feedback
5. **Done** → Custom prompts automatically apply to all new complaints

---

## Testing

**Test a custom prompt:**

```bash
# 1. Set custom prompt for client
curl -X PUT https://your-app.com/api/admin/prompts/{client_id} \
  -H "X-Admin-Password: your_password" \
  -H "Content-Type: application/json" \
  -d '{
    "tone": "friendly",
    "focus_areas": ["shipping"],
    "industry": "ecommerce",
    "classification_rules": {},
    "reply_guidelines": {"max_length": "short"}
  }'

# 2. Send test complaint as that client
curl -X POST https://your-app.com/webhook/complaint \
  -H "x-api-key: client_api_key" \
  -H "Content-Type: application/json" \
  -d '{
    "message": "Where is my order?",
    "source": "api"
  }'

# 3. Check the AI-generated reply in the portal
# Should reflect the custom tone and focus
```

---

## Future: Admin API Key (Phase 2)

Coming soon: Replace `X-Admin-Password` header with:
- Admin API keys (multiple admins)
- Role-based access (super admin, support admin)
- Audit logs for prompt changes
