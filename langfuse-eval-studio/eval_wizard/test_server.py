#!/usr/bin/env python3
"""Unit tests for Regolo Eval Studio (regolo_eval_tui.py and eval_wizard/server.py)."""
import json
import threading
import unittest
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch

import sys
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE))

import regolo_eval_tui as T
import server as S


class TestRegoloEvalStudio(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.httpd = ThreadingHTTPServer(("127.0.0.1", 0), S.Handler)
        cls.port = cls.httpd.server_address[1]
        cls.thread = threading.Thread(target=cls.httpd.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.httpd.shutdown()
        cls.httpd.server_close()

    def test_01_corpus_and_cost_math(self):
        items = T.load_corpus()
        self.assertEqual(len(items), 20)
        c_gemma = T.compute_costs("gemma4-31b", 500, 200)
        c_qwen = T.compute_costs("qwen3.8-27b", 500, 200)
        c_glm = T.compute_costs("glm5.2", 500, 200)
        self.assertAlmostEqual(c_gemma["payg_eur"], 0.00062, places=6)
        self.assertAlmostEqual(c_qwen["payg_eur"], 0.00067, places=6)
        self.assertAlmostEqual(c_glm["payg_eur"], 0.00204, places=6)
        self.assertAlmostEqual(c_gemma["core_eur"], 0.0000455, places=7)

    def test_02_evaluators(self):
        self.assertEqual(T.exact_fact_evaluator("Up to 20 million tokens per day.", "20 million"), 1.0)
        self.assertEqual(T.exact_fact_evaluator("Up to 50 million tokens.", "20 million"), 0.0)
        self.assertEqual(T.parse_judge_score("1"), 1.0)
        self.assertEqual(T.parse_judge_score("0"), 0.0)

    def test_03_http_index_and_dataset(self):
        with urllib.request.urlopen(f"http://127.0.0.1:{self.port}/") as r:
            html = r.read().decode("utf-8")
            self.assertEqual(r.status, 200)
            self.assertIn("Eval Studio", html)
        with urllib.request.urlopen(f"http://127.0.0.1:{self.port}/api/dataset") as r:
            data = json.loads(r.read().decode("utf-8"))
            self.assertEqual(len(data["items"]), 20)

    @patch("regolo_eval_tui.fetch_regolo_models", return_value=["gemma4-31b", "qwen3.8-27b", "glm5.2", "gpt-oss-120b"])
    @patch("regolo_eval_tui.call_regolo_chat")
    def test_04_end_to_end_evaluation_job(self, mock_chat, mock_models):
        def fake_chat(base_url, api_key, model, system_prompt, user_prompt, max_tokens=512, reasoning_effort=None):
            if "Reply with 1" in system_prompt:
                return {"content": "1", "reasoning": "", "prompt_tokens": 120, "completion_tokens": 2, "reasoning_tokens": 0, "total_tokens": 122, "latency_s": 0.15}
            return {
                "content": "The Regolo Core plan includes up to 600 million tokens per month and 20 million tokens per day at 11.70 euro promo.",
                "reasoning": "",
                "prompt_tokens": 500,
                "completion_tokens": 200,
                "reasoning_tokens": 0,
                "total_tokens": 700,
                "latency_s": 0.42,
            }

        mock_chat.side_effect = fake_chat

        req = urllib.request.Request(
            f"http://127.0.0.1:{self.port}/api/models",
            data=json.dumps({"api_key": "sk-test-key"}).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req) as r:
            mdata = json.loads(r.read().decode("utf-8"))
            self.assertIn("gemma4-31b", mdata["models"])

        req_eval = urllib.request.Request(
            f"http://127.0.0.1:{self.port}/api/evaluate",
            data=json.dumps({
                "api_key": "sk-test-key",
                "model": "gemma4-31b",
                "judge_model": "gemma4-31b",
                "mode": "single",
                "sample_count": 3,
                "threshold": 0.85,
            }).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req_eval) as r:
            j = json.loads(r.read().decode("utf-8"))
            job_id = j["job_id"]

        for _ in range(20):
            with urllib.request.urlopen(f"http://127.0.0.1:{self.port}/api/jobs/{job_id}") as r:
                st = json.loads(r.read().decode("utf-8"))
                if st["status"] == "done":
                    run = st["result"]["runs"][0]
                    self.assertTrue(run["ci_passed"])
                    self.assertEqual(run["items_count"], 3)
                    self.assertEqual(run["avg_faithfulness"], 1.0)
                    return
            import time
            time.sleep(0.05)
        self.fail("Evaluation job did not complete in time")


if __name__ == "__main__":
    unittest.main()
