"""Límite de intentos en memoria (ventana deslizante).

Sirve para frenar la fuerza bruta en login y signup. Es un contador por PROCESO: con varios
workers cada uno cuenta por separado, así que el límite real es limit x workers. Para un
límite global exacto haría falta un almacén compartido (por ejemplo Redis).
"""

import time
from collections import deque
from collections.abc import Callable
from math import ceil

from app.core.exceptions import TooManyRequestsError

# Cada tantas operaciones se descartan las claves ya vencidas, para que la memoria no crezca
# sin límite si alguien prueba millones de emails distintos.
_SWEEP_EVERY = 1_000


class SlidingWindowLimiter:
    """Permite como máximo `limit` eventos por clave dentro de los últimos `window` segundos."""

    def __init__(
        self, limit: int, window: float, clock: Callable[[], float] = time.monotonic
    ) -> None:
        self._limit = limit
        self._window = window
        self._clock = clock
        self._events: dict[str, deque[float]] = {}
        self._operations = 0

    def _recent(self, key: str) -> deque[float]:
        """Los eventos de la clave que siguen dentro de la ventana."""
        self._operations += 1
        if self._operations % _SWEEP_EVERY == 0:
            for stale in [k for k in self._events if k != key]:
                self._discard_expired(stale)
        return self._discard_expired(key)

    def _discard_expired(self, key: str) -> deque[float]:
        events = self._events.get(key)
        if events is None:
            return deque()
        threshold = self._clock() - self._window
        while events and events[0] <= threshold:
            events.popleft()
        if not events:
            del self._events[key]
        return events

    def check(self, key: str) -> None:
        """Lanza TooManyRequestsError si la clave ya agotó su cupo. No registra nada."""
        events = self._recent(key)
        if len(events) >= self._limit:
            retry_after = ceil(events[0] + self._window - self._clock())
            raise TooManyRequestsError(retry_after=max(retry_after, 1))

    def record(self, key: str) -> None:
        self._recent(key)
        self._events.setdefault(key, deque()).append(self._clock())

    def hit(self, key: str) -> None:
        """check + record: cuenta el evento solo si todavía hay cupo."""
        self.check(key)
        self.record(key)

    def reset(self, key: str) -> None:
        self._events.pop(key, None)

    def clear(self) -> None:
        self._events.clear()
