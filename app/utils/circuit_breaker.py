from datetime import datetime, timedelta
from enum import Enum
from typing import Callable, Any

from app.utils.logging import get_logger

logger = get_logger(__name__)


class CircuitState(Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class CircuitBreaker:
    """Simple circuit breaker for external service calls"""
    
    def __init__(
        self,
        failure_threshold: int = 5,
        timeout_seconds: int = 60,
        name: str = "unnamed"
    ):
        self.failure_threshold = failure_threshold
        self.timeout = timeout_seconds
        self.name = name
        self.failures = 0
        self.last_failure_time = None
        self.state = CircuitState.CLOSED
    
    def call(self, func: Callable, *args, **kwargs) -> Any:
        """Execute function with circuit breaker protection"""
        
        # Check if circuit should move from OPEN to HALF_OPEN
        if self.state == CircuitState.OPEN:
            if self.last_failure_time and \
               datetime.utcnow() - self.last_failure_time > timedelta(seconds=self.timeout):
                logger.info(f"Circuit breaker [{self.name}] attempting recovery (HALF_OPEN)")
                self.state = CircuitState.HALF_OPEN
                self.failures = 0
            else:
                raise CircuitBreakerOpenError(
                    f"Circuit breaker [{self.name}] is OPEN. Service unavailable."
                )
        
        # Attempt the call
        try:
            result = func(*args, **kwargs)
            
            # Success - reset if we were in HALF_OPEN
            if self.state == CircuitState.HALF_OPEN:
                logger.info(f"Circuit breaker [{self.name}] recovered (CLOSED)")
                self.state = CircuitState.CLOSED
                self.failures = 0
            
            return result
            
        except Exception as e:
            # Failure - increment counter
            self.failures += 1
            self.last_failure_time = datetime.utcnow()
            
            # Open circuit if threshold exceeded
            if self.failures >= self.failure_threshold:
                self.state = CircuitState.OPEN
                logger.error(
                    f"Circuit breaker [{self.name}] opened after {self.failures} failures"
                )
            
            raise
    
    async def call_async(self, func: Callable, *args, **kwargs) -> Any:
        """Async version of circuit breaker call"""
        if self.state == CircuitState.OPEN:
            if self.last_failure_time and \
               datetime.utcnow() - self.last_failure_time > timedelta(seconds=self.timeout):
                self.state = CircuitState.HALF_OPEN
                self.failures = 0
            else:
                raise CircuitBreakerOpenError(
                    f"Circuit breaker [{self.name}] is OPEN. Service unavailable."
                )
        
        try:
            result = await func(*args, **kwargs)
            
            if self.state == CircuitState.HALF_OPEN:
                self.state = CircuitState.CLOSED
                self.failures = 0
            
            return result
            
        except Exception as e:
            self.failures += 1
            self.last_failure_time = datetime.utcnow()
            
            if self.failures >= self.failure_threshold:
                self.state = CircuitState.OPEN
                logger.error(
                    f"Circuit breaker [{self.name}] opened after {self.failures} failures"
                )
            
            raise
    
    def get_state(self) -> dict:
        """Get current circuit breaker state"""
        return {
            "name": self.name,
            "state": self.state.value,
            "failures": self.failures,
            "last_failure": self.last_failure_time.isoformat() if self.last_failure_time else None
        }


class CircuitBreakerOpenError(Exception):
    """Raised when circuit breaker is open"""
    pass


# Global circuit breakers for external services
gemini_breaker = CircuitBreaker(
    failure_threshold=5,
    timeout_seconds=60,
    name="gemini_ai"
)

razorpay_breaker = CircuitBreaker(
    failure_threshold=3,
    timeout_seconds=120,
    name="razorpay"
)

slack_breaker = CircuitBreaker(
    failure_threshold=5,
    timeout_seconds=60,
    name="slack"
)

smtp_breaker = CircuitBreaker(
    failure_threshold=3,
    timeout_seconds=300,
    name="smtp"
)
