import asyncio
import logging
import random
import time
from typing import TypeVar, Callable, Any, Optional

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
    Circuit breaker dengan half-open state untuk recovery yang benar.
    
    States:
        CLOSED  → normal, request diproses
        OPEN    → terlalu banyak failure, semua request langsung fail
        HALF-OPEN → setelah timeout, izinkan 1 request percobaan:
                    sukses → kembali CLOSED
                    gagal  → kembali OPEN, reset timer
    """
    CLOSED = "CLOSED"
    OPEN = "OPEN"
    HALF_OPEN = "HALF_OPEN"

    def __init__(self, failure_threshold: int = 3, timeout_seconds: int = 60):
        self.failure_threshold = failure_threshold
        self.timeout_seconds = timeout_seconds
        self.failure_count = 0
        self.last_failure_time: Optional[float] = None
        self.state = self.CLOSED

    def _check_timeout_reset(self):
        """Transisi OPEN → HALF_OPEN jika timeout sudah lewat."""
        if (
            self.state == self.OPEN
            and self.last_failure_time is not None
            and (asyncio.get_event_loop().time() - self.last_failure_time) > self.timeout_seconds
        ):
            self.state = self.HALF_OPEN
            logger.info(
                f"🟡 [CIRCUIT BREAKER] HALF-OPEN — "
                f"timeout {self.timeout_seconds}s berlalu, izinkan 1 request percobaan"
            )

    async def call(self, coro):
        """Execute coro dengan circuit breaker protection."""
        self._check_timeout_reset()

        if self.state == self.OPEN:
            elapsed = (
                asyncio.get_event_loop().time() - self.last_failure_time
                if self.last_failure_time else 0
            )
            remaining = max(0, self.timeout_seconds - elapsed)
            raise CircuitBreakerOpen(
                f"Circuit breaker OPEN. "
                f"{self.failure_count} failures. Reset dalam {remaining:.0f}s"
            )

        try:
            result = await coro

            # SUCCESS
            if self.state == self.HALF_OPEN:
                logger.info(
                    "✅ [CIRCUIT BREAKER] HALF-OPEN → CLOSED — "
                    "request percobaan berhasil, circuit recovered"
                )
            elif self.failure_count > 0:
                logger.info(
                    f"✅ [CIRCUIT BREAKER] Success — "
                    f"reset failure count dari {self.failure_count}"
                )

            self.failure_count = 0
            self.last_failure_time = None
            self.state = self.CLOSED
            return result

        except Exception as e:
            self.failure_count += 1
            self.last_failure_time = asyncio.get_event_loop().time()

            if self.state == self.HALF_OPEN:
                # Gagal di half-open → balik OPEN, reset timer
                self.state = self.OPEN
                logger.error(
                    f"🔴 [CIRCUIT BREAKER] HALF-OPEN → OPEN — "
                    f"request percobaan gagal: {e}"
                )
                raise CircuitBreakerOpen(
                    f"Circuit breaker kembali OPEN setelah gagal di half-open state"
                ) from e

            logger.warning(
                f"⚠️ [CIRCUIT BREAKER] Failure "
                f"#{self.failure_count}/{self.failure_threshold}: {e}"
            )

            if self.failure_count >= self.failure_threshold:
                self.state = self.OPEN
                logger.error(
                    f"🔴 [CIRCUIT BREAKER] CLOSED → OPEN — "
                    f"{self.failure_count} failures berturut-turut"
                )
                raise CircuitBreakerOpen(
                    f"Circuit breaker open after {self.failure_count} failures"
                ) from e
            raise

    def reset(self):
        """Manual reset — panggil saat service pulih (opsional)."""
        self.failure_count = 0
        self.last_failure_time = None
        self.state = self.CLOSED
        logger.info("🔄 [CIRCUIT BREAKER] Manual reset → CLOSED")

    @property
    def is_open(self) -> bool:
        """Backward-compatible property."""
        return self.state == self.OPEN


async def retry_with_backoff(
    coro_func: Callable[..., Any],
    max_retries: int = 2,
    initial_delay: float = 1.0,
    max_delay: float = 10.0,
    timeout: float = 60.0,
    operation_name: str = "Operation",
    circuit_breaker: Optional[CircuitBreaker] = None,
) -> Any:
    """
    Execute async function dengan exponential backoff retry logic.

    Args:
        coro_func:        Async function to call (no args — partial atau lambda)
        max_retries:      Maximum retry attempts (default 2)
        initial_delay:    Starting delay in seconds (default 1.0s)
        max_delay:        Maximum delay in seconds (default 10s)
        timeout:          Timeout per attempt in seconds (default 60s)
        operation_name:   Nama operasi untuk logging
        circuit_breaker:  Optional CircuitBreaker instance

    Returns:
        Result dari coro_func jika sukses

    Raises:
        RetryExhaustedError:  Jika semua retry gagal
        CircuitBreakerOpen:   Jika circuit breaker terbuka
    """
    attempt = 0
    last_error = None

    while attempt <= max_retries:
        try:
            if circuit_breaker:
                return await circuit_breaker.call(
                    asyncio.wait_for(coro_func(), timeout=timeout)
                )
            else:
                return await asyncio.wait_for(coro_func(), timeout=timeout)

        except asyncio.TimeoutError as e:
            last_error = e
            logger.warning(
                f"⏱️ [RETRY] {operation_name} timeout ({timeout}s) "
                f"— attempt {attempt + 1}/{max_retries + 1}"
            )
        except CircuitBreakerOpen:
            logger.error(f"🔴 [RETRY] {operation_name} — circuit breaker open, abort")
            raise
        except Exception as e:
            last_error = e
            logger.warning(
                f"⚠️ [RETRY] {operation_name} failed "
                f"— attempt {attempt + 1}/{max_retries + 1}: {str(e)[:100]}"
            )

        if attempt < max_retries:
            delay = min(initial_delay * (2 ** attempt), max_delay)
            jitter = random.uniform(0, delay * 0.15)  # 15% jitter
            total_delay = delay + jitter
            logger.info(
                f"⏳ [RETRY] {operation_name} "
                f"— retry ke-{attempt + 2} dalam {total_delay:.2f}s"
            )
            await asyncio.sleep(total_delay)

        attempt += 1

    logger.error(
        f"❌ [RETRY] {operation_name} exhausted after {max_retries + 1} attempts. "
        f"Last error: {str(last_error)}"
    )
    raise RetryExhaustedError(
        f"{operation_name} failed after {max_retries + 1} attempts: {str(last_error)}"
    ) from last_error


# Singleton circuit breakers
# timeout_seconds=120 → circuit bisa recover setelah 2 menit (model loading worst case)
layer0_circuit_breaker = CircuitBreaker(failure_threshold=3, timeout_seconds=120)
layer0_rewriter_circuit_breaker = CircuitBreaker(failure_threshold=3, timeout_seconds=120)
layer1_circuit_breaker = CircuitBreaker(failure_threshold=3, timeout_seconds=120)