from __future__ import annotations

from typing import List, Literal, Optional
from pydantic import BaseModel, Field


Severity = Literal["critical", "major", "minor"]


class SessionConfig(BaseModel):
    """Runtime tuning knobs for planning/review behavior.

    Why: Makes confidence/quality gates explicit and user-adjustable per request.
    """

    strategy_threshold: float = Field(default=0.80, ge=0.1, le=1.0)
    quality_threshold: float = Field(default=0.85, ge=0.1, le=1.0)
    max_iterations: int = Field(default=4, ge=1, le=10)
    output_format: str = Field(default="markdown")


class RunRequest(BaseModel):
    """Top-level input payload for quick and guided FORGE runs."""

    goal: str = Field(min_length=5)
    constraints: List[str] = Field(default_factory=list)
    config: SessionConfig = Field(default_factory=SessionConfig)


class EvidenceItem(BaseModel):
    """Normalized retrieval evidence record consumed by planner/executor prompts."""

    title: str
    url: str
    snippet: str
    source_credibility: float = Field(ge=0.0, le=1.0)


class PlannerOutput(BaseModel):
    """Structured planner result used as phase-2 execution input."""

    plan_summary: str
    subtasks: List[str]
    missing_info_queries: List[str]
    confidence: float = Field(ge=0.0, le=1.0)


class ExecutorDraft(BaseModel):
    """Simple container for executor draft text when typed wrapping is needed."""

    draft: str


class Fault(BaseModel):
    """Single review fault with severity and actionable patch instruction."""

    id: str
    severity: Severity
    issue: str
    patch_instruction: str


class ReviewOutput(BaseModel):
    """Reviewer output containing quality score and list of fix targets."""

    quality_score: float = Field(ge=0.0, le=1.0)
    faults: List[Fault] = Field(default_factory=list)


class ActivityLogEvent(BaseModel):
    """One user-facing activity event emitted during orchestration."""

    step: str
    message: str


class RunResponse(BaseModel):
    """Final output contract for a completed FORGE run."""

    final_output: str
    assumptions: List[str]
    activity_log: List[ActivityLogEvent]
    iterations: int
    ended_reason: str
    confidence_trace: List[float]
    quality_trace: List[float]
    evidence_used: List[EvidenceItem]


class InteractiveContinueRequest(BaseModel):
    """Payload for continuing a guided session with optional user clarification."""

    session_id: str
    user_comment: Optional[str] = None
    skip: bool = False


class InteractiveCancelRequest(BaseModel):
    """Payload for cancelling an in-progress guided session."""

    session_id: str


class InteractiveRunResponse(BaseModel):
    """Response contract for guided mode state transitions.

    Why: Allows frontend to distinguish whether user input is needed or run is complete.
    """

    status: Literal["needs_input", "completed"]
    session_id: str
    question: Optional[str] = None
    note: Optional[str] = None
    result: Optional[RunResponse] = None
