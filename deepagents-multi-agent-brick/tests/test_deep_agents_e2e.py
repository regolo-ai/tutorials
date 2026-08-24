"""End-to-End Test for Deep Agents Multi-Agent Orchestration."""

import pytest
from core.orchestrator import DeepAgentOrchestrator
from core.sandbox import SandboxEnvironment
import config


def test_deep_agents_e2e_pipeline():
    sample_path = config.SAMPLE_REPOS_DIR / "ai_tool_nexus"
    sandbox = SandboxEnvironment(source_repo_path=str(sample_path))
    orchestrator = DeepAgentOrchestrator()

    logs = []
    def log_collector(agent, msg):
        logs.append(f"[{agent}] {msg}")

    result = orchestrator.run_pipeline(
        sandbox=sandbox,
        goal="Synthesize typed FastMCP tool server from raw APIs",
        log_callback=log_collector,
        human_approval_callback=None,
    )

    assert result["status"] == "SUCCESS"
    assert result["duration_sec"] > 0
    assert "planner" in result["results"]
    assert "researcher" in result["results"]
    assert "tool_agent" in result["results"]
    assert "code_executor" in result["results"]
    assert "reviewer" in result["results"]
    assert "report_writer" in result["results"]

    # Verify synthesized files exist in sandbox
    files = sandbox.list_files()
    assert any("mcp_server.py" in f for f in files)
    assert any("models.py" in f for f in files)

    # Verify telemetry savings
    telemetry = result["telemetry"]
    assert telemetry["total_tokens"] > 0
    assert telemetry["cost_savings_usd"] > 0
    assert telemetry["savings_percentage"] > 50.0

    sandbox.cleanup()


def test_deep_agents_assessment_pipeline():
    """Test pipeline execution with module assessment goal on current codebase."""
    sandbox = SandboxEnvironment(source_repo_path=str(config.BASE_DIR))
    orchestrator = DeepAgentOrchestrator()

    logs = []
    result = orchestrator.run_pipeline(
        sandbox=sandbox,
        goal="Analyze all the modules in this repo and create an assessment for me",
        log_callback=lambda a, m: logs.append(f"[{a}] {m}"),
        human_approval_callback=None,
    )

    assert result["status"] == "SUCCESS"
    report_file = result["report_file"]
    assert report_file is not None

    spec_content = config.HARNESS_OUTPUT_DIR.joinpath("HARNESS_SPEC.md").read_text(encoding="utf-8")
    assert "Tabella dei Moduli" in spec_content
    # Ensure multiple core modules are cataloged
    assert "main.py" in spec_content
    assert "tui.py" in spec_content or "config.py" in spec_content or "docker_manager.py" in spec_content
    assert "orchestrator.py" in spec_content or "brick_router.py" in spec_content

    sandbox.cleanup()
