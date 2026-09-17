"""
Benchmark Task 01: Sliding Window Rate Limiter
"""
import time
from typing import Dict, List

class SlidingWindowRateLimiter:
    def __init__(self, max_requests: int, window_seconds: float):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.history: Dict[str, List[float]] = {}

    def allow_request(self, client_id: str, current_timestamp: float = None) -> bool:
        if current_timestamp is None:
            current_timestamp = time.time()
        timestamps = self.history.get(client_id, [])
        cutoff = current_timestamp - self.window_seconds
        timestamps = [t for t in timestamps if t > cutoff]
        if len(timestamps) >= self.max_requests:
            return False
        timestamps.append(current_timestamp)
        self.history[client_id] = timestamps
        return True
