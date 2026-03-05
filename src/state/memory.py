from __future__ import annotations

from dataclasses import dataclass, field
from typing import List

from ..models import ActivityLogEvent


@dataclass
class SessionMemory:
    """In-memory run ledger for constraints, traces, assumptions, and activity logs.

    Why: Maintains a coherent narrative of iterative decisions for transparency and UI output.
    """

    constraint_pinboard: List[str] = field(default_factory=list)
    assumptions: List[str] = field(default_factory=list)
    activity_log: List[ActivityLogEvent] = field(default_factory=list)
    confidence_trace: List[float] = field(default_factory=list)
    quality_trace: List[float] = field(default_factory=list)

    def log(self, step: str, message: str) -> None:
        """Append a new activity event in chronological order.

        Why: Centralized logging keeps UI behavior and debugging consistent across run modes.
        """
        self.activity_log.append(ActivityLogEvent(step=step, message=message))
