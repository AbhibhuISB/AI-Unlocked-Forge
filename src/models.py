from __future__ import annotations

from typing import List, Literal, Optional
from pydantic import BaseModel, Field


Severity = Literal["critical", "major", "minor"]


class SessionConfig(BaseModel):
    strategy_threshold: float = Field(default=0.80, ge=0.1, le=1.0)
    quality_threshold: float = Field(default=0.85, ge=0.1, le=1.0)
    max_iterations: int = Field(default=4, ge=1, le=10)
    output_format: str = Field(default="markdown")


class RunRequest(BaseModel):
    goal: str = Field(min_length=5)
    constraints: List[str] = Field(default_factory=list)
    config: SessionConfig = Field(default_factory=SessionConfig)


class EvidenceItem(BaseModel):
    title: str
    url: str
    snippet: str
    source_credibility: float = Field(ge=0.0, le=1.0)


class PlannerOutput(BaseModel):
    plan_summary: str
    subtasks: List[str]
    missing_info_queries: List[str]
    confidence: float = Field(ge=0.0, le=1.0)


class ExecutorDraft(BaseModel):
    draft: str


class Fault(BaseModel):
    id: str
    severity: Severity
    issue: str
    patch_instruction: str


class ReviewOutput(BaseModel):
    quality_score: float = Field(ge=0.0, le=1.0)
    faults: List[Fault] = Field(default_factory=list)


class ActivityLogEvent(BaseModel):
    step: str
    message: str


class RunResponse(BaseModel):
    final_output: str
    assumptions: List[str]
    activity_log: List[ActivityLogEvent]
    iterations: int
    ended_reason: str
    confidence_trace: List[float]
    quality_trace: List[float]
    evidence_used: List[EvidenceItem]


class InteractiveContinueRequest(BaseModel):
    session_id: str
    user_comment: Optional[str] = None
    skip: bool = False


class InteractiveCancelRequest(BaseModel):
    session_id: str


class InteractiveRunResponse(BaseModel):
    status: Literal["needs_input", "completed"]
    session_id: str
    question: Optional[str] = None
    note: Optional[str] = None
    result: Optional[RunResponse] = None
