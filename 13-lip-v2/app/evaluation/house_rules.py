from __future__ import annotations

import re
from typing import Any, Optional

from ..identify_search.models import ItemNature
from .models import EvaluateCandidatesRequest, EvaluateCandidatesResponse


SERVICE_PATTERN = re.compile(r"\b(service|maintenance|repair|installation|fitting|labou?r|support|cleaning|training)\b", re.I)
RENTAL_PATTERN = re.compile(r"\b(rental|rent|hire|lease|leasing)\b", re.I)
SOFTWARE_PATTERN = re.compile(r"\b(software|saas|subscription|licen[cs]e|cloud|hosting|microsoft 365|office 365)\b", re.I)
RAW_MATERIAL_PATTERN = re.compile(r"\b(raw|bulk|scrap|waste|fabric|fibre|fiber|ore|sand|soil|alloy|timber)\b", re.I)
MIXED_LINE_PATTERN = re.compile(r"\b(labou?r and materials|materials and labou?r|supply and install|supply & install)\b", re.I)
PART_ACCESSORY_PATTERN = re.compile(
    r"\b(blade|filter|toner|cartridge|case|cover|battery|charger|cable|belt|seal|gasket|spare|part|accessory|kit)\b",
    re.I,
)
COMPATIBILITY_PATTERN = re.compile(r"\bfor\s+[a-z0-9]", re.I)


def apply_house_rule_guards(
    request: EvaluateCandidatesRequest,
    response: EvaluateCandidatesResponse,
) -> EvaluateCandidatesResponse:
    payload = response.as_dict()
    item_nature = request.identify_search_output.item_hypothesis.item_nature
    selected = _selected_candidate_context(request, payload)

    if response.decision.value == "select_candidate" and selected is not None:
        label = (selected.get("label") or "").lower()
        line_text = _combined_line_text(request).lower()

        specificity_override = _specificity_parent_override(payload, selected, line_text)
        if specificity_override is not None:
            return EvaluateCandidatesResponse.from_dict(specificity_override).validate_against_request(request)

        if item_nature is ItemNature.SERVICE and not SERVICE_PATTERN.search(label):
            return _build_research_override(
                request=request,
                payload=payload,
                rule_ids=["HR007", "HR008"],
                diagnosis="wrong_search_direction",
                direction="Re-search toward the service being purchased rather than the physical goods involved.",
                queries=_service_queries(request),
            )
        if item_nature is ItemNature.RENTAL_OR_HIRE and not RENTAL_PATTERN.search(label):
            return _build_research_override(
                request=request,
                payload=payload,
                rule_ids=["HR009"],
                diagnosis="wrong_search_direction",
                direction="Re-search toward rental, hire, or lease of the underlying item rather than purchase.",
                queries=_suffix_queries(request, "rental"),
            )
        if item_nature is ItemNature.SOFTWARE_OR_DIGITAL and not SOFTWARE_PATTERN.search(label):
            return _build_research_override(
                request=request,
                payload=payload,
                rule_ids=["HR010", "HR011"],
                diagnosis="wrong_search_direction",
                direction="Re-search toward software, SaaS, subscription, or licence rather than physical goods or public fees.",
                queries=_software_queries(request),
            )
        if _is_raw_material_trap(selected, line_text):
            return _build_research_override(
                request=request,
                payload=payload,
                rule_ids=["HR019", "HR020"],
                diagnosis="semantic_false_positive",
                direction="Re-search away from raw-material areas unless the line is clearly purchasing raw or bulk material.",
                queries=_finished_product_queries(request),
            )
        if _is_part_or_accessory_mismatch(selected, line_text):
            return _build_research_override(
                request=request,
                payload=payload,
                rule_ids=["HR004", "HR005", "HR006"],
                diagnosis="wrong_search_direction",
                direction="Re-search toward the functional component, spare, accessory, or compatible item being purchased rather than the main equipment.",
                queries=_part_queries(request),
            )
        if _is_mixed_line_without_safe_parent(selected, line_text):
            return _build_research_override(
                request=request,
                payload=payload,
                rule_ids=["HR012", "HR013"],
                diagnosis="multiple_plausible_candidates",
                direction="Re-search toward a broader parent or bundle purpose because the line mixes labour, materials, or multiple unrelated deliverables.",
                queries=_mixed_line_queries(request),
            )

    return response


def _build_research_override(
    *,
    request: EvaluateCandidatesRequest,
    payload: dict[str, Any],
    rule_ids: list[str],
    diagnosis: str,
    direction: str,
    queries: list[str],
) -> EvaluateCandidatesResponse:
    max_queries = request.identify_search_input.global_config.max_unspsc_search_queries
    unique_queries = []
    seen: set[str] = set()
    for value in queries:
        normalized = " ".join(value.lower().split())
        if not normalized or normalized in seen:
            continue
        unique_queries.append(value)
        seen.add(normalized)
        if len(unique_queries) >= max_queries:
            break
    payload["decision"] = "re_search_unspsc"
    payload["candidate_set_diagnosis"] = diagnosis
    payload["decision_reason"] = direction
    payload["final_classification"] = None
    payload["web_search"] = None
    payload["unable_to_resolve"] = None
    payload["re_search_unspsc"] = {
        "new_search_direction": direction,
        "queries_to_try": [{"query": query, "priority": index + 1} for index, query in enumerate(unique_queries)],
        "queries_to_avoid": [],
        "candidate_patterns_to_prioritise": [],
        "candidate_patterns_to_reject": [],
    }
    payload["rule_ids_used"] = sorted(set((payload.get("rule_ids_used") or []) + rule_ids))
    return EvaluateCandidatesResponse.from_dict(payload).validate_against_request(request)


def _selected_candidate_context(
    request: EvaluateCandidatesRequest,
    payload: dict[str, Any],
) -> Optional[dict[str, Any]]:
    final_classification = payload.get("final_classification") or {}
    code = final_classification.get("code")
    if not code:
        return None
    for candidate in request.unspsc_search_output.get("candidates", []):
        if candidate.get("code") == code:
            return candidate
        for level_name in ("segment", "family", "class", "commodity"):
            node = (candidate.get("hierarchy_path") or {}).get(level_name)
            if isinstance(node, dict) and node.get("code") == code:
                merged = dict(candidate)
                merged["label"] = node.get("label")
                merged["level"] = level_name
                merged["segment_code"] = (candidate.get("hierarchy_path") or {}).get("segment", {}).get("code")
                return merged
    return None


def _combined_line_text(request: EvaluateCandidatesRequest) -> str:
    target = request.identify_search_input.target_line
    return " ".join(
        value
        for value in [
            target.item_raw_row,
            target.description_clean or "",
        ]
        if value
    )


def _base_identity(request: EvaluateCandidatesRequest) -> str:
    primary = request.identify_search_output.item_hypothesis.primary_identity
    if primary:
        return str(primary).strip()
    return request.identify_search_input.target_line.item_raw_row.strip()


def _service_queries(request: EvaluateCandidatesRequest) -> list[str]:
    base = _base_identity(request)
    return [f"{base} service", f"{base} maintenance service", base]


def _software_queries(request: EvaluateCandidatesRequest) -> list[str]:
    base = _base_identity(request)
    return [f"{base} software", f"{base} subscription", f"{base} licence"]


def _suffix_queries(request: EvaluateCandidatesRequest, suffix: str) -> list[str]:
    base = _base_identity(request)
    return [f"{base} {suffix}", base]


def _finished_product_queries(request: EvaluateCandidatesRequest) -> list[str]:
    base = _base_identity(request)
    return [base, request.identify_search_input.target_line.item_raw_row.strip()]


def _part_queries(request: EvaluateCandidatesRequest) -> list[str]:
    base = _base_identity(request)
    raw = request.identify_search_input.target_line.item_raw_row.strip()
    return [raw, base, f"{base} part"]


def _mixed_line_queries(request: EvaluateCandidatesRequest) -> list[str]:
    base = _base_identity(request)
    raw = request.identify_search_input.target_line.item_raw_row.strip()
    return [raw, base, "general service or supply"]


def _is_raw_material_trap(candidate: dict[str, Any], line_text: str) -> bool:
    segment_code = candidate.get("segment_code")
    label = str(candidate.get("label") or "")
    if not segment_code or not str(segment_code).startswith("11"):
        return False
    if RAW_MATERIAL_PATTERN.search(line_text):
        return False
    return bool(RAW_MATERIAL_PATTERN.search(label))


def _specificity_parent_override(
    payload: dict[str, Any],
    candidate: dict[str, Any],
    line_text: str,
) -> Optional[dict[str, Any]]:
    final_classification = payload.get("final_classification") or {}
    if final_classification.get("selection_source") != "retrieved_candidate":
        return None
    if str(candidate.get("level") or "").lower() != "commodity":
        return None
    hierarchy_path = candidate.get("hierarchy_path") or {}
    class_node = hierarchy_path.get("class")
    if not isinstance(class_node, dict):
        return None
    label = str(candidate.get("label") or "").lower()
    if SERVICE_PATTERN.search(line_text):
        return None
    if _token_overlap(label, line_text) <= 1:
        return _build_parent_selection_override(
            payload=payload,
            parent_code=str(class_node.get("code") or ""),
            parent_label=str(class_node.get("label") or ""),
            source_candidate_code=str(candidate.get("code") or ""),
            source_candidate_label=str(candidate.get("label") or ""),
            rule_ids=["HR017", "HR018"],
            diagnosis="parent_preferred_to_child",
            reason="Selected commodity includes unsupported detail, so the supported parent is safer than over-classifying.",
        )
    return None


def _build_parent_selection_override(
    *,
    payload: dict[str, Any],
    parent_code: str,
    parent_label: str,
    source_candidate_code: str,
    source_candidate_label: str,
    rule_ids: list[str],
    diagnosis: str,
    reason: str,
) -> dict[str, Any]:
    updated = dict(payload)
    updated["decision"] = "select_candidate"
    updated["decision_reason"] = reason
    updated["candidate_set_diagnosis"] = diagnosis
    updated["re_search_unspsc"] = None
    updated["web_search"] = None
    updated["unable_to_resolve"] = None
    updated["final_classification"] = {
        "selection_source": "hierarchy_parent",
        "code": parent_code,
        "label": parent_label,
        "source_candidate_code": source_candidate_code,
        "source_candidate_label": source_candidate_label,
        "fit": "acceptable",
        "classification_confidence": "medium",
        "selection_reason": reason,
        "alternative_rejection_summary": "The returned commodity included unsupported detail beyond the line evidence.",
    }
    updated["rule_ids_used"] = sorted(set((updated.get("rule_ids_used") or []) + rule_ids))
    return updated


def _is_part_or_accessory_mismatch(candidate: dict[str, Any], line_text: str) -> bool:
    if not PART_ACCESSORY_PATTERN.search(line_text):
        return False
    label = str(candidate.get("label") or "")
    if PART_ACCESSORY_PATTERN.search(label):
        return False
    return True


def _is_mixed_line_without_safe_parent(candidate: dict[str, Any], line_text: str) -> bool:
    if not MIXED_LINE_PATTERN.search(line_text):
        return False
    level = str(candidate.get("level") or "").lower()
    return level == "commodity"


def _token_overlap(a: str, b: str) -> int:
    a_tokens = {token for token in re.findall(r"[a-z0-9]+", a.lower()) if len(token) > 2}
    b_tokens = {token for token in re.findall(r"[a-z0-9]+", b.lower()) if len(token) > 2}
    return len(a_tokens & b_tokens)
