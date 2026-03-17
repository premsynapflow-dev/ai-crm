import bleach
import re
from typing import Optional


def sanitize_html(text: str) -> str:
    """Remove all HTML tags and dangerous content"""
    if not text:
        return ""
    return bleach.clean(text, tags=[], strip=True)


def sanitize_email(email: Optional[str]) -> Optional[str]:
    """Validate and sanitize email address"""
    if not email:
        return None
    
    email = email.strip().lower()
    
    # Basic email regex
    email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    if not re.match(email_pattern, email):
        return None
    
    return email


def sanitize_phone(phone: Optional[str]) -> Optional[str]:
    """Sanitize phone number"""
    if not phone:
        return None
    
    # Remove all non-digit characters except +
    phone = re.sub(r'[^\d+]', '', phone.strip())
    
    # Basic validation (10-15 digits)
    if len(phone) < 10 or len(phone) > 15:
        return None
    
    return phone


def sanitize_message(message: str, max_length: int = 10000) -> str:
    """Sanitize user message input"""
    if not message:
        return ""
    
    # Remove HTML
    message = sanitize_html(message)
    
    # Trim whitespace
    message = message.strip()
    
    # Limit length
    if len(message) > max_length:
        message = message[:max_length]
    
    return message


def sanitize_filename(filename: str) -> str:
    """Sanitize filename for safe storage"""
    if not filename:
        return "unnamed"
    
    # Remove path separators and dangerous characters
    filename = re.sub(r'[/\\:*?"<>|]', '', filename)
    
    # Limit length
    if len(filename) > 255:
        filename = filename[:255]
    
    return filename or "unnamed"
