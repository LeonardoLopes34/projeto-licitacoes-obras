from __future__ import annotations

import threading
import time
from collections.abc import Callable


class CircuitBreaker:
    """Circuit breaker pequeno e seguro para chamadas a serviços externos."""

    def __init__(
        self,
        *,
        failure_threshold: int = 3,
        recovery_timeout: float = 30.0,
        clock: Callable[[], float] | None = None,
    ) -> None:
        if failure_threshold < 1:
            raise ValueError("failure_threshold deve ser maior que zero")
        if recovery_timeout <= 0:
            raise ValueError("recovery_timeout deve ser maior que zero")

        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self._clock = clock or time.monotonic
        self._lock = threading.Lock()
        self._consecutive_failures = 0
        self._opened_at: float | None = None
        self._probe_in_flight = False
        self._last_response_time: float | None = None

    @property
    def consecutive_failures(self) -> int:
        with self._lock:
            return self._consecutive_failures

    @property
    def last_response_time(self) -> float | None:
        """Duração, em segundos, da última tentativa registrada."""
        with self._lock:
            return self._last_response_time

    @property
    def is_open(self) -> bool:
        with self._lock:
            return self._opened_at is not None

    def allow_request(self) -> bool:
        """Informa se uma chamada pode ser feita neste momento."""
        with self._lock:
            if self._opened_at is None:
                return True

            if self._clock() - self._opened_at < self.recovery_timeout:
                return False

            if self._probe_in_flight:
                return False

            self._probe_in_flight = True
            return True

    def record_success(self, *, response_time: float | None = None) -> None:
        with self._lock:
            self._consecutive_failures = 0
            self._opened_at = None
            self._probe_in_flight = False
            if response_time is not None:
                self._last_response_time = max(0.0, response_time)

    def record_failure(self, *, response_time: float | None = None) -> None:
        with self._lock:
            self._consecutive_failures += 1
            self._probe_in_flight = False
            if response_time is not None:
                self._last_response_time = max(0.0, response_time)
            if self._consecutive_failures >= self.failure_threshold:
                self._opened_at = self._clock()

    def reset(self) -> None:
        """Limpa o estado do circuito, útil para inicialização controlada e testes."""
        with self._lock:
            self._consecutive_failures = 0
            self._opened_at = None
            self._probe_in_flight = False
            self._last_response_time = None
