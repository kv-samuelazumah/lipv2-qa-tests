from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass(frozen=True)
class LineItemPipelineInput:
    org_id: str
    supplier_raw: str
    line_item_raw: str
    cleaned_line_item: Optional[str] = None
    unit_of_measure_raw: Optional[str] = None
    quantity: Optional[float] = None
    unit_price: Optional[float] = None
    line_subtotal: Optional[float] = None
    unspsc_ready_invoice_description: Optional[str] = None
    supplier_sic_label: Optional[str] = None
    buyer_sic_label: Optional[str] = None
    house_rules: List[Dict[str, str]] = field(default_factory=list)
    max_unspsc_search_queries: int = 6
    max_candidates_per_query: int = 10
    max_candidates_total: int = 30
    web_search_allowed: bool = True


@dataclass(frozen=True)
class LineItemPipelineResult:
    stage: str
    pre_agentic_result: Optional[Dict[str, Any]]
    identify_search_result: Optional[Dict[str, Any]]
    retrieval_result: Optional[Dict[str, Any]]
    evaluation_result: Optional[Dict[str, Any]] = None
    final_result: Optional[Dict[str, Any]] = None

    def as_dict(self) -> Dict[str, Any]:
        return {
            "stage": self.stage,
            "pre_agentic_result": self.pre_agentic_result,
            "identify_search_result": self.identify_search_result,
            "retrieval_result": self.retrieval_result,
            "evaluation_result": self.evaluation_result,
            "final_result": self.final_result,
        }
