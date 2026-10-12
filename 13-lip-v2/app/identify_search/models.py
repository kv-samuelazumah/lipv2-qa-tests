from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class UnderstandingConfidence(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class ItemNature(str, Enum):
    PHYSICAL_GOOD = "physical_good"
    SERVICE = "service"
    SERVICE_WITH_SUPPORTING_GOODS = "service_with_supporting_goods"
    SOFTWARE_OR_DIGITAL = "software_or_digital"
    RENTAL_OR_HIRE = "rental_or_hire"
    FEE_OR_CHARGE = "fee_or_charge"
    MIXED_BUNDLE = "mixed_bundle"
    UNKNOWN = "unknown"


class ContextDependency(str, Enum):
    NONE = "none"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class QueryType(str, Enum):
    SPECIFIC = "specific"
    CONTEXTUAL = "contextual"
    BROAD = "broad"


class WarningCategory(str, Enum):
    GENERIC_OR_WEAK_DESCRIPTION = "generic_or_weak_description"
    UNRESOLVED_IDENTIFIER = "unresolved_identifier"
    ITEM_NATURE_AMBIGUITY = "item_nature_ambiguity"
    BUNDLE_COMPLEXITY = "bundle_complexity"
    CONTEXT_DEPENDENT_IDENTITY = "context_dependent_identity"
    COMMERCIAL_INFERENCE_USED = "commercial_inference_used"
    TEXT_QUALITY_ISSUE = "text_quality_issue"
    PRICE_DISAMBIGUATION = "price_disambiguation"
    OTHER = "other"


class EvidenceType(str, Enum):
    UNSPSC_READY_INVOICE_DESCRIPTION = "unspsc_ready_invoice_description"
    SUPPLIER_NAME = "supplier_name"
    SUPPLIER_SIC_LABEL = "supplier_sic_label"
    BUYER_SIC_LABEL = "buyer_sic_label"
    HOUSE_RULE = "house_rule"


class TargetLineField(str, Enum):
    ITEM_RAW_ROW = "item_raw_row"
    DESCRIPTION_CLEAN = "description_clean"
    UNIT_OF_MEASURE_RAW = "unit_of_measure_raw"
    QUANTITY = "quantity"
    UNIT_PRICE = "unit_price"
    LINE_SUBTOTAL = "line_subtotal"


def _ensure_no_extra(data: Dict[str, Any], allowed: set[str], context: str) -> None:
    extras = set(data) - allowed
    if extras:
        raise ValueError(f"{context} contains unsupported keys: {sorted(extras)}")


def _enum_value(enum_cls, value, field_name: str):
    try:
        return enum_cls(value)
    except ValueError as exc:
        raise ValueError(f"invalid {field_name}: {value}") from exc


@dataclass(frozen=True)
class NumericValue:
    value: Optional[float] = None

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "NumericValue":
        _ensure_no_extra(data, {"value"}, "NumericValue")
        return cls(value=data.get("value"))

    def as_dict(self) -> Dict[str, Any]:
        return {"value": self.value}


@dataclass(frozen=True)
class GlobalConfig:
    max_unspsc_search_queries: int
    web_search_allowed: bool

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "GlobalConfig":
        _ensure_no_extra(data, {"max_unspsc_search_queries", "web_search_allowed"}, "GlobalConfig")
        max_queries = int(data["max_unspsc_search_queries"])
        if max_queries < 1 or max_queries > 20:
            raise ValueError("max_unspsc_search_queries must be between 1 and 20")
        return cls(
            max_unspsc_search_queries=max_queries,
            web_search_allowed=bool(data["web_search_allowed"]),
        )

    def as_dict(self) -> Dict[str, Any]:
        return {
            "max_unspsc_search_queries": self.max_unspsc_search_queries,
            "web_search_allowed": self.web_search_allowed,
        }


@dataclass(frozen=True)
class TargetLine:
    item_raw_row: str
    description_clean: Optional[str] = None
    unit_of_measure_raw: Optional[str] = None
    quantity: NumericValue = field(default_factory=NumericValue)
    unit_price: NumericValue = field(default_factory=NumericValue)
    line_subtotal: NumericValue = field(default_factory=NumericValue)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TargetLine":
        _ensure_no_extra(
            data,
            {
                "item_raw_row",
                "description_clean",
                "unit_of_measure_raw",
                "quantity",
                "unit_price",
                "line_subtotal",
            },
            "TargetLine",
        )
        item_raw_row = str(data["item_raw_row"]).strip()
        if not item_raw_row:
            raise ValueError("item_raw_row is required")
        return cls(
            item_raw_row=item_raw_row,
            description_clean=data.get("description_clean"),
            unit_of_measure_raw=data.get("unit_of_measure_raw"),
            quantity=NumericValue.from_dict(data.get("quantity", {})),
            unit_price=NumericValue.from_dict(data.get("unit_price", {})),
            line_subtotal=NumericValue.from_dict(data.get("line_subtotal", {})),
        )

    def as_dict(self) -> Dict[str, Any]:
        return {
            "item_raw_row": self.item_raw_row,
            "description_clean": self.description_clean,
            "unit_of_measure_raw": self.unit_of_measure_raw,
            "quantity": self.quantity.as_dict(),
            "unit_price": self.unit_price.as_dict(),
            "line_subtotal": self.line_subtotal.as_dict(),
        }


@dataclass(frozen=True)
class InvoiceContext:
    supplier_name: Optional[str] = None
    unspsc_ready_invoice_description: Optional[str] = None
    supplier_sic_label: Optional[str] = None
    buyer_sic_label: Optional[str] = None

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "InvoiceContext":
        _ensure_no_extra(
            data,
            {
                "supplier_name",
                "unspsc_ready_invoice_description",
                "supplier_sic_label",
                "buyer_sic_label",
            },
            "InvoiceContext",
        )
        return cls(
            supplier_name=data.get("supplier_name"),
            unspsc_ready_invoice_description=data.get("unspsc_ready_invoice_description"),
            supplier_sic_label=data.get("supplier_sic_label"),
            buyer_sic_label=data.get("buyer_sic_label"),
        )

    def as_dict(self) -> Dict[str, Any]:
        return {
            "supplier_name": self.supplier_name,
            "unspsc_ready_invoice_description": self.unspsc_ready_invoice_description,
            "supplier_sic_label": self.supplier_sic_label,
            "buyer_sic_label": self.buyer_sic_label,
        }


@dataclass(frozen=True)
class HouseRule:
    rule_name: str
    rule: str

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "HouseRule":
        _ensure_no_extra(data, {"rule_name", "rule"}, "HouseRule")
        if not data.get("rule_name") or not data.get("rule"):
            raise ValueError("HouseRule requires rule_name and rule")
        return cls(rule_name=str(data["rule_name"]), rule=str(data["rule"]))

    def as_dict(self) -> Dict[str, Any]:
        return {"rule_name": self.rule_name, "rule": self.rule}


@dataclass(frozen=True)
class IdentifySearchRequest:
    global_config: GlobalConfig
    target_line: TargetLine
    invoice_context: InvoiceContext
    house_rules: List[HouseRule] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "IdentifySearchRequest":
        _ensure_no_extra(data, {"global_config", "target_line", "invoice_context", "house_rules"}, "IdentifySearchRequest")
        return cls(
            global_config=GlobalConfig.from_dict(data["global_config"]),
            target_line=TargetLine.from_dict(data["target_line"]),
            invoice_context=InvoiceContext.from_dict(data["invoice_context"]),
            house_rules=[HouseRule.from_dict(item) for item in data.get("house_rules", [])],
        )

    def as_dict(self) -> Dict[str, Any]:
        return {
            "global_config": self.global_config.as_dict(),
            "target_line": self.target_line.as_dict(),
            "invoice_context": self.invoice_context.as_dict(),
            "house_rules": [rule.as_dict() for rule in self.house_rules],
        }


@dataclass(frozen=True)
class Interpretation:
    what_it_is: Optional[str] = None
    what_it_is_not: List[str] = field(default_factory=list)
    ambiguity: List[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Interpretation":
        _ensure_no_extra(data, {"what_it_is", "what_it_is_not", "ambiguity"}, "Interpretation")
        return cls(
            what_it_is=data.get("what_it_is"),
            what_it_is_not=[str(value) for value in data.get("what_it_is_not", [])],
            ambiguity=[str(value) for value in data.get("ambiguity", [])],
        )

    def as_dict(self) -> Dict[str, Any]:
        return {
            "what_it_is": self.what_it_is,
            "what_it_is_not": self.what_it_is_not,
            "ambiguity": self.ambiguity,
        }


@dataclass(frozen=True)
class ItemHypothesis:
    understanding_confidence: UnderstandingConfidence
    item_nature: ItemNature
    primary_identity: Optional[str]
    identity_explanation: str
    interpretation: Interpretation

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ItemHypothesis":
        _ensure_no_extra(
            data,
            {
                "understanding_confidence",
                "item_nature",
                "primary_identity",
                "identity_explanation",
                "interpretation",
            },
            "ItemHypothesis",
        )
        explanation = str(data["identity_explanation"]).strip()
        if not explanation:
            raise ValueError("identity_explanation is required")
        return cls(
            understanding_confidence=_enum_value(
                UnderstandingConfidence,
                data["understanding_confidence"],
                "understanding_confidence",
            ),
            item_nature=_enum_value(ItemNature, data["item_nature"], "item_nature"),
            primary_identity=data.get("primary_identity"),
            identity_explanation=explanation,
            interpretation=Interpretation.from_dict(data["interpretation"]),
        )

    def as_dict(self) -> Dict[str, Any]:
        return {
            "understanding_confidence": self.understanding_confidence.value,
            "item_nature": self.item_nature.value,
            "primary_identity": self.primary_identity,
            "identity_explanation": self.identity_explanation,
            "interpretation": self.interpretation.as_dict(),
        }


@dataclass(frozen=True)
class OtherEvidenceUsed:
    evidence_type: EvidenceType
    evidence_text: str
    used_for: str

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "OtherEvidenceUsed":
        _ensure_no_extra(data, {"evidence_type", "evidence_text", "used_for"}, "OtherEvidenceUsed")
        evidence_text = str(data["evidence_text"]).strip()
        used_for = str(data["used_for"]).strip()
        if not evidence_text or not used_for:
            raise ValueError("OtherEvidenceUsed requires evidence_text and used_for")
        return cls(
            evidence_type=_enum_value(EvidenceType, data["evidence_type"], "evidence_type"),
            evidence_text=evidence_text,
            used_for=used_for,
        )

    def as_dict(self) -> Dict[str, Any]:
        return {
            "evidence_type": self.evidence_type.value,
            "evidence_text": self.evidence_text,
            "used_for": self.used_for,
        }


@dataclass(frozen=True)
class EvidenceUsage:
    target_line_fields_used: List[TargetLineField]
    other_evidence_used: List[OtherEvidenceUsed]
    context_dependency: ContextDependency

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "EvidenceUsage":
        _ensure_no_extra(
            data,
            {"target_line_fields_used", "other_evidence_used", "context_dependency"},
            "EvidenceUsage",
        )
        return cls(
            target_line_fields_used=[
                _enum_value(TargetLineField, value, "target_line_fields_used")
                for value in data.get("target_line_fields_used", [])
            ],
            other_evidence_used=[
                OtherEvidenceUsed.from_dict(value)
                for value in data.get("other_evidence_used", [])
            ],
            context_dependency=_enum_value(
                ContextDependency,
                data["context_dependency"],
                "context_dependency",
            ),
        )

    def as_dict(self) -> Dict[str, Any]:
        return {
            "target_line_fields_used": [value.value for value in self.target_line_fields_used],
            "other_evidence_used": [value.as_dict() for value in self.other_evidence_used],
            "context_dependency": self.context_dependency.value,
        }


@dataclass(frozen=True)
class CandidateEvaluationWarning:
    warning_category: WarningCategory
    warning: str

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CandidateEvaluationWarning":
        _ensure_no_extra(data, {"warning_category", "warning"}, "CandidateEvaluationWarning")
        warning = str(data["warning"]).strip()
        if not warning:
            raise ValueError("warning is required")
        return cls(
            warning_category=_enum_value(
                WarningCategory,
                data["warning_category"],
                "warning_category",
            ),
            warning=warning,
        )

    def as_dict(self) -> Dict[str, Any]:
        return {
            "warning_category": self.warning_category.value,
            "warning": self.warning,
        }


@dataclass(frozen=True)
class WebSearchSignal:
    web_search_candidate: bool
    suggested_web_query: Optional[str] = None

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "WebSearchSignal":
        _ensure_no_extra(data, {"web_search_candidate", "suggested_web_query"}, "WebSearchSignal")
        return cls(
            web_search_candidate=bool(data["web_search_candidate"]),
            suggested_web_query=data.get("suggested_web_query"),
        )

    def as_dict(self) -> Dict[str, Any]:
        return {
            "web_search_candidate": self.web_search_candidate,
            "suggested_web_query": self.suggested_web_query,
        }


@dataclass(frozen=True)
class UnspscSearchQuery:
    query: str
    query_type: QueryType
    priority: int
    reason: str

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "UnspscSearchQuery":
        _ensure_no_extra(data, {"query", "query_type", "priority", "reason"}, "UnspscSearchQuery")
        query = str(data["query"]).strip()
        reason = str(data["reason"]).strip()
        priority = int(data["priority"])
        if not query or not reason:
            raise ValueError("UnspscSearchQuery requires query and reason")
        if priority < 1:
            raise ValueError("priority must be >= 1")
        return cls(
            query=query,
            query_type=_enum_value(QueryType, data["query_type"], "query_type"),
            priority=priority,
            reason=reason,
        )

    def as_dict(self) -> Dict[str, Any]:
        return {
            "query": self.query,
            "query_type": self.query_type.value,
            "priority": self.priority,
            "reason": self.reason,
        }


@dataclass(frozen=True)
class IdentifySearchResponse:
    item_hypothesis: ItemHypothesis
    evidence_usage: EvidenceUsage
    candidate_evaluation_warnings: List[CandidateEvaluationWarning]
    web_search_signal: WebSearchSignal
    unspsc_search_queries: List[UnspscSearchQuery]

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "IdentifySearchResponse":
        _ensure_no_extra(
            data,
            {
                "item_hypothesis",
                "evidence_usage",
                "candidate_evaluation_warnings",
                "web_search_signal",
                "unspsc_search_queries",
            },
            "IdentifySearchResponse",
        )
        queries = [UnspscSearchQuery.from_dict(value) for value in data.get("unspsc_search_queries", [])]
        if not queries:
            raise ValueError("unspsc_search_queries must contain at least one query")
        response = cls(
            item_hypothesis=ItemHypothesis.from_dict(data["item_hypothesis"]),
            evidence_usage=EvidenceUsage.from_dict(data["evidence_usage"]),
            candidate_evaluation_warnings=[
                CandidateEvaluationWarning.from_dict(value)
                for value in data.get("candidate_evaluation_warnings", [])
            ],
            web_search_signal=WebSearchSignal.from_dict(data["web_search_signal"]),
            unspsc_search_queries=queries,
        )
        return response._validate_priorities()

    def _validate_priorities(self) -> "IdentifySearchResponse":
        priorities = [query.priority for query in self.unspsc_search_queries]
        expected = list(range(1, len(priorities) + 1))
        if sorted(priorities) != expected:
            raise ValueError("unspsc_search_queries priorities must be unique integers starting at 1")
        return self

    def validate_against_request(self, request: IdentifySearchRequest) -> "IdentifySearchResponse":
        max_queries = request.global_config.max_unspsc_search_queries
        if len(self.unspsc_search_queries) > max_queries:
            raise ValueError(
                f"unspsc_search_queries exceeds max_unspsc_search_queries ({len(self.unspsc_search_queries)} > {max_queries})"
            )
        if not request.global_config.web_search_allowed:
            if self.web_search_signal.web_search_candidate:
                raise ValueError("web_search_candidate must be false when web_search_allowed is false")
            if self.web_search_signal.suggested_web_query is not None:
                raise ValueError("suggested_web_query must be null when web_search_allowed is false")
        normalized_queries = {query.query.strip().lower() for query in self.unspsc_search_queries}
        if len(normalized_queries) != len(self.unspsc_search_queries):
            raise ValueError("unspsc_search_queries must not contain duplicates")
        if QueryType.BROAD not in [query.query_type for query in self.unspsc_search_queries]:
            raise ValueError("unspsc_search_queries must include at least one broad query")
        return self

    def as_dict(self) -> Dict[str, Any]:
        return {
            "item_hypothesis": self.item_hypothesis.as_dict(),
            "evidence_usage": self.evidence_usage.as_dict(),
            "candidate_evaluation_warnings": [value.as_dict() for value in self.candidate_evaluation_warnings],
            "web_search_signal": self.web_search_signal.as_dict(),
            "unspsc_search_queries": [value.as_dict() for value in self.unspsc_search_queries],
        }


IDENTIFY_SEARCH_RESPONSE_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "required": [
        "item_hypothesis",
        "evidence_usage",
        "candidate_evaluation_warnings",
        "web_search_signal",
        "unspsc_search_queries",
    ],
    "additionalProperties": False,
}
