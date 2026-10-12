from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass(frozen=True)
class WebSearchRequest:
    query: str
    supplier_name: Optional[str] = None
    line_item_raw: Optional[str] = None


@dataclass(frozen=True)
class WebSearchResult:
    query: str
    summary: str
    snippets: List[str] = field(default_factory=list)
    metadata: Dict[str, str] = field(default_factory=dict)

    def as_dict(self) -> Dict[str, object]:
        return {
            "query": self.query,
            "summary": self.summary,
            "snippets": self.snippets,
            "metadata": self.metadata,
        }
