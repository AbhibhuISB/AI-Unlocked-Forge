from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, List

from ..models import ActivityLogEvent


@dataclass
class SessionMemory:
    """Store mutable in-memory run state.

    What:
        Tracks constraints, assumptions, activity log, and confidence/quality traces.
    Why:
        Preserves run continuity and observability across iterative orchestration steps.
    """

    constraint_pinboard: List[str] = field(default_factory=list)
    assumptions: List[str] = field(default_factory=list)
    activity_log: List[ActivityLogEvent] = field(default_factory=list)
    confidence_trace: List[float] = field(default_factory=list)
    quality_trace: List[float] = field(default_factory=list)
    on_log: Callable[[ActivityLogEvent], None] | None = None

    def log(self, step: str, message: str) -> None:
        """Append an activity event.

        What:
            Adds one timestamp-ordered `ActivityLogEvent` equivalent entry.
        Why:
            Centralized logging keeps UI reporting and debugging consistent.
        """
        event = ActivityLogEvent(step=step, message=message)
        self.activity_log.append(event)
        if self.on_log is not None:
            self.on_log(event)
