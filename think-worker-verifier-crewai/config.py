"""config.py — Configurazione centralizzata del progetto TWV."""
from __future__ import annotations
import os
from dataclasses import dataclass
from crewai import LLM

@dataclass(slots=True)
class Settings:
    embedding_model: str = os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small")
    max_retries: int = int(os.getenv("TWV_MAX_RETRIES", "2"))
    max_reassigns: int = int(os.getenv("TWV_MAX_REASSIGNS", "2"))
    max_replans: int = int(os.getenv("TWV_MAX_REPLANS", "2"))
    verbose: bool = os.getenv("TWV_VERBOSE", "true").lower() == "true"
    memory_scope_root: str = "/twv"

    # Configurazione Provider OpenAI-compatible
    openai_api_base: str | None = os.getenv("OPENAI_API_BASE") or os.getenv("OPENAI_BASE_URL")
    openai_api_key: str | None = os.getenv("OPENAI_API_KEY")

    # Modelli specifici per ciascun ruolo di agente
    thinker_model: str = os.getenv("THINKER_MODEL") or os.getenv("OPENAI_MODEL_NAME", "gpt-4o")
    worker_model: str = os.getenv("WORKER_MODEL") or os.getenv("OPENAI_MODEL_NAME", "gpt-4o")
    verifier_model: str = os.getenv("VERIFIER_MODEL") or os.getenv("OPENAI_MODEL_NAME", "gpt-4o")

    @property
    def llm_model(self) -> str:
        """Compatibilità retroattiva per moduli esterni."""
        return self.thinker_model

    def _get_llm(self, model_name: str) -> LLM:
        resolved_model = model_name
        # Se c'è un base_url personalizzato e il modello non ha già un prefisso con slash (es. "ollama/"),
        # forziamo il prefisso "openai/" per indicare a litellm/crewai di usare il protocollo compatibile OpenAI.
        if self.openai_api_base and not ("/" in model_name):
            resolved_model = f"openai/{model_name}"
            
        return LLM(
            model=resolved_model,
            base_url=self.openai_api_base,
            api_key=self.openai_api_key,
        )

    @property
    def thinker_llm(self) -> LLM:
        return self._get_llm(self.thinker_model)

    @property
    def worker_llm(self) -> LLM:
        return self._get_llm(self.worker_model)

    @property
    def verifier_llm(self) -> LLM:
        return self._get_llm(self.verifier_model)

    @property
    def embedder(self) -> dict:
        config_dict = {"model_name": self.embedding_model}
        if self.openai_api_base:
            config_dict["api_base"] = self.openai_api_base
        if self.openai_api_key:
            config_dict["api_key"] = self.openai_api_key
        return {"provider": "openai", "config": config_dict}

settings = Settings()
