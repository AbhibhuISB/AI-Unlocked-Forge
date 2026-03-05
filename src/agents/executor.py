from __future__ import annotations

from typing import List

from ..models import EvidenceItem, Fault
from ..prompts import DELTA_PATCH_PROMPT, EXECUTOR_PROMPT
from ..services.llm_client import LLMClient


class ExecutorAgent:
    """Generate drafts and apply targeted revisions.

    What:
        Produces initial outputs and delta patches from reviewer faults.
    Why:
        Keeps execution concerns separate so iterative refinement remains controllable.
    """

    def __init__(self, llm: LLMClient) -> None:
        """Initialize executor dependencies.

        What:
            Stores the LLM client used for generation and patch prompts.
        Why:
            Maintains a single model-access abstraction across the pipeline.
        """
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
        """Generate the first complete draft.

        What:
            Synthesizes goal, constraints, plan details, and evidence into one output.
        Why:
            Creates a concrete artifact for the review/patch loop to improve iteratively.
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
        """Patch an existing draft using reviewer fault instructions.

        What:
            Applies issue-specific fixes rather than recreating the whole draft.
        Why:
            Delta patching is cheaper and often more stable than full regeneration.
        """
        fault_text = "\n".join(
            [f"- [{fault.severity}] {fault.issue} | Patch: {fault.patch_instruction}" for fault in faults]
        )
        prompt = f"Current draft:\n{draft}\n\nFaults:\n{fault_text}\n"
        return self.llm.complete_text(DELTA_PATCH_PROMPT, prompt)
