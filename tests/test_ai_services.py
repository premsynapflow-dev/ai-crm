import asyncio
import uuid

import app.intelligence.chatbot as chatbot_module
from app.db.models import Complaint, EscalationRule
from app.intelligence.classifier import classify_message_async, normalize_classification_output
from app.intelligence.prompt_builder import build_auto_reply_generation_prompt, build_classification_prompt, build_reply_prompt
from app.intelligence.reply_engine import generate_ai_reply_async
from app.services.classification_service import build_client_classification_config


def test_classifier_returns_valid_structure():
    """Test that classifier returns expected structure"""
    result = asyncio.run(classify_message_async("I want a refund"))
    
    assert "intent" in result
    assert "category" in result
    assert "sentiment" in result
    assert "urgency_score" in result
    assert "priority" in result
    assert "recommended_action" in result
    assert "confidence" in result
    assert "summary" in result


def test_classifier_handles_empty_message():
    """Test classifier with empty message"""
    result = asyncio.run(classify_message_async(""))
    
    # Should return fallback
    assert result["confidence"] == 0.0
    assert result["intent"] == "complaint"


def test_classifier_sentiment_bounds():
    """Test that sentiment is bounded -1 to 1"""
    result = asyncio.run(classify_message_async("I absolutely love this!"))
    assert -1.0 <= result["sentiment"] <= 1.0


def test_reply_engine_generates_text():
    """Test reply engine generates text"""
    complaint = Complaint(
        id=uuid.uuid4(),
        ticket_id="TKT-AI-001",
        thread_id="TH-AI-001",
        summary="Need refund",
        category="refund",
        sentiment=-0.5,
        confidence=0.8
    )
    
    result = asyncio.run(generate_ai_reply_async(complaint, []))
    
    assert "reply_text" in result
    assert "confidence_score" in result
    assert len(result["reply_text"]) > 0


def test_reply_prompt_accepts_string_customer_history():
    prompt = build_reply_prompt(
        "Customer reports a login failure",
        ["Previous refund issue", {"summary": "Earlier integration delay"}],
    )

    assert "Previous refund issue" in prompt
    assert "Earlier integration delay" in prompt


def test_auto_reply_prompt_includes_required_context_sections():
    prompt = build_auto_reply_generation_prompt(
        {
            "ticket_number": "TKT-AR-1",
            "category": "refund",
            "sentiment_label": "negative",
            "sentiment_score": -0.6,
            "priority": 2,
            "source": "email",
            "summary": "Customer requested a refund after duplicate billing",
            "customer_name": "Taylor",
            "company_name": "Acme",
            "total_tickets": 4,
            "avg_satisfaction_score": 3.5,
            "churn_risk_score": 28,
            "customer_history": ["- TKT-OLD-1: billing / open / Duplicate charge last month"],
            "recent_messages": ["- Customer (Taylor, 2026-04-12T10:00:00+00:00): I need a refund."],
        }
    )

    assert "Category: refund" in prompt
    assert "Sentiment: negative (-0.6)" in prompt
    assert "CUSTOMER HISTORY" in prompt
    assert "PREVIOUS CONVERSATION" in prompt
    assert '"subject": "Email subject line"' in prompt


def test_client_classification_config_merges_prompt_and_escalation_rules(test_db, test_client_record):
    test_client_record.custom_prompt_enabled = True
    test_client_record.custom_prompt_config = {
        "tone": "empathetic",
        "focus_areas": ["refunds", "chargebacks"],
        "classification_rules": {
            "prioritize_refunds": True,
        },
        "reply_guidelines": {
            "max_length": "short",
        },
        "industry": "finance",
    }
    test_db.add(
        EscalationRule(
            id=uuid.uuid4(),
            client_id=test_client_record.id,
            rule_name="Legal complaints",
            trigger_condition="legal_threat",
            escalation_level=2,
            escalate_to_email="legal@example.com",
            category_code="LEGAL",
            trigger_after_hours=2,
            enabled=True,
        )
    )
    test_db.commit()

    config = build_client_classification_config(test_db, test_client_record)

    assert config["tone"] == "empathetic"
    assert config["industry"] == "finance"
    assert config["focus_areas"] == ["refunds", "chargebacks"]
    assert config["classification_rules"]["prioritize_refunds"] is True
    assert config["classification_rules"]["auto_escalate_legal"] is True
    assert config["reply_guidelines"]["max_length"] == "short"
    assert len(config["escalation_rules"]) == 1
    assert config["escalation_rules"][0]["name"] == "Legal complaints"
    assert config["escalation_rules"][0]["escalate_to"] == "legal@example.com"


def test_classification_prompt_includes_client_escalation_rules():
    prompt = build_classification_prompt(
        "Customer is threatening legal action over a refund",
        {
            "tone": "professional",
            "focus_areas": ["refunds"],
            "classification_rules": {"auto_escalate_legal": True},
            "reply_guidelines": {"max_length": "medium"},
            "industry": "finance",
            "escalation_rules": [
                {
                    "name": "Legal complaints",
                    "trigger_condition": "legal_threat",
                    "escalation_level": 2,
                    "trigger_after_hours": 2,
                    "category_code": "LEGAL",
                    "escalate_to": "legal@example.com",
                }
            ],
        },
    )

    assert "CLIENT ESCALATION RULES" in prompt
    assert "Legal complaints: trigger=legal_threat" in prompt
    assert "target=legal@example.com" in prompt


def test_normalize_classification_output_returns_consistent_schema():
    result = normalize_classification_output(
        {
            "intent": "not_valid",
            "category": "mystery",
            "recommended_action": "do_something_else",
            "priority": "bad",
            "summary": None,
        },
        "Need help with my account",
    )

    assert set(result) == {
        "intent",
        "category",
        "sentiment",
        "urgency_score",
        "priority",
        "recommended_action",
        "confidence",
        "summary",
    }
    assert result["intent"] == "complaint"
    assert result["category"] == "general"
    assert result["recommended_action"] == "support_ticket"
    assert result["priority"] == 2
    assert result["summary"] == "Need help with my account"


def test_chatbot_generate_reply_uses_existing_classification(monkeypatch):
    class DummyQuery:
        def filter(self, *args, **kwargs):
            return self

        def first(self):
            return None

    class DummySession:
        def query(self, *args, **kwargs):
            return DummyQuery()

        def close(self):
            return None

    monkeypatch.setattr(chatbot_module, "SessionLocal", lambda: DummySession())
    monkeypatch.setattr(
        chatbot_module,
        "classify_message",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("classifier should not be called")),
    )
    monkeypatch.setenv("GEMINI_API_KEY", "")

    result = chatbot_module.generate_reply(
        "Need an urgent refund",
        classification={
            "priority": 5,
            "recommended_action": "escalate",
        },
    )

    assert result["reply"] == ""
    assert result["escalate"] is True
