from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from ..identify_search.models import QueryType, UnspscSearchQuery


@dataclass(frozen=True)
class UnspscSearchToolRequest:
    queries: List[UnspscSearchQuery]
    max_candidates_per_query: int
    max_candidates_total: int


@dataclass(frozen=True)
class RetrievedHit:
    unspsc_code: str
    level: str
    title: str
    path: str
    source_channel: str
    source_query: str
    source_query_type: QueryType
    source_priority: int
    raw_score: float
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class FusedCandidate:
    unspsc_code: str
    level: str
    title: str
    path: str
    source_query: str
    source_query_type: QueryType
    source_priority: int
    rrf_score: float
    best_exact_rank: Optional[int]
    best_lexical_rank: Optional[int]
    best_semantic_rank: Optional[int]
    channels_present: List[str]
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class QueryCandidatePool:
    query: str
    query_type: QueryType
    priority: int
    candidates: List[FusedCandidate]


@dataclass(frozen=True)
class StratifiedCandidatePools:
    specific: List[FusedCandidate]
    broad: List[FusedCandidate]
    contextual: List[FusedCandidate]

    def as_dict(self) -> Dict[str, Any]:
        return {
            "specific": [candidate_as_dict(value) for value in self.specific],
            "broad": [candidate_as_dict(value) for value in self.broad],
            "contextual": [candidate_as_dict(value) for value in self.contextual],
        }


@dataclass(frozen=True)
class UnspscHierarchyNode:
    code: str
    label: str

    def as_dict(self) -> Dict[str, str]:
        return {"code": self.code, "label": self.label}


@dataclass(frozen=True)
class UnspscHierarchyPath:
    segment: Optional[UnspscHierarchyNode] = None
    family: Optional[UnspscHierarchyNode] = None
    class_: Optional[UnspscHierarchyNode] = None
    commodity: Optional[UnspscHierarchyNode] = None

    def as_dict(self) -> Dict[str, Optional[Dict[str, str]]]:
        return {
            "segment": None if self.segment is None else self.segment.as_dict(),
            "family": None if self.family is None else self.family.as_dict(),
            "class": None if self.class_ is None else self.class_.as_dict(),
            "commodity": None if self.commodity is None else self.commodity.as_dict(),
        }


@dataclass(frozen=True)
class MatchedQuery:
    query: str
    priority: int

    def as_dict(self) -> Dict[str, Any]:
        return {"query": self.query, "priority": self.priority}


@dataclass(frozen=True)
class SpecificRule:
    rule_id: str
    applies_to_code: str
    applies_to_label: str
    applies_to_level: str
    rule_scope: str
    rule_text: str

    def as_dict(self) -> Dict[str, str]:
        return {
            "rule_id": self.rule_id,
            "applies_to_code": self.applies_to_code,
            "applies_to_label": self.applies_to_label,
            "applies_to_level": self.applies_to_level,
            "rule_scope": self.rule_scope,
            "rule_text": self.rule_text,
        }


@dataclass(frozen=True)
class EvaluationCandidate:
    rank: int
    retrieval_score: float
    code: str
    label: str
    level: str
    hierarchy_path: UnspscHierarchyPath
    code_description: Optional[str]
    code_aliases: List[str]
    matched_queries: List[MatchedQuery]
    specific_rules: List[SpecificRule]

    def as_dict(self) -> Dict[str, Any]:
        return {
            "rank": self.rank,
            "retrieval_score": self.retrieval_score,
            "code": self.code,
            "label": self.label,
            "level": self.level,
            "hierarchy_path": self.hierarchy_path.as_dict(),
            "code_description": self.code_description,
            "code_aliases": self.code_aliases,
            "matched_queries": [value.as_dict() for value in self.matched_queries],
            "specific_rules": [value.as_dict() for value in self.specific_rules],
        }


@dataclass(frozen=True)
class UnspscSearchOutput:
    unspsc_version: str
    queries_searched: List[MatchedQuery]
    retrieval_metadata: Dict[str, Any]
    candidates: List[EvaluationCandidate]
    grouped_candidates: StratifiedCandidatePools

    def as_dict(self) -> Dict[str, Any]:
        return {
            "unspsc_version": self.unspsc_version,
            "queries_searched": [value.as_dict() for value in self.queries_searched],
            "retrieval_metadata": self.retrieval_metadata,
            "candidates": [value.as_dict() for value in self.candidates],
        }


def candidate_as_dict(candidate: FusedCandidate) -> Dict[str, Any]:
    return {
        "unspsc_code": candidate.unspsc_code,
        "level": candidate.level,
        "title": candidate.title,
        "path": candidate.path,
        "source_query": candidate.source_query,
        "source_query_type": candidate.source_query_type.value,
        "source_priority": candidate.source_priority,
        "rrf_score": candidate.rrf_score,
        "best_exact_rank": candidate.best_exact_rank,
        "best_lexical_rank": candidate.best_lexical_rank,
        "best_semantic_rank": candidate.best_semantic_rank,
        "channels_present": candidate.channels_present,
        "metadata": candidate.metadata,
    }


def build_unspsc_search_output(
    *,
    unspsc_version: str,
    queries: List[UnspscSearchQuery],
    grouped_candidates: StratifiedCandidatePools,
    max_candidates_per_query: int,
    max_candidates_total: int,
) -> UnspscSearchOutput:
    candidates = grouped_candidates.specific + grouped_candidates.broad + grouped_candidates.contextual
    max_rrf_score = max((candidate.rrf_score for candidate in candidates), default=0.0)
    normalized_candidates: List[EvaluationCandidate] = []
    for rank, candidate in enumerate(candidates, start=1):
        normalized_candidates.append(
            EvaluationCandidate(
                rank=rank,
                retrieval_score=0.0 if max_rrf_score <= 0 else round(candidate.rrf_score / max_rrf_score, 6),
                code=candidate.unspsc_code,
                label=candidate.title,
                level=str(candidate.level).lower(),
                hierarchy_path=_hierarchy_path_from_metadata(candidate.metadata),
                code_description=_first_str(candidate.metadata, "code_description", "description"),
                code_aliases=_list_str(candidate.metadata, "code_aliases", "aliases", "synonyms"),
                matched_queries=[MatchedQuery(query=candidate.source_query, priority=candidate.source_priority)],
                specific_rules=_specific_rules_from_metadata(candidate.metadata),
            )
        )
    return UnspscSearchOutput(
        unspsc_version=unspsc_version,
        queries_searched=[MatchedQuery(query=value.query, priority=value.priority) for value in queries],
        retrieval_metadata={
            "retrieval_methods": ["exact", "lexical", "semantic"],
            "fusion_method": "rrf",
            "max_candidates_per_query": max_candidates_per_query,
            "max_candidates_total": max_candidates_total,
            "candidate_count": len(normalized_candidates),
        },
        candidates=normalized_candidates,
        grouped_candidates=grouped_candidates,
    )


def _hierarchy_path_from_metadata(metadata: Dict[str, Any]) -> UnspscHierarchyPath:
    return UnspscHierarchyPath(
        segment=_make_node(
            _first_str(metadata, "segment_code"),
            _first_str(metadata, "segment_title", "segment_label"),
        ),
        family=_make_node(
            _first_str(metadata, "family_code"),
            _first_str(metadata, "family_title", "family_label"),
        ),
        class_=_make_node(
            _first_str(metadata, "class_code"),
            _first_str(metadata, "class_title", "class_label"),
        ),
        commodity=_make_node(
            _first_str(metadata, "commodity_code"),
            _first_str(metadata, "commodity_title", "commodity_label"),
        ),
    )


def _make_node(code: Optional[str], label: Optional[str]) -> Optional[UnspscHierarchyNode]:
    if not code or not label:
        return None
    return UnspscHierarchyNode(code=code, label=label)


def _specific_rules_from_metadata(metadata: Dict[str, Any]) -> List[SpecificRule]:
    rules = metadata.get("specific_rules")
    if not isinstance(rules, list):
        return []
    result: List[SpecificRule] = []
    for item in rules:
        if not isinstance(item, dict):
            continue
        if not item.get("rule_id") or not item.get("rule_text"):
            continue
        result.append(
            SpecificRule(
                rule_id=str(item["rule_id"]),
                applies_to_code=str(item.get("applies_to_code") or ""),
                applies_to_label=str(item.get("applies_to_label") or ""),
                applies_to_level=str(item.get("applies_to_level") or ""),
                rule_scope=str(item.get("rule_scope") or ""),
                rule_text=str(item["rule_text"]),
            )
        )
    return result


def _first_str(metadata: Dict[str, Any], *keys: str) -> Optional[str]:
    for key in keys:
        value = metadata.get(key)
        if value not in (None, ""):
            return str(value)
    return None


def _list_str(metadata: Dict[str, Any], *keys: str) -> List[str]:
    for key in keys:
        value = metadata.get(key)
        if isinstance(value, list):
            return [str(item) for item in value if item not in (None, "")]
    return []
