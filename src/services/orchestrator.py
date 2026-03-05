from __future__ import annotations

import os
from uuid import uuid4
from typing import Dict, Tuple
from urllib.parse import urlparse

from ..agents.executor import ExecutorAgent
from ..agents.planner import PlannerAgent
from ..agents.retriever import RetrieverAgent
from ..models import InteractiveRunResponse, RunRequest, RunResponse
from .llm_client import LLMClient
from .search_client import SearchClient
from ..state.memory import SessionMemory


class ForgeOrchestrator:
    """Coordinate FORGE agent workflows.

    What:
        Orchestrates planner, retriever, and executor across quick and guided modes.
    Why:
        Centralized control enforces consistent gates, logging semantics, and safety guards.
    """

    def __init__(self) -> None:
        """Initialize orchestrator dependencies.

        What:
            Creates shared clients/agents and an in-memory interactive session registry.
        Why:
            Keeps stateful guided flows and autonomous runs on the same execution backbone.
        """
        self.llm = LLMClient()
        self.search = SearchClient()
        self.planner = PlannerAgent(self.llm)
        self.retriever = RetrieverAgent(self.search)
        self.executor = ExecutorAgent(self.llm)
        self.interactive_sessions: Dict[str, dict] = {}

    def _thresholds(self, request: RunRequest) -> Tuple[float, float, int]:
        """Resolve effective thresholds for a run.

        What:
            Derives strategy threshold, quality threshold, and max iterations from request/env.
        Why:
            Supports per-request tuning while preserving global defaults.
        """
        config = request.config
        strategy_threshold = config.strategy_threshold or float(os.getenv("DEFAULT_STRATEGY_THRESHOLD", "0.8"))
        quality_threshold = config.quality_threshold or float(os.getenv("DEFAULT_QUALITY_THRESHOLD", "0.85"))
        max_iterations = config.max_iterations or int(os.getenv("DEFAULT_MAX_ITERATIONS", "4"))
        return strategy_threshold, quality_threshold, max_iterations

    def _planner_step(self, state: dict) -> None:
        """Execute one phase-1 planning step.

        What:
            Builds/updates plan, optionally gathers evidence, detects conflicts, and applies source priority.
        Why:
            Encapsulates shared planning semantics used by both quick and guided modes.
        """
        state["memory"].log("planner", f"Planning iteration {state['iteration']}: building task strategy.")
        plan = self.planner.build_plan(
            goal=state["goal"],
            constraints=state["constraints"],
            pinboard=state["memory"].constraint_pinboard,
        )
        state["plan"] = plan
        state["memory"].confidence_trace.append(plan.confidence)
        state["memory"].log("planner_confidence", f"Confidence is {plan.confidence:.2f}; checking if strategy is ready.")

        if plan.missing_info_queries:
            state["memory"].log("retriever", f"I am searching for sources on {len(plan.missing_info_queries)} missing points.")
            state["evidence_used"] = self.retriever.gather(plan.missing_info_queries)
            state["memory"].log("retriever", f"Source search complete. Collected {len(state['evidence_used'])} evidence items.")

            conflict_domains = self._detect_conflict_domains(state["evidence_used"])
            state["conflict_domains"] = conflict_domains
            if conflict_domains:
                state["memory"].log(
                    "retriever_conflict",
                    f"I found potentially conflicting sources: {', '.join(conflict_domains)}.",
                )

            self._apply_source_priority(state)

    def _detect_conflict_domains(self, evidence) -> list[str]:
        """Heuristically detect potentially conflicting source domains.

        What:
            Detects opposite negation patterns between snippets and returns the first conflicting domain pair.
        Why:
            Triggers guided source-priority choice when evidence appears contradictory.
        """
        if len(evidence) < 2:
            return []

        negation_tokens = [" not ", " no ", " never ", " without ", " cannot ", " can't "]
        domains = []

        for item in evidence:
            url = (item.url or "").strip()
            domain = (urlparse(url).netloc or "unknown").lower()
            domains.append(domain)

        for i in range(len(evidence)):
            for j in range(i + 1, len(evidence)):
                a = f" {evidence[i].snippet.lower()} "
                b = f" {evidence[j].snippet.lower()} "
                a_has_neg = any(token in a for token in negation_tokens)
                b_has_neg = any(token in b for token in negation_tokens)
                if a_has_neg != b_has_neg:
                    pair = sorted(set([domains[i], domains[j]]))
                    return [value for value in pair if value]

        return []

    def _extract_priority_from_comment(self, comment: str, conflict_domains: list[str]) -> str | None:
        """Extract chosen source domain from user text.

        What:
            Matches free-form user comment against known conflicting domains.
        Why:
            Keeps input flexible while still producing deterministic source ordering.
        """
        text = (comment or "").lower()
        for domain in conflict_domains:
            if domain and domain in text:
                return domain
        return None

    def _apply_source_priority(self, state: dict) -> None:
        """Reorder evidence using selected source priority.

        What:
            Moves items from the preferred domain ahead of others.
        Why:
            Prompt order influences synthesis, so trusted sources are surfaced first.
        """
        priority = (state.get("source_priority") or "").strip().lower()
        evidence = state.get("evidence_used", [])
        if not priority or not evidence:
            return

        prioritized = []
        others = []
        for item in evidence:
            domain = (urlparse((item.url or "").strip()).netloc or "unknown").lower()
            if priority in domain:
                prioritized.append(item)
            else:
                others.append(item)

        if prioritized:
            state["evidence_used"] = prioritized + others
            state["memory"].log("source_priority", f"Prioritizing evidence from {priority}.")

    def _build_question(self, state: dict) -> str:
        """Build the next guided-mode prompt.

        What:
            Returns either conflict-resolution question or planning-clarification question.
        Why:
            Ensures user interaction stays context-aware and high-signal.
        """
        plan = state["plan"]

        conflict_domains = state.get("conflict_domains", [])
        if conflict_domains and not state.get("source_priority"):
            return (
                f"I found conflicting information across sources ({', '.join(conflict_domains)}). "
                "Which source should I prioritize? You can type a domain name, or click Skip to use default priority."
            )

        if plan and plan.missing_info_queries:
            focus = ", ".join(plan.missing_info_queries[:2])
            return (
                f"I am currently evaluating: {focus}. "
                "Do you want me to proceed with this method and current constraints, or change direction?"
            )
        return "I can proceed with the current approach. Do you want to add or change any constraints before I continue?"

    def _phase2_execute(self, state: dict) -> RunResponse:
        """Execute the draft-and-review loop until quality target or stop condition.

        What:
            Generates draft output, reviews quality, applies targeted patches, and enforces loop guards.
        Why:
            Improves quality iteratively while preventing unbounded or oscillating retries.
        """
        request = state["request"]
        memory = state["memory"]
        plan = state["plan"]
        max_iterations = state["max_iterations"]
        quality_threshold = state["quality_threshold"]

        if plan is None:
            raise RuntimeError("Planner did not produce a plan.")

        memory.log("executor", "Generating first draft based on current best plan.")
        draft = self.executor.generate(
            goal=request.goal,
            constraints=state["constraints"],
            output_format=request.config.output_format,
            plan_summary=plan.plan_summary,
            subtasks=plan.subtasks,
            evidence=state["evidence_used"],
        )

        ended_reason = "max_iterations_reached"
        previous_fault_ids: list[str] = []
        fault_signature_history: list[tuple[str, ...]] = []
        resolved_fault_ids: set[str] = set()
        for review_iteration in range(1, max_iterations + 1):
            memory.log("devils_advocate", f"Review iteration {review_iteration}: stress-testing draft quality.")
            review = self.planner.review_output(request.goal, state["constraints"], draft)
            memory.quality_trace.append(review.quality_score)
            memory.log("quality", f"Quality is {review.quality_score:.2f}; deciding whether to patch.")

            current_fault_ids = [fault.id for fault in review.faults if fault.id]
            current_signature = tuple(sorted(set(current_fault_ids)))
            if current_fault_ids and current_fault_ids == previous_fault_ids:
                # Guard 1: identical consecutive fault sets imply no effective progress.
                ended_reason = "deadlock_guard_triggered"
                memory.log(
                    "deadlock_guard",
                    "Same fault IDs repeated in consecutive review cycles. Stopping to prevent ping-pong loop.",
                )
                break

            if (
                current_signature
                and len(fault_signature_history) >= 3
                and current_signature == fault_signature_history[-2]
                and fault_signature_history[-1] == fault_signature_history[-3]
                and current_signature != fault_signature_history[-1]
            ):
                # Guard 2: alternating signatures (A-B-A-B) indicate ping-pong behavior.
                ended_reason = "deadlock_guard_triggered"
                memory.log(
                    "deadlock_guard",
                    "Alternating fault pattern detected across review cycles. Stopping to prevent ping-pong loop.",
                )
                break

            repeated_resolved = [fault_id for fault_id in current_fault_ids if fault_id in resolved_fault_ids]
            if repeated_resolved:
                memory.log(
                    "deadlock_guard",
                    f"Previously seen fault IDs reappeared: {', '.join(repeated_resolved[:3])}. Monitoring for deadlock.",
                )

            if review.quality_score >= quality_threshold:
                ended_reason = "quality_threshold_met"
                memory.log("gate", "Quality target reached. Finalizing output.")
                break

            if not review.faults:
                ended_reason = "no_faults_but_low_score"
                memory.log("gate", "No clear fixes found. Returning best available output.")
                break

            memory.log("executor_patch", f"I think targeted fixes are better than full rewrite. Applying {len(review.faults)} patches.")
            draft = self.executor.patch(draft, review.faults)
            resolved_fault_ids.update(current_fault_ids)
            previous_fault_ids = current_fault_ids
            if current_signature:
                fault_signature_history.append(current_signature)

        memory.assumptions.append("Prototype assumption: retrieval credibility uses a heuristic fixed baseline.")
        memory.log("session_end", "Run complete. Delivering output, assumptions, and logs.")

        return RunResponse(
            final_output=draft,
            assumptions=memory.assumptions,
            activity_log=memory.activity_log,
            iterations=max(len(memory.confidence_trace), len(memory.quality_trace)),
            ended_reason=ended_reason,
            confidence_trace=memory.confidence_trace,
            quality_trace=memory.quality_trace,
            evidence_used=state["evidence_used"],
        )

    def run(self, request: RunRequest) -> RunResponse:
        """Execute a complete autonomous run.

        What:
            Iterates planning until confidence gate then executes phase-2 refinement.
        Why:
            Supports quick-run UX and synchronous API consumers.
        """
        strategy_threshold, quality_threshold, max_iterations = self._thresholds(request)

        state = {
            "request": request,
            "goal": request.goal,
            "constraints": list(request.constraints),
            "memory": SessionMemory(constraint_pinboard=list(request.constraints)),
            "evidence_used": [],
            "plan": None,
            "iteration": 1,
            "strategy_threshold": strategy_threshold,
            "quality_threshold": quality_threshold,
            "max_iterations": max_iterations,
        }

        state["memory"].log("session_start", "Run started. Reading goal and constraints.")

        for iteration in range(1, max_iterations + 1):
            state["iteration"] = iteration
            self._planner_step(state)

            if state["plan"].confidence >= strategy_threshold:
                state["memory"].log("gate", "Plan looks reliable enough. Moving to execution.")
                break

            state["memory"].log("gate", "Plan confidence is low. Rerouting to another planning pass.")

        return self._phase2_execute(state)

    def start_interactive(self, request: RunRequest) -> InteractiveRunResponse:
        """Start a guided run session.

        What:
            Initializes guided state, executes first planning step, and returns question or final result.
        Why:
            Enables human-in-the-loop planning on top of the same core pipeline.
        """
        strategy_threshold, quality_threshold, max_iterations = self._thresholds(request)
        session_id = str(uuid4())

        state = {
            "request": request,
            "goal": request.goal,
            "constraints": list(request.constraints),
            "memory": SessionMemory(constraint_pinboard=list(request.constraints)),
            "evidence_used": [],
            "plan": None,
            "iteration": 1,
            "strategy_threshold": strategy_threshold,
            "quality_threshold": quality_threshold,
            "max_iterations": max_iterations,
            "source_priority": "",
            "conflict_domains": [],
        }

        state["memory"].log("session_start", "Guided run started. I will ask for your input during planning.")
        self._planner_step(state)

        if state["iteration"] >= state["max_iterations"]:
            state["memory"].log("gate", "Final planning iteration completed. Moving to execution.")
            result = self._phase2_execute(state)
            return InteractiveRunResponse(status="completed", session_id=session_id, result=result)

        self.interactive_sessions[session_id] = state

        question = self._build_question(state)
        state["memory"].log("interactive", question)
        return InteractiveRunResponse(
            status="needs_input",
            session_id=session_id,
            question=question,
            note="Reply with your suggestion or click Skip to continue with current plan.",
        )

    def continue_interactive(self, session_id: str, user_comment: str | None, skip: bool) -> InteractiveRunResponse:
        """Advance an existing guided session.

        What:
            Applies user input/skip, updates constraints or source priority, and continues flow.
        Why:
            Keeps guided transitions explicit, auditable, and deterministic.
        """
        if session_id not in self.interactive_sessions:
            raise RuntimeError("Interactive session not found or expired.")

        state = self.interactive_sessions[session_id]
        conflict_domains = state.get("conflict_domains", [])
        comment_text = (user_comment or "").strip()

        if conflict_domains and not state.get("source_priority"):
            chosen = self._extract_priority_from_comment(comment_text, conflict_domains)
            if chosen:
                state["source_priority"] = chosen
                state["memory"].log("source_priority", f"User selected source priority: {chosen}")
            elif skip and conflict_domains:
                fallback = conflict_domains[0]
                state["source_priority"] = fallback
                state["memory"].log("source_priority", f"No source selected. Using default priority: {fallback}")

        max_reached = state["iteration"] >= state["max_iterations"]

        if skip:
            state["memory"].log("user_input", "User skipped clarification. Proceeding with current method.")
        else:
            if comment_text:
                state["constraints"].append(comment_text)
                state["memory"].constraint_pinboard.append(comment_text)
                state["memory"].log("user_input", f"User clarification received: {comment_text}")
            else:
                state["memory"].log("user_input", "No new clarification provided. Proceeding.")

        if max_reached:
            state["memory"].log("gate", "Reached final planning iteration. Moving to execution.")
            result = self._phase2_execute(state)
            self.interactive_sessions.pop(session_id, None)
            return InteractiveRunResponse(status="completed", session_id=session_id, result=result)

        state["iteration"] += 1
        self._planner_step(state)

        if state["iteration"] >= state["max_iterations"]:
            state["memory"].log("gate", "Final planning iteration completed. Moving to execution.")
            result = self._phase2_execute(state)
            self.interactive_sessions.pop(session_id, None)
            return InteractiveRunResponse(status="completed", session_id=session_id, result=result)

        question = self._build_question(state)
        state["memory"].log("interactive", question)
        return InteractiveRunResponse(
            status="needs_input",
            session_id=session_id,
            question=question,
            note="Reply with your suggestion or click Skip to continue with current plan.",
        )

    def cancel_interactive(self, session_id: str) -> None:
        """Cancel a guided session.

        What:
            Deletes the session state keyed by `session_id` if present.
        Why:
            Frees memory and provides explicit interruption semantics.
        """
        self.interactive_sessions.pop(session_id, None)
