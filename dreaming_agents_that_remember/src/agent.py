from .memory_store import MemoryStore

class LiveSessionAgent:
    def __init__(self, memory_dir: str, llm):
        self.memory_dir = memory_dir
        self.llm = llm
        self.memory_store = MemoryStore(memory_dir)
        self.last_loaded_files = []

    def execute_session(self, user_message: str):
        context, loaded_files = self.memory_store.load_context(user_message)
        self.last_loaded_files = loaded_files

        system_prompt = (
            "You are an agent with access to a mounted filesystem store. "
            "Use the provided index and selected files as your working memory. "
            "Prefer concise updates over copying raw logs.\n\n"
            f"--- SELECTED MOUNTED MEMORY CONTEXT ---\n{context}"
        )

        response = self.llm.query(system_prompt, user_message)

        self.memory_store.append_text(
            "sessions.md",
            (
                "\n"
                f"- Session Note: User provided message: {user_message}\n"
                f"  - Context files loaded: {', '.join(loaded_files) if loaded_files else 'none'}\n"
            ),
        )

        return response
