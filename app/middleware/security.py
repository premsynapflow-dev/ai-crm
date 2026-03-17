from starlette.middleware.base import BaseHTTPMiddleware
from fastapi.responses import JSONResponse


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Add security headers without database queries"""
    
    async def dispatch(self, request, call_next):
        # Check request size
        content_length = request.headers.get("content-length")
        if content_length and int(content_length) > 2_000_000:
            return JSONResponse(
                status_code=413, 
                content={"detail": "Request body too large"}
            )
        
        # Process request
        response = await call_next(request)
        
        # Add security headers
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        
        if request.url.scheme == "https":
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        
        return response
