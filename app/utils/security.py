"""Security utilities for API keys, passwords, and tokens"""

import secrets
from passlib.context import CryptContext

# Configure password hashing with bcrypt
pwd_context = CryptContext(
    schemes=["bcrypt"],
    deprecated="auto",
    bcrypt__rounds=12  # Explicit round count for security
)


def generate_api_key(length: int = 32) -> str:
    """
    Generate cryptographically secure API key.
    
    Args:
        length: Length of the key in bytes (default 32 = 256 bits)
    
    Returns:
        URL-safe base64 encoded string
    """
    return secrets.token_urlsafe(length)


def generate_secure_token(length: int = 32) -> str:
    """
    Generate secure random token.
    
    Args:
        length: Length of the token in bytes
    
    Returns:
        Hex-encoded string
    """
    return secrets.token_hex(length)


def hash_password(password: str) -> str:
    """
    Hash password using bcrypt.
    
    Args:
        password: Plain text password
    
    Returns:
        Hashed password string
    """
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verify password against hash.
    
    Args:
        plain_password: Plain text password to verify
        hashed_password: Previously hashed password
    
    Returns:
        True if password matches, False otherwise
    """
    return pwd_context.verify(plain_password, hashed_password)


def generate_client_secret() -> str:
    """
    Generate client secret for OAuth-like flows.
    
    Returns:
        URL-safe 384-bit token
    """
    return secrets.token_urlsafe(48)
