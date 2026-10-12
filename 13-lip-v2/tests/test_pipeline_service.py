import sys
import unittest
from pathlib import Path


sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.identify_search.models import (
    CandidateEvaluationWarning,
    ContextDependency,
    EvidenceUsage,
    IdentifySearchResponse,
    Interpretation,
    ItemHypothesis,
    ItemNature,
    QueryType,
    UnspscSearchQuery,
    UnderstandingConfidence,
    WarningCategory,
    WebSearchSignal,
)
from app.evaluation.models import (
    CandidateSetDiagnosis,
    ClassificationConfidence,
    ClassificationFit,
    EvaluateCandidatesResponse,
    EvaluationSearchQuery,
    EvaluationDecision,
    FinalClassification,
    ReSearchUnspsc,
    SelectionSource,
    UnableToResolve,
    WebQueryBasis,
    WebSearchInstruction,
)
from app.persistence.repository import InMemoryLineItemSolutionRepository
from app.pipeline.models import LineItemPipelineInput
from app.pipeline.service import LineItemPipelineService
from app.web_search.models import WebSearchResult
from app.web_reidentify.models import WebReidentifyRequest
from app.enrichment.models import SupplierEnrichmentResult


class FakePreAgenticService:
    def __init__(self, result):
        self.result = result

    def resolve(self, org_id: str, supplier_raw: str, line_item_raw: str):
        return self.result


class FakeIdentifyClient:
    def __init__(self):
        self.last_request = None

    def run(self, request):
        self.last_request = request
        return IdentifySearchResponse(
            item_hypothesis=ItemHypothesis(
                understanding_confidence=UnderstandingConfidence.MEDIUM,
                item_nature=ItemNature.PHYSICAL_GOOD,
                primary_identity="laptop computer",
                identity_explanation="price disambiguates notebook to laptop",
                interpretation=Interpretation(
                    what_it_is="Likely a laptop computer.",
                    what_it_is_not=["paper notebook"],
                    ambiguity=[],
                ),
            ),
            evidence_usage=EvidenceUsage(
                target_line_fields_used=[],
                other_evidence_used=[],
                context_dependency=ContextDependency.LOW,
            ),
            candidate_evaluation_warnings=[
                CandidateEvaluationWarning(
                    warning_category=WarningCategory.PRICE_DISAMBIGUATION,
                    warning="Avoid stationery notebook candidates.",
                )
            ],
            web_search_signal=WebSearchSignal(
                web_search_candidate=False,
                suggested_web_query=None,
            ),
            unspsc_search_queries=[
                UnspscSearchQuery(
                    query="laptop computer",
                    query_type=QueryType.SPECIFIC,
                    priority=1,
                    reason="primary identity",
                ),
                UnspscSearchQuery(
                    query="computer equipment",
                    query_type=QueryType.BROAD,
                    priority=2,
                    reason="broad fallback",
                ),
            ],
        )


class FakeSearchTool:
    def __init__(self):
        self.calls = []

    def run(self, request):
        self.calls.append([query.query for query in request.queries])
        class Result:
            def __init__(self, queries):
                self.queries = queries

            def as_dict(self):
                return {
                    "unspsc_version": "test-v1",
                    "queries_searched": [
                        {"query": query, "priority": idx + 1} for idx, query in enumerate(self.queries)
                    ],
                    "retrieval_metadata": {
                        "retrieval_methods": ["exact", "lexical", "semantic"],
                        "fusion_method": "rrf",
                        "max_candidates_per_query": 10,
                        "max_candidates_total": 30,
                        "candidate_count": 2,
                    },
                    "candidates": [
                        {
                            "rank": 1,
                            "retrieval_score": 1.0,
                            "code": "43211503",
                            "label": "Laptop computers",
                            "level": "commodity",
                            "hierarchy_path": {"segment": None, "family": None, "class": None, "commodity": None},
                            "code_description": None,
                            "code_aliases": [],
                            "matched_queries": [{"query": "laptop computer", "priority": 1}],
                            "specific_rules": [],
                        },
                        {
                            "rank": 2,
                            "retrieval_score": 0.5,
                            "code": "43210000",
                            "label": "Computer equipment and accessories",
                            "level": "class",
                            "hierarchy_path": {"segment": None, "family": None, "class": None, "commodity": None},
                            "code_description": None,
                            "code_aliases": [],
                            "matched_queries": [{"query": "computer equipment", "priority": 2}],
                            "specific_rules": [],
                        },
                    ],
                }

        return Result(self.calls[-1])


class FakeEvaluationClient:
    def run(self, request):
        return EvaluateCandidatesResponse(
            decision=EvaluationDecision.SELECT_CANDIDATE,
            decision_reason="Direct laptop candidate fits the line and price evidence best.",
            candidate_set_diagnosis=CandidateSetDiagnosis.CORRECT_CANDIDATE_PRESENT,
            final_classification=FinalClassification(
                selection_source=SelectionSource.RETRIEVED_CANDIDATE,
                code="43211503",
                label="Laptop computers",
                source_candidate_code=None,
                source_candidate_label=None,
                fit=ClassificationFit.STRONG,
                classification_confidence=ClassificationConfidence.HIGH,
                selection_reason="The target line and pricing support laptop computers rather than stationery.",
                alternative_rejection_summary="Broader computer equipment candidates were less specific.",
            ),
            re_search_unspsc=None,
            web_search=None,
            unable_to_resolve=None,
            rule_ids_used=[],
        )


class BrokenEvaluationClient:
    def run(self, request):
        raise ValueError("exactly one decision payload must be populated")


class SequencedEvaluationClient:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = 0

    def run(self, request):
        response = self.responses[self.calls]
        self.calls += 1
        return response


class FakeWebSearchClient:
    def __init__(self):
        self.calls = 0
        self.last_request = None

    def run(self, request):
        self.calls += 1
        self.last_request = request
        return WebSearchResult(
            query=request.query,
            summary="Model XJ-44592 is a laptop computer product line.",
            snippets=["XJ-44592 laptop computer"],
            metadata={"source": "test"},
        )


class FakeWebReidentifyClient:
    def __init__(self):
        self.calls = 0
        self.last_request = None

    def run(self, request: WebReidentifyRequest):
        self.calls += 1
        self.last_request = request
        return IdentifySearchResponse(
            item_hypothesis=ItemHypothesis(
                understanding_confidence=UnderstandingConfidence.MEDIUM,
                item_nature=ItemNature.PHYSICAL_GOOD,
                primary_identity="laptop computer",
                identity_explanation="Web result clarified the model identifier.",
                interpretation=Interpretation(
                    what_it_is="Likely a laptop computer.",
                    what_it_is_not=["unknown equipment"],
                    ambiguity=[],
                ),
            ),
            evidence_usage=EvidenceUsage(
                target_line_fields_used=[],
                other_evidence_used=[],
                context_dependency=ContextDependency.MEDIUM,
            ),
            candidate_evaluation_warnings=[],
            web_search_signal=WebSearchSignal(
                web_search_candidate=False,
                suggested_web_query=None,
            ),
            unspsc_search_queries=[
                UnspscSearchQuery(
                    query="laptop computer",
                    query_type=QueryType.SPECIFIC,
                    priority=1,
                    reason="web-reidentified primary identity",
                ),
                UnspscSearchQuery(
                    query="computer equipment",
                    query_type=QueryType.BROAD,
                    priority=2,
                    reason="fallback",
                ),
            ],
        )


class FakeEnrichmentService:
    def __init__(self):
        self.calls = []

    def enrich_supplier(self, supplier_raw: str):
        self.calls.append(supplier_raw)
        return SupplierEnrichmentResult(
            supplier_raw=supplier_raw,
            supplier_normalized="acme ltd",
            companies_house_number="12345678",
            company_name="Acme Ltd",
            sic_codes=["62012"],
            sic_labels=["Business software development"],
            vat_number=None,
            match_method="exact_normalized_name",
            match_confidence=1.0,
        )


class PipelineServiceTests(unittest.TestCase):
    def test_pre_agentic_hit_short_circuits_pipeline(self):
        service = LineItemPipelineService(
            pre_agentic_service=FakePreAgenticService({"resolved_by": "STABLE_LOOKUP"}),
            identify_client=FakeIdentifyClient(),
            search_tool=FakeSearchTool(),
        )

        result = service.process(
            LineItemPipelineInput(
                org_id="org-1",
                supplier_raw="Acme Ltd",
                line_item_raw="VAT",
            )
        )

        self.assertEqual(result.stage, "PRE_AGENTIC_HIT")
        self.assertEqual(result.pre_agentic_result["resolved_by"], "STABLE_LOOKUP")
        self.assertIsNone(result.identify_search_result)
        self.assertIsNone(result.retrieval_result)
        self.assertIsNone(result.evaluation_result)
        self.assertEqual(result.final_result["resolved_by"], "STABLE_LOOKUP")

    def test_pre_agentic_miss_runs_identify_and_search(self):
        service = LineItemPipelineService(
            pre_agentic_service=FakePreAgenticService(None),
            identify_client=FakeIdentifyClient(),
            search_tool=FakeSearchTool(),
        )

        result = service.process(
            LineItemPipelineInput(
                org_id="org-1",
                supplier_raw="Acme Ltd",
                line_item_raw="Notebook",
                unit_price=1200,
            )
        )

        self.assertEqual(result.stage, "RETRIEVAL_COMPLETE")
        self.assertIsNone(result.pre_agentic_result)
        self.assertEqual(result.identify_search_result["item_hypothesis"]["primary_identity"], "laptop computer")
        self.assertEqual(result.retrieval_result["candidates"][0]["code"], "43211503")
        self.assertIsNone(result.evaluation_result)

    def test_pipeline_runs_evaluation_when_client_is_provided(self):
        service = LineItemPipelineService(
            pre_agentic_service=FakePreAgenticService(None),
            identify_client=FakeIdentifyClient(),
            search_tool=FakeSearchTool(),
            evaluation_client=FakeEvaluationClient(),
            solution_repo=InMemoryLineItemSolutionRepository(),
        )

        result = service.process(
            LineItemPipelineInput(
                org_id="org-1",
                supplier_raw="Acme Ltd",
                line_item_raw="Notebook",
                unit_price=1200,
            )
        )

        self.assertEqual(result.stage, "MATCH_OBTAINED")
        self.assertEqual(result.evaluation_result["decision"], "select_candidate")
        self.assertEqual(result.evaluation_result["final_classification"]["code"], "43211503")
        self.assertEqual(result.final_result["unspsc_code"], "43211503")
        self.assertEqual(result.final_result["solved_for"], ["org-1"])
        self.assertEqual(result.final_result["resolved_by"], "AGENTIC_EVALUATION_SELECT_CANDIDATE")

    def test_evaluation_error_returns_unresolved_instead_of_crashing(self):
        service = LineItemPipelineService(
            pre_agentic_service=FakePreAgenticService(None),
            identify_client=FakeIdentifyClient(),
            search_tool=FakeSearchTool(),
            evaluation_client=BrokenEvaluationClient(),
        )

        result = service.process(
            LineItemPipelineInput(
                org_id="org-1",
                supplier_raw="Unknown Supplier",
                line_item_raw="xxxxxxxxxx",
                unit_price=1200,
            )
        )

        self.assertEqual(result.stage, "UNABLE_TO_RESOLVE")
        self.assertEqual(result.final_result["resolved_by"], "AGENTIC_EVALUATION_ERROR")
        self.assertIn("exactly one decision payload must be populated", result.final_result["reason"])

    def test_pre_agentic_only_mode_returns_miss_without_running_agentic(self):
        service = LineItemPipelineService(
            pre_agentic_service=FakePreAgenticService(None),
            identify_client=FakeIdentifyClient(),
            search_tool=FakeSearchTool(),
        )

        result = service.process(
            LineItemPipelineInput(
                org_id="org-1",
                supplier_raw="Acme Ltd",
                line_item_raw="Notebook",
            ),
            run_until_stage=LineItemPipelineService.RUN_UNTIL_PRE_AGENTIC,
        )

        self.assertEqual(result.stage, "PRE_AGENTIC_MISS")
        self.assertEqual(result.final_result["resolved_by"], "PRE_AGENTIC_MISS")
        self.assertIsNone(result.identify_search_result)

    def test_identify_only_mode_returns_identify_output(self):
        service = LineItemPipelineService(
            pre_agentic_service=FakePreAgenticService(None),
            identify_client=FakeIdentifyClient(),
            search_tool=FakeSearchTool(),
        )

        result = service.process(
            LineItemPipelineInput(
                org_id="org-1",
                supplier_raw="Acme Ltd",
                line_item_raw="Notebook",
            ),
            run_until_stage=LineItemPipelineService.RUN_UNTIL_IDENTIFY,
        )

        self.assertEqual(result.stage, "IDENTIFY_COMPLETE")
        self.assertEqual(result.final_result["resolved_by"], "AGENTIC_IDENTIFY_SEARCH")
        self.assertEqual(result.identify_search_result["item_hypothesis"]["primary_identity"], "laptop computer")
        self.assertIsNone(result.retrieval_result)

    def test_search_only_mode_returns_retrieval_output(self):
        service = LineItemPipelineService(
            pre_agentic_service=FakePreAgenticService(None),
            identify_client=FakeIdentifyClient(),
            search_tool=FakeSearchTool(),
        )

        result = service.process(
            LineItemPipelineInput(
                org_id="org-1",
                supplier_raw="Acme Ltd",
                line_item_raw="Notebook",
            ),
            run_until_stage=LineItemPipelineService.RUN_UNTIL_SEARCH,
        )

        self.assertEqual(result.stage, "RETRIEVAL_COMPLETE")
        self.assertEqual(result.final_result["resolved_by"], "AGENTIC_UNSPSC_SEARCH")
        self.assertEqual(result.retrieval_result["candidates"][0]["code"], "43211503")
        self.assertIsNone(result.evaluation_result)

    def test_evaluate_only_mode_returns_evaluation_output(self):
        service = LineItemPipelineService(
            pre_agentic_service=FakePreAgenticService(None),
            identify_client=FakeIdentifyClient(),
            search_tool=FakeSearchTool(),
            evaluation_client=FakeEvaluationClient(),
        )

        result = service.process(
            LineItemPipelineInput(
                org_id="org-1",
                supplier_raw="Acme Ltd",
                line_item_raw="Notebook",
            ),
            run_until_stage=LineItemPipelineService.RUN_UNTIL_EVALUATE,
        )

        self.assertEqual(result.stage, "EVALUATION_COMPLETE")
        self.assertEqual(result.final_result["resolved_by"], "AGENTIC_EVALUATE_CANDIDATES")
        self.assertEqual(result.evaluation_result["decision"], "select_candidate")

    def test_enrichment_injects_supplier_sic_when_missing_from_input(self):
        identify_client = FakeIdentifyClient()
        service = LineItemPipelineService(
            pre_agentic_service=FakePreAgenticService(None),
            identify_client=identify_client,
            search_tool=FakeSearchTool(),
            enrichment_service=FakeEnrichmentService(),
        )

        result = service.process(
            LineItemPipelineInput(
                org_id="org-1",
                supplier_raw="Acme Ltd",
                line_item_raw="Notebook",
            ),
            run_until_stage=LineItemPipelineService.RUN_UNTIL_IDENTIFY,
        )

        self.assertEqual(result.stage, "IDENTIFY_COMPLETE")
        self.assertEqual(
            identify_client.last_request.invoice_context.supplier_sic_label,
            "Business software development",
        )

    def test_enrichment_is_skipped_for_blank_supplier(self):
        identify_client = FakeIdentifyClient()
        enrichment_service = FakeEnrichmentService()
        service = LineItemPipelineService(
            pre_agentic_service=FakePreAgenticService(None),
            identify_client=identify_client,
            search_tool=FakeSearchTool(),
            enrichment_service=enrichment_service,
        )

        result = service.process(
            LineItemPipelineInput(
                org_id="org-1",
                supplier_raw="   ",
                line_item_raw="Disposable paper coveralls",
            ),
            run_until_stage=LineItemPipelineService.RUN_UNTIL_IDENTIFY,
        )

        self.assertEqual(result.stage, "IDENTIFY_COMPLETE")
        self.assertEqual(enrichment_service.calls, [])
        self.assertIsNone(identify_client.last_request.invoice_context.supplier_sic_label)

    def test_research_loop_runs_second_search_and_then_selects(self):
        search_tool = FakeSearchTool()
        evaluation_client = SequencedEvaluationClient(
            [
                EvaluateCandidatesResponse(
                    decision=EvaluationDecision.RE_SEARCH_UNSPSC,
                    decision_reason="Need tighter search terms.",
                    candidate_set_diagnosis=CandidateSetDiagnosis.RIGHT_AREA_WRONG_SIBLING,
                    final_classification=None,
                    re_search_unspsc=ReSearchUnspsc(
                        new_search_direction="Search more specifically for laptop computers.",
                        queries_to_try=[
                            EvaluationSearchQuery(query="laptop computers", priority=1),
                            EvaluationSearchQuery(query="portable computers", priority=2),
                        ],
                    ),
                    web_search=None,
                    unable_to_resolve=None,
                    rule_ids_used=[],
                ),
                FakeEvaluationClient().run(None),
            ]
        )
        service = LineItemPipelineService(
            pre_agentic_service=FakePreAgenticService(None),
            identify_client=FakeIdentifyClient(),
            search_tool=search_tool,
            evaluation_client=evaluation_client,
            solution_repo=InMemoryLineItemSolutionRepository(),
        )

        result = service.process(
            LineItemPipelineInput(
                org_id="org-1",
                supplier_raw="Acme Ltd",
                line_item_raw="Notebook",
                unit_price=1200,
            )
        )

        self.assertEqual(result.stage, "MATCH_OBTAINED")
        self.assertEqual(search_tool.calls[0], ["laptop computer", "computer equipment"])
        self.assertEqual(search_tool.calls[1], ["laptop computers", "portable computers"])
        self.assertEqual(evaluation_client.calls, 2)

    def test_duplicate_research_queries_end_unresolved(self):
        search_tool = FakeSearchTool()
        evaluation_client = SequencedEvaluationClient(
            [
                EvaluateCandidatesResponse(
                    decision=EvaluationDecision.RE_SEARCH_UNSPSC,
                    decision_reason="Need another search.",
                    candidate_set_diagnosis=CandidateSetDiagnosis.NO_VIABLE_CANDIDATE,
                    final_classification=None,
                    re_search_unspsc=ReSearchUnspsc(
                        new_search_direction="Retry same terms.",
                        queries_to_try=[
                            EvaluationSearchQuery(query="laptop computer", priority=1),
                            EvaluationSearchQuery(query="computer equipment", priority=2),
                        ],
                    ),
                    web_search=None,
                    unable_to_resolve=None,
                    rule_ids_used=[],
                ),
            ]
        )
        service = LineItemPipelineService(
            pre_agentic_service=FakePreAgenticService(None),
            identify_client=FakeIdentifyClient(),
            search_tool=search_tool,
            evaluation_client=evaluation_client,
        )

        result = service.process(
            LineItemPipelineInput(
                org_id="org-1",
                supplier_raw="Acme Ltd",
                line_item_raw="Notebook",
                unit_price=1200,
            )
        )

        self.assertEqual(result.stage, "UNABLE_TO_RESOLVE")
        self.assertIn("duplicate suppression", result.final_result["reason"])

    def test_web_search_loop_re_identifies_then_selects(self):
        class WebFirstIdentifyClient(FakeIdentifyClient):
            def __init__(self):
                self.calls = 0

            def run(self, request):
                self.calls += 1
                if self.calls == 1:
                    return IdentifySearchResponse(
                        item_hypothesis=ItemHypothesis(
                            understanding_confidence=UnderstandingConfidence.LOW,
                            item_nature=ItemNature.UNKNOWN,
                            primary_identity="unknown model code",
                            identity_explanation="Raw text is identifier-like.",
                            interpretation=Interpretation(
                                what_it_is="Unknown product reference.",
                                what_it_is_not=[],
                                ambiguity=["Model not understood"],
                            ),
                        ),
                        evidence_usage=EvidenceUsage(
                            target_line_fields_used=[],
                            other_evidence_used=[],
                            context_dependency=ContextDependency.LOW,
                        ),
                        candidate_evaluation_warnings=[],
                        web_search_signal=WebSearchSignal(
                            web_search_candidate=True,
                            suggested_web_query="XJ-44592",
                        ),
                        unspsc_search_queries=[
                            UnspscSearchQuery(
                                query="unknown equipment",
                                query_type=QueryType.BROAD,
                                priority=1,
                                reason="fallback",
                            )
                        ],
                    )
                return super().run(request)

        evaluation_client = SequencedEvaluationClient(
            [
                EvaluateCandidatesResponse(
                    decision=EvaluationDecision.WEB_SEARCH,
                    decision_reason="Need web lookup for identifier.",
                    candidate_set_diagnosis=CandidateSetDiagnosis.ITEM_IDENTITY_UNRESOLVED,
                    final_classification=None,
                    re_search_unspsc=None,
                    web_search=WebSearchInstruction(
                        query_basis=WebQueryBasis.VISIBLE_IDENTIFIER,
                        query="XJ-44592",
                    ),
                    unable_to_resolve=None,
                    rule_ids_used=[],
                ),
                FakeEvaluationClient().run(None),
            ]
        )
        web_reidentify_client = FakeWebReidentifyClient()
        service = LineItemPipelineService(
            pre_agentic_service=FakePreAgenticService(None),
            identify_client=WebFirstIdentifyClient(),
            search_tool=FakeSearchTool(),
            evaluation_client=evaluation_client,
            web_search_client=FakeWebSearchClient(),
            web_reidentify_client=web_reidentify_client,
            solution_repo=InMemoryLineItemSolutionRepository(),
        )

        result = service.process(
            LineItemPipelineInput(
                org_id="org-1",
                supplier_raw="Acme Ltd",
                line_item_raw="XJ-44592",
                unit_price=1200,
            )
        )

        self.assertEqual(result.stage, "MATCH_OBTAINED")
        self.assertEqual(result.evaluation_result["decision"], "select_candidate")
        self.assertEqual(web_reidentify_client.calls, 1)
        self.assertEqual(web_reidentify_client.last_request.web_search_result.query, "XJ-44592")

    def test_web_search_only_mode_returns_web_lookup_output(self):
        evaluation_client = SequencedEvaluationClient(
            [
                EvaluateCandidatesResponse(
                    decision=EvaluationDecision.WEB_SEARCH,
                    decision_reason="Need web lookup for identifier.",
                    candidate_set_diagnosis=CandidateSetDiagnosis.ITEM_IDENTITY_UNRESOLVED,
                    final_classification=None,
                    re_search_unspsc=None,
                    web_search=WebSearchInstruction(
                        query_basis=WebQueryBasis.VISIBLE_IDENTIFIER,
                        query="XJ-44592",
                    ),
                    unable_to_resolve=None,
                    rule_ids_used=[],
                ),
            ]
        )
        web_search_client = FakeWebSearchClient()
        service = LineItemPipelineService(
            pre_agentic_service=FakePreAgenticService(None),
            identify_client=type("WebFirstIdentifyClient", (FakeIdentifyClient,), {
                "__init__": lambda self: setattr(self, "calls", 0),
                "run": lambda self, request: IdentifySearchResponse(
                    item_hypothesis=ItemHypothesis(
                        understanding_confidence=UnderstandingConfidence.LOW,
                        item_nature=ItemNature.UNKNOWN,
                        primary_identity="unknown model code",
                        identity_explanation="Raw text is identifier-like.",
                        interpretation=Interpretation(
                            what_it_is="Unknown product reference.",
                            what_it_is_not=[],
                            ambiguity=["Model not understood"],
                        ),
                    ),
                    evidence_usage=EvidenceUsage(
                        target_line_fields_used=[],
                        other_evidence_used=[],
                        context_dependency=ContextDependency.LOW,
                    ),
                    candidate_evaluation_warnings=[],
                    web_search_signal=WebSearchSignal(
                        web_search_candidate=True,
                        suggested_web_query="XJ-44592",
                    ),
                    unspsc_search_queries=[
                        UnspscSearchQuery(
                            query="unknown equipment",
                            query_type=QueryType.BROAD,
                            priority=1,
                            reason="fallback",
                        )
                    ],
                ),
            })(),
            search_tool=FakeSearchTool(),
            evaluation_client=evaluation_client,
            web_search_client=web_search_client,
            web_reidentify_client=FakeWebReidentifyClient(),
        )

        result = service.process(
            LineItemPipelineInput(
                org_id="org-1",
                supplier_raw="Acme Ltd",
                line_item_raw="XJ-44592",
            ),
            run_until_stage=LineItemPipelineService.RUN_UNTIL_WEB_SEARCH,
        )

        self.assertEqual(result.stage, "WEB_SEARCH_COMPLETE")
        self.assertEqual(result.final_result["resolved_by"], "AGENTIC_WEB_SEARCH")
        self.assertEqual(result.final_result["web_search_result"]["query"], "XJ-44592")
        self.assertEqual(web_search_client.calls, 1)

    def test_web_reidentify_only_mode_returns_reidentified_queries(self):
        class WebFirstIdentifyClient(FakeIdentifyClient):
            def __init__(self):
                self.calls = 0

            def run(self, request):
                self.calls += 1
                if self.calls == 1:
                    return IdentifySearchResponse(
                        item_hypothesis=ItemHypothesis(
                            understanding_confidence=UnderstandingConfidence.LOW,
                            item_nature=ItemNature.UNKNOWN,
                            primary_identity="unknown model code",
                            identity_explanation="Raw text is identifier-like.",
                            interpretation=Interpretation(
                                what_it_is="Unknown product reference.",
                                what_it_is_not=[],
                                ambiguity=["Model not understood"],
                            ),
                        ),
                        evidence_usage=EvidenceUsage(
                            target_line_fields_used=[],
                            other_evidence_used=[],
                            context_dependency=ContextDependency.LOW,
                        ),
                        candidate_evaluation_warnings=[],
                        web_search_signal=WebSearchSignal(
                            web_search_candidate=True,
                            suggested_web_query="XJ-44592",
                        ),
                        unspsc_search_queries=[
                            UnspscSearchQuery(
                                query="unknown equipment",
                                query_type=QueryType.BROAD,
                                priority=1,
                                reason="fallback",
                            )
                        ],
                    )
                return super().run(request)

        evaluation_client = SequencedEvaluationClient(
            [
                EvaluateCandidatesResponse(
                    decision=EvaluationDecision.WEB_SEARCH,
                    decision_reason="Need web lookup for identifier.",
                    candidate_set_diagnosis=CandidateSetDiagnosis.ITEM_IDENTITY_UNRESOLVED,
                    final_classification=None,
                    re_search_unspsc=None,
                    web_search=WebSearchInstruction(
                        query_basis=WebQueryBasis.VISIBLE_IDENTIFIER,
                        query="XJ-44592",
                    ),
                    unable_to_resolve=None,
                    rule_ids_used=[],
                ),
            ]
        )
        service = LineItemPipelineService(
            pre_agentic_service=FakePreAgenticService(None),
            identify_client=WebFirstIdentifyClient(),
            search_tool=FakeSearchTool(),
            evaluation_client=evaluation_client,
            web_search_client=FakeWebSearchClient(),
            web_reidentify_client=FakeWebReidentifyClient(),
        )

        result = service.process(
            LineItemPipelineInput(
                org_id="org-1",
                supplier_raw="Acme Ltd",
                line_item_raw="XJ-44592",
            ),
            run_until_stage=LineItemPipelineService.RUN_UNTIL_WEB_REIDENTIFY,
        )

        self.assertEqual(result.stage, "WEB_REIDENTIFY_COMPLETE")
        self.assertEqual(result.final_result["resolved_by"], "AGENTIC_WEB_REIDENTIFY")
        self.assertEqual(result.final_result["web_search_result"]["query"], "XJ-44592")
        self.assertEqual(
            result.identify_search_result["unspsc_search_queries"][0]["query"],
            "laptop computer",
        )


if __name__ == "__main__":
    unittest.main()
