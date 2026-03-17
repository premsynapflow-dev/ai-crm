from datetime import datetime, timedelta
from collections import defaultdict
import threading

from starlette.middleware.base import BaseHTTPMiddleware
from fastapi.responses import JSONResponse

from app.utils.logging import get_logger

logger = get_logger(__name__)


class InMemoryRateLimiter:
    """Thread-safe in-memory rate limiter with sliding window"""
    
    def __init__(self):
        self.requests = defaultdict(list)
        self.lock = threading.Lock()
    
    def is_allowed(self, key: str, limit: int, window_seconds: int = 3600) -> bool:
        with self.lock:
            now = datetime.utcnow()
            cutoff = now - timedelta(seconds=window_seconds)
            
            # Remove expired entries
            self.requests[key] = [
                timestamp for timestamp in self.requests[key]
                if timestamp > cutoff
            ]
            
            # Check limit
            if len(self.requests[key]) >= limit:
                return False
            
            # Record this request
            self.requests[key].append(now)
            return True
    
    def cleanup_old_entries(self):
        """Periodically clean up old data"""
        with self.lock:
            now = datetime.utcnow()
            cutoff = now - timedelta(hours=2)
            
            keys_to_delete = []
            for key, timestamps in self.requests.items():
                self.requests[key] = [ts for ts in timestamps if ts > cutoff]
                if not self.requests[key]:
                    keys_to_delete.append(key)
            
            for key in keys_to_delete:
                del self.requests[key]


rate_limiter = InMemoryRateLimiter()


class DatabaseRateLimitMiddleware(BaseHTTPMiddleware):
    """Rate limit middleware using in-memory storage"""
    
    def __init__(self, app):
        super().__init__(app)
        self.rules = {
            "/webhook/complaint": 100,
            "/webhook/email": 100,
            "/webhook/whatsapp": 100,
            "/api/signup": 10,
            "/api/v1/auth/login": 20,
            "/billing/webhook": 1000,
            "/portal": 50,
            "/dashboard": 50,
        }
    
    async def dispatch(self, request, call_next):
        # Find matching rule
        matching_prefix = None
        limit = None
        
        for prefix, rule_limit in self.rules.items():
            if request.url.path.startswith(prefix):
                matching_prefix = prefix
                limit = rule_limit
                break
        
        if matching_prefix and limit:
            ip_address = request.client.host if request.client else "unknown"
            rate_key = f"{ip_address}:{matching_prefix}"
            
            if not rate_limiter.is_allowed(rate_key, limit, window_seconds=3600):
                logger.warning(f"Rate limit exceeded for {ip_address} on {matching_prefix}")
                return JSONResponse(
                    status_code=429,
                    content={
                        "detail": "Rate limit exceeded. Please try again later.",
                        "retry_after": 3600
                    }
                )
        
        return await call_next(request)
