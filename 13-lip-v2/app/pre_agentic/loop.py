from __future__ import annotations

from dataclasses import asdict
from typing import Optional

from .models import PreAgenticRequest, PreAgenticResult, ResolvedBy
from .normalize import build_lookup_hash, normalize_line_item, normalize_supplier
from ..persistence.repository import LineItemSolutionRepository, NonUnspscRuleRepository


class PreAgenticLoop:
    def __init__(
        self,
        solution_repo: LineItemSolutionRepository,
        rule_repo: NonUnspscRuleRepository,
    ):
        self.solution_repo = solution_repo
        self.rule_repo = rule_repo

    def run(self, request: PreAgenticRequest) -> Optional[PreAgenticResult]:
        supplier_normalized = normalize_supplier(request.supplier_raw)
        line_item_normalized = normalize_line_item(request.line_item_raw)
        lookup_hash = build_lookup_hash(supplier_normalized, line_item_normalized)

        unstable_hit = self.solution_repo.find_unstable(lookup_hash=lookup_hash, org_id=request.org_id)
        if unstable_hit is not None:
            return PreAgenticResult(
                resolved_by=ResolvedBy.UNSTABLE_LOOKUP,
                status_code=unstable_hit.status_code,
                policy_code=unstable_hit.policy_code,
                unspsc_code=unstable_hit.unspsc_code,
                unspsc_level=unstable_hit.unspsc_level,
                lookup_hash=lookup_hash,
                reasoning={
                    "matched_row_id": unstable_hit.id,
                    "source_type": unstable_hit.source_type,
                    "stable": unstable_hit.stable,
                },
                selected_label=(unstable_hit.reasoning or {}).get("selected_label"),
            )

        stable_hit = self.solution_repo.find_stable(lookup_hash=lookup_hash)
        if stable_hit is not None:
            return PreAgenticResult(
                resolved_by=ResolvedBy.STABLE_LOOKUP,
                status_code=stable_hit.status_code,
                policy_code=stable_hit.policy_code,
                unspsc_code=stable_hit.unspsc_code,
                unspsc_level=stable_hit.unspsc_level,
                lookup_hash=lookup_hash,
                reasoning={
                    "matched_row_id": stable_hit.id,
                    "source_type": stable_hit.source_type,
                    "stable": stable_hit.stable,
                },
                selected_label=(stable_hit.reasoning or {}).get("selected_label"),
            )

        rule_hit = self.rule_repo.find_first_match(request.line_item_raw)
        if rule_hit is not None:
            return PreAgenticResult(
                resolved_by=ResolvedBy.NON_UNSPSC_RULE,
                status_code=rule_hit.status_code,
                policy_code=rule_hit.policy_code,
                unspsc_code=rule_hit.fallback_unspsc_code,
                unspsc_level=rule_hit.fallback_unspsc_level,
                lookup_hash=lookup_hash,
                reasoning={
                    "matched_rule_id": rule_hit.id,
                    "matched_rule_label": rule_hit.label,
                    "rule_order": rule_hit.rule_order,
                },
                selected_label=rule_hit.label,
            )

        return None

    @staticmethod
    def serialize(result: PreAgenticResult) -> dict:
        payload = asdict(result)
        payload["resolved_by"] = result.resolved_by.value
        return payload
