"""Brick Semantic Router for Deep Agents on Regolo.ai.
Routes each sub-agent dynamically based on:
1. Sub-Agent Role & Profile
2. Task Semantic Complexity (evaluated via 'brick-complexity-pro')
3. Tool Availability & Capability Requirements
4. Residual Pipeline Budget & Token Burn Rate
5. Criticality & Escalation Trigger Gates
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

import config
from core.regolo_client import RegoloClient


@dataclass
class RoutingDecision:
    """Structured decision returned by Brick Semantic Router."""
    subagent_key: str
    role_name: str
    selected_model: str
    fallback_model: str
    router_model: str
    complexity_score: float
    routing_tier: str  # "FAST", "BALANCED", "REASONING", "DOWNSCALED", "ESCALATED"
    reasoning: str
    token_limit: int
    timeout_sec: int
    is_escalated: bool = False
    is_downscaled: bool = False
    criticality: str = "MEDIUM"
    allowed_tools: List[str] = field(default_factory=list)
    latency_sec: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "subagent_key": self.subagent_key,
            "role_name": self.role_name,
            "selected_model": self.selected_model,
            "fallback_model": self.fallback_model,
            "router_model": self.router_model,
            "complexity_score": self.complexity_score,
            "routing_tier": self.routing_tier,
            "reasoning": self.reasoning,
            "token_limit": self.token_limit,
            "timeout_sec": self.timeout_sec,
            "is_escalated": self.is_escalated,
            "is_downscaled": self.is_downscaled,
            "criticality": self.criticality,
            "allowed_tools": self.allowed_tools,
            "latency_sec": self.latency_sec,
        }


class BrickRouter:
    """The Brick Semantic Routing Engine for Multi-Agent Orchestration."""

    def __init__(self, client: Optional[RegoloClient] = None):
        self.client = client or RegoloClient()
        self.routing_history: List[RoutingDecision] = []

    def route_subagent(
        self,
        subagent_key: str,
        task_description: str,
        tools_requested: Optional[List[str]] = None,
        residual_budget: int = 25000,
        total_budget: int = 25000,
        force_escalate: bool = False,
    ) -> RoutingDecision:
        """Dynamically evaluate and route a sub-agent task to the optimal model."""
        profile = config.SUBAGENT_PROFILES.get(subagent_key, {
            "role_name": subagent_key.title(),
            "description": "General sub-agent task",
            "preferred_model": config.REGOLO_MODEL,
            "fallback_model": config.REGOLO_MODEL,
            "escalation_model": "qwen3.5-122b",
            "token_limit": 2500,
            "timeout_sec": 30,
            "allowed_tools": [],
            "escalation_threshold": 7.0,
            "criticality": "MEDIUM",
        })

        allowed_tools = tools_requested or profile.get("allowed_tools", [])
        budget_ratio = residual_budget / max(1, total_budget)
        criticality = profile.get("criticality", "MEDIUM")

        # 1. Ask 'brick-complexity-pro' meta-router for semantic complexity evaluation
        eval_res = self.client.evaluate_complexity(
            task_description=task_description,
            role=subagent_key,
            tools_requested=allowed_tools,
            current_budget_ratio=budget_ratio,
        )

        complexity_score = eval_res.get("complexity_score", 5.0)
        escalation_threshold = profile.get("escalation_threshold", 7.0)

        # 2. Dynamic Decision Engine
        is_escalated = False
        is_downscaled = False
        selected_model = profile["preferred_model"]
        routing_tier = "BALANCED"
        reasoning = ""

        # A. Check for budget exhaustion / downscale pressure
        if budget_ratio < (1.0 - config.BUDGET_WARNING_THRESHOLD) and criticality not in ("CRITICAL", "HIGH"):
            # Budget pressure: downscale low/medium priority sub-agents to economical model
            selected_model = config.normalize_model_name("gpt-oss-20b")
            routing_tier = "DOWNSCALED"
            is_downscaled = True
            reasoning = f"Budget pressure ({int(budget_ratio*100)}% remaining): Brick downscaled {profile['role_name']} to {selected_model} to preserve tokens."

        # B. Check for escalation condition (criticality, failure retry, or high complexity)
        elif force_escalate or (complexity_score >= escalation_threshold and config.ENABLE_DYNAMIC_ESCALATION):
            selected_model = config.normalize_model_name(profile.get("escalation_model", "qwen3.5-122b"))
            routing_tier = "ESCALATED"
            is_escalated = True
            reasoning = f"Complexity threshold exceeded ({complexity_score:.1f} >= {escalation_threshold:.1f}): Brick escalated {profile['role_name']} to deep reasoning model {selected_model}."

        # C. Standard profile match with brick-complexity-pro recommendation
        else:
            rec_model = eval_res.get("recommended_model", profile["preferred_model"])
            rec_tier = eval_res.get("recommended_tier", "BALANCED")
            selected_model = config.normalize_model_name(rec_model)
            routing_tier = rec_tier
            reasoning = eval_res.get("routing_reasoning", f"Brick routed {profile['role_name']} to {selected_model} based on role fit and complexity {complexity_score:.1f}/10.")

        decision = RoutingDecision(
            subagent_key=subagent_key,
            role_name=profile["role_name"],
            selected_model=config.normalize_model_name(selected_model),
            fallback_model=config.normalize_model_name(profile.get("fallback_model", config.REGOLO_MODEL)),
            router_model=config.normalize_model_name(eval_res.get("router_model", config.MODEL_BRICK_ROUTER)),
            complexity_score=complexity_score,
            routing_tier=routing_tier,
            reasoning=reasoning,
            token_limit=profile.get("token_limit", 2500),
            timeout_sec=profile.get("timeout_sec", 30),
            is_escalated=is_escalated,
            is_downscaled=is_downscaled,
            criticality=criticality,
            allowed_tools=allowed_tools,
            latency_sec=eval_res.get("latency_sec", 0.1),
        )

        self.routing_history.append(decision)
        return decision

    def get_routing_matrix(self) -> List[Dict[str, Any]]:
        """Return the baseline routing matrix for all registered sub-agents."""
        matrix = []
        for key, p in config.SUBAGENT_PROFILES.items():
            matrix.append({
                "subagent_key": key,
                "role_name": p["role_name"],
                "preferred_model": p["preferred_model"],
                "fallback_model": p["fallback_model"],
                "escalation_model": p.get("escalation_model", "qwen3.5-122b"),
                "token_limit": p["token_limit"],
                "timeout_sec": p["timeout_sec"],
                "escalation_threshold": p["escalation_threshold"],
                "criticality": p["criticality"],
                "allowed_tools": p["allowed_tools"],
            })
        return matrix
