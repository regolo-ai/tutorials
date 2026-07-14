"""
src/feedback.py
---------------
Feedback and knowledge update layer.

After each review cycle:
  1. Persist outcomes to Qdrant review_memory
  2. Append lessons to code_review_skill.md
  3. Propose doc updates for recurring patterns

This closes the loop: review outcomes improve future retrieval.
"""
import logging
from pathlib import Path
from typing import List, Optional

logger = logging.getLogger("closed_loop.feedback")

ROOT = Path(__file__).resolve().parent.parent
SKILL_FILE = ROOT / "code_review_skill.md"


class FeedbackManager:
    """
    Connects review outcomes back to the knowledge base.
    """

    def __init__(self, retriever=None):
        """retriever: QdrantRetriever instance (optional — degrades gracefully)"""
        self.retriever = retriever
        self._lessons_this_run: List[str] = []

    def record_lesson(self, lesson: str) -> None:
        """Buffer a lesson learned during the current review run."""
        self._lessons_this_run.append(lesson)

    def flush_lessons(self) -> None:
        """Append buffered lessons to code_review_skill.md."""
        if not self._lessons_this_run:
            return
        with SKILL_FILE.open("a", encoding="utf-8") as f:
            for lesson in self._lessons_this_run:
                f.write(f"- {lesson}\n")
        logger.info("Flushed %d lessons to %s", len(self._lessons_this_run), SKILL_FILE)
        self._lessons_this_run.clear()

    def persist_outcome(
        self,
        target_path: str,
        status: str,
        iterations: int,
        reason: str,
    ) -> None:
        """
        Persist the review outcome to Qdrant review_memory.
        Also flushes pending lessons.
        """
        self.flush_lessons()
        if self.retriever is not None:
            self.retriever.persist_review_outcome(
                target_path=target_path,
                status=status,
                iterations=iterations,
                reason=reason,
                lessons=list(self._lessons_this_run),
            )
        else:
            logger.info("No retriever configured. Outcome not persisted to Qdrant.")

    def propose_doc_update(self, pattern: str, evidence: List[str]) -> Optional[str]:
        """
        If a recurring pattern is detected, return a candidate doc update string.
        In a full enterprise setup this would open a PR or ticket.
        """
        if len(evidence) < 2:
            return None
        proposal = (
            f"Recurring pattern detected: {pattern}\n"
            f"Evidence ({len(evidence)} occurrences):\n"
            + "\n".join(f"  - {e}" for e in evidence[:5])
            + "\nConsider updating coding standards or runbook."
        )
        logger.info("Doc update proposed for pattern: %s", pattern)
        return proposal
