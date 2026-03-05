from __future__ import annotations

from typing import List

from ..models import EvidenceItem, Fault
from ..prompts import DELTA_PATCH_PROMPT, EXECUTOR_PROMPT
from ..services.llm_client import LLMClient


class ExecutorAgent:
    """Generate drafts and apply targeted revisions from review faults.

    Why: Separating execution from planning/review enables iterative refinement
    without collapsing all concerns into one large prompt.
    """

    def __init__(self, llm: LLMClient) -> None:
        """Store shared LLM client for draft generation and patching."""
        self.llm = llm

    def generate(
        self,
        goal: str,
        constraints: List[str],
        output_format: str,
        plan_summary: str,
        subtasks: List[str],
        evidence: List[EvidenceItem],
    ) -> str:
        """Create the first full draft from strategy, constraints, and evidence.

        Why: Produces a concrete artifact that can be reviewed and patched in the
        quality loop instead of repeatedly replanning from scratch.
        """
        prompt = (
            f"Goal:\n{goal}\n\n"
            f"Output format: {output_format}\n\n"
            f"Constraints:\n- " + "\n- ".join(constraints if constraints else ["None provided"]) + "\n\n"
            f"Plan summary:\n{plan_summary}\n\n"
            f"Subtasks:\n- " + "\n- ".join(subtasks if subtasks else ["None"]) + "\n\n"
            f"Evidence:\n" + "\n".join([f"- {item.title}: {item.snippet} ({item.url})" for item in evidence[:10]]) + "\n\n"
            "Include a final section named 'Assumptions'."
        )
        return self.llm.complete_text(EXECUTOR_PROMPT, prompt)

    def patch(self, draft: str, faults: List[Fault]) -> str:
        """Apply focused fixes to an existing draft using reviewer fault items.

        Why: Delta patching is cheaper and usually more stable than full regeneration
        when only a subset of quality issues must be corrected.
        """
        fault_text = "\n".join(
            [f"- [{fault.severity}] {fault.issue} | Patch: {fault.patch_instruction}" for fault in faults]
        )
        prompt = f"Current draft:\n{draft}\n\nFaults:\n{fault_text}\n"
        return self.llm.complete_text(DELTA_PATCH_PROMPT, prompt)
