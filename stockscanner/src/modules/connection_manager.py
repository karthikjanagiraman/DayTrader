"""
Connection Manager for IBKR
Handles connection health, rate limiting, and automatic recovery
"""

import time
import threading
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
from loguru import logger
from collections import deque
import statistics


class RateLimitManager:
    """Manages API rate limits with adaptive throttling"""

    def __init__(self, max_requests_per_second: float = 10):
        """
        Initialize rate limit manager

        Args:
            max_requests_per_second: Maximum requests per second
        """
        self.max_requests_per_second = max_requests_per_second
        self.min_interval = 1.0 / max_requests_per_second
        self.request_times = deque(maxlen=100)
        self.lock = threading.Lock()
        self.violations = 0
        self.last_violation = None
        self.adaptive_factor = 1.0

    def wait_if_needed(self):
        """Wait if necessary to respect rate limits"""
        with self.lock:
            now = time.time()

            # Clean old entries (older than 1 second)
            while self.request_times and self.request_times[0] < now - 1:
                self.request_times.popleft()

            # Check if we need to wait
            if len(self.request_times) >= self.max_requests_per_second * self.adaptive_factor:
                oldest = self.request_times[0]
                wait_time = max(0, 1 - (now - oldest))
                if wait_time > 0:
                    logger.debug(f"Rate limiting: waiting {wait_time:.2f}s")
                    time.sleep(wait_time)

            # Record this request
            self.request_times.append(time.time())

    def report_violation(self):
        """Report a rate limit violation"""
        with self.lock:
            self.violations += 1
            self.last_violation = time.time()
            # Increase throttling
            self.adaptive_factor = max(0.5, self.adaptive_factor * 0.8)
            logger.warning(f"Rate limit violation #{self.violations}, reducing rate to {self.max_requests_per_second * self.adaptive_factor:.1f} req/s")

    def report_success(self):
        """Report successful request"""
        with self.lock:
            # Gradually increase rate if no recent violations
            if self.last_violation and time.time() - self.last_violation > 30:
                self.adaptive_factor = min(1.0, self.adaptive_factor * 1.05)

    def get_current_rate(self) -> float:
        """Get current request rate"""
        with self.lock:
            return self.max_requests_per_second * self.adaptive_factor


class ConnectionHealth:
    """Monitors connection health and performance"""

    def __init__(self, window_size: int = 100):
        """
        Initialize health monitor

        Args:
            window_size: Size of monitoring window
        """
        self.window_size = window_size
        self.response_times = deque(maxlen=window_size)
        self.error_count = 0
        self.success_count = 0
        self.last_error = None
        self.last_success = None
        self.lock = threading.Lock()

    def record_request(self, success: bool, response_time: float = None, error: str = None):
        """Record a request result"""
        with self.lock:
            if success:
                self.success_count += 1
                self.last_success = time.time()
                if response_time:
                    self.response_times.append(response_time)
            else:
                self.error_count += 1
                self.last_error = time.time()
                if error:
                    logger.debug(f"Request failed: {error}")

    def get_health_score(self) -> float:
        """
        Get health score (0-100)

        Returns:
            Health score percentage
        """
        with self.lock:
            if self.success_count + self.error_count == 0:
                return 100.0

            success_rate = self.success_count / (self.success_count + self.error_count)

            # Factor in recent errors
            recent_error_penalty = 0
            if self.last_error and time.time() - self.last_error < 60:
                recent_error_penalty = 0.2

            return max(0, min(100, (success_rate - recent_error_penalty) * 100))

    def get_avg_response_time(self) -> float:
        """Get average response time"""
        with self.lock:
            if self.response_times:
                return statistics.mean(self.response_times)
            return 0

    def should_throttle(self) -> bool:
        """Check if we should throttle requests"""
        with self.lock:
            # Throttle if health is poor
            if self.get_health_score() < 50:
                return True

            # Throttle if recent errors
            if self.last_error and time.time() - self.last_error < 10:
                error_rate = self.error_count / max(1, self.success_count + self.error_count)
                return error_rate > 0.3

            return False

    def reset(self):
        """Reset health statistics"""
        with self.lock:
            self.response_times.clear()
            self.error_count = 0
            self.success_count = 0
            self.last_error = None
            self.last_success = None


class ConnectionManager:
    """Manages IBKR connections with health monitoring and auto-recovery"""

    def __init__(self, config: Dict[str, Any]):
        """
        Initialize connection manager

        Args:
            config: Configuration dictionary
        """
        self.config = config
        self.rate_limiter = RateLimitManager(
            max_requests_per_second=config.get('max_requests_per_second', 10)
        )
        self.health_monitor = ConnectionHealth()
        self.connections: Dict[int, Any] = {}
        self.lock = threading.Lock()
        self.auto_recovery_enabled = config.get('auto_recovery', True)
        self.last_recovery_attempt = None

    def before_request(self):
        """Called before making a request"""
        # Check health
        if self.health_monitor.should_throttle():
            time.sleep(0.5)  # Extra throttling for poor health

        # Rate limiting
        self.rate_limiter.wait_if_needed()

    def after_request(self, success: bool, response_time: float = None, error: str = None):
        """
        Called after request completion

        Args:
            success: Whether request succeeded
            response_time: Request duration in seconds
            error: Error message if failed
        """
        self.health_monitor.record_request(success, response_time, error)

        if success:
            self.rate_limiter.report_success()
        else:
            # Check for rate limit errors
            if error and ('pacing' in error.lower() or 'rate' in error.lower()):
                self.rate_limiter.report_violation()

            # Auto recovery if needed
            if self.auto_recovery_enabled:
                self._check_auto_recovery()

    def _check_auto_recovery(self):
        """Check if auto-recovery is needed"""
        health_score = self.health_monitor.get_health_score()

        if health_score < 30:
            # Very poor health - attempt recovery
            if not self.last_recovery_attempt or \
               time.time() - self.last_recovery_attempt > 60:
                logger.warning(f"Poor connection health ({health_score:.1f}%), attempting recovery...")
                self.last_recovery_attempt = time.time()
                self._perform_recovery()

    def _perform_recovery(self):
        """Perform connection recovery"""
        try:
            # Reset health monitor
            self.health_monitor.reset()

            # Reset rate limiter
            self.rate_limiter.adaptive_factor = 0.5  # Start slow

            logger.info("Connection recovery initiated")

            # Wait a bit for things to settle
            time.sleep(2)

        except Exception as e:
            logger.error(f"Recovery failed: {e}")

    def get_status(self) -> Dict[str, Any]:
        """Get connection manager status"""
        return {
            'health_score': self.health_monitor.get_health_score(),
            'avg_response_time': self.health_monitor.get_avg_response_time(),
            'success_count': self.health_monitor.success_count,
            'error_count': self.health_monitor.error_count,
            'current_rate_limit': self.rate_limiter.get_current_rate(),
            'rate_violations': self.rate_limiter.violations
        }