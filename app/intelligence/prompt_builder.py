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

    prompt = f"""Classify this customer message and return ONLY valid JSON, no markdown.

BUSINESS CONTEXT:
{industry_context}

TONE GUIDANCE:
{tone_instruction}

FOCUS AREAS:
Pay special attention to issues related to: {focus_text}

CLASSIFICATION RULES:
{rules_section}

Message: \"{message}\"

Rules for recommended_action:
- Use 'escalate' when: refund request, fraud claim, urgent complaint, legal threat, abuse, or sentiment is very negative (below -0.7)
- Use 'notify_sales' when: pricing inquiry, enterprise/bulk question, upgrade interest, or sales opportunity
- Use 'support_ticket' when: general help, order status, technical issue
- Use 'auto_reply' when: simple FAQ, easily resolved automatically
- Use 'product_feedback' when: feature request or product suggestion

Also include a short concise summary of the message.

Return exactly this structure:
{{
  "intent": "one of: complaint/refund_request/sales_lead/support/order_status/feature_request",
  "category": "one of: refund/billing/technical/abuse/general/sales",
  "sentiment": <float -1.0 to 1.0>,
  "urgency_score": <float 0.0 to 1.0>,
  "priority": <integer 1-5>,
  "recommended_action": "one of: escalate/notify_sales/support_ticket/auto_reply/product_feedback",
  "confidence": <float 0.0 to 1.0>,
  "summary": "short concise summary of the message"
}}"""

    return prompt


def _history_item_summary(item: Any) -> str:
    if isinstance(item, dict):
        return str(item.get("summary", "") or "").strip()
    if isinstance(item, str):
        return item.strip()
    return str(getattr(item, "summary", "") or "").strip()


def build_reply_prompt(complaint_summary: str, customer_history: list, config: Optional[Dict] = None) -> str:
    """Build reply generation prompt from template

    Args:
        complaint_summary: Complaint summary
        customer_history: List of past complaints
        config: Custom prompt config (or None for default)

    Returns:
        Formatted prompt for AI reply generation
    """
    config = config or DEFAULT_CONFIG

    # Extract config values
    tone = config.get("tone", "professional")
    reply_guidelines = config.get("reply_guidelines", {}) or {}
    industry = config.get("industry", "general")

    # Build prompt
    tone_instruction = TONE_STYLES.get(tone, TONE_STYLES["professional"])
    industry_context = INDUSTRY_CONTEXTS.get(industry, INDUSTRY_CONTEXTS["general"])

    # Max length guidance
    length_map = {
        "short": "2-3 sentences max",
        "medium": "2-3 paragraphs",
        "long": "detailed explanation with multiple paragraphs"
    }
    max_length = length_map.get(reply_guidelines.get("max_length", "medium"), length_map["medium"])

    # History context
    history_text = ""
    if customer_history:
        history_summaries = [_history_item_summary(item) for item in customer_history[-3:]]
        history_text = "Previous interactions:\n"
        for summary in history_summaries:
            if summary:
                history_text += f"- {summary}\n"

    # Signature
    signature = reply_guidelines.get("signature", "Best regards,\nSupport Team")

    # Policy links
    include_links = reply_guidelines.get("include_policy_links", False)
    link_instruction = "\n- Include relevant policy or help center links where appropriate" if include_links else ""

    prompt = f"""You are a helpful customer service agent. Generate a professional, empathetic reply.

BUSINESS CONTEXT:
{industry_context}

TONE GUIDANCE:
{tone_instruction}

LENGTH:
Keep the response {max_length}.

Customer message: {complaint_summary}

{history_text}

Requirements:
- Be empathetic and address the specific issue
- Provide actionable next steps if applicable{link_instruction}
- Do NOT make promises you can't keep
- End with: {signature}

Reply:"""

    return prompt


def build_thread_reply_prompt(
    complaint_summary: str,
    conversation_transcript: str,
    config: Optional[Dict] = None,
) -> str:
    """Build a reply prompt using only the current complaint thread."""
    config = config or DEFAULT_CONFIG

    tone = config.get("tone", "professional")
    reply_guidelines = config.get("reply_guidelines", {}) or {}
    industry = config.get("industry", "general")

    tone_instruction = TONE_STYLES.get(tone, TONE_STYLES["professional"])
    industry_context = INDUSTRY_CONTEXTS.get(industry, INDUSTRY_CONTEXTS["general"])

    length_map = {
        "short": "2-3 sentences max",
        "medium": "2-3 paragraphs",
        "long": "detailed explanation with multiple paragraphs",
    }
    max_length = length_map.get(reply_guidelines.get("max_length", "medium"), length_map["medium"])
    signature = reply_guidelines.get("signature", "Best regards,\nSupport Team")
    include_links = reply_guidelines.get("include_policy_links", False)
    link_instruction = "\n- Include relevant policy or help center links where appropriate" if include_links else ""

    prompt = f"""You are a helpful customer service agent. Generate a professional, empathetic reply.

BUSINESS CONTEXT:
{industry_context}

TONE GUIDANCE:
{tone_instruction}

LENGTH:
Keep the response {max_length}.

SOURCE OF TRUTH:
Use ONLY the conversation thread below.
Do NOT use information from any other ticket, customer conversation, or historical case.
If the thread does not contain enough information, ask a concise follow-up question instead of assuming facts.

Complaint summary: {complaint_summary}

Conversation transcript:
{conversation_transcript or complaint_summary}

Requirements:
- Address the latest customer message while staying consistent with the full thread
- Be empathetic and specific to this conversation
- Provide actionable next steps if applicable{link_instruction}
- Do NOT make promises you can't keep
- End with: {signature}

Reply:"""

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
