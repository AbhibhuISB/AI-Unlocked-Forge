from __future__ import annotations

from typing import List, Literal, Optional
from pydantic import BaseModel, Field


Severity = Literal["critical", "major", "minor"]


class SessionConfig(BaseModel):
    """Define runtime tuning parameters.

    What:
        Stores thresholds, iteration caps, and output formatting preferences.
    Why:
        Exposes key pipeline controls to callers while keeping safe bounds.
    """

    strategy_threshold: float = Field(default=0.80, ge=0.1, le=1.0)
    quality_threshold: float = Field(default=0.85, ge=0.1, le=1.0)
    max_iterations: int = Field(default=4, ge=1, le=10)
    output_format: str = Field(default="markdown")


class RunRequest(BaseModel):
    """Represent a run request payload.

    What:
        Carries goal, constraints, and optional session config.
    Why:
        Provides one validated input contract for both quick and guided flows.
    """

    goal: str = Field(min_length=5)
    constraints: List[str] = Field(default_factory=list)
    config: SessionConfig = Field(default_factory=SessionConfig)


class EvidenceItem(BaseModel):
    """Represent one retrieval evidence item.

    What:
        Captures title, URL, snippet, and heuristic credibility.
    Why:
        Gives planner/executor a consistent source record format.
    """

    title: str
    url: str
    snippet: str
    source_credibility: float = Field(ge=0.0, le=1.0)


class PlannerOutput(BaseModel):
    """Represent planner output for downstream execution.

    What:
        Stores summary, subtasks, missing-info queries, and confidence score.
    Why:
        Provides typed handoff from planning to retrieval and execution phases.
    """

    plan_summary: str
    subtasks: List[str]
    missing_info_queries: List[str]
    confidence: float = Field(ge=0.0, le=1.0)


class ExecutorDraft(BaseModel):
    """Wrap executor draft text.

    What:
        Holds draft output in a typed model.
    Why:
        Supports consistency where typed payloads are preferred.
    """

    draft: str


class Fault(BaseModel):
    """Describe one review-detected issue.

    What:
        Includes stable fault ID, severity, issue description, and patch instruction.
    Why:
        Enables deterministic patch loops and deadlock/cycle detection.
    """

    id: str
    severity: Severity
    issue: str
    patch_instruction: str


class ReviewOutput(BaseModel):
    """Represent output from the reviewer step.

    What:
        Contains quality score and actionable fault list.
    Why:
        Drives gating and patch behavior in phase 2.
    """

    quality_score: float = Field(ge=0.0, le=1.0)
    faults: List[Fault] = Field(default_factory=list)


class ActivityLogEvent(BaseModel):
    """Represent one activity log event.

    What:
        Stores step identifier and human-readable message.
    Why:
        Supports transparent progress reporting in UI and API responses.
    """

    step: str
    message: str


class RunResponse(BaseModel):
    """Represent final response for a completed run.

    What:
        Returns output, assumptions, traces, logs, evidence, and end reason.
    Why:
        Gives callers both deliverable content and explainability metadata.
    """

    final_output: str
    assumptions: List[str]
    activity_log: List[ActivityLogEvent]
    iterations: int
    ended_reason: str
    confidence_trace: List[float]
    quality_trace: List[float]
    evidence_used: List[EvidenceItem]


class InteractiveContinueRequest(BaseModel):
    """Represent guided-session continuation input.

    What:
        Carries session ID plus optional user comment or skip flag.
    Why:
        Keeps guided progression explicit and validated.
    """

    session_id: str
    user_comment: Optional[str] = None
    skip: bool = False


class InteractiveCancelRequest(BaseModel):
    """Represent guided-session cancel input.

    What:
        Identifies session to cancel.
    Why:
        Enables safe interruption of in-progress guided runs.
    """

    session_id: str


class InteractiveRunResponse(BaseModel):
    """Represent guided mode state transition response.

    What:
        Returns session status plus either next question or completed result.
    Why:
        Lets clients render guided UX correctly without guessing orchestration state.
    """

    status: Literal["needs_input", "completed"]
    session_id: str
    question: Optional[str] = None
    note: Optional[str] = None
    result: Optional[RunResponse] = None


class LiveRunStartResponse(BaseModel):
    """Represent live-run startup response.

    What:
        Returns session identifier for a newly spawned background quick run.
    Why:
        Allows clients to subscribe to live status stream using the returned session ID.
    """

    status: Literal["started"]
    session_id: str


class LiveRunCancelRequest(BaseModel):
    """Represent live-run cancel input.

    What:
        Identifies a background live-run session to cancel.
    Why:
        Provides user-controlled interruption for streamed quick runs.
    """

    session_id: str
