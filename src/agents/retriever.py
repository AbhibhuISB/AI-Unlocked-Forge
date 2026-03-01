from __future__ import annotations

from typing import List

from ..models import EvidenceItem
from ..services.search_client import SearchClient


class RetrieverAgent:
    def __init__(self, search: SearchClient) -> None:
        self.search = search

    def gather(self, queries: List[str]) -> List[EvidenceItem]:
        evidence: List[EvidenceItem] = []
        for query in queries:
            evidence.extend(self.search.search(query=query, count=2))
        return evidence
