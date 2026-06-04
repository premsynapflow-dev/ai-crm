"""
Build custom AI prompts from client templates
"""

from typing import Any, Dict, Optional


# Default prompt configuration
DEFAULT_CONFIG = {
    "tone": "professional",
    "focus_areas": ["general support", "billing", "technical issues"],
    "classification_rules": {
        "prioritize_refunds": False,
        "auto_escalate_legal": True,
    },
    "escalation_rules": [],
    "reply_guidelines": {
        "max_length": "medium",
        "include_policy_links": False,
        "signature": "Best regards,\nSupport Team"
    },
    "industry": "general"
}


TONE_STYLES = {
    "professional": "Be professional and formal. Use proper grammar and avoid casual language.",
    "friendly": "Be warm and friendly. Use a conversational tone while remaining respectful.",
    "empathetic": "Show deep empathy and understanding. Acknowledge customer frustration.",
    "formal": "Maintain strict formality. Use formal language and proper titles.",
}


INDUSTRY_CONTEXTS = {
    "ecommerce": "This is an e-commerce business. Common issues: shipping delays, refunds, product quality.",
    "saas": "This is a SaaS company. Common issues: bugs, feature requests, billing, integrations.",
    "healthcare": "This is a healthcare provider. Use HIPAA-compliant language. Be very empathetic.",
    "finance": "This is a financial services company. Use precise, compliant language. Avoid speculation.",
    "education": "This is an educational institution. Be supportive and patient.",
    "general": "General business context."
}


def build_classification_prompt(message: str, config: Optional[Dict] = None) -> str:
    """Build classification prompt from template

    Args:
        message: Customer complaint message
        config: Custom prompt config (or None for default)

    Returns:
        Formatted prompt for AI classification
    """
    config = config or DEFAULT_CONFIG

    # Extract config values
    tone = config.get("tone", "professional")
    focus_areas = config.get("focus_areas", ["general support"]) or ["general support"]
    classification_rules = config.get("classification_rules", {}) or {}
    escalation_rules = config.get("escalation_rules", []) or []
    industry = config.get("industry", "general")

    # Build prompt
    tone_instruction = TONE_STYLES.get(tone, TONE_STYLES["professional"])
    industry_context = INDUSTRY_CONTEXTS.get(industry, INDUSTRY_CONTEXTS["general"])

    # Focus areas guidance
    focus_text = ", ".join(focus_areas)

    # Classification rules
    rules_text = []
    if classification_rules.get("prioritize_refunds"):
        rules_text.append("- ALWAYS classify refund requests with high urgency and priority 5")
    if classification_rules.get("auto_escalate_legal"):
        rules_text.append("- ALWAYS use 'escalate' action for legal threats or compliance issues")
    if classification_rules.get("prioritize_bugs"):
        rules_text.append("- Technical bugs should be classified as high priority")

    rules_section = "\n".join(rules_text) if rules_text else "- Follow standard classification rules"
    escalation_text = []
    for rule in escalation_rules[:10]:
        rule_name = str(rule.get("name") or "Unnamed rule").strip()
        trigger_condition = str(rule.get("trigger_condition") or "custom").strip()
        category_code = str(rule.get("category_code") or "").strip()
        escalation_level = rule.get("escalation_level")
        trigger_after_hours = rule.get("trigger_after_hours")
        escalate_to = str(rule.get("escalate_to") or "configured escalation owner").strip()

        parts = [f"{rule_name}: trigger={trigger_condition}"]
        if category_code:
            parts.append(f"category={category_code}")
        if escalation_level is not None:
            parts.append(f"level={escalation_level}")
        if trigger_after_hours is not None:
            parts.append(f"after_hours={trigger_after_hours}")
        parts.append(f"target={escalate_to}")
        escalation_text.append(f"- {', '.join(parts)}")

    escalation_section = (
        "\n".join(escalation_text)
        if escalation_text
        else "- No client-specific escalation rules configured."
    )

    prompt = f"""Classify this customer message and return ONLY valid JSON, no markdown.

BUSINESS CONTEXT:
{industry_context}

TONE GUIDANCE:
{tone_instruction}

FOCUS AREAS:
Pay special attention to issues related to: {focus_text}

CLASSIFICATION RULES:
{rules_section}

CLIENT ESCALATION RULES:
{escalation_section}

Message: \"{message}\"

CATEGORY DEFINITIONS — always pick the most specific match; fall back to 'general' only when none apply:
- refund: Customer wants money back, reimbursement, chargeback, or return of payment — applies regardless of tone ("Refund now", "Please refund me", "I'd like to request a refund" are all refund)
- billing: Payment or invoice problem that is NOT a refund ask — overcharge, wrong charge, payment failed, invoice error, subscription fee dispute
- technical: Product or software not functioning — broken item, app crash, login failure, bug, error message, service outage, defective goods
- sales: Purchase intent or commercial inquiry — pricing questions, plan comparison, demo request, discount inquiry, upgrade/downgrade interest
- abuse: Message contains threats, legal threats ("I'll sue"), harassment, hate speech, or offensive language toward staff
- spam: Unsolicited outreach, phishing, marketing email complaint, opt-out/unsubscribe request, "I never signed up for this"
- general: Does not clearly fit any of the above — ambiguous feedback, general questions, compliments

INTENT DEFINITIONS — pick the most accurate one:
- refund_request: Any message asking for money back, regardless of phrasing or politeness
- complaint: Dissatisfaction expressed without an explicit refund ask (delivery delay, poor service, damaged product complaint)
- support: Customer needs help with a technical or account issue
- order_status: Customer asking where their order is or for shipping/delivery updates
- feature_request: Customer suggesting a new feature or product improvement
- sales_lead: Customer expressing purchase interest or asking commercial questions

Tiebreaker rules:
- If the message contains "refund" anywhere → category=refund, intent=refund_request
- If the message asks for pricing, a quote, or "how much" → category=sales, intent=sales_lead
- If the message describes something broken, crashing, or not working → category=technical, intent=support
- If the message mentions being overcharged or an invoice error (without asking for a refund) → category=billing

Rules for recommended_action:
- Use 'escalate' when: refund request, fraud claim, urgent complaint, legal threat, abuse, or sentiment is very negative (below -0.7)
- If a configured client escalation rule clearly applies based on the message, use 'escalate'
- Use 'notify_sales' when: pricing inquiry, enterprise/bulk question, upgrade interest, or sales opportunity
- Use 'support_ticket' when: general help, order status, technical issue
- Use 'auto_reply' when: simple FAQ, easily resolved automatically
- Use 'product_feedback' when: feature request or product suggestion

Also include a short concise summary of the message.

Return exactly this structure:
{{
  "intent": "one of: complaint/refund_request/sales_lead/support/order_status/feature_request",
  "category": "one of: refund/billing/technical/abuse/general/sales/spam",
  "sentiment": <float -1.0 to 1.0>,
  "urgency_score": <float 0.0 to 1.0>,
  "priority": <integer 1-5>,
  "recommended_action": "one of: escalate/notify_sales/support_ticket/auto_reply/product_feedback",
  "confidence": <float 0.0 to 1.0>,
  "summary": "short concise summary of the message",
  "emotion_dimensions": {{
    "frustration": <float 0.0 to 1.0>,
    "urgency": <float 0.0 to 1.0>,
    "confusion": <float 0.0 to 1.0>,
    "satisfaction": <float 0.0 to 1.0>,
    "aggression": <float 0.0 to 1.0>,
    "loyalty": <float 0.0 to 1.0>
  }}
}}"""

    return prompt


def _parse_reply_guidelines(config: Dict) -> tuple[str, str, bool]:
    """
    Return (custom_instructions, signature, include_policy_links) from config.

    The settings API stores reply_guidelines as a free-text string written by
    the client.  Legacy internal configs store it as a dict.  Both forms are
    handled here so custom instructions are never silently dropped.
    """
    raw = config.get("reply_guidelines", {}) or {}
    if isinstance(raw, str):
        return raw.strip(), "Best regards,\nSupport Team", False
    return (
        str(raw.get("custom_instructions", "") or "").strip(),
        str(raw.get("signature", "") or "Best regards,\nSupport Team"),
        bool(raw.get("include_policy_links", False)),
    )


def _history_item_summary(item: Any) -> str:
    if isinstance(item, dict):
        return str(item.get("summary", "") or "").strip()
    if isinstance(item, str):
        return item.strip()
    return str(getattr(item, "summary", "") or "").strip()


_EVIDENCE_KEYWORDS = frozenset([
    "broken", "damaged", "defective", "cracked", "dented", "scratched",
    "wrong item", "wrong product", "not as described", "poor quality",
    "bad packaging", "terrible package", "arrived late", "delayed", "never arrived",
    "not delivered", "missing item", "tampered",
])


def _evidence_instruction(summary: str, category: str) -> str:
    text = (summary + " " + category).lower()
    needs_evidence = any(kw in text for kw in _EVIDENCE_KEYWORDS)
    if needs_evidence:
        return (
            "This complaint involves a physical product or delivery condition claim. "
            "Ask the customer to share a photo or short video of the product/packaging as part of the resolution process. "
            "Frame it as a standard required step, not as distrust."
        )
    return "Provide clear next steps for resolving the issue."


def build_reply_prompt(
    complaint_summary: str,
    customer_history: list,
    config: Optional[Dict] = None,
    *,
    category: str = "",
    intent: str = "",
    customer_name: str = "",
    urgency_score: float = 0.0,
    sentiment_label: str = "neutral",
) -> str:
    config = config or DEFAULT_CONFIG

    tone = config.get("tone", "professional")
    reply_guidelines = config.get("reply_guidelines", {}) or {}
    industry = config.get("industry", "general")

    industry_context = INDUSTRY_CONTEXTS.get(industry, INDUSTRY_CONTEXTS["general"])
    custom_instructions, signature, include_links = _parse_reply_guidelines(config)
    link_instruction = "\n- Include relevant policy or help center links where appropriate" if include_links else ""

    history_text = ""
    if customer_history:
        history_summaries = [_history_item_summary(item) for item in customer_history[-3:]]
        lines = [s for s in history_summaries if s]
        if lines:
            history_text = "CUSTOMER HISTORY:\n" + "\n".join(f"- {s}" for s in lines) + "\n"

    greeting = f"Hi {customer_name.strip()}," if customer_name and customer_name.strip() else "Hi,"
    evidence_note = _evidence_instruction(complaint_summary, category)
    brand_section = f"\nBRAND VOICE & CUSTOM INSTRUCTIONS (highest priority — follow these above all else):\n{custom_instructions}\n" if custom_instructions else ""

    prompt = f"""You are a senior customer support agent at a professional brand. Write a concise, helpful reply to this customer complaint.

BUSINESS CONTEXT:
{industry_context}

TICKET CONTEXT:
- Category: {category or "general"}
- Intent: {intent or "complaint"}
- Sentiment: {sentiment_label}
- Urgency: {urgency_score:.2f}

CUSTOMER MESSAGE:
{complaint_summary}

{history_text}{brand_section}
STRICT RULES:
1. Start the email body with: {greeting}
2. DO NOT copy, paraphrase, or quote back any part of the customer's message — they know what they wrote.
3. Address every distinct issue mentioned (e.g. damaged item AND late delivery are two separate problems — name both).
4. Call the issue by what it actually is, never by a generic label like "your complaint" or "your refund issue".
5. {evidence_note}
6. Lead with one sentence of genuine acknowledgement, then immediately state the next concrete action.
7. Avoid corporate filler: "Thank you for reaching out", "We apologize for any inconvenience", "We value your business" are banned.
8. Do NOT promise outcomes (refund approved, replacement dispatched) — commit only to investigation or asking for evidence.
9. Keep to 2–3 short paragraphs.{link_instruction}
10. End with: {signature}

Reply:"""

    return prompt


def build_thread_reply_prompt(
    complaint_summary: str,
    conversation_transcript: str,
    config: Optional[Dict] = None,
    *,
    category: str = "",
    intent: str = "",
    customer_name: str = "",
    knowledge_lines: Optional[list] = None,
) -> str:
    """Build a reply prompt using only the current complaint thread."""
    config = config or DEFAULT_CONFIG

    industry = config.get("industry", "general")
    industry_context = INDUSTRY_CONTEXTS.get(industry, INDUSTRY_CONTEXTS["general"])
    custom_instructions, signature, include_links = _parse_reply_guidelines(config)
    link_instruction = "\n- Include relevant policy or help center links where appropriate" if include_links else ""

    greeting = f"Hi {customer_name.strip()}," if customer_name and customer_name.strip() else "Hi,"
    evidence_note = _evidence_instruction(complaint_summary, category)
    brand_section = f"\nBRAND VOICE & CUSTOM INSTRUCTIONS (highest priority — follow these above all else):\n{custom_instructions}\n" if custom_instructions else ""

    kb_lines = knowledge_lines or []
    kb_section = ""
    if kb_lines:
        kb_section = "\nAPPROVED KNOWLEDGE BASE (use these facts when directly relevant — do not contradict them):\n" + "\n".join(kb_lines) + "\n"

    prompt = f"""You are a senior customer support agent. Write a reply to the latest customer message in this thread.

BUSINESS CONTEXT:
{industry_context}

TICKET CONTEXT:
- Category: {category or "general"}
- Intent: {intent or "complaint"}

SOURCE OF TRUTH:
Use ONLY the conversation thread below. Do NOT invent facts not present in the thread.
If the thread lacks enough information to resolve the issue, ask a focused follow-up question.

Complaint summary: {complaint_summary}

Conversation transcript:
{conversation_transcript or complaint_summary}
{kb_section}{brand_section}
STRICT RULES:
1. Start the email body with: {greeting}
2. DO NOT copy, paraphrase, or quote back any part of the customer's messages.
3. Address every distinct issue mentioned — name each one specifically.
4. {evidence_note}
5. Avoid filler phrases: "Thank you for reaching out", "We apologize for any inconvenience" are banned.
6. Be concrete about what happens next and when.
7. Do NOT promise resolved outcomes — only commit to investigation or next steps.{link_instruction}
8. End with: {signature}

Reply:"""

    return prompt


def build_auto_reply_generation_prompt(context: Dict[str, Any], config: Optional[Dict] = None) -> str:
    """Build a structured prompt for approval-gated auto-reply drafts."""
    config = config or DEFAULT_CONFIG

    tone = config.get("tone", "professional")
    industry = config.get("industry", "general")

    tone_instruction = TONE_STYLES.get(tone, TONE_STYLES["professional"])
    industry_context = INDUSTRY_CONTEXTS.get(industry, INDUSTRY_CONTEXTS["general"])
    custom_instructions, signature, _ = _parse_reply_guidelines(config)

    history_lines = context.get("customer_history") or ["- No prior customer history available."]
    message_lines = context.get("recent_messages") or ["- No previous conversation available."]
    raw_knowledge = context.get("relevant_knowledge") or []
    knowledge_lines = raw_knowledge if raw_knowledge else ["- No approved knowledge base entries matched this ticket."]

    category = context.get("category") or "general"
    summary = context.get("summary") or "No complaint summary provided"
    customer_name = context.get("customer_name") or ""
    greeting = f"Hi {customer_name.strip()}," if customer_name and customer_name.strip() else "Hi,"
    evidence_note = _evidence_instruction(summary, category)
    brand_section = (
        f"\nBRAND VOICE & CUSTOM INSTRUCTIONS (highest priority — follow these above all else):\n{custom_instructions}\n"
        if custom_instructions else ""
    )

    prompt = f"""You are a senior customer support agent at a professional brand drafting a reply that will be reviewed by a human before sending.

BUSINESS CONTEXT:
{industry_context}

TONE GUIDANCE:
{tone_instruction}

TICKET CONTEXT:
- Ticket: {context.get("ticket_number") or "Not assigned"}
- Category: {category}
- Sentiment: {context.get("sentiment_label") or "neutral"} ({context.get("sentiment_score")})
- Priority: {context.get("priority") or "unknown"}
- Channel: {context.get("source") or "unknown"}
- Summary: {summary}

CUSTOMER CONTEXT:
- Name: {customer_name or "Customer"}
- Company: {context.get("company_name") or "Unknown"}
- Total tickets: {context.get("total_tickets") if context.get("total_tickets") is not None else "Unknown"}
- Avg satisfaction: {context.get("avg_satisfaction_score") if context.get("avg_satisfaction_score") is not None else "Unknown"}
- Churn risk: {context.get("churn_risk_score") if context.get("churn_risk_score") is not None else "Unknown"}

CUSTOMER HISTORY:
{chr(10).join(history_lines)}

APPROVED KNOWLEDGE BASE (use these facts when directly relevant — do not contradict them):
{chr(10).join(knowledge_lines)}

PREVIOUS CONVERSATION:
{chr(10).join(message_lines)}
{brand_section}
STRICT WRITING RULES:
1. Start the email body with: {greeting}
2. DO NOT copy, paraphrase, or quote back any part of the customer's messages — they already know what they wrote.
3. Address every distinct issue mentioned in the complaint separately and by name (e.g. "your item arrived damaged" and "your delivery was delayed" — not "your complaint" or "your refund issue").
4. {evidence_note}
5. Lead with one sentence of genuine acknowledgement, then immediately move to concrete next steps.
6. BANNED phrases — do not use any of these: "Thank you for reaching out", "We apologize for any inconvenience", "We value your business", "We understand your frustration", "We are sorry to hear".
7. Do NOT promise outcomes (refund approved, replacement dispatched) unless the APPROVED KNOWLEDGE BASE or PREVIOUS CONVERSATION explicitly confirms eligibility.
8. If context is incomplete, describe what the team will investigate and give a specific timeframe.
9. Keep the body to 2–3 short paragraphs. No bullet points in the email body.
10. End the body with this signature exactly:
{signature}

Return ONLY valid JSON:
{{
  "subject": "Email subject line (concise, reflects the actual issue)",
  "body": "Email body",
  "confidence_score": 0.0
}}"""

    return prompt


def get_prompt_config_for_client(client) -> Optional[Dict]:
    """Get prompt config for a client

    Args:
        client: Client model instance

    Returns:
        Prompt config dict or None if not customized
    """
    if not getattr(client, "custom_prompt_enabled", False):
        return None

    return getattr(client, "custom_prompt_config", None)
