#!/usr/bin/env python3
"""Main Entrypoint for Regolo.ai + Cognee Long-Term Memory Suite.
Supports interactive TUI mode and automated headless CLI workflows.
"""

import argparse
import json
import sys
import time
from pathlib import Path

import config
from core.agent_loop import CodingAgentLoop
from core.cognee_engine import CogneeMemoryEngine
from core.docker_manager import get_services_status, start_all_services, stop_all_services
from core.env_checker import run_full_setup
from tui import run_tui


def main():
    parser = argparse.ArgumentParser(
        description="Regolo.ai + Cognee Long-Term Memory Suite for Coding Agents"
    )
    parser.add_argument("--demo", action="store_true", help="Execute the Naive RAG vs Cognee Memory benchmark directly")
    parser.add_argument("--react-demo", action="store_true", help="Execute Feature Implementation & CI Self-Healing ReAct mini-loop with live pytest")
    parser.add_argument("--timeline-demo", action="store_true", help="Execute Multi-Session Timeline learning demo (Day 1 -> Day 2 -> Day 15)")
    parser.add_argument("--causal-demo", action="store_true", help="Execute Causal Trail Multi-Hop Knowledge Graph traversal demo")
    parser.add_argument("--setup", action="store_true", help="Run full environment setup non-interactively")
    parser.add_argument("--services", choices=["start", "stop", "status"], help="Manage Docker background services")
    parser.add_argument("--cognify", type=str, help="Index a custom codebase path into Cognee memory graph")
    parser.add_argument("--recall", type=str, help="Query long-term memory graph for architectural context")
    parser.add_argument("--graph-summary", action="store_true", help="Print topological summary and Cognee Web UI link")
    parser.add_argument("--view-graph", action="store_true", help="Generate and open the interactive visual knowledge graph in browser")

    args = parser.parse_args()

    if args.setup:
        print("⚡ Running Environment Setup...")
        res = run_full_setup()
        for k, (ok, msg) in res.items():
            print(f"[{'OK' if ok else 'FAIL'}] {k}: {msg}")
        return

    if args.services:
        if args.services == "status":
            stat = get_services_status()
            print(json.dumps(stat, indent=2))
        elif args.services == "start":
            res = start_all_services()
            print("Started services:", res)
        elif args.services == "stop":
            res = stop_all_services()
            print("Stopped services:", res)
        return

    if args.cognify:
        target = Path(args.cognify).resolve()
        engine = CogneeMemoryEngine()
        res = engine.cognify_codebase(target)
        print("Cognify Result:", json.dumps(res, indent=2))
        return

    if args.recall:
        engine = CogneeMemoryEngine()
        res = engine.recall_memory(args.recall)
        print(res["memory_prompt_block"])
        return

    if args.graph_summary:
        engine = CogneeMemoryEngine()
        summary = engine.get_graph_summary()
        ui_info = engine.get_web_ui_url()
        html_file = engine.generate_visual_html_graph()
        output = {
            "summary": summary,
            "cognee_web_ui": ui_info,
            "visual_html_graph": str(html_file),
            "edges": engine.get_formatted_edge_list(),
        }
        print(json.dumps(output, indent=2))
        return

    if args.view_graph:
        import http.server
        import socketserver
        import time
        import webbrowser
        from core.docker_manager import find_available_port

        engine = CogneeMemoryEngine()
        html_file = engine.generate_visual_html_graph()
        port = find_available_port(8850)
        url = f"http://127.0.0.1:{port}/"

        print("=" * 70)
        print("⚡ REGOLO.AI + COGNEE • KNOWLEDGE GRAPH LIVE SERVER")
        print("=" * 70)
        print(f"📁 Serving File:      {html_file.name}")
        print(f"🌐 Local Web URL:     \033[1;32m{url}\033[0m")
        print(f"🛑 Terminate Server:  Press \033[1;33mCTRL+C\033[0m to stop")
        print("=" * 70)
        print(f"[{time.strftime('%H:%M:%S')}] 🟢 Server active on port {port}. Opening browser...\n")

        try:
            webbrowser.open(url)
        except Exception:
            pass

        class GraphServerHandler(http.server.SimpleHTTPRequestHandler):
            def __init__(self, *a, **kw):
                super().__init__(*a, directory=str(config.DATA_DIR), **kw)

            def do_GET(self):
                clean_p = self.path.split("?")[0].split("#")[0]
                if clean_p in ["", "/", "/index.html", "/visualizer", "/graph"]:
                    self.path = "/knowledge_graph_visualizer.html"
                elif clean_p.startswith("/data/"):
                    self.path = clean_p.replace("/data/", "/", 1)
                elif clean_p == "/favicon.ico":
                    self.send_response(204)
                    self.end_headers()
                    return
                return super().do_GET()

            def handle(self):
                try:
                    super().handle()
                except (ConnectionResetError, BrokenPipeError, TimeoutError, OSError):
                    pass

            def log_message(self, format_str, *args_log):
                sys.stdout.write(f"[{time.strftime('%H:%M:%S')}] 🌐 {self.address_string()} - {format_str % args_log}\n")
                sys.stdout.flush()

        class ThreadingGraphServer(socketserver.ThreadingMixIn, http.server.HTTPServer):
            daemon_threads = True
            allow_reuse_address = True

        httpd = ThreadingGraphServer(("127.0.0.1", port), GraphServerHandler)
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print(f"\n[{time.strftime('%H:%M:%S')}] 🛑 Knowledge graph server stopped by user (CTRL+C). Goodbye!\n")
            httpd.shutdown()
            httpd.server_close()
            return

    if args.react_demo:
        agent_loop = CodingAgentLoop()
        res = agent_loop.run_react_self_healing_demo()
        print(json.dumps(res, indent=2))
        return

    if args.timeline_demo:
        agent_loop = CodingAgentLoop()
        res = agent_loop.run_multi_session_timeline_demo()
        print(json.dumps(res, indent=2))
        return

    if args.causal_demo:
        agent_loop = CodingAgentLoop()
        res = agent_loop.run_causal_trail_demo()
        print(json.dumps(res, indent=2))
        return

    if args.demo:
        agent_loop = CodingAgentLoop()
        task = "Add user search endpoint respecting tenant isolation and parameterized SQL queries"
        report = agent_loop.run_comparison_benchmark(task)
        print(json.dumps(report, indent=2))
        return

    # Default: launch interactive Rich Green TUI
    run_tui()


if __name__ == "__main__":
    main()
