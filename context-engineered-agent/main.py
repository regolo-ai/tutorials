from agent import ContextEngineAgent

def main():
    agent = ContextEngineAgent()
    task = (
        "Analyze 'user_activity.csv' to locate the top active user, "
        "write it to persistent notes, then run a sub-agent to compute "
        "the aggregated transaction revenues."
    )
    agent.run(task)

if __name__ == "__main__":
    main()