import sys
import unittest
from pathlib import Path


sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.evaluation.client import _normalize_evaluate_candidates_payload
from app.evaluation.models import (
    EvaluateCandidatesRequest,
    EvaluateCandidatesResponse,
    EvaluationDecision,
)
from app.identify_search.models import IdentifySearchRequest, IdentifySearchResponse


def make_identify_request() -> IdentifySearchRequest:
    return IdentifySearchRequest.from_dict(
        {
            "global_config": {
                "max_unspsc_search_queries": 3,
                "web_search_allowed": True,
            },
            "target_line": {
                "item_raw_row": "Notebook",
                "description_clean": "notebook",
                "unit_of_measure_raw": "ea",
                "quantity": {"value": 1},
                "unit_price": {"value": 1200},
                "line_subtotal": {"value": 1200},
            },
            "invoice_context": {
                "supplier_name": "Acme Ltd",
                "unspsc_ready_invoice_description": "Office equipment",
                "supplier_sic_label": None,
                "buyer_sic_label": None,
            },
            "house_rules": [],
        }
    )


def make_identify_response() -> IdentifySearchResponse:
    return IdentifySearchResponse.from_dict(
        {
            "item_hypothesis": {
                "understanding_confidence": "medium",
                "item_nature": "physical_good",
                "primary_identity": "laptop computer",
                "identity_explanation": "High unit price supports laptop meaning.",
                "interpretation": {
                    "what_it_is": "Likely a laptop computer",
                    "what_it_is_not": ["paper notebook"],
                    "ambiguity": [],
                },
            },
            "evidence_usage": {
                "target_line_fields_used": ["item_raw_row", "unit_price"],
                "other_evidence_used": [],
                "context_dependency": "low",
            },
            "candidate_evaluation_warnings": [
                {
                    "warning_category": "price_disambiguation",
                    "warning": "Avoid stationery notebook candidates.",
                }
            ],
            "web_search_signal": {
                "web_search_candidate": False,
                "suggested_web_query": None,
            },
            "unspsc_search_queries": [
                {
                    "query": "laptop computer",
                    "query_type": "specific",
                    "priority": 1,
                    "reason": "primary",
                },
                {
                    "query": "computer equipment",
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
        "queries_searched": [{"query": "laptop computer", "priority": 1}],
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
                "code": "43211503",
                "label": "Laptop computers",
                "level": "commodity",
                "hierarchy_path": {
                    "segment": {"code": "43000000", "label": "Information Technology Broadcasting and Telecommunications"},
                    "family": {"code": "43210000", "label": "Computer Equipment and Accessories"},
                    "class": {"code": "43211500", "label": "Computers"},
                    "commodity": {"code": "43211503", "label": "Laptop computers"},
                },
                "code_description": None,
                "code_aliases": ["notebook computer"],
                "matched_queries": [{"query": "laptop computer", "priority": 1}],
                "specific_rules": [],
            }
        ],
    }


class EvaluateCandidatesModelTests(unittest.TestCase):
    def test_normalizer_accepts_selected_code_and_reasoning_aliases(self):
        request = EvaluateCandidatesRequest(
            identify_search_input=make_identify_request(),
            identify_search_output=make_identify_response(),
            unspsc_search_output=make_search_output(),
        )

        normalized = _normalize_evaluate_candidates_payload(
            {
                "decision": "select_candidate",
                "selected_code": "43211503",
                "reasoning": "Laptop candidate fits best.",
            },
            request,
        )

        response = EvaluateCandidatesResponse.from_dict(normalized)

        self.assertEqual(response.decision, EvaluationDecision.SELECT_CANDIDATE)
        self.assertEqual(response.final_classification.code, "43211503")
        self.assertEqual(response.decision_reason, "Laptop candidate fits best.")

    def test_select_candidate_response_validates(self):
        request = EvaluateCandidatesRequest(
            identify_search_input=make_identify_request(),
            identify_search_output=make_identify_response(),
            unspsc_search_output=make_search_output(),
        )
        response = EvaluateCandidatesResponse.from_dict(
            {
                "decision": "select_candidate",
                "decision_reason": "Direct laptop candidate fits best.",
                "candidate_set_diagnosis": "correct_candidate_present",
                "final_classification": {
                    "selection_source": "retrieved_candidate",
                    "code": "43211503",
                    "label": "Laptop computers",
                    "source_candidate_code": None,
                    "source_candidate_label": None,
                    "fit": "strong",
                    "classification_confidence": "high",
                    "selection_reason": "Line and price support laptop computers.",
                    "alternative_rejection_summary": "Broader candidates were less specific.",
                },
                "re_search_unspsc": None,
                "web_search": None,
                "unable_to_resolve": None,
                "rule_ids_used": [],
            }
        )

        validated = response.validate_against_request(request)

        self.assertEqual(validated.decision, EvaluationDecision.SELECT_CANDIDATE)

    def test_research_respects_query_limit(self):
        request = EvaluateCandidatesRequest(
            identify_search_input=make_identify_request(),
            identify_search_output=make_identify_response(),
            unspsc_search_output=make_search_output(),
        )
        response = EvaluateCandidatesResponse.from_dict(
            {
                "decision": "re_search_unspsc",
                "decision_reason": "Current candidates are close but too broad.",
                "candidate_set_diagnosis": "candidates_too_general",
                "final_classification": None,
                "re_search_unspsc": {
                    "new_search_direction": "Search for laptop computers specifically.",
                    "queries_to_try": [
                        {"query": "laptop computer", "priority": 1},
                        {"query": "notebook computer", "priority": 2},
                        {"query": "portable computers", "priority": 3},
                        {"query": "office laptop devices", "priority": 4},
                    ],
                    "queries_to_avoid": [],
                    "candidate_patterns_to_prioritise": [],
                    "candidate_patterns_to_reject": [],
                },
                "web_search": None,
                "unable_to_resolve": None,
                "rule_ids_used": [],
            }
        )

        with self.assertRaises(ValueError):
            response.validate_against_request(request)


if __name__ == "__main__":
    unittest.main()
