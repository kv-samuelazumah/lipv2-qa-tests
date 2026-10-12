from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class ResolvedBy(str, Enum):
    UNSTABLE_LOOKUP = "UNSTABLE_LOOKUP"
    STABLE_LOOKUP = "STABLE_LOOKUP"
    NON_UNSPSC_RULE = "NON_UNSPSC_RULE"
    AGENTIC_LOOP = "AGENTIC_LOOP"


@dataclass(frozen=True)
class PreAgenticRequest:
    org_id: str
    supplier_raw: str
    line_item_raw: str


@dataclass(frozen=True)
class LineItemSolution:
    id: str
    lookup_hash: str
    supplier_raw: str
    supplier_normalized: str
    line_item_raw: str
    line_item_normalized: str
    solved_for: List[str] = field(default_factory=list)
    stable: bool = False
    unspsc_code: Optional[str] = None
    unspsc_level: Optional[str] = None
    policy_code: Optional[str] = None
    status_code: str = "SOLVED"
    source_type: str = "AGENTIC"
    reasoning: Dict[str, Any] = field(default_factory=dict)

    def recompute_stable(self) -> "LineItemSolution":
        return LineItemSolution(
            id=self.id,
            lookup_hash=self.lookup_hash,
            supplier_raw=self.supplier_raw,
            supplier_normalized=self.supplier_normalized,
            line_item_raw=self.line_item_raw,
            line_item_normalized=self.line_item_normalized,
            solved_for=list(self.solved_for),
            stable=len(set(self.solved_for)) >= 3,
            unspsc_code=self.unspsc_code,
            unspsc_level=self.unspsc_level,
            policy_code=self.policy_code,
            status_code=self.status_code,
            source_type=self.source_type,
            reasoning=dict(self.reasoning),
        )


@dataclass(frozen=True)
class NonUnspscRule:
    id: str
    rule_order: int
    label: str
    pattern: str
    policy_code: str
    status_code: str
    fallback_unspsc_code: Optional[str] = None
    fallback_unspsc_level: Optional[str] = None
    active: bool = True


@dataclass(frozen=True)
class PreAgenticResult:
    resolved_by: ResolvedBy
    status_code: str
    policy_code: Optional[str]
    unspsc_code: Optional[str]
    unspsc_level: Optional[str]
    lookup_hash: str
    reasoning: Dict[str, Any]
    selected_label: Optional[str] = None
