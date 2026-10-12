from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict

from ..evaluation.models import EvaluateCandidatesResponse
from ..identify_search.models import IdentifySearchRequest, IdentifySearchResponse
from ..web_search.models import WebSearchResult


@dataclass(frozen=True)
class WebReidentifyRequest:
    identify_search_input: IdentifySearchRequest
    identify_search_output: IdentifySearchResponse
    evaluation_output: EvaluateCandidatesResponse
    web_search_result: WebSearchResult

    def as_dict(self) -> Dict[str, Any]:
        return {
            "identify_search_input": self.identify_search_input.as_dict(),
            "identify_search_output": self.identify_search_output.as_dict(),
            "evaluation_output": self.evaluation_output.as_dict(),
            "web_search_result": self.web_search_result.as_dict(),
        }
