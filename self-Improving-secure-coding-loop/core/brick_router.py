"""Brick Semantic Router for Closed-Loop Secure Coding Agent on Regolo.ai.
Dynamically routes each sub-agent / stage based on:
1. Sub-Agent Profile & Role Requirements
2. Task Semantic Complexity evaluated via 'brick-complexity-pro'
3. Residual Pipeline Token Budget & Burn Rate
4. Criticality & Zero-Trust Escalation Gates
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import config
from core.regolo_client import RegoloClient, normalize_model_name


@dataclass
class RoutingDecision:
    """Structured routing decision returned by Brick Semantic Router."""
    stage_key: str
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

    @property
    def subagent_key(self) -> str:
        return self.stage_key

    def to_dict(self) -> Dict[str, Any]:
        return {
            "stage_key": self.stage_key,
            "subagent_key": self.stage_key,
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
    """Semantic Routing Engine powered by 'brick-complexity-pro' on Regolo.ai."""

    def __init__(self, client: Optional[RegoloClient] = None):
        self.client = client or RegoloClient()
        self.routing_history: List[RoutingDecision] = []

    def route_stage(
        self,
        stage: str,
        task_description: str,
        files: Optional[List[str]] = None,
        tools_requested: Optional[List[str]] = None,
        residual_budget: int = 25000,
        total_budget: int = 25000,
        force_escalate: bool = False,
    ) -> RoutingDecision:
        """Dynamically evaluate and route a stage task to the optimal specialized model."""
        profile = config.SUBAGENT_PROFILES.get(stage, {
            "role_name": stage.replace("_", " ").title(),
            "description": f"Stage task for {stage}",
            "preferred_model": config.STAGE_CONFIGS.get(stage, {}).get("model", config.REGOLO_MODEL),
            "fallback_model": "glm5.2",
            "escalation_model": "qwen3.5-122b",
            "token_limit": config.STAGE_CONFIGS.get(stage, {}).get("max_tokens", 2048),
            "timeout_sec": 45,
            "escalation_threshold": config.ESCALATION_COMPLEXITY_THRESHOLD,
            "criticality": "MEDIUM",
            "allowed_tools": [],
        })

        allowed_tools = tools_requested or profile.get("allowed_tools", [])
        budget_ratio = residual_budget / max(1, total_budget)
        criticality = profile.get("criticality", "MEDIUM")

        # 1. Ask 'brick-complexity-pro' meta-router for semantic complexity evaluation
        eval_res = self.client.evaluate_complexity(
            task_description=task_description,
            role=profile["role_name"],
            tools_requested=allowed_tools,
            current_budget_ratio=budget_ratio,
        )

        complexity_score = float(eval_res.get("complexity_score", 5.0))
        escalation_threshold = float(profile.get("escalation_threshold", config.ESCALATION_COMPLEXITY_THRESHOLD))

        # 2. Dynamic Routing Decision Logic
        is_escalated = False
        is_downscaled = False
        selected_model = profile["preferred_model"]
        routing_tier = "BALANCED"
        reasoning = ""

        # A. Budget exhaustion / downscale pressure check
        if budget_ratio < (1.0 - config.BUDGET_WARNING_THRESHOLD) and criticality not in ("CRITICAL", "HIGH"):
            selected_model = "gpt-oss-20b"
            routing_tier = "DOWNSCALED"
            is_downscaled = True
            reasoning = f"Budget pressure ({int(budget_ratio*100)}% remaining): Brick downscaled {profile['role_name']} to {selected_model} to preserve tokens."

        # B. Escalation condition (criticality, failure retry, or high complexity)
        elif force_escalate or (complexity_score >= escalation_threshold and config.ENABLE_DYNAMIC_ESCALATION):
            selected_model = profile.get("escalation_model", "qwen3.5-122b")
            routing_tier = "ESCALATED"
            is_escalated = True
            reasoning = f"Complexity threshold reached ({complexity_score:.1f} >= {escalation_threshold:.1f}): Brick escalated {profile['role_name']} to deep reasoning model {selected_model}."

        # C. Brick dynamic recommendation
        else:
            rec_model = eval_res.get("recommended_model", profile["preferred_model"])
            rec_tier = eval_res.get("recommended_tier", "BALANCED")
            selected_model = rec_model if config.ENABLE_SEMANTIC_ROUTING else profile["preferred_model"]
            routing_tier = rec_tier
            reasoning = eval_res.get(
                "routing_reasoning",
                f"Brick routed {profile['role_name']} to {selected_model} (complexity: {complexity_score:.1f}/10, tier: {routing_tier}).",
            )

        selected_model = normalize_model_name(selected_model)
        fallback_model = normalize_model_name(profile.get("fallback_model", "glm5.2"))

        decision = RoutingDecision(
            stage_key=stage,
            role_name=profile["role_name"],
            selected_model=selected_model,
            fallback_model=fallback_model,
            router_model=eval_res.get("router_model", config.MODEL_BRICK_ROUTER),
            complexity_score=complexity_score,
            routing_tier=routing_tier,
            reasoning=reasoning,
            token_limit=profile.get("token_limit", 2048),
            timeout_sec=profile.get("timeout_sec", 45),
            is_escalated=is_escalated,
            is_downscaled=is_downscaled,
            criticality=criticality,
            allowed_tools=allowed_tools,
            latency_sec=eval_res.get("latency_sec", 0.1),
        )

        self.routing_history.append(decision)
        return decision

    # Alias for subagent compatibility
    route_subagent = route_stage

    def get_routing_matrix(self) -> List[Dict[str, Any]]:
        """Return the baseline routing matrix for all registered stages/sub-agents."""
        matrix = []
        for key, p in config.SUBAGENT_PROFILES.items():
            matrix.append({
                "stage_key": key,
                "subagent_key": key,
                "role_name": p["role_name"],
                "preferred_model": normalize_model_name(p["preferred_model"]),
                "fallback_model": normalize_model_name(p["fallback_model"]),
                "escalation_model": normalize_model_name(p.get("escalation_model", "qwen3.5-122b")),
                "token_limit": p["token_limit"],
                "timeout_sec": p["timeout_sec"],
                "escalation_threshold": p["escalation_threshold"],
                "criticality": p["criticality"],
                "allowed_tools": p["allowed_tools"],
            })
        return matrix
