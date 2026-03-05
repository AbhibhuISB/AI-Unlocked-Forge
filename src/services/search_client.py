from __future__ import annotations

import os
from typing import List

import httpx

from ..models import EvidenceItem


class SearchClient:
    """Thin Bing Search wrapper that returns normalized evidence items.

    Why: Isolates vendor-specific API calls and lets retriever consume a stable model.
    """

    def __init__(self) -> None:
        """Load search credentials and endpoint from environment variables."""
        self.api_key = os.getenv("BING_SEARCH_API_KEY", "")
        self.endpoint = os.getenv("BING_SEARCH_ENDPOINT", "https://api.bing.microsoft.com/v7.0/search")

    def search(self, query: str, count: int = 3) -> List[EvidenceItem]:
        """Execute a web query and convert results into `EvidenceItem` objects.

        Why: Standardized evidence records simplify downstream prompting and logging.
        """
        if not self.api_key:
            # Deterministic placeholder keeps the pipeline functional without hard failure.
            return [
                EvidenceItem(
                    title="Retriever key missing",
                    url="",
                    snippet=f"No Bing key configured. Query not executed: {query}",
                    source_credibility=0.2,
                )
            ]

        headers = {"Ocp-Apim-Subscription-Key": self.api_key}
        params = {"q": query, "count": count, "responseFilter": "Webpages"}

        with httpx.Client(timeout=15) as client:
            response = client.get(self.endpoint, headers=headers, params=params)
            response.raise_for_status()
            payload = response.json()

        items = payload.get("webPages", {}).get("value", [])
        results: List[EvidenceItem] = []
        for item in items:
            results.append(
                EvidenceItem(
                    title=item.get("name", "Untitled"),
                    url=item.get("url", ""),
                    snippet=item.get("snippet", ""),
                    source_credibility=0.7,
                )
            )
        return results
