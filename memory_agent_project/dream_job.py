from main import choose_model, choose_provider, fetch_regolo_models, setup_env_and_get_key
from src.console import Style, file_list, info, panel, step, success
from src.dream import DreamingOrchestrator


def build_llm():
    provider = choose_provider()
    if provider == "1":
        from src.llm import LocalLLM

        step(1, "Initializing Local LLM", "Ollama with deterministic mock fallback")
        return LocalLLM()

    from src.llm import RegoloLLM

    models = fetch_regolo_models()
    model_name = choose_model(models)
    api_key = setup_env_and_get_key()
    step(1, "Initializing Regolo LLM", f"Model: {model_name}")
    return RegoloLLM(model_name=model_name, api_key=api_key)


def run_dream_job():
    panel(
        "Offline Dream Job",
        [
            "Runs consolidation without starting a live user session.",
            "Use this entry point for cron, launchd, CI, or manual review runs.",
        ],
        Style.BLUE,
    )
    llm = build_llm()

    step(2, "Dream cycle", "Reading input memory and historical transcripts")
    dreamer = DreamingOrchestrator(
        input_store="data/input_memory",
        transcripts_dir="data/transcripts",
        output_store="data/output_memory",
        llm=llm,
    )
    status = dreamer.run_dream_cycle()
    success(status["status"])
    file_list("Files written", status["files_written"])
    if status["diff_available"]:
        info("Human review diff available at data/output_memory/_review.diff")


if __name__ == "__main__":
    run_dream_job()