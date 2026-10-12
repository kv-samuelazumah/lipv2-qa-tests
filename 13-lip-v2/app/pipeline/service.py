from __future__ import annotations

import logging
import time
from typing import Any, Callable, Optional, TypeVar

from ..core.config import Config
from ..enrichment.models import SupplierEnrichmentResult
from ..enrichment.service import SupplierEnrichmentService
from ..evaluation.client import DeepSeekEvaluateCandidatesClient, EvaluateCandidatesClient
from ..evaluation.house_rules import apply_house_rule_guards
from ..evaluation.models import EvaluateCandidatesRequest, EvaluateCandidatesResponse, EvaluationDecision
from ..house_rules import merge_house_rules
from ..identify_search.client import DeepSeekIdentifySearchClient, IdentifySearchClient
from ..identify_search.models import (
    HouseRule,
    IdentifySearchRequest,
    IdentifySearchResponse,
    InvoiceContext,
    NumericValue,
    QueryType,
    TargetLine,
    UnspscSearchQuery,
)
from ..persistence.repository import LineItemSolutionRepository, PostgresLineItemSolutionRepository
from ..pre_agentic.service import PreAgenticService
from ..search.models import UnspscSearchToolRequest
from ..search.service import UnspscSearchTool
from ..web_search.client import WebSearchClient
from ..web_search.models import WebSearchRequest
from ..web_reidentify.client import DeepSeekWebReidentifyClient, WebReidentifyClient
from ..web_reidentify.models import WebReidentifyRequest
from .models import LineItemPipelineInput, LineItemPipelineResult


LOG = logging.getLogger("lip.v2.pipeline")
T = TypeVar("T")


class LineItemPipelineService:
    MAX_UNSPSC_RESEARCH_LOOPS = 2
    MAX_WEB_SEARCH_LOOPS = 1
    MAX_TOTAL_AGENTIC_LOOPS = 3
    RUN_UNTIL_PRE_AGENTIC = "pre_agentic"
    RUN_UNTIL_IDENTIFY = "identify"
    RUN_UNTIL_SEARCH = "search"
    RUN_UNTIL_EVALUATE = "evaluate"
    RUN_UNTIL_WEB_SEARCH = "web_search"
    RUN_UNTIL_WEB_REIDENTIFY = "web_reidentify"
    RUN_UNTIL_FULL = "full"

    def __init__(
        self,
        pre_agentic_service: Optional[PreAgenticService] = None,
        identify_client: Optional[IdentifySearchClient] = None,
        search_tool: Optional[UnspscSearchTool] = None,
        evaluation_client: Optional[EvaluateCandidatesClient] = None,
        solution_repo: Optional[LineItemSolutionRepository] = None,
        web_search_client: Optional[WebSearchClient] = None,
        web_reidentify_client: Optional[WebReidentifyClient] = None,
        enrichment_service: Optional[SupplierEnrichmentService] = None,
    ):
        self.pre_agentic_service = pre_agentic_service or PreAgenticService()
        self.identify_client = identify_client
        self.search_tool = search_tool
        self.evaluation_client = evaluation_client
        self.solution_repo = solution_repo
        self.web_search_client = web_search_client
        self.web_reidentify_client = web_reidentify_client
        self.enrichment_service = enrichment_service
        self._default_identify_client: Optional[IdentifySearchClient] = None
        self._default_search_tool: Optional[UnspscSearchTool] = None
        self._default_evaluation_client: Optional[EvaluateCandidatesClient] = None

    def process(
        self,
        payload: LineItemPipelineInput,
        *,
        run_until_stage: str = RUN_UNTIL_FULL,
        skip_pre_agentic: bool = False,
    ) -> LineItemPipelineResult:
        def run_stage(name: str, operation: Callable[[], T]) -> T:
            started_at = time.perf_counter()
            LOG.info("Pipeline stage started stage=%s org=%s", name, payload.org_id)
            try:
                value = operation()
            except Exception:
                LOG.exception(
                    "Pipeline stage failed stage=%s org=%s elapsed_ms=%.1f",
                    name,
                    payload.org_id,
                    (time.perf_counter() - started_at) * 1000,
                )
                raise
            LOG.info(
                "Pipeline stage completed stage=%s org=%s elapsed_ms=%.1f",
                name,
                payload.org_id,
                (time.perf_counter() - started_at) * 1000,
            )
            return value

        pre_agentic_result = None
        if not skip_pre_agentic:
            pre_agentic_result = run_stage(
                "pre_agentic",
                lambda: self.pre_agentic_service.resolve(
                    org_id=payload.org_id,
                    supplier_raw=payload.supplier_raw,
                    line_item_raw=payload.line_item_raw,
                ),
            )
            if pre_agentic_result is not None:
                return LineItemPipelineResult(
                    stage="PRE_AGENTIC_HIT",
                    pre_agentic_result=pre_agentic_result,
                    identify_search_result=None,
                    retrieval_result=None,
                    evaluation_result=None,
                    final_result={
                        "resolved_by": pre_agentic_result["resolved_by"],
                        "status_code": pre_agentic_result.get("status_code"),
                        "policy_code": pre_agentic_result.get("policy_code"),
                        "unspsc_code": pre_agentic_result.get("unspsc_code"),
                        "unspsc_level": pre_agentic_result.get("unspsc_level"),
                        "lookup_hash": pre_agentic_result.get("lookup_hash"),
                        "selected_label": pre_agentic_result.get("selected_label"),
                    },
                )
            if run_until_stage == self.RUN_UNTIL_PRE_AGENTIC:
                return LineItemPipelineResult(
                    stage="PRE_AGENTIC_MISS",
                    pre_agentic_result=None,
                    identify_search_result=None,
                    retrieval_result=None,
                    evaluation_result=None,
                    final_result={
                        "resolved_by": "PRE_AGENTIC_MISS",
                        "status_code": "NO_MATCH",
                        "policy_code": None,
                        "unspsc_code": None,
                        "unspsc_level": None,
                    },
                )
        elif run_until_stage == self.RUN_UNTIL_PRE_AGENTIC:
            return LineItemPipelineResult(
                stage="PRE_AGENTIC_SKIPPED",
                pre_agentic_result=None,
                identify_search_result=None,
                retrieval_result=None,
                evaluation_result=None,
                final_result={
                    "resolved_by": "PRE_AGENTIC_SKIPPED",
                    "status_code": "SKIPPED",
                    "policy_code": None,
                    "unspsc_code": None,
                    "unspsc_level": None,
                },
            )

        identify_client = self.identify_client or self._resolve_identify_client()
        search_tool = self.search_tool or self._resolve_search_tool()
        evaluation_client = self._resolve_evaluation_client()
        enrichment = run_stage(
            "supplier_enrichment",
            lambda: self._resolve_supplier_enrichment(payload),
        )
        identify_request = self._build_identify_request(payload, enrichment)
        identify_result = run_stage(
            "identify_search",
            lambda: identify_client.run(identify_request),
        )
        if run_until_stage == self.RUN_UNTIL_IDENTIFY:
            return LineItemPipelineResult(
                stage="IDENTIFY_COMPLETE",
                pre_agentic_result=pre_agentic_result,
                identify_search_result=identify_result.as_dict(),
                retrieval_result=None,
                evaluation_result=None,
                final_result={
                    "resolved_by": "AGENTIC_IDENTIFY_SEARCH",
                    "status_code": "IN_PROGRESS",
                    "policy_code": None,
                    "unspsc_code": None,
                    "unspsc_level": None,
                },
            )
        active_queries = identify_result.unspsc_search_queries
        tried_queries: set[str] = set()
        unspsc_research_loops = 0
        web_search_loops = 0
        total_loops = 0
        last_retrieval_result = None
        last_evaluation_result = None

        while True:
            filtered_queries = self._filter_new_queries(active_queries, tried_queries)
            if not filtered_queries:
                return self._build_unable_to_resolve_result(
                    pre_agentic_result=pre_agentic_result,
                    identify_result=identify_result,
                    retrieval_result=last_retrieval_result,
                    evaluation_result=last_evaluation_result,
                    reason="No new UNSPSC search queries remained after duplicate suppression.",
                    diagnosis="no_viable_candidate",
                    resolved_by="AGENTIC_RESEARCH_NO_NEW_QUERIES",
                )
            self._mark_queries_tried(filtered_queries, tried_queries)
            retrieval_result = run_stage(
                "unspsc_search",
                lambda: search_tool.run(
                    UnspscSearchToolRequest(
                        queries=filtered_queries,
                        max_candidates_per_query=payload.max_candidates_per_query,
                        max_candidates_total=payload.max_candidates_total,
                    )
                ),
            )
            last_retrieval_result = retrieval_result.as_dict()
            if evaluation_client is None:
                return LineItemPipelineResult(
                    stage="RETRIEVAL_COMPLETE",
                    pre_agentic_result=pre_agentic_result,
                    identify_search_result=identify_result.as_dict(),
                    retrieval_result=last_retrieval_result,
                    evaluation_result=None,
                    final_result={
                        "resolved_by": "AGENTIC_UNSPSC_SEARCH",
                        "status_code": "IN_PROGRESS",
                        "policy_code": None,
                        "unspsc_code": None,
                        "unspsc_level": None,
                    },
                )
            if run_until_stage == self.RUN_UNTIL_SEARCH:
                return LineItemPipelineResult(
                    stage="RETRIEVAL_COMPLETE",
                    pre_agentic_result=pre_agentic_result,
                    identify_search_result=identify_result.as_dict(),
                    retrieval_result=last_retrieval_result,
                    evaluation_result=None,
                    final_result={
                        "resolved_by": "AGENTIC_UNSPSC_SEARCH",
                        "status_code": "IN_PROGRESS",
                        "policy_code": None,
                        "unspsc_code": None,
                        "unspsc_level": None,
                    },
                )
            evaluation_request = EvaluateCandidatesRequest(
                identify_search_input=identify_request,
                identify_search_output=identify_result,
                unspsc_search_output=last_retrieval_result,
            )
            try:
                evaluation_result = run_stage(
                    "evaluate_candidates",
                    lambda: evaluation_client.run(evaluation_request),
                )
                evaluation_result = apply_house_rule_guards(evaluation_request, evaluation_result)
            except Exception as exc:  # noqa: BLE001
                return self._build_unable_to_resolve_result(
                    pre_agentic_result=pre_agentic_result,
                    identify_result=identify_result,
                    retrieval_result=last_retrieval_result,
                    evaluation_result=None,
                    reason=f"Evaluate Candidates failed: {exc}",
                    diagnosis="insufficient_evidence_impossible",
                    resolved_by="AGENTIC_EVALUATION_ERROR",
                )
            last_evaluation_result = evaluation_result.as_dict()
            if run_until_stage == self.RUN_UNTIL_EVALUATE:
                return LineItemPipelineResult(
                    stage="EVALUATION_COMPLETE",
                    pre_agentic_result=pre_agentic_result,
                    identify_search_result=identify_result.as_dict(),
                    retrieval_result=last_retrieval_result,
                    evaluation_result=last_evaluation_result,
                    final_result={
                        "resolved_by": "AGENTIC_EVALUATE_CANDIDATES",
                        "status_code": "IN_PROGRESS",
                        "policy_code": None,
                        "unspsc_code": None,
                        "unspsc_level": None,
                    },
                )
            if evaluation_result.decision is EvaluationDecision.SELECT_CANDIDATE:
                final_result = self._persist_agentic_match(
                    payload=payload,
                    retrieval_result=last_retrieval_result,
                    evaluation_result=last_evaluation_result,
                )
                return LineItemPipelineResult(
                    stage="MATCH_OBTAINED",
                    pre_agentic_result=pre_agentic_result,
                    identify_search_result=identify_result.as_dict(),
                    retrieval_result=last_retrieval_result,
                    evaluation_result=last_evaluation_result,
                    final_result=final_result,
                )
            if evaluation_result.decision is EvaluationDecision.RE_SEARCH_UNSPSC:
                if (
                    unspsc_research_loops >= self.MAX_UNSPSC_RESEARCH_LOOPS
                    or total_loops >= self.MAX_TOTAL_AGENTIC_LOOPS
                ):
                    return self._build_unable_to_resolve_result(
                        pre_agentic_result=pre_agentic_result,
                        identify_result=identify_result,
                        retrieval_result=last_retrieval_result,
                        evaluation_result=last_evaluation_result,
                        reason="UNSPSC re-search loop limit reached without a defensible final match.",
                        diagnosis=evaluation_result.candidate_set_diagnosis.value,
                        resolved_by="AGENTIC_RESEARCH_EXHAUSTED",
                    )
                unspsc_research_loops += 1
                total_loops += 1
                active_queries = self._build_research_queries(evaluation_result)
                continue
            if evaluation_result.decision is EvaluationDecision.WEB_SEARCH:
                if (
                    not payload.web_search_allowed
                    or web_search_loops >= self.MAX_WEB_SEARCH_LOOPS
                    or total_loops >= self.MAX_TOTAL_AGENTIC_LOOPS
                    or self.web_search_client is None
                    or self._resolve_web_reidentify_client() is None
                ):
                    return self._build_unable_to_resolve_result(
                        pre_agentic_result=pre_agentic_result,
                        identify_result=identify_result,
                        retrieval_result=last_retrieval_result,
                        evaluation_result=last_evaluation_result,
                        reason="Web-search route was requested but could not be executed within configured limits.",
                        diagnosis="item_identity_unresolved",
                        resolved_by="AGENTIC_WEB_SEARCH_BLOCKED",
                    )
                web_result = run_stage(
                    "web_search",
                    lambda: self.web_search_client.run(
                        WebSearchRequest(
                            query=evaluation_result.web_search.query,
                            supplier_name=payload.supplier_raw,
                            line_item_raw=payload.line_item_raw,
                        )
                    ),
                )
                if run_until_stage == self.RUN_UNTIL_WEB_SEARCH:
                    return LineItemPipelineResult(
                        stage="WEB_SEARCH_COMPLETE",
                        pre_agentic_result=pre_agentic_result,
                        identify_search_result=identify_result.as_dict(),
                        retrieval_result=last_retrieval_result,
                        evaluation_result=last_evaluation_result,
                        final_result={
                            "resolved_by": "AGENTIC_WEB_SEARCH",
                            "status_code": "IN_PROGRESS",
                            "policy_code": None,
                            "unspsc_code": None,
                            "unspsc_level": None,
                            "web_search_result": web_result.as_dict(),
                        },
                    )
                web_reidentify_client = self._resolve_web_reidentify_client()
                if web_reidentify_client is None:
                    return self._build_unable_to_resolve_result(
                        pre_agentic_result=pre_agentic_result,
                        identify_result=identify_result,
                        retrieval_result=last_retrieval_result,
                        evaluation_result=last_evaluation_result,
                        reason="Web re-identify step was unavailable.",
                        diagnosis="item_identity_unresolved",
                        resolved_by="AGENTIC_WEB_REIDENTIFY_UNAVAILABLE",
                    )
                web_search_loops += 1
                total_loops += 1
                identify_result = run_stage(
                    "web_reidentify",
                    lambda: web_reidentify_client.run(
                        WebReidentifyRequest(
                            identify_search_input=identify_request,
                            identify_search_output=identify_result,
                            evaluation_output=evaluation_result,
                            web_search_result=web_result,
                        )
                    ),
                )
                if run_until_stage == self.RUN_UNTIL_WEB_REIDENTIFY:
                    return LineItemPipelineResult(
                        stage="WEB_REIDENTIFY_COMPLETE",
                        pre_agentic_result=pre_agentic_result,
                        identify_search_result=identify_result.as_dict(),
                        retrieval_result=last_retrieval_result,
                        evaluation_result=last_evaluation_result,
                        final_result={
                            "resolved_by": "AGENTIC_WEB_REIDENTIFY",
                            "status_code": "IN_PROGRESS",
                            "policy_code": None,
                            "unspsc_code": None,
                            "unspsc_level": None,
                            "web_search_result": web_result.as_dict(),
                        },
                    )
                active_queries = identify_result.unspsc_search_queries
                continue
            return LineItemPipelineResult(
                stage="UNABLE_TO_RESOLVE",
                pre_agentic_result=pre_agentic_result,
                identify_search_result=identify_result.as_dict(),
                retrieval_result=last_retrieval_result,
                evaluation_result=last_evaluation_result,
                final_result={
                    "resolved_by": "AGENTIC_EVALUATION_UNABLE_TO_RESOLVE",
                    "status_code": "UNRESOLVED",
                    "policy_code": None,
                    "unspsc_code": None,
                    "unspsc_level": None,
                    "reason": evaluation_result.decision_reason,
                },
            )

    def _resolve_evaluation_client(self) -> Optional[EvaluateCandidatesClient]:
        if self.evaluation_client is not None:
            return self.evaluation_client
        if not Config.get_evaluate_candidates_api_key():
            return None
        if self._default_evaluation_client is None:
            self._default_evaluation_client = DeepSeekEvaluateCandidatesClient()
        return self._default_evaluation_client

    def _resolve_identify_client(self) -> IdentifySearchClient:
        if self._default_identify_client is None:
            self._default_identify_client = DeepSeekIdentifySearchClient()
        return self._default_identify_client

    def _resolve_search_tool(self) -> UnspscSearchTool:
        if self._default_search_tool is None:
            self._default_search_tool = UnspscSearchTool()
        return self._default_search_tool

    def _resolve_web_reidentify_client(self) -> Optional[WebReidentifyClient]:
        if self.web_reidentify_client is not None:
            return self.web_reidentify_client
        if not Config.get_web_reidentify_api_key():
            return None
        return DeepSeekWebReidentifyClient()

    @staticmethod
    def _normalize_query_key(query: str) -> str:
        return " ".join(query.lower().split())

    def _filter_new_queries(
        self,
        queries: list[UnspscSearchQuery],
        tried_queries: set[str],
    ) -> list[UnspscSearchQuery]:
        deduped: list[UnspscSearchQuery] = []
        seen_batch: set[str] = set()
        for query in sorted(queries, key=lambda value: value.priority):
            key = self._normalize_query_key(query.query)
            if key in tried_queries or key in seen_batch:
                continue
            deduped.append(query)
            seen_batch.add(key)
        return deduped

    def _mark_queries_tried(self, queries: list[UnspscSearchQuery], tried_queries: set[str]) -> None:
        for query in queries:
            tried_queries.add(self._normalize_query_key(query.query))

    def _build_research_queries(
        self,
        evaluation_result: EvaluateCandidatesResponse,
    ) -> list[UnspscSearchQuery]:
        if evaluation_result.re_search_unspsc is None:
            raise ValueError("re_search_unspsc payload is required")
        ordered = sorted(evaluation_result.re_search_unspsc.queries_to_try, key=lambda value: value.priority)
        rebuilt: list[UnspscSearchQuery] = []
        for index, value in enumerate(ordered):
            if len(ordered) == 1:
                query_type = QueryType.BROAD
            elif index == 0:
                query_type = QueryType.SPECIFIC
            elif index == len(ordered) - 1:
                query_type = QueryType.BROAD
            else:
                query_type = QueryType.CONTEXTUAL
            rebuilt.append(
                UnspscSearchQuery(
                    query=value.query,
                    query_type=query_type,
                    priority=index + 1,
                    reason=evaluation_result.re_search_unspsc.new_search_direction,
                )
            )
        return rebuilt

    def _build_identify_request(
        self,
        payload: LineItemPipelineInput,
        enrichment: Optional[SupplierEnrichmentResult] = None,
    ) -> IdentifySearchRequest:
        merged_house_rules = merge_house_rules(payload.house_rules)
        return IdentifySearchRequest(
            global_config=self._build_global_config(payload),
            target_line=self._build_target_line(payload),
            invoice_context=self._build_invoice_context(payload, enrichment),
            house_rules=[HouseRule.from_dict(rule) for rule in merged_house_rules],
        )

    def _build_unable_to_resolve_result(
        self,
        *,
        pre_agentic_result: Optional[dict[str, Any]],
        identify_result: IdentifySearchResponse,
        retrieval_result: Optional[dict[str, Any]],
        evaluation_result: Optional[dict[str, Any]],
        reason: str,
        diagnosis: str,
        resolved_by: str,
    ) -> LineItemPipelineResult:
        return LineItemPipelineResult(
            stage="UNABLE_TO_RESOLVE",
            pre_agentic_result=pre_agentic_result,
            identify_search_result=identify_result.as_dict(),
            retrieval_result=retrieval_result,
            evaluation_result=evaluation_result,
            final_result={
                "resolved_by": resolved_by,
                "status_code": "UNRESOLVED",
                "policy_code": None,
                "unspsc_code": None,
                "unspsc_level": None,
                "reason": reason,
                "candidate_set_diagnosis": diagnosis,
            },
        )

    def _persist_agentic_match(
        self,
        *,
        payload: LineItemPipelineInput,
        retrieval_result: dict[str, Any],
        evaluation_result: dict[str, Any],
    ) -> dict[str, Any]:
        final_classification = evaluation_result["final_classification"]
        if final_classification is None:
            raise ValueError("final_classification is required for select_candidate")
        selected_code = final_classification["code"]
        selected_label = final_classification["label"]
        selected_level = self._resolve_selected_level(
            selected_code=selected_code,
            final_classification=final_classification,
            retrieval_result=retrieval_result,
        )
        reasoning = {
            "decision_reason": evaluation_result["decision_reason"],
            "candidate_set_diagnosis": evaluation_result["candidate_set_diagnosis"],
            "selection_source": final_classification["selection_source"],
            "selection_reason": final_classification["selection_reason"],
            "classification_confidence": final_classification["classification_confidence"],
            "fit": final_classification["fit"],
            "alternative_rejection_summary": final_classification["alternative_rejection_summary"],
            "rule_ids_used": evaluation_result["rule_ids_used"],
            "source_candidate_code": final_classification["source_candidate_code"],
            "source_candidate_label": final_classification["source_candidate_label"],
        }
        if self.solution_repo is not None:
            solution = self.solution_repo.upsert_agentic_solution(
                org_id=payload.org_id,
                supplier_raw=payload.supplier_raw,
                line_item_raw=payload.line_item_raw,
                unspsc_code=selected_code,
                unspsc_level=selected_level,
                reasoning=reasoning,
                selected_label=selected_label,
            )
            return {
                "resolved_by": (
                    "AGENTIC_EVALUATION_SELECT_PARENT"
                    if final_classification["selection_source"] == "hierarchy_parent"
                    else "AGENTIC_EVALUATION_SELECT_CANDIDATE"
                ),
                "status_code": solution.status_code,
                "policy_code": solution.policy_code,
                "unspsc_code": solution.unspsc_code,
                "unspsc_level": solution.unspsc_level,
                "stable": solution.stable,
                "solved_for": solution.solved_for,
                "lookup_hash": solution.lookup_hash,
                "selected_label": selected_label,
                "selection_source": final_classification["selection_source"],
                "selection_reason": final_classification["selection_reason"],
                "row_id": solution.id,
            }
        session = self.pre_agentic_service.db.get_session()
        try:
            repository = PostgresLineItemSolutionRepository(session)
            solution = repository.upsert_agentic_solution(
                org_id=payload.org_id,
                supplier_raw=payload.supplier_raw,
                line_item_raw=payload.line_item_raw,
                unspsc_code=selected_code,
                unspsc_level=selected_level,
                reasoning=reasoning,
                selected_label=selected_label,
            )
            return {
                "resolved_by": (
                    "AGENTIC_EVALUATION_SELECT_PARENT"
                    if final_classification["selection_source"] == "hierarchy_parent"
                    else "AGENTIC_EVALUATION_SELECT_CANDIDATE"
                ),
                "status_code": solution.status_code,
                "policy_code": solution.policy_code,
                "unspsc_code": solution.unspsc_code,
                "unspsc_level": solution.unspsc_level,
                "stable": solution.stable,
                "solved_for": solution.solved_for,
                "lookup_hash": solution.lookup_hash,
                "selected_label": selected_label,
                "selection_source": final_classification["selection_source"],
                "selection_reason": final_classification["selection_reason"],
                "row_id": solution.id,
            }
        finally:
            session.close()

    @staticmethod
    def _resolve_selected_level(
        *,
        selected_code: str,
        final_classification: dict[str, Any],
        retrieval_result: dict[str, Any],
    ) -> str:
        for candidate in retrieval_result.get("candidates", []):
            if final_classification["selection_source"] == "retrieved_candidate" and candidate.get("code") == selected_code:
                return str(candidate.get("level") or "commodity").upper()
            path = candidate.get("hierarchy_path") or {}
            for level_name in ("segment", "family", "class", "commodity"):
                node = path.get(level_name)
                if isinstance(node, dict) and node.get("code") == selected_code:
                    return level_name.upper()
        return "COMMODITY"

    @staticmethod
    def _build_global_config(payload: LineItemPipelineInput):
        from ..identify_search.models import GlobalConfig

        return GlobalConfig(
            max_unspsc_search_queries=payload.max_unspsc_search_queries,
            web_search_allowed=payload.web_search_allowed,
        )

    @staticmethod
    def _build_target_line(payload: LineItemPipelineInput) -> TargetLine:
        return TargetLine(
            item_raw_row=payload.line_item_raw,
            description_clean=payload.cleaned_line_item,
            unit_of_measure_raw=payload.unit_of_measure_raw,
            quantity=NumericValue(value=payload.quantity),
            unit_price=NumericValue(value=payload.unit_price),
            line_subtotal=NumericValue(value=payload.line_subtotal),
        )

    @staticmethod
    def _build_invoice_context(
        payload: LineItemPipelineInput,
        enrichment: Optional[SupplierEnrichmentResult] = None,
    ) -> InvoiceContext:
        return InvoiceContext(
            supplier_name=payload.supplier_raw or None,
            unspsc_ready_invoice_description=payload.unspsc_ready_invoice_description,
            supplier_sic_label=payload.supplier_sic_label or (None if enrichment is None else enrichment.supplier_sic_label),
            buyer_sic_label=payload.buyer_sic_label,
        )

    def _resolve_supplier_enrichment(
        self,
        payload: LineItemPipelineInput,
    ) -> Optional[SupplierEnrichmentResult]:
        # An empty normalized name makes the fuzzy Companies House lookup both
        # meaningless and extremely expensive (minutes on the local corpus).
        if not payload.supplier_raw.strip():
            return None
        if payload.supplier_sic_label:
            return None
        if self.enrichment_service is None:
            return None
        return self.enrichment_service.enrich_supplier(payload.supplier_raw)
