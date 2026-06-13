import asyncio
import logging
import random
from typing import TypeVar, Callable, Any, Optional
from functools import wraps

logger = logging.getLogger("CAKRA_RETRY")

T = TypeVar('T')


class RetryExhaustedError(Exception):
    """Exception raised when all retry attempts have been exhausted"""
    pass


class CircuitBreakerOpen(Exception):
    """Exception raised when circuit breaker is open"""
    pass


class CircuitBreaker:
    """
    Simple circuit breaker untuk mencegah cascading failures.
    Jika >3 failures dalam 60s, buka circuit (semua request langsung fail).
    """
    def __init__(self, failure_threshold: int = 3, timeout_seconds: int = 60):
        self.failure_threshold = failure_threshold
        self.timeout_seconds = timeout_seconds
        self.failure_count = 0
        self.last_failure_time = None
        self.is_open = False

    async def call(self, coro):
        """Execute coro dengan circuit breaker protection"""
        # Reset jika timeout sudah terlewat
        if self.last_failure_time and (asyncio.get_event_loop().time() - self.last_failure_time) > self.timeout_seconds:
            self.failure_count = 0
            self.is_open = False
            logger.info("🔄 [CIRCUIT BREAKER] Reset — timeout periode berlalu")

        # Cek apakah circuit terbuka
        if self.is_open:
            raise CircuitBreakerOpen(
                f"Circuit breaker open. {self.failure_count} failures dalam {self.timeout_seconds}s"
            )

        try:
            result = await coro
            # Success — reset failure count
            if self.failure_count > 0:
                logger.info(f"✅ [CIRCUIT BREAKER] Success detected — reset failure count dari {self.failure_count}")
                self.failure_count = 0
            return result
        except Exception as e:
            self.failure_count += 1
            self.last_failure_time = asyncio.get_event_loop().time()
            logger.warning(f"⚠️ [CIRCUIT BREAKER] Failure #{self.failure_count}/{self.failure_threshold}: {e}")

            if self.failure_count >= self.failure_threshold:
                self.is_open = True
                logger.error(f"🔴 [CIRCUIT BREAKER] OPEN — terlalu banyak failures ({self.failure_count})")
                raise CircuitBreakerOpen(
                    f"Circuit breaker open after {self.failure_count} failures"
                ) from e
            raise


async def retry_with_backoff(
    coro_func: Callable[..., Any],
    max_retries: int = 2,
    initial_delay: float = 0.5,
    max_delay: float = 5.0,
    timeout: float = 60.0,
    operation_name: str = "Operation",
    circuit_breaker: Optional[CircuitBreaker] = None,
) -> Any:
    """
    Execute async function dengan exponential backoff retry logic.
    
    Args:
        coro_func: Async function to call (no args — harus sudah partial atau lambda)
        max_retries: Maximum number of retry attempts (default 2)
        initial_delay: Starting delay in seconds (default 0.5s)
        max_delay: Maximum delay in seconds (default 5s)
        timeout: Total timeout untuk sekali attempt (default 60s)
        operation_name: Nama operasi untuk logging
        circuit_breaker: Optional circuit breaker instance
    
    Returns:
        Result dari coro_func jika sukses
        
    Raises:
        RetryExhaustedError: Jika semua retry gagal
        CircuitBreakerOpen: Jika circuit breaker terbuka
    """
    
    attempt = 0
    last_error = None
    
    while attempt <= max_retries:
        try:
            if circuit_breaker:
                return await circuit_breaker.call(asyncio.wait_for(coro_func(), timeout=timeout))
            else:
                return await asyncio.wait_for(coro_func(), timeout=timeout)
                
        except asyncio.TimeoutError as e:
            last_error = e
            logger.warning(
                f"⏱️ [RETRY] {operation_name} timeout ({timeout}s) — attempt {attempt + 1}/{max_retries + 1}"
            )
        except CircuitBreakerOpen as e:
            logger.error(f"🔴 [RETRY] {operation_name} — circuit breaker open")
            raise
        except Exception as e:
            last_error = e
            logger.warning(
                f"⚠️ [RETRY] {operation_name} failed — attempt {attempt + 1}/{max_retries + 1}: {str(e)[:100]}"
            )
        
        # Jika masih ada retry tersisa
        if attempt < max_retries:
            # Exponential backoff with jitter
            delay = min(initial_delay * (2 ** attempt), max_delay)
            jitter = random.uniform(0, delay * 0.1)  # 10% jitter
            total_delay = delay + jitter
            
            logger.info(
                f"⏳ [RETRY] {operation_name} — menunggu {total_delay:.2f}s sebelum retry"
            )
            await asyncio.sleep(total_delay)
        
        attempt += 1
    
    # Semua retry exhausted
    logger.error(
        f"❌ [RETRY] {operation_name} failed after {max_retries + 1} attempts. Last error: {str(last_error)}"
    )
    raise RetryExhaustedError(
        f"{operation_name} failed after {max_retries + 1} attempts: {str(last_error)}"
    ) from last_error


# Singleton circuit breakers untuk Layer 0 dan Layer 1
layer0_circuit_breaker = CircuitBreaker(failure_threshold=3, timeout_seconds=60)
layer1_circuit_breaker = CircuitBreaker(failure_threshold=3, timeout_seconds=60)
