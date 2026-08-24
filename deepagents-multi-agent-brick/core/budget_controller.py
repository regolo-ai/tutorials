"""Budget Controller & Telemetry Engine for Deep Agents on Regolo.ai.
Monitors token burn, latency, calculates exact cost savings vs Single Frontier Baseline,
and persists telemetry data for PR evidence & TUI dashboards.
"""

import json
import os
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

import config


@dataclass
class TelemetryEvent:
    """Individual execution event logged by a sub-agent."""
    subagent_key: str
    role_name: str
    model: str
    stage: str
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    latency_sec: float
    cost_regolo_usd: float
    cost_frontier_usd: float
    routing_tier: str
    is_escalated: bool
    is_downscaled: bool
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class BudgetController:
    """Active Budget Governance and Cost Analytics Controller."""

    def __init__(self, total_budget: Optional[int] = None):
        self.total_budget = total_budget or config.TOTAL_PIPELINE_TOKEN_BUDGET
        self.events: List[TelemetryEvent] = []
        self.current_run_events: List[TelemetryEvent] = []
        self.telemetry_file = config.TELEMETRY_FILE
        self._load_existing_telemetry()

    def _load_existing_telemetry(self):
        """Load past telemetry events if present."""
        if self.telemetry_file.exists():
            try:
                data = json.loads(self.telemetry_file.read_text(encoding="utf-8"))
                for item in data.get("events", []):
                    self.events.append(TelemetryEvent(**item))
            except Exception:
                pass

    def start_new_run(self, total_budget: Optional[int] = None):
        """Initialize a fresh budget session for a new pipeline execution."""
        if total_budget:
            self.total_budget = total_budget
        self.current_run_events = []

    def record_step(
        self,
        subagent_key: str,
        role_name: str,
        model: str,
        stage: str,
        prompt_tokens: int,
        completion_tokens: int,
        latency_sec: float,
        routing_tier: str = "BALANCED",
        is_escalated: bool = False,
        is_downscaled: bool = False,
    ) -> TelemetryEvent:
        """Record sub-agent execution metrics and compute cost deltas."""
        total_tokens = prompt_tokens + completion_tokens
        
        # Calculate Regolo Routed Cost
        regolo_pricing = config.PRICING_CATALOG["brick_routed_regolo"].get(
            model,
            {"prompt": 0.60, "completion": 1.80}  # fallback to GLM-5.2 pricing
        )
        cost_regolo = (
            (prompt_tokens / 1_000_000) * regolo_pricing["prompt"]
            + (completion_tokens / 1_000_000) * regolo_pricing["completion"]
        )

        # Calculate Single Frontier Baseline Cost (Omni Pro @ $3 / $15 per 1M)
        frontier_pricing = config.PRICING_CATALOG["single_frontier_baseline"]["frontier_omni_pro"]
        cost_frontier = (
            (prompt_tokens / 1_000_000) * frontier_pricing["prompt"]
            + (completion_tokens / 1_000_000) * frontier_pricing["completion"]
        )

        event = TelemetryEvent(
            subagent_key=subagent_key,
            role_name=role_name,
            model=model,
            stage=stage,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
            latency_sec=latency_sec,
            cost_regolo_usd=round(cost_regolo, 6),
            cost_frontier_usd=round(cost_frontier, 6),
            routing_tier=routing_tier,
            is_escalated=is_escalated,
            is_downscaled=is_downscaled,
        )

        self.events.append(event)
        self.current_run_events.append(event)
        self.save_telemetry()
        return event

    def _active_events(self) -> List[TelemetryEvent]:
        """Return the events list for the current active run, falling back to all events."""
        return self.current_run_events if self.current_run_events else self.events

    def get_residual_budget(self) -> int:
        """Get remaining tokens in current pipeline run."""
        spent = sum(e.total_tokens for e in self._active_events())
        return max(0, self.total_budget - spent)

    def get_budget_ratio(self) -> float:
        """Return ratio of remaining budget (0.0 to 1.0) in current pipeline run."""
        spent = sum(e.total_tokens for e in self._active_events())
        return max(0.0, 1.0 - (spent / max(1, self.total_budget)))

    def is_warning_threshold_reached(self) -> bool:
        """Check if token burn exceeded the warning threshold (e.g. 75%) in current run."""
        spent = sum(e.total_tokens for e in self._active_events())
        return (spent / max(1, self.total_budget)) >= config.BUDGET_WARNING_THRESHOLD

    def get_summary(self) -> Dict[str, Any]:
        """Generate comprehensive telemetry and cost comparison summary for the active run."""
        active_list = self._active_events()
        total_prompt = sum(e.prompt_tokens for e in active_list)
        total_completion = sum(e.completion_tokens for e in active_list)
        total_tokens = total_prompt + total_completion
        total_latency = sum(e.latency_sec for e in active_list)
        total_regolo_cost = sum(e.cost_regolo_usd for e in active_list)
        total_frontier_cost = sum(e.cost_frontier_usd for e in active_list)

        cost_savings_usd = max(0.0, total_frontier_cost - total_regolo_cost)
        savings_pct = (
            round((1.0 - (total_regolo_cost / max(0.000001, total_frontier_cost))) * 100, 1)
            if total_frontier_cost > 0 else 0.0
        )

        return {
            "total_events": len(active_list),
            "total_tokens": total_tokens,
            "total_prompt_tokens": total_prompt,
            "total_completion_tokens": total_completion,
            "residual_tokens": self.get_residual_budget(),
            "total_budget": self.total_budget,
            "budget_spent_pct": round((total_tokens / max(1, self.total_budget)) * 100, 1),
            "total_latency_sec": round(total_latency, 2),
            "total_regolo_cost_usd": round(total_regolo_cost, 4),
            "total_frontier_cost_usd": round(total_frontier_cost, 4),
            "cost_savings_usd": round(cost_savings_usd, 4),
            "savings_percentage": savings_pct,
            "events": [e.to_dict() for e in active_list],
        }

    def save_telemetry(self):
        """Persist telemetry data to disk."""
        summary = self.get_summary()
        self.telemetry_file.parent.mkdir(exist_ok=True, parents=True)
        self.telemetry_file.write_text(json.dumps(summary, indent=2), encoding="utf-8")

    def clear(self):
        """Clear all events and reset telemetry."""
        self.events.clear()
        self.current_run_events.clear()
        if self.telemetry_file.exists():
            self.telemetry_file.unlink()


# Global Singleton accessor
_global_budget_controller: Optional[BudgetController] = None


def get_budget_controller() -> BudgetController:
    global _global_budget_controller
    if _global_budget_controller is None:
        _global_budget_controller = BudgetController()
    return _global_budget_controller
