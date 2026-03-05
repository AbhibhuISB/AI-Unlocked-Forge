from __future__ import annotations

from typing import List

from pydantic import BaseModel

from ..models import PlannerOutput, ReviewOutput
from ..prompts import DEVILS_ADVOCATE_PROMPT, PLANNER_PROMPT, TOT_PLANNER_PROMPT
from ..services.llm_client import LLMClient


class PlannerAgent:
    """Plan strategy and review output quality.

    What:
        Provides plan generation (including ToT selection) and devil's-advocate review.
    Why:
        Separating planning/review from execution keeps responsibilities clear and extensible.
    """

    def __init__(self, llm: LLMClient) -> None:
        """Initialize planner dependencies.

        What:
            Stores a shared LLM client used by planning and review calls.
        Why:
            Centralizes model access and keeps the agent easy to test and reuse.
        """
        self.llm = llm

    @staticmethod
    def _clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
        """Clamp a score into a bounded interval.

        What:
            Restricts numeric values to `[low, high]`.
        Why:
            Protects downstream threshold gates from malformed or drifted model scores.
        """
        return max(low, min(high, value))

    @staticmethod
    def _overall(constraint_score: float, feasibility_score: float, risk_penalty: float) -> float:
        """Compute weighted utility for ToT candidate ranking.

        What:
            Combines constraint, feasibility, and risk into one comparable score.
        Why:
            Enables deterministic branch selection aligned with FORGE planning priorities.
        """
        return PlannerAgent._clamp(0.55 * constraint_score + 0.35 * feasibility_score - 0.10 * risk_penalty)

    def build_plan(self, goal: str, constraints: List[str], pinboard: List[str]) -> PlannerOutput:
        """Build a planning strategy from goal and constraints.

        What:
            Uses Tree-of-Thoughts candidate generation, recomputes branch scores,
            and returns the best viable path; falls back to legacy planner if needed.
        Why:
            Improves robustness versus single-shot planning without sacrificing runtime reliability.
        """
        class _ToTCandidate(BaseModel):
            path_id: str
            plan_summary: str
            subtasks: List[str]
            missing_info_queries: List[str]
            constraint_score: float
            feasibility_score: float
            risk_penalty: float
            overall_score: float
            confidence: float

        class _ToTResult(BaseModel):
            candidates: List[_ToTCandidate]
            selected_path_id: str
            pruned_path_ids: List[str]
            selected_reason: str

        class _PlannerSchema(BaseModel):
            plan_summary: str
            subtasks: List[str]
            missing_info_queries: List[str]
            confidence: float

        prompt = (
            f"Goal:\n{goal}\n\n"
            f"Constraints:\n- " + "\n- ".join(constraints if constraints else ["None provided"]) + "\n\n"
            f"Constraint Pinboard (must satisfy all):\n- " + "\n- ".join(pinboard if pinboard else ["None"]) + "\n"
        )

        try:
            tot = self.llm.complete_json(TOT_PLANNER_PROMPT, prompt, _ToTResult)

            candidates = []
            pruned_ids = set(tot.pruned_path_ids)
            for candidate in tot.candidates[:3]:
                recomputed = self._overall(
                    constraint_score=float(candidate.constraint_score),
                    feasibility_score=float(candidate.feasibility_score),
                    risk_penalty=float(candidate.risk_penalty),
                )
                confidence = self._clamp(float(candidate.confidence))
                candidates.append(
                    {
                        "path_id": candidate.path_id,
                        "plan_summary": candidate.plan_summary,
                        "subtasks": candidate.subtasks,
                        "missing_info_queries": candidate.missing_info_queries,
                        "overall_score": recomputed,
                        "confidence": confidence,
                        "pruned": candidate.path_id in pruned_ids,
                    }
                )

            viable = [item for item in candidates if not item["pruned"]]
            pool = viable if viable else candidates
            if not pool:
                raise RuntimeError("ToT returned no candidate paths")

            selected = max(pool, key=lambda item: item["overall_score"])
            return PlannerOutput(
                plan_summary=selected["plan_summary"],
                subtasks=selected["subtasks"],
                missing_info_queries=selected["missing_info_queries"],
                confidence=self._clamp(0.5 * selected["confidence"] + 0.5 * selected["overall_score"]),
            )
        except Exception:
            # Fallback keeps the pipeline operational even if ToT structure is invalid.
            data = self.llm.complete_json(PLANNER_PROMPT, prompt, _PlannerSchema)
            return PlannerOutput(**data.model_dump())

    def review_output(self, goal: str, constraints: List[str], draft: str) -> ReviewOutput:
        """Review a draft and return quality plus faults.

        What:
            Produces a numeric quality score and actionable issue list.
        Why:
            Supports targeted patching loops instead of expensive full rewrites.
        """
        class _ReviewSchema(BaseModel):
            quality_score: float
            faults: list

        prompt = (
            f"Goal:\n{goal}\n\n"
            f"Constraints:\n- " + "\n- ".join(constraints if constraints else ["None provided"]) + "\n\n"
            f"Draft:\n{draft}\n"
        )
        data = self.llm.complete_json(DEVILS_ADVOCATE_PROMPT, prompt, _ReviewSchema)
        return ReviewOutput.model_validate(data.model_dump())
