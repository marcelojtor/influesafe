import time
from collections import deque, defaultdict

class SimpleRateLimiter:
    """
    Rate limiter simples em memória (processo único).
    - window_s: janela em segundos (ex.: 60)
    - max_requests: máx. requisições por janela
    - min_interval_s: intervalo mínimo entre req (ex.: 1.0)
    """
    def __init__(self, window_s: int = 60, max_requests: int = 6, min_interval_s: float = 1.0):
        self.window_s = window_s
        self.max_requests = max_requests
        self.min_interval_s = min_interval_s
        self.events = defaultdict(deque)
        self.last_call = {}

    def allow(self, key: str) -> bool:
        now = time.time()
        q = self.events[key]

        # Remove eventos fora da janela
        while q and (now - q[0]) > self.window_s:
            q.popleft()

        # Checa limites
        if q and (now - self.last_call.get(key, 0)) < self.min_interval_s:
            return False
        if len(q) >= self.max_requests:
            return False

        q.append(now)
        self.last_call[key] = now
        return True
