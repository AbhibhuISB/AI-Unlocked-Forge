from __future__ import annotations

from typing import List

from pydantic import BaseModel

from ..models import PlannerOutput, ReviewOutput
from ..prompts import DEVILS_ADVOCATE_PROMPT, PLANNER_PROMPT
from ..services.llm_client import LLMClient


class PlannerAgent:
    def __init__(self, llm: LLMClient) -> None:
        self.llm = llm

    def build_plan(self, goal: str, constraints: List[str], pinboard: List[str]) -> PlannerOutput:
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
        data = self.llm.complete_json(PLANNER_PROMPT, prompt, _PlannerSchema)
        return PlannerOutput(**data.model_dump())

    def review_output(self, goal: str, constraints: List[str], draft: str) -> ReviewOutput:
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
