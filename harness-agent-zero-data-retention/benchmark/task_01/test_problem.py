import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from problem import SlidingWindowRateLimiter

def test_single_client_allows_up_to_limit():
    limiter = SlidingWindowRateLimiter(max_requests=3, window_seconds=10.0)
    t = 100.0
    assert limiter.allow_request("user_1", current_timestamp=t) is True
    assert limiter.allow_request("user_1", current_timestamp=t + 1) is True
    assert limiter.allow_request("user_1", current_timestamp=t + 2) is True
    assert limiter.allow_request("user_1", current_timestamp=t + 3) is False

def test_sliding_window_eviction():
    limiter = SlidingWindowRateLimiter(max_requests=2, window_seconds=5.0)
    assert limiter.allow_request("user_2", current_timestamp=10.0) is True
    assert limiter.allow_request("user_2", current_timestamp=12.0) is True
    assert limiter.allow_request("user_2", current_timestamp=14.0) is False
    assert limiter.allow_request("user_2", current_timestamp=15.1) is True

def test_multiple_clients_isolated():
    limiter = SlidingWindowRateLimiter(max_requests=1, window_seconds=5.0)
    assert limiter.allow_request("alice", current_timestamp=1.0) is True
    assert limiter.allow_request("bob", current_timestamp=1.0) is True
    assert limiter.allow_request("alice", current_timestamp=2.0) is False
    assert limiter.allow_request("bob", current_timestamp=2.0) is False
