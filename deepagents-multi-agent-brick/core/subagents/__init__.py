"""Subagents package for Deep Agents Multi-Agent Orchestration."""

from core.subagents.base import BaseSubAgent, SubAgentResult
from core.subagents.browser_tool_agent import BrowserToolAgent
from core.subagents.code_executor import CodeExecutorSubAgent
from core.subagents.planner import PlannerSubAgent
from core.subagents.report_writer import ReportWriterSubAgent
from core.subagents.researcher import ResearcherSubAgent
from core.subagents.reviewer import ReviewerSubAgent

__all__ = [
    "BaseSubAgent",
    "SubAgentResult",
    "PlannerSubAgent",
    "ResearcherSubAgent",
    "BrowserToolAgent",
    "CodeExecutorSubAgent",
    "ReviewerSubAgent",
    "ReportWriterSubAgent",
]
