"""Offline unit tests for Regolo REA Studio (rea_wizard/server.py)."""
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import server as S

REA_JSON = json.dumps({
    "evidence": [{"symbol": "ipc:vault:unlock", "surface": "Preload Bridge", "contract": "AES-256-GCM"}],
    "poc_endpoints": [{"route": "POST /api/v1/vault/unseal", "purpose": "Cloud replacement"}],
})
SPEC_MD = "## Extracted Feature & Evidence Summary\n" + "word " * 60


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
        r = S.execute_run("k", "qwen3.5-122b", "web-har-to-poc", "pos", {"files": sample_dumps()}, True, True, lambda *_: None)
        self.assertEqual([s["model"] for s in r["stages"]], ["brick-v1-beta", "qwen3.5-122b"])
        self.assertFalse(r["router_retry"])
        self.assertIn("REA_MCP_INPUT_SCHEMA_PROFILE", r["html"])

        S.chat = FakeChat(bad_router=True)
        r2 = S.execute_run("k", "qwen3.5-122b", "web-har-to-poc", "pos", {"files": sample_dumps()}, True, True, lambda *_: None)
        self.assertTrue(r2["router_retry"])
        self.assertEqual([s["stage"] for s in r2["stages"]][:2], ["Triage REA evidence dump", "Triage REA evidence dump (retry)"])

    def test_pick_folder_endpoint_registered(self):
        self.assertTrue(callable(getattr(S, "pick_folder", None)))


if __name__ == "__main__":
    unittest.main()
