"""pydantic_patch.py — Monkeypatching runtime per disabilitare extra='forbid' in CrewAI Memory."""
from __future__ import annotations
import logging

logger = logging.getLogger("pydantic_patch")

def apply_pydantic_patch() -> None:
    """Modifica la configurazione Pydantic delle classi interne di CrewAI Memory

    per consentire campi extra ed evitare gli errori extra_forbidden (es. 'using defaults')
    quando si lavora con LLM non-OpenAI OpenAI-compatible.
    """
    try:
        import crewai.memory.analyze as cma
        
        # Classi di CrewAI Memory che usano extra="forbid"
        target_classes = [
            cma.ExtractedMetadata,
            cma.ConsolidationPlan,
            cma.ConsolidationAction
        ]
        
        for cls in target_classes:
            if hasattr(cls, "model_config"):
                # Sostituiamo 'forbid' con 'ignore' per far ignorare a Pydantic i campi estranei dell'LLM
                cls.model_config["extra"] = "ignore"
                try:
                    cls.model_rebuild(force=True)
                except Exception as ex:
                    logger.debug(f"Impossibile ricostruire il modello {cls.__name__}: {ex}")
                    
        logger.info("✔ Pydantic patch per CrewAI Memory applicata con successo (extra='ignore').")
    except Exception as e:
        logger.warning(f"Impossibile applicare il patch Pydantic su CrewAI Memory: {e}")
