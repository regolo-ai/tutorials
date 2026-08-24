"""Tests for Deep Agent Sub-Agents."""

import pytest
from core.sandbox import SandboxEnvironment
from core.subagents.browser_tool_agent import BrowserToolAgent
from core.subagents.code_executor import CodeExecutorSubAgent
from core.subagents.planner import PlannerSubAgent
from core.subagents.report_writer import ReportWriterSubAgent
from core.subagents.researcher import ResearcherSubAgent
from core.subagents.reviewer import ReviewerSubAgent
import config


@pytest.fixture
def test_sandbox():
    sample_path = config.SAMPLE_REPOS_DIR / "ai_tool_nexus"
    sb = SandboxEnvironment(source_repo_path=str(sample_path))
    yield sb
    sb.cleanup()


def test_planner_subagent(test_sandbox):
    planner = PlannerSubAgent()
    res = planner.run(sandbox=test_sandbox, context={"goal": "Synthesize MCP Tools"})
    assert res.status == "SUCCESS"
    assert "steps" in res.structured_data
    assert len(res.structured_data["steps"]) >= 4
    assert res.tokens_used > 0


def test_researcher_subagent(test_sandbox):
    researcher = ResearcherSubAgent()
    res = researcher.run(sandbox=test_sandbox, context={})
    assert res.status == "SUCCESS"
    assert "endpoints_analyzed" in res.structured_data
    assert len(res.structured_data["endpoints_analyzed"]) > 0


def test_browser_tool_agent(test_sandbox):
    tool_agent = BrowserToolAgent()
    context = {
        "researcher_output": {
            "endpoints_analyzed": [{"name": "vector_search", "parameters": {"query": "str"}}]
        }
    }
    res = tool_agent.run(sandbox=test_sandbox, context=context)
    assert res.status == "SUCCESS"
    assert "probed_results" in res.structured_data


def test_code_executor_subagent(test_sandbox):
    executor = CodeExecutorSubAgent()
    context = {
        "researcher_output": {"endpoints_analyzed": []},
        "tool_agent_output": {"probed_results": []},
    }
    res = executor.run(sandbox=test_sandbox, context=context)
    assert res.status == "SUCCESS"
    assert len(res.artifacts_created) > 0
    assert test_sandbox.read_file("harness/mcp_server.py") is not None


def test_reviewer_subagent(test_sandbox):
    reviewer = ReviewerSubAgent()
    context = {
        "code_executor_output": {
            "files": {"harness/mcp_server.py": "class DeepAgentMCPServer: pass"},
            "test_results": {"passed": True},
        }
    }
    res = reviewer.run(sandbox=test_sandbox, context=context)
    assert res.status == "SUCCESS"
    assert "harness_score" in res.structured_data
    assert res.structured_data["harness_score"] > 80


def test_report_writer_subagent(test_sandbox):
    writer = ReportWriterSubAgent()
    context = {
        "planner_output": {"target_goal": "MCP Tool Harness"},
        "researcher_output": {},
        "code_executor_output": {"tools_synthesized": ["tool_1"]},
        "reviewer_output": {"harness_score": 98.0, "checks": []},
    }
    res = writer.run(sandbox=test_sandbox, context=context)
    assert res.status == "SUCCESS"
    assert len(res.artifacts_created) > 0
