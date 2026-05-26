import sys
import json
from agent.orchestrator import StockPilotOrchestrator

def run_e2e_tests():
    print("==================================================")
    print("Starting E2E Tests for StockPilot (Decomposed)")
    print("==================================================")
    
    orchestrator = StockPilotOrchestrator()
    
    print("\n[TEST 1] Testing F1: Low Stock Sweep via Python Code execution...")
    query_f1 = "Run the daily low-stock sweep and identify which items require a replenishment order."
    
    try:
        response_f1 = orchestrator.route_and_execute(query_f1)
        print("Raw Agent Output:")
        print(response_f1)
        
        assert "SKU-0116" in response_f1, "SKU-0116 should be identified as low stock."
        assert "SKU-0300" in response_f1, "SKU-0300 should be identified as low stock."
        assert "SKU-0200" not in response_f1, "SKU-0200 has sufficient stock and should not be listed."
        print(">>> [TEST 1] SUCCESSFUL: Low-stock identified accurately via code primitive.")
    except AssertionError as e:
        print(f">>> [TEST 1] FAILED: {str(e)}")
    except Exception as e:
        print(f">>> [TEST 1] FAILED with unexpected error: {str(e)}")

    print("\n[TEST 2] Testing R8: Promotional Month Demand Forecast...")
    query_r8 = "Generate the demand forecast for SKU-0116 during the promo month of October (30 days)."
    
    try:
        response_r8 = orchestrator.route_and_execute(query_r8)
        print("Raw Agent Output:")
        print(response_r8)
        
        clean_json_str = response_r8.replace("```json", "").replace("```", "").strip()
        data = json.loads(clean_json_str)
        
        expected_demand = 12 * 30 * 3.1
        actual_demand = float(data.get("forecasted_demand", 0))
        
        print(f"Expected computed demand: {expected_demand} units.")
        print(f"Agent computed demand: {actual_demand} units.")
        
        assert abs(actual_demand - expected_demand) < 0.1, f"Forecast error. Expected {expected_demand}, got {actual_demand}."
        print(">>> [TEST 2] SUCCESSFUL: Subagent correctly computed the promo multiplier without prompt leakage.")
    except AssertionError as e:
        print(f">>> [TEST 2] FAILED: {str(e)}")
    except json.JSONDecodeError:
        print(">>> [TEST 2] FAILED: Output was not valid JSON.")
    except Exception as e:
        print(f">>> [TEST 2] FAILED with unexpected error: {str(e)}")

    print("\n==================================================")
    print("E2E Test Session Concluded.")
    print("==================================================")

if __name__ == '__main__':
    run_e2e_tests()