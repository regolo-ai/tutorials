from agent.llm_client import query_llm

def forecaster_subagent(sku: str, sales_velocity: float, horizon_days: int, is_promo: bool, skill_context: str) -> str:
    """Specialized subagent that only computes demand forecasting formulas."""
    promo_status = "This is a promotional month." if is_promo else "This is a normal month."
    
    prompt = (
        f"Perform the calculation for SKU: {sku}.\n"
        f"Base Sales Velocity: {sales_velocity} units/day.\n"
        f"Forecast Horizon: {horizon_days} days.\n"
        f"Promo Status: {promo_status}\n"
        f"Apply the rules provided in your system instructions and output ONLY the raw JSON."
    )
    
    system_prompt = (
        f"You are the Specialized Forecasting Subagent.\n"
        f"Here are your rules:\n{skill_context}\n"
        f"Compute carefully. Output only valid JSON. Do not write markdown blocks or conversational text."
    )
    
    return query_llm(prompt, system_prompt=system_prompt)