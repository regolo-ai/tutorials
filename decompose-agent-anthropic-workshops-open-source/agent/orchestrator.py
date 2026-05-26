import os
from agent.llm_client import query_llm
from agent.tools import run_python_analysis
from agent.subagents import forecaster_subagent

class StockPilotOrchestrator:
    def __init__(self):
        self.base_system_prompt = (
            "You are StockPilot, a high-performance inventory manager.\n"
            "Keep responses concise, structured, and strictly factual.\n"
            "Delegate actions to tools or subagents when structured calculation is required."
        )
        
    def _load_skill(self, skill_name: str) -> str:
        skill_path = os.path.join("skills", f"{skill_name}.txt")
        if os.path.exists(skill_path):
            with open(skill_path, "r") as f:
                return f.read()
        return ""

    def route_and_execute(self, user_query: str) -> str:
        """Classifies the user query, injects the correct skill, and executes the action."""
        routing_prompt = (
            f"Classify the following query into one of these categories: "
            f"['LOW_STOCK_SWEEP', 'PROMO_FORECAST', 'GENERAL'].\n"
            f"Query: {user_query}\n"
            f"Output only the category name, nothing else."
        )
        category = query_llm(routing_prompt).strip()
        
        if "LOW_STOCK_SWEEP" in category:
            skill = self._load_skill("reorder-policy")
            code_generation_prompt = (
                f"Write a Python script using pandas to find all SKUs in 'data/stock_levels.csv' "
                f"where the stock is strictly below the ReorderPoint.\n"
                f"For each low-stock SKU, compute the 'Order_Qty' using the formula: (2 * ReorderPoint) - Stock.\n"
                f"Print the results as a list of dictionaries with keys: 'SKU', 'Stock', 'ReorderPoint', 'Order_Qty'.\n"
                f"Output only python code inside raw text. Do not wrap in markdown codeblocks."
            )
            python_code = query_llm(code_generation_prompt, system_prompt=skill)
            execution_result = run_python_analysis(python_code)
            return execution_result

        elif "PROMO_FORECAST" in category:
            skill = self._load_skill("forecasting")
            data_fetch_code = (
                "import pandas as pd\n"
                "df_sales = pd.read_csv('data/sales_history.csv')\n"
                "velocity = df_sales[df_sales['SKU'] == 'SKU-0116']['SalesVelocity'].values[0]\n"
                "print(velocity)"
            )
            velocity_str = run_python_analysis(data_fetch_code)
            try:
                sales_velocity = float(velocity_str)
            except ValueError:
                sales_velocity = 12.0
            
            subagent_response = forecaster_subagent(
                sku="SKU-0116",
                sales_velocity=sales_velocity,
                horizon_days=30,
                is_promo=True,
                skill_context=skill
            )
            return subagent_response
        else:
            return query_llm(user_query, system_prompt=self.base_system_prompt)