from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

from ..identify_search.models import HouseRule, IdentifySearchRequest, IdentifySearchResponse


def _ensure_no_extra(data: Dict[str, Any], allowed: set[str], context: str) -> None:
    extras = set(data) - allowed
    if extras:
        raise ValueError(f"{context} contains unsupported keys: {sorted(extras)}")


def _enum_value(enum_cls, value, field_name: str):
    try:
        return enum_cls(value)
    except ValueError as exc:
        raise ValueError(f"invalid {field_name}: {value}") from exc


class EvaluationDecision(str, Enum):
    SELECT_CANDIDATE = "select_candidate"
    RE_SEARCH_UNSPSC = "re_search_unspsc"
    WEB_SEARCH = "web_search"
    UNABLE_TO_RESOLVE = "unable_to_resolve"


class CandidateSetDiagnosis(str, Enum):
    CORRECT_CANDIDATE_PRESENT = "correct_candidate_present"
    PARENT_PREFERRED_TO_CHILD = "parent_preferred_to_child"
    BEST_AVAILABLE_CANDIDATE_SELECTED = "best_available_candidate_selected"
    CANDIDATES_TOO_GENERAL = "candidates_too_general"
    CANDIDATES_TOO_SPECIFIC = "candidates_too_specific"
    RIGHT_AREA_WRONG_SIBLING = "right_area_wrong_sibling"
    WRONG_SEARCH_DIRECTION = "wrong_search_direction"
    SEMANTIC_FALSE_POSITIVE = "semantic_false_positive"
    ITEM_IDENTITY_UNRESOLVED = "item_identity_unresolved"
    MULTIPLE_PLAUSIBLE_CANDIDATES = "multiple_plausible_candidates"
    NO_VIABLE_CANDIDATE = "no_viable_candidate"
    INSUFFICIENT_EVIDENCE_IMPOSSIBLE = "insufficient_evidence_impossible"


class SelectionSource(str, Enum):
    RETRIEVED_CANDIDATE = "retrieved_candidate"
    HIERARCHY_PARENT = "hierarchy_parent"


class ClassificationFit(str, Enum):
    STRONG = "strong"
    ACCEPTABLE = "acceptable"
    WEAK = "weak"


class ClassificationConfidence(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class WebQueryBasis(str, Enum):
    IDENTIFY_SUGGESTED_QUERY = "identify_suggested_query"
    DESCRIPTION_CLEAN = "description_clean"
    ITEM_RAW_ROW = "item_raw_row"
    SUPPLIER_PLUS_LINE = "supplier_plus_line"
    BRAND_MODEL = "brand_model"
    VISIBLE_IDENTIFIER = "visible_identifier"
    EVALUATION_CONSTRUCTED = "evaluation_constructed"


@dataclass(frozen=True)
class EvaluationSearchQuery:
    query: str
    priority: int

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "EvaluationSearchQuery":
        _ensure_no_extra(data, {"query", "priority"}, "EvaluationSearchQuery")
        query = str(data["query"]).strip()
        priority = int(data["priority"])
        if not query:
            raise ValueError("query is required")
        if priority < 1:
            raise ValueError("priority must be >= 1")
        return cls(query=query, priority=priority)

    def as_dict(self) -> Dict[str, Any]:
        return {"query": self.query, "priority": self.priority}


@dataclass(frozen=True)
class FinalClassification:
    selection_source: SelectionSource
    code: str
    label: str
    source_candidate_code: Optional[str]
    source_candidate_label: Optional[str]
    fit: ClassificationFit
    classification_confidence: ClassificationConfidence
    selection_reason: str
    alternative_rejection_summary: Optional[str]

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "FinalClassification":
        _ensure_no_extra(
            data,
            {
                "selection_source",
                "code",
                "label",
                "source_candidate_code",
                "source_candidate_label",
                "fit",
                "classification_confidence",
                "selection_reason",
                "alternative_rejection_summary",
            },
            "FinalClassification",
        )
        selection_source = _enum_value(SelectionSource, data["selection_source"], "selection_source")
        source_candidate_code = data.get("source_candidate_code")
        source_candidate_label = data.get("source_candidate_label")
        if selection_source is SelectionSource.RETRIEVED_CANDIDATE:
            if source_candidate_code is not None or source_candidate_label is not None:
                raise ValueError("source_candidate_code/source_candidate_label must be null for retrieved_candidate")
        else:
            if not source_candidate_code or not source_candidate_label:
                raise ValueError("source candidate fields are required for hierarchy_parent")
        return cls(
            selection_source=selection_source,
            code=str(data["code"]).strip(),
            label=str(data["label"]).strip(),
            source_candidate_code=source_candidate_code,
            source_candidate_label=source_candidate_label,
            fit=_enum_value(ClassificationFit, data["fit"], "fit"),
            classification_confidence=_enum_value(
                ClassificationConfidence,
                data["classification_confidence"],
                "classification_confidence",
            ),
            selection_reason=str(data["selection_reason"]).strip(),
            alternative_rejection_summary=data.get("alternative_rejection_summary"),
        )

    def as_dict(self) -> Dict[str, Any]:
        return {
            "selection_source": self.selection_source.value,
            "code": self.code,
            "label": self.label,
            "source_candidate_code": self.source_candidate_code,
            "source_candidate_label": self.source_candidate_label,
            "fit": self.fit.value,
            "classification_confidence": self.classification_confidence.value,
            "selection_reason": self.selection_reason,
            "alternative_rejection_summary": self.alternative_rejection_summary,
        }


@dataclass(frozen=True)
class ReSearchUnspsc:
    new_search_direction: str
    queries_to_try: List[EvaluationSearchQuery]
    queries_to_avoid: List[str] = field(default_factory=list)
    candidate_patterns_to_prioritise: List[str] = field(default_factory=list)
    candidate_patterns_to_reject: List[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ReSearchUnspsc":
        _ensure_no_extra(
            data,
            {
                "new_search_direction",
                "queries_to_try",
                "queries_to_avoid",
                "candidate_patterns_to_prioritise",
                "candidate_patterns_to_reject",
            },
            "ReSearchUnspsc",
        )
        queries = [EvaluationSearchQuery.from_dict(value) for value in data["queries_to_try"]]
        priorities = [value.priority for value in queries]
        if sorted(priorities) != list(range(1, len(priorities) + 1)):
            raise ValueError("queries_to_try priorities must be unique integers starting at 1")
        return cls(
            new_search_direction=str(data["new_search_direction"]).strip(),
            queries_to_try=queries,
            queries_to_avoid=[str(value) for value in data.get("queries_to_avoid", [])],
            candidate_patterns_to_prioritise=[
                str(value) for value in data.get("candidate_patterns_to_prioritise", [])
            ],
            candidate_patterns_to_reject=[
                str(value) for value in data.get("candidate_patterns_to_reject", [])
            ],
        )

    def as_dict(self) -> Dict[str, Any]:
        return {
            "new_search_direction": self.new_search_direction,
            "queries_to_try": [value.as_dict() for value in self.queries_to_try],
            "queries_to_avoid": self.queries_to_avoid,
            "candidate_patterns_to_prioritise": self.candidate_patterns_to_prioritise,
            "candidate_patterns_to_reject": self.candidate_patterns_to_reject,
        }


@dataclass(frozen=True)
class WebSearchInstruction:
    query_basis: WebQueryBasis
    query: str

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "WebSearchInstruction":
        _ensure_no_extra(data, {"query_basis", "query"}, "WebSearchInstruction")
        query = str(data["query"]).strip()
        if not query:
            raise ValueError("query is required")
        return cls(
            query_basis=_enum_value(WebQueryBasis, data["query_basis"], "query_basis"),
            query=query,
        )

    def as_dict(self) -> Dict[str, Any]:
        return {
            "query_basis": self.query_basis.value,
            "query": self.query,
        }


@dataclass(frozen=True)
class UnableToResolve:
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "UnableToResolve":
        _ensure_no_extra(data, set(), "UnableToResolve")
        return cls()

    def as_dict(self) -> Dict[str, Any]:
        return {}


@dataclass(frozen=True)
class EvaluateCandidatesRequest:
    identify_search_input: IdentifySearchRequest
    identify_search_output: IdentifySearchResponse
    unspsc_search_output: Dict[str, Any]

    def as_dict(self) -> Dict[str, Any]:
        payload = self.identify_search_input.as_dict()
        payload["identify_search_output"] = self.identify_search_output.as_dict()
        payload["unspsc_search_output"] = self.unspsc_search_output
        return payload


@dataclass(frozen=True)
class EvaluateCandidatesResponse:
    decision: EvaluationDecision
    decision_reason: str
    candidate_set_diagnosis: CandidateSetDiagnosis
    final_classification: Optional[FinalClassification]
    re_search_unspsc: Optional[ReSearchUnspsc]
    web_search: Optional[WebSearchInstruction]
    unable_to_resolve: Optional[UnableToResolve]
    rule_ids_used: List[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "EvaluateCandidatesResponse":
        _ensure_no_extra(
            data,
            {
                "decision",
                "decision_reason",
                "candidate_set_diagnosis",
                "final_classification",
                "re_search_unspsc",
                "web_search",
                "unable_to_resolve",
                "rule_ids_used",
            },
            "EvaluateCandidatesResponse",
        )
        decision = _enum_value(EvaluationDecision, data["decision"], "decision")
        result = cls(
            decision=decision,
            decision_reason=str(data["decision_reason"]).strip(),
            candidate_set_diagnosis=_enum_value(
                CandidateSetDiagnosis,
                data["candidate_set_diagnosis"],
                "candidate_set_diagnosis",
            ),
            final_classification=(
                None
                if data.get("final_classification") is None
                else FinalClassification.from_dict(data["final_classification"])
            ),
            re_search_unspsc=(
                None if data.get("re_search_unspsc") is None else ReSearchUnspsc.from_dict(data["re_search_unspsc"])
            ),
            web_search=None if data.get("web_search") is None else WebSearchInstruction.from_dict(data["web_search"]),
            unable_to_resolve=(
                None if data.get("unable_to_resolve") is None else UnableToResolve.from_dict(data["unable_to_resolve"])
            ),
            rule_ids_used=[str(value) for value in data.get("rule_ids_used", [])],
        )
        return result.validate()

    def validate(self) -> "EvaluateCandidatesResponse":
        populated = [
            self.final_classification is not None,
            self.re_search_unspsc is not None,
            self.web_search is not None,
            self.unable_to_resolve is not None,
        ]
        if sum(populated) != 1:
            raise ValueError("exactly one decision payload must be populated")
        if self.decision is EvaluationDecision.SELECT_CANDIDATE and self.final_classification is None:
            raise ValueError("final_classification is required for select_candidate")
        if self.decision is EvaluationDecision.RE_SEARCH_UNSPSC and self.re_search_unspsc is None:
            raise ValueError("re_search_unspsc is required for re_search_unspsc")
        if self.decision is EvaluationDecision.WEB_SEARCH and self.web_search is None:
            raise ValueError("web_search is required for web_search")
        if self.decision is EvaluationDecision.UNABLE_TO_RESOLVE and self.unable_to_resolve is None:
            raise ValueError("unable_to_resolve is required for unable_to_resolve")
        return self

    def validate_against_request(self, request: EvaluateCandidatesRequest) -> "EvaluateCandidatesResponse":
        if self.re_search_unspsc is not None:
            if len(self.re_search_unspsc.queries_to_try) > request.identify_search_input.global_config.max_unspsc_search_queries:
                raise ValueError("re_search_unspsc exceeds max_unspsc_search_queries")
        if self.web_search is not None and not request.identify_search_input.global_config.web_search_allowed:
            raise ValueError("web_search decision is not allowed by global_config")
        return self

    def as_dict(self) -> Dict[str, Any]:
        return {
            "decision": self.decision.value,
            "decision_reason": self.decision_reason,
            "candidate_set_diagnosis": self.candidate_set_diagnosis.value,
            "final_classification": None if self.final_classification is None else self.final_classification.as_dict(),
            "re_search_unspsc": None if self.re_search_unspsc is None else self.re_search_unspsc.as_dict(),
            "web_search": None if self.web_search is None else self.web_search.as_dict(),
            "unable_to_resolve": None if self.unable_to_resolve is None else self.unable_to_resolve.as_dict(),
            "rule_ids_used": self.rule_ids_used,
        }

