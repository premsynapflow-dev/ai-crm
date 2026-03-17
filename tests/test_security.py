import pytest
from app.utils.sanitize import (
    sanitize_html,
    sanitize_email,
    sanitize_phone,
    sanitize_message,
)
from app.utils.security import generate_api_key, hash_password, verify_password


def test_html_sanitization():
    """Test HTML tags are removed"""
    dirty = "<script>alert('xss')</script>Hello"
    clean = sanitize_html(dirty)
    assert "<script>" not in clean
    assert "Hello" in clean


def test_email_validation():
    """Test email validation"""
    assert sanitize_email("test@example.com") == "test@example.com"
    assert sanitize_email("invalid") is None
    assert sanitize_email("test@") is None


def test_phone_sanitization():
    """Test phone sanitization"""
    assert sanitize_phone("+1-234-567-8900") == "+12345678900"
    assert sanitize_phone("123") is None  # Too short


def test_message_sanitization():
    """Test message sanitization"""
    dirty = "<b>Test</b> message\n\n\n  "
    clean = sanitize_message(dirty)
    assert "<b>" not in clean
    assert "Test message" in clean


def test_api_key_generation():
    """Test API key is cryptographically secure"""
    key1 = generate_api_key()
    key2 = generate_api_key()
    
    assert len(key1) > 30
    assert key1 != key2  # Should be unique


def test_password_hashing():
    """Test password hashing and verification"""
    password = "SecurePassword123!"
    hashed = hash_password(password)
    
    assert password != hashed
    assert verify_password(password, hashed)
    assert not verify_password("wrong", hashed)
