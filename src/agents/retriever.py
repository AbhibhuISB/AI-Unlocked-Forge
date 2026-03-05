from __future__ import annotations

from typing import List

from ..models import EvidenceItem
from ..services.search_client import SearchClient


class RetrieverAgent:
    """Retrieve supporting evidence snippets for planner uncertainty points.

    Why: Keeps external evidence lookup isolated from planning and execution logic,
    so search strategy can evolve independently.
    """

    def __init__(self, search: SearchClient) -> None:
        """Inject search client used for web evidence retrieval."""
        self.search = search

    def gather(self, queries: List[str]) -> List[EvidenceItem]:
        """Run each query and merge retrieved evidence items into one list.

        Why: Planner confidence is improved when unresolved questions are backed by
        explicit source snippets.
        """
        evidence: List[EvidenceItem] = []
        for query in queries:
            evidence.extend(self.search.search(query=query, count=2))
        return evidence
