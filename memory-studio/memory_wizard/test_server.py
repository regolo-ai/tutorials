"""Offline unit tests for Regolo Memory Studio (memory_wizard/server.py)."""
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import server as S

WIKI_JSON = json.dumps({
    "decisions": [{"slug": "adr-01-ed25519", "title": "Ed25519 Assertion", "summary": "Keep leeway=45s"}],
    "procedures": [{"slug": "proc-wal", "title": "SQLite WAL", "summary": "Keep synchronous=NORMAL"}],
    "failed_approaches": ["Do not set synchronous=OFF"],
    "open_questions": ["Verify daily pool threshold"],
})
HANDOFF_MD = "## Where We Left Off\n" + "word " * 50


class FakeChat:
    def __init__(self, bad_router=False):
        self.calls = []
        self.bad_router = bad_router

    def __call__(self, key, model, system, user, max_tokens):
        self.calls.append((model, len(user)))
        if self.bad_router and model == S.ROUTER_MODEL:
            return {"content": "{broken", "prompt_tokens": 20, "completion_tokens": 900, "total_tokens": 920, "latency_s": 0.8}
        content = WIKI_JSON if "consolidation worker" in system else HANDOFF_MD
        return {"content": content, "prompt_tokens": len(user) // 4, "completion_tokens": 110, "total_tokens": len(user) // 4 + 110, "latency_s": 0.9}


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
        r = S.execute_run("k", "qwen3.5-122b", "claude-to-opencode", "proj", {"files": sample_files()}, True, True, lambda *_: None)
        self.assertEqual([s["model"] for s in r["stages"]], ["brick-complexity-pro", "qwen3.5-122b"])
        self.assertFalse(r["router_retry"])
        self.assertIn("wiki/decisions/adr-01-ed25519.md", r["html"])
        self.assertIn("AI_MEMORY_LLM_COMPAT_DISABLE_THINKING", r["html"])

        S.chat = FakeChat(bad_router=True)
        r2 = S.execute_run("k", "qwen3.5-122b", "claude-to-opencode", "proj", {"files": sample_files()}, True, True, lambda *_: None)
        self.assertTrue(r2["router_retry"])
        self.assertEqual([s["stage"] for s in r2["stages"]][:2], ["Consolidate wiki pages", "Consolidate wiki pages (retry)"])


if __name__ == "__main__":
    unittest.main()
