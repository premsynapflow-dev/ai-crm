import asyncio
from app.intelligence.classifier import classify_message_async
from app.intelligence.prompt_builder import build_reply_prompt
from app.intelligence.reply_engine import generate_ai_reply_async
from app.db.models import Complaint
import uuid


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
