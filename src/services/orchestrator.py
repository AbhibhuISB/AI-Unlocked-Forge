from __future__ import annotations

import os
from typing import List

from ..agents.executor import ExecutorAgent
from ..agents.planner import PlannerAgent
from ..agents.retriever import RetrieverAgent
from ..models import RunRequest, RunResponse
from .llm_client import LLMClient
from .search_client import SearchClient
from ..state.memory import SessionMemory


class ForgeOrchestrator:
    def __init__(self) -> None:
        self.llm = LLMClient()
        self.search = SearchClient()
        self.planner = PlannerAgent(self.llm)
        self.retriever = RetrieverAgent(self.search)
        self.executor = ExecutorAgent(self.llm)

    def run(self, request: RunRequest) -> RunResponse:
        config = request.config
        strategy_threshold = config.strategy_threshold or float(os.getenv("DEFAULT_STRATEGY_THRESHOLD", "0.8"))
        quality_threshold = config.quality_threshold or float(os.getenv("DEFAULT_QUALITY_THRESHOLD", "0.85"))
        max_iterations = config.max_iterations or int(os.getenv("DEFAULT_MAX_ITERATIONS", "4"))

        memory = SessionMemory(constraint_pinboard=list(request.constraints))
        evidence_used = []

        memory.log("session_start", "FORGE run started.")

        plan = None
        for iteration in range(1, max_iterations + 1):
            memory.log("planner", f"Building strategy iteration {iteration}.")
            plan = self.planner.build_plan(
                goal=request.goal,
                constraints=request.constraints,
                pinboard=memory.constraint_pinboard,
            )
            memory.confidence_trace.append(plan.confidence)
            memory.log("planner_confidence", f"Planner confidence={plan.confidence:.2f}")

            if plan.missing_info_queries:
                memory.log("retriever", f"Fetching evidence for {len(plan.missing_info_queries)} queries.")
                evidence_used = self.retriever.gather(plan.missing_info_queries)
                memory.log("retriever", f"Retrieved {len(evidence_used)} evidence items.")

            if plan.confidence >= strategy_threshold:
                memory.log("gate", "Strategy threshold met. Moving to execution phase.")
                break

            memory.log("gate", "Strategy threshold not met. Re-planning.")

        if plan is None:
            raise RuntimeError("Planner did not produce a plan.")

        memory.log("executor", "Generating first draft.")
        draft = self.executor.generate(
            goal=request.goal,
            constraints=request.constraints,
            output_format=config.output_format,
            plan_summary=plan.plan_summary,
            subtasks=plan.subtasks,
            evidence=evidence_used,
        )

        ended_reason = "max_iterations_reached"
        for review_iteration in range(1, max_iterations + 1):
            memory.log("devils_advocate", f"Running quality review iteration {review_iteration}.")
            review = self.planner.review_output(request.goal, request.constraints, draft)
            memory.quality_trace.append(review.quality_score)
            memory.log("quality", f"Quality score={review.quality_score:.2f}")

            if review.quality_score >= quality_threshold:
                ended_reason = "quality_threshold_met"
                memory.log("gate", "Quality threshold met. Finishing run.")
                break

            if not review.faults:
                ended_reason = "no_faults_but_low_score"
                memory.log("gate", "No actionable faults returned. Finishing run.")
                break

            memory.log("executor_patch", f"Applying {len(review.faults)} targeted patches.")
            draft = self.executor.patch(draft, review.faults)

        memory.assumptions.append("Prototype assumption: retrieval credibility uses a heuristic fixed baseline.")
        memory.log("session_end", "FORGE run completed.")

        return RunResponse(
            final_output=draft,
            assumptions=memory.assumptions,
            activity_log=memory.activity_log,
            iterations=max(len(memory.confidence_trace), len(memory.quality_trace)),
            ended_reason=ended_reason,
            confidence_trace=memory.confidence_trace,
            quality_trace=memory.quality_trace,
            evidence_used=evidence_used,
        )
