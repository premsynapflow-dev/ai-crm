import pytest
from app.intelligence.classifier import classify_message_async
from app.intelligence.reply_engine import generate_ai_reply_async
from app.db.models import Complaint
import uuid


@pytest.mark.asyncio
async def test_classifier_returns_valid_structure():
    """Test that classifier returns expected structure"""
    result = await classify_message_async("I want a refund")
    
    assert "intent" in result
    assert "category" in result
    assert "sentiment" in result
    assert "urgency_score" in result
    assert "priority" in result
    assert "recommended_action" in result
    assert "confidence" in result
    assert "summary" in result


@pytest.mark.asyncio
async def test_classifier_handles_empty_message():
    """Test classifier with empty message"""
    result = await classify_message_async("")
    
    # Should return fallback
    assert result["confidence"] == 0.0
    assert result["intent"] == "complaint"


@pytest.mark.asyncio
async def test_classifier_sentiment_bounds():
    """Test that sentiment is bounded -1 to 1"""
    result = await classify_message_async("I absolutely love this!")
    assert -1.0 <= result["sentiment"] <= 1.0


@pytest.mark.asyncio
async def test_reply_engine_generates_text():
    """Test reply engine generates text"""
    complaint = Complaint(
        id=uuid.uuid4(),
        summary="Need refund",
        category="refund",
        sentiment=-0.5,
        confidence=0.8
    )
    
    result = await generate_ai_reply_async(complaint, [])
    
    assert "reply_text" in result
    assert "confidence_score" in result
    assert len(result["reply_text"]) > 0
