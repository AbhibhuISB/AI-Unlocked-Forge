from __future__ import annotations

from typing import List

from ..models import EvidenceItem
from ..services.search_client import SearchClient


class RetrieverAgent:
    """Retrieve external evidence for unresolved planning questions.

    What:
        Runs search queries and returns normalized `EvidenceItem` objects.
    Why:
        Isolates retrieval concerns from planning/execution so search strategy can evolve independently.
    """

    def __init__(self, search: SearchClient) -> None:
        """Initialize retriever dependencies.

        What:
            Stores the search client used to execute web queries.
        Why:
            Keeps network/client wiring outside core retrieval logic.
        """
        self.search = search

    def gather(self, queries: List[str]) -> List[EvidenceItem]:
        """Collect evidence for a list of search queries.

        What:
            Executes each query and merges all retrieved items into a single list.
        Why:
            Provides planner/executor with source-backed context for uncertain areas.
        """
        evidence: List[EvidenceItem] = []
        for query in queries:
            evidence.extend(self.search.search(query=query, count=2))
        return evidence
