import sys
import unittest
from pathlib import Path


sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.evaluation.house_rules import apply_house_rule_guards
from app.evaluation.models import (
    CandidateSetDiagnosis,
    ClassificationConfidence,
    ClassificationFit,
    EvaluateCandidatesRequest,
    EvaluateCandidatesResponse,
    EvaluationDecision,
    FinalClassification,
    SelectionSource,
)
from app.house_rules import DEFAULT_HOUSE_RULES, merge_house_rules
from app.identify_search.models import IdentifySearchRequest, IdentifySearchResponse


def make_identify_request(item_raw_row: str = "Boiler service") -> IdentifySearchRequest:
    return IdentifySearchRequest.from_dict(
        {
            "global_config": {
                "max_unspsc_search_queries": 3,
                "web_search_allowed": True,
            },
            "target_line": {
                "item_raw_row": item_raw_row,
                "description_clean": item_raw_row.lower(),
                "unit_of_measure_raw": "ea",
                "quantity": {"value": 1},
                "unit_price": {"value": 1200},
                "line_subtotal": {"value": 1200},
            },
            "invoice_context": {
                "supplier_name": "Acme Ltd",
                "unspsc_ready_invoice_description": "Maintenance services",
                "supplier_sic_label": None,
                "buyer_sic_label": None,
            },
            "house_rules": [],
        }
    )


def make_identify_response(item_nature: str = "service", primary_identity: str = "boiler service") -> IdentifySearchResponse:
    return IdentifySearchResponse.from_dict(
        {
            "item_hypothesis": {
                "understanding_confidence": "medium",
                "item_nature": item_nature,
                "primary_identity": primary_identity,
                "identity_explanation": "Line indicates service.",
                "interpretation": {
                    "what_it_is": primary_identity,
                    "what_it_is_not": [],
                    "ambiguity": [],
                },
            },
            "evidence_usage": {
                "target_line_fields_used": ["item_raw_row"],
                "other_evidence_used": [],
                "context_dependency": "low",
            },
            "candidate_evaluation_warnings": [],
            "web_search_signal": {
                "web_search_candidate": False,
                "suggested_web_query": None,
            },
            "unspsc_search_queries": [
                {
                    "query": primary_identity,
                    "query_type": "specific",
                    "priority": 1,
                    "reason": "primary",
                },
                {
                    "query": "maintenance service",
                    "query_type": "broad",
                    "priority": 2,
                    "reason": "fallback",
                },
            ],
        }
    )


def make_search_output():
    return {
        "unspsc_version": "test-v1",
        "queries_searched": [{"query": "boiler service", "priority": 1}],
        "retrieval_metadata": {
            "retrieval_methods": ["exact", "lexical", "semantic"],
            "fusion_method": "rrf",
            "max_candidates_per_query": 10,
            "max_candidates_total": 30,
            "candidate_count": 1,
        },
        "candidates": [
            {
                "rank": 1,
                "retrieval_score": 1.0,
                "code": "40102001",
                "label": "Boilers",
                "level": "commodity",
                "hierarchy_path": {
                    "segment": {"code": "40000000", "label": "Distribution and Conditioning Systems and Equipment"},
                    "family": {"code": "40100000", "label": "Heating and ventilation and air circulation"},
                    "class": {"code": "40102000", "label": "Boilers"},
                    "commodity": {"code": "40102001", "label": "Boilers"},
                },
                "code_description": None,
                "code_aliases": [],
                "matched_queries": [{"query": "boiler service", "priority": 1}],
                "specific_rules": [],
            }
        ],
    }


class HouseRulesTests(unittest.TestCase):
    def test_merge_house_rules_includes_defaults_and_deduplicates(self):
        merged = merge_house_rules(
            [
                {"rule_name": "HR001", "rule": "overridden duplicate"},
                {"rule_name": "HR900", "rule": "Custom rule"},
            ]
        )

        self.assertEqual(merged[0]["rule_name"], "HR001")
        self.assertEqual(len([rule for rule in merged if rule["rule_name"] == "HR001"]), 1)
        self.assertTrue(any(rule["rule_name"] == "HR900" for rule in merged))
        self.assertEqual(len(merged), len(DEFAULT_HOUSE_RULES) + 1)

    def test_service_rule_guard_researches_when_model_selects_physical_good(self):
        request = EvaluateCandidatesRequest(
            identify_search_input=make_identify_request(),
            identify_search_output=make_identify_response(),
            unspsc_search_output=make_search_output(),
        )
        response = EvaluateCandidatesResponse(
            decision=EvaluationDecision.SELECT_CANDIDATE,
            decision_reason="Boiler candidate was highest ranked.",
            candidate_set_diagnosis=CandidateSetDiagnosis.CORRECT_CANDIDATE_PRESENT,
            final_classification=FinalClassification(
                selection_source=SelectionSource.RETRIEVED_CANDIDATE,
                code="40102001",
                label="Boilers",
                source_candidate_code=None,
                source_candidate_label=None,
                fit=ClassificationFit.ACCEPTABLE,
                classification_confidence=ClassificationConfidence.MEDIUM,
                selection_reason="Picked boiler equipment candidate.",
                alternative_rejection_summary=None,
            ),
            re_search_unspsc=None,
            web_search=None,
            unable_to_resolve=None,
            rule_ids_used=[],
        )

        guarded = apply_house_rule_guards(request, response)

        self.assertEqual(guarded.decision, EvaluationDecision.RE_SEARCH_UNSPSC)
        self.assertIn("HR007", guarded.rule_ids_used)
        self.assertIn("service", guarded.re_search_unspsc.new_search_direction.lower())

    def test_parent_override_when_child_is_too_specific(self):
        request = EvaluateCandidatesRequest(
            identify_search_input=make_identify_request(item_raw_row="Laptop"),
            identify_search_output=make_identify_response(item_nature="physical_good", primary_identity="laptop"),
            unspsc_search_output={
                "unspsc_version": "test-v1",
                "queries_searched": [{"query": "laptop", "priority": 1}],
                "retrieval_metadata": {
                    "retrieval_methods": ["exact", "lexical", "semantic"],
                    "fusion_method": "rrf",
                    "max_candidates_per_query": 10,
                    "max_candidates_total": 30,
                    "candidate_count": 1,
                },
                "candidates": [
                    {
                        "rank": 1,
                        "retrieval_score": 1.0,
                        "code": "43211509",
                        "label": "Ruggedised laptop computers",
                        "level": "commodity",
                        "hierarchy_path": {
                            "segment": {"code": "43000000", "label": "IT"},
                            "family": {"code": "43210000", "label": "Computer equipment"},
                            "class": {"code": "43211500", "label": "Computers"},
                            "commodity": {"code": "43211509", "label": "Ruggedised laptop computers"},
                        },
                        "code_description": None,
                        "code_aliases": [],
                        "matched_queries": [{"query": "laptop", "priority": 1}],
                        "specific_rules": [],
                    }
                ],
            },
        )
        response = EvaluateCandidatesResponse(
            decision=EvaluationDecision.SELECT_CANDIDATE,
            decision_reason="Selected top commodity.",
            candidate_set_diagnosis=CandidateSetDiagnosis.CORRECT_CANDIDATE_PRESENT,
            final_classification=FinalClassification(
                selection_source=SelectionSource.RETRIEVED_CANDIDATE,
                code="43211509",
                label="Ruggedised laptop computers",
                source_candidate_code=None,
                source_candidate_label=None,
                fit=ClassificationFit.ACCEPTABLE,
                classification_confidence=ClassificationConfidence.MEDIUM,
                selection_reason="Selected top commodity.",
                alternative_rejection_summary=None,
            ),
            re_search_unspsc=None,
            web_search=None,
            unable_to_resolve=None,
            rule_ids_used=[],
        )

        guarded = apply_house_rule_guards(request, response)

        self.assertEqual(guarded.decision, EvaluationDecision.SELECT_CANDIDATE)
        self.assertEqual(guarded.final_classification.selection_source.value, "hierarchy_parent")
        self.assertEqual(guarded.final_classification.code, "43211500")
        self.assertIn("HR017", guarded.rule_ids_used)

    def test_part_accessory_rule_forces_research(self):
        request = EvaluateCandidatesRequest(
            identify_search_input=make_identify_request(item_raw_row="Printer toner"),
            identify_search_output=make_identify_response(item_nature="physical_good", primary_identity="printer toner"),
            unspsc_search_output={
                "unspsc_version": "test-v1",
                "queries_searched": [{"query": "printer toner", "priority": 1}],
                "retrieval_metadata": {
                    "retrieval_methods": ["exact", "lexical", "semantic"],
                    "fusion_method": "rrf",
                    "max_candidates_per_query": 10,
                    "max_candidates_total": 30,
                    "candidate_count": 1,
                },
                "candidates": [
                    {
                        "rank": 1,
                        "retrieval_score": 1.0,
                        "code": "43212100",
                        "label": "Printers",
                        "level": "class",
                        "hierarchy_path": {
                            "segment": {"code": "43000000", "label": "IT"},
                            "family": {"code": "43210000", "label": "Computer equipment"},
                            "class": {"code": "43212100", "label": "Printers"},
                            "commodity": None,
                        },
                        "code_description": None,
                        "code_aliases": [],
                        "matched_queries": [{"query": "printer toner", "priority": 1}],
                        "specific_rules": [],
                    }
                ],
            },
        )
        response = EvaluateCandidatesResponse(
            decision=EvaluationDecision.SELECT_CANDIDATE,
            decision_reason="Selected printer candidate.",
            candidate_set_diagnosis=CandidateSetDiagnosis.CORRECT_CANDIDATE_PRESENT,
            final_classification=FinalClassification(
                selection_source=SelectionSource.RETRIEVED_CANDIDATE,
                code="43212100",
                label="Printers",
                source_candidate_code=None,
                source_candidate_label=None,
                fit=ClassificationFit.ACCEPTABLE,
                classification_confidence=ClassificationConfidence.MEDIUM,
                selection_reason="Selected printer candidate.",
                alternative_rejection_summary=None,
            ),
            re_search_unspsc=None,
            web_search=None,
            unable_to_resolve=None,
            rule_ids_used=[],
        )

        guarded = apply_house_rule_guards(request, response)

        self.assertEqual(guarded.decision, EvaluationDecision.RE_SEARCH_UNSPSC)
        self.assertIn("HR004", guarded.rule_ids_used)
        self.assertIn("accessory", guarded.re_search_unspsc.new_search_direction.lower())


if __name__ == "__main__":
    unittest.main()
