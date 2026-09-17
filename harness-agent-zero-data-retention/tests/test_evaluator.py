from regolo_agent_stack.evaluator import evaluate_code

def test_evaluator_passes_good_code():
    code = (
        "class SlidingWindowRateLimiter:\n"
        "    def __init__(self, max_requests, window_seconds):\n"
        "        self.max_requests=max_requests\n"
        "        self.window_seconds=window_seconds\n"
        "        self.history={}\n"
        "    def allow_request(self, client_id, current_timestamp=None):\n"
        "        import time\n"
        "        if current_timestamp is None:\n"
        "            current_timestamp=time.time()\n"
        "        timestamps=[t for t in self.history.get(client_id, []) if t>current_timestamp-self.window_seconds]\n"
        "        if len(timestamps)>=self.max_requests:\n"
        "            return False\n"
        "        timestamps.append(current_timestamp)\n"
        "        self.history[client_id]=timestamps\n"
        "        return True\n"
    )
    res = evaluate_code(code)
    assert res["success"] is True
