"""Circuit breaker pattern for fetch cycle resilience."""

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Optional, List

logger = logging.getLogger(__name__)


@dataclass
class CircuitBreakerStatus:
    """Status snapshot for admin dashboard consumption."""
    state: str  # CLOSED, OPEN, HALF_OPEN
    failure_count: int
    last_success: Optional[datetime]
    last_failure: Optional[datetime]
    cooldown_duration: int  # seconds
    cooldown_remaining: Optional[int]  # seconds, None if not OPEN
    error_count_since_success: int


class CircuitBreaker:
    """Circuit breaker for fetch cycle protection.

    States:
    - CLOSED: Normal operation, fetch cycles proceed
    - OPEN: Circuit tripped, fetch cycles blocked until cooldown
    - HALF_OPEN: Testing recovery with single probe fetch
    """

    def __init__(self):
        self.state = "CLOSED"
        self.failure_count = 0
        self.last_success: Optional[datetime] = None
        self.last_failure: Optional[datetime] = None
        self.cooldown_duration = 3600  # 1 hour in seconds
        self.max_cooldown = 86400  # 24 hours in seconds
        self.error_count_since_success = 0
        self.recent_errors: List[dict] = []

    def should_allow_fetch(self) -> bool:
        """Check if fetch cycle should be allowed to proceed."""
        if self.state == "CLOSED":
            return True

        if self.state == "OPEN":
            # Check if cooldown period has elapsed
            if self.last_failure:
                elapsed = (datetime.now() - self.last_failure).total_seconds()
                if elapsed >= self.cooldown_duration:
                    # Transition to HALF_OPEN for probe
                    self.state = "HALF_OPEN"
                    logger.info("Circuit breaker transitioning to HALF_OPEN (probe attempt)")
                    return True
                else:
                    remaining = int(self.cooldown_duration - elapsed)
                    logger.warning(f"Circuit breaker OPEN - cooldown remaining: {remaining}s")
                    return False
            return False

        if self.state == "HALF_OPEN":
            # Allow single probe
            return True

        return False

    def record_success(self):
        """Record successful fetch cycle."""
        self.state = "CLOSED"
        self.failure_count = 0
        self.error_count_since_success = 0
        self.last_success = datetime.now()
        self.cooldown_duration = 3600  # Reset to 1 hour
        logger.info("Fetch cycle successful. Circuit breaker CLOSED.")

    def record_failure(self, error_info: Optional[dict] = None):
        """Record failed fetch cycle."""
        self.failure_count += 1
        self.error_count_since_success += 1
        self.last_failure = datetime.now()

        # Store recent error info (keep last 10)
        if error_info:
            self.recent_errors.append({
                "timestamp": datetime.now(),
                "info": error_info
            })
            if len(self.recent_errors) > 10:
                self.recent_errors = self.recent_errors[-10:]

        if self.state == "HALF_OPEN":
            # Probe failed, go back to OPEN and double cooldown
            self.state = "OPEN"
            self._double_cooldown()
            logger.warning(f"Probe failed, doubling cooldown to {self.cooldown_duration}s")
        elif self.failure_count >= 3:
            # Trip circuit after 3 failures
            self.state = "OPEN"
            logger.error(f"Circuit breaker tripped after {self.failure_count} failures")
        else:
            # Stay CLOSED but count the failure
            logger.warning(f"Fetch cycle failed ({self.failure_count}/3)")

    def _double_cooldown(self):
        """Double cooldown duration up to maximum."""
        self.cooldown_duration = min(self.cooldown_duration * 2, self.max_cooldown)

    def get_status(self) -> CircuitBreakerStatus:
        """Get current status for dashboard display."""
        cooldown_remaining = None
        if self.state == "OPEN" and self.last_failure:
            elapsed = (datetime.now() - self.last_failure).total_seconds()
            cooldown_remaining = max(0, int(self.cooldown_duration - elapsed))

        return CircuitBreakerStatus(
            state=self.state,
            failure_count=self.failure_count,
            last_success=self.last_success,
            last_failure=self.last_failure,
            cooldown_duration=self.cooldown_duration,
            cooldown_remaining=cooldown_remaining,
            error_count_since_success=self.error_count_since_success
        )

    def force_close(self):
        """Force circuit breaker to CLOSED state (admin override)."""
        self.state = "CLOSED"
        self.failure_count = 0
        # Preserve error_count_since_success and recent_errors for diagnostics
        logger.warning("Circuit breaker FORCE CLOSED by admin")

    def get_recent_errors(self) -> List[dict]:
        """Get copy of recent error list."""
        return self.recent_errors.copy()


# Module-level singleton - in-memory, resets on app restart
circuit_breaker = CircuitBreaker()
