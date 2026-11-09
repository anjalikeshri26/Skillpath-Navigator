"""In-process sliding-window limiter. Good enough for one API worker; use Redis or a gateway when scaling out."""
import threading
import time
from collections import defaultdict, deque


class SlidingWindowLimiter:
    def __init__(self, max_events: int, window_seconds: float):
        self.max_events = max_events
        self.window = window_seconds
        self._events: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def _prune(self, key: str, now: float) -> deque:
        events = self._events[key]
        while events and now - events[0] > self.window:
            events.popleft()
        return events

    def retry_after(self, key: str) -> float:
        """Seconds until another attempt is allowed; 0 when the key is not limited."""
        now = time.monotonic()
        with self._lock:
            events = self._prune(key, now)
            if len(events) < self.max_events:
                return 0.0
            return max(0.0, self.window - (now - events[0]))

    def hit(self, key: str) -> None:
        with self._lock:
            self._events[key].append(time.monotonic())

    def reset(self, key: str) -> None:
        with self._lock:
            self._events.pop(key, None)
