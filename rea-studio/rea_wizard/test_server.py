"""Offline unit tests for Regolo REA Studio (rea_wizard/server.py)."""
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import server as S

REA_JSON = json.dumps({
    "evidence": [{"id": f"e{i}", "symbol": f"ipc:sync:ch_{i}", "scope": "Main Process", "detail": "batch=250"} for i in range(4)],
})
SPEC_MD = "## Architecture & IPC Overview\n" + "word " * 60


class FakeChat:
    def __init__(self, bad_router=False):
        self.calls = []
        self.bad_router = bad_router

    def __call__(self, key, model, system, user, max_tokens):
        self.calls.append((model, len(user)))
        if self.bad_router and model == S.ROUTER_MODEL:
            return {"content": "{broken", "prompt_tokens": 20, "completion_tokens": 900, "total_tokens": 920, "latency_s": 0.7}
        content = REA_JSON if "evidence triage" in system else SPEC_MD
        return {"content": content, "prompt_tokens": len(user) // 4, "completion_tokens": 110, "total_tokens": len(user) // 4 + 110, "latency_s": 0.8}


def sample_dumps():
    ipc = json.dumps({
        "bundle": "app.asar",
        "ipc_channels": [{"channel": f"ui:hover_{i}", "scope": "renderer_ui"} for i in range(100)]
        + [{"channel": "ipc:vault:unlock", "scope": "preload_bridge"}],
    }, indent=2)
    return [{"path": "electron_ipc.json", "content": ipc}]


class ReaStudioTests(unittest.TestCase):
    def test_sieve_collapses_ui_channels(self):
        comp = S.scan_uploaded(sample_dumps(), "pos", compact=True)
        full = S.scan_uploaded(sample_dumps(), "pos", compact=False)
        self.assertIn("ipc:vault:unlock", comp["skeleton_text"])
        self.assertGreater(full["compact_chars"], 5 * comp["compact_chars"])

    def test_routed_triage_and_retry(self):
        S.chat = FakeChat(bad_router=False)
        r = S.execute_run("k", "qwen3.5-122b", "01", "pos", {"files": sample_dumps()}, True, True, lambda *_: None)
        self.assertEqual([s["model"] for s in r["stages"]], ["brick-complexity-pro", "qwen3.5-122b"])
        self.assertFalse(r["router_retry"])

        S.chat = FakeChat(bad_router=True)
        r2 = S.execute_run("k", "qwen3.5-122b", "01", "pos", {"files": sample_dumps()}, True, True, lambda *_: None)
        self.assertTrue(r2["router_retry"])
        self.assertEqual([s["stage"] for s in r2["stages"]][:2], ["Triage IPC & binary symbols", "Triage IPC & binary symbols (retry)"])


if __name__ == "__main__":
    unittest.main()
