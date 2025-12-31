from dotenv import load_dotenv
load_dotenv()

from crewai import Crew, Process
from agents import competitive_analyst, copywriter, campaign_manager
from tasks import analysis_task, copy_task, strategy_task

# Assemble the launch crew
product_launch_crew = Crew(
    agents=[competitive_analyst, copywriter, campaign_manager],
    tasks=[analysis_task, copy_task, strategy_task],
    process=Process.sequential,  # Tasks execute in dependency order
    verbose=True
)

# Test function to run the crew locally
def test_crew():
    result = product_launch_crew.kickoff(inputs={
        "product_name": "Premium Organic Face Serum",
        "market_segment": "Natural Beauty E-commerce"
    })
    print("\n=== CREW OUTPUT ===")
    print(result)
    
    # Write output to local file
    with open("output.md", "w") as f:
        f.write("# CrewAI Product Launch Output\n\n")
        f.write(str(result))
    print("\nOutput written to output.md")
    
    return result

if __name__ == "__main__":
    test_crew()
