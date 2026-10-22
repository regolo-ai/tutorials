"""Offline unit tests for Regolo Memory Studio (memory_wizard/server.py)."""
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import server as S

PRICES = {"brick-complexity-pro": {"in": 0.10, "out": 0.40}, "qwen3.5-122b": {"in": 1.00, "out": 4.20}}
MEM_JSON = json.dumps({
    "modules": [{"id": f"m{i}", "path": f"src/mod_{i}.py", "role": "Core", "invariant": "Ed25519 verified"} for i in range(4)],
    "decisions": [{"id": "d0", "status": "LOCKED", "rule": "Keep WAL synchronous=NORMAL"}],
})
HANDOFF_MD = "## Handoff Brief\n" + "word " * 60


class FakeChat:
    def __init__(self, bad_router=False):
        self.calls = []
        self.bad_router = bad_router

    def __call__(self, key, model, system, user, max_tokens):
        self.calls.append((model, len(user)))
        if self.bad_router and model == S.ROUTER_MODEL:
            return {"content": "{truncated", "prompt_tokens": 20, "completion_tokens": 900, "total_tokens": 920, "latency_s": 0.8}
        content = MEM_JSON if "memory consolidator" in system else HANDOFF_MD
        return {"content": content, "prompt_tokens": len(user) // 4, "completion_tokens": 120, "total_tokens": len(user) // 4 + 120, "latency_s": 0.9}


def sample_files():
    return [
        {"path": "src/auth.py", "content": "# comment\n" * 40 + "API_SECRET = 'sk-1234567890abcdef'\nJWT_LEEWAY = 45\n" + "x = 1\n" * 120},
        {"path": "src/wal.py", "content": "# comment\n" * 40 + "WAL_PAGES = 1000\n" * 80},
    ]


class MemoryStudioTests(unittest.TestCase):
    def test_scan_redacts_secrets_and_compresses(self):
        comp = S.scan_uploaded(sample_files(), "proj", compact=True)
        full = S.scan_uploaded(sample_files(), "proj", compact=False)
        self.assertIn("<redacted>", comp["skeleton_text"])
        self.assertNotIn("sk-1234567890abcdef", comp["skeleton_text"])
        self.assertNotIn("sk-1234567890abcdef", full["skeleton_text"])
        self.assertGreater(full["compact_chars"], 2 * comp["compact_chars"])

    def test_routed_consolidation_and_retry(self):
        S.chat = FakeChat(bad_router=False)
        r = S.execute_run("k", "qwen3.5-122b", "01", "proj", {"files": sample_files()}, True, True, lambda *_: None)
        self.assertEqual([s["model"] for s in r["stages"]], ["brick-complexity-pro", "qwen3.5-122b"])
        self.assertFalse(r["router_retry"])

        S.chat = FakeChat(bad_router=True)
        r2 = S.execute_run("k", "qwen3.5-122b", "01", "proj", {"files": sample_files()}, True, True, lambda *_: None)
        self.assertTrue(r2["router_retry"])
        self.assertEqual([s["stage"] for s in r2["stages"]][:2], ["Consolidate wiki index", "Consolidate wiki index (retry)"])


if __name__ == "__main__":
    unittest.main()
