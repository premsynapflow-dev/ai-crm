import hmac
import hashlib
from fastapi import HTTPException, Request


def verify_webhook_signature(
    payload: bytes,
    signature: str,
    secret: str
) -> bool:
    """Verify HMAC signature for webhook"""
    if not secret:
        return True  # Skip if no secret configured
    
    expected_signature = hmac.new(
        secret.encode('utf-8'),
        payload,
        hashlib.sha256
    ).hexdigest()
    
    return hmac.compare_digest(expected_signature, signature)


async def verify_razorpay_signature(
    request: Request,
    secret: str
) -> bool:
    """Verify Razorpay webhook signature"""
    signature = request.headers.get("x-razorpay-signature", "")
    if not signature:
        return False
    
    payload = await request.body()
    return verify_webhook_signature(payload, signature, secret)
