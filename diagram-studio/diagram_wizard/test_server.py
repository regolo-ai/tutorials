"""Offline tests for the parts of server.py where a mistake would be silent. Run: python3 -m unittest diagram_wizard/test_server.py
(no network: Regolo calls are replaced by a fake)."""
import json, os, subprocess, sys, tempfile, unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import server as S

PRICES = {"brick-complexity-pro": {"in": 0.10, "out": 0.40}, "qwen3.5-122b": {"in": 1.00, "out": 4.20}}
TOPO = json.dumps({"nodes": [{"id": f"a{i}", "label": f"Svc{i}", "role": "Service", "detail": "x"} for i in range(5)],
                   "edges": [{"from": "a0", "to": "a1", "protocol": "http"}]})
LONG_SECTION = "## Summary\n" + "word " * 80


class Fake:
    """Stands in for S.chat; records which model and how many prompt characters each stage got."""
    def __init__(self, fail_router=False, bad_router_json=False):
        self.calls, self.fail_router, self.bad_router_json = [], fail_router, bad_router_json

    def __call__(self, key, model, system, user, max_tokens):
        if self.fail_router and model == S.ROUTER_MODEL:
            raise S.UserError("model not available")
        self.calls.append((model, len(user)))
        if self.bad_router_json and model == S.ROUTER_MODEL and "topology extractor" in system:
            self.calls.append((model, len(user)))
            return {"content": TOPO[:60], "prompt_tokens": 10, "completion_tokens": 900, "total_tokens": 910, "latency_s": 1.0}  # truncated JSON
        content = TOPO if "topology extractor" in system else ("<svg>" if "SVG engine" in system else LONG_SECTION)
        return {"content": content, "prompt_tokens": len(user) // 4, "completion_tokens": 100, "total_tokens": len(user) // 4 + 100, "latency_s": 1.0}


def project_files():
    code = "# comment\n" * 30 + "services:\n  api_key: sk-live-SECRET123\n  web:\n    image: x\n" + "x: 1\n" * 200
    return [{"path": "docker-compose.yml", "content": code}, {"path": "app/main.py", "content": "# c\nimport os\nTOKEN = 'abc'\n" * 40}]


class Costs(unittest.TestCase):
    def test_cost_known_and_unknown(self):
        self.assertAlmostEqual(S.cost_eur("qwen3.5-122b", 1_000_000, 1_000_000, PRICES), 5.20)
        self.assertAlmostEqual(S.cost_eur("brick-complexity-pro", 10_000, 1_000, PRICES), 0.0014)
        self.assertIsNone(S.cost_eur("some-other-model", 10, 10, PRICES))

    def test_totals_unpriced_model_gives_no_total(self):
        st = [{"model": "a", "prompt_tokens": 10, "completion_tokens": 5, "latency_s": 1.0, "cost_eur": 0.1},
              {"model": "b", "prompt_tokens": 10, "completion_tokens": 5, "latency_s": 2.0, "cost_eur": None}]
        t = S.totals_of(st, 3.3)
        self.assertEqual((t["total_tokens"], t["latency_s"], t["cost_eur"], t["unpriced_models"]), (30, 3.0, None, ["b"]))

    def test_pct_change(self):
        self.assertEqual(S.pct_change(200, 50), -75.0)
        self.assertIsNone(S.pct_change(0, 5)); self.assertIsNone(S.pct_change(5, None))


class Scan(unittest.TestCase):
    def test_compact_drops_comments_and_redacts(self):
        c = S.scan_uploaded(project_files(), "p", compact=True)
        self.assertNotIn("# comment", c["skeleton_text"]); self.assertNotIn("SECRET123", c["skeleton_text"])
        self.assertIn("api_key: <redacted>", c["skeleton_text"])

    def test_full_keeps_text_but_still_redacts(self):
        f, c = S.scan_uploaded(project_files(), "p", compact=False), S.scan_uploaded(project_files(), "p", compact=True)
        self.assertGreater(f["compact_chars"], 3 * c["compact_chars"])
        self.assertNotIn("SECRET123", f["skeleton_text"]); self.assertNotIn("'abc'", f["skeleton_text"])


class Routing(unittest.TestCase):
    def run_it(self, routed, compact, fake):
        S.chat = fake
        info = {"files": project_files()}
        return S.execute_run("k", "qwen3.5-122b", "01", "p", info, routed, compact, lambda *_: None)

    def test_routed_sends_extraction_to_router_and_rest_to_model(self):
        f = Fake(); r = self.run_it(True, True, f)
        self.assertEqual([m for m, _ in f.calls], [S.ROUTER_MODEL, "qwen3.5-122b", "qwen3.5-122b"])
        self.assertEqual([s["stage"] for s in r["stages"]], ["Extract components", "Draw the diagram", "Write the knowledge base"])
        self.assertFalse(r["router_fallback"]); self.assertEqual(r["svg_source"], "fallback")  # fake svg is rejected: layout builder used

    def test_single_uses_one_model(self):
        f = Fake(); self.run_it(False, True, f)
        self.assertEqual({m for m, _ in f.calls}, {"qwen3.5-122b"})

    def test_router_failure_falls_back_to_chosen_model(self):
        f = Fake(fail_router=True); r = self.run_it(True, True, f)
        self.assertTrue(r["router_fallback"]); self.assertEqual(r["stages"][0]["model"], "qwen3.5-122b")

    def test_unusable_router_json_is_retried_on_the_chosen_model(self):
        f = Fake(bad_router_json=True); r = self.run_it(True, True, f)
        self.assertTrue(r["router_retry"]); self.assertEqual(r["topology_source"], "model")
        self.assertEqual([s["stage"] for s in r["stages"]][:2], ["Extract components", "Extract components (retry)"])
        self.assertEqual(r["stages"][1]["model"], "qwen3.5-122b")

    def test_baseline_sends_more_than_optimized(self):
        base = self.run_it(False, False, Fake()); opt = self.run_it(True, True, Fake())
        self.assertGreater(base["totals"]["prompt_tokens"], 2 * opt["totals"]["prompt_tokens"])
        self.assertGreater(base["scan"]["sent_chars"], opt["scan"]["sent_chars"])


class GitignoreRules(unittest.TestCase):
    def make(self, git: bool):
        d = Path(tempfile.mkdtemp())
        for rel, body in {".gitignore": "ignored_dir/\n*.sql\n!keep.sql\n/data/*.json\nsub/**/secret_*.py\n*.log\n", "docker-compose.yml": "services: {}\n",
                          "src/main.py": "x=1\n", "ignored_dir/a.py": "x", "schema.sql": "x", "keep.sql": "x", "data/d.json": "{}",
                          "sub/deep/secret_a.py": "x", "sub/deep/ok.py": "x", "run.log": "x", ".env": "K=1"}.items():
            (d / rel).parent.mkdir(parents=True, exist_ok=True); (d / rel).write_text(body)
        if git:
            subprocess.run(["git", "-C", str(d), "init", "-q"], check=True)
        return d

    def check(self, git):
        r = S.inspect_project(str(self.make(git)))
        self.assertEqual(sorted(r["selected"]), ["docker-compose.yml", "keep.sql", "src/main.py", "sub/deep/ok.py"])
        return r["mode"]

    def test_parser_fallback(self): self.assertEqual(self.check(False), ".gitignore files")
    def test_git_mode(self): self.assertEqual(self.check(True), "git")


if __name__ == "__main__":
    unittest.main()
