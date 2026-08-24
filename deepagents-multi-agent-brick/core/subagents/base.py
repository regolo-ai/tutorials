"""Base SubAgent class for Deep Agents Orchestration on Regolo.ai."""

import json
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

import config
from core.brick_router import BrickRouter, RoutingDecision
from core.budget_controller import BudgetController, get_budget_controller
from core.regolo_client import RegoloClient
from core.sandbox import SandboxEnvironment

logger = logging.getLogger(__name__)


@dataclass
class SubAgentResult:
    """Standardized output from any Deep Agent sub-agent execution."""
    subagent_key: str
    role_name: str
    status: str  # "SUCCESS", "FAILED", "ESCALATED"
    output_text: str
    structured_data: Dict[str, Any]
    routing_decision: RoutingDecision
    tokens_used: int
    prompt_tokens: int
    completion_tokens: int
    latency_sec: float
    cost_regolo_usd: float
    cost_frontier_usd: float
    artifacts_created: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "subagent_key": self.subagent_key,
            "role_name": self.role_name,
            "status": self.status,
            "output_text": self.output_text,
            "structured_data": self.structured_data,
            "routing_decision": self.routing_decision.to_dict(),
            "tokens_used": self.tokens_used,
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "latency_sec": self.latency_sec,
            "cost_regolo_usd": self.cost_regolo_usd,
            "cost_frontier_usd": self.cost_frontier_usd,
            "artifacts_created": self.artifacts_created,
        }


class BaseSubAgent(ABC):
    """Abstract Base Class for all Deep Agent Sub-Agents."""

    def __init__(
        self,
        subagent_key: str,
        client: Optional[RegoloClient] = None,
        router: Optional[BrickRouter] = None,
        budget_controller: Optional[BudgetController] = None,
    ):
        self.subagent_key = subagent_key
        self.client = client or RegoloClient()
        self.router = router or BrickRouter(client=self.client)
        self.budget_controller = budget_controller or get_budget_controller()
        self.profile = config.SUBAGENT_PROFILES.get(subagent_key, {})

    @abstractmethod
    def run(
        self,
        sandbox: SandboxEnvironment,
        context: Dict[str, Any],
        log_callback: Optional[Callable[[str, str], None]] = None,
        force_escalate: bool = False,
    ) -> SubAgentResult:
        """Execute the sub-agent's primary task."""
        pass

    def _route_task(
        self,
        task_description: str,
        tools_requested: Optional[List[str]] = None,
        force_escalate: bool = False,
    ) -> RoutingDecision:
        """Evaluate task complexity and determine optimal model via Brick."""
        residual = self.budget_controller.get_residual_budget()
        decision = self.router.route_subagent(
            subagent_key=self.subagent_key,
            task_description=task_description,
            tools_requested=tools_requested or self.profile.get("allowed_tools", []),
            residual_budget=residual,
            total_budget=self.budget_controller.total_budget,
            force_escalate=force_escalate,
        )
        return decision

    def _execute_llm(
        self,
        decision: RoutingDecision,
        messages: List[Dict[str, str]],
        stage: str,
    ) -> Dict[str, Any]:
        """Execute LLM call and record telemetry in Budget Controller."""
        resp = self.client.chat_completion(
            model=decision.selected_model,
            messages=messages,
            temperature=self.profile.get("temperature", 0.2),
            max_tokens=decision.token_limit,
            timeout=decision.timeout_sec,
        )

        event = self.budget_controller.record_step(
            subagent_key=self.subagent_key,
            role_name=decision.role_name,
            model=resp["model"],
            stage=stage,
            prompt_tokens=resp["prompt_tokens"],
            completion_tokens=resp["completion_tokens"],
            latency_sec=resp["latency_sec"],
            routing_tier=decision.routing_tier,
            is_escalated=decision.is_escalated,
            is_downscaled=decision.is_downscaled,
        )

        return {
            "content": resp["content"],
            "event": event,
            "resp": resp,
        }

    def _parse_json_safely(self, text: str) -> Dict[str, Any]:
        """Extract and parse JSON object from markdown-fenced or raw response."""
        cleaned = text.strip()
        if "```json" in cleaned:
            cleaned = cleaned.split("```json")[1].split("```")[0].strip()
        elif "```" in cleaned:
            cleaned = cleaned.split("```")[1].split("```")[0].strip()
        try:
            return json.loads(cleaned)
        except Exception:
            return {}
